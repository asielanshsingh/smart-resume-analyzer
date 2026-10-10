"""
Tests for global error handlers:
  - 404 on unknown routes
  - 405 wrong HTTP method on API endpoints
  - 400 malformed / missing-field JSON on /api/analyze and /api/score
  - 413 oversized upload
"""
import io

import pytest


class TestNotFoundHandler:
    def test_unknown_route_returns_404_json(self, client):
        resp = client.get("/this/does/not/exist")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "NOT_FOUND"

    def test_unknown_api_route_returns_404_json(self, client):
        resp = client.get("/api/does-not-exist")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "NOT_FOUND"


class TestMethodNotAllowedHandler:
    def test_get_on_upload_returns_405_json(self, client):
        resp = client.get("/api/upload")
        assert resp.status_code == 405
        data = resp.get_json()
        assert data["error"]["code"] == "METHOD_NOT_ALLOWED"

    def test_get_on_analyze_returns_405_json(self, client):
        resp = client.get("/api/analyze")
        assert resp.status_code == 405
        data = resp.get_json()
        assert data["error"]["code"] == "METHOD_NOT_ALLOWED"

    def test_post_on_roles_returns_405_json(self, client):
        resp = client.post("/api/roles")
        assert resp.status_code == 405
        data = resp.get_json()
        assert data["error"]["code"] == "METHOD_NOT_ALLOWED"


class TestMalformedJsonHandler:
    def test_analyze_non_json_body_returns_400(self, client):
        resp = client.post(
            "/api/analyze",
            data="not json at all",
            content_type="application/json",
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "BAD_REQUEST"

    def test_analyze_missing_content_type_returns_400(self, client):
        resp = client.post("/api/analyze", data="{}")
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "BAD_REQUEST"

    def test_score_missing_resume_id_returns_400(self, client):
        resp = client.post(
            "/api/score",
            json={},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "BAD_REQUEST"

    def test_analyze_missing_resume_id_returns_400(self, client):
        resp = client.post(
            "/api/analyze",
            json={"role_id": "software_engineer"},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "BAD_REQUEST"

    def test_analyze_missing_role_returns_400(self, client):
        resp = client.post(
            "/api/analyze",
            json={"resume_id": 1},
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "BAD_REQUEST"


class TestOversizedUploadHandler:
    def test_oversized_file_returns_413(self, client):
        """Uploading a file that exceeds MAX_CONTENT_LENGTH (5 MB in TestingConfig)."""
        large_bytes = b"%PDF-1.4 " + b"A" * (6 * 1024 * 1024)  # 6 MB
        resp = client.post(
            "/api/upload",
            data={"file": (io.BytesIO(large_bytes), "big_resume.pdf")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 413
        data = resp.get_json()
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


class TestSecurityHeaders:
    def test_security_headers_on_health(self, client):
        resp = client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_security_headers_on_api(self, client):
        resp = client.get("/api/roles")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
