# Strands Ossie Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a Strands Agent whose Bedrock model actually selects the Glue Skill discovery, Ossie compilation, and Athena execution tools.

**Architecture:** Keep AWS access and semantic enforcement in a deterministic `SemanticRuntime`, expose only three narrow methods as Strands `@tool` functions, and let the Bedrock model orchestrate them. Record both Strands OpenTelemetry spans and the model-authored `toolUse` blocks so declared tools and invoked tools cannot be confused.

**Tech Stack:** Python 3.11, strands-agents 1.35.0, Amazon Bedrock Claude Sonnet 4.6, boto3, OpenTelemetry, AWS Glue Data Catalog, Amazon S3, Apache Ossie YAML, Amazon Athena, unittest.

**Spec:** `docs/superpowers/specs/2026-08-18-strands-ossie-agent-design.md`

## Global Constraints

- Use AWS profile `default` and region `us-west-2`.
- Use Bedrock inference profile `global.anthropic.claude-sonnet-4-6`.
- Keep `run_aws_poc.py` as the deterministic baseline.
- Do not enable account-wide Bedrock Model Invocation Logging.
- Do not accept arbitrary contract URIs, tables, Metric names, Dimension names, or SQL statements.
- Redact bucket names, account IDs, ARNs, credentials, and full trace payloads from publishable evidence.
- Develop every production behavior with a failing test first.

---

### Task 1: Deterministic semantic runtime and security boundaries

**Files:**
- Create: `assets/code/glue-ossie-skill-poc/semantic_runtime.py`
- Create: `assets/code/glue-ossie-skill-poc/test_semantic_runtime.py`
- Reuse: `assets/code/glue-ossie-skill-poc/ossie_athena.py`

**Interfaces:**
- Produces: `SemanticRuntime(config, glue, s3, athena, ossie_schema)`
- Produces: `discover_semantic_contract(search_text: str) -> dict`
- Produces: `compile_ossie_metric(contract_uri: str, metric_name: str, dimension_name: str) -> dict`
- Produces: `execute_athena_query(sql: str) -> dict`

- [ ] **Step 1: Write failing discovery and URI-binding tests**

```python
class SemanticRuntimeTest(unittest.TestCase):
    def test_discovers_contract_through_related_skill(self):
        runtime = make_runtime()
        found = runtime.discover_semantic_contract("net revenue")
        self.assertEqual(found["contract_name"], "sales.ossie.yaml")
        self.assertEqual(found["declared_tools"], [
            "compile_ossie_metric", "execute_athena_query"
        ])

    def test_rejects_contract_uri_not_returned_by_discovery(self):
        runtime = make_runtime()
        runtime.discover_semantic_contract("net revenue")
        with self.assertRaisesRegex(SemanticRuntimeError, "not discovered"):
            runtime.compile_ossie_metric(
                "s3://other/evil.yaml", "net_revenue", "customers.region"
            )
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```shell
python -m unittest -v test_semantic_runtime.py
```

Expected: import failure because `semantic_runtime.py` does not exist.

- [ ] **Step 3: Implement discovery and URI binding**

Implement immutable `RuntimeConfig`, `SemanticRuntimeError`, and `SemanticRuntime`. Discovery must execute `SearchAssets → GetAsset → amazon::RelatedTo → GetAsset Skill → S3 GetObject → parse_skill_manifest`, store the discovered URI internally, and return only the filename plus digest in its public result.

- [ ] **Step 4: Run discovery tests and verify GREEN**

Run the same unittest command and require both tests to pass.

- [ ] **Step 5: Write failing compilation and SQL-safety tests**

```python
def test_compiles_only_discovered_contract(self):
    runtime = make_runtime()
    found = runtime.discover_semantic_contract("net revenue")
    compiled = runtime.compile_ossie_metric(
        found["contract_uri"], "net_revenue", "customers.region"
    )
    self.assertIn("LEFT JOIN", compiled["sql"])
    self.assertEqual(compiled["metric"], "net_revenue")

def test_rejects_non_select_or_multiple_statements(self):
    runtime = make_runtime()
    for sql in ["DROP TABLE orders", "SELECT 1; DROP TABLE orders"]:
        with self.subTest(sql=sql):
            with self.assertRaisesRegex(SemanticRuntimeError, "read-only"):
                runtime.execute_athena_query(sql)
```

- [ ] **Step 6: Run tests and verify RED for missing compilation and execution behavior**

- [ ] **Step 7: Implement Schema validation, restricted compilation, and Athena execution**

Compilation must load the exact discovered object, validate it with `jsonschema.validate`, call `compile_metric_query`, and return the SQL with a SHA-256 digest. Execution must reject comments, multiple statements, non-`SELECT` prefixes, and tables outside `heuristicwave_ossie_poc.orders` and `heuristicwave_ossie_poc.customers`; then poll the configured Athena workgroup to a terminal state.

- [ ] **Step 8: Run all runtime and legacy tests**

```shell
python -m unittest -v test_semantic_runtime.py test_ossie_athena.py
```

Expected: all tests pass.

- [ ] **Step 9: Commit Task 1**

```shell
git add assets/code/glue-ossie-skill-poc/semantic_runtime.py \
        assets/code/glue-ossie-skill-poc/test_semantic_runtime.py
git commit -m "feat: add guarded Ossie semantic runtime"
```

### Task 2: Strands tools and invocation evidence

**Files:**
- Create: `assets/code/glue-ossie-skill-poc/strands_tools.py`
- Create: `assets/code/glue-ossie-skill-poc/trace_audit.py`
- Create: `assets/code/glue-ossie-skill-poc/test_strands_agent.py`

**Interfaces:**
- Consumes: `SemanticRuntime`
- Produces: `build_semantic_tools(runtime) -> list[DecoratedFunctionTool]`
- Produces: `extract_tool_uses(messages: list[Message]) -> list[dict]`
- Produces: `assert_required_tool_sequence(tool_uses: list[dict]) -> None`
- Produces: `write_redacted_audit(path, model_id, messages, runtime_snapshot) -> dict`

- [ ] **Step 1: Write failing Tool registry tests**

```python
def test_builds_exactly_three_semantic_tools(self):
    tools = build_semantic_tools(FakeRuntime())
    self.assertEqual(
        [item.tool_name for item in tools],
        [
            "discover_semantic_contract",
            "compile_ossie_metric",
            "execute_athena_query",
        ],
    )
```

- [ ] **Step 2: Run the test and verify RED because `strands_tools` is absent**

- [ ] **Step 3: Implement the three `@tool` wrappers**

Each wrapper must have a docstring describing when the model should call it and delegate directly to the corresponding runtime method. No tool may expose boto3 clients or arbitrary file access.

- [ ] **Step 4: Run the Tool registry test and verify GREEN**

- [ ] **Step 5: Write failing audit extraction tests**

```python
def test_extracts_model_authored_tool_use_in_order(self):
    messages = [
        {"role": "assistant", "content": [{"toolUse": {
            "toolUseId": "1", "name": "discover_semantic_contract",
            "input": {"search_text": "net revenue"}
        }}]},
        {"role": "assistant", "content": [{"toolUse": {
            "toolUseId": "2", "name": "compile_ossie_metric",
            "input": {"metric_name": "net_revenue"}
        }}]},
        {"role": "assistant", "content": [{"toolUse": {
            "toolUseId": "3", "name": "execute_athena_query",
            "input": {"sql": "SELECT ..."}
        }}]},
    ]
    calls = extract_tool_uses(messages)
    assert_required_tool_sequence(calls)
    self.assertEqual([call["name"] for call in calls], [
        "discover_semantic_contract",
        "compile_ossie_metric",
        "execute_athena_query",
    ])
```

- [ ] **Step 6: Run the audit test and verify RED because audit functions are absent**

- [ ] **Step 7: Implement trace audit and redaction**

Extract only assistant-authored `toolUse` blocks. Replace contract URIs with filenames, SQL text with SHA-256 digests, and omit account identifiers. Reject a missing, repeated, or out-of-order required sequence.

- [ ] **Step 8: Run all offline tests**

```shell
python -m unittest -v test_semantic_runtime.py test_ossie_athena.py test_strands_agent.py
```

- [ ] **Step 9: Commit Task 2**

```shell
git add assets/code/glue-ossie-skill-poc/strands_tools.py \
        assets/code/glue-ossie-skill-poc/trace_audit.py \
        assets/code/glue-ossie-skill-poc/test_strands_agent.py
git commit -m "feat: expose semantic tools with trace audit"
```

### Task 3: Bedrock-backed Strands Agent and live trace

**Files:**
- Create: `assets/code/glue-ossie-skill-poc/run_strands_agent.py`
- Modify: `assets/code/glue-ossie-skill-poc/requirements.txt`
- Create: `assets/code/glue-ossie-skill-poc/.gitignore`
- Modify: `assets/code/glue-ossie-skill-poc/README.md`

**Interfaces:**
- Consumes: semantic runtime, Strands tools, trace audit
- Produces: `artifacts/strands-trace.jsonl`
- Produces: `artifacts/tool-audit.json`
- Produces: process exit code 0 only for the required Tool sequence and successful Athena result

- [ ] **Step 1: Add pinned Strands and OpenTelemetry dependencies**

Append:

```text
strands-agents[otel]==1.35.0
```

Create `.gitignore` with:

```text
.venv/
artifacts/strands-trace.jsonl
artifacts/tool-audit.json
```

- [ ] **Step 2: Install the isolated environment and run offline tests before the Agent entry point exists**

```shell
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest -v \
  test_semantic_runtime.py test_ossie_athena.py test_strands_agent.py
```

- [ ] **Step 3: Implement `run_strands_agent.py`**

The entry point must configure:

```python
MODEL_ID = "global.anthropic.claude-sonnet-4-6"
USER_PROMPT = "지역별 순매출을 보여줘. 사용한 Metric과 Relationship도 설명해줘."

model = BedrockModel(
    boto_session=session,
    model_id=MODEL_ID,
    temperature=0,
    max_tokens=1200,
)
agent = Agent(
    model=model,
    tools=build_semantic_tools(runtime),
    system_prompt=SYSTEM_PROMPT,
    callback_handler=None,
    trace_attributes={"poc.name": "glue-ossie-strands"},
)
```

Configure `StrandsTelemetry().setup_console_exporter(...)` to write one JSON object per line to `artifacts/strands-trace.jsonl`. After `agent(USER_PROMPT)`, force-flush OpenTelemetry, extract `agent.messages`, assert the required sequence, write `tool-audit.json`, and verify the expected rows.

- [ ] **Step 4: Run one live Strands invocation**

```shell
.venv/bin/python run_strands_agent.py
```

Expected:

```text
tool_sequence_verified=true
athena_state=SUCCEEDED
BUSAN=110000
SEOUL=320000
```

- [ ] **Step 5: Inspect trace evidence**

```shell
python -m json.tool artifacts/tool-audit.json
rg 'discover_semantic_contract|compile_ossie_metric|execute_athena_query' \
  artifacts/strands-trace.jsonl
```

Require all three names in both message-history audit and OpenTelemetry trace.

- [ ] **Step 6: Update README with deterministic and Agent run commands**

Document that the deterministic Runner validates the data path while the Strands run proves Bedrock-authored Tool selection.

- [ ] **Step 7: Commit Task 3 source and documentation without runtime artifacts**

```shell
git add assets/code/glue-ossie-skill-poc/run_strands_agent.py \
        assets/code/glue-ossie-skill-poc/requirements.txt \
        assets/code/glue-ossie-skill-poc/.gitignore \
        assets/code/glue-ossie-skill-poc/README.md
git commit -m "feat: run Ossie tools through Strands and Bedrock"
```

### Task 4: Publish verified findings in the blog

**Files:**
- Modify: `_posts/ai/2026-08-06-AI-Ready-Data-Ontology.md`
- Create: `assets/code/glue-ossie-skill-poc/artifacts/tool-audit.example.json`

**Interfaces:**
- Consumes: verified live `tool-audit.json` and trace
- Produces: a redacted reproducible explanation and evidence artifact

- [ ] **Step 1: Create a redacted example from the verified audit**

Copy only model ID, trace ID, Tool names, sanitized parameters, contract filename and digest, Athena state, query ID suffix, and result rows. Do not include S3 bucket names, ARNs, or account IDs.

- [ ] **Step 2: Rewrite the execution section**

State that the prior Python Runner parsed declarations and called fixed functions. Add a separate Strands section explaining that the Bedrock model generated the `toolUse` blocks and that Strands executed those selected tools. Show the three-call sequence from the redacted audit and link to the reproducible code.

- [ ] **Step 3: Build Jekyll and verify rendered claims**

```shell
/Users/heuri/.rbenv/shims/bundle exec jekyll build
rg 'Strands|toolUse|discover_semantic_contract' output/AI-Ready-Data-Ontology.html
```

- [ ] **Step 4: Run the complete verification suite**

```shell
cd assets/code/glue-ossie-skill-poc
.venv/bin/python -m unittest -v \
  test_semantic_runtime.py test_ossie_athena.py test_strands_agent.py
cd ../../..
/Users/heuri/.rbenv/shims/bundle exec jekyll build
```

- [ ] **Step 5: Commit Task 4**

```shell
git add _posts/ai/2026-08-06-AI-Ready-Data-Ontology.md \
        assets/code/glue-ossie-skill-poc/artifacts/tool-audit.example.json
git commit -m "docs: verify Bedrock tool selection with Strands trace"
```
