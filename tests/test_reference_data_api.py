"""Full-stack tests for reference data REST endpoints and OpenAPI schema."""

from fastapi.testclient import TestClient


def test_regions_endpoint(client: TestClient):
    response = client.get("/api/regions")
    assert response.status_code == 200
    assert response.json() == [
        "East Asia & Pacific",
        "Europe & Central Asia",
        "Sub-Saharan Africa",
    ]


def test_countries_endpoint_and_region_filter(client: TestClient):
    all_resp = client.get("/api/countries")
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 4
    assert set(all_resp.json()[0].keys()) == {"iso3", "name"}

    filtered = client.get(
        "/api/countries", params={"region": "Europe & Central Asia"}
    )
    assert filtered.status_code == 200
    assert filtered.json() == [
        {"iso3": "FRA", "name": "France"},
        {"iso3": "ROU", "name": "Romania"},
    ]


def test_indicators_list_and_single_indicator(client: TestClient):
    list_resp = client.get("/api/indicators")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 3
    assert set(items[0].keys()) == {"code", "name"}

    detail_resp = client.get("/api/indicators/WHOSIS_000001")
    assert detail_resp.status_code == 200
    assert detail_resp.json() == {
        "code": "WHOSIS_000001",
        "name": "Life expectancy at birth",
        "unit": "years",
    }

    missing_resp = client.get("/api/indicators/UNKNOWN_CODE")
    assert missing_resp.status_code == 404


def test_openapi_schema_lists_api_and_excludes_html_pages(client: TestClient):
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/api/regions" in paths
    assert "/api/countries" in paths
    assert "/api/indicators" in paths
    assert "/api/indicators/{indicator_code}" in paths
    assert "/api/indicators/{indicator_code}/period-averages" in paths

    assert "/observations" not in paths
    assert "/period-averages" not in paths
    assert "/calculator" not in paths
