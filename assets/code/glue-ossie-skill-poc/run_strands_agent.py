import json
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import boto3
from opentelemetry import trace
from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

from semantic_runtime import RuntimeConfig, SemanticRuntime
from strands_tools import build_semantic_tools
from trace_audit import write_redacted_audit


REGION = "us-west-2"
DATABASE = "heuristicwave_ossie_poc"
WORKGROUP = "heuristicwave-ossie-poc"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"
OBJECT_PREFIX = "semantic-skill-ossie-poc"
OSSIE_COMMIT = "88e0011148283302c9a04cd0287e00e0b9d87354"
OSSIE_SCHEMA_URL = (
    "https://raw.githubusercontent.com/apache/ossie/"
    f"{OSSIE_COMMIT}/core-spec/osi-schema.json"
)
USER_PROMPT = (
    "지역별 순매출을 보여줘. 사용한 Metric과 Relationship도 설명해줘."
)
SYSTEM_PROMPT = """You are a governed semantic analytics agent.

For this request, use the available tools instead of inventing SQL or data.
Call each tool exactly once in this order:
1. discover_semantic_contract with the English search text "net revenue".
2. compile_ossie_metric with the returned contract_uri, metric_name
   "net_revenue", and dimension_name "customers.region".
3. execute_athena_query with the exact SQL returned by the compiler.

After all tools succeed, answer in Korean. State the values by region and name
the Metric and Relationship returned by the tools. Never modify the compiled
SQL and never claim that Glue or Ossie executed SQL by itself.
"""


EXPECTED_ROWS = {
    ("BUSAN", "110000.00"),
    ("SEOUL", "320000.00"),
}


def verify_expected_rows(rows):
    actual = {(row.get("region"), row.get("net_revenue")) for row in rows}
    if actual != EXPECTED_ROWS:
        raise RuntimeError(f"Received unexpected Athena rows: {rows}")


def read_trace_id(path):
    with open(path, encoding="utf-8") as trace_file:
        for line in trace_file:
            if not line.strip():
                continue
            span = json.loads(line)
            trace_id = span.get("context", {}).get("trace_id")
            if trace_id:
                return trace_id
    return None


def format_span_jsonl(span):
    return json.dumps(
        json.loads(span.to_json()),
        ensure_ascii=False,
        separators=(",", ":"),
    ) + os.linesep


def build_runtime(session):
    glue = session.client("glue")
    s3 = session.client("s3")
    athena = session.client("athena")
    orders_table = glue.get_table(DatabaseName=DATABASE, Name="orders")["Table"]
    orders_location = urlparse(orders_table["StorageDescriptor"]["Location"])
    bucket = orders_location.netloc
    if not bucket:
        raise RuntimeError("The orders table does not have an S3 location")

    with urllib.request.urlopen(OSSIE_SCHEMA_URL, timeout=30) as response:
        ossie_schema = json.load(response)

    return SemanticRuntime(
        config=RuntimeConfig(
            database=DATABASE,
            workgroup=WORKGROUP,
            output_location=f"s3://{bucket}/{OBJECT_PREFIX}/athena-results/",
            skill_attachment="ossieSemanticContract",
            allowed_contract_prefix=f"s3://{bucket}/{OBJECT_PREFIX}/",
        ),
        glue=glue,
        s3=s3,
        athena=athena,
        ossie_schema=ossie_schema,
    )


def main():
    base_dir = Path(__file__).resolve().parent
    artifacts_dir = base_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    trace_path = artifacts_dir / "strands-trace.jsonl"
    audit_path = artifacts_dir / "tool-audit.json"

    session = boto3.Session(profile_name="default", region_name=REGION)
    runtime = build_runtime(session)
    model = BedrockModel(
        boto_session=session,
        model_id=MODEL_ID,
        temperature=0,
        max_tokens=1200,
    )

    with trace_path.open("w", encoding="utf-8") as trace_file:
        telemetry = StrandsTelemetry()
        telemetry.setup_console_exporter(
            out=trace_file,
            formatter=format_span_jsonl,
        )
        agent = Agent(
            model=model,
            tools=build_semantic_tools(runtime),
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
            trace_attributes={"poc.name": "glue-ossie-strands"},
        )
        result = agent(USER_PROMPT)
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "force_flush"):
            tracer_provider.force_flush()
        trace_file.flush()

    verify_expected_rows(runtime.snapshot["rows"])
    trace_id = read_trace_id(trace_path)
    audit = write_redacted_audit(
        path=audit_path,
        model_id=MODEL_ID,
        messages=agent.messages,
        runtime_snapshot=runtime.snapshot,
        trace_id=trace_id,
    )

    print(
        json.dumps(
            {
                "tool_sequence_verified": True,
                "actual_tool_sequence": audit["actual_tool_sequence"],
                "athena_state": audit["athena_state"],
                "rows": audit["rows"],
                "trace_id": trace_id,
                "trace_file": trace_path.name,
                "audit_file": audit_path.name,
                "agent_answer": str(result),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
