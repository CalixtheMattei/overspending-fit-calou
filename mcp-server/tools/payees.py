"""MCP tools for payees."""
import client


def register(mcp):
    @mcp.tool()
    async def list_payees(q: str = None, limit: int = 20) -> list:
        """List known payees (merchants or persons).

        Returns id, name, kind (person | merchant | unknown), transaction_count.
        Use payee IDs when filtering transactions by payee.
        """
        return await client.get("/payees", q=q, limit=limit)

    @mcp.tool()
    async def list_automatic_payee_suggestions(
        q: str = None,
        limit: int = 20,
        include_ignored: bool = False,
    ) -> list:
        """List automatic payee suggestions derived from supplier names in imported CSVs.

        Returns name, canonical_name, linked_transaction_count, is_ignored.
        These can be confirmed into real payees via the UI.
        """
        return await client.get(
            "/payees/automatic",
            q=q,
            limit=limit,
            include_ignored=include_ignored,
        )
