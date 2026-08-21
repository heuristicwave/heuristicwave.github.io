# Sales Semantic Skill

## Purpose

Use this skill when a user asks for net revenue or regional sales analysis.

## Related data

- `heuristicwave_ossie_poc.orders`: order amount and cancellation status
- `heuristicwave_ossie_poc.customers`: official customer sales region

## Business context

- Use the `net_revenue` Metric for sales excluding cancelled orders.
- Use the `orders_to_customers` Relationship for regional analysis.
- Use `customers.region` as the official sales region.

## Semantic contract

- URI: `s3://<bucket>/semantic-skill-ossie-poc/sales.ossie.yaml`
- Format: `apache-ossie`
- Target engine: `athena`

## Approved tools

- Compiler: `compile_ossie_metric`
- Executor: `execute_athena_query`

## Execution instructions

- Load and validate the referenced Apache Ossie contract.
- Resolve Metric expressions and Dataset relationships from the contract.
- Compile only approved Dataset, Metric and Dimension identifiers.
- Execute the generated SQL with Amazon Athena.
- Return the Metric name and applied Relationship with the result.

## Query pattern

- User request: `Show net revenue by customer region.`
- Metric: `net_revenue`
- Dimension: `customers.region`
