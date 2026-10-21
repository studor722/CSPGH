import sys
import logging
from app.database import engine, SessionLocal
from app.models import Base, Country
from etl.extract_worldbank import extract_worldbank_countries, extract_worldbank_indicator
from etl.extract_who import extract_who_indicator
from etl.extract_owid import extract_owid_dataset
from etl.clean import clean_observations
from etl.load import load_sources, load_countries, get_or_create_indicator, load_observations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ETL")


def run_pipeline(quick_mode: bool = False):
    """
    Execute end-to-end ETL pipeline:
    1. Ensure database schema exists
    2. Seed data sources
    3. Seed country dimensions
    4. Fetch, clean, and load core global health indicators
    """
    logger.info("Initializing database schema...")
    Base.metadata.create_all(engine)

    logger.info("Step 1: Loading data sources...")
    source_map = load_sources()
    logger.info(f"Sources initialized: {source_map}")

    logger.info("Step 2: Extracting and loading countries from World Bank...")
    df_countries = extract_worldbank_countries()
    num_countries = load_countries(df_countries)
    logger.info(f"Loaded {num_countries} countries.")

    with SessionLocal() as db:
        valid_iso3 = {c.iso3 for c in db.query(Country.iso3).all()}

    indicators_to_load = [
        # (Source, Code, Name, Unit, ExtractorFunc, ExtractorArgs)
        (
            "WHO GHO",
            "WHOSIS_000001",
            "Life expectancy at birth (years)",
            "years",
            extract_who_indicator,
            ("WHOSIS_000001",),
            "https://ghoapi.azureedge.net/api/WHOSIS_000001"
        ),
        (
            "World Bank",
            "SP.DYN.LE00.IN",
            "Life expectancy at birth, total (World Bank)",
            "years",
            extract_worldbank_indicator,
            ("SP.DYN.LE00.IN", "2015:2023"),
            "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.LE00.IN"
        ),
        (
            "WHO GHO",
            "M_Est_tob_curr_std",
            "Age-standardized tobacco use prevalence (15+ years)",
            "%",
            extract_who_indicator,
            ("M_Est_tob_curr_std",),
            "https://ghoapi.azureedge.net/api/M_Est_tob_curr_std"
        ),
        (
            "World Bank",
            "SH.PRV.SMOK",
            "Prevalence of current tobacco use (% of adults)",
            "%",
            extract_worldbank_indicator,
            ("SH.PRV.SMOK", "2015:2023"),
            "https://api.worldbank.org/v2/country/all/indicator/SH.PRV.SMOK"
        ),
        (
            "WHO GHO",
            "SA_0000001400",
            "Alcohol per capita (15+) consumption",
            "litres pure alcohol",
            extract_who_indicator,
            ("SA_0000001400",),
            "https://ghoapi.azureedge.net/api/SA_0000001400"
        ),
        (
            "World Bank",
            "SH.XPD.CHEX.GD.ZS",
            "Current health expenditure (% of GDP)",
            "% of GDP",
            extract_worldbank_indicator,
            ("SH.XPD.CHEX.GD.ZS", "2018:2023"),
            "https://api.worldbank.org/v2/country/all/indicator/SH.XPD.CHEX.GD.ZS"
        ),
        (
            "World Bank",
            "NY.GDP.PCAP.CD",
            "GDP per capita (current US$)",
            "current US$",
            extract_worldbank_indicator,
            ("NY.GDP.PCAP.CD", "2018:2023"),
            "https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD"
        ),
    ]

    for src_name, ind_code, ind_name, unit, extractor, args, src_url in indicators_to_load:
        logger.info(f"Processing indicator: {ind_code} ({ind_name}) from {src_name}...")
        try:
            df_raw = extractor(*args)
            df_cleaned = clean_observations(df_raw, valid_country_codes=valid_iso3)
            ind_id = get_or_create_indicator(
                code=ind_code,
                name=ind_name,
                unit=unit,
                source_id=source_map[src_name]
            )
            rows = load_observations(
                df=df_cleaned,
                indicator_id=ind_id,
                source_name=src_name,
                indicator_code=ind_code,
                source_url=src_url
            )
            logger.info(f"Loaded {rows} observations for {ind_code}.")
        except Exception as e:
            logger.error(f"Error importing {ind_code}: {e}", exc_info=True)

    logger.info("ETL pipeline execution completed successfully.")


if __name__ == "__main__":
    run_pipeline()
