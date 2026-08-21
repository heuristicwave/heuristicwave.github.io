import re


class ContractError(ValueError):
    pass


def parse_skill_manifest(skill_markdown):
    labels = {
        "URI": "semantic_contract_uri",
        "Format": "semantic_contract_format",
        "Target engine": "target_engine",
        "Compiler": "compiler_tool",
        "Executor": "execution_tool",
    }

    manifest = {}
    for label, key in labels.items():
        match = re.search(
            rf"^- {re.escape(label)}:\s+`?([^`\n]+)`?\s*$",
            skill_markdown,
            flags=re.MULTILINE,
        )
        if match:
            manifest[key] = match.group(1).strip()

    missing = set(labels.values()).difference(manifest)
    if missing:
        raise ContractError(
            "Skill instructions are missing: " + ", ".join(sorted(missing))
        )
    return manifest


def compile_metric_query(model, metric_name, dimension_name):
    semantic_models = model.get("semantic_model", [])
    if len(semantic_models) != 1:
        raise ContractError("Exactly one semantic model is required")

    semantic_model = semantic_models[0]
    datasets = {
        dataset["name"]: dataset for dataset in semantic_model.get("datasets", [])
    }

    metric = next(
        (
            item
            for item in semantic_model.get("metrics", [])
            if item.get("name") == metric_name
        ),
        None,
    )
    if metric is None:
        raise ContractError(f"Unknown metric: {metric_name}")

    ansi_expression = next(
        (
            item.get("expression")
            for item in metric.get("expression", {}).get("dialects", [])
            if item.get("dialect") == "ANSI_SQL"
        ),
        None,
    )
    if not ansi_expression:
        raise ContractError(f"Metric has no ANSI_SQL expression: {metric_name}")

    try:
        dimension_dataset, dimension_field = dimension_name.split(".", 1)
    except ValueError as exc:
        raise ContractError(
            "Dimension must be written as <dataset>.<field>"
        ) from exc

    referenced_datasets = [
        name
        for name in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.", ansi_expression)
        if name in datasets
    ]
    if not referenced_datasets:
        raise ContractError(f"Metric does not reference a dataset: {metric_name}")
    fact_dataset = referenced_datasets[0]

    relationship = next(
        (
            item
            for item in semantic_model.get("relationships", [])
            if item.get("from") == fact_dataset
            and item.get("to") == dimension_dataset
        ),
        None,
    )
    if relationship is None:
        raise ContractError(
            f"No relationship from {fact_dataset} to {dimension_dataset}"
        )

    from_columns = relationship.get("from_columns", [])
    to_columns = relationship.get("to_columns", [])
    if len(from_columns) != 1 or len(to_columns) != 1:
        raise ContractError("This PoC compiler supports one-column relationships only")

    fact_source = datasets[fact_dataset]["source"]
    dimension_source = datasets[dimension_dataset]["source"]

    return f"""SELECT
  {dimension_dataset}.{dimension_field} AS {dimension_field},
  {ansi_expression} AS {metric_name}
FROM {fact_source} AS {fact_dataset}
LEFT JOIN {dimension_source} AS {dimension_dataset}
  ON {fact_dataset}.{from_columns[0]} = {dimension_dataset}.{to_columns[0]}
GROUP BY {dimension_dataset}.{dimension_field}
ORDER BY {dimension_dataset}.{dimension_field};"""
