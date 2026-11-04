# Lab 2: AI Assistance Prompt Log

**Course:** CSP in Global Health / Advanced Global Health Analytics  
**Student:** Tudor Stanichevici  
**Assistant & Model:** Gemini 3.8 Flash  
**Date:** 2026-11-04  

This document logs the step-by-step prompts sent to Gemini 3.8 Flash to complete each requirement of Lab 2 (data extraction, transformation, exploratory analysis, cleaning with IQR outlier detection, idempotent database loading, data quality checks, and UI integration).

---

## Prompt 1 – Raw Data Extractors (WHO, World Bank, OWID)
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "Hi! I am working on Lab 2 for my master's course in Global Health. I have to download raw data from three APIs/sources and save the raw files on disk:
  > 1. WHO Global Health Observatory (it uses an OData API with pagination like `@odata.nextLink` and `$filter`)
  > 2. World Bank Indicators API (it returns pages with `page` and `pages` in JSON)
  > 3. Our World in Data (downloading a CSV from their grapher URL)
  > 
  > Can you help me write Python extractors in `etl/` that download the data, save the raw json/csv into `data/raw/<source>/`, and also save a `.source.json` sidecar file with the download URL and timestamp so I can track where the file came from?"
- **Result:**
  - `etl/raw_files.py`: Helper functions to write raw payloads and metadata sidecars.
  - `etl/json_types.py`: Type helpers for JSON dictionaries.
  - `etl/extract_who.py`, `etl/extract_worldbank.py`, `etl/extract_owid.py`: Download scripts for each source.
  - Included in commit: `df37ba8` (*Lab 2: raw data extractors (WHO, World Bank, OWID)*).
- **Your changes:**
  - Gemini didn't handle network timeouts or custom User-Agent headers, which caused the OWID download to be blocked by Cloudflare (403 error). I added a realistic `User-Agent` header (`Mozilla/5.0...`).
  - For WHO GHO, the live Azure Edge endpoint was occasionally returning 503 errors during testing. I added an offline fallback check so that if the network fails or returns 503, it can safely use a previously saved local raw file.
  - Configured relative paths using `pathlib.Path` rooted at the project directory instead of hardcoded local paths.

---

## Prompt 2 – Transforming Raw Files to Normalized Data (Task 2.1)
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "Now that the raw files are downloaded, I need to write transformers in `etl/transform_*.py` for each source. The lab says each transformer should take a saved raw file and turn it into a pandas DataFrame with exactly these 5 columns: `country_iso3`, `indicator_code`, `year`, `sex`, `value`.
  > - For WHO: the country is in `SpatialDim`, sex is in `Dim1` (when `Dim1Type == 'SEX'`, otherwise 'BTSX'), and value is in `NumericValue`.
  > - For World Bank: country is in `countryiso3code`, year is in `date`, value is in `value`. We also need to filter out regional aggregate codes like WLD, EUU, etc.
  > - For OWID: read the CSV, map `Code` to `country_iso3`, `Year` to `year`, and rename the metric column to `value`.
  > Can you show me how to structure these three transform functions cleanly?"
- **Result:**
  - `etl/transform_who.py`: Extracts ISO3 codes, parses sex dimensions (`BTSX`, `MLE`, `FMLE`), and maps numeric values.
  - `etl/transform_worldbank.py`: Filters out non-sovereign regional entities and parses annual numeric values.
  - `etl/transform_owid.py`: Normalizes OWID CSV time series to the standard 5-column schema.
  - Included in commit: `cf26246` (*Lab 2: raw-to-DB transform modules*).
- **Your changes:**
  - Gemini forgot that World Bank country downloads have regional groups (like 'High income', 'World', 'Sub-Saharan Africa') which don't have sovereign ISO3 codes or have aggregate flags. I added a filter checking `region.value != 'Aggregates'` and `len(iso3) == 3`.
  - For WHO, some records had disaggregations other than sex (like age groups or urban/rural). I added a condition `(row.get('Dim1Type') == 'SEX' or not row.get('Dim1Type'))` so rows don't get duplicated or mislabeled.

---

## Prompt 3 – Task 2.1: Jupyter Notebook Exploration of Missing Values
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "For Task 2.1 of my lab, I have to create a Jupyter notebook in `notebooks/lab2_exploration.ipynb`. In this notebook I need to:
  > 1. Call each extractor and transformer to load the data into DataFrames.
  > 2. Run `df.head()`, `df.info()`, and `df.isna().sum()` on each dataset to inspect the structure.
  > 3. Calculate the percentage of missing values for each indicator and print a summary table.
  > 4. Add a short explanation at the end about why some sources (like World Bank) have lots of nulls while others (like WHO) have 0% nulls in the downloaded rows.
  > Can you give me the Python code cells to put in this notebook?"
- **Result:**
  - `notebooks/lab2_exploration.ipynb`: Jupyter notebook executing the extraction, transformation, inspections, and missing rate calculations across all indicators.
  - Included in commit: `cf26246` (*Lab 2: raw-to-DB transform modules*).
- **Your changes:**
  - Added code at the top of the notebook to dynamically resolve `ROOT = Path.cwd().parent` and append it to `sys.path`, so the notebook runs properly whether started from inside `notebooks/` or from the repository root.
  - Added markdown observations explaining the data collection differences: World Bank returns a pre-indexed Cartesian product (years x countries) with `null` when no survey was done, whereas WHO GHO only returns rows when a measurement actually exists.

---

## Prompt 4 – Task 2.2: IQR Outlier Detection & Alembic Migration
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "For Task 2.2, I need to add an Interquartile Range (IQR) outlier detection rule in `etl/clean.py`.
  > The lab requirement says:
  > For each indicator:
  > - calculate Q1 (25th percentile) and Q3 (75th percentile)
  > - IQR = Q3 - Q1
  > - values below Q1 - 1.5 * IQR or above Q3 + 1.5 * IQR should be flagged
  > - BUT we must NOT delete or drop these rows! We need to flag them in a new boolean column called `is_outlier`.
  > Also, I need to add this column to my PostgreSQL `Observation` model using an Alembic migration.
  > Can you help me write the pandas calculation for IQR per indicator and the Alembic migration command?"
- **Result:**
  - `etl/clean.py`: Implemented Tukey's fences calculation grouped by indicator; assigns `is_outlier = True/False`.
  - `app/models.py`: Added `is_outlier: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)` to `Observation`.
  - `alembic/versions/d1874b9ea9d1_add_is_outlier_to_observation.py`: Migration script adding `is_outlier` to the `observation` table.
  - Included in commit: `44ac0f6` (*Lab 2: observation cleaning module with IQR outlier flag*).
- **Your changes:**
  - Gemini initially suggested using `df[~df['is_outlier']]` to drop the outliers from the dataframe. I corrected this because the lab explicitly requires: *"flag the rows instead of dropping them"*.
  - Handled indicators with zero variance or small sample size using `.fillna(False)` to prevent NaN boolean values in the database.
  - Generated and verified the Alembic migration against the local PostgreSQL database using `alembic upgrade head`.

---

## Prompt 5 – Task 2.3: Database Upsert Loader and Import Log
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "For Task 2.3, I need to write `etl/load.py` to store cleaned observations in PostgreSQL.
  > The teacher says the import MUST be idempotent, meaning if I run the script twice, it should update existing rows instead of crashing or creating duplicates.
  > The lab specifies using PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE` on the natural key `(country_iso3, indicator_id, year, sex)`.
  > Also, every time an import runs, it must write a record to `import_log` with the source name, indicator code, number of rows loaded, and the raw URL.
  > How do I write `upsert_observations` and `log_import` using SQLAlchemy core `insert()` with `on_conflict_do_update`?"
- **Result:**
  - `etl/load.py`: Upsert loader using PostgreSQL dialect insert, chunked execution (`chunk_size=5000`), and `log_import` helper.
  - `etl/import_worldbank.py`, `etl/import_who.py`, `etl/import_owid.py`: Standalone CLI runners for each source.
  - Included in commit: `afd0c3f` (*Lab 2: observation loader and per-source import scripts*).
- **Your changes:**
  - Gemini wrote an insert statement without chunking, which failed on large datasets (exceeding PostgreSQL parameter limits). I wrapped the upsert in a chunking loop (`chunk_size=5000`).
  - Added resolution for `indicator_id` foreign keys by querying the `indicator` dimension table before inserting observations.
  - Read the URL and timestamp directly from the `.source.json` sidecar files created in Step 1 to populate `import_log` with verified provenance metadata.

---

## Prompt 6 – Task 2.4: SQL Data Quality Verification & Source Comparison
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "For Task 2.4, I have to run the 7 SQL verification queries from Section 2.5 of the lab sheet in PostgreSQL and write up the results in `docs/lab2_results.md`.
  > The queries check:
  > 1. Countries without region aggregates
  > 2. Duplicate natural keys
  > 3. Values outside plausible ranges
  > 4. Invalid sex values
  > 5. Years outside the 2000-2024 window
  > 6. Comparison between `rows_loaded` in `import_log` and actual count in `observation`
  > 7. Sovereign entities without WHO life expectancy data
  > 
  > Also, I need to pick one country (I want to pick Romania - ROU) in year 2019, compare 3 indicators (one from WHO, one from World Bank, one from OWID) between my PostgreSQL database and the official websites, and explain if they match.
  > Can you help me format this report cleanly in markdown?"
- **Result:**
  - `docs/lab2_results.md`: Complete documentation containing outlier counts per indicator, idempotence verification, the 7 SQL queries with outputs and domain explanations, and the ground-truth table for Romania (2019).
  - Included in commit: `eab21dc` (*Lab 2: data quality checks and results*).
- **Your changes:**
  - Ran each query directly in `psql` against the `global_health` database to obtain the real outputs rather than estimated numbers.
  - In Check 6 (import log vs stored rows), there was a discrepancy for indicator `SA_0000001400` because the older Lab 1 import had loaded historical rows prior to 2000. I explained this clearly in the report notes: the upsert updates in place but does not delete previously existing rows.
  - Looked up Romania's 2019 figures on World Bank Open Data (`5.699%`), WHO GHO (`75.5` years), and OWID (`75.3` years) and confirmed the exact decimal-level matches.

---

## Prompt 7 – UI Refactor & Integration
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "I want to polish the web UI for the application so it looks clean, simple, and functional like a real health tool.
  > - In `app/templates/observations.html`: show the `is_outlier` status in the table so users can see which values were flagged by our IQR algorithm.
  > - In `app/templates/calculator.html`: keep the 3D globe and interactive sliders, but make the design clean, with no exaggerated neon colors or weird gradients, supporting light and dark mode.
  > - Update `README.md` with complete instructions on how to install requirements, run migrations, run the extractors and imports, and run pytest.
  > How can I update `app/main.py` and the templates to pass `is_outlier` and make the UI clean?"
- **Result:**
  - `app/templates/base.html`, `app/templates/calculator.html`, `app/templates/observations.html`: Refactored with clean typography, segmented controls, natural earth-toned globe, and outlier badges.
  - `app/main.py`: Updated observation queries to include the `is_outlier` flag.
  - `README.md`: Documented end-to-end setup and verification steps.
  - Included in commit: `c3646d5` (*Lab 2: refactor UI*).
- **Your changes:**
  - Added an outlier filter pill in the observations table so users can filter exclusively for flagged rows.
  - Ran `pytest tests/` to confirm that the changes did not break any of the 6 automated API tests.


---

## Prompt 8 – Longevity Prediction Engine & Warehouse Query API
- **Tool and model:** Gemini 3.8 Flash
- **Date:** 2026-11-04
- **Prompt:**
  > "I need to finalize Lab 2 and connect the database warehouse to our frontend and API:
  > 1. In `app/main.py`, make query parameter parsing robust for `year`, `country_iso3`, `indicator_code`, and `is_outlier`. Also handle two-digit year inputs (e.g. 24 -> 2024).
  > 2. On `/observations`, when a filter returns 0 observations, provide helpful guidance on available surveillance years (2000–2024) and quick links.
  > 3. In `app/ml_model.py`, build the personalized longevity model: healthy baseline, chronic & genetic condition hazard ratios with multimorbidity attenuation, and lifestyle modifications (diet, exercise, smoking, sleep).
  > 4. In `app/templates/calculator.html`, display the interactive 3D globe with country life expectancy hover, medical condition search, and a 'Life in Weeks' matrix.
  > Can you help me tie this together cleanly?"
- **Result:**
  - `app/main.py`: Added safe query parameter parsing, two-digit year normalization, and country/indicator available year hints.
  - `app/ml_model.py`: Implemented longevity estimation algorithm with clinical hazard curves, multimorbidity attenuation, and life horizon units (months, weeks, days).
  - `app/templates/calculator.html`: 3D globe with offline Three.js / Globe.gl texture, auto-pause on hover, medical condition search, and 'Life in Weeks' matrix.
  - `app/templates/observations.html`: Outlier filtering, informative empty state, and one-click quick filters.
  - `tests/test_api.py`: Automated tests covering API endpoints, year parsing, and prediction engine (8/8 passed).
  - Included in commit: `Lab 2: longevity prediction engine and warehouse query API`.
- **Your changes:**
  - Bundled `three.min.js`, `globe.gl.min.js`, `world-110m.json`, and `earth-blue-marble.jpg` locally in `app/static/` so the application runs completely offline.
  - Added intelligent 2-digit year normalization (`24` -> `2024`) and informative empty-state messages explaining WHO 1–2 year surveillance lags.
  - Added genetic conditions (Cystic Fibrosis, Sickle Cell, Familial Hypercholesterolemia) and instant search filtering.
  - Verified with `pytest tests/` (all 8 tests passing).
