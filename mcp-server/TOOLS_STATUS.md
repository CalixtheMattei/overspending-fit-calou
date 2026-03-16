# MCP Server — Tools Status

Source of truth for what's implemented, what's deferred, and why.
Update this file at the end of every coding session.

---

## Session 1 — 2026-03-04

### Implemented (14 tools across 6 modules)

| Tool | Module | Endpoint | Notes |
|---|---|---|---|
| `list_transactions` | transactions | GET /transactions | status, type, q, payee_id, category_id, limit, offset |
| `get_transaction` | transactions | GET /transactions/{id} | full detail with splits |
| `get_transaction_summary` | transactions | GET /transactions/summary | uncategorized count + 30d % |
| `get_spending_flow` | analytics | GET /analytics/flow | Sankey data, date range, exclude_transfers |
| `get_payee_analytics` | analytics | GET /analytics/payees | top N payees with time series |
| `get_category_analytics` | analytics | GET /analytics/category/{ref} | drilldown, ref = int ID or "uncategorized" |
| `list_moments` | moments | GET /moments | q, limit |
| `get_moment` | moments | GET /moments/{id} | single moment detail |
| `create_moment` | moments | POST /moments | name, start_date, end_date, description |
| `list_moment_tagged_splits` | moments | GET /moments/{id}/tagged | splits tagged to a moment |
| `list_categories` | categories | GET /categories | q, limit |
| `get_category_tree` | categories | GET /categories/presets | full tree with hierarchy |
| `list_payees` | payees | GET /payees | q, limit |
| `list_automatic_payee_suggestions` | payees | GET /payees/automatic | q, limit, include_ignored |
| `list_rules` | rules | GET /rules | all rules read-only |
| `get_rule_impacts` | rules | GET /rules/{id}/impacts | rule impact history |

### Infrastructure created
- `mcp-server/server.py` — FastMCP entry point, stdio + SSE transport
- `mcp-server/client.py` — shared httpx proxy helpers (get, post, patch, delete)
- `mcp-server/requirements.txt` — mcp[cli], httpx
- `mcp-server/Dockerfile` — python:3.12-slim
- `docker-compose.yml` — added `mcp` service (SSE port 3001)
- `.claude/settings.local.json` — mcpServers block for local stdio dev
- `.env.example` — MCP_HOST_PORT added

---

## Deferred — Session 2 (target: after splits QA is complete)

| Tool | Endpoint | Reason deferred |
|---|---|---|
| `update_transaction` | PATCH /transactions/{id} | Simple, safe. Add in session 2 |
| `update_splits` | PUT /transactions/{id}/splits | Requires split-sum invariant to be QAed first. Complex confirm_reassign flow |
| `update_moment` | PATCH /moments/{id} | Low priority, trivial once decided to add |
| `delete_moment` | DELETE /moments/{id} | Destructive — add with explicit warning in docstring |
| `get_transaction_rule_history` | GET /transactions/{id}/rule-history | Nice-to-have, add with rules tools |

## Deferred — Session 3 (target: after rules engine QA)

| Tool | Endpoint | Reason deferred |
|---|---|---|
| `run_rules` | POST /rules/run | State mutation + dry_run/apply scope. Needs QA coverage first |
| `preview_rule` | POST /rules/preview | Complex matcher/action JSON schema — needs examples |
| `create_rule` | POST /rules | Add only after run_rules is verified |
| `apply_payee_suggestion` | POST /payees/automatic/apply | Low risk but add alongside payee write tools |
| `create_payee` | POST /payees | Add in session 3 |

## Deferred — Not prioritized

| Tool | Endpoint | Reason |
|---|---|---|
| `import_csv` | POST /imports | File upload via MCP is awkward; use UI for imports |
| `list_import_rows` | GET /imports/rows | Useful for debugging, low priority |
| `get_category_transactions` | GET /analytics/category/{ref}/transactions | Add when category drilldown workflow is common |
| `get_internal_account_analytics` | GET /analytics/internal-accounts | Add when needed |

---

## Known issues / TODOs

- [ ] FastMCP SSE `host` parameter: verify `mcp.run(transport="sse", host=..., port=...)` signature matches installed mcp version — may need `mcp.settings.host` instead
- [ ] No auth on the MCP server itself — it trusts anyone who can reach port 3001. Fine for private VPS; add token check if exposed publicly
- [ ] `client.py` creates a new `httpx.AsyncClient` per call — acceptable for low-volume MCP usage, but consider a persistent client if needed
