-- =============================================================================
-- 01_catalog_and_schemas.sql
-- Synthetic EHR POC — AI-Powered Patient Cohort Builder
-- Target: Databricks (Unity Catalog + Delta Lake)
-- Run order: 01 → 03 → 04 → 05  (02 and 06 are intentionally empty)
--
-- Uses the existing 'dev' catalog.
-- Schema naming convention: {env}_{layer}_{domain}
--   test_  prefix = development / POC environment
--   prod_  prefix = production environment
--
-- Two schemas:
--   dev.test_silver_ehr_clinical  — clinical domain tables + NLP outputs
--   dev.test_gold_ehr_cohort      — cohort definitions, membership, ML features
-- =============================================================================

-- Clinical domain tables: patient, encounter, condition, observation,
-- medication_order, procedure, clinical_note, nlp_run, note_nlp_entity
CREATE SCHEMA IF NOT EXISTS dev.test_silver_ehr_clinical
  COMMENT 'Silver / clinical layer: core EHR domain tables and NLP entity outputs, populated with synthetic (Synthea) data. Swap test_ prefix to prod_ for production.';

-- Cohort output tables: cohort_definition, cohort_member, patient_feature
CREATE SCHEMA IF NOT EXISTS dev.test_gold_ehr_cohort
  COMMENT 'Gold / cohort layer: cohort definitions, membership with coded/NLP provenance, and per-patient ML feature table. Swap test_ prefix to prod_ for production.';
