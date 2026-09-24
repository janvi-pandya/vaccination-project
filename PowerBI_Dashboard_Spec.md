# Power BI Dashboard Specification — Vaccination Data Analysis

Power BI Desktop isn't available to author a `.pbix` file directly in this environment. This
spec is built directly on `sql/schema.sql` / `vaccination.db` and `sql/analysis_queries.sql`, so
connecting Power BI's SQL/ODBC connector to that schema and building each page below reproduces
the dashboards the project brief asks for.

## Data connection
- **Get Data → Database → ODBC/SQLite** pointed at `vaccination.db` (or the same schema loaded
  into SQL Server/PostgreSQL for production use), or **Get Data → Text/CSV** against the files
  in `cleaned_data/` if a live DB connection isn't available.
- Import all 4 dimension tables and 5 fact tables; build relationships `dim_country.country_code
  → fact_*.country_code`, `dim_antigen.antigen_code → fact_coverage.antigen_code`,
  `dim_disease.disease_code → fact_incidence.disease_code` / `fact_reported_cases.disease_code`,
  `dim_vaccine.vaccine_code → fact_vaccine_schedule.vaccine_code`.
- Set a scheduled refresh against the source database once it's hosted centrally.

## Core DAX measures
```
Avg Coverage % = AVERAGE(fact_coverage[coverage])
Total Doses = SUM(fact_coverage[doses])
Total Target Population = SUM(fact_coverage[target_number])
Pct of Target Covered = DIVIDE([Total Doses], [Total Target Population])
Total Reported Cases = SUM(fact_reported_cases[cases])
Avg Incidence Rate = AVERAGE(fact_incidence[incidence_rate])
Countries Below 80% Coverage =
    CALCULATE(DISTINCTCOUNT(fact_coverage[country_code]), fact_coverage[coverage] < 80)
Dose Drop-off pp =
    CALCULATE([Avg Coverage %], fact_coverage[antigen_code] = "DTPCV1")
    - CALCULATE([Avg Coverage %], fact_coverage[antigen_code] = "DTPCV3")
YoY Coverage Change =
    [Avg Coverage %] - CALCULATE([Avg Coverage %], SAMEPERIODLASTYEAR(fact_coverage_date[Date]))
```
(For `SAMEPERIODLASTYEAR`/time intelligence, add a small `Year` calendar table 1980-2023 and mark
it as a date table, or use `year`-based `CALCULATE` filters directly since the grain is annual.)

## Page 1 — Global Overview
- **KPI cards:** Avg Coverage % (latest year), Total Reported Cases (latest year), Countries
  Below 80% Coverage, YoY Coverage Change.
- **Line chart:** Avg Coverage % by Year, one series per antigen (slicer: DTPCV3 / MCV1 / BCG),
  1980–2023.
- **Filled/geographical heatmap:** Avg Coverage % by country (map visual keyed on
  `dim_country.country_code`, ISO-3), for a chosen antigen and year — the brief's "geographical
  heatmap" requirement.
- **Slicers:** Year, WHO Region, Antigen.

## Page 2 — Coverage vs. Disease Burden
- **Dual-axis line/combo chart:** Avg Coverage % (line) vs. Avg Incidence Rate (bars) by Year,
  for a selected disease/antigen pair (default: MCV1 / Measles) — sourced from
  `analysis_queries.sql` query "EASY 1 & 9".
- **Scatter plot:** DTP3 Coverage % (x) vs. Pertussis Incidence Rate (y, log scale), one point
  per country-year, colored by WHO Region — makes the country-level vs. global-aggregate
  distinction visible interactively (drag a time slider to watch the cloud move).
- **Table/matrix:** Top 10 countries by disease cases in the latest year, with their coverage %
  alongside (from analysis query "EASY 10").

## Page 3 — Regional Disparities & Resource Allocation
- **Bar chart:** Avg Coverage % by WHO Region (from analysis query "SCENARIO 1"), sorted
  ascending, with a reference line at the 95% WHO target.
- **Bar chart:** 10 lowest-coverage countries, latest year, colored by WHO Region.
- **Bar chart:** Dose 1 → Dose 3 drop-off (percentage points) by country, sorted descending —
  surfaces the "resource allocation" and "drop-off rate" questions on one page.
- **Slicer:** Antigen, Year.

## Page 4 — Vaccine Introduction & Schedule
- **Step/area chart:** Cumulative countries introducing a selected vaccine, by year and WHO
  Region (from analysis query "MEDIUM 6") — shows introduction-timeline disparities.
- **Table:** Vaccine schedule detail (rounds, target population, age administered) filterable by
  country and vaccine, from `fact_vaccine_schedule`.
- **KPI card:** % of target population covered by a selected antigen (from analysis query
  "MEDIUM 4").

## Page 5 — Priority Diseases
- **Grouped bar chart:** BCG vs. HepB3 coverage by WHO Region (analysis query "MEDIUM 9").
- **Line chart:** Global reported cases over time (log scale) for a selected priority disease
  (TB proxy via BCG antigen framing, Hepatitis B, Measles, Polio).
- **Card:** Countries with coverage ≥ 90% but incidence above the global median for the selected
  disease — the "high incidence despite high coverage" flag from analysis query "EASY 10".

## Interactivity / UX notes
- Every page shares a single **Year** and **WHO Region** slicer, synced across pages
  (Format → Edit Interactions), so a user filtering to AFRO/2023 on Page 1 sees the same filter
  reflected on Pages 2–5.
- Coverage-category (ADMIN/OFFICIAL/WUENIC) should default to **WUENIC** wherever a single
  coverage series is shown, with a small toggle/slicer for users who want to compare
  methodologies (mirrors the EDA notebook's Chart 12 finding).
- Tooltips on the map and scatter visuals should show country name, year, coverage %, and
  incidence rate together, since those are the values analysts will want without drilling in.
