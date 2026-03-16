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
        Use apply_automatic_payee_suggestion to confirm a suggestion into a real payee.
        """
        return await client.get(
            "/payees/automatic",
            q=q,
            limit=limit,
            include_ignored=include_ignored,
        )

    @mcp.tool()
    async def create_payee(name: str, kind: str = "unknown") -> dict:
        """Create a new payee manually.

        name: display name (e.g. "Decathlon", "Hamon Ocyane")
        kind: "person" | "merchant" | "unknown" (default: "unknown")
        Returns the created payee with id, name, kind, transaction_count.
        If a payee with the same canonical name already exists, returns the existing one.
        """
        return await client.post("/payees", {"name": name, "kind": kind})

    @mcp.tool()
    async def apply_automatic_payee_suggestion(
        seed_canonical_name: str,
        payee_name: str,
        kind: str = "merchant",
        overwrite_existing: bool = False,
    ) -> dict:
        """Confirm an automatic payee suggestion: creates the payee and bulk-assigns it
        to all matching transactions from that seed.

        seed_canonical_name: canonical_name from list_automatic_payee_suggestions
        payee_name: display name to use for the new payee
        kind: "person" | "merchant" | "unknown"
        overwrite_existing: if True, reassigns transactions already linked to another payee
        Returns payee, matched_transaction_count, updated_transaction_count.
        """
        return await client.post("/payees/automatic/apply", {
            "seed_canonical_name": seed_canonical_name,
            "payee_name": payee_name,
            "kind": kind,
            "overwrite_existing": overwrite_existing,
        })

    @mcp.tool()
    async def update_payee(
        payee_id: int,
        name: str = None,
        kind: str = None,
    ) -> dict:
        """Update a payee's name or kind.

        All parameters are optional — only provided fields are sent.
        kind: "person" | "merchant" | "unknown"
        Returns the updated payee.
        """
        body = {}
        if name is not None:
            body["name"] = name
        if kind is not None:
            body["kind"] = kind
        return await client.patch(f"/payees/{payee_id}", body)

    @mcp.tool()
    async def delete_payee(payee_id: int) -> dict:
        """Delete a payee. Transactions linked to it are unlinked.

        Returns deleted: true and transaction_count (number of transactions unlinked).
        """
        return await client.delete(f"/payees/{payee_id}")
