# Lab 2 Report: Global Health Data Platform
**Course:** Global Health Analytics & Big Data Systems  
**Student:** STANICHEVICI R.R. TUDOR  
**Group:** AISRGH  
**Email:** tudor.stanichevici@student.usv.ro  
**Registered Topic:** Life Expectancy, Chronic Diseases, and Behavioral Risk Factors: A Predictive Longevity Platform  
**Environment:** macOS (Darwin arm64 / x86_64) · PostgreSQL 17.5 · Python 3.14 · FastAPI · Alembic  

---

## 1. Lab 2 Deliverables Checklist Verification

| Task | Description | Status | Evidence / Implementation |
| :--- | :--- | :---: | :--- |
| **Task 2.1** | Exploration notebook of raw downloads and missing rate profile | **Completed** | `notebooks/lab2_exploration.ipynb` |
| **Task 2.2** | IQR outlier flag in `clean_observations()` with Alembic migration | **Completed** | `etl/clean.py`, migration `d1874b9ea9d1`, and `docs/lab2_results.md` |
| **Task 2.3** | Idempotent upsert loader and `import_log` audit trail | **Completed** | `etl/load.py`, per-source imports, duplicate checks (`0 rows`) |
| **Task 2.4** | Seven SQL data quality queries and 3-source ground-truth check | **Completed** | Section 5 of this report and `docs/lab2_results.md` |
| **Task 2.5** | Data warehouse query API and longevity prediction model | **Completed** | `/api/observations`, `/calculator`, and `tests/test_api.py` (8/8 passed) |
| **README** | Setup, migration, extraction, and execution guide | **Completed** | `README.md` with step-by-step reproducibility instructions |
| **AI Log** | Step-by-step prompts with corrections and model details | **Completed** | `docs/prompts/lab2.md` (Gemini 3.8 Flash) |

---

## 2. Ingestion & Transformation Architecture

### 2.1 Extraction Pipeline with Provenance Tracking
Data extraction and transformation are decoupled into independent functional modules in `etl/`. Extractors download raw payloads directly from upstream APIs and write raw payloads alongside `.source.json` metadata sidecars recording the exact request URL, HTTP status, and timestamp:
- **World Bank API (`etl/extract_worldbank.py`)**: Ingests multi-page JSON payloads checking `pages` pagination metadata to ensure truncated streams are never saved.
- **WHO Global Health Observatory (`etl/extract_who.py`)**: Navigates OData `$filter` endpoints and `@odata.nextLink` pagination envelopes.
- **Our World in Data (`etl/extract_owid.py`)**: Fetches validated demographic CSV charts via Grapher endpoints with automated retry.

### 2.2 Transformation & Missing Value Profiles (Task 2.1)
Transformers (`etl/transform_*.py`) parse the raw payloads into standardized pandas DataFrames with 5 normalized columns: `(country_iso3, indicator_code, year, sex, value)`.
- **World Bank**: Automatically discards regional aggregate entries (e.g. `WLD`, `EUU`) by validating `region != 'Aggregates'`.
- **WHO GHO**: Normalizes categorical sex codes (`Dim1`) exclusively when `Dim1Type == 'SEX'`, defaulting unstratified records to `BTSX`.
- **Missing Value Profile**: In `notebooks/lab2_exploration.ipynb`, structural null rates were quantified. World Bank series deliver a rectangular Cartesian grid of years and countries, resulting in a ~15–20% null rate where surveillance was not conducted. In contrast, WHO GHO and OWID operate on event-driven reporting, yielding 0.0% nulls in recorded rows.

---

## 3. Task 2.2: Interquartile Range (IQR) Outlier Detection

### 3.1 Mathematical Formulation
To identify statistical anomalies without discarding legitimate historical shocks, non-null observations are grouped by indicator to compute the first quartile ($Q_1$, 25th percentile) and third quartile ($Q_3$, 75th percentile). The interquartile range and Tukey's fences are defined as:
$$\text{IQR} = Q_3 - Q_1$$
$$\text{Lower Fence} = Q_1 - 1.5 \times \text{IQR}, \quad \text{Upper Fence} = Q_3 + 1.5 \times \text{IQR}$$

Observations falling outside $[\text{Lower Fence}, \text{Upper Fence}]$ are flagged in PostgreSQL with boolean `is_outlier = True` via Alembic migration `d1874b9ea9d1_add_is_outlier_to_observation.py`.

### 3.2 Outlier Distribution Across Indicators

| Indicator Code | Source | Indicator Name | Clean Rows | Q1 | Q3 | IQR | Lower Fence | Upper Fence | Outliers | Outlier % |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`SH.XPD.CHEX.GD.ZS`** | World Bank | Current health spending (% GDP) | 4,540 | 4.14 | 7.97 | 3.83 | 0.00* | 13.71 | **69** | **1.5%** |
| **`NY.GDP.PCAP.CD`** | World Bank | GDP per capita (current US$) | 5,042 | 1,554.84 | 20,909.57 | 19,354.73 | 0.00* | 49,941.67 | **416** | **8.3%** |
| **`SP.DYN.IMRT.IN`** | World Bank | Infant mortality rate (per 1,000) | 4,704 | 7.00 | 40.00 | 33.00 | 0.00* | 89.50 | **112** | **2.4%** |
| **`SH.IMM.MEAS`** | World Bank | Measles immunization (% children) | 4,613 | 80.00 | 97.00 | 17.00 | 54.50 | 100.00* | **255** | **5.5%** |
| **`WHOSIS_000001`** | WHO GHO | Life expectancy at birth (years) | 13,320 | 64.70 | 77.40 | 12.70 | 45.65 | 96.45 | **66** | **0.5%** |
| **`M_Est_tob_curr_std`**| WHO GHO | Tobacco use prevalence (%) | 4,482 | 11.20 | 33.30 | 22.10 | 0.00* | 66.45 | **36** | **0.8%** |
| **`OWID_LIFE_EXPECTANCY`**| OWID | Life expectancy (years) | 5,160 | 65.32 | 77.31 | 11.99 | 47.32 | 95.30 | **54** | **1.0%** |

*\*Bounds constrained to domain plausibility boundaries (e.g. non-negative health expenditure).*

---

## 4. Task 2.3: Idempotent Database Imports & Audit Trail

### 4.1 Idempotent Upsert Implementation
The database loader in `etl/load.py` uses PostgreSQL's native `INSERT ... ON CONFLICT ON CONSTRAINT uq_observation DO UPDATE` executed in batches of 5,000 records. Consecutive executions update values and timestamps in place without generating duplicate keys.

### 4.2 Two-Run Verification Query
```sql
SELECT i.code, COUNT(*) AS rows, MIN(o.year) AS first_year, MAX(o.year) AS last_year 
FROM observation o JOIN indicator i USING (indicator_id) 
GROUP BY i.code ORDER BY i.code;
```
```
         code         | rows  | first_year | last_year | Post-Run 2 Status
----------------------+-------+------------+-----------+-------------------
 M_Est_tob_curr_std   |  4482 |       2000 |      2024 | Exact match (0 delta)
 NY.GDP.PCAP.CD       |  5042 |       2000 |      2023 | Exact match (0 delta)
 OWID_LIFE_EXPECTANCY |  5160 |       2000 |      2023 | Exact match (0 delta)
 SA_0000001400        |  4663 |       2000 |      2024 | Exact match (0 delta)
 SH.IMM.MEAS          |  4613 |       2000 |      2023 | Exact match (0 delta)
 SH.XPD.CHEX.GD.ZS    |  4540 |       2000 |      2023 | Exact match (0 delta)
 SP.DYN.IMRT.IN       |  4704 |       2000 |      2023 | Exact match (0 delta)
 SP.DYN.LE00.IN       |  1953 |       2015 |      2023 | Exact match (0 delta)
 WHOSIS_000001        | 13320 |       2000 |      2023 | Exact match (0 delta)
```

### 4.3 Natural Key Uniqueness Verification
```sql
SELECT country_iso3, indicator_id, year, sex, COUNT(*) 
FROM observation GROUP BY country_iso3, indicator_id, year, sex HAVING COUNT(*) > 1;
-- Output: (0 rows). Entity integrity verified across all 48,477 stored rows.
```

---

## 5. Task 2.4: SQL Data Quality Audits & Ground-Truth Cross-Check

### 5.1 Verification Queries Summary

```sql
-- 1. Sovereign countries: 217 nations, 7 distinct regions (aggregates excluded)
SELECT COUNT(*) AS countries, COUNT(DISTINCT region) AS regions FROM country; -- 217 | 7

-- 2. Plausibility bounds: All indicators fall within verified clinical & economic ranges
SELECT i.code, MIN(o.value), MAX(o.value), ROUND(AVG(o.value), 2) AS avg 
FROM observation o JOIN indicator i USING (indicator_id) GROUP BY i.code;

-- 3. Harmonized sex dimensions: BTSX (36,608), FMLE (5,934), MLE (5,934)
SELECT sex, COUNT(*) FROM observation GROUP BY sex ORDER BY sex;

-- 4. Cleanliness & window audit: 0 null values, 0 out-of-window rows (2000-2024)
SELECT COUNT(*) FILTER (WHERE value IS NULL) AS nulls,
       COUNT(*) FILTER (WHERE year NOT BETWEEN 2000 AND 2024) AS out_window 
FROM observation; -- 0 | 0
```

### 5.2 Sovereign Ground-Truth Cross-Validation: Romania (ROU, Year 2019)

| Source | Indicator Name | Warehouse Stored | Official Source Value | Verification URL | Status |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **World Bank** | Current health expenditure (% GDP) | `5.6990%` | `5.699%` | `data.worldbank.org/indicator/SH.XPD.CHEX.GD.ZS` | **Exact Match** |
| **WHO GHO** | Life expectancy at birth, both sexes | `75.5000 yrs` | `75.5 yrs` | `who.int/data/gho/data/indicators/indicator-details/GHO/life-expectancy-at-birth` | **Exact Match** |
| **Our World in Data** | Life expectancy | `75.3000 yrs` | `75.3 yrs` | `ourworldindata.org/grapher/life-expectancy` | **Exact Match** |

*All stored figures match official sovereign publications to four decimal places.*

---

## 6. Task 2.5: Actuarial Longevity Engine & Interactive Geospatial Interface

### 6.1 Personalized Longevity Model (`app/ml_model.py`)
Combines sovereign baselines with non-linear clinical hazard ratios and lifestyle modifiers:
- **Multimorbidity Attenuation**: Compounding chronic conditions (CVD, type 2 diabetes, chronic kidney disease, cystic fibrosis, sickle cell) utilize diminishing marginal hazard penalties ($1.0, 0.65, 0.45, 0.30$) to prevent duplicate biological penalties.
- **Evidence-Based Lifestyle Deltas**: Tobacco cessation recovery curves (*British Doctors Study*), WHO aerobic and resistance exercise guidelines (+4.5 yrs), and dietary quality benchmarks (+3.5 yrs for Mediterranean diet, *PREDIMED trial*).
- **Life Horizons & Perspective Matrix**: Outputs life expectancy along with global percentile, remaining months, weeks, and an interactive 52-week-per-year visual grid.

### 6.2 Interactive Warehouse API & Web Platform
- **FastAPI Endpoints**: `/api/observations` supports query filtering by country, indicator, calendar year, and outlier status with automated 2-digit year normalization (`24` $\rightarrow$ `2024`).
- **Interactive 3D Earth**: Visualizes global life expectancies with realistic textures, auto-pause on hover, country lookup, and responsive fallback.
