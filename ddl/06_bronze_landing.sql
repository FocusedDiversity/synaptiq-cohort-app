-- =============================================================================
-- 06_bronze_landing.sql
-- Raw landing tables. Retaining raw payloads lets us re-conform silver without
-- re-extracting from source, and recover fields we haven't modeled yet.
--
-- VARIANT requires DBR 15.3+. On older runtimes replace VARIANT with STRING.
-- =============================================================================

-- Generic landing for all FHIR R4 $export NDJSON (Epic on FHIR + athena FHIR).
CREATE TABLE IF NOT EXISTS ehr_poc.bronze.raw_fhir_resource (
  resource_type   STRING NOT NULL COMMENT 'Patient | Encounter | Condition | Observation | DocumentReference | ...',
  resource_id     STRING NOT NULL,
  source_system   STRING NOT NULL COMMENT 'epic | athena | synthea',
  bundle_id       STRING,
  payload         VARIANT COMMENT 'raw FHIR JSON resource',
  ingested_at     TIMESTAMP DEFAULT current_timestamp()
)
COMMENT 'Raw FHIR resources as ingested from $export / bundles.'
CLUSTER BY (source_system, resource_type);

-- Generic landing for Epic Clarity SQL extracts.
CREATE TABLE IF NOT EXISTS ehr_poc.bronze.raw_clarity_extract (
  source_table    STRING NOT NULL COMMENT 'e.g. PAT_ENC, ORDER_RESULTS, HNO_NOTE_TEXT',
  natural_key     STRING COMMENT 'business key of the source row (e.g. PAT_ENC_CSN_ID)',
  payload         VARIANT COMMENT 'raw row as JSON/struct',
  extract_batch_id STRING,
  ingested_at     TIMESTAMP DEFAULT current_timestamp()
)
COMMENT 'Raw Epic Clarity rows as ingested from SQL extracts.'
CLUSTER BY (source_table);
