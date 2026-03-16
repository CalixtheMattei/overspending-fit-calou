"""MCP tools for analytics."""
import client


def register(mcp):
    @mcp.tool()
    async def get_spending_flow(
        start_date: str = None,
        end_date: str = None,
        exclude_transfers: bool = True,
        exclude_moment_tagged: bool = False,
    ) -> dict:
        """Get Sankey flow data showing how money moves across transaction types and categories.

        Dates in YYYY-MM-DD format.
        Returns nodes[], links[], and totals (income/expenses/refunds/transfers).
        """
        return await client.get(
            "/analytics/flow",
            start_date=start_date,
            end_date=end_date,
            exclude_transfers=exclude_transfers,
            exclude_moment_tagged=exclude_moment_tagged,
        )

    @mcp.tool()
    async def get_payee_analytics(
        start_date: str = None,
        end_date: str = None,
        granularity: str = "month",
        exclude_transfers: bool = True,
        exclude_moment_tagged: bool = False,
        limit: int = 10,
    ) -> dict:
        """Get top payees by spending with time series.

        granularity: day | week | month
        Returns rows[] with entity_id, entity_name, income, expense, net, and series[].
        """
        return await client.get(
            "/analytics/payees",
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            exclude_transfers=exclude_transfers,
            exclude_moment_tagged=exclude_moment_tagged,
            limit=limit,
        )

    @mcp.tool()
    async def get_category_analytics(
        category_ref: str,
        start_date: str = None,
        end_date: str = None,
        exclude_transfers: bool = True,
        exclude_moment_tagged: bool = False,
        include_children: bool = True,
    ) -> dict:
        """Get spending breakdown for a specific category or 'uncategorized'.

        category_ref: integer category ID or the string "uncategorized"
        Dates in YYYY-MM-DD format.
        Returns totals (income_abs, expense_abs, net), transaction_count, and branch nodes/links.
        """
        return await client.get(
            f"/analytics/category/{category_ref}",
            start_date=start_date,
            end_date=end_date,
            exclude_transfers=exclude_transfers,
            exclude_moment_tagged=exclude_moment_tagged,
            include_children=include_children,
        )
