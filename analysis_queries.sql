-- ============================================================================
-- Vaccination Data Analysis — Analytical Queries
-- Each query is numbered against the "Questions to be answered" section of
-- the project brief. These are the queries Power BI's SQL connector would
-- pull from (as DirectQuery views) or that back each dashboard visual.
-- ============================================================================

-- EASY 1 & 9: How do vaccination rates correlate with a decrease in disease incidence?
-- (country-year DTPCV3 coverage vs Pertussis incidence, as one example pairing)
SELECT fc.country_code, fc.year,
       fc.coverage AS dtpcv3_coverage,
       fi.incidence_rate AS pertussis_incidence
FROM fact_coverage fc
JOIN fact_incidence fi
  ON fi.country_code = fc.country_code AND fi.year = fc.year
WHERE fc.antigen_code = 'DTPCV3' AND fi.disease_code = 'PERTUSSIS'
ORDER BY fc.country_code, fc.year;

-- EASY 2: Drop-off rate between 1st dose and subsequent doses (DTP1 -> DTP3)
SELECT d1.country_code, d1.year,
       d1.coverage AS dose1_coverage,
       d3.coverage AS dose3_coverage,
       ROUND(d1.coverage - d3.coverage, 2) AS drop_off_pp
FROM fact_coverage d1
JOIN fact_coverage d3
  ON d1.country_code = d3.country_code AND d1.year = d3.year
WHERE d1.antigen_code = 'DTPCV1' AND d3.antigen_code = 'DTPCV3'
ORDER BY drop_off_pp DESC;

-- EASY 6: Has booster dose uptake increased over time? (4th dose = 1st booster)
SELECT year, ROUND(AVG(coverage), 2) AS avg_booster_coverage
FROM fact_coverage
WHERE antigen_code = 'DIPHCV4'
GROUP BY year
ORDER BY year;

-- EASY 8 (proxy): country size vs coverage, using target_number as a population proxy
SELECT country_code, year, target_number, coverage
FROM fact_coverage
WHERE antigen_code = 'DTPCV3' AND target_number IS NOT NULL
ORDER BY target_number DESC;

-- EASY 10: Regions/countries with high disease incidence despite high vaccination rates
SELECT fc.country_code, c.country_name, fc.year,
       fc.coverage AS coverage_pct, fi.incidence_rate
FROM fact_coverage fc
JOIN fact_incidence fi ON fi.country_code = fc.country_code AND fi.year = fc.year
JOIN dim_country c ON c.country_code = fc.country_code
WHERE fc.antigen_code = 'DTPCV3' AND fi.disease_code = 'PERTUSSIS'
      AND fc.coverage >= 90 AND fi.incidence_rate > 0
ORDER BY fi.incidence_rate DESC;

-- MEDIUM 1 & 2: Vaccine introduction vs trend in disease cases before/after
SELECT vi.country_code, vi.vaccine_description, vi.year AS intro_year,
       rc.year AS case_year, rc.disease_code, rc.cases,
       (rc.year - vi.year) AS years_since_introduction
FROM fact_vaccine_introduction vi
JOIN fact_reported_cases rc
  ON rc.country_code = vi.country_code
  AND rc.year BETWEEN vi.year - 5 AND vi.year + 5   -- +/-5yr window around introduction, not a full cross join
WHERE vi.introduced = 'Yes'
ORDER BY vi.country_code, vi.vaccine_description, rc.year;

-- MEDIUM 3: Diseases with the most significant % reduction in cases (first vs last year on record)
WITH bounds AS (
    SELECT disease_code, country_code, MIN(year) AS min_y, MAX(year) AS max_y
    FROM fact_reported_cases GROUP BY disease_code, country_code
)
SELECT b.disease_code,
       SUM(CASE WHEN rc.year = b.min_y THEN rc.cases ELSE 0 END) AS cases_first_year,
       SUM(CASE WHEN rc.year = b.max_y THEN rc.cases ELSE 0 END) AS cases_last_year
FROM bounds b
JOIN fact_reported_cases rc ON rc.country_code = b.country_code AND rc.disease_code = b.disease_code
GROUP BY b.disease_code;

-- MEDIUM 4: % of target population covered by each vaccine (global, latest year)
SELECT antigen_code,
       ROUND(SUM(doses) * 100.0 / SUM(target_number), 2) AS pct_target_covered
FROM fact_coverage
WHERE year = (SELECT MAX(year) FROM fact_coverage) AND target_number > 0
GROUP BY antigen_code
ORDER BY pct_target_covered DESC;

-- MEDIUM 6: Disparities in vaccine introduction timelines across WHO regions
SELECT c.who_region, vi.vaccine_description,
       MIN(vi.year) AS earliest_intro, MAX(vi.year) AS latest_intro,
       ROUND(AVG(vi.year), 1) AS avg_intro_year
FROM fact_vaccine_introduction vi
JOIN dim_country c ON c.country_code = vi.country_code
WHERE vi.introduced = 'Yes'
GROUP BY c.who_region, vi.vaccine_description
ORDER BY vi.vaccine_description, avg_intro_year;

-- MEDIUM 8: Regions/countries with low coverage despite high vaccine availability
SELECT c.country_name, c.who_region, fc.antigen_code, fc.year, fc.coverage
FROM fact_coverage fc
JOIN dim_country c ON c.country_code = fc.country_code
JOIN fact_vaccine_introduction vi
     ON vi.country_code = fc.country_code AND vi.year <= fc.year
WHERE vi.introduced = 'Yes' AND fc.coverage < 50
ORDER BY fc.coverage ASC;

-- MEDIUM 9: Gaps in coverage for high-priority diseases (TB via BCG, Hepatitis B via HEPB3)
SELECT c.who_region, fc.antigen_code,
       ROUND(AVG(fc.coverage), 2) AS avg_coverage
FROM fact_coverage fc
JOIN dim_country c ON c.country_code = fc.country_code
WHERE fc.antigen_code IN ('BCG', 'HEPB3') AND fc.year = (SELECT MAX(year) FROM fact_coverage)
GROUP BY c.who_region, fc.antigen_code
ORDER BY fc.antigen_code, avg_coverage;

-- MEDIUM 10: Are certain diseases more prevalent in specific geographic areas?
SELECT c.who_region, fi.disease_code, ROUND(AVG(fi.incidence_rate), 3) AS avg_incidence
FROM fact_incidence fi
JOIN dim_country c ON c.country_code = fi.country_code
GROUP BY c.who_region, fi.disease_code
ORDER BY fi.disease_code, avg_incidence DESC;

-- SCENARIO 1: Regions with low vaccination coverage for targeted resource allocation
SELECT c.who_region, ROUND(AVG(fc.coverage), 2) AS avg_coverage, COUNT(DISTINCT fc.country_code) AS n_countries
FROM fact_coverage fc
JOIN dim_country c ON c.country_code = fc.country_code
WHERE fc.antigen_code = 'DTPCV3' AND fc.year = (SELECT MAX(year) FROM fact_coverage)
GROUP BY c.who_region
ORDER BY avg_coverage ASC;

-- SCENARIO 2: Effectiveness of a measles campaign launched ~5 years ago (trend check)
SELECT year, ROUND(AVG(coverage), 2) AS avg_measles_coverage
FROM fact_coverage
WHERE antigen_code = 'MCV1'
GROUP BY year
ORDER BY year;

-- SCENARIO 6: Global progress toward 95% measles coverage by 2030
SELECT year, ROUND(AVG(coverage), 2) AS avg_measles_coverage
FROM fact_coverage
WHERE antigen_code LIKE '%MCV1%'
GROUP BY year
ORDER BY year;
