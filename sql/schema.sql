-- ============================================================================
-- Vaccination Data Analysis — SQL Schema
-- Normalized star schema: 4 dimension tables + 5 fact tables
-- Portable ANSI SQL (tested against SQLite for this deliverable; the same
-- DDL runs on PostgreSQL/MySQL with minor type-name substitutions noted below)
-- ============================================================================

-- ---------------------------------------------------------------------------
-- DIMENSION TABLES
-- ---------------------------------------------------------------------------

CREATE TABLE dim_country (
    country_code   VARCHAR(3)   PRIMARY KEY,   -- ISO Alpha-3 code
    country_name   VARCHAR(150) NOT NULL,
    who_region     VARCHAR(10)                 -- AFRO, AMRO, EMRO, EURO, SEARO, WPRO
);

CREATE TABLE dim_antigen (
    antigen_code        VARCHAR(30)  PRIMARY KEY,
    antigen_description VARCHAR(255) NOT NULL
);

CREATE TABLE dim_disease (
    disease_code        VARCHAR(30)  PRIMARY KEY,
    disease_description VARCHAR(255) NOT NULL
);

CREATE TABLE dim_vaccine (
    vaccine_code        VARCHAR(30)  PRIMARY KEY,
    vaccine_description VARCHAR(255) NOT NULL
);

-- ---------------------------------------------------------------------------
-- FACT TABLES
-- ---------------------------------------------------------------------------

-- Table 1 (report) — Coverage Data
CREATE TABLE fact_coverage (
    coverage_id                    INTEGER PRIMARY KEY,   -- MySQL/Postgres: AUTO_INCREMENT / SERIAL
    country_code                   VARCHAR(3)   NOT NULL,
    year                           SMALLINT     NOT NULL,
    antigen_code                   VARCHAR(30)  NOT NULL,
    coverage_category              VARCHAR(20),
    coverage_category_description  VARCHAR(255),
    target_number                  BIGINT,
    doses                          BIGINT,
    coverage                       DECIMAL(6,2),           -- percentage, 0-100
    FOREIGN KEY (country_code) REFERENCES dim_country(country_code),
    FOREIGN KEY (antigen_code) REFERENCES dim_antigen(antigen_code)
);

-- Table 2 (report) — Incidence Rate
CREATE TABLE fact_incidence (
    incidence_id    INTEGER PRIMARY KEY,
    country_code    VARCHAR(3)   NOT NULL,
    year            SMALLINT     NOT NULL,
    disease_code    VARCHAR(30)  NOT NULL,
    denominator     VARCHAR(60),                 -- rate base, e.g. "per 1,000,000 total population"
    incidence_rate  DECIMAL(12,4),
    FOREIGN KEY (country_code) REFERENCES dim_country(country_code),
    FOREIGN KEY (disease_code) REFERENCES dim_disease(disease_code)
);

-- Table 3 (report) — Reported Cases
CREATE TABLE fact_reported_cases (
    case_id         INTEGER PRIMARY KEY,
    country_code    VARCHAR(3)   NOT NULL,
    year            SMALLINT     NOT NULL,
    disease_code    VARCHAR(30)  NOT NULL,
    cases           BIGINT,
    FOREIGN KEY (country_code) REFERENCES dim_country(country_code),
    FOREIGN KEY (disease_code) REFERENCES dim_disease(disease_code)
);

-- Table 4 (report) — Vaccine Introduction
-- (no vaccine code in the source; vaccine_description is the natural key here)
CREATE TABLE fact_vaccine_introduction (
    intro_id            INTEGER PRIMARY KEY,
    country_code        VARCHAR(3)   NOT NULL,
    year                 SMALLINT     NOT NULL,
    vaccine_description  VARCHAR(255) NOT NULL,
    introduced            VARCHAR(3),             -- 'Yes' / 'No'
    FOREIGN KEY (country_code) REFERENCES dim_country(country_code)
);

-- Table 5 (report) — Vaccine Schedule Data
CREATE TABLE fact_vaccine_schedule (
    schedule_id             INTEGER PRIMARY KEY,
    country_code             VARCHAR(3)   NOT NULL,
    year                      SMALLINT     NOT NULL,
    vaccine_code              VARCHAR(30)  NOT NULL,
    schedule_rounds           DECIMAL(4,1),
    target_pop                VARCHAR(60),
    target_pop_description    VARCHAR(255),
    geoarea                    VARCHAR(60),
    age_administered           VARCHAR(60),
    source_comment             VARCHAR(500),
    FOREIGN KEY (country_code) REFERENCES dim_country(country_code),
    FOREIGN KEY (vaccine_code) REFERENCES dim_vaccine(vaccine_code)
);

-- ---------------------------------------------------------------------------
-- INDEXES for the join/filter patterns the report's questions need most
-- ---------------------------------------------------------------------------
CREATE INDEX idx_coverage_country_year   ON fact_coverage(country_code, year);
CREATE INDEX idx_coverage_antigen        ON fact_coverage(antigen_code);
CREATE INDEX idx_incidence_country_year  ON fact_incidence(country_code, year);
CREATE INDEX idx_incidence_disease       ON fact_incidence(disease_code);
CREATE INDEX idx_cases_country_year      ON fact_reported_cases(country_code, year);
CREATE INDEX idx_cases_disease           ON fact_reported_cases(disease_code);
CREATE INDEX idx_intro_country_year      ON fact_vaccine_introduction(country_code, year);
CREATE INDEX idx_schedule_country_year   ON fact_vaccine_schedule(country_code, year);
