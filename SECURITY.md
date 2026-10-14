# Security Hardening Plan

Black-box pentest of the deployed app (`smart-resume-analyzer-4lji.onrender.com`)
plus a source review of this repository. Status tracked below.

## Severity legend
- CRITICAL - exploitable exposure of other people's data or full compromise
- HIGH - abuse / DoS / auth gaps
- MEDIUM - information disclosure, weak defaults
- LOW - hygiene

---

## DONE - Round 1: access control

### [CRITICAL] Broken access control on /api/history
Fixed: analyses are scoped to an anonymous per-visitor `owner_token` (signed
session cookie). The endpoint returns only the caller's own records.

### [CRITICAL] IDOR on /api/analysis/<identifier>
Fixed: numeric primary-key IDs require session ownership; only unguessable
`share_token`s remain a public access path.

### [HIGH] Unscoped IDOR on /api/analyze + /api/upload
Fixed: uploads carry `owner_token`, dedup is scoped per owner, analyze enforces
ownership. Schema migration `_migrate_owner_token` adds the column on deploy.

---

## DONE - Round 2: abuse control + disclosure + headers

### [HIGH] No rate limiting
Fixed: `Flask-Limiter` (in-memory) applied to `/api/upload`, `/api/analyze`,
`/api/analysis/*`, `/api/history`, `/api/score`, `/api/ats`. `ProxyFix` added so
limits key off the real client IP (not Render's proxy IP). Limiter is imported
defensively via `app/extensions.py` - if the dependency is ever missing the app
still boots. Throttling is disabled under `TestingConfig`.

### [MEDIUM] Upload error message leaked internals
Fixed: `/api/upload` no longer returns `f"...: {e!s}"` to the client; details
stay in the server log.

### [LOW] /health disclosed version
Fixed: `/health` and `/api/health` now return `status` + `service` only (no
`version`). Kept `service` because `tests/test_health.py` asserts on it.

### [LOW] Missing transport/permission headers
Fixed: added `Strict-Transport-Security` and `Permissions-Policy` on top of the
existing `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.

---

## TODO - remaining problems, in priority order

### HIGH
1. Session-cookie scoping is NOT authentication. For anything long-lived,
   add real accounts (login + hashed passwords) and move `owner_token` to a
   `user_id` foreign key.

### MEDIUM
2. DB on `sqlite:////tmp/app.db` resets on every deploy and is single-instance.
   Move to managed Postgres before real traffic.
3. CORS: confirm no permissive `Access-Control-Allow-Origin: *` on API routes.
4. File-type validation: verify magic bytes (not just extension) for PDF/DOCX
   before parsing; keep server-side `MAX_CONTENT_LENGTH` enforced.

### LOW
5. Content-Security-Policy: DELIBERATELY DEFERRED. The templates load Tailwind
   via the Play CDN (`cdn.tailwindcss.com`) which needs inline/eval scripts, so a
   strict CSP would break the UI. To enable CSP safely, first self-host the CSS
   (drop the CDN), then add a nonce-based policy.
6. robots.txt / security.txt.
7. CSRF protection once any authenticated state exists.
8. Dependency hygiene: pin versions and run `pip-audit` in CI.

### VERIFY AFTER EACH FIX
- `curl -s https://<app>/api/history` in a fresh (no-cookie) client -> empty list.
- `curl -s https://<app>/api/analysis/1` in a fresh client -> 404.
- `curl -I https://<app>/` -> HSTS + Permissions-Policy present.
- Hammer `/api/upload` > 10x/min -> 429 with `RATE_LIMITED` JSON.
