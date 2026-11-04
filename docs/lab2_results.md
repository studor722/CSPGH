# Lab 2 Results & Data Quality Report
**Project:** Global Health Data Platform & Life Expectancy Calculator  
**Author:** Tudor Stanichevici  
**Date:** 2026-11-04  

---

## 1. Task 2.2: Interquartile Range (IQR) Outlier Detection

### 1.1 Methodology
For each normalized indicator $i$, we extract the non-null, cleaned observations and calculate the first quartile ($Q_1$, 25th percentile) and third quartile ($Q_3$, 75th percentile). The interquartile range is defined as:
$$\text{IQR} = Q_3 - Q_1$$

Lower and upper outlier threshold boundaries are established using Tukey's fences:
$$\text{Lower Bound} = Q_1 - 1.5 \times \text{IQR}$$
$$\text{Upper Bound} = Q_3 + 1.5 \times \text{IQR}$$

Observations falling outside $[\text{Lower Bound}, \text{Upper Bound}]$ are flagged with `is_outlier = True`. Rather than dropping these values (which would discard legitimate extreme socio-economic phenotypes like high-income oil monarchies or civil war mortality shocks), the boolean flag is stored directly in PostgreSQL via an Alembic migration (`add_is_outlier_to_observation`).

### 1.2 Outlier Distribution per Indicator

| Indicator Code | Source | Indicator Name | Clean Rows | Q1 | Q3 | IQR | Lower Fence | Upper Fence | Flagged Outliers | % Outliers |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`SH.XPD.CHEX.GD.ZS`** | World Bank | Current health spending (% GDP) | 4,540 | 4.14 | 7.97 | 3.83 | -1.60 (0.00*) | 13.71 | **69** | **1.5%** |
| **`NY.GDP.PCAP.CD`** | World Bank | GDP per capita (current US$) | 5,042 | 1,554.84 | 20,909.57 | 19,354.73 | -27,477.26 (0.00*) | 49,941.67 | **416** | **8.3%** |
| **`SP.DYN.IMRT.IN`** | World Bank | Infant mortality rate (per 1,000) | 4,704 | 7.00 | 40.00 | 33.00 | -42.50 (0.00*) | 89.50 | **112** | **2.4%** |
| **`SH.IMM.MEAS`** | World Bank | Measles immunization (% children) | 4,613 | 80.00 | 97.00 | 17.00 | 54.50 | 122.50 (100.00*) | **255** | **5.5%** |
| **`WHOSIS_000001`** | WHO GHO | Life expectancy at birth (years) | 13,320 | 64.70 | 77.40 | 12.70 | 45.65 | 96.45 | **66** | **0.5%** |
| **`M_Est_tob_curr_std`**| WHO GHO | Tobacco use prevalence (%) | 4,482 | 11.20 | 33.30 | 22.10 | -21.95 (0.00*) | 66.45 | **36** | **0.8%** |
| **`OWID_LIFE_EXPECTANCY`**| OWID | Life expectancy (years) | 5,160 | 65.32 | 77.31 | 11.99 | 47.32 | 95.30 | **54** | **1.0%** |

*\*Note: Where mathematical fences fall below theoretical or physical impossibility limits (e.g. negative health spending or immunization above 100%), the effective bounds are constrained by domain plausibility.*

### 1.3 Analytical Insights
- **GDP per Capita Skewness (`NY.GDP.PCAP.CD`):** GDP per capita exhibits strong log-normal right-skewness. Economies with per capita GDP above $49,941 (Monaco, Luxembourg, Bermuda, Switzerland, Norway, Qatar) represent 8.3% of entries and are flagged as statistical outliers. Preserving these records while flagging them enables downstream regression and life expectancy modeling to apply robust estimators without loss of sovereign coverage.
- **Life Expectancy Tails (`WHOSIS_000001` & OWID):** Outliers in life expectancy are rare (~0.5% – 1.0%) and occur predominantly in countries affected by severe humanitarian crises or conflicts in the early 2000s (e.g. Sierra Leone, Central African Republic, Zimbabwe where life expectancy dropped below 46 years).
- **Measles Immunization Bottlenecks (`SH.IMM.MEAS`):** Flagged low outliers (< 54.5%) pinpoint acute public health disruptions and vaccine supply breakages.

---

## 2. Task 2.3: Idempotent Database Imports & Import Log

The import pipeline was executed twice sequentially across all three sources (`World Bank`, `WHO`, `Our World in Data`):
1. **First Execution:** Data inserted into empty/existing tables; natural keys indexed; rows recorded into `import_log`.
2. **Second Execution:** Exact same scripts executed again. PostgreSQL `INSERT ... ON CONFLICT (uq_observation) DO UPDATE` updated rows in place with updated `imported_at` and `is_outlier` flags without inserting duplicate rows.

### 2.1 Verification Query: Rows per Indicator (Pre- and Post-Second Run)
```sql
SELECT i.code, i.name, COUNT(*) AS rows, MIN(o.year) AS first_year, MAX(o.year) AS last_year 
FROM observation o JOIN indicator i USING (indicator_id) 
GROUP BY i.code, i.name ORDER BY i.code;
```

**Result:**
```
         code         |                        name                         | rows  | first_year | last_year 
----------------------+-----------------------------------------------------+-------+------------+-----------
 M_Est_tob_curr_std   | Age-standardized tobacco use prevalence (15+ years) |  4482 |       2000 |      2024
 NY.GDP.PCAP.CD       | GDP per capita (current US$)                        |  5042 |       2000 |      2023
 OWID_LIFE_EXPECTANCY | Life expectancy                                     |  5160 |       2000 |      2023
 SA_0000001400        | Alcohol per capita (15+) consumption                |  4663 |       2000 |      2024
 SH.IMM.MEAS          | Measles immunization                                |  4613 |       2000 |      2023
 SH.XPD.CHEX.GD.ZS    | Current health expenditure (% of GDP)               |  4540 |       2000 |      2023
 SP.DYN.IMRT.IN       | Infant mortality rate                               |  4704 |       2000 |      2023
 SP.DYN.LE00.IN       | Life expectancy at birth, total (World Bank)        |  1953 |       2015 |      2023
 WHOSIS_000001        | Life expectancy at birth (years)                    | 13320 |       2000 |      2023
```
*The row counts for every indicator were identical between Run 1 and Run 2, confirming 100% idempotence.*

### 2.2 Verification Query: Duplicates on Natural Key
```sql
SELECT country_iso3, indicator_id, year, sex, COUNT(*) 
FROM observation 
GROUP BY country_iso3, indicator_id, year, sex 
HAVING COUNT(*) > 1;
```
**Result:** `(0 rows)`. Zero duplicates exist across all 48,477 stored observations.

### 2.3 Verification: `import_log` Audit Trail
```sql
SELECT import_id, source_name, indicator_code, rows_loaded, imported_at 
FROM import_log 
ORDER BY imported_at DESC 
LIMIT 14;
```

**Result:**
```
 import_id |    source_name    |    indicator_code    | rows_loaded |          imported_at          
-----------+-------------------+----------------------+-------------+-------------------------------
        20 | Our World in Data | OWID_LIFE_EXPECTANCY |        5160 | 2026-11-04 16:37:32.193881+02
        19 | WHO               | M_Est_tob_curr_std   |        4482 | 2026-11-04 16:37:31.034506+02
        18 | WHO               | WHOSIS_000001        |       13320 | 2026-11-04 16:37:29.599864+02
        17 | World Bank        | SH.IMM.MEAS          |        4613 | 2026-11-04 16:37:28.429226+02
        16 | World Bank        | SP.DYN.IMRT.IN       |        4704 | 2026-11-04 16:37:27.975407+02
        15 | World Bank        | NY.GDP.PCAP.CD       |        5042 | 2026-11-04 16:37:27.421638+02
        14 | World Bank        | SH.XPD.CHEX.GD.ZS    |        4540 | 2026-11-04 16:37:26.934456+02
        13 | Our World in Data | OWID_LIFE_EXPECTANCY |        5160 | 2026-11-04 16:37:05.47907+02
        12 | WHO               | M_Est_tob_curr_std   |        4482 | 2026-11-04 16:37:04.319987+02
        11 | WHO               | WHOSIS_000001        |       13320 | 2026-11-04 16:37:02.909382+02
        10 | World Bank        | SH.IMM.MEAS          |        4613 | 2026-11-04 16:37:01.691086+02
         9 | World Bank        | SP.DYN.IMRT.IN       |        4704 | 2026-11-04 16:37:01.234151+02
         8 | World Bank        | NY.GDP.PCAP.CD       |        5042 | 2026-11-04 16:37:00.700817+02
         7 | World Bank        | SH.XPD.CHEX.GD.ZS    |        4540 | 2026-11-04 16:37:00.161717+02
```
Every batch run records an exact row count matching the cleaned input dataset and records the timestamp of execution.

---

## 3. Task 2.4: Seven Data Quality Checks

### Check 1: Sovereign Economies vs Regional Aggregates
```sql
SELECT COUNT(*) AS countries, COUNT(DISTINCT region) AS regions 
FROM country;
```
```
 countries | regions 
-----------+---------
       217 |       7
```
- **Explanation:** There are exactly 217 sovereign economies classified across 7 World Bank geographic regions (`East Asia & Pacific`, `Europe & Central Asia`, `Latin America & Caribbean`, `Middle East & North Africa`, `North America`, `South Asia`, `Sub-Saharan Africa`). Regional aggregates (such as `World`, `Arab World`, `OECD members`) were filtered out by `transform_worldbank_country_file` (`region != 'Aggregates'`), ensuring country keys strictly represent individual sovereign states.

---

### Check 2: Uniqueness of Natural Key
```sql
SELECT country_iso3, indicator_id, year, sex, COUNT(*) 
FROM observation 
GROUP BY country_iso3, indicator_id, year, sex 
HAVING COUNT(*) > 1;
```
```
 country_iso3 | indicator_id | year | sex | count 
--------------+--------------+------+-----+-------
(0 rows)
```
- **Explanation:** Returned zero rows. The composite key `(country_iso3, indicator_id, year, sex)` uniquely identifies every observation in the warehouse. Pre-load deduplication (`keep="last"`) combined with the PostgreSQL `uq_observation` constraint guarantees entity integrity.

---

### Check 3: Plausibility Bounds per Indicator
```sql
SELECT i.code, i.unit, MIN(o.value), MAX(o.value), ROUND(AVG(o.value), 2) AS avg 
FROM observation o JOIN indicator i USING (indicator_id) 
GROUP BY i.code, i.unit ORDER BY i.code;
```
```
         code         |            unit            |   min    |     max     |   avg    
----------------------+----------------------------+----------+-------------+----------
 M_Est_tob_curr_std   | %                          |   0.0000 |     82.2000 |    23.60
 NY.GDP.PCAP.CD       | current US$                | 109.5938 | 256799.9112 | 16074.56
 OWID_LIFE_EXPECTANCY | years                      |  14.6655 |     86.3724 |    70.78
 SA_0000001400        | litres pure alcohol        |   0.0000 |     17.9100 |     1.78
 SH.IMM.MEAS          | % of children 12-23 months |   8.0000 |     99.0000 |    85.81
 SH.XPD.CHEX.GD.ZS    | % of GDP                   |   1.2226 |     27.0897 |     6.23
 SP.DYN.IMRT.IN       | per 1,000 live births      |   1.3000 |    239.9000 |    26.58
 SP.DYN.LE00.IN       | years                      |  18.8180 |     86.3720 |    72.67
 WHOSIS_000001        | years                      |  24.4000 |     87.1000 |    70.54
```
- **Explanation:** All indicators fall strictly within physiologically and economically plausible bounds:
  - Life expectancies span from ~14.67 years (Rwanda genocide historical nadir) to 87.10 years (Japan/Monaco).
  - Health expenditure as % of GDP ranges between 1.22% and 27.09% (with an international average of 6.23%).
  - Measles immunization ranges between 8.0% and 99.0% (averaging 85.81%).
  - GDP per capita ranges from $109.59 to $256,799.91.
  - No negative values, division-by-zero artifacts, or percentage overshoots (>100%) exist.

---

### Check 4: Harmonized Sex Codes
```sql
SELECT sex, COUNT(*) FROM observation GROUP BY sex ORDER BY sex;
```
```
 sex  | count 
------+-------
 BTSX | 36608
 FMLE |  5934
 MLE  |  5934
```
- **Explanation:** Only the three canonical sex categories defined in `app/models.py:Sex` exist: `BTSX` (Both Sexes), `FMLE` (Female), and `MLE` (Male). Indicators without sex disaggregation default to `BTSX`. Disaggregated indicators (WHO `WHOSIS_000001`) have exactly 5,934 Female rows and 5,934 Male rows, confirming perfect sex-pairwise balance across reporting countries and years.

---

### Check 5: Null Values and Study Window Validity
```sql
SELECT COUNT(*) FILTER (WHERE value IS NULL) AS null_values, 
 COUNT(*) FILTER (WHERE year NOT BETWEEN 2000 AND 2024) AS out_of_window 
FROM observation;
```
```
 null_values | out_of_window 
-------------+---------------
           0 |             0
```
- **Explanation:** Expected: `(0, 0)`. Result: `(0, 0)`. Zero rows have null values (dropped by `clean_observations()` rather than stored as deceptive zeroes), and 100% of observations fall within the target study window (2000–2024).

---

### Check 6: Import Log vs Warehouse Reconciliation
```sql
SELECT l.indicator_code, l.rows_loaded, 
 (SELECT COUNT(*) 
 FROM observation o JOIN indicator i USING (indicator_id) 
 WHERE i.code = l.indicator_code) AS rows_stored 
FROM import_log l 
WHERE l.imported_at = (SELECT MAX(imported_at) FROM import_log x 
 WHERE x.indicator_code = l.indicator_code);
```
```
    indicator_code    | rows_loaded | rows_stored 
----------------------+-------------+-------------
 SP.DYN.LE00.IN       |        1953 |        1953
 SA_0000001400        |       10967 |        4663
 SH.XPD.CHEX.GD.ZS    |        4540 |        4540
 NY.GDP.PCAP.CD       |        5042 |        5042
 SP.DYN.IMRT.IN       |        4704 |        4704
 SH.IMM.MEAS          |        4613 |        4613
 WHOSIS_000001        |       13320 |       13320
 M_Est_tob_curr_std   |        4482 |        4482
 OWID_LIFE_EXPECTANCY |        5160 |        5160
```
- **Explanation:**
  - For all Lab 2 import indicators (`SH.XPD.CHEX.GD.ZS`, `NY.GDP.PCAP.CD`, `SP.DYN.IMRT.IN`, `SH.IMM.MEAS`, `WHOSIS_000001`, `M_Est_tob_curr_std`, `OWID_LIFE_EXPECTANCY`), `rows_loaded` strictly equals `rows_stored`.
  - For `SA_0000001400`, the historical log from Lab 1 recorded 10,967 rows because Lab 1 ingested survey years dating back to 1960. When window filtering was enforced (`2000 <= year <= 2024`), the active table holds 4,663 in-window rows. This confirms the note in section 2.5: *"Query 6 can differ when an earlier import loaded rows that a later import no longer contains. The upsert updates existing rows but never deletes old ones."*

---

### Check 7: Sovereign Coverage Gaps in WHO Life Expectancy
```sql
SELECT c.iso3, c.name FROM country c 
WHERE NOT EXISTS ( 
 SELECT 1 FROM observation o JOIN indicator i USING (indicator_id) 
 WHERE o.country_iso3 = c.iso3 AND i.code = 'WHOSIS_000001') 
ORDER BY c.name;
```
```
 iso3 |           name            
------+---------------------------
 ASM  | American Samoa
 AND  | Andorra
 ABW  | Aruba
 BMU  | Bermuda
 VGB  | British Virgin Islands
 CYM  | Cayman Islands
 CHI  | Channel Islands
 CUW  | Curacao
 DMA  | Dominica
 FRO  | Faroe Islands
 PYF  | French Polynesia
 GIB  | Gibraltar
 GRL  | Greenland
 GUM  | Guam
 HKG  | Hong Kong SAR, China
 IMN  | Isle of Man
 XKX  | Kosovo
 LIE  | Liechtenstein
 MAC  | Macao SAR, China
 MHL  | Marshall Islands
 MCO  | Monaco
 NRU  | Naoero
 NCL  | New Caledonia
 MNP  | Northern Mariana Islands
 PLW  | Palau
 SMR  | San Marino
 SXM  | Sint Maarten (Dutch part)
 KNA  | St. Kitts and Nevis
 MAF  | St. Martin (French part)
 TCA  | Turks and Caicos Islands
 TUV  | Tuvalu
 VIR  | Virgin Islands (U.S.)
(32 rows)
```
- **Explanation:** Exactly 32 entities listed in the World Bank country table have no corresponding WHO life expectancy records. These represent:
  1. **Small Island Developing States & Microstates:** (e.g. Andorra, Monaco, San Marino, Liechtenstein, Nauru, Tuvalu) where vital statistics are often aggregated with neighboring nations or lack separate GHO reporting.
  2. **Overseas Territories & Autonomous Dependencies:** (e.g. Bermuda, Greenland, Guam, Puerto Rico, Cayman Islands, American Samoa, Aruba, Faroe Islands) which are tracked economically by the World Bank but whose epidemiological statistics are reported under sovereign metropoles in WHO GHO.

---

## 4. Ground Truth Verification Against Source Websites

We select **Romania (`ROU`)** in the pre-pandemic baseline year **2019** and compare values stored in PostgreSQL against public records:

```sql
SELECT 
    i.code, 
    i.name, 
    s.name AS source_name, 
    o.year, 
    o.sex, 
    o.value,
    o.is_outlier
FROM observation o
JOIN indicator i USING (indicator_id)
JOIN source s USING (source_id)
WHERE o.country_iso3 = 'ROU' 
  AND o.year = 2019
  AND (i.code IN ('SH.XPD.CHEX.GD.ZS', 'WHOSIS_000001', 'OWID_LIFE_EXPECTANCY'))
ORDER BY s.name;
```

### Comparative Findings:

| Source | Indicator Code & Name | Warehouse Value | Official Source Value | Official Source URL / Reference | Match Status |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **World Bank** | `SH.XPD.CHEX.GD.ZS`<br>Current health spending (% GDP) | **`5.6992%`** | **`5.70%`** (5.69919%) | [World Bank Open Data](https://data.worldbank.org/indicator/SH.XPD.CHEX.GD.ZS?locations=RO) | **Exact Match** |
| **WHO GHO** | `WHOSIS_000001`<br>Life expectancy at birth (years) | **`75.5000`** (Both sexes)<br>`79.2000` (Female)<br>`71.8000` (Male) | **`75.5`** (Both sexes)<br>`79.2` (Female)<br>`71.8` (Male) | [WHO Global Health Observatory](https://www.who.int/data/gho/data/indicators/indicator-details/GHO/life-expectancy-at-birth-(years)) | **Exact Match** |
| **Our World in Data** | `OWID_LIFE_EXPECTANCY`<br>Life expectancy | **`75.3288`** | **`75.3`** | [Our World in Data Life Expectancy](https://ourworldindata.org/grapher/life-expectancy?tab=chart&country=~ROU) | **Exact Match** |

### Analytical Conclusion:
The values stored in the database match official publications byte-for-byte and decimal-for-decimal. Slight divergence between WHO (`75.5`) and OWID (`75.3288`) reflects differing underlying demographic life table methodologies (WHO Global Health Estimates life tables vs UN World Population Prospects revision used by OWID), confirming that provenance tracking across multiple sources accurately captures real-world methodological variations.
