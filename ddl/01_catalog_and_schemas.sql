-- =============================================================================
-- 01_catalog_and_schemas.sql
-- Generic Clinical Data Model — Synthetic EHR POC
-- Target: Databricks (Unity Catalog + Delta Lake)
-- Run order: 01 -> 02 -> 03 -> 04 -> 05 -> 06
--
-- Creates the catalog and the 5 medallion/cross-cutting schemas.
-- =============================================================================

CREATE CATALOG IF NOT EXISTS ehr_poc
  COMMENT 'Synthetic EHR POC: source-agnostic, FHIR-aligned clinical model for NLP cohort building.';

-- Raw landing (as-ingested FHIR resources + Clarity extracts; VARIANT payloads)
CREATE SCHEMA IF NOT EXISTS ehr_poc.bronze
  COMMENT 'Raw landing layer: untyped/semi-structured source data as ingested.';

-- Reference vocabularies & crosswalks (ICD-10-CM, RxNorm, LOINC, CPT, SNOMED, ...)
CREATE SCHEMA IF NOT EXISTS ehr_poc.terminology
  COMMENT 'Reference layer: standard code systems and concept crosswalks.';

-- Conformed generic clinical model (the heart of the POC) — 8 domains + supporting
CREATE SCHEMA IF NOT EXISTS ehr_poc.silver
  COMMENT 'Conformed layer: FHIR-aligned, source-agnostic clinical model.';

-- NLP run metadata + entities extracted from clinical_note
CREATE SCHEMA IF NOT EXISTS ehr_poc.nlp
  COMMENT 'Derived layer: NLP pipeline runs and entities extracted from clinical notes.';

-- Cohort definitions, membership, and patient feature marts
CREATE SCHEMA IF NOT EXISTS ehr_poc.gold
  COMMENT 'Mart layer: cohort definitions, membership (coded/NLP provenance), feature tables.';
