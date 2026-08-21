import json
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import boto3
import jsonschema
import yaml

from ossie_athena import compile_metric_query, parse_skill_manifest


REGION = "us-west-2"
DATABASE = "heuristicwave_ossie_poc"
WORKGROUP = "heuristicwave-ossie-poc"
SKILL_IDENTIFIER = "sales-semantic-skill-ossie-poc"
SKILL_ATTACHMENT = "ossieSemanticContract"
OBJECT_PREFIX = "semantic-skill-ossie-poc"
OSSIE_COMMIT = "88e0011148283302c9a04cd0287e00e0b9d87354"
OSSIE_SCHEMA_URL = (
    "https://raw.githubusercontent.com/apache/ossie/"
    f"{OSSIE_COMMIT}/core-spec/osi-schema.json"
)


def main():
    base_dir = Path(__file__).resolve().parent
    contract_bytes = (base_dir / "sales.ossie.yaml").read_bytes()
    contract = yaml.safe_load(contract_bytes)

    with urllib.request.urlopen(OSSIE_SCHEMA_URL, timeout=30) as response:
        ossie_schema = json.load(response)
    jsonschema.validate(contract, ossie_schema)

    session = boto3.Session(profile_name="default", region_name=REGION)
    sts = session.client("sts")
    glue = session.client("glue")
    s3 = session.client("s3")
    athena = session.client("athena")

    account_id = sts.get_caller_identity()["Account"]
    orders_table = glue.get_table(DatabaseName=DATABASE, Name="orders")["Table"]
    orders_location = urlparse(orders_table["StorageDescriptor"]["Location"])
    bucket = orders_location.netloc

    contract_key = f"{OBJECT_PREFIX}/sales.ossie.yaml"
    skill_key = f"{OBJECT_PREFIX}/sales-semantic-skill.md"
    contract_uri = f"s3://{bucket}/{contract_key}"
    skill_uri = f"s3://{bucket}/{skill_key}"

    skill_markdown = (
        (base_dir / "sales-semantic-skill.md")
        .read_text(encoding="utf-8")
        .replace("s3://<bucket>/", f"s3://{bucket}/")
    )

    s3.put_object(
        Bucket=bucket,
        Key=contract_key,
        Body=contract_bytes,
        ContentType="application/yaml",
    )
    s3.put_object(
        Bucket=bucket,
        Key=skill_key,
        Body=skill_markdown.encode("utf-8"),
        ContentType="text/markdown; charset=utf-8",
    )

    glue.put_asset(
        AssetTypeId="amazon::Skill",
        Identifier=SKILL_IDENTIFIER,
        Name=SKILL_IDENTIFIER,
        Description="Skill that discovers the Apache Ossie sales contract",
        Forms={
            "amazon::Skill": {
                "FormTypeId": "amazon::Skill",
                "Content": json.dumps({"uri": skill_uri}),
            }
        },
    )

    table_arn = (
        f"arn:aws:glue:{REGION}:{account_id}:table/{DATABASE}/orders"
    )
    glue.put_attachment(
        AssetIdentifier=table_arn,
        AttachmentName=SKILL_ATTACHMENT,
        FormTypeId="amazon::RelatedTo",
        Content=json.dumps({"assetIdentifiers": [SKILL_IDENTIFIER]}),
    )

    search = glue.search_assets(SearchText="net revenue", MaxResults=10)
    orders_asset = next(
        item for item in search.get("Items", []) if item.get("AssetName") == "orders"
    )
    asset = glue.get_asset(Identifier=orders_asset["Id"])
    attachment = asset["Attachments"][SKILL_ATTACHMENT]
    related = json.loads(attachment["Content"])["assetIdentifiers"]
    if SKILL_IDENTIFIER not in related:
        raise RuntimeError("The orders asset did not return the expected Skill")

    skill_asset = glue.get_asset(Identifier=SKILL_IDENTIFIER)
    skill_form = skill_asset["Forms"]["amazon::Skill"]
    discovered_skill_uri = json.loads(skill_form["Content"])["uri"]
    skill_location = urlparse(discovered_skill_uri)
    discovered_skill = s3.get_object(
        Bucket=skill_location.netloc,
        Key=skill_location.path.lstrip("/"),
    )["Body"].read().decode("utf-8")
    manifest = parse_skill_manifest(discovered_skill)

    if manifest["semantic_contract_uri"] != contract_uri:
        raise RuntimeError("Skill points to an unexpected semantic contract")
    if manifest["compiler_tool"] != "compile_ossie_metric":
        raise RuntimeError("Skill requested an unsupported compiler tool")
    if manifest["execution_tool"] != "execute_athena_query":
        raise RuntimeError("Skill requested an unsupported execution tool")

    discovered_contract_location = urlparse(manifest["semantic_contract_uri"])
    discovered_contract = yaml.safe_load(
        s3.get_object(
            Bucket=discovered_contract_location.netloc,
            Key=discovered_contract_location.path.lstrip("/"),
        )["Body"].read()
    )
    jsonschema.validate(discovered_contract, ossie_schema)

    sql = compile_metric_query(
        discovered_contract,
        metric_name="net_revenue",
        dimension_name="customers.region",
    )

    query = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Catalog": "AwsDataCatalog", "Database": DATABASE},
        ResultConfiguration={
            "OutputLocation": f"s3://{bucket}/{OBJECT_PREFIX}/athena-results/"
        },
        WorkGroup=WORKGROUP,
    )
    query_id = query["QueryExecutionId"]

    deadline = time.time() + 90
    while time.time() < deadline:
        execution = athena.get_query_execution(QueryExecutionId=query_id)[
            "QueryExecution"
        ]
        state = execution["Status"]["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        time.sleep(1)
    else:
        raise TimeoutError("Athena query did not finish within 90 seconds")

    if state != "SUCCEEDED":
        reason = execution["Status"].get("StateChangeReason", "unknown")
        raise RuntimeError(f"Athena query ended in {state}: {reason}")

    result = athena.get_query_results(QueryExecutionId=query_id)
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

    print(
        json.dumps(
            {
                "glue_search_asset": orders_asset["AssetName"],
                "skill_discovered": SKILL_IDENTIFIER,
                "contract_format": manifest["semantic_contract_format"],
                "contract_version": discovered_contract["version"],
                "compiler_tool": manifest["compiler_tool"],
                "execution_tool": manifest["execution_tool"],
                "metric": "net_revenue",
                "dimension": "customers.region",
                "athena_state": state,
                "rows": values,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
