# Synaptiq Cohort Builder — Databricks POC

An AI-powered patient cohort identification platform built on **Databricks**, demonstrating how clinical research teams, data scientists, and care management analysts can rapidly build, validate, and export patient cohorts from structured EHR data and unstructured clinical notes — without writing SQL.

---

## The Problem This Solves

Patient cohort identification is one of the most labor-intensive and error-prone tasks in clinical research, population health, and care management. Today, identifying a cohort like *"adults over 40 with Type 2 diabetes, currently on metformin, who experienced a cardiovascular event in the past two years"* typically requires:

- A data analyst writing complex multi-table SQL across fragmented source systems
- A clinician manually reviewing results for accuracy
- Days to weeks of iteration before a list of eligible patients is production-ready

This compounds across use cases:

| Use Case | Who Needs It | Pain Today |
|---|---|---|
| **Clinical trial recruitment** | Research coordinators, PIs | Weeks of manual chart review; up to 40% of trials fail to recruit on time |
| **Retrospective research** | Epidemiologists, data scientists | Inconsistent phenotyping across studies; no audit trail |
| **Care gap closure** | Care managers, quality teams | High-cost patient lists built in spreadsheets, manually refreshed |
| **Population health** | CMOs, health plan analysts | ICD codes alone miss patients documented only in notes |
| **Comparative effectiveness** | HEOR analysts | Defining matched control cohorts is slow and hard to reproduce |

**The NLP gap** makes this worse: a patient diagnosed in a clinical note — *"the patient's longstanding Type 2 diabetes"* — but not yet coded in the structured record is invisible to every ICD-based query. Studies estimate 20–40% of clinically relevant findings are documented only in free text.

---

## What This App Does

A **Databricks App** (Streamlit UI + Unity Catalog backend) that lets clinicians and researchers:

1. **Build cohorts using natural language or structured criteria** — ICD-10, RxNorm, LOINC, demographics, date windows, and NLP-derived clinical findings from free-text notes
2. **Combine coded and NLP evidence** — a patient qualifies if their structured record OR their clinical notes (with negation/uncertainty filtering) match the criteria
3. **Explain every member** — each patient's qualifying evidence (which condition row, observation, or NLP entity triggered inclusion) is stored and surfaced in the UI
4. **Classify cohorts by study design** — condition, exposure, control, operational, or administrative; retrospective or prospective
5. **Export and reproduce** — cohort definitions are versioned SQL/JSON; membership can be exported to CSV or downstream systems

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Streamlit App (Databricks Apps)                                 │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │ Cohort Builder │  │   My Cohorts    │  │ Patient Explorer │  │
│  │ (ICD/RxNorm/   │  │ (browse, export,│  │ (timeline, notes,│  │
│  │  LOINC + NLP)  │  │  manage status) │  │  NLP entities)   │  │
│  └────────────────┘  └─────────────────┘  └──────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │ databricks-sql-connector
┌───────────────────────────────▼─────────────────────────────────┐
│  Unity Catalog — dev                                             │
│                                                                  │
│  test_silver_ehr_clinical          test_gold_ehr_cohort          │
│  ├─ patient                        ├─ cohort_definition          │
│  ├─ encounter                      ├─ cohort_member              │
│  ├─ condition                      └─ patient_feature            │
│  ├─ observation                                                  │
│  ├─ medication_order                                             │
│  ├─ procedure                                                    │
│  ├─ clinical_note  ◄── NLP ──► note_nlp_entity                  │
│  └─ nlp_run                                                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Repository Layout

```
.
├── app.yaml                      Databricks Apps run command
├── app.py                        Home dashboard
├── config.py                     Schema/table constants
├── db.py                         Connection manager (SP OAuth)
├── requirements.txt
├── pages/
│   ├── 01_cohort_builder.py      Cohort definition + preview + save
│   ├── 02_cohort_review.py       Browse cohorts, member list, CSV export
│   └── 03_patient_explorer.py    MRN search, timeline, note viewer
│
├── ddl/                          SQL DDL — run once to create schemas + tables
│   ├── 01_catalog_and_schemas.sql
│   ├── 03_silver_clinical_model.sql   clinical tables (patient → clinical_note)
│   ├── 04_nlp.sql                     nlp_run + note_nlp_entity
│   └── 05_gold_cohort.sql             cohort_definition + cohort_member + patient_feature
│
├── generate_ehr_silver.py        Databricks notebook — synthetic data generator
├── sample_clinical_notes.py      Databricks notebook — clinical note template library
│
└── docs/
    ├── ehr-generic-data-model.md  Full data model design reference
    └── ehr-source-schemas.md      Epic Clarity & athenahealth source schema notes
```

---

## Data Model

Two schemas in the `dev` Unity Catalog. The `test_` prefix indicates the POC/dev environment; swap to `prod_` for production without changing any application code.

```
dev.test_silver_ehr_clinical        ← clinical + NLP layer
├── patient               demographics (age, sex, race, ethnicity, zip)
├── encounter             visits — inpatient / outpatient / ED / telehealth
├── condition             ICD-10-CM diagnoses + problem list items
├── observation           LOINC lab results + vital signs (one table, category discriminates)
├── medication_order      RxNorm prescriptions and inpatient orders
├── procedure             CPT / HCPCS procedures
├── clinical_note         full free-text note body ← NLP pipeline input
├── nlp_run               NLP pipeline execution metadata (reproducibility)
└── note_nlp_entity       extracted clinical entities with negation / certainty / temporality

dev.test_gold_ehr_cohort            ← cohort output layer
├── cohort_definition     named cohort criteria, type, category, version
├── cohort_member         who qualified + WHY + index date
└── patient_feature       wide per-patient ML feature table
```

### Cohort classification

Every saved cohort is tagged along two axes:

| Dimension | Values | Purpose |
|---|---|---|
| `cohort_type` | `condition` / `exposure` / `control` / `operational` / `administrative` | What the cohort is for |
| `cohort_category` | `retrospective` / `prospective` | When relative to the data |

### Why NLP matters for cohort accuracy

The `note_nlp_entity` table stores extracted clinical mentions with four attributes that make NLP-derived cohorts trustworthy rather than noisy:

| Attribute | Example preventing a false positive |
|---|---|
| `negation = true` | *"No evidence of pneumonia"* → excluded |
| `certainty = 'uncertain'` | *"Rule out sepsis"* → excluded from definite-diagnosis cohorts |
| `temporality = 'family'` | *"Family history of coronary artery disease"* → not attributed to patient |
| `subject = 'family'` | *"Mother has Type 2 diabetes"* → not attributed to patient |

A cohort query using only ICD codes misses patients documented solely in notes. A naïve keyword search on notes catches *"no diabetes"* as a false positive. This model does neither.

---

## Synthetic Data Generator

The POC is populated entirely with **Python-generated synthetic data** — no real PHI, no external dependencies, fully deterministic with a seed. There is no Bronze/FHIR ingestion layer; data is written directly to the silver tables via `spark.createDataFrame()` → `saveAsTable()`.

### Phenotype-driven generation

Patients are assigned a clinical phenotype at creation time. The phenotype drives which conditions, medications, labs, and note content each patient receives — ensuring the demo cohort query returns a realistic and explainable result set.

| Phenotype | % | ~N (500-pt run) | Clinical profile |
|---|---|---|---|
| `t2dm_cvd` | 10% | 50 | **Primary demo target** — T2DM + metformin + coronary artery disease or heart failure |
| `t2dm_only` | 20% | 100 | T2DM managed with metformin, no cardiovascular history |
| `t2dm_alt_med` | 10% | 50 | T2DM on Januvia or insulin — intentionally **excluded** from the metformin cohort |
| `hypertension` | 20% | 100 | Essential HTN, no diabetes |
| `prediabetes` | 5% | 25 | Incidental borderline glucose — lifestyle management only |
| `general` | 35% | 175 | Mixed background population |

### Clinical note strategy

Each encounter gets one clinical note. The note category and template are chosen based on encounter class and patient phenotype:

| Encounter class | Note category | Example phenotype content |
|---|---|---|
| `inpatient` | Discharge summary | Heart failure + T2DM admission; metformin held/resumed; negated PE and MI |
| First outpatient | History & Physical | New T2DM presentation; rule-out T1DM vs T2DM; slow-healing wound |
| Follow-up | Progress note | Diabetes monitoring; peripheral neuropathy; negated retinopathy |
| Prediabetes | Progress note | Asymptomatic; family history T2DM; lifestyle counseling |
| General | Acute care note | URIs, rule-out pneumonia; negated diabetes |

Notes are rendered from clinical templates in [`sample_clinical_notes.py`](sample_clinical_notes.py) using patient-specific demographics and phenotype-appropriate lab values. The template library deliberately includes all four `certainty` values and all three `temporality` values to give the NLP pipeline realistic training and validation material.

### Configuration knobs

All population parameters live at the top of [`generate_ehr_silver.py`](generate_ehr_silver.py):

```python
N_PATIENTS = 500          # change to 5000 for full run
SEED       = 42           # change for a different population
DATE_START = datetime.date(2025, 1, 1)
DATE_END   = datetime.date(2026, 12, 31)

PHENOTYPE_DIST = {        # proportions must sum to 1.0
    "t2dm_cvd":    0.10,
    "t2dm_only":   0.20,
    ...
}
```

---

## Setup & Run Order

### 1. Create schemas and tables (run once)

Execute against a Databricks SQL warehouse in order. Files `02_terminology.sql` and `06_bronze_landing.sql` are intentionally empty — skip them.

```
ddl/01_catalog_and_schemas.sql     ← creates dev.test_silver_ehr_clinical + dev.test_gold_ehr_cohort
ddl/03_silver_clinical_model.sql   ← 7 clinical tables
ddl/04_nlp.sql                     ← nlp_run + note_nlp_entity
ddl/05_gold_cohort.sql             ← cohort_definition + cohort_member + patient_feature
```

**Known Databricks SQL warehouse requirements:**
- All tables include `TBLPROPERTIES ('delta.feature.allowColumnDefaults' = 'supported')` — required for `DEFAULT` column values on serverless warehouses
- `UNIQUE` constraints are removed (requires `spark.databricks.sql.dsv2.unique.enabled`, a warehouse-level flag not available on serverless)
- `VARIANT` in `cohort_member.qualifying_evidence` requires DBR 15.3+; replace with `STRING` on older runtimes

### 2. Generate synthetic data

The workspace is connected to this Git repo — sync from `main` to pick up the latest notebooks.

```
1. sample_clinical_notes.py     run first (defines NOTES_LIBRARY)
2. generate_ehr_silver.py       run second (generates + writes all 7 tables)
```

In `generate_ehr_silver.py` Section 5, optionally uncomment to use the full note library:
```python
%run ./sample_clinical_notes
```

Expected output at 500 patients:

| Table | ~Rows |
|---|---|
| patient | 500 |
| encounter | 2,500 |
| condition | 7,500 |
| observation | 12,500 |
| medication_order | 5,000 |
| procedure | 5,000 |
| clinical_note | 2,500 |

The built-in validation query confirms the primary demo cohort:
```sql
-- T2DM + metformin + CVD in last 2 years → should return ~50 patients
```

### 3. Deploy the Streamlit app

The `app/` folder deploys as a **Databricks App**. The workspace Git integration means any push to `main` can be synced without re-uploading files.

**Environment variables to set in the App configuration:**

| Variable | Required | Notes |
|---|---|---|
| `DATABRICKS_HTTP_PATH` | Yes | SQL warehouse HTTP path |
| `DATABRICKS_TOKEN` | Dev only | Personal Access Token |
| `DATABRICKS_CLIENT_ID` | Production | Service Principal client ID |
| `DATABRICKS_CLIENT_SECRET` | Production | Service Principal client secret |

`DATABRICKS_HOST` is injected automatically by the Databricks Apps runtime.

`db.py` tries SP OAuth first, falls back to PAT — no code change needed when switching from dev to production credentials.

---

## DDL conventions

- **Surrogate keys**: `BIGINT GENERATED BY DEFAULT AS IDENTITY` — explicit values can be inserted by the generator
- **Coding pattern**: every clinical code stored as a `(*_code, *_system, *_display)` trio — no separate vocabulary reference tables required for the POC
- **Constraints**: `PRIMARY KEY` / `FOREIGN KEY` are `NOT ENFORCED RELY` — informational only; they document intent and let the Databricks optimizer use them without blocking writes
- **Clustering**: `CLUSTER BY` (liquid clustering) instead of static partitioning
- **No Bronze layer**: synthetic data loads directly to silver; FHIR/Clarity source integration is documented in [`docs/ehr-source-schemas.md`](docs/ehr-source-schemas.md) for future real-data phases

---

## Roadmap

- [ ] NLP extraction pipeline (Spark NLP or Claude API) → populate `note_nlp_entity`
- [ ] Genie Space configuration over `test_silver_ehr_clinical` with sample queries
- [ ] `patient_feature` assembly notebook (HbA1c trend, encounter utilization, NLP finding count)
- [ ] Scale to 5,000 patients (`N_PATIENTS = 5000` in generator)
- [ ] Real-data integration path: FHIR R4 → silver conformance layer
- [ ] Risk scoring notebook (HCC, cardiovascular risk) → `patient_feature`
