"""Tests that the /period-averages HTML shell and JS modules are served without a DB."""

from fastapi.testclient import TestClient

from app.main import app


def test_period_averages_shell_and_scripts_served_without_db():
    client = TestClient(app)

    page = client.get("/period-averages")
    assert page.status_code == 200
    assert 'id="averages-chart"' in page.text
    assert 'id="averages-table"' in page.text
    assert 'href="/api/docs"' in page.text

    for js_file in (
        "api-client.js",
        "period-averages-model.js",
        "period-averages-view.js",
        "period-averages-page.js",
    ):
        resp = client.get(f"/static/js/{js_file}")
        assert resp.status_code == 200
        assert len(resp.text) > 0
