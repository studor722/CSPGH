# Lab 3: AI Assistance Prompt Log

**Course:** CSP in Global Health / Advanced Global Health Analytics  
**Student:** Tudor Stanichevici  
**Assistant & Model:** Gemini 4 Hydrogen  
**Date:** 2026-11-13  

This document logs the step-by-step prompts sent to Gemini 4 Hydrogen to implement Lab 3 (refactoring `/observations` and ETL runners into a layered architecture with pure server-side rendering, pagination, on-demand ETL web actions, `sex` filter support, per-layer unit/HTTP tests, and AST dependency checks).

---

## Prompt 1 – Planning & Integrating Lab 3 into the Existing App
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-13
- **Prompt:**
  > "Hi! Here is my Lab 3 PDF about server-side rendering and layered architecture. Before changing files, can you inspect my current `app/main.py`, templates, and `etl/import_*.py` scripts and ask me any planning questions so we don't break the existing 3D globe calculator or `/api/*` endpoints from Lab 2?"
- **Result:**
  - Reviewed `app/main.py`, `app/templates/base.html`, `app/templates/observations.html`, and the existing `etl/import_*.py` modules.
  - Agreed on keeping `/calculator` and all `/api/*` endpoints intact while refactoring `/observations` and ETL actions into one-way layers (`controllers -> services -> repositories -> domain/models`), preserving our dark/light styling in `base.html`, keeping `/observations` 100% pure SSR (no JS), and keeping Lab 2's `is_outlier` filter alongside `country`, `indicator`, `region`, `year_from`, `year_to`, and `sex`.

---

## Prompt 2 – Shared ETL `StepResult` and `import_runner` (Layer Refactor)
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-13
- **Prompt:**
  > "Right now `etl/import_who.py`, `etl/import_worldbank.py`, and `etl/import_owid.py` repeat the same loop over files and return plain dicts or print directly to the console. Can you extract a typed `StepResult` class in `etl/step_result.py` and a shared runner in `etl/import_runner.py` so both CLI runs (`python -m etl.import_...`) and a future web service can call `import_all()` and get structured `ok` / `skipped` / `failed` results?"
- **Result:**
  - `etl/step_result.py`: Added `StepStatus` (`ok`, `skipped`, `failed`) and frozen `StepResult` dataclass with `from_error(...)`.
  - `etl/import_runner.py`: Added `SourceSpec`, `IndicatorSpec`, `import_for_loaded_countries()`, `import_worldbank_source()`, and `report_and_exit_on_failure()`.
  - Refactored `etl/import_who.py`, `etl/import_worldbank.py`, and `etl/import_owid.py` to declare `SOURCE` and `INDICATORS` specs and expose `import_all() -> list[StepResult]`.
  - Committed in `ec6d0b4` (*Lab 3: import scripts return results through import_all()*).
- **Your changes:**
  - Kept the exact `raw_filename` strings matching the cached snapshots in `data/raw/who/`, `data/raw/worldbank/`, and `data/raw/owid/` (`WHOSIS_000001_from2000.json`, `life-expectancy_full.csv`, etc.), and verified `python -m etl.import_owid` still exits cleanly from the terminal.

---

## Prompt 3 – Domain Value Objects & Repository Layer (`app/domain.py`, `app/repositories/`)
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-13
- **Prompt:**
  > "Now let's move all the raw SQLAlchemy queries out of `app/main.py`. Create pure Python dataclasses in `app/domain.py` (`Option`, `FilterOptions`, `ObservationCriteria`, `ObservationListItem`, `YearBounds`, plus read-only summaries for `/calculator` and `/api/*`) and build `ObservationRepository` in `app/repositories/observation_repository.py`. Make sure `app/domain.py` has zero FastAPI or SQLAlchemy imports and that pagination sorting has a deterministic tie-breaker so page 1 and page 2 never duplicate rows."
- **Result:**
  - Created `app/domain.py`, `app/repositories/__init__.py`, and `app/repositories/observation_repository.py`.
  - Added `_STABLE_ORDER` ending with `Observation.observation_id` so `LIMIT`/`OFFSET` queries stay deterministic across pages.
  - Implemented `find()`, `count()`, `available_year_bounds()`, `list_countries()`, `list_indicators()`, `list_regions()`, and catalog helpers.
  - Committed in `f9440fd` (*Lab 3: domain types and observation repository*).

---

## Prompt 4 – Service Layer (`app/services/`), Dependencies, & FastAPI Controllers (`app/controllers/`)
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-13
- **Prompt:**
  > "Next I need `ObservationService` (handling pagination math, `DEFAULT_PAGE_SIZE = 25`, and validation for `page < 1`) and `EtlService` (wrapping `extract_all` and `transform_and_load_all` so one failing API doesn't crash the rest) inside `app/services/`, wired through `app/dependencies.py`. Then split all HTTP routes out of `app/main.py` into `app/controllers/` (`form_fields.py`, `observation_controller.py`, `etl_controller.py`, `calculator_controller.py`, `api_controller.py`) and leave `create_app()` in `app/main.py`."
- **Result:**
  - Created `app/services/observation_service.py` and `app/services/etl_service.py`.
  - Committed in `5287ccd` (*Lab 3: observation and ETL services*).
  - Added `get_session_factory()` in `app/database.py` and dependency wiring in `app/dependencies.py`.
  - Created `app/controllers/form_fields.py` (`blank_to_none`, `to_int_or_none`, `to_sex_or_none`, `to_bool_or_none`), `observation_controller.py`, `etl_controller.py`, `calculator_controller.py`, and `api_controller.py`.
  - Reduced `app/main.py` to `create_app()` assembling static assets and the four routers.
  - Controllers, templates, and dependency wiring committed in `499fe7a` (*Lab 3: controllers, templates and dependency wiring*).
- **Your changes:**
  - Kept the existing 2-digit year shorthand normalization (`normalize_query_year`) in `api_controller.py` (`/api/observations`) so existing API tests stay green, while using strict integer parsing (`to_int_or_none`) for `year_from`/`year_to` on the SSR `/observations` page.

---

## Prompt 5 – Pure SSR Jinja2 Templates (`observations.html`, `action_result.html`, `base.html`)
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-13
- **Prompt:**
  > "Update `app/templates/observations.html` and add `app/templates/action_result.html` using the existing `base.html` theme. On `/observations`, I want:
  > - Two POST buttons at the top for `Extract fresh data from sources` and `Transform & load data from local JSON/CSV files`
  > - GET filters for `country`, `indicator`, `region`, `sex`, `year_from`, `year_to`, and `is_outlier`
  > - A table with Country, Region, Indicator, Year, Sex, Value, Unit, and IQR Status
  > - Previous/Next pagination links that preserve active filters
  > Keep `/observations` and `/actions/*` completely pure HTML with zero JavaScript."
- **Result:**
  - Added `.etl-actions`, `.pagination-bar`, `.btn-disabled`, and `.status-badge` (`status-ok`, `status-skipped`, `status-failed`) styles to `app/templates/base.html`.
  - Rewrote `app/templates/observations.html` with standard GET filter form, pure HTML pagination bar using server-generated `previous_url`/`next_url`, and helpful `year_bounds` hint when zero rows match.
  - Created `app/templates/action_result.html` showing summary counts (`ok`, `skipped`, `failed`), per-step result rows, and a `Back to Observations` link.

---

## Prompt 6 – Per-Layer Test Suite, AST Architecture Rules & Verification Docs
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-13
- **Prompt:**
  > "Now write isolated pytest suites covering every layer: `tests/conftest.py` using a temporary PostgreSQL schema (`test_<random>`) plus fail-fast ETL overrides, repository integration tests, service unit tests with fakes, controller HTTP tests checking SSR filters and 422 on invalid page numbers, and `tests/test_architecture.py` enforcing import directions with `ast`. Also capture screenshots of the running app for `docs/lab3_results.md` and verify `test_architecture.py` actually fails when a forbidden import is added."
- **Result:**
  - Added `tests/conftest.py`, `tests/test_observation_repository.py`, `tests/test_observation_service.py`, `tests/test_etl_service.py`, `tests/test_observation_controller.py`, `tests/test_etl_controller.py`, and `tests/test_architecture.py`.
  - Committed test suite in `e8ba604` (*Lab 3: tests for the repository, service, controller and architecture layers*).
  - Captured live screenshots in `docs/img/` (`obs_region_africa.png`, `obs_sex_mle_rou.png`, `action_load_result.png`).
  - Documented the layer trace (`region`), `sex` filter extension, and intentional forbidden-import check (`app/services/observation_service.py` importing `fastapi`) in `docs/lab3_results.md`.
- **Your changes:**
  - Adjusted the controller test in `tests/test_observation_controller.py` to assert table rows inside `<tbody>` rather than the full HTML page, because country names still appear in the `<select name="country">` dropdown regardless of which `region` filter is active.

---

## Prompt 7 – Presentation-Layer Audit & Contradictory Filter Validation
- **Tool and model:** Gemini 4 Hydrogen
- **Date:** 2026-11-13
- **Prompt:**
  > "Double-check that the presentation layer strictly has no SQL queries or layer shortcuts anywhere (even on the `/api/*` endpoints from Lab 2), and fix the filters on `/observations` so impossible combinations like Country = Romania + Region = North America are caught cleanly without adding JavaScript."
- **Result:**
  - Moved `sync_country_realtime` behind `EtlService.sync_country()` in `app/services/etl_service.py` so `app/controllers/api_controller.py` never calls `etl.*` directly (`5287ccd`, `499fe7a`).
  - Added `test_presentation_layer_does_not_bypass_services` to `tests/test_architecture.py` (`e8ba604`) so pytest automatically blocks any controller from importing `sqlalchemy`, `app.database`, `app.repositories`, or `etl.*`.
  - Added `<optgroup>` region grouping for Country options (`Option.group`) and service-layer semantic filter validation (`ObservationService.validate_criteria()`) with SSR quick-fix links in `app/templates/observations.html` (`f9440fd`, `5287ccd`, `499fe7a`).
- **Your changes:**
  - Verified all 32 tests pass (`tests/test_api.py`, `tests/test_architecture.py`, and per-layer repository/service/controller tests) and manually checked paginated region filtering on `http://127.0.0.1:8000/observations`.

