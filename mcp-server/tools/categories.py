"""MCP tools for categories."""
import client


def register(mcp):
    @mcp.tool()
    async def list_categories(q: str = None, limit: int = 50) -> list:
        """List all spending categories.

        Returns id, name, parent_id, color, icon, sort_order, is_custom, group.
        Use category IDs when filtering transactions or analytics by category.
        """
        return await client.get("/categories", q=q, limit=limit)

    @mcp.tool()
    async def get_category_tree() -> dict:
        """Get the full category tree with parent/child hierarchy, preset colors, and icons.

        Returns colors[], icons[], categories[], and tree[] (nested with children[]).
        """
        return await client.get("/categories/presets")
