"""MCP tools for Moments (event-based spending overlays)."""
import client


def register(mcp):
    @mcp.tool()
    async def list_moments(q: str = None, limit: int = 50) -> list:
        """List all Moments (event-based spending periods).

        Returns id, name, start_date, end_date, description, tagged_splits_count,
        expenses_total, income_total, and top_categories[].
        """
        return await client.get("/moments", q=q, limit=limit)

    @mcp.tool()
    async def get_moment(moment_id: int) -> dict:
        """Get full detail for a single Moment including spending totals and top categories."""
        return await client.get(f"/moments/{moment_id}")

    @mcp.tool()
    async def create_moment(
        name: str,
        start_date: str,
        end_date: str,
        description: str = None,
    ) -> dict:
        """Create a new Moment (event-based spending overlay).

        name: human-readable label (e.g. "Ski Trip Feb 2025")
        start_date / end_date: YYYY-MM-DD format
        description: optional free-text note
        Returns the created Moment object.
        """
        body = {"name": name, "start_date": start_date, "end_date": end_date}
        if description:
            body["description"] = description
        return await client.post("/moments", body)

    @mcp.tool()
    async def update_moment(
        moment_id: int,
        cover_image_url: str = None,
        name: str = None,
        description: str = None,
    ) -> dict:
        """Update fields on an existing Moment via PATCH /moments/{moment_id}.

        All parameters are optional — only provided fields are sent.
        cover_image_url: data URI string (e.g. data:image/svg+xml;base64,...)
        Returns the updated Moment object.
        """
        body = {}
        if cover_image_url is not None:
            body["cover_image_url"] = cover_image_url
        if name is not None:
            body["name"] = name
        if description is not None:
            body["description"] = description
        return await client.patch(f"/moments/{moment_id}", body)

    @mcp.tool()
    async def list_moment_tagged_splits(
        moment_id: int,
        q: str = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        """List the transaction splits currently tagged to a Moment.

        Returns rows[] with split_id, transaction_id, amount, label_raw, category, and note.
        """
        return await client.get(
            f"/moments/{moment_id}/tagged",
            q=q,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    async def refresh_moment_candidates(moment_id: int) -> dict:
        """Scan all transactions within a Moment's date range and generate candidate splits.

        Must be called before decide_moment_candidates. Returns inserted_count, touched_count,
        and status_counts (pending/accepted/rejected).
        """
        return await client.post(f"/moments/{moment_id}/candidates/refresh", {})

    @mcp.tool()
    async def list_moment_candidates(
        moment_id: int,
        status: str = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict:
        """List candidate splits for a Moment.

        status: filter by "pending" | "accepted" | "rejected" (omit for all)
        Returns rows[] with candidate id, split_id, status, and full split details
        (transaction_id, amount, label_raw, supplier_raw, operation_at, category_id).
        """
        return await client.get(
            f"/moments/{moment_id}/candidates",
            status=status,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    async def decide_moment_candidates(
        moment_id: int,
        split_ids: list[int],
        decision: str,
        confirm_reassign: bool = False,
    ) -> dict:
        """Accept or reject candidate splits for a Moment.

        decision: "accepted" (tags split to moment) | "rejected" (excludes it)
        split_ids: list of split IDs to decide (from list_moment_candidates)
        confirm_reassign: set True if splits are already tagged to another moment and you want to move them
        Returns updated_count and status_counts.
        """
        return await client.post(
            f"/moments/{moment_id}/candidates/decision",
            {"split_ids": split_ids, "decision": decision, "confirm_reassign": confirm_reassign},
        )
