"""MCP tools for transactions."""
import client


def register(mcp):
    @mcp.tool()
    async def list_transactions(
        status: str = "uncategorized",
        type: str = "all",
        q: str = None,
        payee_id: int = None,
        category_id: int = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        """List transactions with optional filters.

        status: uncategorized | categorized | all
        type: expense | income | refund | transfer | all
        q: free-text search (label, supplier, payee name)
        Returns rows[], total, limit, offset.
        """
        return await client.get(
            "/transactions",
            status=status,
            type=type,
            q=q,
            payee_id=payee_id,
            category_id=category_id,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    async def get_transaction(transaction_id: int) -> dict:
        """Get full detail for a single transaction including its splits, category provenance, and split balance status."""
        return await client.get(f"/transactions/{transaction_id}")

    @mcp.tool()
    async def get_transaction_summary() -> dict:
        """Get high-level categorization stats: uncategorized count, uncategorized total, and categorized % over last 30 days."""
        return await client.get("/transactions/summary")
