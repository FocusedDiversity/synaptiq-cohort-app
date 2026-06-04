# EHR Source Database Schemas for NLP Patient Cohort Building

> Epic Clarity & athenahealth (athenaNet/athenaOne). Synaptiq — Data Architecture.

A senior-data-architect reference for extracting source clinical data from the two
target EHRs — **Epic** (via the **Clarity** reporting database) and **athenahealth**
(via API / managed analytics products) — to feed an NLP-based patient-cohort pipeline.

> **Scope & accuracy note.** Epic's full Clarity/Caboodle data dictionaries and
> athenahealth's DataView/Data-Warehouse-Feed schemas are **proprietary and behind
> customer login** — neither vendor publishes a complete public schema. Table and
> column names below are drawn from public/semi-public sources (Epic's ONC EHI
> Export Specification, university OMOP/i2b2 ETL projects, athenahealth's developer
> portal and FHIR Implementation Guide). **Always verify exact names against the
> live data dictionary of the specific customer instance** before building ETL —
> available tables vary by licensed modules and local configuration. Items we could
> not fully confirm are flagged inline with ⚠️.

---

## 0. The architectural contrast (read this first)

The two systems sit at opposite ends of the data-access spectrum, and this dictates
the entire integration strategy:

| | **Epic** | **athenahealth** |
|---|---|---|
| Deployment | On-premises / customer-hosted (or Epic-hosted) | Cloud SaaS, multi-tenant |
| Primary analytics surface | **Clarity** — relational copy (Oracle / SQL Server) of the live Chronicles DB, **direct SQL** | **No direct production DB**; API-first |
| "Closest to a queryable DB" | Clarity (and newer **Caboodle** dimensional warehouse) | **DataView** (managed Snowflake) and **Data Warehouse Feed** (daily flat files) |
| Standardized API | Epic on FHIR (R4) | ONC-certified FHIR R4 + Bulk `$export` |
| Raw schema published? | No (EHI Export Spec is the only public slice) | No (DataView/feed schemas delivered under contract) |
| Free-text for NLP | `HNO_*` note tables + order result narratives (line-wrapped rows) | `DocumentReference` + `Binary` attachments (PDF/RTF/HTML/scanned-image) |

**Takeaway:** For Epic you design a **SQL ETL against Clarity**. For athenahealth you
design an **API/Bulk-FHIR harvester** (optionally backed by DataView SQL for structured
domains). The unstructured-text strategy differs the most: Epic gives you line-wrapped
text rows to concatenate; athena gives you documents to fetch, decode, and frequently
**OCR**.

---

# Part I — Epic Clarity

## How Epic data is structured

- **Two databases.** Epic runs **Chronicles** (the live hierarchical MUMPS "M"
  database — the actual EHR) and **Clarity** (a relational copy on **Oracle or
  Microsoft SQL Server**) refreshed by a nightly ETL. You query Clarity, never
  Chronicles directly.
- **The `LINE` pattern.** Chronicles multi-valued fields become child rows in Clarity,
  keyed by a parent ID + a `LINE` integer (starts at 1, increments). This appears in
  ~275 tables and is **the** mechanism for note text, lab components, and encounter
  diagnoses. To rebuild an ordered value (a note body), concatenate child rows
  **ordered by `LINE`**.
- **Naming conventions:** `_C` = category code (numeric → resolve via a `ZC_*` table);
  `_YN` = Y/N/null flag; `_ID` = foreign key; `*_REAL` dates are **days since
  1840-12-31** (MUMPS internal), while `CONTACT_DATE`/`*_TIME` are normal datetimes.
- **Key identifiers:**
  - `PAT_ID` — Epic internal patient ID (never shown to users, stable for life)
  - `PAT_MRN_ID` — the human-visible MRN (can be facility-specific)
  - `PAT_ENC_CSN_ID` — **Contact Serial Number**, the universal encounter key (unique
    across all patients/encounters)
  - `HSP_ACCOUNT_ID` (HAR) — hospital billing account; multiple encounters can share one

> The public **EHI Export Specification** (open.epic.com/EHITables) renames some
> foreign-key columns with a `_NAME` suffix (e.g. `MEDICATION_ID_MEDICATION_NAME`) by
> pre-joining the master table. In native Clarity these are just `MEDICATION_ID`, etc.

## 1. Patient Demographics

| Table | Key columns | Notes |
|---|---|---|
| **PATIENT** | `PAT_ID` (PK), `PAT_NAME`, `BIRTH_DATE`, `SEX_C`, `PAT_MRN_ID`, `ADD_LINE_1/2`, `CITY`, `ZIP`, `MARITAL_STATUS_C` | Master demographics, one row per patient |
| **PATIENT_2 / _3 / _4** | extend `PATIENT` via `PAT_ID` | Chronicles overflow tables — columns that don't fit the master spill into numbered siblings |
| **PATIENT_RACE** | `PAT_ID`, `LINE`, `PATIENT_RACE_C` | One row per race (patients may have multiple) |
| **IDENTITY_ID** | `PAT_ID`, `IDENTITY_TYPE_ID`, `IDENTITY_ID` | Holds **all** identifiers (MRN, enterprise EPI, etc.), one per type — critical when an org has multiple MRN types |

Codes resolve via `ZC_SEX`, `ZC_MARITAL_STATUS`, `ZC_PATIENT_RACE`.

## 2. Encounters / Visits

| Table | Key columns | Notes |
|---|---|---|
| **PAT_ENC** | `PAT_ENC_CSN_ID` (PK), `PAT_ID`, `CONTACT_DATE`, `PAT_ENC_DATE_REAL`, `ENC_TYPE_C`, `DEPARTMENT_ID`, `VISIT_PROV_ID`, `APPT_STATUS_C`, `EFFECTIVE_DATE_DTTM`, `ENC_CLOSED_YN` | One row per encounter (visits, telephone, appts). `PAT_ENC_DATE_REAL` distinguishes same-day contacts |
| **PAT_ENC_HSP** | `PAT_ENC_CSN_ID` (PK), `HOSP_ADMSN_TIME`, `HOSP_DISCH_TIME`, `ADT_PAT_CLASS_C`, `ADMIT_SOURCE_C`, `DISCH_DISP_C`, `ADT_ARRIVAL_TIME`, `EXP_LEN_OF_STAY` | Inpatient/ED detail via ADT; LOS = discharge − admission |
| **HSP_ACCOUNT** | `HSP_ACCOUNT_ID` (PK = HAR), `FINAL_DRG_ID`, `ACCT_CLASS_HA_C`, `ADM_DATE_TIME`, `DISCH_DATE_TIME`, `PRIM_PAYOR_ID` | Hospital billing account; episode-level; DRG in `FINAL_DRG_ID` |
| **CLARITY_ADT** | `PAT_ENC_CSN_ID`, `EVENT_ID`, `EVENT_TYPE_C`, `EVENT_TIME`, `PAT_CLASS_C`, `DEPARTMENT_ID`, `ROOM_ID`, `BED_ID` | ADT event log — admit/discharge/transfer audit trail; best source for movement & bed history |

Codes via `ZC_DISP_ENC_TYPE`, `ZC_PAT_CLASS`, `ZC_DISCH_DISP`.

## 3. Clinical Notes — ⭐ CRITICAL for NLP

Epic stores notes as **metadata + line-wrapped text** across several tables:

| Table | Key columns | Notes |
|---|---|---|
| **HNO_INFO** | `NOTE_ID` (PK), `IP_NOTE_TYPE_C`, `NOTE_TYPE_NOADD_C`, `PAT_ENC_CSN_ID`, `ENTRY_USER_ID`, `DATE_OF_SERVIC_DTTM`, `LST_FILED_INST_DTTM`, `UNSIGNED_YN` | **Note metadata**, one row per note. `IP_NOTE_TYPE_C` = clinical type: Progress Note, Consult, **Discharge Summary**, H&P, etc. |
| **HNO_NOTE_TEXT** ⚠️ | `NOTE_ID`, `LINE`, `NOTE_CSN_ID`, `NOTE_TEXT` | **The actual note body**, one wrapped line per row. Full note = concatenate `NOTE_TEXT` **ordered by `LINE`** (`STRING_AGG(... ) WITHIN GROUP (ORDER BY LINE)` on SQL Server, `LISTAGG` on Oracle). ⚠️ Column spelling confirmed via JHM OMOP ETL docs but verify in-instance |
| **NOTE_ENC_INFO** | `NOTE_ID`, `NOTE_CSN_ID`, `CONTACT_DATE`, `NOTE_STATUS_C`, `AUTHOR_USER_ID`, `AUTHOR_LINKED_PROV_ID` | Per-**contact/version** info — addenda, signing status, author per revision. Join for the signed/final version |

**Where specific report types live:**

- **Discharge summaries, progress notes, H&P, consults** → all in `HNO_INFO`/`HNO_NOTE_TEXT`, filtered by `IP_NOTE_TYPE_C`.
- **Pathology / radiology / micro narrative reports** → **not** in `HNO`. They arrive as
  **result text on the order**: `ORDER_PROC` → result components, with narrative in
  `ORDER_RES_COMMENT` / `ORDER_NARRATIVE` ⚠️ (exact table name varies) and short values
  in `ORDER_RESULTS.ORD_VALUE`. Long narratives are line-wrapped, keyed by
  `(ORDER_PROC_ID, LINE)` — concatenate by `LINE`.

> **NLP storage rule:** *every* long free-text field in Clarity is line-wrapped into
> child rows and must be reassembled `ORDER BY LINE`. Make that a core utility in the
> pipeline — it applies uniformly to notes, result comments, and order narratives.

## 4. Diagnoses (ICD-10)

| Table | Key columns | Notes |
|---|---|---|
| **PAT_ENC_DX** | `PAT_ENC_CSN_ID`, `LINE` (PK), `CONTACT_DATE`, `DX_ID`, `PRIMARY_DX_YN`, `DX_CHRONIC_YN`, `DX_LINK_PROB_ID` | Encounter diagnoses. `DX_ID` is Epic's **internal** dx ID (not ICD directly) |
| **PROBLEM_LIST** | `PROBLEM_LIST_ID` (PK), `PAT_ID`, `DX_ID`, `NOTED_DATE`, `RESOLVED_DATE`, `PROBLEM_STATUS_C`, `PRIORITY_C`, `CHRONIC_YN` | Longitudinal problem list; deleted problems remain (status Active/Resolved/Deleted) |
| **CLARITY_EDG** | `DX_ID` (PK), `DX_NAME`, `CURRENT_ICD9_LIST`, `CURRENT_ICD10_LIST` | **Diagnosis master.** ICD fields are **comma-separated lists** — one `DX_ID` → multiple codes |
| **EDG_CURRENT_ICD10** | `DX_ID`, `LINE`, `ICD10_CODE` | Normalized child table: current ICD-10 per `DX_ID`, one code/row. Prefer this over parsing the CSV |
| **HSP_ACCT_DX_LIST** | `HSP_ACCOUNT_ID`, `LINE`, `DX_ID`, `FINAL_ICD10_CODES`, `DX_QUALIFIER_C` | **Billing/coded** (HIM-abstracted) dx for claims — distinct from clinician-entered `PAT_ENC_DX` |

> **Cohort caveat:** `DX_ID` ↔ ICD is many-to-many, so joining
> `PAT_ENC_DX`→`EDG_CURRENT_ICD10` can **duplicate** rows. The OHDSI community
> explicitly warns about CONDITION_OCCURRENCE duplication here.

## 5. Medications

| Table | Key columns | Notes |
|---|---|---|
| **ORDER_MED** | `ORDER_MED_ID` (PK), `PAT_ID`, `PAT_ENC_CSN_ID`, `MEDICATION_ID`, `ORDER_START_TIME`, `ORDER_END_TIME`, `SIG`, `HV_DISCRETE_DOSE`, `HV_DOSE_UNIT_C`, `MED_ROUTE_C`, `ORDER_STATUS_C`, `MED_PRESC_PROV_ID`, `ORDER_CLASS_C` | Medication **orders/prescriptions**; `ORDER_CLASS_C` separates inpatient vs outpatient |
| **MAR_ADMIN_INFO** | `ORDER_MED_ID`, `LINE`, `TAKEN_TIME`, `SCHEDULED_TIME`, `MAR_ACTION_C` (Given/Held/Refused), `SIG`, `DOSE_UNIT_C`, `INFUSION_RATE`, `MAR_ADMIN_BY_USER_ID` | **MAR** — what was *actually administered* (inpatient). Essential for true drug exposure vs merely ordered |
| **CLARITY_MEDICATION** | `MEDICATION_ID` (PK), `NAME`, `GENERIC_NAME`, `STRENGTH`, `FORM`, `ROUTE`, `GENERIC_CAI_ID` | **Medication master** |
| **RXNORM_CODES / RX_MED_GCNSEQNO / clarity_ndc_codes** ⚠️ | `MEDICATION_ID`/`GCN_SEQ_NO` → `RXNORM_CODE` / `NDC` | Crosswalks to RxNorm/NDC/GPI/GCN — RxNorm is usually reached via these, not a single column on `CLARITY_MEDICATION` |

## 6. Lab Results

| Table | Key columns | Notes |
|---|---|---|
| **ORDER_PROC** | `ORDER_PROC_ID` (PK), `PAT_ID`, `PAT_ENC_CSN_ID`, `PROC_ID`, `ORDER_TYPE_C`, `ORDER_STATUS_C`, `RESULT_LAB_ID`, `ORDER_TIME`, `RESULT_TIME`, `SPECIMN_TAKEN_TIME` | Order header (labs, imaging, procedures share this table) |
| **ORDER_RESULTS** | `ORDER_PROC_ID`, `LINE` (PK), `COMPONENT_ID`, `ORD_VALUE`, `ORD_NUM_VALUE`, `REFERENCE_LOW`, `REFERENCE_HIGH`, `REFERENCE_UNIT`, `RESULT_FLAG_C`, `RESULT_DATE`, `COMPONENT_COMMENT` | **Discrete results**, one row per component. `ORD_VALUE` = short text; `ORD_NUM_VALUE` = numeric (sentinel `9999999` if non-numeric); `RESULT_FLAG_C` = High/Low/Panic/Abnormal |
| **CLARITY_COMPONENT** | `COMPONENT_ID` (PK), `NAME`, `COMMON_NAME`, `BASE_NAME`, `DEFAULT_LNC_ID` (→ LOINC), `LOINC_CODE` | **Lab component master.** `DEFAULT_LNC_ID` not always populated → many components lack LOINC (known gap) |
| **LNC_DB_MAIN** | `LNC_ID`, `LOINC_CODE`, … | LOINC master; join `CLARITY_COMPONENT.DEFAULT_LNC_ID` → here |

Microbiology/pathology narrative text on a result lives in the result-comment/narrative
child tables noted in §3.

## 7. Procedures (CPT/HCPCS)

| Table | Key columns | Notes |
|---|---|---|
| **ORDER_PROC** | (as above) + `PROC_ID` | Clinical procedure orders; `PROC_ID` → `CLARITY_EAP` |
| **CLARITY_EAP** | `PROC_ID` (PK), `PROC_NAME`, `PROC_CODE` (the **CPT/HCPCS**), `PROC_CAT_ID`, `RVU` | **Procedure master**; CPT lives in `PROC_CODE` |
| **ARPB_TRANSACTIONS** | `TX_ID`, `PAT_ID`, `ACCOUNT_ID`, `PROC_ID`, `CPT_CODE`, `SERVICE_DATE`, `MODIFIER_*` | **Professional billing** — authoritative CPT-coded billed procedures (with modifiers) |
| **HSP_ACCT_PX_LIST / HSP_ACCT_CPT_CODES** ⚠️ | `HSP_ACCOUNT_ID`, `LINE`, `PROC_ID`/`CPT_CODE`, `PROC_PERF_DATE` | Hospital-account coded procedures (HIM-abstracted, facility billing) |
| **OR_LOG / OR_LOG_ALL_PROC / OR_CASE** | `LOG_ID`, `PAT_ID`, `OR_PROC_ID`, surgical times | OpTime surgical/OR case tables for operative procedures |

OHDSI guidance: pull CPT from billing (`ARPB`/`HSP_ACCT`) + `CLARITY_EAP.PROC_CODE`.

## 8. Vital Signs (Flowsheets)

| Table | Key columns | Notes |
|---|---|---|
| **IP_FLWSHT_REC** | `FSD_ID` (PK), `INPATIENT_DATA_ID`, `PAT_ENC_CSN_ID` | One flowsheet record per encounter; encounter → flowsheet link |
| **IP_FLWSHT_MEAS** | `FSD_ID`, `LINE` (PK), `FLO_MEAS_ID`, `MEAS_VALUE` ⚠️, `RECORDED_TIME`, `ENTRY_TIME`, `MEAS_COMMENT`, `TAKEN_USER_ID` | **The measurements** — EAV table, one row per cell. `MEAS_VALUE` holds the value ("120/80", "72", "98.6") |
| **IP_FLO_GP_DATA** | `FLO_MEAS_ID`, `FLO_MEAS_NAME`, `DISP_NAME`, `FLO_GROUP_ID`, `VALUE_TYPE_C` | Maps a measurement ID → its name (BP, Pulse, Weight, Height) |
| **FLO_GROUP / FLT_TEMPLATE** | flowsheet group/template defs | `FLO_GROUP_ID` groups related rows (e.g. all vitals under one header) |

**Vitals pattern:** each vital is a `FLO_MEAS_ID` row in `IP_FLWSHT_MEAS`. Filter by the
target `FLO_MEAS_ID`s, read `MEAS_VALUE` + `RECORDED_TIME`. **BP is one "120/80" string
needing parsing.**

## Epic — Integration & Access Methods

- **Direct Clarity DB access** — SQL against Oracle / SQL Server. Resolve category
  codes via `ZC_*`, master files via `CLARITY_*`. Best for bulk analytics / cohort
  building.
- **Caboodle** (Cogito enterprise data warehouse) — newer **dimensional star schema**
  (`*Fact` / `*Dim`), flatter and faster than Clarity. Confirmed names: **PatientDim**,
  **EncounterFact**, **LabComponentResultFact** (EAV). Likely analogs (verify ⚠️):
  `DiagnosisEventFact`, `MedicationOrderFact`/`MedicationAdministrationFact`,
  `ProcedureFact`, note-text fact, `DepartmentDim`, `ProviderDim`, `DateDim`. Uses a
  **durable key** so all SCD versions of a patient share one key. Can ingest non-Epic
  data (Clarity is Epic-only).
- **Epic on FHIR (R4)** — register at **fhir.epic.com** for a client ID; sandbox test
  patients available. Resource → domain map:
  - `Patient` → PATIENT/IDENTITY_ID
  - `Encounter` → PAT_ENC / PAT_ENC_HSP
  - `Condition` → PAT_ENC_DX / PROBLEM_LIST
  - `Observation[laboratory]` → ORDER_RESULTS; `Observation[vital-signs]` → flowsheets
  - `MedicationRequest` → ORDER_MED; `MedicationAdministration` → MAR_ADMIN_INFO
  - `Procedure` → ORDER_PROC / billing
  - **`DocumentReference` + `Binary`** → **clinical notes** (HNO) — DocumentReference =
    metadata, Binary = the note content. This is the FHIR path to unstructured text.
- **HL7 v2 interfaces** — ADT (A01/A03…), ORM/ORU (orders/results), MDM (documents)
  via Bridges/Interconnect for real-time integration.

## Epic — Licensing / Access / PHI

- **No public schema.** The full Clarity Data Dictionary, **Clarity Compass**, and
  **Caboodle** dictionary are behind **UserWeb** login and require an active Epic
  customer relationship. The only public slice is the **EHI Export Specification**
  (open.epic.com/EHITables), published for ONC/Cures compliance.
- **Training/certification** typically expected: **Clarity Data Model** (CLR2xx),
  **Cogito/Caboodle Fundamentals (CDW110)**, plus SQL.
- **Access provisioning** via your org's Epic team / **Data Courier**; analyst
  credentials on UserWeb for the dictionary.
- **PHI/HIPAA** — Clarity/Caboodle are full of PHI; access is role-restricted,
  IRB-governed for research. Note free text frequently contains identifiers → NLP on
  notes is especially sensitive. De-identified research extracts (Stanford **STARR**,
  Mount Sinai **MSDW**) are the usual research vehicle.
- **Table availability varies by org** — depends on licensed modules and local config.

---

# Part II — athenahealth (athenaNet / athenaOne)

## The core difference: API-first, not database-first

athenahealth is a **cloud, multi-tenant SaaS EHR**. Customers do **not** receive a copy
of the production OLTP database, there is **no published raw schema**, and there is **no
general-purpose SQL connection to the live system.** Data is exposed through five
channels:

| Channel | Nature | Best for |
|---|---|---|
| **athenaNet REST API** (`api.platform.athenahealth.com/v1/{practiceid}/...`) | 800+ transactional JSON endpoints, real-time, write-capable | Workflow integration, targeted chart pulls, document text |
| **FHIR R4 API** (`api.platform.athenahealth.com/fhir/r4`) | ONC-certified, USCDI, read/search + **Bulk `$export`** | Standardized cohort extraction, population-scale pulls |
| **DataView** (Snowflake-backed) ⚠️ | Managed near-copy analytic DB; browser SQL + ODBC/BI; daily data, ~monthly schema | The closest "Clarity-style" SQL analytics |
| **Data Warehouse Feed** ⚠️ | Daily flat files to FTP/SFTP (initial full load + daily deltas) | Traditional ETL into your own warehouse |
| **EHI / C-CDA Export** | Cures-Act self-service bulk export (FHIR NDJSON + custom resources; or C-CDA docs) | Compliance-driven full-record export |

> Honest answer to "is there direct DB/SQL access?": **not to the live production
> database — but DataView (managed Snowflake) and the Data Warehouse Feed are
> data-at-rest analytics products.** DataView is the realistic Clarity substitute for
> structured domains; supplement with API/Bulk-FHIR for free-text documents. ⚠️
> **DataView / feed table names are not public** (delivered under contract) — confirm
> specific clinical table names with the athenahealth account team.

## Access methods in detail

### athenaNet REST API
- **Host:** `https://api.platform.athenahealth.com` (legacy `api.athenahealth.com/v1`).
  Most endpoints are **practice-scoped** (`{practiceid}` in path); **`departmentid`** is
  required/recommended on scheduling & clinical workflows.
- **Auth:** **OAuth 2.0** — `client_credentials` (B2B server-to-server) and
  `authorization_code` (patient/user-facing). Token: `POST /oauth2/v1/token` with HTTP
  Basic (client_id/secret); Bearer token thereafter. Access gated by **service scopes**.
- **Rate limits:** HTTP **429** on exceed; per-app limits not public — plan backoff.

### FHIR R4 API (USCDI + Bulk Data)
- **ONC-certified USCDI FHIR R4 Read & Search** (Cures Act §170.315(g)(10)) — the
  regulatory floor every athenaOne customer can invoke.
- **Per-environment base URLs** (Preview + Production); `fhir.athena.io` hosts the
  "Athena Core" IG; patient-access surfaced at `mydata.athenahealth.com`.
- **Auth:** SMART on FHIR + OAuth 2.0, TLS 1.2.
- **Bulk Data `$export`** (added in the 22.7 release) → async kickoff/poll/download of
  **NDJSON** per resource. The population-scale path.

### DataView (Snowflake) — closest to Clarity
- Managed **Snowflake** DB; access via browser SQL editor, **ODBC**, or BI/ETL tools
  (Tableau, Power BI). **Daily data refresh; ~monthly schema updates** (auto-added
  tables/columns). The natural home for SQL cohort building — except bulky free-text
  notes, which are better pulled via API/FHIR.

### Data Warehouse Feed — flat-file ETL
- Initial full historical load + **daily delta flat files** to **FTP/SFTP**, loaded into
  your own RDBMS. Static schema (changes need a formal upgrade project).

### EHI & C-CDA Export (Cures-Act self-service)
- **EHI Export** — self-service EHI export via FHIR Bulk Data → **NDJSON**, combining
  standard FHIR R4 resources **and** athenahealth **custom (non-FHIR) billing resources**
  (Adjustment, BillingStatement, Charge, Claim, Collection, Deductible, Eligibility,
  PatientInsurance, Payment).
- **C-CDA Export** — CCD patient summaries (C-CDA 2.1 / CDA R2); human-readable
  longitudinal narrative.

### Developer program & Marketplace ("More Disruption Please")
- Partner ecosystem = the **Marketplace** (MDP), 800+ solutions. Free **sandbox/Preview**
  credentials at **developer.athenahealth.com** (synthetic data). **Production** access
  requires Marketplace partner onboarding (BAA / data-use review, reportedly ~6–12 weeks).

## FHIR R4 resource catalog (athenahealth IG v25.0.0)

- **Clinical:** AllergyIntolerance, Binary, CarePlan, CareTeam, ClinicalImpression,
  **Condition**, Consent, Device, **DiagnosticReport**, **DocumentReference**,
  **Encounter**, FamilyMemberHistory, Goal, Immunization, Media,
  MedicationAdministration, MedicationDispense, **MedicationRequest**,
  **MedicationStatement**, **Observation**, **Procedure**, ServiceRequest, Specimen
- **Practice management:** Account, **Appointment**, Coverage, **Patient**, Posting,
  RelatedPerson, Schedule, Slot
- **System:** AuditEvent, ConceptMap, CapabilityStatement, Endpoint, List, Location,
  **Medication**, NamingSystem, OperationDefinition, Organization, **Practitioner**,
  PractitionerRole, Provenance, Subscription, ValueSet
- **Custom (billing):** Adjustment, BillingStatement, Charge, Claim, Collection,
  Deductible, Eligibility, PatientInsurance, Payment

## The 8 clinical domains

> Proprietary REST paths shown as `/v1/{practiceid}/...` (prefix implicit). ⚠️ The docs
> portal is JS-rendered/not reliably scrapeable — verify exact sub-path spelling in-portal.

### 1. Patient Demographics
- **REST:** `GET /patients` (best-match search), `GET /patients/{patientid}`, `POST`,
  `PUT /patients/{patientid}`.
- **FHIR:** **`Patient`** (US Core) — search by name/birthdate/identifier.
- **Identifiers (critical):** primary key is **`patientid`**, **practice-scoped** (local
  to a `practiceid`) — *not* a global ID. An **Enterprise ID** links a patient across
  departments/practices. **MRN and insurance member ID are typically custom fields**, not
  first-class identifiers — important for mapping. In FHIR they surface in
  `Patient.identifier[]`.

### 2. Encounters / Visits
- **Conceptual split: Appointment ≠ Encounter.** Appointment = the scheduling object;
  Encounter = the clinical visit/documentation context created at check-in. Cohort logic
  needing "actual visits" should use Encounter (or checked-in/out appointments), not raw
  bookings.
- **REST:** `/appointments` (book/search/cancel), Appointment Check-In, `/encounter` /
  **Encounter Services** / **Encounter Service Notes**, **Encounter Chart**. `departmentid`
  central.
- **FHIR:** **`Encounter`** (class, type, status, period, participant, location,
  reasonCode); **`Appointment`**, **`Schedule`/`Slot`** for scheduling.

### 3. Clinical Notes / Unstructured Text — ⭐ CRITICAL for NLP
Free text lives in **two main places**:

**(a) `DocumentReference` + `Binary` (the main vehicle).**
`DocumentReference` indexes clinical documents — notes, encounter documents, discharge
summaries, pathology/imaging reports, scanned faxes, referral letters. Content sits in
`DocumentReference.content.attachment` as either **inline base64** (`attachment.data`) or
a **URL** (`attachment.url`) to a **`Binary`** resource. `attachment.contentType` is the
format — commonly **application/pdf, text/html, text/rtf, text/plain, or scanned
TIFF/JPEG**. **Expect a heavy mix of PDF and scanned faxed images → your NLP pipeline
needs OCR** for a meaningful fraction, not just text parsing.

**(b) Proprietary document & encounter-note endpoints.**
REST document model with classes/types (**Clinical Document**, **Encounter Document**,
Patient Case, Medical Record) + a **Document Classification** workflow. Encounter
narrative via **Encounter Service Notes** / **Encounter Chart**, sometimes as
**HTML-formatted** note bodies.

> **Practical NLP guidance:** For population-scale harvesting, **Bulk `$export`** the
> `DocumentReference` resources, resolve each `Binary`/attachment, then branch on
> `contentType` (text/HTML parse vs PDF extract vs image→OCR). Use C-CDA export as a
> structured-narrative complement. **Do not expect a clean "notes" table in DataView** —
> the bulky text bodies live behind DocumentReference/Binary.

### 4. Diagnoses (ICD-10)
- **REST:** `GET /chart/{patientid}/problems` → problem-list entries with **ICD-10 +
  SNOMED CT**. Encounter diagnoses (visit/claim-attached) are distinct from the
  longitudinal problem list.
- **FHIR:** **`Condition`** (US Core) — `category` separates `problem-list-item` vs
  `encounter-diagnosis`; `code` carries ICD-10-CM/SNOMED; `clinicalStatus`/
  `verificationStatus` for active/resolved.

### 5. Medications
- **REST:** `GET /chart/{patientid}/medications` — name, dose, route, frequency,
  prescriber, pharmacy. e-Prescribing over **Surescripts**.
- **FHIR:** **`MedicationRequest`** (orders/prescriptions) + **`MedicationStatement`**
  (reported use), plus `MedicationDispense`, `MedicationAdministration`, `Medication`.
  Coding via **RxNorm / NDC** in `medicationCodeableConcept`.

### 6. Lab Results
- **REST:** `GET /chart/{patientid}/labresults` and `.../labresults/{orderid}` — values,
  **reference ranges, abnormal flags**, units. Orders separate from results.
- **FHIR:** **`Observation[laboratory]`** (value, unit, referenceRange, interpretation,
  **LOINC** in `code`) + **`DiagnosticReport`** to group a panel (with `result[]` and
  possibly a `presentedForm` attachment for the full report). **`ServiceRequest`** = the
  order; **`Specimen`** = the sample.

### 7. Procedures (CPT/HCPCS)
- **REST:** surgical history / procedures via chart and encounter endpoints; **CPT/HCPCS**
  primarily on the **billing/charge** side.
- **FHIR:** **`Procedure`** (US Core) — `code` = **CPT/HCPCS/SNOMED**,
  `performedDateTime/Period`, status. **Clinical vs billed procedures can diverge** — for
  a complete cohort you may need `Procedure` *and* the custom **Charge/Claim** resources
  (via EHI export).

### 8. Vital Signs
- **REST:** `GET /chart/{patientid}/vitals` — date, values, units.
- **FHIR:** **`Observation[vital-signs]`** — height, weight, BMI, BP
  (systolic/diastolic as `component`s), HR, RR, temp, SpO2 (US Core vital-signs LOINC
  profiles).

## athenahealth — domain → channel quick map

| Domain | Proprietary REST | FHIR R4 | Notes |
|---|---|---|---|
| Demographics | `/patients`, `/patients/{id}` | `Patient` | patientid is practice-scoped; MRN often a custom field |
| Encounters/Visits | `/appointments`, `/encounter`, check-in | `Encounter`, `Appointment`, `Schedule`/`Slot` | Appointment ≠ Encounter |
| **Clinical Notes** | Clinical/Encounter Documents, Encounter Service Notes, Doc Classification | **`DocumentReference` + `Binary`** | **Free text here; PDF/RTF/HTML/base64; OCR often needed** |
| Diagnoses | `/chart/{id}/problems` | `Condition` | ICD-10 + SNOMED; problem-list vs encounter-dx |
| Medications | `/chart/{id}/medications` | `MedicationRequest`/`MedicationStatement` | RxNorm/NDC; Surescripts |
| Lab Results | `/chart/{id}/labresults[/{orderid}]` | `Observation[laboratory]`, `DiagnosticReport` | LOINC, ref ranges, abnormal flags |
| Procedures | chart/encounter procedures | `Procedure` (+ Charge/Claim custom) | CPT/HCPCS; clinical vs billed |
| Vital Signs | `/chart/{id}/vitals` | `Observation[vital-signs]` | BP as components |

## athenahealth — Licensing / Access / Compliance

- **Must be a customer or approved Marketplace partner.** No anonymous/public production
  access. Production credentials via **Marketplace onboarding** (data-use review, ~weeks).
- **OAuth 2.0** credentials per app; **service scopes** gate endpoints;
  `practiceid`/`departmentid` scope the data.
- **HIPAA / BAA** executed with the covered entity before PHI exchange.
- **No raw schema published.** REST docs are field-level/JS-rendered;
  **DataView/Data-Warehouse-Feed schemas are contract-delivered, not public** — verify
  table names with the account team.
- **ONC / USCDI mandate** guarantees a standardized, certified FHIR R4 + Bulk `$export`
  path independent of the proprietary API — good news for portability.
- **Rate limits** enforced (HTTP 429) but not publicly quantified — budget for backoff /
  limit-increase requests.

---

# Part III — Recommended NLP cohort-building architecture

**Structured cohort attributes (dx, meds, labs, vitals, procedures, demographics,
encounters):**
- *Epic* → SQL ETL against **Clarity** (or Caboodle facts/dims): `PAT_ENC_DX`/
  `PROBLEM_LIST`→`EDG_CURRENT_ICD10`, `ORDER_MED`/`MAR_ADMIN_INFO`→`CLARITY_MEDICATION`,
  `ORDER_RESULTS`→`CLARITY_COMPONENT`/LOINC, `ORDER_PROC`/`ARPB_TRANSACTIONS`→`CLARITY_EAP`,
  `IP_FLWSHT_MEAS`→`IP_FLO_GP_DATA`.
- *athenahealth* → **DataView (Snowflake SQL)** if licensed, else **FHIR Bulk `$export`**
  (NDJSON) of `Condition`, `MedicationRequest`, `Observation`, `Procedure`, `Patient`,
  `Encounter`.

**Unstructured text for NLP:**
- *Epic* → `HNO_INFO` + `HNO_NOTE_TEXT` (concatenate by `LINE`) for notes; order
  result comments/narratives on `ORDER_PROC`/`ORDER_RESULTS` for path/rad reports (also
  line-wrapped). Via FHIR: `DocumentReference` + `Binary`.
- *athenahealth* → enumerate `DocumentReference` (Bulk `$export`/search), resolve
  `Binary`/attachments, branch on `contentType` → text/HTML parse, PDF extract, or **OCR**
  for scanned/faxed images. C-CDA export as a structured-narrative complement.

**Cross-cutting:**
- **Identity resolution.** Epic: `PAT_ID` ↔ `PAT_MRN_ID` via `IDENTITY_ID`. athena:
  practice-scoped `patientid` + Enterprise ID; treat **MRN as a custom field**.
- **Free-text reassembly (Epic).** Build a reusable `ORDER BY LINE` concatenation utility
  — it applies uniformly to notes, result comments, and order narratives.
- **De-duplication (Epic).** Guard against `DX_ID`↔ICD many-to-many row duplication.
- **Compliance.** Operate under the customer **BAA**; scope credentials minimally; log
  access (Epic audit / athena `AuditEvent`/`Provenance`). Free text frequently contains
  PHI identifiers → de-identify before/within the NLP layer.

---

# Accuracy flags (verify against the live instance)

**Epic Clarity**

1. `IP_FLWSHT_MEAS.MEAS_VALUE` — standard value column but absent from the EHI render;
   confirm.
2. `HNO_NOTE_TEXT` columns (`NOTE_TEXT`, `LINE`, `NOTE_CSN_ID`) — documented in JHM's
   OMOP ETL but page not fully rendered; confirm exact names.
3. Pathology/radiology narrative table — commonly `ORDER_RES_COMMENT`/`ORDER_NARRATIVE`
   keyed by `(ORDER_PROC_ID, LINE)`; exact name varies.
4. `CLARITY_MEDICATION` RxNorm — usually via crosswalks (`RXNORM_CODES`,
   `RX_MED_GCNSEQNO`), not a single column.
5. Caboodle fact/dim names beyond `PatientDim`/`EncounterFact`/`LabComponentResultFact` —
   inferred from convention.
6. `HSP_ACCT_PX_LIST`/`HSP_ACCT_CPT_CODES` exact names — verify.

**athenahealth**

1. **DataView / Data Warehouse Feed table-level schemas are not public** — delivered
   under contract; confirm specific clinical table names with the account team.
2. The docs portal is JS-rendered — a few proprietary REST sub-paths are reconstructed
   from secondary sources; verify in-portal.

---

# Sources

**Epic**

- Epic EHI Export Spec (authoritative public schema): <https://open.epic.com/EHITables/GetTable/PAT_ENC.htm> (and PAT_ENC_HSP, PAT_ENC_DX, PROBLEM_LIST, ORDER_PROC, ORDER_RESULTS, ORDER_MED, HNO_INFO, IP_FLWSHT_MEAS)
- EHI Living Manual (Chronicles→Clarity, LINE/date conventions): <https://joshuamandel.com/ehi-living-manual/00-04-epic-data-architecture/>
- JHM Epic→OMOP ETL (HNO_NOTE_TEXT, notes metadata): <https://pm.jh.edu/omop_etl/html/compiled_nbs/markdowns/HNO_NOTE_TEXT.html>
- OMOPHub Clarity guide: <https://omophub.com/blog/epic-clarity-data-model> · FHIR: <https://omophub.com/blog/epic-fhir-api>
- OHDSI forums (dx & procedure mapping pitfalls): <https://forums.ohdsi.org/t/populating-condition-occurrence-using-epic-clarity-and-its-duplications/11949> · <https://forums.ohdsi.org/t/comprehensive-procedure-mapping-from-epic/20144>
- GPC-informatics (med→RxNorm, terminology): <https://informatics.gpcnetwork.org/trac/Project/ticket/391>
- CLARITY_EDG / ICD-10 structures: <https://pmc.ncbi.nlm.nih.gov/articles/PMC4453378/>
- Stanford STARR dictionary: <https://med.stanford.edu/content/dam/sm/researchit/Content/STARR-Data-Dictionary.pdf> · Mount Sinai MSDW: <https://labs.icahn.mssm.edu/msdw/>
- Epic on FHIR: <https://fhir.epic.com/> · open.epic: <https://open.epic.com/interface/FHIR>
- Caboodle overviews: <https://digitalhealth.folio3.com/blog/guide-to-epic-caboodle/> · <https://www.mindbowser.com/understanding-epic-caboodle/>

**athenahealth**

- APIs overview / all APIs / charts: <https://docs.athenahealth.com/api/guides/overview> · <https://docs.athenahealth.com/api/docs/all-apis> · <https://docs.athenahealth.com/api/docs/charts>
- REST refs: <https://docs.athenahealth.com/api/api-ref/patient> · <https://docs.athenahealth.com/api/api-ref/appointment> · <https://docs.athenahealth.com/api/api-ref/encounter-service-notes> · <https://docs.athenahealth.com/api/api-ref/medications> · <https://docs.athenahealth.com/api/api-ref/vitals>
- FHIR: <https://docs.athenahealth.com/api/docs/fhir-apis> · base URLs <https://docs.athenahealth.com/api/guides/base-fhir-urls> · DocumentReference <https://docs.athenahealth.com/api/fhir-r4/document-reference> · DiagnosticReport <https://docs.athenahealth.com/api/fhir-r4/diagnostic-report>
- FHIR R4 IG v25.0.0 (resource catalog): <https://docs.mydata.athenahealth.com/fhir-r4/index.html> · EHI export <https://docs.mydata.athenahealth.com/fhir-r4/ehiexport.html>
- Athena Core DocumentReference profile: <https://fhir.athena.io/athenacoreext/StructureDefinition-ah-documentreference.html> · Document Classification guide <https://docs.athenahealth.com/api/workflows/document-classification-guide>
- USCDI FHIR R4 (22.7) / Bulk Data (22.7): <https://docs.athenahealth.com/api/resources/227-release-new-certified-uscdi-fhir-r4-read-and-search-apis> · <https://docs.athenahealth.com/api/resources/227-release-added-fhir-bulk-data-access-capability-support-21st-century-cures>
- OAuth: <https://docs.athenahealth.com/api/guides/authorization-overview>
- Developer portal / Marketplace: <https://www.athenahealth.com/developer-portal> · <https://www.athenahealth.com/solutions/marketplace-program>
- C-CDA export FAQ: <https://www.athenahealth.com/sites/default/files/media_docs/ccda-data-export-2022-combined.pdf>
- DataView vs Data Warehouse Feed: <https://dataartisans.tech/athenahealth-data-view-vs-data-warehouse-feed/> · Integration guide: <https://www.tactionsoft.com/blog/athenahealth-api-integration-guide/>
