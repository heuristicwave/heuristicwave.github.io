from strands import tool


def build_semantic_tools(runtime):
    @tool
    def discover_semantic_contract(search_text: str) -> dict:
        """Find the semantic contract related to a business data request.

        Call this first when a user asks for a business Metric or analysis.

        Args:
            search_text: English business meaning to search in Glue Data Catalog.
        """
        return runtime.discover_semantic_contract(search_text)

    @tool
    def compile_ossie_metric(
        contract_uri: str,
        metric_name: str,
        dimension_name: str,
    ) -> dict:
        """Compile a discovered Apache Ossie Metric into guarded Athena SQL.

        Call this only with the contract URI returned by
        discover_semantic_contract.

        Args:
            contract_uri: S3 URI returned by semantic contract discovery.
            metric_name: Ossie Metric name to calculate.
            dimension_name: Qualified dimension in dataset.field form.
        """
        return runtime.compile_ossie_metric(
            contract_uri,
            metric_name,
            dimension_name,
        )

    @tool
    def execute_athena_query(sql: str) -> dict:
        """Execute SQL produced by compile_ossie_metric with Amazon Athena.

        Args:
            sql: Read-only Athena SQL returned by compile_ossie_metric.
        """
        return runtime.execute_athena_query(sql)

    return [
        discover_semantic_contract,
        compile_ossie_metric,
        execute_athena_query,
    ]
