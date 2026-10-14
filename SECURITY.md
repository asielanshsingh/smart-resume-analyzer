# Security Hardening Plan

Black-box pentest of the deployed app (`smart-resume-analyzer-4lji.onrender.com`)
plus a source review of this repository. Status tracked below.

## Severity legend
- CRITICAL - exploitable exposure of other people's data or full compromise
- HIGH - abuse / DoS / auth gaps
- MEDIUM - information disclosure, weak defaults
- LOW - hygiene

---

## FIXED in this branch (security/fix-access-control)

### [CRITICAL] Broken access control on /api/history
Every stored analysis (all users) was returned to any unauthenticated caller.
Fix: analyses are now scoped to an anonymous per-visitor `owner_token`
(signed session cookie). `/api/history` only returns the caller's own records.

### [CRITICAL] IDOR on /api/analysis/<identifier>
Numeric primary keys were enumerable and returned full records including
contact PII (`include_sensitive=True`). Fix: numeric IDs now require session
ownership; only unguessable `share_token`s remain a public access path.

### [HIGH] Unscoped IDOR on /api/analyze + /api/upload
Any `resume_id` could be analyzed by anyone; upload dedup returned another
visitor's row for a matching file hash. Fix: upload sets `owner_token`,
dedup is scoped per-owner, and analyze enforces ownership.

Files changed: `app/__init__.py`, `app/models.py`, `app/routes/api.py`
(schema migration `_migrate_owner_token` auto-adds the column on deploy).

---

## TODO - remaining problems, in priority order

### HIGH
1. Rate limiting / abuse control (no throttling anywhere)
   - Add `Flask-Limiter` per-IP limits on `/api/analyze`, `/api/upload`,
     `/api/analysis/*`, `/api/history`.
   - Tune for the free Render instance to avoid self-DoS.

2. Session-cookie scoping is not authentication
   - For anything long-lived, replace anonymous sessions with real accounts
     (login + hashed passwords) and move `owner_token` to `user_id`.

### MEDIUM
3. Upload info leak: bare `except Exception as e:` in `upload_resume`
   returns `f"...: {e!s}"` to the client (internal error text).
   - Return a generic message; log the detail server-side only.

4. In-memory/SQLite at `sqlite:////tmp/app.db` resets on every deploy and is
   single-instance. Move to managed Postgres before real traffic.

5. CORS: confirm no permissive `Access-Control-Allow-Origin: *` on API routes.

6. File-type validation: verify magic bytes (not just extension) for PDF/DOCX
   before parsing; keep server-side `MAX_CONTENT_LENGTH` enforced.

### LOW
7. `/health` exposes `service` + `version` - drop version in prod.
8. Add `robots.txt` / `security.txt`; add `Content-Security-Policy` and
   `Strict-Transport-Security` headers (currently only nosniff/frame/referrer).
9. Add CSRF protection once any authenticated state exists.
10. Dependency hygiene: pin versions and run `pip-audit` in CI
    (pdfplumber/pypdf/python-docx parser CVEs).

### VERIFY AFTER EACH FIX
- `curl -s https://<app>/api/history` in a fresh (no-cookie) client -> empty list.
- `curl -s https://<app>/api/analysis/1` in a fresh client -> 404.
- `curl -I https://<app>/` -> check security headers present.
