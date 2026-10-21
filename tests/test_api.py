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
    assert "Personal Longevity Calculator" in response.text
    assert "Step 1: Your Baseline Origin" in response.text


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


def test_country_baseline_api():
    response = client.get("/api/country/USA/baseline")
    assert response.status_code == 200
    data = response.json()
    assert data["iso3"] == "USA"
    assert "life_expectancy" in data
    assert data["life_expectancy"] > 50


def test_calculator_evaluate_api():
    payload = {
        "country_iso3": "USA",
        "current_age": 30,
        "sex": "BTSX",
        "smoking": "heavy",
        "alcohol": "excessive",
        "exercise": "sedentary",
        "bmi": "obese",
    }
    response = client.post("/api/calculator/evaluate", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["country_iso3"] == "USA"
    assert res["net_habit_impact"] < 0
    assert res["predicted_life_expectancy"] < res["baseline_life_expectancy"]
    assert "smoking" in res["factors"]
