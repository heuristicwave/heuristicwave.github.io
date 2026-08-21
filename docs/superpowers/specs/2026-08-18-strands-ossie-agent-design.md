# Strands Ossie Agent Design

## Goal

Replace the deterministic orchestration in the existing Glue Skill + Apache Ossie + Athena PoC with a Strands Agent backed by an Amazon Bedrock model, and produce verifiable evidence that the model selected and invoked the semantic discovery, compilation, and execution tools.

## Scope

The implementation extends `assets/code/glue-ossie-skill-poc/`. It keeps the existing AWS resources, Ossie contract, restricted SQL compiler, and Athena workgroup. It adds an agent entry point, three Strands tools, local tracing, offline tests, and one real Bedrock integration run.

The implementation does not enable account-wide Bedrock Model Invocation Logging, deploy to AgentCore, create a general Ossie query engine, or permit arbitrary SQL execution.

## Runtime Architecture

The agent uses the active Bedrock inference profile `global.anthropic.claude-sonnet-4-6` in `us-west-2` through the AWS `default` profile.

The model receives one user request: `지역별 순매출을 보여줘.` It can select only these tools:

1. `discover_semantic_contract(search_text)`
   - Calls Glue `SearchAssets`.
   - Resolves the `orders` Data Asset and its `amazon::RelatedTo` Skill attachment.
   - Reads the Skill Asset URI, downloads its Markdown from S3, and parses the application-defined `Semantic contract` and `Approved tools` sections.
   - Returns the contract URI, format, target engine, available approved tool names, and a content digest.
2. `compile_ossie_metric(contract_uri, metric_name, dimension_name)`
   - Requires the URI to match the contract discovered from the Skill.
   - Downloads and validates the Ossie YAML against the pinned Ossie JSON Schema.
   - Calls the existing restricted compiler and returns SQL plus the selected Metric and Relationship.
3. `execute_athena_query(sql)`
   - Accepts only one `SELECT` statement referencing the allow-listed Glue database and tables.
   - Executes through the existing Athena workgroup and returns rows, query execution ID, and final state.

The agent system prompt requires discovery before compilation and compilation before execution. The tools independently enforce this boundary; the prompt is not treated as a security control.

## Code Boundaries

- `semantic_runtime.py`: AWS clients, Skill discovery, contract loading, Schema validation, restricted SQL compilation, and Athena execution. This module contains no Strands dependency and is tested offline through injected clients.
- `strands_tools.py`: Three `@tool` wrappers with concise descriptions and typed parameters. Each wrapper delegates to `SemanticRuntime`.
- `trace_audit.py`: OpenTelemetry JSONL exporter setup and extraction of actual `toolUse` blocks from the completed agent message history into a small redacted audit artifact.
- `run_strands_agent.py`: Bedrock model configuration, Strands Agent construction, invocation, trace finalization, and final verification report.
- `test_semantic_runtime.py`: Offline unit tests for discovery, URI binding, compilation, SQL restrictions, and execution result handling.
- `test_strands_tools.py`: Offline tests for tool schemas and delegation without invoking Bedrock.
- `artifacts/`: Runtime-generated trace and audit files, excluded from Git except for an optional redacted example produced after the integration run.

Existing `ossie_athena.py` remains the restricted compiler. Existing `run_aws_poc.py` remains as a deterministic baseline for comparison.

## Evidence and Observability

Strands OpenTelemetry tracing writes a local JSONL file for the development run. The trace must contain the agent lifecycle, Bedrock model spans, and tool execution spans.

A second redacted audit JSON records:

- Bedrock model identifier
- trace ID
- ordered `toolUse` names and sanitized inputs
- tool success or failure
- discovered Skill identifier
- contract filename and SHA-256 digest, without the bucket name
- generated SQL digest and Athena query execution ID
- final Athena state and returned rows

The integration check passes only when the actual message history contains these tool calls in order:

```text
discover_semantic_contract
compile_ossie_metric
execute_athena_query
```

Reading tool names from Markdown is recorded separately as `declared_tools`; it is not counted as evidence that the model selected those tools.

## Security and Failure Handling

- AWS access uses the existing `default` profile and `us-west-2`.
- Contract URIs must use `s3`, remain under the discovered bucket and object prefix, and match the Skill-declared URI.
- Ossie documents must pass the pinned JSON Schema before compilation.
- Metric and Dimension identifiers must exist in the validated contract.
- SQL must be a single read-only `SELECT`; comments, semicolons followed by another statement, and non-allow-listed tables are rejected.
- Athena runs only in `heuristicwave-ossie-poc` with its configured output location and timeout.
- Trace artifacts redact account IDs, bucket names, ARNs, credentials, and full prompts beyond the synthetic test question.
- Tool failures are returned to the agent and emitted as error spans. The script exits non-zero when the required tool sequence or Athena success is absent.

## Test Strategy

Development follows red-green-refactor.

Offline tests cover:

- Skill Markdown parsing and related Skill discovery.
- Rejection of a contract URI not returned by discovery.
- Ossie Schema validation failure.
- Compilation of `net_revenue` by `customers.region`.
- Rejection of unknown metrics, dimensions, relationships, and unsafe SQL.
- Audit extraction distinguishes declared tool names from actual `toolUse` messages.

One live integration run uses the existing synthetic AWS resources and makes the minimum Bedrock calls required by the Strands loop. It must prove:

- the model invoked all three tools in order;
- the contract fetched through the Skill matches the recorded digest;
- Athena completed with `SUCCEEDED`;
- the returned rows remain `BUSAN = 110000` and `SEOUL = 320000`;
- the JSONL trace and redacted audit artifact were created.

## Documentation Update

After verification, the blog will replace the deterministic-runner claim with two clearly separated results:

1. the original Runner proved the Glue Skill → Ossie contract → compiler → Athena data path;
2. the Strands run proved that a Bedrock model actually selected the registered tools, with the tool sequence shown by Strands trace and message-history evidence.

The post will not claim that Glue or Ossie automatically executes SQL, nor that AWS defines the Markdown parser convention.

## References

- [Strands Agents tools](https://strandsagents.com/docs/user-guide/concepts/tools/)
- [Strands Agents traces](https://strandsagents.com/docs/user-guide/observability-evaluation/traces/)
- [Strands Amazon Bedrock provider](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/)
- [AWS Glue Skill assets for AI agents](https://docs.aws.amazon.com/glue/latest/dg/catalog-skill-assets.html)
