# Vitalis · Global Health Data Platform & Life Expectancy Calculator
**Lab 1: Topic, Environment, Architecture & Database Design**

Vitalis is a global health data platform and actuarial life expectancy calculation platform. It integrates sovereign demographic data from the **World Health Organization (WHO)** Global Health Observatory, the **World Bank**, and **Our World in Data (OWID)** into a unified **PostgreSQL** star schema, exposing a **FastAPI** backend and an interactive multi-step **Longevity Calculator**.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.12+** (tested with Python 3.14)
- **PostgreSQL 16+** (running locally on port `5432` or via Docker)
- **Git**

### 2. Environment Setup
```bash
# Clone and enter directory
git clone <your-repo-url>
cd CSPGH

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Database Setup
Ensure PostgreSQL is running with the database and user configured in `.env`:
```bash
# Create database user and database (if not already created)
psql -U postgres -h localhost -c "CREATE USER gh_user WITH PASSWORD 'gh_pass';"
psql -U postgres -h localhost -c "CREATE DATABASE global_health OWNER gh_user ENCODING 'UTF8';"

# Create schema tables using SQLAlchemy
python -m app.create_tables
```

### 4. Ingest Global Health Indicators (ETL)
Run the automated pipeline to ingest sovereign countries and indicators:
```bash
python -m etl.run_import
```

### 5. Launch Application
```bash
uvicorn app.main:app --reload --port 8000
```
- **Web UI & Calculator**: [http://localhost:8000/calculator](http://localhost:8000/calculator)
- **Data Platform Explorer**: [http://localhost:8000/observations](http://localhost:8000/observations)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Run Tests
```bash
PYTHONPATH=. pytest tests/
```

---

## 📁 Project Architecture & Layout

```
CSPGH/
├── .env                  # Database connection credentials (git-ignored)
├── .env.example          # Template environment file
├── .gitignore            # Git ignore rules
├── requirements.txt      # Python dependencies
├── docker-compose.yml    # Optional Docker PostgreSQL container
├── schema_dump.sql       # PostgreSQL exported schema dump (Task 1.9)
├── README.md             # Project overview & documentation
├── REPORT_LAB1.md        # Comprehensive Lab 1 report (Tasks 1.2 – 1.9)
├── db/
│   └── schema.sql        # Reference SQL DDL schema
├── data/
│   └── raw/              # Cached JSON / CSV downloads from APIs
├── etl/
│   ├── __init__.py
│   ├── extract_who.py    # WHO GHO OData API extractor
│   ├── extract_worldbank.py # World Bank API extractor
│   ├── extract_owid.py   # Our World in Data CSV extractor
│   ├── clean.py          # pycountry mapping & data validation
│   ├── load.py           # PostgreSQL upsert & import_log audit
│   └── run_import.py     # End-to-end import pipeline runner
├── app/
│   ├── __init__.py
│   ├── database.py       # SQLAlchemy engine & session dependency
│   ├── models.py         # SQLAlchemy ORM declarative models
│   ├── create_tables.py  # DDL execution script
│   ├── main.py           # FastAPI endpoints & calculation engine
│   └── templates/
│       ├── base.html     # Dark mode glassmorphic UI layout
│       ├── calculator.html # Step-by-step longevity calculator wizard
│       └── observations.html # Data platform table explorer
├── notebooks/            # Jupyter exploratory data analysis
└── tests/
    └── test_api.py       # API & calculator validation tests
```

---

## 🧮 Life Expectancy Calculator Logic

The multi-step calculator integrates:
1. **National Baseline**: Fetches the latest sovereign life expectancy for the user's selected country and sex from the `observation` table (WHO `WHOSIS_000001` / World Bank `SP.DYN.LE00.IN`).
2. **Habit Impact Offsets**:
   - **Smoking Habit**: Non-smoker (`0.0y`), Former smoker (`-1.5y`), Light (`-4.5y`), Moderate (`-7.0y`), Heavy (`-10.0y`). (*Doll et al. BMJ 2004*)
   - **Alcohol Consumption**: Rare/None (`0.0y`), Moderate (`-0.5y`), Heavy (`-2.0y`), Excessive (`-5.0y`). (*Wood et al. Lancet 2018*)
   - **Physical Activity**: Sedentary (`-2.5y`), Light (`0.0y`), Active 150m/wk (`+3.8y`), High/Athlete (`+4.5y`). (*Moore et al. PLOS Med 2012*)
   - **BMI Classification**: Underweight (`-2.0y`), Normal (`0.0y`), Overweight (`-1.2y`), Obese (`-4.0y`). (*Lancet 2009*)
3. **Longevity Forecast**: Computes personalized predicted lifespan, remaining years of life, net habit impact, and actionable recommendations.
