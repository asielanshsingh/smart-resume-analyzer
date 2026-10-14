"""Shared Flask extension instances.

Rate limiting is OPTIONAL and defensive: if Flask-Limiter is not installed
(or fails to import), the application still boots and simply runs without
throttling. A missing dependency must never take the whole service down.
"""

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="memory://",
    )
except Exception:  # pragma: no cover - keep the app bootable no matter what
    limiter = None
