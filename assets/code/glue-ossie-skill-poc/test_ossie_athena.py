import unittest

from ossie_athena import compile_metric_query, parse_skill_manifest


MODEL = {
    "semantic_model": [
        {
            "name": "sales_analytics",
            "datasets": [
                {
                    "name": "orders",
                    "source": "heuristicwave_ossie_poc.orders",
                },
                {
                    "name": "customers",
                    "source": "heuristicwave_ossie_poc.customers",
                },
            ],
            "relationships": [
                {
                    "name": "orders_to_customers",
                    "from": "orders",
                    "to": "customers",
                    "from_columns": ["customer_id"],
                    "to_columns": ["customer_id"],
                }
            ],
            "metrics": [
                {
                    "name": "net_revenue",
                    "expression": {
                        "dialects": [
                            {
                                "dialect": "ANSI_SQL",
                                "expression": (
                                    "SUM(CASE WHEN orders.status <> 'CANCELLED' "
                                    "THEN orders.amount ELSE DECIMAL '0' END)"
                                ),
                            }
                        ]
                    },
                }
            ],
        }
    ]
}


class CompileMetricQueryTest(unittest.TestCase):
    def test_compiles_net_revenue_by_customer_region(self):
        sql = compile_metric_query(
            MODEL,
            metric_name="net_revenue",
            dimension_name="customers.region",
        )

        self.assertEqual(
            sql,
            """SELECT
  customers.region AS region,
  SUM(CASE WHEN orders.status <> 'CANCELLED' THEN orders.amount ELSE DECIMAL '0' END) AS net_revenue
FROM heuristicwave_ossie_poc.orders AS orders
LEFT JOIN heuristicwave_ossie_poc.customers AS customers
  ON orders.customer_id = customers.customer_id
GROUP BY customers.region
ORDER BY customers.region;""",
        )

    def test_reads_ossie_contract_and_tools_from_skill_markdown(self):
        manifest = parse_skill_manifest(
            """# Sales Semantic Skill

## Semantic contract

- URI: `s3://example/semantic/sales.ossie.yaml`
- Format: `apache-ossie`
- Target engine: `athena`

## Approved tools

- Compiler: `compile_ossie_metric`
- Executor: `execute_athena_query`
"""
        )

        self.assertEqual(
            manifest,
            {
                "semantic_contract_uri": (
                    "s3://example/semantic/sales.ossie.yaml"
                ),
                "semantic_contract_format": "apache-ossie",
                "target_engine": "athena",
                "compiler_tool": "compile_ossie_metric",
                "execution_tool": "execute_athena_query",
            },
        )


if __name__ == "__main__":
    unittest.main()
