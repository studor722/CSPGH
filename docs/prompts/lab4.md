# Lab 4: AI Assistance Prompt Log

**Course:** CSP in Global Health / Advanced Global Health Analytics  
**Student:** Tudor Stanichevici  
**Assistant & Model:** Gemini 4 Hydrogen  
**Date:** 2026-11-18  

---

## Prompt 1 – Planning & Integrating the REST API
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-18
- **Prompt:**
  > "Hi! Can you look at my current project and help me plan how to add the new REST API and the client-side averages page without breaking the calculator or the observations page?"
- **Result:**
  - Reviewed the existing controllers, services, and `base.html` layout.
  - Agreed to keep `/calculator`, `/observations`, and the globe/pipeline endpoints working, move OpenAPI docs to `/api/docs`, hide HTML pages from the API docs, and style the new page to match the existing theme.
- **Your changes:**
  - Confirmed we should keep the existing navigation structure and add the new page link in the top bar.

---

## Prompt 2 – Lookup Endpoints for Regions, Countries, and Indicators
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-18
- **Prompt:**
  > "Let's start with the lookup endpoints for the REST API: regions, countries (with an optional region filter), and indicators. Please make sure they only return the public fields the client needs and don't duplicate the old routes."
- **Result:**
  - Updated `app/repositories/observation_repository.py`, `app/services/observation_service.py`, `app/controllers/api/schemas.py`, `app/controllers/api/reference_data_api.py`, and `app/controllers/api_controller.py` (commits `f95f741`, `1ebfe82`).
- **Your changes:**
  - Kept the existing country list behavior for the calculator page so nothing broke there.

---

## Prompt 3 – Per-Period Indicator Averages Endpoint
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-18
- **Prompt:**
  > "Now let's build the backend for the per-period indicator averages endpoint. It should group years into periods in PostgreSQL, round the averages to two decimals, return missing periods as null, and return 404 or 422 when the indicator or query parameters are invalid."
- **Result:**
  - Added domain types in `app/domain.py`, repository aggregation in `app/repositories/period_average_repository.py`, service validation and series alignment in `app/services/period_average_service.py`, dependency wiring in `app/dependencies.py`, and routes in `app/controllers/api/period_average_api.py` and `app/main.py` (commits `f95f741`, `1ebfe82`).
- **Your changes:**
  - Checked the rounded numbers for Romania and France on life expectancy.

---

## Prompt 4 – Client-Side Page Shell and Filter Controls
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-18
- **Prompt:**
  > "Next, can you create the new averages page shell and the JavaScript modules so the page loads indicators, regions, and countries from the API and updates the filters without reloading?"
- **Result:**
  - Created `app/controllers/period_average_page_controller.py`, `app/templates/period_averages.html`, updated `app/templates/base.html`, and added `app/static/js/api-client.js`, `app/static/js/period-averages-model.js`, `app/static/js/period-averages-view.js`, and `app/static/js/period-averages-page.js` (commit `e5847d3`).
- **Your changes:**
  - Adjusted the page layout and colors so both light and dark modes match the rest of the app.

---

## Prompt 5 – Chart, Table, Sex Choice, and Single-Indicator Endpoint
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-18
- **Prompt:**
  > "Can you wire up the line chart and table on the averages page, cancel outdated requests when filters change quickly, and also add a sex filter plus an endpoint to fetch details for a single indicator?"
- **Result:**
  - Added Chart.js rendering, `textContent`-safe table rendering, `AbortController` request cancellation, the `sex` parameter on the API and page, and the single-indicator endpoint in `app/controllers/api/reference_data_api.py` (commits `1ebfe82`, `e5847d3`).
- **Your changes:**
  - Tested the `sex` filter with WHO life expectancy (`WHOSIS_000001`) since OWID life expectancy only stores both-sexes values.

---

## Prompt 6 – Automated Tests and Verification
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-18
- **Prompt:**
  > "Finally, please write the tests for the new repository, service, REST endpoints, and page shell, and help me verify the live API responses."
- **Result:**
  - Created `tests/test_period_average_service.py`, `tests/test_period_average_repository.py`, `tests/test_period_average_api.py`, `tests/test_reference_data_api.py`, and `tests/test_period_average_page_controller.py`, plus `docs/lab4_results.md` (commits `f95f741`, `1ebfe82`, `e5847d3`, `155ab98`).
- **Your changes:**
  - Fixed the API test overrides to target the test client's app instance so all 48 tests pass.
