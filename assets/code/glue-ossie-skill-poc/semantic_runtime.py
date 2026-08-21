import hashlib
import json
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import jsonschema
import yaml

from ossie_athena import compile_metric_query, parse_skill_manifest


class SemanticRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    database: str
    workgroup: str
    output_location: str
    skill_attachment: str
    allowed_contract_prefix: str
    query_timeout_seconds: int = 90
    poll_interval_seconds: float = 1.0


class SemanticRuntime:
    def __init__(self, config, glue, s3, athena, ossie_schema):
        self.config = config
        self.glue = glue
        self.s3 = s3
        self.athena = athena
        self.ossie_schema = ossie_schema
        self._discovered_contract_uri = None
        self._snapshot = {}

    @property
    def snapshot(self):
        return dict(self._snapshot)

    def _read_s3_uri(self, uri):
        location = urlparse(uri)
        if location.scheme != "s3" or not location.netloc or not location.path:
            raise SemanticRuntimeError("Only a complete s3 URI is allowed")
        return self.s3.get_object(
            Bucket=location.netloc,
            Key=location.path.lstrip("/"),
        )["Body"].read()

    def discover_semantic_contract(self, search_text):
        search = self.glue.search_assets(SearchText=search_text, MaxResults=10)
        data_asset = next(
            (
                item
                for item in search.get("Items", [])
                if item.get("AssetName") == "orders"
            ),
            None,
        )
        if data_asset is None:
            raise SemanticRuntimeError("The orders data asset was not found")

        asset = self.glue.get_asset(Identifier=data_asset["Id"])
        try:
            attachment = asset["Attachments"][self.config.skill_attachment]
            skill_id = json.loads(attachment["Content"])["assetIdentifiers"][0]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise SemanticRuntimeError(
                "The data asset has no usable related Skill"
            ) from exc

        skill = self.glue.get_asset(Identifier=skill_id)
        try:
            skill_uri = json.loads(
                skill["Forms"]["amazon::Skill"]["Content"]
            )["uri"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise SemanticRuntimeError("The Skill has no readable URI") from exc

        skill_bytes = self._read_s3_uri(skill_uri)
        manifest = parse_skill_manifest(skill_bytes.decode("utf-8"))
        contract_uri = manifest["semantic_contract_uri"]
        if not contract_uri.startswith(self.config.allowed_contract_prefix):
            raise SemanticRuntimeError("The contract URI is outside the allowed prefix")
        if manifest["semantic_contract_format"] != "apache-ossie":
            raise SemanticRuntimeError("The Skill does not declare an Apache Ossie contract")
        if manifest["target_engine"] != "athena":
            raise SemanticRuntimeError("The Skill does not target Athena")

        self._discovered_contract_uri = contract_uri
        contract_name = urlparse(contract_uri).path.rsplit("/", 1)[-1]
        discovered = {
            "skill_id": skill_id,
            "skill_document": urlparse(skill_uri).path.rsplit("/", 1)[-1],
            "skill_sha256": hashlib.sha256(skill_bytes).hexdigest(),
            "contract_uri": contract_uri,
            "contract_name": contract_name,
            "contract_format": manifest["semantic_contract_format"],
            "target_engine": manifest["target_engine"],
            "declared_tools": [
                manifest["compiler_tool"],
                manifest["execution_tool"],
            ],
        }
        self._snapshot.update(discovered)
        return discovered

    def compile_ossie_metric(self, contract_uri, metric_name, dimension_name):
        if contract_uri != self._discovered_contract_uri:
            raise SemanticRuntimeError(
                "The contract URI was not discovered from the related Skill"
            )

        contract_bytes = self._read_s3_uri(contract_uri)
        try:
            contract = yaml.safe_load(contract_bytes)
            jsonschema.validate(contract, self.ossie_schema)
        except (yaml.YAMLError, jsonschema.ValidationError) as exc:
            raise SemanticRuntimeError(
                "The Ossie contract failed schema validation"
            ) from exc
        sql = compile_metric_query(contract, metric_name, dimension_name)

        dimension_dataset = dimension_name.split(".", 1)[0]
        semantic_model = contract["semantic_model"][0]
        relationship = next(
            (
                item["name"]
                for item in semantic_model.get("relationships", [])
                if item.get("to") == dimension_dataset
            ),
            None,
        )
        if relationship is None:
            raise SemanticRuntimeError(
                f"No relationship targets dimension dataset: {dimension_dataset}"
            )

        compiled = {
            "contract_name": urlparse(contract_uri).path.rsplit("/", 1)[-1],
            "contract_sha256": hashlib.sha256(contract_bytes).hexdigest(),
            "contract_version": contract["version"],
            "metric": metric_name,
            "dimension": dimension_name,
            "relationship": relationship,
            "sql": sql,
            "sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        }
        self._snapshot.update(compiled)
        return compiled

    def _validate_read_only_sql(self, sql):
        normalized = sql.strip()
        if re.match(r"^SELECT\b", normalized, flags=re.IGNORECASE) is None:
            raise SemanticRuntimeError("Only a read-only SELECT is allowed")
        body = normalized[:-1] if normalized.endswith(";") else normalized
        if ";" in body or "--" in body or "/*" in body or "*/" in body:
            raise SemanticRuntimeError("Only one read-only SQL statement is allowed")

        table_pattern = re.compile(
            r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)",
            flags=re.IGNORECASE,
        )
        referenced_tables = set(table_pattern.findall(body))
        allowed_tables = {
            f"{self.config.database}.orders",
            f"{self.config.database}.customers",
        }
        if not referenced_tables or not referenced_tables.issubset(allowed_tables):
            raise SemanticRuntimeError("SQL references a table outside the allow-listed set")

    def execute_athena_query(self, sql):
        self._validate_read_only_sql(sql)
        query = self.athena.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={
                "Catalog": "AwsDataCatalog",
                "Database": self.config.database,
            },
            ResultConfiguration={"OutputLocation": self.config.output_location},
            WorkGroup=self.config.workgroup,
        )
        query_id = query["QueryExecutionId"]

        deadline = time.time() + self.config.query_timeout_seconds
        state = "QUEUED"
        execution = None
        while time.time() < deadline:
            execution = self.athena.get_query_execution(
                QueryExecutionId=query_id
            )["QueryExecution"]
            state = execution["Status"]["State"]
            if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                break
            time.sleep(self.config.poll_interval_seconds)
        else:
            raise SemanticRuntimeError("Athena query timed out")

        if state != "SUCCEEDED":
            reason = execution["Status"].get("StateChangeReason", "unknown")
            raise SemanticRuntimeError(f"Athena query ended in {state}: {reason}")

        result = self.athena.get_query_results(QueryExecutionId=query_id)
        rows = result["ResultSet"]["Rows"]
        headers = [item.get("VarCharValue") for item in rows[0]["Data"]]
        values = [
            dict(
                zip(
                    headers,
                    [item.get("VarCharValue") for item in row["Data"]],
                )
            )
            for row in rows[1:]
        ]
        completed = {
            "athena_state": state,
            "query_execution_id": query_id,
            "rows": values,
        }
        self._snapshot.update(completed)
        return completed
