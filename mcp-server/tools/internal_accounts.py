"""MCP tools for internal accounts (savings, investment, cash accounts)."""
import client


def register(mcp):
    @mcp.tool()
    async def list_internal_accounts() -> list:
        """List all internal accounts (Livret A, PEA, cash, etc.).

        Returns id, name, type, position, is_archived, split_count.
        Internal accounts are used to tag split internal movements (e.g. savings transfers).
        """
        return await client.get("/internal-accounts")

    @mcp.tool()
    async def create_internal_account(
        name: str,
        type: str = None,
        position: int = None,
    ) -> dict:
        """Create a new internal account.

        name: display name (e.g. "Livret A", "PEA", "Cash wallet")
        type: optional free-text type label (e.g. "savings", "investment", "cash")
        position: display order (0 = first). Defaults to appended at end.
        Returns the created internal account.
        """
        body = {"name": name}
        if type is not None:
            body["type"] = type
        if position is not None:
            body["position"] = position
        return await client.post("/internal-accounts", body)

    @mcp.tool()
    async def update_internal_account(
        account_id: int,
        name: str = None,
        type: str = None,
        position: int = None,
        is_archived: bool = None,
    ) -> dict:
        """Update an existing internal account.

        All parameters are optional — only provided fields are sent.
        is_archived: set True to hide the account from active lists.
        Returns the updated internal account.
        """
        body = {}
        if name is not None:
            body["name"] = name
        if type is not None:
            body["type"] = type
        if position is not None:
            body["position"] = position
        if is_archived is not None:
            body["is_archived"] = is_archived
        return await client.patch(f"/internal-accounts/{account_id}", body)

    @mcp.tool()
    async def delete_internal_account(account_id: int) -> dict:
        """Delete an internal account. Splits referencing it are unlinked.

        Returns deleted: true and split_count (number of splits unlinked).
        """
        return await client.delete(f"/internal-accounts/{account_id}")
