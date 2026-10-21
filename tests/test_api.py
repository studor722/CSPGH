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


def test_chronic_diseases_api():
    response = client.get("/api/chronic-diseases")
    assert response.status_code == 200
    data = response.json()
    assert "cardiovascular" in data
    assert "diabetes" in data
    assert data["cardiovascular"]["loss_years"] > 0


def test_country_baseline_api():
    response = client.get("/api/country/ROU/baseline")
    assert response.status_code == 200
    data = response.json()
    assert data["iso3"] == "ROU"
    assert "life_expectancy" in data
    assert data["life_expectancy"] > 60


def test_calculator_evaluate_with_chronic_diseases():
    payload = {
        "country_iso3": "ROU",
        "current_age": 45,
        "sex": "BTSX",
        "chronic_diseases": ["cardiovascular", "diabetes"],
        "smoking": "heavy",
        "alcohol": "heavy",
        "exercise": "sedentary",
        "bmi": "obese",
        "sleep": "deprived",
    }
    response = client.post("/api/calculator/evaluate", json=payload)
    assert response.status_code == 200
    res = response.json()
    assert res["country_iso3"] == "ROU"
    assert res["disease_penalty"] > 0
    assert res["predicted_life_expectancy"] < res["baseline_life_expectancy"]
    assert len(res["active_chronic_diseases"]) == 2
    assert len(res["feature_contributions"]) >= 5
    assert len(res["potential_recoveries"]) > 0
