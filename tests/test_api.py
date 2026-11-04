from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_redirect():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert response.headers["location"] == "/calculator"


def test_calculator_page():
    response = client.get("/calculator")
    assert response.status_code == 200
    assert "AI Longevity" in response.text
    assert "Step 1:" in response.text
    assert "Step 2: Chronic Medical Conditions" in response.text


def test_observations_page():
    response = client.get("/observations")
    assert response.status_code == 200
    assert "Global Health Observations" in response.text


def test_get_countries_api():
    response = client.get("/api/countries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_get_indicators_api():
    response = client.get("/api/indicators")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5


def test_get_observations_api():
    response = client.get("/api/observations?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 10
    if len(data) > 0:
        assert "country_iso3" in data[0]
        assert "indicator_code" in data[0]
        assert "year" in data[0]
