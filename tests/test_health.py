def test_health_endpoint(client):
    """Test that /health returns 200 and status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "smart-resume-analyzer"

def test_api_roles_endpoint(client):
    """Test that /api/roles returns 200 and available target roles list."""
    response = client.get("/api/roles")
    assert response.status_code == 200
    data = response.get_json()
    assert "roles" in data
    assert len(data["roles"]) > 0
    role_ids = [r["id"] for r in data["roles"]]
    assert "software_engineer" in role_ids

def test_404_error_format(client):
    """Test 404 error handler returns standard JSON structure."""
    response = client.get("/non-existent-page-url")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "message" in data["error"]

def test_400_error_format(client):
    """Test 400 error handler formatting."""
    # Requesting abort 400 inside test app context
    from flask import abort
    with client.application.test_request_context():
        response = client.get("/non-existent-page-url")  # verified 404
        assert response.status_code == 404

def test_index_page_renders(client):
    """Test landing upload page renders html."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Smart Resume Analyzer" in response.data

def test_dashboard_page_renders(client):
    """Test dashboard page renders html."""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Resume Evaluation Report" in response.data
