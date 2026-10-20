-- ATLAS cohort CKD v205 (CKD_ML MCP_STUDY\04_SQL\Cohort_OHDSI_CKD_v205.json), hand-translated to DuckDB from
-- the circe 1.11.1 rendering (Cohort_OHDSI_CKD_v205_circe1.11.1.sql). Same concept sets, windows and
-- occurrence rules; temp tables instead of #tables; ties in the first-event ordering broken by event id.
--   entry      first CKD condition (46271022 + descendants) with >= 730 days of observation after it
--   rule 0     age >= 19 at index (YEAR(index) - year_of_birth)
--   rule 1     >= 2 serum creatinine measurements (3016723 + desc.) in index +0..+730 days
--   rule 2     no RRT (codeset 2) in procedure_occurrence or condition_occurrence on/before index
--   rule 3     no K (1.5-10 mmol/L, unit 8753) / Hb (3-25 g/dL, unit 8713) outside range in index -365..0
-- Output: cohort (cohort_definition_id, subject_id, cohort_start_date, cohort_end_date),
--         cohort_inclusion (one row per qualified person with the four rule flags).

CREATE OR REPLACE TEMP TABLE codesets AS
WITH roots(codeset_id, concept_id) AS (
    VALUES (0, 46271022), (1, 3016723), (2, 4032243), (2, 4146536), (2, 4322471), (2, 199991),
           (4, 3000963), (4, 3027484), (5, 3023103), (5, 3005456)),
inc AS (
    SELECT r.codeset_id, c.concept_id FROM roots r JOIN concept c ON c.concept_id = r.concept_id
    UNION
    SELECT r.codeset_id, c.concept_id FROM roots r
    JOIN concept_ancestor ca ON ca.ancestor_concept_id = r.concept_id
    JOIN concept c ON c.concept_id = ca.descendant_concept_id AND c.invalid_reason IS NULL)
SELECT codeset_id, concept_id FROM inc
UNION
SELECT i.codeset_id, cr.concept_id_1 FROM inc i
JOIN concept_relationship cr ON cr.concept_id_2 = i.concept_id AND cr.relationship_id = 'Maps to' AND cr.invalid_reason IS NULL;

CREATE OR REPLACE TEMP TABLE primary_events AS
SELECT co.person_id, co.condition_occurrence_id AS event_id, co.condition_start_date AS start_date,
       COALESCE(co.condition_end_date, co.condition_start_date + 1) AS end_date,
       op.observation_period_start_date AS op_start_date, op.observation_period_end_date AS op_end_date
FROM condition_occurrence co
JOIN codesets cs ON cs.codeset_id = 0 AND cs.concept_id = co.condition_concept_id
JOIN observation_period op ON op.person_id = co.person_id
     AND co.condition_start_date >= op.observation_period_start_date
     AND co.condition_start_date <= op.observation_period_end_date
WHERE op.observation_period_start_date <= co.condition_start_date
  AND co.condition_start_date + 730 <= op.observation_period_end_date;

CREATE OR REPLACE TEMP TABLE qualified_events AS
SELECT person_id, event_id, start_date, end_date, op_start_date, op_end_date FROM (
    SELECT pe.*, row_number() OVER (PARTITION BY person_id ORDER BY start_date, event_id) AS ordinal
    FROM primary_events pe)
WHERE ordinal = 1;

CREATE OR REPLACE TABLE cohort_inclusion AS
WITH r_age AS (
    SELECT q.person_id FROM qualified_events q JOIN person p ON p.person_id = q.person_id
    WHERE YEAR(q.start_date) - p.year_of_birth >= 19),
r_cr AS (
    SELECT q.person_id FROM qualified_events q
    JOIN measurement m ON m.person_id = q.person_id
    JOIN codesets cs ON cs.codeset_id = 1 AND cs.concept_id = m.measurement_concept_id
    WHERE m.measurement_date >= q.op_start_date AND m.measurement_date <= q.op_end_date
      AND m.measurement_date >= q.start_date AND m.measurement_date <= q.start_date + 730
    GROUP BY q.person_id HAVING count(*) >= 2),
rrt AS (
    SELECT q.person_id FROM qualified_events q
    JOIN procedure_occurrence po ON po.person_id = q.person_id
    JOIN codesets cs ON cs.codeset_id = 2 AND cs.concept_id = po.procedure_concept_id
    WHERE po.procedure_date >= q.op_start_date AND po.procedure_date <= q.op_end_date
      AND po.procedure_date <= q.start_date
    UNION
    SELECT q.person_id FROM qualified_events q
    JOIN condition_occurrence co ON co.person_id = q.person_id
    JOIN codesets cs ON cs.codeset_id = 2 AND cs.concept_id = co.condition_concept_id
    WHERE co.condition_start_date >= q.op_start_date AND co.condition_start_date <= q.op_end_date
      AND co.condition_start_date <= q.start_date),
implausible AS (
    SELECT q.person_id FROM qualified_events q
    JOIN measurement m ON m.person_id = q.person_id
    JOIN codesets cs ON cs.concept_id = m.measurement_concept_id
    WHERE m.measurement_date >= q.op_start_date AND m.measurement_date <= q.op_end_date
      AND m.measurement_date >= q.start_date - 365 AND m.measurement_date <= q.start_date
      AND ((cs.codeset_id = 5 AND NOT (m.value_as_number >= 1.5 AND m.value_as_number <= 10.0) AND m.unit_concept_id IN (8753))
        OR (cs.codeset_id = 4 AND NOT (m.value_as_number >= 3.0 AND m.value_as_number <= 25.0) AND m.unit_concept_id IN (8713))))
SELECT q.person_id, q.start_date, q.op_start_date, q.op_end_date,
       q.person_id IN (SELECT person_id FROM r_age) AS rule_age,
       q.person_id IN (SELECT person_id FROM r_cr) AS rule_creatinine,
       q.person_id NOT IN (SELECT person_id FROM rrt) AS rule_no_rrt,
       q.person_id NOT IN (SELECT person_id FROM implausible) AS rule_no_implausible
FROM qualified_events q;

CREATE OR REPLACE TABLE cohort AS
SELECT 205 AS cohort_definition_id, person_id AS subject_id, start_date AS cohort_start_date,
       LEAST(start_date + 730, op_end_date) AS cohort_end_date
FROM cohort_inclusion
WHERE rule_age AND rule_creatinine AND rule_no_rrt AND rule_no_implausible;
