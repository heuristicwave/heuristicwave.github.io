# Glue Skill + Apache Ossie + Strands Agent PoC

This directory contains the minimal reproducible code used by the blog post.

The deterministic baseline follows this path:

```text
Glue SearchAssets
  -> amazon::RelatedTo Skill Asset
  -> Skill Markdown in S3
  -> Apache Ossie YAML in S3
  -> compile_metric_query
  -> Amazon Athena
```

`run_aws_poc.py` proves that this data path works, but it does not prove that
an LLM selected the declared tools. The Strands extension registers three
actual tools with a Bedrock-backed Agent:

```text
discover_semantic_contract
  -> compile_ossie_metric
  -> execute_athena_query
```

`run_strands_agent.py` requires the model-authored `toolUse` blocks to contain
that exact sequence. It also emits a Strands OpenTelemetry trace so the same
tool executions can be checked independently through `gen_ai.tool.name`.

The compiler intentionally supports one Metric and one many-to-one Relationship.
It is not a general Apache Ossie query engine.

AWS Glue stores the Skill Asset URI; it does not define or parse YAML
frontmatter inside the referenced document. This PoC keeps the skill as plain
Markdown and uses the `Semantic contract` and `Approved tools` sections as a
small application-level parsing convention.

```shell
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest -v test_ossie_athena.py
.venv/bin/python run_aws_poc.py
.venv/bin/python -m unittest -v \
  test_semantic_runtime.py test_ossie_athena.py test_strands_agent.py
.venv/bin/python run_strands_agent.py
```

The AWS run expects an authenticated `default` profile and the existing
`heuristicwave_ossie_poc` database, `orders` and `customers` tables, and
`heuristicwave-ossie-poc` Athena workgroup in `us-west-2`.

The Strands run additionally uses the active Bedrock inference profile
`global.anthropic.claude-sonnet-4-6`. Runtime evidence is written locally to:

- `artifacts/tool-audit.json`: redacted model-authored Tool sequence
- `artifacts/strands-trace.jsonl`: Strands OpenTelemetry spans

These runtime files are ignored by Git. They can contain prompts and Tool
results, so inspect and redact them before sharing. Account-wide Bedrock Model
Invocation Logging is not enabled by this PoC.
