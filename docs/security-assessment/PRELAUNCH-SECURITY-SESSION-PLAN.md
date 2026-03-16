# Pre-Launch Security Session Plan

This plan is for future internet deployment (Render) of the current `personal-expense` app.
It is aligned to `personal-expense-threat-model.md` and assumes:
- app is currently local-only,
- internet publication is planned,
- user/admin flows are not implemented yet.

## Objective
Ship a public v1 without critical/high unresolved security risks for:
- unauthenticated data exposure and mutation,
- cross-user data access,
- upload abuse and storage abuse,
- deployment misconfiguration.

## Rules For Running Sessions
- Do not publish to internet before Session 4 completion.
- Keep each session focused on one security theme.
- For each session: implement, test, and add/update docs in same PR.
- Any change that touches auth/authorization requires integration tests.

## Priority Mapping
- TM-001: unauthenticated API access -> Sessions 1, 2, 4
- TM-002: upload abuse/DoS -> Sessions 3, 4
- TM-003: raw data exfiltration -> Sessions 2, 3, 4
- TM-004: cross-user access (future multi-user) -> Sessions 1, 2
- TM-005: CSRF risk (if cookie auth) -> Session 2
- TM-006: missing auditability -> Session 5
- TM-007: CI supply-chain risk -> Session 6
- TM-008: prod secrets/config risk -> Session 4

## Session Backlog

## Session 0 - Security Architecture Freeze
Goal: lock core security decisions before coding auth.

Deliverables:
- Decide auth model for v1: `Authorization: Bearer` preferred for API-first flow.
- Decide tenancy model: single-user now vs user-owned rows from day one.
- Decide deployment split on Render: frontend + backend services, private DB networking.
- Write short ADR in `docs/` with these decisions.

Exit criteria:
- You can answer: who can call which API and how identity is passed.
- You can answer: where DB and backend are reachable from.

Suggested prompt:
`Implement a security ADR for auth, tenancy, and Render deployment boundaries based on the existing threat model. Keep it short and explicit.`

## Session 1 - Identity Foundation (AuthN + Data Ownership)
Goal: add foundational user identity and row ownership in backend models/routes.

Deliverables:
- Introduce `users` table and user identity abstraction.
- Add ownership columns (`user_id`) to user-owned tables:
  - imports, import_rows, transactions, splits, categories, payees, moments, internal_accounts.
- Add migration strategy for existing local data.
- Introduce auth dependency in FastAPI and wire protected routers through dependency boundary.

Exit criteria:
- All non-health routes require authenticated identity.
- Each query/mutation is scoped by current `user_id`.
- Integration tests prove user A cannot read/write user B resources.

Suggested prompt:
`Add user identity and ownership scoping to backend models and routers, including alembic migrations and tests for cross-user access denial.`

## Session 2 - Authorization + Session/Token Security
Goal: harden auth flows and protect state-changing operations.

Deliverables:
- Implement token/session issuance and validation with strict expiry/rotation.
- Add role model for future admin flow (at least schema + guard hooks).
- Enforce object-level authorization in all ID-based routes.
- If cookie auth is chosen: implement CSRF tokens + SameSite strategy.
- Standardize error responses for auth/authz failures (401/403/404 policy).

Exit criteria:
- Every protected endpoint has explicit authz check semantics.
- No route accepts security tokens in URL query params.
- Tests cover auth bypass, IDOR, and CSRF (if cookie mode).

Suggested prompt:
`Harden auth and authorization across all FastAPI routers, add CSRF protections if cookie auth is used, and add regression tests for auth bypass and IDOR.`

## Session 3 - Import Surface Hardening (Uploads + Sensitive Data)
Goal: reduce import-related confidentiality and DoS risk.

Deliverables:
- Add strict request size limits (proxy + app-level guard).
- Add upload rate limiting (IP and/or user based) on import endpoints.
- Replace full in-memory upload reads with safer bounded/streaming handling where feasible.
- Introduce import retention policy:
  - configurable delete window for stored original CSV files,
  - optional endpoint/data minimization for `raw_json`.
- Ensure file serving stays attachment-safe and ownership-scoped.

Exit criteria:
- Oversized uploads are rejected early with clear errors.
- Repeated upload abuse is throttled.
- Sensitive raw import data exposure is reduced and owner-restricted.

Suggested prompt:
`Harden import endpoints against abuse by adding size limits, rate limiting, owner-scoped file access, and a retention/minimization strategy for raw import data.`

## Session 4 - Render Deployment Hardening
Goal: make production runtime secure-by-default.

Deliverables:
- Production config validation on startup:
  - fail fast on default/weak secrets,
  - fail fast when required env vars missing.
- Lock CORS to real frontend origin(s) only.
- Ensure backend is not publicly exposed unless required (prefer internal/private networking behind frontend/proxy).
- Add HTTPS-aware settings for cookies if used (`Secure` only in TLS environments).
- Add reverse-proxy hardening knobs (request/body limits, timeouts).

Exit criteria:
- Production startup fails on insecure config.
- CORS and network exposure are least privilege.
- Deployment checklist for Render exists in docs.

Suggested prompt:
`Implement production hardening for Render deployment: strict env validation, CORS tightening, secure network exposure defaults, and startup fail-fast checks.`

## Session 5 - Audit Trail + Detection
Goal: improve forensic visibility and integrity recovery.

Deliverables:
- Add append-only audit events for critical mutations:
  - transaction patch,
  - splits replace,
  - imports create/delete/download,
  - category/payee/internal account mutations.
- Include actor, resource, before/after summary, timestamp, request metadata.
- Add security-focused structured logs and basic anomaly counters.

Exit criteria:
- Critical state changes are attributable to actor + time + action.
- You can investigate suspicious mutation sequences from logs.

Suggested prompt:
`Add append-only audit logging and structured security events for critical API mutations, with tests ensuring audit records are always written.`

## Session 6 - CI/Supply Chain Hardening
Goal: reduce malicious update risk from dependencies/workflows.

Deliverables:
- Tighten GitHub workflow permissions to least privilege.
- Add CODEOWNERS gate for security-sensitive paths:
  - `backend/app/main.py`,
  - `backend/app/routers/`,
  - `backend/app/services/import_service.py`,
  - `.github/workflows/`.
- Add dependency and image vulnerability checks in CI.
- Add policy for `sync-components` workflow review before merge.

Exit criteria:
- Security-sensitive changes require explicit reviewer path.
- CI surfaces dependency risk before merge.

Suggested prompt:
`Harden GitHub workflows and repo policy for supply-chain risk: least-privilege permissions, CODEOWNERS on security paths, and dependency vulnerability checks in CI.`

## Session 7 - Security Regression Harness + Launch Gate
Goal: block launch until core security controls are verified.

Deliverables:
- Add integration security test suite:
  - unauthenticated access denied,
  - cross-user read/write denied,
  - CSRF protected (if cookie mode),
  - upload size/rate protections enforced,
  - sensitive data routes owner-scoped.
- Add pre-launch checklist document with explicit go/no-go criteria.
- Optional: run manual adversarial QA script for top abuse paths.

Exit criteria:
- All high/critical threat cases have automated coverage and pass.
- Launch checklist says `GO` with no unresolved critical/high findings.

Suggested prompt:
`Create a launch-blocking security regression suite and a go/no-go checklist mapped to the threat model IDs.`

## Launch Gate (Must Be True Before Public Release)
- No anonymous access to financial read/write endpoints.
- Ownership enforcement on all user data routes.
- Upload limits and throttling active in production.
- Secrets/config validation enforced at startup.
- Audit logging available for critical mutations.
- CI includes dependency/security checks and reviewer protections.

## Suggested Working Order
1. Session 0
2. Session 1
3. Session 2
4. Session 3
5. Session 4
6. Session 5
7. Session 6
8. Session 7

## Notes
- If you want fastest safe path to first public launch, prioritize Sessions 1-4 and 7.
- Session 5 and 6 materially improve long-term resilience and incident response and should still be done before broad adoption.
