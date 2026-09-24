"""Build vaccination.db (SQLite) from sql/schema.sql + cleaned_data/*.csv"""
import sqlite3
import pandas as pd
import os

DB_PATH = "vaccination.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = sqlite3.connect(DB_PATH)
with open("sql/schema.sql") as f:
    ddl = f.read()
conn.executescript(ddl)

tables = {
    "dim_country": "cleaned_data/dim_country.csv",
    "dim_antigen": "cleaned_data/dim_antigen.csv",
    "dim_disease": "cleaned_data/dim_disease.csv",
    "dim_vaccine": "cleaned_data/dim_vaccine.csv",
    "fact_coverage": "cleaned_data/fact_coverage.csv",
    "fact_incidence": "cleaned_data/fact_incidence.csv",
    "fact_reported_cases": "cleaned_data/fact_reported_cases.csv",
    "fact_vaccine_introduction": "cleaned_data/fact_vaccine_introduction.csv",
    "fact_vaccine_schedule": "cleaned_data/fact_vaccine_schedule.csv",
}

for table, path in tables.items():
    df = pd.read_csv(path)
    df.to_sql(table, conn, if_exists="append", index=False)
    print(f"loaded {table:28s} {len(df):>8,} rows")

conn.commit()

# sanity check: row counts + a join
cur = conn.cursor()
cur.execute("""
    SELECT c.who_region, ROUND(AVG(fc.coverage),1) AS avg_coverage
    FROM fact_coverage fc
    JOIN dim_country c ON c.country_code = fc.country_code
    WHERE fc.antigen_code = 'DTPCV3' AND fc.year = 2023
    GROUP BY c.who_region
    ORDER BY avg_coverage DESC
""")
print("\nSanity check — avg DTPCV3 coverage by WHO region, 2023:")
for row in cur.fetchall():
    print(" ", row)

conn.close()
print(f"\n{DB_PATH} built successfully.")
