# Security Best Practices Report

## Executive Summary

The codebase has one critical backend issue: API endpoints that read and mutate financial data are exposed without authentication/authorization controls. There are also several medium issues around hardening (public API documentation exposure, missing frontend security headers/CSP posture, and unbounded upload memory usage) plus one low-severity configuration hygiene issue (development credentials in defaults).

## Critical Findings

### SP-001 - Unauthenticated API Access Across Sensitive Routes
- Rule ID: `FASTAPI-AUTH-001`, `FASTAPI-AUTHZ-001`
- Severity: Critical
- Location: `backend/app/main.py:17`, `backend/app/main.py:18`, `backend/app/main.py:19`, `backend/app/main.py:20`, `backend/app/main.py:21`, `backend/app/main.py:22`, `backend/app/main.py:23`, `backend/app/main.py:24`, `backend/app/main.py:25`, `backend/app/routers/categories.py:39`, `backend/app/routers/categories.py:60`, `backend/app/routers/categories.py:91`, `backend/app/routers/payees.py:51`, `backend/app/routers/payees.py:70`, `backend/app/routers/payees.py:97`, `backend/app/routers/transactions.py:219`, `backend/app/routers/transactions.py:256`, `backend/app/routers/imports.py:22`, `backend/app/routers/imports.py:36`
- Evidence:
  - All routers are included directly without auth dependencies in app bootstrap.
  - Write endpoints (`POST`, `PATCH`, `PUT`, `DELETE`) accept only DB session dependency (`Depends(get_db)`) and no identity/permission checks.
- Impact: Any client with network access to the API can read, create, modify, or delete financial records and import data.
- Fix:
  - Add centralized authentication dependency (e.g., JWT/Bearer or session) and enforce it at router level for all non-public routes.
  - Add authorization checks for object access/modification (ownership or role-based permissions).
  - Keep only explicit public routes unauthenticated (e.g., health check).
- Mitigation:
  - Restrict API network exposure at reverse proxy/firewall while auth is being implemented.
- False positive notes:
  - If auth is enforced entirely by an upstream gateway, verify this with runtime policy and mTLS/API-gateway config; app code currently does not enforce it.

## Medium Findings

### SP-002 - OpenAPI/Docs Endpoints Enabled by Default
- Rule ID: `FASTAPI-OPENAPI-001`
- Severity: Medium
- Location: `backend/app/main.py:7`
- Evidence:
  - App initializes with default `FastAPI(...)` and does not disable/protect `docs_url`, `redoc_url`, or `openapi_url`.
- Impact: API surface and schemas are easily discoverable, reducing attacker effort for endpoint and payload enumeration.
- Fix:
  - In production, set `docs_url=None`, `redoc_url=None`, `openapi_url=None`, or protect docs behind authentication/network allowlist.
- Mitigation:
  - Restrict docs routes at reverse proxy for production deployments.
- False positive notes:
  - If production ingress blocks these paths, verify with deployed route policy and external checks.

### SP-003 - Missing Frontend Security Headers/CSP Hardening
- Rule ID: `REACT-CSP-001`, `REACT-HEADERS-001`
- Severity: Medium
- Location: `frontend/nginx.conf:1`, `frontend/nginx.conf:7`, `frontend/nginx.conf:11`, `frontend/index.html:20`
- Evidence:
  - Nginx config contains routing/proxy rules but no explicit security headers (`Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options` or `frame-ancestors`, `Referrer-Policy`, `Permissions-Policy`).
  - HTML includes inline script block for theme initialization.
- Impact: Browser-side hardening against XSS/clickjacking/content-type confusion is weaker than recommended defaults.
- Fix:
  - Add security headers at Nginx/edge.
  - Move inline script to external file or use nonce/hash CSP strategy if inline script is required.
- Mitigation:
  - Start with CSP report-only mode to reduce breakage risk before enforcing.
- False positive notes:
  - If headers are injected by CDN/ingress, verify runtime response headers in production.

### SP-004 - Unbounded File Read in Import Upload Endpoints
- Rule ID: `FASTAPI-UPLOAD-001`
- Severity: Medium
- Location: `backend/app/routers/imports.py:23`, `backend/app/routers/imports.py:24`, `backend/app/routers/imports.py:37`, `backend/app/routers/imports.py:38`
- Evidence:
  - Upload handlers read full body into memory via `await file.read()` with no explicit size guard.
- Impact: Large uploads can increase memory pressure and can be abused for application-layer DoS.
- Fix:
  - Enforce explicit max upload size in app logic and proxy (`client_max_body_size`), with consistent limits and clear error handling.
  - Prefer streamed/chunked handling where practical.
- Mitigation:
  - Add rate limiting and request body limits at ingress.
- False positive notes:
  - Some deployments may already enforce strict body limits at API gateway; confirm configured and tested limits.

## Low Findings

### SP-005 - Development Credentials Embedded in Defaults
- Rule ID: `FASTAPI-SUPPLY-001` (config hygiene), general secure-defaults
- Severity: Low
- Location: `backend/app/config.py:8`, `docker-compose.yml:5`, `docker-compose.yml:6`, `docker-compose.yml:16`
- Evidence:
  - Default DB URL and compose env use `postgres:postgres`.
- Impact: If copied to non-dev environments, weak credentials materially increase compromise risk.
- Fix:
  - Require environment-provided strong credentials for non-development.
  - Add environment validation guard (fail startup if default credentials detected outside development).
- Mitigation:
  - Keep development-only compose isolated from external network exposure.
- False positive notes:
  - This is acceptable for local-only development; risk is credential reuse beyond local scope.

## Suggested Remediation Order
1. Implement authentication + authorization boundaries (SP-001).
2. Disable/protect API docs in production (SP-002).
3. Add upload/body-size guards in app and ingress (SP-004).
4. Add frontend security headers/CSP strategy (SP-003).
5. Harden credential defaults and environment validation (SP-005).
