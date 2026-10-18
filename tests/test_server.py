"""
tests/test_server.py
--------------------
Tests for ui/server.py ASGI Web Server endpoints.
"""

import pytest
from starlette.testclient import TestClient
from ui.server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_index_endpoint(client):
    """GET / serves the web index HTML file."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Zomato Concierge" in resp.text
    assert "Discovery Controls" in resp.text


def test_health_endpoint(client):
    """GET /api/health returns valid status and metadata."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Zomato Concierge AI"
    assert "dataset_rows" in data


def test_static_assets(client):
    """GET /css/style.css and /js/app.js are served properly."""
    css_resp = client.get("/css/style.css")
    assert css_resp.status_code == 200
    assert "Obsidian Gourmet Concierge" in css_resp.text

    js_resp = client.get("/js/app.js")
    assert js_resp.status_code == 200
    assert "conciergeApp" in js_resp.text


def test_locations_and_cuisines_endpoint(client):
    """Autocomplete endpoints return lists."""
    loc_resp = client.get("/api/locations")
    assert loc_resp.status_code == 200
    assert isinstance(loc_resp.json().get("locations"), list)

    cui_resp = client.get("/api/cuisines")
    assert cui_resp.status_code == 200
    assert isinstance(cui_resp.json().get("cuisines"), list)


def test_recommend_missing_location(client):
    """POST /api/recommend with missing location returns 400 error."""
    resp = client.post("/api/recommend", json={"location": ""})
    assert resp.status_code == 400
    assert resp.json()["success"] is False
    assert "Location is required" in resp.json()["error"]
