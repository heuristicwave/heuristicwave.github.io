import json
import tempfile
import unittest
from pathlib import Path

from strands_tools import build_semantic_tools
from run_strands_agent import format_span_jsonl, read_trace_id, verify_expected_rows
from trace_audit import (
    ToolSequenceError,
    assert_required_tool_sequence,
    extract_tool_uses,
    write_redacted_audit,
)


REQUIRED_TOOL_NAMES = [
    "discover_semantic_contract",
    "compile_ossie_metric",
    "execute_athena_query",
]


class FakeRuntime:
    def discover_semantic_contract(self, search_text):
        return {"search_text": search_text}

    def compile_ossie_metric(self, contract_uri, metric_name, dimension_name):
        return {
            "contract_uri": contract_uri,
            "metric": metric_name,
            "dimension": dimension_name,
        }

    def execute_athena_query(self, sql):
        return {"sql": sql}


def make_messages():
    return [
        {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "tool-1",
                        "name": "discover_semantic_contract",
                        "input": {"search_text": "net revenue"},
                    }
                }
            ],
        },
        {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "tool-2",
                        "name": "compile_ossie_metric",
                        "input": {
                            "contract_uri": (
                                "s3://private-bucket/semantic-skill-ossie-poc/"
                                "sales.ossie.yaml"
                            ),
                            "metric_name": "net_revenue",
                            "dimension_name": "customers.region",
                        },
                    }
                }
            ],
        },
        {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "tool-3",
                        "name": "execute_athena_query",
                        "input": {
                            "sql": (
                                "SELECT customers.region FROM "
                                "heuristicwave_ossie_poc.customers"
                            )
                        },
                    }
                }
            ],
        },
    ]


class StrandsAgentSupportTest(unittest.TestCase):
    def test_builds_exactly_three_semantic_tools(self):
        tools = build_semantic_tools(FakeRuntime())

        self.assertEqual([item.tool_name for item in tools], REQUIRED_TOOL_NAMES)

    def test_extracts_model_authored_tool_use_in_order(self):
        calls = extract_tool_uses(make_messages())

        assert_required_tool_sequence(calls)
        self.assertEqual([call["name"] for call in calls], REQUIRED_TOOL_NAMES)

    def test_rejects_repeated_or_out_of_order_tool_use(self):
        calls = extract_tool_uses(make_messages())

        for invalid in [calls[:2], [calls[1], calls[0], calls[2]], calls + calls[-1:]]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ToolSequenceError):
                    assert_required_tool_sequence(invalid)

    def test_writes_redacted_audit_without_uri_or_sql(self):
        messages = make_messages()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "audit.json"

            audit = write_redacted_audit(
                path=path,
                model_id="global.anthropic.claude-sonnet-4-6",
                messages=messages,
                runtime_snapshot={
                    "contract_name": "sales.ossie.yaml",
                    "contract_sha256": "a" * 64,
                    "athena_state": "SUCCEEDED",
                    "query_execution_id": "1234567890abcdef",
                    "rows": [
                        {"region": "BUSAN", "net_revenue": "110000.00"}
                    ],
                },
            )

            serialized = path.read_text(encoding="utf-8")
            self.assertEqual(json.loads(serialized), audit)
            self.assertNotIn("private-bucket", serialized)
            self.assertNotIn("SELECT customers", serialized)
            self.assertEqual(
                audit["tool_uses"][1]["input"]["contract_name"],
                "sales.ossie.yaml",
            )
            self.assertEqual(len(audit["tool_uses"][2]["input"]["sql_sha256"]), 64)
            self.assertEqual(audit["query_execution_id_suffix"], "90abcdef")

    def test_verifies_expected_athena_rows(self):
        rows = [
            {"region": "BUSAN", "net_revenue": "110000.00"},
            {"region": "SEOUL", "net_revenue": "320000.00"},
        ]

        verify_expected_rows(rows)

        with self.assertRaisesRegex(RuntimeError, "unexpected Athena rows"):
            verify_expected_rows(rows[:1])

    def test_reads_trace_id_from_jsonl_span(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "trace.jsonl"
            path.write_text(
                '{"name":"execute_athena_query","context":'
                '{"trace_id":"0xabc123","span_id":"0xdef456"}}\n',
                encoding="utf-8",
            )

            self.assertEqual(read_trace_id(path), "0xabc123")

    def test_formats_pretty_span_as_single_jsonl_record(self):
        class FakeSpan:
            def to_json(self):
                return '{\n  "name": "chat",\n  "context": {"trace_id": "0x1"}\n}'

        record = format_span_jsonl(FakeSpan())

        self.assertEqual(record.count("\n"), 1)
        self.assertEqual(json.loads(record)["context"]["trace_id"], "0x1")


if __name__ == "__main__":
    unittest.main()
