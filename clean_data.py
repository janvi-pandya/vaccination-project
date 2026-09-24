"""
Vaccination Data Analysis — Data Cleaning Script
=================================================
Cleans the 5 raw WHO tables (coverage, incidence rate, reported cases,
vaccine introduction, vaccine schedule) and writes:
  - cleaned fact/dimension CSVs to cleaned_data/
  - a cleaning summary (rows in/out, nulls handled) to cleaned_data/cleaning_log.txt
"""

import pandas as pd
import numpy as np
import os

RAW = "data"
OUT = "cleaned_data"
os.makedirs(OUT, exist_ok=True)

log_lines = []
def log(msg):
    print(msg)
    log_lines.append(str(msg))

# ---------------------------------------------------------------------------
# 1. LOAD
# ---------------------------------------------------------------------------
cov   = pd.read_excel(f"{RAW}/coverage-data.xlsx", sheet_name="Data")
inc   = pd.read_excel(f"{RAW}/incidence-rate-data.xlsx", sheet_name="Data")
cas   = pd.read_excel(f"{RAW}/reported-cases-data.xlsx", sheet_name="Data")
intro = pd.read_excel(f"{RAW}/vaccine-introduction-data.xlsx", sheet_name="Data")
sched = pd.read_excel(f"{RAW}/vaccine-schedule-data.xlsx", sheet_name="Data")

log("RAW ROW COUNTS")
for name, df in [("coverage", cov), ("incidence", inc), ("cases", cas),
                  ("introduction", intro), ("schedule", sched)]:
    log(f"  {name:15s}: {len(df):,}")

# ---------------------------------------------------------------------------
# 2. DROP THE TRAILING METADATA/FOOTER ROW ("Created: ... UTC")
#    Every raw sheet has one junk row at the bottom that isn't real data.
# ---------------------------------------------------------------------------
def drop_footer(df, group_col):
    return df[~df[group_col].astype(str).str.startswith("Created:", na=False)].copy()

cov = drop_footer(cov, "GROUP")
inc = drop_footer(inc, "GROUP")
cas = drop_footer(cas, "GROUP")
# intro/sched carry the same "Created: ... UTC" footer row, keyed off ISO_3_CODE instead of GROUP
intro = drop_footer(intro, "ISO_3_CODE")
sched = drop_footer(sched, "ISO_3_CODE")
intro = intro.dropna(subset=["ISO_3_CODE"]).copy()
sched = sched.dropna(subset=["ISO_3_CODE"]).copy()

# ---------------------------------------------------------------------------
# 3. RESTRICT COUNTRY-LEVEL FACT TABLES TO GROUP == 'COUNTRIES'
#    (coverage/incidence/cases also carry WHO_REGIONS/GLOBAL/WB_* aggregate
#    rollups that would double-count if joined into a country-grain star
#    schema; they're kept in a companion CSV, not the SQL fact tables.)
# ---------------------------------------------------------------------------
cov_agg  = cov[cov["GROUP"] != "COUNTRIES"].copy()
inc_agg  = inc[inc["GROUP"] != "COUNTRIES"].copy()
cas_agg  = cas[cas["GROUP"] != "COUNTRIES"].copy()

cov = cov[cov["GROUP"] == "COUNTRIES"].copy()
inc = inc[inc["GROUP"] == "COUNTRIES"].copy()
cas = cas[cas["GROUP"] == "COUNTRIES"].copy()

log("\nAFTER FOOTER REMOVAL + COUNTRY-LEVEL FILTER")
for name, df in [("coverage", cov), ("incidence", inc), ("cases", cas)]:
    log(f"  {name:15s}: {len(df):,}")

# ---------------------------------------------------------------------------
# 4. TYPE / FORMAT NORMALIZATION
# ---------------------------------------------------------------------------
def clean_year(df, col="YEAR"):
    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df

for df in (cov, inc, cas, intro, sched, cov_agg, inc_agg, cas_agg):
    clean_year(df)

# strip whitespace on all string/object columns
for df in (cov, inc, cas, intro, sched):
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan})
    for c in df.select_dtypes(include="string").columns:
        df[c] = df[c].str.strip()

# normalize Yes/No text in INTRO
intro["INTRO"] = intro["INTRO"].str.title()
intro.loc[~intro["INTRO"].isin(["Yes", "No"]), "INTRO"] = np.nan

# ---------------------------------------------------------------------------
# 5. HANDLE MISSING VALUES
#    Public-health rates are never imputed (a guessed coverage % or
#    incidence rate would fabricate an outcome metric); rows missing the
#    core measured value are dropped from the fact table used for
#    modelling/analysis. NAME==NaN with a valid CODE is filled by looking
#    up any other row with the same CODE.
# ---------------------------------------------------------------------------
def fill_name_from_code(df):
    lookup = df.dropna(subset=["NAME"]).drop_duplicates("CODE").set_index("CODE")["NAME"]
    df["NAME"] = df["NAME"].fillna(df["CODE"].map(lookup))
    return df

cov = fill_name_from_code(cov)
inc = fill_name_from_code(inc)
cas = fill_name_from_code(cas)

n_before = len(cov); cov = cov.dropna(subset=["COVERAGE"]); log(f"\ncoverage: dropped {n_before-len(cov):,} rows with no COVERAGE value ({len(cov):,} remain)")
n_before = len(inc); inc = inc.dropna(subset=["INCIDENCE_RATE"]); log(f"incidence: dropped {n_before-len(inc):,} rows with no INCIDENCE_RATE value ({len(inc):,} remain)")
n_before = len(cas); cas = cas.dropna(subset=["CASES"]); log(f"cases: dropped {n_before-len(cas):,} rows with no CASES value ({len(cas):,} remain)")

# schedule: TARGETPOP / AGEADMINISTERED / SOURCECOMMENT genuinely blank for many
# rows (not every schedule round has a target subgroup) -> keep, mark explicitly
sched["TARGETPOP"] = sched["TARGETPOP"].fillna("NOT_SPECIFIED")
sched["AGEADMINISTERED"] = sched["AGEADMINISTERED"].fillna("NOT_SPECIFIED")

# ---------------------------------------------------------------------------
# 6. NORMALIZE UNITS
#    COVERAGE stays a 0-100 percentage (already consistent in source);
#    DOSES/TARGET_NUMBER/CASES are counts; INCIDENCE_RATE keeps its stated
#    DENOMINATOR (rate base differs by disease, e.g. per 1,000 vs per
#    1,000,000) — denominator is preserved as its own column so rates are
#    never silently compared across different bases.
# ---------------------------------------------------------------------------
cov["COVERAGE"] = cov["COVERAGE"].clip(lower=0, upper=100)

# ---------------------------------------------------------------------------
# 7. DEDUPLICATE
# ---------------------------------------------------------------------------
for name, df in [("coverage", cov), ("incidence", inc), ("cases", cas),
                  ("introduction", intro), ("schedule", sched)]:
    d = df.duplicated().sum()
    if d:
        log(f"{name}: dropping {d} exact duplicate rows")
    df.drop_duplicates(inplace=True)

# ---------------------------------------------------------------------------
# 8. BUILD DIMENSION TABLES
# ---------------------------------------------------------------------------
# country dimension: union of CODE/NAME (fact side) and ISO_3_CODE/COUNTRYNAME/WHO_REGION
c1 = cov[["CODE", "NAME"]].drop_duplicates().rename(columns={"CODE": "country_code", "NAME": "country_name"})
c2 = inc[["CODE", "NAME"]].drop_duplicates().rename(columns={"CODE": "country_code", "NAME": "country_name"})
c3 = cas[["CODE", "NAME"]].drop_duplicates().rename(columns={"CODE": "country_code", "NAME": "country_name"})
c4 = intro[["ISO_3_CODE", "COUNTRYNAME", "WHO_REGION"]].drop_duplicates().rename(
    columns={"ISO_3_CODE": "country_code", "COUNTRYNAME": "country_name", "WHO_REGION": "who_region"})
c5 = sched[["ISO_3_CODE", "COUNTRYNAME", "WHO_REGION"]].drop_duplicates().rename(
    columns={"ISO_3_CODE": "country_code", "COUNTRYNAME": "country_name", "WHO_REGION": "who_region"})

countries = pd.concat([c1, c2, c3], ignore_index=True).drop_duplicates("country_code")
region_map = pd.concat([c4, c5], ignore_index=True).drop_duplicates("country_code")[["country_code", "who_region"]]
dim_country = countries.merge(region_map, on="country_code", how="left").drop_duplicates("country_code").reset_index(drop=True)
log(f"\ndim_country: {len(dim_country)} countries ({dim_country['who_region'].notna().sum()} with a known WHO region)")

dim_antigen = cov[["ANTIGEN", "ANTIGEN_DESCRIPTION"]].drop_duplicates().rename(
    columns={"ANTIGEN": "antigen_code", "ANTIGEN_DESCRIPTION": "antigen_description"}).dropna(subset=["antigen_code"])

dim_disease = pd.concat([
    inc[["DISEASE", "DISEASE_DESCRIPTION"]].rename(columns={"DISEASE": "disease_code", "DISEASE_DESCRIPTION": "disease_description"}),
    cas[["DISEASE", "DISEASE_DESCRIPTION"]].rename(columns={"DISEASE": "disease_code", "DISEASE_DESCRIPTION": "disease_description"}),
], ignore_index=True).drop_duplicates("disease_code").dropna(subset=["disease_code"]).reset_index(drop=True)

dim_vaccine = sched[["VACCINECODE", "VACCINE_DESCRIPTION"]].drop_duplicates().rename(
    columns={"VACCINECODE": "vaccine_code", "VACCINE_DESCRIPTION": "vaccine_description"}).dropna(subset=["vaccine_code"])

# ---------------------------------------------------------------------------
# 9. BUILD FACT TABLES (renamed to snake_case, FK-ready)
# ---------------------------------------------------------------------------
fact_coverage = cov.rename(columns={
    "CODE": "country_code", "YEAR": "year", "ANTIGEN": "antigen_code",
    "COVERAGE_CATEGORY": "coverage_category", "COVERAGE_CATEGORY_DESCRIPTION": "coverage_category_description",
    "TARGET_NUMBER": "target_number", "DOSES": "doses", "COVERAGE": "coverage"
})[["country_code", "year", "antigen_code", "coverage_category",
    "coverage_category_description", "target_number", "doses", "coverage"]].reset_index(drop=True)
fact_coverage.insert(0, "coverage_id", range(1, len(fact_coverage) + 1))

fact_incidence = inc.rename(columns={
    "CODE": "country_code", "YEAR": "year", "DISEASE": "disease_code",
    "DENOMINATOR": "denominator", "INCIDENCE_RATE": "incidence_rate"
})[["country_code", "year", "disease_code", "denominator", "incidence_rate"]].reset_index(drop=True)
fact_incidence.insert(0, "incidence_id", range(1, len(fact_incidence) + 1))

fact_reported_cases = cas.rename(columns={
    "CODE": "country_code", "YEAR": "year", "DISEASE": "disease_code", "CASES": "cases"
})[["country_code", "year", "disease_code", "cases"]].reset_index(drop=True)
fact_reported_cases.insert(0, "case_id", range(1, len(fact_reported_cases) + 1))

fact_vaccine_introduction = intro.rename(columns={
    "ISO_3_CODE": "country_code", "YEAR": "year", "DESCRIPTION": "vaccine_description", "INTRO": "introduced"
})[["country_code", "year", "vaccine_description", "introduced"]].reset_index(drop=True)
fact_vaccine_introduction.insert(0, "intro_id", range(1, len(fact_vaccine_introduction) + 1))

fact_vaccine_schedule = sched.rename(columns={
    "ISO_3_CODE": "country_code", "YEAR": "year", "VACCINECODE": "vaccine_code",
    "SCHEDULEROUNDS": "schedule_rounds", "TARGETPOP": "target_pop",
    "TARGETPOP_DESCRIPTION": "target_pop_description", "GEOAREA": "geoarea",
    "AGEADMINISTERED": "age_administered", "SOURCECOMMENT": "source_comment"
})[["country_code", "year", "vaccine_code", "schedule_rounds", "target_pop",
    "target_pop_description", "geoarea", "age_administered", "source_comment"]].reset_index(drop=True)
fact_vaccine_schedule.insert(0, "schedule_id", range(1, len(fact_vaccine_schedule) + 1))

# ---------------------------------------------------------------------------
# 10. WRITE CLEANED CSVs
# ---------------------------------------------------------------------------
dim_country.to_csv(f"{OUT}/dim_country.csv", index=False)
dim_antigen.to_csv(f"{OUT}/dim_antigen.csv", index=False)
dim_disease.to_csv(f"{OUT}/dim_disease.csv", index=False)
dim_vaccine.to_csv(f"{OUT}/dim_vaccine.csv", index=False)
fact_coverage.to_csv(f"{OUT}/fact_coverage.csv", index=False)
fact_incidence.to_csv(f"{OUT}/fact_incidence.csv", index=False)
fact_reported_cases.to_csv(f"{OUT}/fact_reported_cases.csv", index=False)
fact_vaccine_introduction.to_csv(f"{OUT}/fact_vaccine_introduction.csv", index=False)
fact_vaccine_schedule.to_csv(f"{OUT}/fact_vaccine_schedule.csv", index=False)
# region/global rollups kept separately (not part of the country-grain star schema)
cov_agg.to_csv(f"{OUT}/aggregate_coverage_rollups.csv", index=False)
inc_agg.to_csv(f"{OUT}/aggregate_incidence_rollups.csv", index=False)
cas_agg.to_csv(f"{OUT}/aggregate_cases_rollups.csv", index=False)

log("\nFINAL CLEANED ROW COUNTS")
for name, df in [("dim_country", dim_country), ("dim_antigen", dim_antigen),
                  ("dim_disease", dim_disease), ("dim_vaccine", dim_vaccine),
                  ("fact_coverage", fact_coverage), ("fact_incidence", fact_incidence),
                  ("fact_reported_cases", fact_reported_cases),
                  ("fact_vaccine_introduction", fact_vaccine_introduction),
                  ("fact_vaccine_schedule", fact_vaccine_schedule)]:
    log(f"  {name:28s}: {len(df):,}")

with open(f"{OUT}/cleaning_log.txt", "w") as f:
    f.write("\n".join(log_lines))

print("\nDone. Cleaned files written to", OUT)
