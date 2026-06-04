# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # Synthetic EHR Silver Layer Generator
# MAGIC
# MAGIC Populates all 7 clinical tables in `dev.test_silver_ehr_clinical`:
# MAGIC `patient`, `encounter`, `condition`, `observation`,
# MAGIC `medication_order`, `procedure`, `clinical_note`
# MAGIC
# MAGIC ## Quick-start
# MAGIC | Run | N_PATIENTS | Purpose |
# MAGIC |---|---|---|
# MAGIC | Analysis | **500** | Initial exploration, NLP tuning, cohort query dev |
# MAGIC | Full POC | **5000** | Final demo dataset |
# MAGIC
# MAGIC Change `N_PATIENTS` in Section 1 and re-run all cells.
# MAGIC
# MAGIC ## Phenotype distribution (500 patients)
# MAGIC | Phenotype | % | ~N | Demo purpose |
# MAGIC |---|---|---|---|
# MAGIC | `t2dm_cvd` | 10% | 50 | **Primary cohort target** — T2DM + metformin + CVD |
# MAGIC | `t2dm_only` | 20% | 100 | T2DM on metformin, no CVD |
# MAGIC | `t2dm_alt_med` | 10% | 50 | T2DM on Januvia/insulin — excluded from metformin cohort |
# MAGIC | `hypertension` | 20% | 100 | HTN primary, no diabetes |
# MAGIC | `prediabetes` | 5% | 25 | Caught incidentally, lifestyle management |
# MAGIC | `general` | 35% | 175 | Background population |
# MAGIC
# MAGIC ## Optional: enhanced note templates
# MAGIC Upload `sample_clinical_notes.py` to the same Databricks folder and
# MAGIC uncomment the `%run` cell in Section 5 to use the full note library.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Imports and Configuration

# COMMAND ----------

from __future__ import annotations

import datetime
import itertools
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Target catalog / schema
# ---------------------------------------------------------------------------
CATALOG       = "dev"
SILVER_SCHEMA = "test_silver_ehr_clinical"

# ---------------------------------------------------------------------------
# *** TUNE THESE KNOBS ***
# ---------------------------------------------------------------------------
N_PATIENTS = 500          # change to 5000 for full POC run
SEED       = 42           # master seed — change to generate a different population

DATE_START = datetime.date(2022, 1, 1)
DATE_END   = datetime.date(2024, 12, 31)

# Phenotype mix (must sum to 1.0)
PHENOTYPE_DIST = {
    "t2dm_cvd":    0.10,
    "t2dm_only":   0.20,
    "t2dm_alt_med": 0.10,
    "hypertension": 0.20,
    "prediabetes":  0.05,
    "general":      0.35,
}

# Mean encounters per patient per phenotype (Poisson λ)
ENCOUNTER_RATE = {
    "t2dm_cvd":    8,
    "t2dm_only":   6,
    "t2dm_alt_med": 5,
    "hypertension": 4,
    "prediabetes":  3,
    "general":      4,
}

DATA_SOURCE = "SynaptiqEHR_POC"

print("Config loaded.")
print(f"  N_PATIENTS={N_PATIENTS}  SEED={SEED}")
print(f"  DATE_START={DATE_START}  DATE_END={DATE_END}")
print(f"  Target: {CATALOG}.{SILVER_SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Reference Data

# COMMAND ----------

# ICD-10-CM: code -> (display, is_chronic)
ICD10 = {
    "E11.9":   ("Type 2 diabetes mellitus without complications", True),
    "E11.65":  ("Type 2 diabetes mellitus with hyperglycemia", True),
    "I10":     ("Essential hypertension", True),
    "I25.10":  ("Coronary artery disease, native vessel", True),
    "I50.9":   ("Heart failure, unspecified", True),
    "I63.9":   ("Cerebral infarction, unspecified", False),
    "E78.5":   ("Hyperlipidemia, unspecified", True),
    "E11.40":  ("Type 2 diabetes mellitus with diabetic neuropathy, unspecified", True),
    "R73.09":  ("Prediabetes", False),
    "J06.9":   ("Acute upper respiratory infection, unspecified", False),
    "N39.0":   ("Urinary tract infection, site not specified", False),
    "K21.0":   ("Gastro-esophageal reflux disease with esophagitis", False),
    "M54.5":   ("Low back pain", False),
    "F32.9":   ("Major depressive disorder, single episode, unspecified", True),
    "J44.1":   ("Chronic obstructive pulmonary disease with exacerbation", True),
    "G43.909": ("Migraine, unspecified, not intractable, without status migrainosus", False),
    "Z00.00":  ("Encounter for general adult medical examination without abnormal findings", False),
    "M17.11":  ("Primary osteoarthritis, right knee", True),
    "R05.9":   ("Cough, unspecified", False),
    "Z87.891": ("Personal history of nicotine dependence", False),
}

# Codes that are random background (not phenotype-primary)
BACKGROUND_ICD10 = [
    "J06.9", "N39.0", "K21.0", "M54.5", "F32.9",
    "G43.909", "Z00.00", "M17.11", "R05.9", "Z87.891",
]

# CVD conditions for t2dm_cvd phenotype — one assigned per patient
CVD_ICD10 = ["I25.10", "I50.9", "I63.9"]

# LOINC labs: code -> (display, unit, ref_low, ref_high)
LOINC_LABS = {
    "4548-4":  ("Hemoglobin A1c/Hemoglobin.total in Blood", "%",      4.5,  6.5),
    "2345-7":  ("Glucose [Mass/volume] in Serum or Plasma",  "mg/dL",  70.0, 100.0),
    "2160-0":  ("Creatinine [Mass/volume] in Serum or Plasma","mg/dL",  0.6,  1.2),
    "2089-1":  ("LDL Cholesterol", "mg/dL", 0.0, 100.0),
    "718-7":   ("Hemoglobin [Mass/volume] in Blood", "g/dL", 12.0, 17.5),
    "6690-2":  ("Leukocytes [#/volume] in Blood by Automated count", "10*3/uL", 4.5, 11.0),
    "2823-3":  ("Potassium [Moles/volume] in Serum or Plasma", "mEq/L", 3.5, 5.1),
}

# LOINC vitals: code -> (display, unit, ref_low, ref_high)
LOINC_VITALS = {
    "85354-9": ("Blood pressure panel",          "mmHg",  None,  None),   # parent panel
    "8480-6":  ("Systolic blood pressure",       "mmHg",  90.0,  120.0),
    "8462-4":  ("Diastolic blood pressure",      "mmHg",  60.0,  80.0),
    "8867-4":  ("Heart rate",                    "/min",  60.0,  100.0),
    "39156-5": ("Body mass index (BMI) [Ratio]", "kg/m2", 18.5,  25.0),
    "3141-9":  ("Body weight Measured",          "kg",    45.0,  120.0),
    "8310-5":  ("Body temperature",              "Cel",   36.1,  37.2),
}

# Medications: key -> (rxnorm_code, display, dose_qty, dose_unit, route, frequency, sig)
MEDICATIONS = {
    "metformin_500":    ("860975",  "Metformin 500 mg",              "500",  "mg",    "oral",         "BID",    "Take 1 tablet by mouth twice daily with meals"),
    "metformin_1000":   ("861007",  "Metformin 1000 mg",             "1000", "mg",    "oral",         "BID",    "Take 1 tablet by mouth twice daily with meals"),
    "atorvastatin_20":  ("617311",  "Atorvastatin 20 mg",            "20",   "mg",    "oral",         "nightly","Take 1 tablet by mouth at bedtime"),
    "atorvastatin_40":  ("617312",  "Atorvastatin 40 mg",            "40",   "mg",    "oral",         "nightly","Take 1 tablet by mouth at bedtime"),
    "lisinopril_10":    ("314076",  "Lisinopril 10 mg",              "10",   "mg",    "oral",         "daily",  "Take 1 tablet by mouth once daily"),
    "amlodipine_5":     ("329528",  "Amlodipine 5 mg",               "5",    "mg",    "oral",         "daily",  "Take 1 tablet by mouth once daily"),
    "carvedilol_625":   ("200609",  "Carvedilol 6.25 mg",            "6.25", "mg",    "oral",         "BID",    "Take 1 tablet by mouth twice daily with food"),
    "furosemide_40":    ("310429",  "Furosemide 40 mg",              "40",   "mg",    "oral",         "daily",  "Take 1 tablet by mouth once daily in the morning"),
    "aspirin_81":       ("212033",  "Aspirin 81 mg",                 "81",   "mg",    "oral",         "daily",  "Take 1 tablet by mouth once daily"),
    "sitagliptin_100":  ("665035",  "Sitagliptin (Januvia) 100 mg",  "100",  "mg",    "oral",         "daily",  "Take 1 tablet by mouth once daily"),
    "insulin_glargine": ("285129",  "Insulin glargine 20 units",     "20",   "units", "subcutaneous", "nightly","Inject 20 units subcutaneously at bedtime"),
    "omeprazole_20":    ("40790",   "Omeprazole 20 mg",              "20",   "mg",    "oral",         "daily",  "Take 1 capsule by mouth once daily before breakfast"),
    "sertraline_50":    ("41493",   "Sertraline 50 mg",              "50",   "mg",    "oral",         "daily",  "Take 1 tablet by mouth once daily"),
    "levothyroxine_50": ("36567",   "Levothyroxine 50 mcg",          "50",   "mcg",   "oral",         "daily",  "Take 1 tablet by mouth once daily on an empty stomach"),
    "albuterol_inh":    ("745678",  "Albuterol Inhaler 90 mcg",      "90",   "mcg",   "inhaled",      "PRN",    "Inhale 2 puffs as needed for shortness of breath"),
    "metoprolol_25":    ("435",     "Metoprolol succinate 25 mg",    "25",   "mg",    "oral",         "daily",  "Take 1 tablet by mouth once daily"),
}

# Phenotype-guaranteed medications (assigned to 1st encounter, persist)
PHENOTYPE_MEDS = {
    "t2dm_cvd":    ["metformin_1000", "atorvastatin_40", "lisinopril_10", "aspirin_81", "carvedilol_625"],
    "t2dm_only":   ["metformin_1000"],
    "t2dm_alt_med": ["sitagliptin_100"],   # intentionally NO metformin
    "hypertension": ["lisinopril_10"],
    "prediabetes":  [],
    "general":      [],
}

# Background meds (random 0-2 per encounter)
BACKGROUND_MEDS = [
    "omeprazole_20", "sertraline_50", "levothyroxine_50",
    "albuterol_inh", "metoprolol_25", "amlodipine_5",
]

# CPT procedures: code -> (display, category)
CPT_PROCEDURES = {
    "99213": ("Office visit, established patient, low complexity",      "diagnostic"),
    "99214": ("Office visit, established patient, moderate complexity", "diagnostic"),
    "99232": ("Hospital subsequent visit",                             "diagnostic"),
    "99283": ("Emergency department visit, moderate severity",          "diagnostic"),
    "93000": ("Electrocardiogram, routine ECG with interpretation",    "diagnostic"),
    "71046": ("Radiologic exam, chest, 2 views",                       "diagnostic"),
    "36415": ("Venipuncture, routine",                                 "diagnostic"),
    "80053": ("Comprehensive metabolic panel",                         "diagnostic"),
    "85025": ("Complete blood count with differential",                "diagnostic"),
    "80061": ("Lipid panel",                                           "diagnostic"),
    "82947": ("Glucose, blood; quantitative",                          "diagnostic"),
    "93798": ("Cardiac rehabilitation",                                "therapeutic"),
    "97110": ("Therapeutic exercises",                                 "therapeutic"),
    "45378": ("Colonoscopy",                                           "diagnostic"),
    "27447": ("Total knee replacement",                                "surgical"),
    "99395": ("Preventive medicine visit, 18-39 years",               "diagnostic"),
    "99396": ("Preventive medicine visit, 40-64 years",               "diagnostic"),
    "93306": ("Echocardiography, transthoracic, complete",            "diagnostic"),
    "74177": ("CT abdomen and pelvis with contrast",                  "diagnostic"),
    "70553": ("MRI brain without and with contrast",                  "diagnostic"),
}

# CPTs heavily favored by phenotype
PHENOTYPE_PREFERRED_CPT = {
    "t2dm_cvd":    ["93000", "80061", "80053", "82947", "93306"],
    "t2dm_only":   ["80053", "82947", "80061", "85025", "99214"],
    "t2dm_alt_med": ["80053", "82947", "80061", "99214"],
    "hypertension": ["99213", "99214", "93000", "80053", "71046"],
    "prediabetes":  ["99213", "82947", "99395", "80061"],
    "general":      list(CPT_PROCEDURES.keys()),
}

FIRST_NAMES_F = ["Emma","Olivia","Ava","Isabella","Sophia","Mia","Charlotte","Amelia",
                  "Harper","Evelyn","Abigail","Emily","Elizabeth","Sofia","Avery",
                  "Ella","Scarlett","Grace","Victoria","Riley","Natalie","Zoe"]
FIRST_NAMES_M = ["Liam","Noah","William","James","Oliver","Benjamin","Elijah","Lucas",
                  "Mason","Logan","Alexander","Ethan","Daniel","Jacob","Michael",
                  "Henry","Jackson","Sebastian","Aiden","Matthew","David","Joseph"]
LAST_NAMES    = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
                  "Rodriguez","Martinez","Hernandez","Lopez","Wilson","Anderson","Thomas",
                  "Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White",
                  "Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
                  "Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores"]
STATES        = ["CA","TX","FL","NY","PA","IL","OH","GA","NC","MI","NJ","VA","WA","AZ","MA"]
RACES         = ["White","Black or African American","Asian","American Indian or Alaska Native","Other","Unknown"]
ETHNICITIES   = ["Not Hispanic or Latino","Hispanic or Latino","Unknown"]
MARITAL_STATI = ["married","single","divorced","widowed","separated"]
FACILITIES    = [
    "Synaptiq Regional Medical Center", "Community Health Partners",
    "University Hospital", "Valley Primary Care", "Downtown Urgent Care",
    "Lakeside Medical Group", "Riverside Family Medicine",
]
PROVIDERS     = [
    "Dr. Sarah Chen", "Dr. Marcus Williams", "Dr. Priya Patel",
    "Dr. James O'Brien", "Dr. Lisa Rodriguez", "Dr. Robert Kim",
    "Dr. Angela Thompson", "Dr. David Nguyen", "Dr. Maria Santos",
    "Dr. John Mitchell", "Dr. Amy Foster", "Dr. Carlos Rivera",
]

print("Reference data loaded.")
print(f"  {len(ICD10)} ICD-10 codes  |  {len(MEDICATIONS)} medications  |  {len(CPT_PROCEDURES)} CPT codes")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Helper: write_delta

# COMMAND ----------

def write_delta(pdf: pd.DataFrame, catalog: str, schema: str, table: str) -> None:
    """
    Write a pandas DataFrame as a Delta table (overwrite, idempotent).
    Casts all-None (NullType) columns to StringType to avoid Parquet errors.
    Drops any internal-only columns prefixed with '_' before writing.
    """
    from pyspark.sql import functions as F
    from pyspark.sql.types import NullType, StringType

    # Drop generator-internal columns (e.g. _phenotype used for joins)
    internal_cols = [c for c in pdf.columns if c.startswith("_")]
    if internal_cols:
        pdf = pdf.drop(columns=internal_cols)

    full_name = f"`{catalog}`.`{schema}`.`{table}`"
    sdf = spark.createDataFrame(pdf)

    null_cols = [f.name for f in sdf.schema.fields if isinstance(f.dataType, NullType)]
    for col_name in null_cols:
        sdf = sdf.withColumn(col_name, F.lit(None).cast(StringType()))

    (sdf.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(full_name))
    count = spark.table(full_name).count()
    print(f"  Wrote {count:>8,} rows  →  {full_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Phenotype Assignment

# COMMAND ----------

def assign_phenotypes(n: int, rng: np.random.Generator) -> list[str]:
    """Assign one phenotype per patient using PHENOTYPE_DIST probabilities."""
    labels  = list(PHENOTYPE_DIST.keys())
    weights = list(PHENOTYPE_DIST.values())
    return rng.choice(labels, size=n, p=weights).tolist()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Inline Note Templates
# MAGIC
# MAGIC Compact templates for the 6 phenotypes × 4 note types.
# MAGIC For the richer full-length note library, upload `sample_clinical_notes.py`
# MAGIC to the same Databricks workspace folder and uncomment the line below.

# COMMAND ----------

# Optional: uncomment to use the full note library from sample_clinical_notes.py
# %run ./sample_clinical_notes

# COMMAND ----------

def render_note(template: str, **kwargs) -> str:
    """Substitute {variable} placeholders; missing keys are left intact."""
    defaults = {
        "name": "Patient", "age": "60", "sex": "male",
        "he_she": "he", "his_her": "his", "him_her": "him",
        "mrn": "MRN-000000", "admit_date": "2024-01-01",
        "disch_date": "2024-01-03", "service_date": "2024-01-01",
        "provider": "Attending Physician", "facility": "General Hospital",
        "systolic": "128", "diastolic": "80", "hr": "72",
        "bmi": "28.4", "weight": "82", "hba1c": "7.6",
        "glucose": "142", "creatinine": "0.9", "ldl": "98",
        "hba1c_prior": "8.0", "age_at_dx": "52",
    }
    merged = {**defaults, **kwargs}
    result = template
    for key, val in merged.items():
        result = result.replace("{" + key + "}", str(val))
    return result


# Inline templates — one per key use case
_T_DS_T2DM_CVD = """\
DISCHARGE SUMMARY | {facility}
Patient: {name}  MRN: {mrn}  Age/Sex: {age}-year-old {sex}
Admitted: {admit_date}  Discharged: {disch_date}  Attending: {provider}

PRINCIPAL DIAGNOSIS: Acute decompensated heart failure (I50.9)
SECONDARY: Type 2 diabetes mellitus (E11.9), Essential hypertension (I10),
           Coronary artery disease (I25.10), Hyperlipidemia (E78.5)

HOSPITAL COURSE:
{name} is a {age}-year-old {sex} with Type 2 diabetes mellitus managed with metformin \
1000 mg twice daily and coronary artery disease who presented with dyspnea and lower \
extremity edema. IV furosemide was initiated with good diuretic response. \
Metformin was held on admission and resumed at discharge after renal function remained \
stable. HbA1c on admission: {hba1c}%. No evidence of acute myocardial infarction — \
serial troponins negative. CT pulmonary angiography ruled out pulmonary embolism. \
Patient denies chest pain throughout admission.

FAMILY HISTORY: Father with coronary artery disease (MI at age 58). \
Mother with Type 2 diabetes.

VITAL SIGNS AT DISCHARGE: BP {systolic}/{diastolic} mmHg | HR {hr} bpm | BMI {bmi}

DISCHARGE MEDICATIONS:
1. Metformin 1000 mg PO BID (resumed)   2. Lisinopril 10 mg PO daily
3. Carvedilol 6.25 mg PO BID            4. Furosemide 40 mg PO daily
5. Atorvastatin 40 mg PO nightly        6. Aspirin 81 mg PO daily

FOLLOW-UP: Cardiology 2 weeks, Primary Care 1 week.
"""

_T_PN_T2DM = """\
PROGRESS NOTE — DIABETES MANAGEMENT | {service_date} | {facility}
Patient: {name}  MRN: {mrn}  Age: {age}  Sex: {sex}  Provider: {provider}

SUBJECTIVE: Routine Type 2 diabetes follow-up. Patient adherent to metformin \
1000 mg BID. Reports no episodes of hypoglycemia. Tingling in bilateral feet at \
night consistent with peripheral neuropathy.

OBJECTIVE: BP {systolic}/{diastolic} mmHg | HR {hr} bpm | Weight {weight} kg | BMI {bmi}
HbA1c: {hba1c}% | Fasting glucose: {glucose} mg/dL | Creatinine: {creatinine} mg/dL
Funduscopic exam: no signs of diabetic retinopathy.
Monofilament: reduced sensation bilateral distal lower extremities.

ASSESSMENT: Type 2 diabetes mellitus with early peripheral neuropathy. HbA1c {hba1c}%.
No evidence of retinopathy. No active foot ulcers. Denies chest pain or dyspnea.

PLAN: Continue metformin. Reinforce glycemic control. Refer podiatry and neurology.
Follow-up 3 months with repeat HbA1c.
"""

_T_PN_HTN = """\
PROGRESS NOTE — HYPERTENSION FOLLOW-UP | {service_date} | {facility}
Patient: {name}  MRN: {mrn}  Age: {age}  Sex: {sex}  Provider: {provider}

SUBJECTIVE: Hypertension follow-up. Home BP logs 130-140/80-88 mmHg. \
No chest pain. No dyspnea. Denies diabetes mellitus. Denies polyuria or polydipsia.

OBJECTIVE: BP {systolic}/{diastolic} mmHg | HR {hr} bpm | BMI {bmi}
Creatinine: {creatinine} mg/dL | Potassium: 4.1 mEq/L | LDL: {ldl} mg/dL
Fasting glucose: {glucose} mg/dL — borderline; no diabetes diagnosis at this time.

ASSESSMENT: Essential hypertension, above goal. No coronary artery disease on record.
Family history: father with coronary artery disease. Rule out prediabetes — \
will recheck fasting glucose in 3 months.

PLAN: Uptitrate amlodipine to 10 mg. DASH diet reinforced. Initiate low-intensity statin.
"""

_T_PN_PREDIABETES = """\
PROGRESS NOTE — PREDIABETES COUNSELING | {service_date} | {facility}
Patient: {name}  MRN: {mrn}  Age: {age}  Sex: {sex}  Provider: {provider}

SUBJECTIVE: Incidental prediabetes found on routine labs. Patient denies fatigue, \
polyuria, or polydipsia. Family history positive for Type 2 diabetes (mother).

OBJECTIVE: BP {systolic}/{diastolic} mmHg | BMI {bmi}
Fasting Plasma Glucose: {glucose} mg/dL | HbA1c: {hba1c}%

ASSESSMENT: Prediabetes. No diagnosis of diabetes mellitus at this time.

PLAN: Lifestyle modification counseling. Refer to Diabetes Prevention Program. \
Repeat FPG and HbA1c in 6 months. Metformin deferred — lifestyle trial first.
"""

_T_HP_UNDIAGNOSED = """\
HISTORY AND PHYSICAL — NEW PATIENT | {service_date} | {facility}
Patient: {name}  MRN: {mrn}  Age: {age}  Sex: {sex}  Provider: {provider}

CHIEF COMPLAINT: Excessive thirst, frequent urination, fatigue, weight loss x 3 weeks.

SUBJECTIVE: Patient reports excessive thirst (polydipsia) and needing to urinate \
multiple times throughout the night (nocturia) for the past 3 weeks. Complains of \
generalized fatigue and unintentional 10-lb weight loss despite increased appetite \
(polyphagia). Notes blurry vision over the past week. Slow-healing laceration on \
right great toe noted. No prior diagnosis of diabetes.

OBJECTIVE: BMI {bmi} | BP {systolic}/{diastolic} mmHg
Urine dipstick: positive for glycosuria and ketones.
Point-of-care glucose: {glucose} mg/dL. HbA1c pending.

ASSESSMENT: New-onset hyperglycemia; rule out Type 1 vs. Type 2 Diabetes Mellitus.

PLAN: Draw fasting HbA1c, C-peptide, GAD-65 antibodies. Wound care for toe laceration. \
Ophthalmology referral. Follow-up 48-72 hours for lab results.
"""

_T_PN_GENERAL = """\
PROGRESS NOTE — ACUTE CARE VISIT | {service_date} | {facility}
Patient: {name}  MRN: {mrn}  Age: {age}  Sex: {sex}  Provider: {provider}

SUBJECTIVE: Cough and low-grade fever x 5 days. Denies shortness of breath. \
No chest pain. Denies diabetes mellitus. No known asthma or COPD.

OBJECTIVE: Temp 37.9°C | BP {systolic}/{diastolic} mmHg | HR {hr} bpm | SpO2 97% RA
Pulmonary: mild scattered rhonchi, clearing with cough. No focal consolidation.

ASSESSMENT: Acute upper respiratory infection, viral etiology most likely. \
No evidence of bacterial pneumonia. Rule out early pneumonia if symptoms worsen.

PLAN: Symptomatic treatment. Return if dyspnea develops or fever persists >5 more days.
"""

_T_HP_T2DM = """\
HISTORY AND PHYSICAL | {service_date} | {facility}
Patient: {name}  MRN: {mrn}  Age: {age}  Sex: {sex}  Provider: {provider}

HPI: {age}-year-old {sex} with {age_at_dx}-year history of Type 2 diabetes mellitus \
on metformin 500 mg BID and hypertension presenting for pre-operative evaluation. \
HbA1c {hba1c}%. Denies angina, no known coronary artery disease on record. \
No active foot ulcers — remote history of right great toe ulcer, fully healed 3 years ago.

FAMILY HISTORY: Father with Type 2 diabetes, hypertension, deceased (MI age 71). \
Mother with hypertension.

VITALS: BP {systolic}/{diastolic} | HR {hr} | BMI {bmi}

ASSESSMENT: T2DM suboptimally controlled (HbA1c {hba1c}%). Hypertension controlled.
No diabetic retinopathy documented. No current neuropathy symptoms.

PLAN: Hold metformin 48h pre-op. Continue antihypertensives. Low cardiac risk.
"""

# Assemble inline NOTES_LIBRARY (overridden if %run sample_clinical_notes succeeds)
try:
    _ = NOTES_LIBRARY   # test if already defined by %run
    print("Using note library from sample_clinical_notes.py")
except NameError:
    NOTES_LIBRARY = {
        "discharge_summary": {
            "t2dm_cvd":    [_T_DS_T2DM_CVD],
            "t2dm_only":   [_T_DS_T2DM_CVD],
            "general":     [_T_DS_T2DM_CVD],
        },
        "progress": {
            "t2dm_cvd":    [_T_PN_T2DM],
            "t2dm_only":   [_T_PN_T2DM],
            "t2dm_alt_med":[_T_PN_T2DM],
            "hypertension":[_T_PN_HTN],
            "prediabetes": [_T_PN_PREDIABETES],
            "general":     [_T_PN_GENERAL],
        },
        "hp": {
            "undiagnosed": [_T_HP_UNDIAGNOSED],
            "t2dm_cvd":    [_T_HP_T2DM],
            "t2dm_only":   [_T_HP_T2DM],
            "t2dm_alt_med":[_T_HP_T2DM],
            "hypertension":[_T_PN_HTN],
            "prediabetes": [_T_PN_PREDIABETES],
            "general":     [_T_PN_GENERAL],
        },
    }
    print("Using inline note templates.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Generator Functions

# COMMAND ----------

def gen_patients(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate n patient rows with sequential patient_sk (1..n).
    Includes _phenotype column (prefixed _ so write_delta drops it).
    """
    phenotypes = assign_phenotypes(n, rng)
    now = datetime.datetime.utcnow()
    rows = []

    for i in range(n):
        patient_sk = i + 1
        phenotype  = phenotypes[i]
        sex        = rng.choice(["male", "female"])
        fn         = rng.choice(FIRST_NAMES_F if sex == "female" else FIRST_NAMES_M)
        ln         = rng.choice(LAST_NAMES)
        state      = rng.choice(STATES)

        # Age range influenced by phenotype
        if phenotype in ("t2dm_cvd", "t2dm_only", "t2dm_alt_med"):
            age_years = int(rng.integers(40, 80))
        elif phenotype == "prediabetes":
            age_years = int(rng.integers(30, 65))
        elif phenotype == "hypertension":
            age_years = int(rng.integers(45, 80))
        else:
            age_years = int(rng.integers(18, 85))

        today      = datetime.date(2024, 6, 1)  # reference date for age calc
        birth_year = today.year - age_years
        birth_date = datetime.date(birth_year, int(rng.integers(1, 13)), int(rng.integers(1, 29)))

        deceased   = rng.random() < 0.015
        deceased_date = (
            datetime.date(int(rng.integers(2022, 2025)), int(rng.integers(1, 13)), int(rng.integers(1, 29)))
            if deceased else None
        )

        rows.append({
            "patient_sk":       patient_sk,
            "mrn":              f"MRN-{patient_sk:06d}",
            "birth_date":       birth_date,
            "sex":              sex,
            "gender_identity":  sex,
            "race":             rng.choice(RACES),
            "ethnicity":        rng.choice(ETHNICITIES),
            "deceased_flag":    deceased,
            "deceased_date":    deceased_date,
            "city":             f"City{rng.integers(1, 300):03d}",
            "state":            state,
            "zip":              f"{int(rng.integers(10000, 99999)):05d}",
            "primary_language": "English",
            "marital_status":   rng.choice(MARITAL_STATI),
            "loaded_at":        now,
            # Internal — dropped before write
            "_phenotype":       phenotype,
            "_first_name":      fn,
            "_last_name":       ln,
            "_age_years":       age_years,
        })
    return pd.DataFrame(rows)


def gen_encounters(patients_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate encounters for all patients.
    encounter_sk is sequential across the full dataset.
    Returns df with _phenotype, _patient_name, _age columns for downstream use.
    """
    now = datetime.datetime.utcnow()
    date_range_days = (DATE_END - DATE_START).days
    rows = []
    enc_sk = 1

    CLASSES      = ["inpatient", "outpatient", "emergency", "ambulatory", "telehealth"]
    CLASS_TYPES  = {
        "inpatient":   "Hospital Admission",
        "outpatient":  "Outpatient Visit",
        "emergency":   "Emergency Department Visit",
        "ambulatory":  "Ambulatory Care Visit",
        "telehealth":  "Telehealth Visit",
    }
    # Encounter class weights by phenotype
    CLASS_WEIGHTS = {
        "t2dm_cvd":    [0.20, 0.40, 0.15, 0.15, 0.10],
        "t2dm_only":   [0.05, 0.55, 0.10, 0.20, 0.10],
        "t2dm_alt_med":[0.05, 0.55, 0.10, 0.20, 0.10],
        "hypertension":[0.03, 0.60, 0.07, 0.20, 0.10],
        "prediabetes": [0.00, 0.60, 0.05, 0.25, 0.10],
        "general":     [0.05, 0.50, 0.15, 0.20, 0.10],
    }
    ADMIT_SOURCES = ["1", "2", "4", "5", "7"]
    DISCH_DISPS   = ["01", "02", "03", "05", "07"]

    for _, pt in patients_df.iterrows():
        phenotype  = pt["_phenotype"]
        mean_enc   = ENCOUNTER_RATE[phenotype]
        n_enc      = max(1, int(rng.poisson(mean_enc)))
        weights    = CLASS_WEIGHTS[phenotype]

        for j in range(n_enc):
            enc_class   = rng.choice(CLASSES, p=weights)
            day_offset  = int(rng.integers(0, max(1, date_range_days)))
            start_date  = DATE_START + datetime.timedelta(days=day_offset)
            los_days    = int(rng.integers(1, 5)) if enc_class == "inpatient" else 0
            end_date    = start_date + datetime.timedelta(days=los_days)
            start_ts    = datetime.datetime.combine(start_date, datetime.time(int(rng.integers(6, 22)), 0))
            end_ts      = datetime.datetime.combine(end_date, datetime.time(int(rng.integers(8, 23)), 0))

            is_inpatient = enc_class in ("inpatient", "emergency")

            rows.append({
                "encounter_sk":           enc_sk,
                "patient_sk":             int(pt["patient_sk"]),
                "encounter_class":        enc_class,
                "encounter_type":         CLASS_TYPES[enc_class],
                "status":                 "finished",
                "period_start":           start_ts,
                "period_end":             end_ts,
                "admit_source":           rng.choice(ADMIT_SOURCES) if is_inpatient else None,
                "discharge_disposition":  rng.choice(DISCH_DISPS) if enc_class == "inpatient" else None,
                "attending_provider_name":rng.choice(PROVIDERS),
                "facility_name":          rng.choice(FACILITIES),
                "loaded_at":              now,
                # Internal
                "_phenotype":             phenotype,
                "_encounter_index":       j,   # 0 = first encounter for note-type logic
                "_patient_name":          f"{pt['_first_name']} {pt['_last_name']}",
                "_age_years":             int(pt["_age_years"]),
                "_sex":                   pt["sex"],
                "_mrn":                   pt["mrn"],
            })
            enc_sk += 1

    return pd.DataFrame(rows)


def gen_conditions(encounters_df: pd.DataFrame, patients_df: pd.DataFrame,
                   rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate conditions for each encounter.
    Primary conditions are phenotype-driven; 0-2 background conditions added per encounter.
    CVD condition is assigned consistently to the same t2dm_cvd patient.
    """
    now = datetime.datetime.utcnow()
    rows = []
    cond_sk = 1

    # Pre-assign CVD code per t2dm_cvd patient so it's consistent across encounters
    cvd_by_patient: dict[int, str] = {}
    for _, pt in patients_df.iterrows():
        if pt["_phenotype"] == "t2dm_cvd":
            cvd_by_patient[int(pt["patient_sk"])] = rng.choice(CVD_ICD10)

    PHENOTYPE_PRIMARY_ICD = {
        "t2dm_cvd":    ["E11.9"],
        "t2dm_only":   ["E11.9"],
        "t2dm_alt_med":["E11.9"],
        "hypertension":["I10"],
        "prediabetes": ["R73.09"],
        "general":     [],
    }

    for _, enc in encounters_df.iterrows():
        phenotype = enc["_phenotype"]
        patient_sk = int(enc["patient_sk"])
        enc_start  = enc["period_start"]
        enc_date   = enc_start.date() if hasattr(enc_start, "date") else enc_start

        # Primary phenotype conditions
        primary_codes = list(PHENOTYPE_PRIMARY_ICD[phenotype])
        if phenotype == "t2dm_cvd" and patient_sk in cvd_by_patient:
            primary_codes.append(cvd_by_patient[patient_sk])
        if phenotype == "general":
            primary_codes = [rng.choice(BACKGROUND_ICD10)]

        for rank, icd_code in enumerate(primary_codes, start=1):
            display, is_chronic = ICD10.get(icd_code, (f"Diagnosis {icd_code}", False))
            onset_days_ago  = int(rng.integers(30, 1000)) if is_chronic else int(rng.integers(1, 30))
            onset_date      = enc_date - datetime.timedelta(days=onset_days_ago)
            clinical_status = "active" if is_chronic else rng.choice(["active", "resolved"])
            resolved_date   = (
                enc_date + datetime.timedelta(days=int(rng.integers(7, 60)))
                if clinical_status == "resolved" else None
            )
            category = "problem-list-item" if is_chronic else "encounter-diagnosis"

            rows.append({
                "condition_sk":        cond_sk,
                "patient_sk":          patient_sk,
                "encounter_sk":        int(enc["encounter_sk"]),
                "category":            category,
                "condition_code":      icd_code,
                "condition_system":    "ICD-10-CM",
                "condition_display":   display,
                "clinical_status":     clinical_status,
                "verification_status": "confirmed",
                "rank":                rank,
                "is_chronic":          is_chronic,
                "onset_date":          onset_date,
                "recorded_date":       enc_date,
                "resolved_date":       resolved_date,
                "loaded_at":           now,
            })
            cond_sk += 1

        # 0-2 background conditions per encounter
        n_background = int(rng.integers(0, 3))
        bg_codes     = rng.choice(BACKGROUND_ICD10, size=n_background, replace=False).tolist()
        for bg_code in bg_codes:
            display, is_chronic = ICD10.get(bg_code, (f"Diagnosis {bg_code}", False))
            rows.append({
                "condition_sk":        cond_sk,
                "patient_sk":          patient_sk,
                "encounter_sk":        int(enc["encounter_sk"]),
                "category":            "encounter-diagnosis",
                "condition_code":      bg_code,
                "condition_system":    "ICD-10-CM",
                "condition_display":   display,
                "clinical_status":     "resolved",
                "verification_status": "confirmed",
                "rank":                len(primary_codes) + 1,
                "is_chronic":          is_chronic,
                "onset_date":          enc_date - datetime.timedelta(days=int(rng.integers(1, 14))),
                "recorded_date":       enc_date,
                "resolved_date":       enc_date + datetime.timedelta(days=int(rng.integers(3, 21))),
                "loaded_at":           now,
            })
            cond_sk += 1

    return pd.DataFrame(rows)


def gen_observations(encounters_df: pd.DataFrame, patients_df: pd.DataFrame,
                     rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate lab and vital-sign observations per encounter.
    - Vitals: BP (parent + systolic + diastolic), HR, BMI, weight — every encounter
    - Labs: phenotype-driven (HbA1c/glucose for T2DM, lipid panel broadly)
    - BP uses parent_observation_sk pattern per DDL spec
    """
    now = datetime.datetime.utcnow()
    rows: list[dict] = []
    obs_sk_counter = itertools.count(1)

    # Phenotype-specific lab LOINC codes
    PHENOTYPE_LABS = {
        "t2dm_cvd":    ["4548-4", "2345-7", "2160-0", "2089-1", "85025"],
        "t2dm_only":   ["4548-4", "2345-7", "2160-0", "2089-1"],
        "t2dm_alt_med":["4548-4", "2345-7", "2160-0", "2089-1"],
        "hypertension":["2160-0", "2089-1", "2823-3"],
        "prediabetes": ["2345-7", "2089-1"],
        "general":     ["718-7", "6690-2"],
    }

    # Phenotype-specific HbA1c distribution
    HBAC1C_PARAMS = {
        "t2dm_cvd":    (8.2, 1.2),
        "t2dm_only":   (7.4, 1.0),
        "t2dm_alt_med":(8.5, 1.3),
        "hypertension":(5.4, 0.4),
        "prediabetes": (5.9, 0.3),
        "general":     (5.2, 0.5),
    }
    BMI_PARAMS = {
        "t2dm_cvd":    (31.5, 4.0),
        "t2dm_only":   (30.0, 4.5),
        "t2dm_alt_med":(31.0, 4.5),
        "hypertension":(28.5, 4.0),
        "prediabetes": (29.0, 3.5),
        "general":     (26.0, 4.0),
    }
    SBP_PARAMS = {  # systolic BP mean, std
        "t2dm_cvd":    (138, 14),
        "t2dm_only":   (130, 12),
        "t2dm_alt_med":(132, 12),
        "hypertension":(145, 16),
        "prediabetes": (122, 10),
        "general":     (118, 12),
    }

    for _, enc in encounters_df.iterrows():
        phenotype = enc["_phenotype"]
        patient_sk = int(enc["patient_sk"])
        enc_sk     = int(enc["encounter_sk"])
        enc_date   = enc["period_start"]
        eff_dt     = enc_date if isinstance(enc_date, datetime.datetime) \
                     else datetime.datetime.combine(enc_date, datetime.time(9, 0))

        bmi_mean, bmi_std = BMI_PARAMS[phenotype]
        sbp_mean, sbp_std = SBP_PARAMS[phenotype]

        bmi_val  = float(np.clip(rng.normal(bmi_mean, bmi_std), 17.0, 55.0))
        sbp_val  = float(np.clip(rng.normal(sbp_mean, sbp_std), 90.0, 190.0))
        dbp_val  = float(np.clip(rng.normal(sbp_val * 0.60, 7.0), 55.0, 120.0))
        hr_val   = float(np.clip(rng.normal(74, 12), 45.0, 130.0))
        wt_val   = float(np.clip(rng.normal(82 + (bmi_val - 26) * 2, 8), 40.0, 180.0))

        # ---- BP Panel (parent row + 2 component rows) ----
        bp_panel_sk = next(obs_sk_counter)
        systolic_sk = next(obs_sk_counter)
        diastolic_sk = next(obs_sk_counter)

        rows.append({
            "observation_sk": bp_panel_sk, "patient_sk": patient_sk,
            "encounter_sk": enc_sk, "category": "vital-signs",
            "observation_code": "85354-9", "observation_system": "LOINC",
            "observation_display": "Blood pressure panel",
            "value_numeric": None, "value_string": f"{sbp_val:.0f}/{dbp_val:.0f}",
            "unit": "mmHg", "reference_range_low": None, "reference_range_high": None,
            "interpretation": None, "effective_datetime": eff_dt,
            "parent_observation_sk": None, "loaded_at": now,
        })
        rows.append({
            "observation_sk": systolic_sk, "patient_sk": patient_sk,
            "encounter_sk": enc_sk, "category": "vital-signs",
            "observation_code": "8480-6", "observation_system": "LOINC",
            "observation_display": "Systolic blood pressure",
            "value_numeric": round(sbp_val, 1), "value_string": None,
            "unit": "mmHg", "reference_range_low": 90.0, "reference_range_high": 120.0,
            "interpretation": "normal" if sbp_val <= 130 else ("high" if sbp_val <= 160 else "critical"),
            "effective_datetime": eff_dt,
            "parent_observation_sk": bp_panel_sk, "loaded_at": now,
        })
        rows.append({
            "observation_sk": diastolic_sk, "patient_sk": patient_sk,
            "encounter_sk": enc_sk, "category": "vital-signs",
            "observation_code": "8462-4", "observation_system": "LOINC",
            "observation_display": "Diastolic blood pressure",
            "value_numeric": round(dbp_val, 1), "value_string": None,
            "unit": "mmHg", "reference_range_low": 60.0, "reference_range_high": 80.0,
            "interpretation": "normal" if dbp_val <= 85 else "high",
            "effective_datetime": eff_dt,
            "parent_observation_sk": bp_panel_sk, "loaded_at": now,
        })

        # ---- Other vitals ----
        for code, val, unit, ref_lo, ref_hi in [
            ("8867-4", hr_val,  "/min",   60.0, 100.0),
            ("39156-5", bmi_val, "kg/m2", 18.5,  25.0),
            ("3141-9",  wt_val,  "kg",    45.0, 120.0),
        ]:
            interp = "normal" if ref_lo <= val <= ref_hi else ("high" if val > ref_hi else "low")
            rows.append({
                "observation_sk": next(obs_sk_counter), "patient_sk": patient_sk,
                "encounter_sk": enc_sk, "category": "vital-signs",
                "observation_code": code, "observation_system": "LOINC",
                "observation_display": LOINC_VITALS[code][0],
                "value_numeric": round(val, 1), "value_string": None,
                "unit": unit, "reference_range_low": ref_lo, "reference_range_high": ref_hi,
                "interpretation": interp, "effective_datetime": eff_dt,
                "parent_observation_sk": None, "loaded_at": now,
            })

        # ---- Labs (phenotype-driven) ----
        lab_codes = PHENOTYPE_LABS.get(phenotype, [])
        # Not every encounter has labs — 70% chance
        if rng.random() > 0.30:
            for lab_code in lab_codes:
                if lab_code not in LOINC_LABS:
                    continue
                desc, unit, ref_lo, ref_hi = LOINC_LABS[lab_code]

                if lab_code == "4548-4":   # HbA1c
                    mu, sigma = HBAC1C_PARAMS[phenotype]
                    val = float(np.clip(rng.normal(mu, sigma), 4.5, 13.0))
                elif lab_code == "2345-7": # Glucose
                    base = 160 if phenotype in ("t2dm_cvd","t2dm_only","t2dm_alt_med") else \
                           110 if phenotype == "prediabetes" else 90
                    val = float(np.clip(rng.normal(base, 25), 55.0, 400.0))
                else:
                    val = float(rng.uniform(ref_lo * 0.8, ref_hi * 1.2))
                    val = float(np.clip(val, ref_lo * 0.5, ref_hi * 2.0))

                val = round(val, 2)
                interp = "normal" if ref_lo <= val <= ref_hi else ("high" if val > ref_hi else "low")

                rows.append({
                    "observation_sk": next(obs_sk_counter), "patient_sk": patient_sk,
                    "encounter_sk": enc_sk, "category": "laboratory",
                    "observation_code": lab_code, "observation_system": "LOINC",
                    "observation_display": desc,
                    "value_numeric": val, "value_string": None,
                    "unit": unit, "reference_range_low": ref_lo, "reference_range_high": ref_hi,
                    "interpretation": interp,
                    "effective_datetime": eff_dt - datetime.timedelta(hours=2),
                    "parent_observation_sk": None, "loaded_at": now,
                })

    return pd.DataFrame(rows)


def gen_medication_orders(encounters_df: pd.DataFrame, patients_df: pd.DataFrame,
                          rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate medication orders per encounter.
    First encounter for each patient receives all phenotype-primary medications.
    Subsequent encounters receive 0-2 random background medications.
    """
    now = datetime.datetime.utcnow()
    rows = []
    med_sk = 1

    seen_patients: set[int] = set()

    for _, enc in encounters_df.iterrows():
        phenotype  = enc["_phenotype"]
        patient_sk = int(enc["patient_sk"])
        enc_sk     = int(enc["encounter_sk"])
        enc_start  = enc["period_start"]
        start_ts   = enc_start if isinstance(enc_start, datetime.datetime) \
                     else datetime.datetime.combine(enc_start, datetime.time(9, 0))

        first_encounter = patient_sk not in seen_patients
        seen_patients.add(patient_sk)

        # Primary meds on first encounter
        med_keys = []
        if first_encounter:
            med_keys = list(PHENOTYPE_MEDS[phenotype])

        # 0-2 background meds on every encounter
        n_bg = int(rng.integers(0, 3))
        bg_keys = rng.choice(BACKGROUND_MEDS, size=min(n_bg, len(BACKGROUND_MEDS)), replace=False).tolist()
        med_keys += bg_keys

        for med_key in med_keys:
            if med_key not in MEDICATIONS:
                continue
            rxnorm, display, dose_qty, dose_unit, route, freq, sig = MEDICATIONS[med_key]
            duration_days = int(rng.integers(30, 365))
            rows.append({
                "med_order_sk":  med_sk,
                "patient_sk":    patient_sk,
                "encounter_sk":  enc_sk,
                "med_code":      rxnorm,
                "med_system":    "RxNorm",
                "med_display":   display,
                "ndc_code":      None,
                "order_class":   "inpatient" if enc["encounter_class"] == "inpatient" else "outpatient",
                "dose_quantity": dose_qty,
                "dose_unit":     dose_unit,
                "route":         route,
                "frequency":     freq,
                "sig_text":      sig,
                "order_status":  "active",
                "start_datetime":start_ts,
                "end_datetime":  start_ts + datetime.timedelta(days=duration_days),
                "loaded_at":     now,
            })
            med_sk += 1

    return pd.DataFrame(rows)


def gen_procedures(encounters_df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Generate 1-2 CPT procedures per encounter, phenotype-weighted."""
    now = datetime.datetime.utcnow()
    rows = []
    proc_sk = 1

    for _, enc in encounters_df.iterrows():
        phenotype  = enc["_phenotype"]
        patient_sk = int(enc["patient_sk"])
        enc_sk     = int(enc["encounter_sk"])
        enc_start  = enc["period_start"]
        perf_ts    = enc_start if isinstance(enc_start, datetime.datetime) \
                     else datetime.datetime.combine(enc_start, datetime.time(10, 0))

        preferred_pool = PHENOTYPE_PREFERRED_CPT[phenotype]
        n_procs = int(rng.integers(1, 3))

        # 70% chance from preferred pool, 30% from full CPT pool
        for _ in range(n_procs):
            if rng.random() < 0.70:
                cpt_code = rng.choice(preferred_pool)
            else:
                cpt_code = rng.choice(list(CPT_PROCEDURES.keys()))

            display, category = CPT_PROCEDURES.get(cpt_code, (f"Procedure {cpt_code}", "diagnostic"))
            rows.append({
                "procedure_sk":       proc_sk,
                "patient_sk":         patient_sk,
                "encounter_sk":       enc_sk,
                "procedure_code":     cpt_code,
                "procedure_system":   "CPT",
                "procedure_display":  display,
                "procedure_category": category,
                "status":             "completed",
                "performed_datetime": perf_ts,
                "loaded_at":          now,
            })
            proc_sk += 1

    return pd.DataFrame(rows)


def gen_clinical_notes(encounters_df: pd.DataFrame,
                       rng: np.random.Generator) -> pd.DataFrame:
    """
    Generate one clinical note per encounter.
    Note category is determined by encounter_class and encounter index.
    Template is chosen from NOTES_LIBRARY by phenotype.
    """
    now = datetime.datetime.utcnow()
    rows = []
    note_sk = 1

    # LOINC document type codes
    LOINC_NOTE_TYPES = {
        "discharge_summary": ("18842-5", "Discharge summary"),
        "progress":          ("11506-3", "Progress note"),
        "hp":                ("34117-2", "History and physical note"),
        "consult":           ("11488-4", "Consult note"),
    }

    for _, enc in encounters_df.iterrows():
        phenotype   = enc["_phenotype"]
        enc_class   = enc["encounter_class"]
        enc_index   = int(enc["_encounter_index"])
        patient_sk  = int(enc["patient_sk"])
        enc_sk      = int(enc["encounter_sk"])
        svc_date    = enc["period_start"]
        if not isinstance(svc_date, datetime.datetime):
            svc_date = datetime.datetime.combine(svc_date, datetime.time(14, 0))
        admit_date  = svc_date.strftime("%Y-%m-%d")
        disch_date  = (svc_date + datetime.timedelta(days=2)).strftime("%Y-%m-%d")

        # Determine note category
        if enc_class == "inpatient":
            note_cat = "discharge_summary"
        elif enc_index == 0:
            note_cat = "hp"
        else:
            note_cat = "progress"

        # Phenotype-appropriate template selection
        note_cat_lib = NOTES_LIBRARY.get(note_cat, NOTES_LIBRARY.get("progress", {}))
        if phenotype in note_cat_lib:
            templates = note_cat_lib[phenotype]
        else:
            fallback_cat = NOTES_LIBRARY.get("progress", {})
            templates = fallback_cat.get("general", [_T_PN_GENERAL])

        template = templates[int(rng.integers(0, len(templates)))]

        # Generate phenotype-appropriate clinical values for rendering
        if phenotype in ("t2dm_cvd", "t2dm_only", "t2dm_alt_med"):
            hba1c   = round(float(np.clip(rng.normal(7.8, 0.9), 6.0, 12.5)), 1)
            glucose = int(np.clip(rng.normal(155, 30), 90, 400))
        elif phenotype == "prediabetes":
            hba1c   = round(float(np.clip(rng.normal(5.9, 0.2), 5.7, 6.4)), 1)
            glucose = int(np.clip(rng.normal(110, 8), 100, 125))
        else:
            hba1c   = round(float(np.clip(rng.normal(5.3, 0.4), 4.5, 6.4)), 1)
            glucose = int(np.clip(rng.normal(92, 10), 70, 100))

        sbp  = int(np.clip(rng.normal(132, 14), 90, 190))
        dbp  = int(np.clip(rng.normal(80, 8), 55, 115))
        hr   = int(np.clip(rng.normal(74, 10), 50, 120))
        bmi  = round(float(np.clip(rng.normal(29, 4), 18, 50)), 1)
        wt   = int(np.clip(rng.normal(82, 12), 45, 180))
        cr   = round(float(np.clip(rng.normal(0.9, 0.2), 0.5, 3.0)), 2)
        ldl  = int(np.clip(rng.normal(95, 22), 40, 220))
        age_at_dx = max(18, int(enc["_age_years"]) - int(rng.integers(3, 15)))

        note_text = render_note(
            template,
            name=enc["_patient_name"],
            age=str(enc["_age_years"]),
            sex=enc["_sex"],
            he_she="he" if enc["_sex"] == "male" else "she",
            his_her="his" if enc["_sex"] == "male" else "her",
            him_her="him" if enc["_sex"] == "male" else "her",
            mrn=enc["_mrn"],
            admit_date=admit_date,
            disch_date=disch_date,
            service_date=svc_date.strftime("%Y-%m-%d"),
            provider=enc["attending_provider_name"],
            facility=enc["facility_name"],
            systolic=str(sbp), diastolic=str(dbp), hr=str(hr),
            bmi=str(bmi), weight=str(wt),
            hba1c=str(hba1c), hba1c_prior=str(round(hba1c + rng.uniform(0.2, 1.0), 1)),
            glucose=str(glucose), creatinine=str(cr), ldl=str(ldl),
            age_at_dx=str(age_at_dx),
        )

        loinc_code, loinc_display = LOINC_NOTE_TYPES.get(note_cat, ("11506-3", "Progress note"))

        rows.append({
            "note_sk":          note_sk,
            "patient_sk":       patient_sk,
            "encounter_sk":     enc_sk,
            "note_type_code":   loinc_code,
            "note_type_system": "LOINC",
            "note_type_display":loinc_display,
            "note_category":    note_cat,
            "author_name":      enc["attending_provider_name"],
            "service_date":     svc_date,
            "status":           "signed",
            "note_text":        note_text,
            "loaded_at":        now,
        })
        note_sk += 1

    return pd.DataFrame(rows)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Execute — Generate and Write All Tables

# COMMAND ----------

print("=" * 65)
print(f"GENERATING SYNTHETIC EHR DATA — {N_PATIENTS} patients")
print(f"  Schema : {CATALOG}.{SILVER_SCHEMA}")
print(f"  Dates  : {DATE_START} → {DATE_END}")
print(f"  Seed   : {SEED}")
print("=" * 65)

rng = np.random.default_rng(SEED)

spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SILVER_SCHEMA}`")
print(f"Schema {CATALOG}.{SILVER_SCHEMA} ready.\n")

# COMMAND ----------

print("--- patients ---")
patients_df = gen_patients(N_PATIENTS, rng)
write_delta(patients_df, CATALOG, SILVER_SCHEMA, "patient")
pheno_counts = patients_df["_phenotype"].value_counts().to_dict()
print(f"  Phenotype breakdown: {pheno_counts}")

# COMMAND ----------

print("\n--- encounters ---")
encounters_df = gen_encounters(patients_df, rng)
write_delta(encounters_df, CATALOG, SILVER_SCHEMA, "encounter")
print(f"  Mean encounters/patient: {len(encounters_df) / N_PATIENTS:.1f}")

# COMMAND ----------

print("\n--- conditions ---")
conditions_df = gen_conditions(encounters_df, patients_df, rng)
write_delta(conditions_df, CATALOG, SILVER_SCHEMA, "condition")
print(f"  Mean conditions/encounter: {len(conditions_df) / len(encounters_df):.1f}")

# COMMAND ----------

print("\n--- observations (labs + vitals) ---")
observations_df = gen_observations(encounters_df, patients_df, rng)
write_delta(observations_df, CATALOG, SILVER_SCHEMA, "observation")
lab_ct   = (observations_df["category"] == "laboratory").sum()
vital_ct = (observations_df["category"] == "vital-signs").sum()
print(f"  Labs: {lab_ct:,}  |  Vitals: {vital_ct:,}")

# COMMAND ----------

print("\n--- medication orders ---")
meds_df = gen_medication_orders(encounters_df, patients_df, rng)
write_delta(meds_df, CATALOG, SILVER_SCHEMA, "medication_order")
print(f"  Mean meds/encounter: {len(meds_df) / len(encounters_df):.1f}")

# COMMAND ----------

print("\n--- procedures ---")
procs_df = gen_procedures(encounters_df, rng)
write_delta(procs_df, CATALOG, SILVER_SCHEMA, "procedure")
print(f"  Mean procedures/encounter: {len(procs_df) / len(encounters_df):.1f}")

# COMMAND ----------

print("\n--- clinical notes ---")
notes_df = gen_clinical_notes(encounters_df, rng)
write_delta(notes_df, CATALOG, SILVER_SCHEMA, "clinical_note")
note_cats = notes_df["note_category"].value_counts().to_dict()
print(f"  Note categories: {note_cats}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Validation

# COMMAND ----------

from pyspark.sql import functions as F

print("=" * 65)
print("VALIDATION SUMMARY")
print("=" * 65)

tables = ["patient","encounter","condition","observation","medication_order","procedure","clinical_note"]
print("\n--- Row counts ---")
for tbl in tables:
    n = spark.table(f"`{CATALOG}`.`{SILVER_SCHEMA}`.`{tbl}`").count()
    print(f"  {tbl:<22s}  {n:>8,}")

# COMMAND ----------

print("\n--- Phenotype distribution (patients) ---")
pheno_df = spark.createDataFrame(
    [(k, v) for k, v in pheno_counts.items()],
    ["phenotype", "count"]
).withColumn("pct", F.round(F.col("count") / N_PATIENTS * 100, 1))
display(pheno_df.orderBy("count", ascending=False))

# COMMAND ----------

print("\n--- HbA1c by phenotype (should be higher for T2DM phenotypes) ---")
hba1c_q = f"""
SELECT p._phenotype_proxy,
       ROUND(AVG(o.value_numeric), 2) AS mean_hba1c,
       COUNT(*)                       AS n_results
FROM   `{CATALOG}`.`{SILVER_SCHEMA}`.`observation` o
JOIN   `{CATALOG}`.`{SILVER_SCHEMA}`.`patient` pat ON o.patient_sk = pat.patient_sk
JOIN (
    SELECT patient_sk,
           CASE
             WHEN mrn LIKE 'MRN-000%' THEN 'see_condition'
             ELSE 'unknown'
           END AS _phenotype_proxy
    FROM `{CATALOG}`.`{SILVER_SCHEMA}`.`patient`
) p ON o.patient_sk = p.patient_sk
WHERE  o.observation_code = '4548-4'
GROUP BY p._phenotype_proxy
"""
# Simpler: just show HbA1c distribution
hba1c_dist = (
    spark.table(f"`{CATALOG}`.`{SILVER_SCHEMA}`.`observation`")
    .filter(F.col("observation_code") == "4548-4")
    .agg(
        F.round(F.mean("value_numeric"), 2).alias("mean_hba1c"),
        F.round(F.expr("percentile(value_numeric, 0.25)"), 2).alias("p25"),
        F.round(F.expr("percentile(value_numeric, 0.75)"), 2).alias("p75"),
        F.count("*").alias("n"),
    )
)
display(hba1c_dist)

# COMMAND ----------

print("\n--- T2DM + Metformin + CVD cohort size (target: ~50 for 500-patient run) ---")
cohort_q = f"""
WITH t2dm AS (
    SELECT DISTINCT patient_sk
    FROM   `{CATALOG}`.`{SILVER_SCHEMA}`.`condition`
    WHERE  condition_code = 'E11.9'
),
on_metformin AS (
    SELECT DISTINCT patient_sk
    FROM   `{CATALOG}`.`{SILVER_SCHEMA}`.`medication_order`
    WHERE  med_code IN ('860975', '861007')   -- RxNorm metformin codes
),
cvd AS (
    SELECT DISTINCT patient_sk
    FROM   `{CATALOG}`.`{SILVER_SCHEMA}`.`condition`
    WHERE  condition_code IN ('I25.10','I50.9','I63.9')
    AND    recorded_date >= DATE_SUB(CURRENT_DATE(), 730)  -- last 2 years
)
SELECT COUNT(*) AS cohort_size
FROM   t2dm
JOIN   on_metformin USING (patient_sk)
JOIN   cvd          USING (patient_sk)
"""
cohort_size = spark.sql(cohort_q).collect()[0]["cohort_size"]
print(f"  T2DM + Metformin + CVD cohort: {cohort_size} patients")
print(f"  (Expected ~{int(N_PATIENTS * 0.10)} for {N_PATIENTS}-patient run)")

# COMMAND ----------

print("\n--- Metformin patients (should be ~30% of population) ---")
metformin_ct = (
    spark.table(f"`{CATALOG}`.`{SILVER_SCHEMA}`.`medication_order`")
    .filter(F.col("med_code").isin(["860975", "861007"]))
    .select("patient_sk").distinct().count()
)
print(f"  Patients on metformin: {metformin_ct} ({metformin_ct/N_PATIENTS*100:.1f}%)")
print(f"  (Expected ~{int(N_PATIENTS * 0.30)} = t2dm_cvd 10% + t2dm_only 20%)")

# COMMAND ----------

print("\n--- Note category distribution ---")
display(
    spark.table(f"`{CATALOG}`.`{SILVER_SCHEMA}`.`clinical_note`")
    .groupBy("note_category")
    .agg(F.count("*").alias("count"))
    .orderBy("count", ascending=False)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Done
# MAGIC
# MAGIC ### Summary table
# MAGIC
# MAGIC | Table | Purpose | Key demo queries |
# MAGIC |---|---|---|
# MAGIC | `patient` | Demographics | Filter by age, sex, race |
# MAGIC | `encounter` | Visit history | Inpatient vs outpatient, date ranges |
# MAGIC | `condition` | Diagnoses | ICD-10 cohort criteria (E11.9, I25.10, …) |
# MAGIC | `observation` | Labs + vitals | HbA1c trends, BP control, BMI |
# MAGIC | `medication_order` | Prescriptions | Metformin, statin, ACE inhibitor filters |
# MAGIC | `procedure` | CPT events | ECG, echo, cardiac rehab |
# MAGIC | `clinical_note` | Free text | NLP entity extraction input |
# MAGIC
# MAGIC ### To scale to 5,000 patients
# MAGIC Change `N_PATIENTS = 5000` in Section 1 and re-run all cells.
# MAGIC Expected runtime: ~5-10 minutes on a single-node cluster.
# MAGIC
# MAGIC ### Next step: NLP extraction
# MAGIC Run the NLP pipeline against `clinical_note.note_text` to populate
# MAGIC `dev.test_silver_ehr_clinical.nlp_run` and `note_nlp_entity`.
