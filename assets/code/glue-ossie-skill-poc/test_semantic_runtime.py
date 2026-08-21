import io
import json
import unittest
from pathlib import Path

from semantic_runtime import (
    RuntimeConfig,
    SemanticRuntime,
    SemanticRuntimeError,
)


BASE_DIR = Path(__file__).resolve().parent
SKILL_ID = "sales-semantic-skill-ossie-poc"
SKILL_URI = "s3://example-bucket/semantic-skill-ossie-poc/sales-semantic-skill.md"
CONTRACT_URI = "s3://example-bucket/semantic-skill-ossie-poc/sales.ossie.yaml"


class FakeGlue:
    def search_assets(self, **kwargs):
        return {"Items": [{"AssetName": "orders", "Id": "orders-id"}]}

    def get_asset(self, **kwargs):
        identifier = kwargs["Identifier"]
        if identifier == "orders-id":
            return {
                "Attachments": {
                    "ossieSemanticContract": {
                        "Content": json.dumps(
                            {"assetIdentifiers": [SKILL_ID]}
                        )
                    }
                }
            }
        if identifier == SKILL_ID:
            return {
                "Forms": {
                    "amazon::Skill": {
                        "Content": json.dumps({"uri": SKILL_URI})
                    }
                }
            }
        raise KeyError(identifier)


class FakeS3:
    def __init__(self):
        skill = f"""# Sales Semantic Skill

## Semantic contract

- URI: `{CONTRACT_URI}`
- Format: `apache-ossie`
- Target engine: `athena`

## Approved tools

- Compiler: `compile_ossie_metric`
- Executor: `execute_athena_query`
""".encode("utf-8")
        self.objects = {
            ("example-bucket", "semantic-skill-ossie-poc/sales-semantic-skill.md"): skill,
            ("example-bucket", "semantic-skill-ossie-poc/sales.ossie.yaml"): (
                BASE_DIR / "sales.ossie.yaml"
            ).read_bytes(),
        }

    def get_object(self, **kwargs):
        body = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        return {"Body": io.BytesIO(body)}


class FakeAthena:
    def __init__(self):
        self.query_string = None

    def start_query_execution(self, **kwargs):
        self.query_string = kwargs["QueryString"]
        return {"QueryExecutionId": "query-123"}

    def get_query_execution(self, **kwargs):
        return {"QueryExecution": {"Status": {"State": "SUCCEEDED"}}}

    def get_query_results(self, **kwargs):
        return {
            "ResultSet": {
                "Rows": [
                    {"Data": [
                        {"VarCharValue": "region"},
                        {"VarCharValue": "net_revenue"},
                    ]},
                    {"Data": [
                        {"VarCharValue": "BUSAN"},
                        {"VarCharValue": "110000.00"},
                    ]},
                    {"Data": [
                        {"VarCharValue": "SEOUL"},
                        {"VarCharValue": "320000.00"},
                    ]},
                ]
            }
        }


def make_runtime():
    return SemanticRuntime(
        config=RuntimeConfig(
            database="heuristicwave_ossie_poc",
            workgroup="heuristicwave-ossie-poc",
            output_location="s3://example-bucket/results/",
            skill_attachment="ossieSemanticContract",
            allowed_contract_prefix=(
                "s3://example-bucket/semantic-skill-ossie-poc/"
            ),
        ),
        glue=FakeGlue(),
        s3=FakeS3(),
        athena=FakeAthena(),
        ossie_schema={
            "type": "object",
            "required": ["version", "semantic_model"],
        },
    )


class SemanticRuntimeTest(unittest.TestCase):
    def test_discovers_contract_through_related_skill(self):
        runtime = make_runtime()

        found = runtime.discover_semantic_contract("net revenue")

        self.assertEqual(found["skill_id"], SKILL_ID)
        self.assertEqual(found["contract_name"], "sales.ossie.yaml")
        self.assertEqual(found["contract_uri"], CONTRACT_URI)
        self.assertEqual(
            found["declared_tools"],
            ["compile_ossie_metric", "execute_athena_query"],
        )

    def test_rejects_contract_uri_not_returned_by_discovery(self):
        runtime = make_runtime()
        runtime.discover_semantic_contract("net revenue")

        with self.assertRaisesRegex(SemanticRuntimeError, "not discovered"):
            runtime.compile_ossie_metric(
                "s3://other-bucket/evil.yaml",
                "net_revenue",
                "customers.region",
            )

    def test_rejects_contract_that_fails_ossie_schema(self):
        runtime = make_runtime()
        found = runtime.discover_semantic_contract("net revenue")
        runtime.s3.objects[
            ("example-bucket", "semantic-skill-ossie-poc/sales.ossie.yaml")
        ] = b"version: broken\n"

        with self.assertRaisesRegex(SemanticRuntimeError, "schema validation"):
            runtime.compile_ossie_metric(
                found["contract_uri"],
                "net_revenue",
                "customers.region",
            )

    def test_compiles_metric_from_discovered_contract(self):
        runtime = make_runtime()
        found = runtime.discover_semantic_contract("net revenue")

        compiled = runtime.compile_ossie_metric(
            found["contract_uri"],
            "net_revenue",
            "customers.region",
        )

        self.assertEqual(compiled["metric"], "net_revenue")
        self.assertEqual(compiled["dimension"], "customers.region")
        self.assertEqual(compiled["relationship"], "orders_to_customers")
        self.assertIn(
            "LEFT JOIN heuristicwave_ossie_poc.customers AS customers",
            compiled["sql"],
        )
        self.assertEqual(len(compiled["sql_sha256"]), 64)
        self.assertEqual(runtime.snapshot["relationship"], "orders_to_customers")

    def test_rejects_non_select_or_multiple_statements(self):
        runtime = make_runtime()

        for sql in [
            "DROP TABLE heuristicwave_ossie_poc.orders",
            "SELECT 1; DROP TABLE heuristicwave_ossie_poc.orders",
            "SELECT * FROM another_database.orders",
        ]:
            with self.subTest(sql=sql):
                with self.assertRaisesRegex(
                    SemanticRuntimeError,
                    "read-only|allow-listed",
                ):
                    runtime.execute_athena_query(sql)

    def test_executes_compiled_select_and_returns_rows(self):
        runtime = make_runtime()
        found = runtime.discover_semantic_contract("net revenue")
        compiled = runtime.compile_ossie_metric(
            found["contract_uri"],
            "net_revenue",
            "customers.region",
        )

        execution = runtime.execute_athena_query(compiled["sql"])

        self.assertEqual(execution["athena_state"], "SUCCEEDED")
        self.assertEqual(execution["query_execution_id"], "query-123")
        self.assertEqual(
            execution["rows"],
            [
                {"region": "BUSAN", "net_revenue": "110000.00"},
                {"region": "SEOUL", "net_revenue": "320000.00"},
            ],
        )
        self.assertEqual(runtime.snapshot["athena_state"], "SUCCEEDED")
        self.assertEqual(runtime.snapshot["contract_name"], "sales.ossie.yaml")


if __name__ == "__main__":
    unittest.main()
