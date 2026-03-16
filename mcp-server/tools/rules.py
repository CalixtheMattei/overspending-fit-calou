"""MCP tools for categorization rules."""
import client


def register(mcp):
    @mcp.tool()
    async def list_rules() -> list:
        """List all auto-categorization rules.

        Returns id, name, priority, enabled, matcher_json (conditions), action_json (what to apply),
        and timestamps. Rules are applied in priority order to auto-categorize transactions on import.
        """
        return await client.get("/rules")

    @mcp.tool()
    async def create_rule(
        name: str,
        matcher_json: dict,
        action_json: dict,
        priority: int | None = None,
        enabled: bool = True,
    ) -> dict:
        """Create a new auto-categorization rule.

        matcher_json format:
          {"all": [{"predicate": "supplier_contains", "value": "sncf"}]}
          {"any": [{"predicate": "supplier_contains", "value": "x"}, {"predicate": "label_contains", "value": "y"}]}
          Predicates: supplier_contains, label_contains, label_regex, type_is, amount_equals, amount_between

        action_json format:
          {"set_type": "expense", "set_category": 25}
          set_type values: expense, income, transfer, refund
          set_category: integer category id

        priority: lower number = higher priority. If omitted, rule is prepended above existing rules.
        """
        payload = {
            "name": name,
            "matcher_json": matcher_json,
            "action_json": action_json,
            "enabled": enabled,
        }
        if priority is not None:
            payload["priority"] = priority
        return await client.post("/rules", payload)

    @mcp.tool()
    async def run_rules(
        scope: str = "all",
        mode: str = "apply",
        allow_overwrite: bool = False,
        rule_ids: list[int] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        """Run rules against transactions and apply categorizations.

        scope: "all" | "date_range" (requires date_from/date_to) | "import" (requires import_id)
        mode: "apply" (default, saves changes) | "dry_run" (preview only, no save)
        allow_overwrite: if True, re-categorize already-categorized transactions
        rule_ids: optional list of specific rule IDs to run (default: all enabled rules)

        Returns a batch summary with counts of applied/skipped transactions.
        """
        payload: dict = {"scope": scope, "mode": mode, "allow_overwrite": allow_overwrite}
        if rule_ids is not None:
            payload["rule_ids"] = rule_ids
        if date_from is not None:
            payload["date_from"] = date_from
        if date_to is not None:
            payload["date_to"] = date_to
        return await client.post("/rules/run", payload)

    @mcp.tool()
    async def preview_rule(
        matcher_json: dict,
        action_json: dict,
        scope: str = "all",
        mode: str = "non_destructive",
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """Preview which transactions a rule would affect, without saving anything.

        matcher_json / action_json: same format as create_rule.
        scope: "all" | "date_range"
        mode: "non_destructive" (only uncategorized) | "destructive" (would overwrite existing)
        Returns rows[] of matching transactions with before/after state.
        """
        payload = {
            "scope": {"type": scope},
            "matcher_json": matcher_json,
            "action_json": action_json,
            "mode": mode,
            "limit": limit,
            "offset": offset,
        }
        return await client.post("/rules/preview", payload)

    @mcp.tool()
    async def get_rule_impacts(
        rule_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get the history of transactions affected by a specific rule.

        Returns rows[] with transaction_id, status, before/after state, and applied_at timestamp.
        """
        return await client.get(f"/rules/{rule_id}/impacts", limit=limit, offset=offset)
