# Synaptiq Cohort App

AI-powered patient cohort builder on **Databricks** using Genie for natural-language
queries, NLP entity extraction from clinical notes, and explainable cohort membership.
Populated with **synthetic (Synthea) EHR data** — no real PHI required.

## What's here

| Path | Contents |
|---|---|
| [`docs/ehr-generic-data-model.md`](docs/ehr-generic-data-model.md) | Full data model design — domains, tables, NLP layer, cohort layer. |
| [`docs/ehr-source-schemas.md`](docs/ehr-source-schemas.md) | Reference: Epic Clarity & athenahealth source schemas (for future real-data integration). |
| [`ddl/`](ddl/) | Runnable Databricks SQL DDL. |

## Data model at a glance

Two schemas in the existing `dev` Unity Catalog. Schema prefix `test_` = POC/dev environment; swap to `prod_` for production:

```
dev.test_silver_ehr_clinical        (clinical domain + NLP)
├── patient               demographics
├── encounter             visits / admissions
├── condition             diagnoses + problem list (ICD-10-CM)
├── observation           lab results + vital signs (LOINC)  [category discriminates]
├── medication_order      prescriptions / orders (RxNorm)
├── procedure             clinical procedures (CPT)
├── clinical_note         free-text notes  ← NLP input
├── nlp_run               NLP pipeline metadata (reproducibility)
└── note_nlp_entity       extracted clinical entities with negation/certainty/temporality

dev.test_gold_ehr_cohort            (cohort output)
├── cohort_definition     named cohort criteria (from Genie or UI)
├── cohort_member         who qualified + WHY (coded | nlp | both)
└── patient_feature       wide per-patient ML feature table (optional)
```

### Why this works for the demo

- **Genie** can query all tables in one schema with natural language:
  *"Find patients with Type 2 diabetes on metformin with a cardiovascular event in the last 2 years"*
- **Coded path**: `condition` + `medication_order` + `procedure`/`observation` joins
- **NLP path**: `note_nlp_entity` with `negation=false AND certainty='positive' AND temporality='current'` guards against false-positive matches
- **Explainability**: `cohort_member.qualifying_source` and `qualifying_evidence` show exactly why each patient qualified

## Running the DDL

Execute against a Databricks SQL warehouse in order (02 and 06 are no-ops — skip them):

```sql
ddl/01_catalog_and_schemas.sql   -- dev.test_silver_ehr_clinical + dev.test_gold_ehr_cohort schemas
ddl/03_poc_clinical_tables.sql   -- patient, encounter, condition, observation,
                                 --   medication_order, procedure, clinical_note
ddl/04_nlp_tables.sql            -- nlp_run, note_nlp_entity
ddl/05_cohort_tables.sql         -- cohort_definition, cohort_member, patient_feature
```

Notes:
- `PRIMARY KEY` / `FOREIGN KEY` constraints are **informational only** (`NOT ENFORCED RELY`)
  — they document intent and help the optimizer; the data loader owns referential integrity.
- `VARIANT` columns (in `cohort_member.qualifying_evidence`) require **DBR 15.3+**;
  replace with `STRING` (JSON) on older runtimes.
- Tables use **liquid clustering** (`CLUSTER BY`) rather than partitioning.

## Loading synthetic data

Use **[Synthea](https://github.com/synthetichealth/synthea)** to generate FHIR R4 NDJSON,
then map FHIR resources to `ehr_poc.clinical.*` tables:

| FHIR resource | Target table |
|---|---|
| `Patient` | `patient` |
| `Encounter` | `encounter` |
| `Condition` | `condition` |
| `Observation` | `observation` |
| `MedicationRequest` | `medication_order` |
| `Procedure` | `procedure` |
| `DocumentReference` + `Binary` | `clinical_note` |

For demo notes (NLP path), hand-author 10–20 synthetic discharge summaries that include:
- Positive mentions: *"The patient has Type 2 diabetes mellitus..."*
- Negated mentions: *"No evidence of pneumonia..."*
- Family history: *"Family history of coronary artery disease..."*
- Uncertain mentions: *"Rule out sepsis..."*

These exercise all four `certainty` values and validate the NLP cohort logic.

## Next steps

- [ ] Synthea loader notebook (FHIR → `ehr_poc.clinical.*`)
- [ ] Hand-authored synthetic notes + NLP extraction pipeline
- [ ] Genie space configuration over `ehr_poc.clinical` with sample queries
- [ ] Databricks App UI (cohort builder, member list, export)
- [ ] `patient_feature` assembly notebook (for ML risk scoring)
