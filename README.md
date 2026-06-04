# Synaptiq Cohort App

NLP-based patient cohort building over synthetic EHR data conformed from multiple
source systems (**Epic** and **athenahealth**) into a single, source-agnostic clinical
data model on **Databricks** (Unity Catalog + Delta Lake).

## What's here

| Path | Contents |
|---|---|
| [`docs/ehr-source-schemas.md`](docs/ehr-source-schemas.md) | Research on the two EHR **source** schemas (Epic Clarity & athenahealth) across 8 clinical domains, plus API/integration and licensing notes. |
| [`docs/ehr-generic-data-model.md`](docs/ehr-generic-data-model.md) | Design of the **generic, FHIR-aligned target model** — domains, tables, keys, NLP layer, cohort layer, and source→target mapping. |
| [`ddl/`](ddl/) | Runnable Databricks SQL DDL for the model. |

## Data model at a glance

A medallion layout in the `ehr_poc` Unity Catalog:

```
ehr_poc
├── bronze        raw FHIR resources + Clarity extracts (VARIANT payloads)
├── terminology   code_system, concept crosswalks (ICD-10 / RxNorm / LOINC / CPT / SNOMED)
├── silver        conformed FHIR-aligned clinical model (8 domains + supporting)  ← core
├── nlp           nlp_run, note_nlp_entity (entities extracted from clinical notes)
└── gold          cohort_definition, cohort_member, patient_feature
```

The 8 clinical domains: **patient**, **encounter**, **condition** (diagnoses),
**medication_order/_administration**, **observation** (labs + vitals), **procedure**,
**diagnostic_report**, and the NLP centerpiece **clinical_note**.

## Running the DDL

Execute against a Databricks SQL warehouse / cluster in order:

```sql
-- in the Databricks SQL editor or via the CLI, run sequentially:
ddl/01_catalog_and_schemas.sql
ddl/02_terminology.sql
ddl/03_silver_clinical_model.sql
ddl/04_nlp.sql
ddl/05_gold_cohort.sql
ddl/06_bronze_landing.sql
```

Notes:
- `PRIMARY KEY` / `FOREIGN KEY` constraints are **informational only** in Databricks
  (not enforced at write time) — the ETL layer owns referential integrity.
- `VARIANT` columns require **DBR 15.3+**; replace with `STRING` (JSON) on older runtimes.
- Tables use **liquid clustering** (`CLUSTER BY`) rather than partitioning.

## Status

Proof-of-concept design + schema. Next candidates: source→silver ETL, a synthetic data
loader (e.g. **Synthea**, `source_system = 'synthea'`), the NLP extraction pipeline, and
example cohort queries.
