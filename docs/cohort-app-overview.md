# Synaptiq Cohort Builder
## Product Overview & Technical Reference

**Version:** 0.1.0 POC &nbsp;|&nbsp; **Platform:** Azure Databricks &nbsp;|&nbsp; **Date:** June 2026  
**Author:** Synaptiq Engineering

---

# SECTION 1 — EXECUTIVE SUMMARY
### *For Clinical Researchers, Research Coordinators & Business Stakeholders*

---

## What Is It?

The **Synaptiq Cohort Builder** is an AI-powered patient cohort identification platform built on Azure Databricks. It allows clinical researchers, research coordinators, and care management analysts to define, preview, and save patient cohorts using structured clinical criteria — ICD-10 diagnoses, RxNorm medications, LOINC lab thresholds — and NLP-derived findings extracted directly from free-text clinical notes, without writing a single line of SQL.

It was purpose-built to solve one of the most labor-intensive bottlenecks in clinical research: **identifying the right patients, quickly, with a reproducible and explainable audit trail.**

---

## The Problem It Solves

Patient cohort identification touches nearly every function in a health system — clinical trials, quality reporting, population health, care management, and comparative effectiveness research. Today the process is slow, fragmented, and error-prone:

| Problem | Impact |
|---|---|
| Multi-table SQL written by hand per study | Days to weeks per cohort; bottleneck on data engineering |
| ICD codes alone miss 20–40% of clinically relevant findings | Incomplete cohorts; patients documented only in notes are invisible |
| No audit trail of who qualified and why | Compliance risk; results not reproducible across teams |
| Cohort logic lives in one-off notebooks | Can't be re-used, versioned, or shared across analysts |
| No standard vocabulary for cohort types | Control cohorts conflated with condition cohorts; study designs poorly documented |

The Synaptiq Cohort Builder eliminates these through a point-and-click criteria builder, NLP-powered note mining, and a persistent gold-layer cohort repository in Unity Catalog.

---

## What It Does

The platform provides a guided four-step workflow and surfaces results through three integrated application pages:

### Step 1 — Cohort Identity
Name the cohort, write a description, classify it by **type** (condition / exposure / control / operational / administrative) and **study design** (retrospective / prospective). These classifications are stored with the cohort definition and drive downstream filtering in the review and governance views.

### Step 2 — Inclusion Criteria (three methods)

**Structured criteria** — point-and-click selection of:
- ICD-10-CM diagnosis codes + clinical status (active / resolved / inactive)
- RxNorm medication codes + order status
- LOINC lab/vital thresholds with numeric min/max bounds
- Date windows and patient demographics (age range, sex)

**NLP-derived criteria** — patients whose clinical notes contain positively-asserted mentions of a concept, filtered by:
- Certainty: positive / uncertain / hypothetical
- Temporality: current / historical / family history
- Negation automatically excluded (`negation = false`)

**Natural Language (Genie)** — *coming in Phase 2* — send a plain-English description to a Databricks Genie Space; receive back a SQL-translated patient set.

### Step 3 — Exclusion Criteria
Optional ICD-10 or RxNorm exclusions applied as NOT IN subqueries against the same clinical tables.

### Step 4 — Preview & Save
- Dry-run count with generated SQL always shown (transparency for researchers)
- Sample patient table (MRN, DOB, sex, race)
- One-click save to `cohort_definition` + `cohort_member` in the gold layer
- Each saved member record includes `index_date` (time-zero anchor) and `qualifying_source`

---

## Key Outputs Per Cohort

| Output | Where | Description |
|---|---|---|
| Cohort definition | `dev.test_gold_ehr_cohort.cohort_definition` | Name, type, category, criteria JSON, version, created_by |
| Member roster | `dev.test_gold_ehr_cohort.cohort_member` | patient_sk, index_date, qualifying_source, qualifying_evidence |
| Patient feature table | `dev.test_gold_ehr_cohort.patient_feature` | Wide per-patient ML features (HbA1c trend, encounter rate, NLP count) |
| CSV export | Browser download | Full member list via My Cohorts page |
| Generated SQL | In-app expander | The exact WHERE clause used — always visible, always reproducible |

---

## Cohort Classification System

Every saved cohort is tagged along two dimensions, stored permanently in `cohort_definition`:

| Dimension | Values | Purpose |
|---|---|---|
| `cohort_type` | `condition` | Patients sharing a clinical diagnosis (e.g. T2DM) |
| | `exposure` | Patients on a specific drug, procedure, or intervention |
| | `control` | Patients WITHOUT the condition/exposure — comparator arm |
| | `operational` | High-cost patients, risk stratification, care gap targets |
| | `administrative` | Trial recruitment lists, quality reporting, billing |
| `cohort_category` | `retrospective` | Built from historical EHR data |
| | `prospective` | Defined on current criteria; captures new patients over time |

---

## Why NLP Matters for Cohort Accuracy

The `note_nlp_entity` table stores extracted clinical mentions with four attributes that make NLP-derived inclusion trustworthy rather than noisy:

| Attribute | Example preventing a false positive |
|---|---|
| `negation = true` | *"No evidence of pneumonia"* → excluded |
| `certainty = 'uncertain'` | *"Rule out sepsis"* → excluded from definite-diagnosis cohorts |
| `temporality = 'family'` | *"Family history of coronary artery disease"* → not attributed to patient |
| `subject = 'family'` | *"Mother has Type 2 diabetes"* → not attributed to patient |

A cohort query using only ICD codes misses patients documented solely in free-text notes. A naïve keyword search catches *"no diabetes"* as a false positive. This model does neither.

---

## Who Uses It

| User | How They Use It |
|---|---|
| **Research Coordinators / PIs** | Build trial recruitment cohorts from ICD + medication criteria; export member lists |
| **Epidemiologists / Data Scientists** | Define retrospective cohorts with index dates; build matched control arms |
| **Care Management Analysts** | Identify high-risk populations for outreach programs |
| **Clinical Informatics** | Validate cohort logic against NLP findings; inspect patient timelines |
| **Data Governance / Compliance** | Audit who defined what cohort, when, and with what criteria |

---

## High-Level Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SYNAPTIQ COHORT BUILDER                               │
│                           Azure Databricks Platform                          │
└─────────────────────────────────────────────────────────────────────────────┘

  USERS                      DATABRICKS APP                  UNITY CATALOG
  ─────                      ──────────────                  ─────────────

  Research                   ┌──────────────────────┐
  Coordinators  ────────────▶│                      │──────▶  dev.test_silver_ehr_clinical
  Data Scientists ──────────▶│   Streamlit UI        │         ├─ patient
  Care Managers ────────────▶│   (Synaptiq Cohort    │         ├─ encounter
  Clinical      ────────────▶│    Builder)           │         ├─ condition
  Informatics                │                      │──────▶  ├─ observation
                             └──────────┬───────────┘         ├─ medication_order
                                        │                      ├─ procedure
                          ┌─────────────▼──────────────┐       ├─ clinical_note
                          │         3 Pages             │       ├─ nlp_run
                          │                            │       └─ note_nlp_entity
                          │  🔬 Cohort Builder          │
                          │  📋 My Cohorts             │──────▶  dev.test_gold_ehr_cohort
                          │  🧑‍⚕️ Patient Explorer       │         ├─ cohort_definition
                          └─────────────┬──────────────┘         ├─ cohort_member
                                        │                         └─ patient_feature
                                        │ databricks-sql-connector
                          ┌─────────────▼──────────────┐
                          │   SQL Warehouse             │
                          │   /sql/1.0/warehouses/      │
                          │   7c48969bf427f0dd          │
                          └────────────────────────────┘
                                        │
                          ┌─────────────▼──────────────┐
                          │   Genie Space (Phase 2)     │
                          │   Natural Language → SQL    │
                          │   over silver tables        │
                          └────────────────────────────┘
```

---

---

# SECTION 2 — TECHNICAL REFERENCE
### *For Data Engineers & Platform Teams*

---

## Architecture Overview

The platform is a **Databricks App** (containerised Streamlit web application) running on Azure Databricks with serverless compute. It has no external dependencies beyond Azure Databricks. Authentication uses ambient OAuth credentials injected by the Databricks Apps runtime — no service principal secret management required in application code.

### Technology Stack

| Layer | Technology |
|---|---|
| UI Framework | Streamlit (Python) |
| Hosting | Databricks Apps (containerised, serverless) |
| Catalog & Security | Unity Catalog (`dev` catalog; `test_` / `prod_` schema prefix for environment isolation) |
| Data Storage | Delta Lake tables (silver clinical layer + gold cohort layer) |
| SQL Execution | `databricks-sql-connector` via SQL warehouse |
| Auth | `databricks-sdk` `WorkspaceClient()` — ambient OAuth (no token management in app code) |
| NLP Pipeline | Spark NLP or Claude API *(Phase 1 — not yet implemented)* |
| Conversational AI | Databricks AI/BI Genie Conversation API *(Phase 2 — not yet implemented)* |
| Synthetic Data | Python + pandas + NumPy; phenotype-driven; written directly to silver via `spark.saveAsTable` |

---

## Application Modules

```
.                               ← repo root = app source root (app.yaml here)
├── app.yaml                    Databricks Apps run command + DATABRICKS_HTTP_PATH env var
├── app.py                      Home dashboard — population KPIs + recent cohorts
├── config.py                   All schema/table constants; cohort type & category value sets
├── db.py                       Connection manager — WorkspaceClient() ambient auth
├── requirements.txt
└── pages/
    ├── 01_cohort_builder.py    Step 1–4 cohort definition, criteria builder, preview, save
    ├── 02_cohort_review.py     Browse + filter saved cohorts; member list; CSV export; status mgmt
    └── 03_patient_explorer.py  MRN search → 6-tab clinical timeline (encounters, conditions,
                                labs/vitals with Plotly trend, medications, procedures, notes + NLP)
```

**Supporting notebooks (Databricks workspace):**

```
generate_ehr_silver.py      Synthetic data generator — writes all 7 silver tables
sample_clinical_notes.py    Clinical note template library — %run'd by generator
ddl/
  01_catalog_and_schemas.sql   Creates dev.test_silver_ehr_clinical + dev.test_gold_ehr_cohort
  03_silver_clinical_model.sql 7 clinical tables
  04_nlp.sql                   nlp_run + note_nlp_entity
  05_gold_cohort.sql           cohort_definition + cohort_member + patient_feature
```

---

## Data Model

Two schemas in the `dev` Unity Catalog. The `test_` prefix isolates the POC environment; swap to `prod_` for production — all application code reads constants from `config.py`.

### Silver layer — `dev.test_silver_ehr_clinical`

| Table | Description | Key columns |
|---|---|---|
| `patient` | Demographics | mrn, birth_date, sex, race, ethnicity, zip |
| `encounter` | All visit types (inpatient / outpatient / ED / telehealth) | encounter_class, period_start, period_end, facility_name |
| `condition` | ICD-10-CM diagnoses + problem list | condition_code, clinical_status, is_chronic, onset_date |
| `observation` | LOINC labs + vital signs (one table, category discriminates) | observation_code, category, value_numeric, parent_observation_sk |
| `medication_order` | RxNorm prescriptions + inpatient orders | med_code, order_status, dose_quantity, route, frequency |
| `procedure` | CPT / HCPCS procedures | procedure_code, procedure_category, performed_datetime |
| `clinical_note` | Full free-text note body | note_category, note_type_display, service_date, note_text |
| `nlp_run` | NLP pipeline execution metadata | pipeline_name, model_version, run_status, notes_processed |
| `note_nlp_entity` | Extracted clinical entities | concept_code, certainty, negation, temporality, subject, confidence |

**BP observation pattern:** Blood pressure is stored as three rows — parent panel (LOINC `85354-9`) + systolic component (`8480-6`) + diastolic component (`8462-4`), linked via `parent_observation_sk`. The Patient Explorer filters to `parent_observation_sk IS NULL` for the top-level display.

### Gold layer — `dev.test_gold_ehr_cohort`

| Table | Description | Key columns |
|---|---|---|
| `cohort_definition` | Named cohort criteria, versioned | cohort_type, cohort_category, definition_logic (JSON), primary_concept_code, status, version |
| `cohort_member` | Who qualified + why + when | patient_sk, index_date, qualifying_source, qualifying_evidence (VARIANT) |
| `patient_feature` | Wide per-patient ML feature table | *(assembly notebook — Phase 1)* |

**Cross-schema FK:** `cohort_member.patient_sk → dev.test_silver_ehr_clinical.patient.patient_sk` (`NOT ENFORCED RELY` — optimizer hint, not enforced at write time).

### DDL conventions

- **Surrogate keys:** `BIGINT GENERATED BY DEFAULT AS IDENTITY` — explicit values insertable by generator
- **Coding pattern:** every clinical code stored as `(*_code, *_system, *_display)` trio — no vocabulary reference tables
- **Constraints:** `PRIMARY KEY` / `FOREIGN KEY` with `NOT ENFORCED RELY` — informational only
- **Clustering:** `CLUSTER BY` (liquid clustering) — no static partitioning
- **Column defaults:** all tables include `TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')` — required for serverless SQL warehouses
- **No UNIQUE constraints:** disabled on serverless (`spark.databricks.sql.dsv2.unique.enabled` not settable via SQL)

---

## Synthetic Data Generator

### Phenotype-driven generation

500 patients (scalable to 5,000) are assigned one of six clinical phenotypes at creation time. The phenotype drives conditions, medications, labs, note templates, and encounter frequency — ensuring the demo cohort query returns a realistic and explainable result set.

| Phenotype | % | ~N (500-pt) | Clinical profile |
|---|---|---|---|
| `t2dm_cvd` | 10% | 50 | **Primary demo target** — T2DM + metformin + CAD or heart failure |
| `t2dm_only` | 20% | 100 | T2DM on metformin, no cardiovascular history |
| `t2dm_alt_med` | 10% | 50 | T2DM on Januvia or insulin — intentionally excluded from metformin cohort |
| `hypertension` | 20% | 100 | Essential HTN, no diabetes |
| `prediabetes` | 5% | 25 | Borderline glucose, lifestyle management only |
| `general` | 35% | 175 | Mixed background population |

**Date range:** 2025-01-01 → 2026-12-31  
**Seed:** `SEED = 42` (change for a different population; all runs reproducible)

### Clinical note strategy

Each encounter gets one clinical note. Note category and template are selected by encounter class and patient phenotype. The template library in `sample_clinical_notes.py` includes all four `certainty` values and all three `temporality` values — giving the NLP pipeline realistic training and validation material.

| Encounter class | Note category | Example content |
|---|---|---|
| Inpatient | Discharge summary | Heart failure + T2DM admission; metformin held/resumed; negated PE and MI |
| First outpatient | History & Physical | New T2DM presentation; rule-out T1DM vs T2DM; slow-healing wound |
| Follow-up | Progress note | Diabetes monitoring; peripheral neuropathy; negated retinopathy |
| Prediabetes | Progress note | Asymptomatic; family history T2DM; lifestyle counseling |
| General | Acute care note | URI, rule-out pneumonia; negated diabetes |

---

## Deployment

| Component | Value |
|---|---|
| App name | `cohort-builder` |
| App URL | *(available in Databricks workspace → Compute → Apps)* |
| SQL warehouse HTTP path | `/sql/1.0/warehouses/7c48969bf427f0dd` |
| Workspace | `https://adb-7405619521761591.11.azuredatabricks.net` |
| Catalog | `dev` |
| Silver schema | `dev.test_silver_ehr_clinical` |
| Gold schema | `dev.test_gold_ehr_cohort` |
| Source repo | `github.com/synaptiq/Synatpq-cohort-app` (branch: `main`) |
| Environment | Sync from `main` in Databricks Repos → redeploy app |

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Auth | `WorkspaceClient()` ambient OAuth (no token) | Databricks Apps injects credentials at runtime; no secret management in code |
| Schema isolation | `test_` / `prod_` prefix on schema names | Single `dev` catalog available; environment swap is a one-line change in `config.py` |
| No Bronze layer | Synthetic data written directly to silver | POC has no real source system; FHIR/Clarity integration documented in `docs/` for Phase 3 |
| Vocabulary storage | Inline `(*_code, *_system, *_display)` trios | No separate vocab tables needed for POC; avoids join complexity |
| BP observations | 3-row parent + systolic + diastolic pattern | Matches FHIR `Observation.component` model; preserves component-level codes for LOINC queries |
| Cohort save pattern | INSERT to gold tables (not Spark write) | SQL connector available in Apps container; no SparkSession needed for single-record inserts |
| NLP false-positive prevention | `negation`, `certainty`, `temporality`, `subject` columns | Naïve keyword search catches negated/family mentions as false positives; this model does not |
| Generated SQL always visible | Expander shown even when n=0 | Researchers need to verify the criteria logic; essential for debugging and trust |

---

---

# SECTION 3 — ROADMAP & MILESTONES

---

## Current State (POC v0.1 — June 2026)

| Capability | Status |
|---|---|
| Structured cohort builder (ICD-10 / RxNorm / LOINC / demographics) | ✅ Complete |
| Cohort type + category classification | ✅ Complete |
| Preview with generated SQL transparency | ✅ Complete |
| Save cohort definition + member roster to gold layer | ✅ Complete |
| My Cohorts — browse, filter, export CSV, manage status | ✅ Complete |
| Patient Explorer — MRN search, 6-tab clinical timeline | ✅ Complete |
| Labs & vitals trend charts (Plotly) | ✅ Complete |
| Clinical note viewer with NLP entity panel | ✅ Complete (NLP panel ready; awaits pipeline data) |
| Synthetic 500-patient dataset (6 phenotypes, 2025–2026) | ✅ Complete |
| Databricks App deployment (ambient OAuth, no PAT) | ✅ Complete |

---

## Phase 1 — NLP & Feature Engineering *(Target: Q3 2026)*

| Item | Description |
|---|---|
| **NLP extraction pipeline** | Run Spark NLP or Claude API over `clinical_note` → populate `note_nlp_entity`. Unlocks the NLP-derived criteria tab in Cohort Builder. |
| **NLP-derived cohort builder** | NLP tab currently returns 0 (no pipeline data). Once pipeline runs, validate concept_code matching and certainty/temporality filters. |
| **`patient_feature` assembly notebook** | Compute HbA1c trend slope, encounter utilization rate, NLP finding count, chronic condition burden → write to `patient_feature` for ML/risk use cases. |
| **Risk scoring** | HCC risk score and basic cardiovascular risk flag computed from conditions + medications → appended to `patient_feature`. |
| **Scale to 5,000 patients** | Change `N_PATIENTS = 5000` in generator; re-run after validating 500-patient cohort queries. |

---

## Phase 2 — Intelligence & Natural Language *(Target: Q4 2026)*

| Item | Description |
|---|---|
| **Genie Space configuration** | Configure a Databricks AI/BI Genie Space over `dev.test_silver_ehr_clinical` with curated sample queries. Enables the Natural Language tab in Cohort Builder. |
| **Genie cohort builder integration** | Wire `genie_chat.py`-style API calls into the NL tab — send plain-English cohort description, receive back SQL + patient set. |
| **Cohort comparison view** | Side-by-side demographic and clinical summary for condition cohort vs matched control cohort — age, sex, comorbidity distributions. |
| **Cohort versioning diff** | Compare v1 vs v2 of the same cohort definition — which patients were added/dropped between runs. |
| **Boolean logic builder** | Allow AND/OR grouping of criteria blocks (currently all criteria are AND-joined). |

---

## Phase 3 — Production Readiness *(Target: H1 2027)*

| Item | Description |
|---|---|
| **Real EHR data integration** | FHIR R4 → silver conformance layer. Mapping documented in `docs/ehr-source-schemas.md`. Epic Clarity and athenahealth source schemas mapped. |
| **Bronze landing layer** | Reintroduce `bronze_` schemas for raw FHIR bundles / Clarity extracts before silver conformance. |
| **`prod_` schema promotion** | Rename schemas from `test_` to `prod_`; update `config.py` `SILVER_SCHEMA` / `GOLD_SCHEMA`. Full regression test against real data. |
| **Multi-user cohort sharing** | Cohort definitions visible to team members; `created_by` filters; cohort status workflow (draft → active → archived). |
| **Temporal pattern matching** | Index event + lookback/follow-up window enforcement (condition A must precede medication B by ≤90 days). Uses `index_date` + `lookback_days` / `follow_up_days` columns already in `cohort_definition`. |

---

## Phase 4 — Advanced Analytics *(Target: H2 2027)*

| Item | Description |
|---|---|
| **Survival analysis** | Kaplan-Meier curves for time-to-event outcomes (e.g. time to first CVD event in T2DM cohort) |
| **FHIR bundle export** | Export cohort + qualifying evidence as FHIR Bundle for integration with trial management systems |
| **Email / notification on membership change** | Alert when a prospective cohort gains / loses members vs prior run |
| **Automated cohort refresh** | Scheduled Databricks Job to re-execute cohort SQL and update `cohort_member` nightly |
| **External system integration** | Push cohort member lists to REDCap, Epic Orders, or CTMS via API |

---

*Document maintained in `docs/cohort-app-overview.md` — update as milestones complete.*
