-- Database Schema for Global Health Data Platform
-- Topic: Life Expectancy and Behavioral Risk Factors (Smoking, Alcohol, BMI, Health Spending)

CREATE TABLE IF NOT EXISTS source (
    source_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    url TEXT
);

CREATE TABLE IF NOT EXISTS country (
    iso3 VARCHAR(3) PRIMARY KEY,
    iso2 VARCHAR(2),
    name VARCHAR(100) NOT NULL,
    region VARCHAR(100),
    income_group VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS indicator (
    indicator_id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50),
    source_id INTEGER NOT NULL REFERENCES source(source_id)
);

CREATE TABLE IF NOT EXISTS observation (
    observation_id BIGSERIAL PRIMARY KEY,
    country_iso3 VARCHAR(3) NOT NULL REFERENCES country(iso3),
    indicator_id INTEGER NOT NULL REFERENCES indicator(indicator_id),
    year SMALLINT NOT NULL,
    sex VARCHAR(10) NOT NULL DEFAULT 'BTSX',
    age_group VARCHAR(20) NOT NULL DEFAULT 'ALL',
    value NUMERIC(18, 4),
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_observation UNIQUE (country_iso3, indicator_id, year, sex, age_group)
);

CREATE INDEX IF NOT EXISTS ix_observation_indicator_year ON observation (indicator_id, year);
CREATE INDEX IF NOT EXISTS ix_observation_country ON observation (country_iso3);

CREATE TABLE IF NOT EXISTS import_log (
    import_id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    indicator_code VARCHAR(50) NOT NULL,
    url TEXT NOT NULL,
    rows_loaded INTEGER NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
