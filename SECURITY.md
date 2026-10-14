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
Fixed: `Flask-Limiter` (in-memory) applied to the API routes. `ProxyFix` added so
limits key off the real client IP. Imported defensively via `app/extensions.py`;
disabled under `TestingConfig`.

### [MEDIUM] Upload error message leaked internals
Fixed: `/api/upload` no longer returns exception text to the client.

### [LOW] /health disclosed version
Fixed: returns `status` + `service` only.

### [LOW] Missing transport/permission headers
Fixed: added `Strict-Transport-Security` and `Permissions-Policy`.

---

## DONE - Round 3: low-risk quick wins (additive only)

### [MEDIUM] File-type validation - ALREADY IMPLEMENTED (verified)
`app/services/parser.py::validate_file_content` already enforces extension
allow-list, size cap, and magic-byte checks (`%PDF` for pdf, `PK\x03\x04` for
docx), raising `MismatchedFileTypeError` on mismatch. No change needed - the
original finding was a false alarm.

### [MEDIUM] CORS - VERIFIED SAFE (no change needed)
No CORS library is installed and no `Access-Control-Allow-*` headers are set, so
the browser enforces same-origin by default. No wildcard origin exists.

### [LOW] API responses could be cached
Fixed: `Cache-Control: no-store` is now set on `/api/*` responses so browsers and
intermediary caches never retain personal resume data.

### [LOW] No crawler policy / security contact
Fixed: `/robots.txt` (disallows /api/, /dashboard, /result/) and
`/.well-known/security.txt` (RFC 9116 contact) are now served.

### [LOW] Dependency hygiene
Added `.github/workflows/security.yml` (pip-audit report + ruff + pytest) and
`.github/dependabot.yml` (weekly pip + actions updates).

---

## TODO - remaining problems, in priority order

### HIGH
1. Session-cookie scoping is NOT authentication. For anything long-lived, add
   real accounts (login + hashed passwords) and move `owner_token` to a
   `user_id` foreign key.

### MEDIUM
2. DB on `sqlite:////tmp/app.db` resets on every deploy and is single-instance.
   Move to managed Postgres before real traffic.

### LOW
3. Content-Security-Policy: DELIBERATELY DEFERRED. Templates load Tailwind via
   the Play CDN (`cdn.tailwindcss.com`) which needs inline/eval scripts, so a
   strict CSP would break the UI. Self-host the CSS first, then add a
   nonce-based policy.
4. CSRF protection once any authenticated state exists.

### VERIFY AFTER EACH FIX
- `curl -s https://<app>/api/history` in a fresh client -> empty list.
- `curl -s https://<app>/api/analysis/1` in a fresh client -> 404.
- `curl -I https://<app>/api/roles` -> contains `Cache-Control: no-store`.
- `curl -s https://<app>/robots.txt` and `/.well-known/security.txt` -> 200 text.
- Hammer `/api/upload` > 10x/min -> 429 with `RATE_LIMITED` JSON.
