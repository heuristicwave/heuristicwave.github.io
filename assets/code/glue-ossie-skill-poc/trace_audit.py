import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_TOOL_NAMES = [
    "discover_semantic_contract",
    "compile_ossie_metric",
    "execute_athena_query",
]


class ToolSequenceError(RuntimeError):
    pass


def extract_tool_uses(messages):
    tool_uses = []
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for content in message.get("content", []):
            if "toolUse" not in content:
                continue
            tool_use = content["toolUse"]
            tool_uses.append(
                {
                    "tool_use_id": tool_use["toolUseId"],
                    "name": tool_use["name"],
                    "input": tool_use.get("input", {}),
                }
            )
    return tool_uses


def assert_required_tool_sequence(tool_uses):
    actual = [item["name"] for item in tool_uses]
    if actual != REQUIRED_TOOL_NAMES:
        raise ToolSequenceError(
            f"Expected Tool sequence {REQUIRED_TOOL_NAMES}, received {actual}"
        )


def _redact_input(tool_input):
    redacted = {}
    for key, value in tool_input.items():
        if key == "contract_uri":
            redacted["contract_name"] = urlparse(value).path.rsplit("/", 1)[-1]
        elif key == "sql":
            redacted["sql_sha256"] = hashlib.sha256(
                value.encode("utf-8")
            ).hexdigest()
        else:
            redacted[key] = value
    return redacted


def write_redacted_audit(
    path,
    model_id,
    messages,
    runtime_snapshot,
    trace_id=None,
):
    tool_uses = extract_tool_uses(messages)
    assert_required_tool_sequence(tool_uses)
    query_execution_id = runtime_snapshot["query_execution_id"]
    audit = {
        "model_id": model_id,
        "trace_id": trace_id,
        "actual_tool_sequence": [item["name"] for item in tool_uses],
        "tool_uses": [
            {
                "tool_use_id": item["tool_use_id"],
                "name": item["name"],
                "input": _redact_input(item["input"]),
            }
            for item in tool_uses
        ],
        "contract_name": runtime_snapshot["contract_name"],
        "contract_sha256": runtime_snapshot["contract_sha256"],
        "athena_state": runtime_snapshot["athena_state"],
        "query_execution_id_suffix": query_execution_id[-8:],
        "rows": runtime_snapshot["rows"],
    }
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return audit
