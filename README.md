# Global Health Data Platform & Life Expectancy Calculator
**Lab 1 & Lab 2: Topic, Architecture, Ingestion, Cleaning, Storage & Outlier Detection**

A modular global health data platform and actuarial life expectancy calculation system. It ingests sovereign demographic data from the **World Health Organization (WHO)** Global Health Observatory, the **World Bank**, and **Our World in Data (OWID)** into a unified **PostgreSQL** star schema, applying statistical data cleaning, Tukey IQR outlier flagging, and idempotent upserts, exposing a **FastAPI** backend and an interactive multi-step **Life Expectancy Calculator**.

---

## 🚀 Quick Start Guide (From Scratch)

### 1. Prerequisites
- **Python 3.12+** (tested with Python 3.14)
- **PostgreSQL 16+** (running locally on port `5432` or via Docker)
- **Git**

### 2. Environment Setup
```bash
# Clone repository and enter directory
git clone <your-repo-url>
cd CSPGH

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies (FastAPI, SQLAlchemy, Alembic, Pandas, Requests, etc.)
pip install -r requirements.txt
```

### 3. Database & Migration Setup
Create the PostgreSQL database and user if not already present:
```bash
# Initialize PostgreSQL user and database
psql -U postgres -h localhost -c "CREATE USER gh_user WITH PASSWORD 'gh_pass';"
psql -U postgres -h localhost -c "CREATE DATABASE global_health OWNER gh_user ENCODING 'UTF8';"

# Create base tables and run Alembic migrations
python -m app.create_tables
alembic upgrade head
```

### 4. Step-by-Step Data Pipeline (Extraction & Ingestion)

#### Step 4.1: Download Raw Datasets (Extract)
Run extraction from a Python shell or script. Raw downloads land in `data/raw/<source>/` accompanied by provenance metadata sidecars (`<filename>.source.json`):
```python
from etl.extract_worldbank import download_worldbank_countries, download_worldbank_indicator
from etl.extract_who import download_who_indicator
from etl.extract_owid import download_owid_chart

# 1. World Bank sovereign countries and indicators (2000-2023)
download_worldbank_countries()
for code in ["SH.XPD.CHEX.GD.ZS", "NY.GDP.PCAP.CD", "SP.DYN.IMRT.IN", "SH.IMM.MEAS"]:
    download_worldbank_indicator(code, "2000:2023")

# 2. WHO Global Health Observatory indicators (2000-present)
download_who_indicator("WHOSIS_000001", 2000)
download_who_indicator("M_Est_tob_curr_std", 2000)

# 3. Our World in Data curated charts
download_owid_chart("life-expectancy")
```

#### Step 4.2: Run Idempotent Ingestion Scripts (Transform, Clean & Load)
Execute the modular import scripts. Always run World Bank first to populate the country dimension table:
```bash
# 1. World Bank (populates sovereign country table + WB indicators)
python -m etl.import_worldbank

# 2. WHO GHO (life expectancy & tobacco prevalence)
python -m etl.import_who

# 3. Our World in Data (historical life expectancy series)
python -m etl.import_owid
```
*Note: All import scripts use `INSERT ... ON CONFLICT (uq_observation) DO UPDATE`, making subsequent runs fully idempotent without creating duplicate rows.*

---

## 🔍 Data Quality Verification & SQL Checks

Connect to PostgreSQL with `psql` to execute the Lab 2 quality checks:
```bash
PGPASSWORD=gh_pass psql -U gh_user -h localhost -d global_health
```

```sql
-- 1. Sovereign Countries (Expected: 217 countries, 7 regions)
SELECT COUNT(*) AS countries, COUNT(DISTINCT region) AS regions FROM country;

-- 2. Duplicates on Natural Key (Expected: 0 rows)
SELECT country_iso3, indicator_id, year, sex, COUNT(*) 
FROM observation 
GROUP BY country_iso3, indicator_id, year, sex 
HAVING COUNT(*) > 1;

-- 3. Plausible Bounds & Outlier Summary
SELECT i.code, i.unit, MIN(o.value), MAX(o.value), ROUND(AVG(o.value), 2) AS avg 
FROM observation o JOIN indicator i USING (indicator_id) 
GROUP BY i.code, i.unit ORDER BY i.code;

-- 4. Harmonized Sex Codes (Expected: BTSX, FMLE, MLE)
SELECT sex, COUNT(*) FROM observation GROUP BY sex ORDER BY sex;

-- 5. Missing Values & Window Check (Expected: 0 nulls, 0 out-of-window)
SELECT COUNT(*) FILTER (WHERE value IS NULL) AS null_values, 
       COUNT(*) FILTER (WHERE year NOT BETWEEN 2000 AND 2024) AS out_of_window 
FROM observation;

-- 6. Import Log vs Warehouse Reconciliation
SELECT l.indicator_code, l.rows_loaded, 
       (SELECT COUNT(*) FROM observation o JOIN indicator i USING (indicator_id) 
        WHERE i.code = l.indicator_code) AS rows_stored 
FROM import_log l 
WHERE l.imported_at = (SELECT MAX(imported_at) FROM import_log x 
                       WHERE x.indicator_code = l.indicator_code);

-- 7. WHO Life Expectancy Sovereign Coverage Gaps
SELECT c.iso3, c.name FROM country c 
WHERE NOT EXISTS ( 
    SELECT 1 FROM observation o JOIN indicator i USING (indicator_id) 
    WHERE o.country_iso3 = c.iso3 AND i.code = 'WHOSIS_000001') 
ORDER BY c.name;
```

---

## 📊 Exploratory Notebook

An interactive Jupyter notebook exploring raw files, missing value distributions, and provider structures is located at:
```bash
jupyter notebook notebooks/lab2_exploration.ipynb
```

---

## 💻 Running the Web Application & Tests

### Start Server
```bash
uvicorn app.main:app --reload --port 8000
```
- **3D Globe & Life Expectancy Calculator:** [http://localhost:8000/calculator](http://localhost:8000/calculator)
- **Observations Warehouse Explorer:** [http://localhost:8000/observations](http://localhost:8000/observations)
- **REST API OpenAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### Run Automated Tests
```bash
PYTHONPATH=. pytest tests/
```

---

## 📁 Repository Directory Structure

```
CSPGH/
├── .env                  # Database credentials (git-ignored)
├── .env.example          # Sample environment variables
├── .gitignore            # Git exclusions (.env, data/raw/)
├── requirements.txt      # Project dependencies
├── docker-compose.yml    # PostgreSQL Docker service
├── README.md             # Project & setup guide
├── REPORT_LAB1.md        # Lab 1 formal report
├── alembic.ini           # Alembic database migration config
├── alembic/
│   ├── env.py            # Migration runtime environment
│   └── versions/         # Schema migration history
│       └── d1874b9ea9d1_add_is_outlier_to_observation.py
├── docs/
│   ├── lab2_results.md   # Lab 2 results, IQR outlier statistics & SQL checks
│   └── prompts/
│       └── lab2.md       # AI prompt traceability log
├── notebooks/
│   └── lab2_exploration.ipynb # Task 2.1 data exploration notebook
├── data/
│   └── raw/              # Landing zone (who/, worldbank/, owid/) (git-ignored)
├── etl/
│   ├── raw_files.py      # Raw bytes persistence & provenance sidecars
│   ├── json_types.py     # JSON aliases & key validation
│   ├── extract_who.py    # WHO GHO OData extractor
│   ├── extract_worldbank.py # World Bank API extractor
│   ├── extract_owid.py   # Our World in Data CSV extractor
│   ├── transform_who.py  # WHO record normalizer
│   ├── transform_worldbank.py # World Bank record normalizer
│   ├── transform_owid.py # OWID chart normalizer
│   ├── clean.py          # Validation, plausibility & IQR outlier detection
│   ├── load.py           # Idempotent upsert & import_log
│   ├── import_worldbank.py # World Bank import CLI
│   ├── import_who.py     # WHO GHO import CLI
│   ├── import_owid.py    # OWID import CLI
│   └── realtime_pipeline.py # Live single-country synchronization
├── app/
│   ├── database.py       # Engine & session management
│   ├── models.py         # SQLAlchemy models (Country, Indicator, Observation, ImportLog)
│   ├── main.py           # FastAPI web application routes
│   ├── ml_model.py       # Actuarial longevity hazard model
│   └── templates/        # Jinja2 HTML templates
└── tests/
    └── test_api.py       # Pytest suite
```
