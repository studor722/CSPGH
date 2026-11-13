"""HTTP tests for the SSR /observations controller and filter form coercion."""

from app.dependencies import get_observation_service
from app.repositories.observation_repository import ObservationRepository
from app.services.observation_service import ObservationService


def test_observations_page_is_pure_ssr_and_lists_rows(client):
    response = client.get("/observations")
    assert response.status_code == 200
    assert "Global Health Observations" in response.text
    assert "<script" not in response.text.lower()
    assert "Romania" in response.text
    assert "Kenya" in response.text
    assert "Japan" in response.text
    assert "Showing 10 of 10 observations" in response.text


def test_observations_region_and_sex_filters(client):
    region_resp = client.get("/observations?region=Sub-Saharan+Africa")
    assert region_resp.status_code == 200
    assert "Showing 2 of 2 observations" in region_resp.text
    tbody = region_resp.text.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    assert "Kenya" in tbody
    assert "Romania" not in tbody

    sex_resp = client.get("/observations?country=ROU&sex=MLE")
    assert sex_resp.status_code == 200
    assert "Showing 2 of 2 observations" in sex_resp.text
    sex_tbody = sex_resp.text.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    assert "72.10" in sex_tbody
    assert "37.40" in sex_tbody
    assert "79.20" not in sex_tbody


def test_blank_and_invalid_filters_degrade_to_none_while_bad_page_422(client):
    clean_resp = client.get(
        "/observations?country=&indicator=&region=&year_from=abc&year_to=&sex=BOGUS&is_outlier=maybe"
    )
    assert clean_resp.status_code == 200
    assert "Showing 10 of 10 observations" in clean_resp.text

    bad_page = client.get("/observations?page=0")
    assert bad_page.status_code == 422


def test_pagination_links_preserve_active_filters(client, db_session):
    def _small_page_service() -> ObservationService:
        return ObservationService(ObservationRepository(db_session), page_size=2)

    client.app.dependency_overrides[get_observation_service] = _small_page_service

    resp = client.get("/observations?region=Europe+%26+Central+Asia&sex=FMLE&page=1")
    assert resp.status_code == 200
    assert "Showing 2 of 2 observations" in resp.text

    resp_multi = client.get("/observations?region=Europe+%26+Central+Asia&page=1")
    assert resp_multi.status_code == 200
    assert "Page 1 of 3" in resp_multi.text
    assert "region=Europe+%26+Central+Asia&amp;page=2" in resp_multi.text or (
        "region=Europe+%26+Central+Asia&page=2" in resp_multi.text
    )

    resp_p2 = client.get("/observations?region=Europe+%26+Central+Asia&page=2")
    assert resp_p2.status_code == 200
    assert "Page 2 of 3" in resp_p2.text
    assert "page=1" in resp_p2.text
    assert "page=3" in resp_p2.text


def test_empty_filter_result_shows_available_year_hint(client):
    resp = client.get("/observations?country=KEN&year_from=2025")
    assert resp.status_code == 200
    assert "No observations matched the specified filter criteria" in resp.text
    assert "2020" in resp.text


def test_contradictory_country_and_region_explains_conflict_and_groups_countries(client):
    resp = client.get("/observations?country=ROU&region=North+America")
    assert resp.status_code == 200
    assert '<optgroup label="Europe &amp; Central Asia">' in resp.text
    assert "Romania (ROU) belongs to &#39;Europe &amp; Central Asia&#39;, not &#39;North America&#39;." in resp.text
    assert "Clear Region filter" in resp.text
    assert 'href="/observations?country=ROU"' in resp.text
