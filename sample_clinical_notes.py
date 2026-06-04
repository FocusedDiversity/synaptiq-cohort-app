# Databricks notebook source

# COMMAND ----------

# MAGIC %md
# MAGIC # Sample Clinical Notes Library
# MAGIC
# MAGIC Realistic synthetic note templates for the EHR POC cohort builder.
# MAGIC Designed to exercise all four NLP entity attributes:
# MAGIC
# MAGIC | Attribute | Values exercised |
# MAGIC |---|---|
# MAGIC | `certainty` | positive, negated, uncertain, hypothetical |
# MAGIC | `temporality` | current, historical, family |
# MAGIC | `negation` | true (negated mentions), false (positive mentions) |
# MAGIC | `subject` | patient, family |
# MAGIC
# MAGIC ## How to use
# MAGIC
# MAGIC Each template is a Python f-string-style template using `{variable}` placeholders.
# MAGIC Call `render_note(template, **kwargs)` to produce a final note string.
# MAGIC
# MAGIC Available placeholders (all optional with defaults):
# MAGIC   {name}         - patient full name
# MAGIC   {age}          - age in years
# MAGIC   {sex}          - male / female
# MAGIC   {he_she}       - he / she
# MAGIC   {his_her}      - his / her
# MAGIC   {him_her}      - him / her
# MAGIC   {mrn}          - medical record number
# MAGIC   {admit_date}   - admission date string
# MAGIC   {disch_date}   - discharge date string
# MAGIC   {service_date} - note service date string
# MAGIC   {provider}     - attending / author provider name
# MAGIC   {facility}     - facility name
# MAGIC   {systolic}     - systolic BP (mmHg)
# MAGIC   {diastolic}    - diastolic BP (mmHg)
# MAGIC   {hr}           - heart rate (bpm)
# MAGIC   {bmi}          - BMI (kg/m²)
# MAGIC   {hba1c}        - HbA1c (%)
# MAGIC   {glucose}      - fasting glucose (mg/dL)
# MAGIC   {creatinine}   - serum creatinine (mg/dL)
# MAGIC   {ldl}          - LDL cholesterol (mg/dL)
# MAGIC   {weight}       - body weight (kg)
# MAGIC
# MAGIC ## Structure of NOTES_LIBRARY
# MAGIC
# MAGIC   NOTES_LIBRARY[note_category][phenotype] = [list of template strings]
# MAGIC
# MAGIC note_category : discharge_summary | progress | hp | consult | radiology | pathology
# MAGIC phenotype     : t2dm_cvd | t2dm_only | t2dm_alt_med | hypertension | general

# COMMAND ----------

def render_note(template: str, **kwargs) -> str:
    """
    Render a note template by substituting {variable} placeholders.
    Any placeholder not supplied in kwargs is left as-is (no KeyError).
    """
    import re

    defaults = {
        "name":          "Patient",
        "age":           "65",
        "sex":           "male",
        "he_she":        "he",
        "his_her":       "his",
        "him_her":       "him",
        "mrn":           "MRN-UNKNOWN",
        "admit_date":    "2024-01-01",
        "disch_date":    "2024-01-03",
        "service_date":  "2024-01-01",
        "provider":      "Attending Physician",
        "facility":      "General Hospital",
        "systolic":      "128",
        "diastolic":     "80",
        "hr":            "72",
        "bmi":           "28.4",
        "hba1c":         "7.6",
        "glucose":       "142",
        "creatinine":    "0.9",
        "ldl":           "98",
        "weight":        "82",
    }
    merged = {**defaults, **kwargs}
    # Replace known placeholders; leave unknown ones intact
    result = template
    for key, val in merged.items():
        result = result.replace("{" + key + "}", str(val))
    return result

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Discharge Summaries

# COMMAND ----------

# ---------------------------------------------------------------------------
# DISCHARGE SUMMARY — T2DM + Cardiovascular Disease (t2dm_cvd)
# NLP targets: positive T2DM, positive CVD, positive metformin,
#              negated PE/MI, family history CAD, historical HTN
# ---------------------------------------------------------------------------

DS_T2DM_CVD_1 = """\
DISCHARGE SUMMARY

Patient: {name}                    MRN: {mrn}
Age/Sex: {age}-year-old {sex}      Facility: {facility}
Admission: {admit_date}            Discharge: {disch_date}
Attending: Dr. {provider}

PRINCIPAL DIAGNOSIS
  Acute decompensated heart failure (I50.9)

SECONDARY DIAGNOSES
  1. Type 2 diabetes mellitus without complications (E11.9)
  2. Essential hypertension (I10)
  3. Hyperlipidemia (E78.5)
  4. Coronary artery disease, native vessel (I25.10)

REASON FOR ADMISSION
{name} is a {age}-year-old {sex} with a known history of Type 2 diabetes mellitus \
managed with metformin 500 mg twice daily, coronary artery disease, and chronic \
hypertension who presented to the emergency department with worsening dyspnea on \
exertion and bilateral lower extremity edema over the preceding five days. \
{he_she.capitalize()} reported a weight gain of approximately 4 kg in the past week.

HOSPITAL COURSE
The patient was admitted to the medical floor and initiated on intravenous furosemide \
with excellent diuretic response. Cardiology was consulted and recommended an \
echocardiogram, which demonstrated reduced left ventricular ejection fraction of 35%, \
consistent with systolic heart failure. Metformin was held on admission due to the risk \
of lactic acidosis in the setting of acute decompensation and was resumed at discharge \
after {his_her} renal function remained stable throughout the hospitalization.

Blood glucose levels were monitored closely. HbA1c obtained on admission was {hba1c}%. \
Endocrinology was not consulted; current regimen was deemed appropriate given the \
degree of glycemic control.

PERTINENT NEGATIVES
No evidence of acute myocardial infarction. Serial troponins were negative x2. \
CT pulmonary angiography ruled out pulmonary embolism. Patient denies chest pain \
at rest or on exertion prior to this admission. No fever or leukocytosis to suggest \
infectious etiology. No acute kidney injury identified on admission labs.

FAMILY HISTORY
Family history is significant for coronary artery disease — {his_her} father had \
a myocardial infarction at age 58. {his_her.capitalize()} mother carries a diagnosis \
of Type 2 diabetes.

VITAL SIGNS AT DISCHARGE
BP {systolic}/{diastolic} mmHg | HR {hr} bpm | BMI {bmi} kg/m²

LABORATORY (DISCHARGE)
  Creatinine: {creatinine} mg/dL | BMP within normal limits | HbA1c: {hba1c}%

DISCHARGE MEDICATIONS
  1. Metformin 500 mg PO BID (resumed)
  2. Lisinopril 10 mg PO daily
  3. Carvedilol 6.25 mg PO BID
  4. Furosemide 40 mg PO daily
  5. Atorvastatin 40 mg PO nightly
  6. Aspirin 81 mg PO daily

DISCHARGE CONDITION: Stable
FOLLOW-UP: Cardiology in 2 weeks. Primary Care in 1 week.
"""

DS_T2DM_CVD_2 = """\
DISCHARGE SUMMARY

Patient: {name}    MRN: {mrn}    DOB-derived Age: {age}    Sex: {sex}
Admitted: {admit_date}    Discharged: {disch_date}
Attending: Dr. {provider}    Facility: {facility}

DIAGNOSES AT DISCHARGE
  Primary:   Unstable angina (I20.0)
  Secondary: Type 2 diabetes mellitus with diabetic chronic kidney disease (E11.65)
             Hypertension (I10)
             Chronic heart failure with reduced ejection fraction (I50.9)

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with a history of Type 2 diabetes mellitus on \
metformin 1000 mg twice daily and insulin glargine 20 units nightly, hypertension, \
and known coronary artery disease who presented with an episode of substernal chest \
tightness radiating to the left arm lasting approximately 20 minutes, which resolved \
with sublingual nitroglycerin in the field.

HOSPITAL COURSE
Initial electrocardiogram showed no ST-elevation. Troponin I was mildly elevated at \
0.06 ng/mL and remained stable on serial checks, not consistent with type 1 MI. \
Cardiology performed coronary angiography demonstrating 70% stenosis of the left \
anterior descending artery. A drug-eluting stent was placed without complication. \
{he_she.capitalize()} was started on dual antiplatelet therapy (aspirin and ticagrelor).

Glycemic management: Metformin was held peri-procedure. Insulin was continued. \
Fasting glucose ranged from {glucose} to 210 mg/dL during hospitalization. \
Renal function remained stable with creatinine of {creatinine} mg/dL.

PERTINENT NEGATIVES
No ST-elevation myocardial infarction. No evidence of aortic dissection on CT imaging. \
Denies cocaine or stimulant use. No known prior stroke or TIA. \
Patient denies palpitations, syncope, or near-syncope prior to this event.

FAMILY / SOCIAL HISTORY
Strong family history of cardiovascular disease: father died of myocardial infarction \
at age 61, brother underwent coronary artery bypass grafting at age 55. \
No family history of bleeding disorders.

LABS AT DISCHARGE
HbA1c: {hba1c}% | Creatinine: {creatinine} mg/dL | LDL: {ldl} mg/dL (post-statin)

DISCHARGE MEDICATIONS
  1. Aspirin 81 mg PO daily (indefinite)
  2. Ticagrelor 90 mg PO BID (minimum 12 months)
  3. Metformin 1000 mg PO BID (resumed)
  4. Insulin glargine 20 units SC nightly
  5. Lisinopril 5 mg PO daily
  6. Rosuvastatin 40 mg PO nightly
  7. Metoprolol succinate 25 mg PO daily

FOLLOW-UP: Cardiology in 1 week, Endocrinology in 4 weeks.
"""

# ---------------------------------------------------------------------------
# DISCHARGE SUMMARY — T2DM only (t2dm_only)
# NLP targets: positive T2DM, positive metformin, negated CVD/complications,
#              historical foot ulcer
# ---------------------------------------------------------------------------

DS_T2DM_ONLY_1 = """\
DISCHARGE SUMMARY

Patient: {name}    MRN: {mrn}    Age: {age}    Sex: {sex}
Admitted: {admit_date}    Discharged: {disch_date}
Attending: Dr. {provider}

PRINCIPAL DIAGNOSIS
  Hyperosmolar hyperglycemic state (HHS) in the setting of Type 2 diabetes mellitus (E11.0)

SECONDARY DIAGNOSES
  1. Type 2 diabetes mellitus (E11.9)
  2. Urinary tract infection (N39.0)

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with Type 2 diabetes mellitus previously managed \
with metformin 500 mg twice daily who presented after {his_her} family noted progressive \
confusion, polydipsia, and polyuria over 3 days. {he_she.capitalize()} reported \
having stopped metformin approximately 2 weeks prior due to gastrointestinal side effects. \
Admission glucose was 780 mg/dL with serum osmolality of 328 mOsm/kg.

HOSPITAL COURSE
Patient was admitted to the medical ICU and initiated on an insulin drip with aggressive \
IV fluid resuscitation. Glucose and electrolytes were monitored hourly. Mental status \
improved significantly within 24 hours of treatment. Urine culture grew E. coli; \
trimethoprim-sulfamethoxazole was initiated for uncomplicated urinary tract infection. \
Nephrology was consulted. No evidence of acute kidney injury.

Metformin was not restarted during hospitalization. Diabetes education was provided. \
Endocrinology recommended transitioning to metformin 500 mg daily with gradual \
up-titration and adding a GLP-1 receptor agonist (semaglutide 0.5 mg SC weekly) \
given ongoing difficulty with glycemic control.

PERTINENT NEGATIVES
No evidence of myocardial infarction precipitating the hyperglycemic event. \
No diabetic ketoacidosis (anion gap normal). No peripheral neuropathy documented \
on this admission. No active foot ulcer — {he_she} has a remote history of \
a right great toe ulcer that fully healed two years ago. \
No coronary artery disease on record. Denies chest pain or dyspnea.

FAMILY HISTORY
Mother and maternal aunt both have Type 2 diabetes. No family history of \
premature cardiovascular disease.

HbA1c AT ADMISSION: {hba1c}%
DISCHARGE WEIGHT: {weight} kg | BMI: {bmi} kg/m²

DISCHARGE MEDICATIONS
  1. Metformin 500 mg PO daily (titrate up per PCP)
  2. Semaglutide 0.5 mg SC weekly (new)
  3. Trimethoprim-sulfamethoxazole DS PO BID x 3 days (complete course)

FOLLOW-UP: Endocrinology in 2 weeks. Primary Care in 1 week.
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Progress Notes

# COMMAND ----------

# ---------------------------------------------------------------------------
# PROGRESS NOTE — T2DM + CVD follow-up (t2dm_cvd)
# NLP targets: positive T2DM, CVD, metformin; negated hypoglycemia;
#              historical MI; uncertain renal function trend
# ---------------------------------------------------------------------------

PN_T2DM_CVD_1 = """\
PROGRESS NOTE — CARDIOLOGY / DIABETES FOLLOW-UP

Date: {service_date}    Patient: {name}    MRN: {mrn}    Age: {age}    Sex: {sex}
Provider: Dr. {provider}

CHIEF COMPLAINT
Follow-up after recent hospitalization for acute decompensated heart failure.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with Type 2 diabetes mellitus on metformin \
500 mg twice daily, coronary artery disease status post percutaneous coronary \
intervention, and chronic heart failure with reduced ejection fraction \
(last EF 35%) presenting for post-discharge follow-up. {he_she.capitalize()} \
reports improvement in dyspnea and lower extremity edema since discharge. \
{he_she.capitalize()} has been compliant with {his_her} medications and low-sodium diet. \
No new chest pain. No palpitations or pre-syncope.

REVIEW OF SYSTEMS
POSITIVE: Mild exertional fatigue. Occasional nocturia (1-2x per night).
NEGATIVE: No chest pain at rest or exertion. No orthopnea or paroxysmal nocturnal \
dyspnea. Denies hypoglycemia. No blurred vision. No numbness or tingling in feet. \
No new lower extremity edema.

MEDICATIONS (current)
  1. Metformin 500 mg PO BID
  2. Lisinopril 10 mg PO daily
  3. Carvedilol 6.25 mg PO BID
  4. Furosemide 40 mg PO daily
  5. Atorvastatin 40 mg PO nightly
  6. Aspirin 81 mg PO daily

VITAL SIGNS
BP {systolic}/{diastolic} mmHg | HR {hr} bpm | Weight {weight} kg | BMI {bmi} kg/m²

PHYSICAL EXAMINATION
General: Alert, no acute distress.
Cardiovascular: Regular rate and rhythm. 2/6 holosystolic murmur at apex. \
No S3 gallop. JVP not elevated.
Pulmonary: Clear to auscultation bilaterally. No crackles.
Extremities: Trace bilateral pitting edema at ankles only. No calf tenderness.

LABORATORY
HbA1c: {hba1c}% (previous {hba1c_prior}% — modest improvement)
Fasting glucose: {glucose} mg/dL
Creatinine: {creatinine} mg/dL — trending up from 0.8 mg/dL 3 months ago, \
though not yet meeting criteria for dose adjustment of metformin. \
Will monitor closely; rule out early diabetic nephropathy in context of \
suboptimal glycemic control.
LDL: {ldl} mg/dL (at goal on atorvastatin)
BNP: 480 pg/mL (down from 1,200 pg/mL at admission — favorable response)

ASSESSMENT AND PLAN
1. Chronic heart failure, EF 35% — NYHA Class II. Responding to current regimen. \
   Continue furosemide. Follow-up echocardiogram in 3 months.
2. Type 2 diabetes mellitus — HbA1c improved but not yet at goal. \
   Continue metformin. Consider adding SGLT2 inhibitor given dual benefit \
   in heart failure and glycemic control.
3. Coronary artery disease — continue aspirin and statin. LDL at target.
4. Renal function — creatinine trending up. Repeat CMP in 6 weeks. \
   If creatinine exceeds 1.5 mg/dL, reduce or hold metformin per guidelines.

Return to clinic in 6 weeks.
"""

# ---------------------------------------------------------------------------
# PROGRESS NOTE — T2DM diabetes management visit (t2dm_only)
# NLP targets: positive T2DM, positive metformin; negated complications
# ---------------------------------------------------------------------------

PN_T2DM_ONLY_1 = """\
PROGRESS NOTE — DIABETES MANAGEMENT

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Provider: Dr. {provider}

CHIEF COMPLAINT
Routine diabetes follow-up.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} presenting for scheduled Type 2 diabetes \
management. {he_she.capitalize()} has been diagnosed with Type 2 diabetes mellitus \
for approximately 8 years and is currently managed with metformin 1000 mg twice daily. \
{he_she.capitalize()} denies any episodes of hypoglycemia. Reports compliance with \
medications and adherence to a low-carbohydrate diet. {he_she.capitalize()} has been \
checking blood glucose at home — fasting readings averaging 140-160 mg/dL.

REVIEW OF SYSTEMS
POSITIVE: Increased thirst and urinary frequency. Fatigue.
NEGATIVE: No chest pain. No shortness of breath. No lower extremity edema. \
No blurred vision. No tingling, numbness, or burning pain in hands or feet. \
No episodes of hypoglycemia. Denies nausea or diarrhea on current metformin dose.

MEDICATIONS
  1. Metformin 1000 mg PO BID

VITAL SIGNS
BP {systolic}/{diastolic} mmHg | HR {hr} bpm | Weight {weight} kg | BMI {bmi} kg/m²

PHYSICAL EXAMINATION
Alert, oriented x3. Cardiovascular: Regular rate and rhythm, no murmurs. \
Pulmonary: Clear to auscultation bilaterally. Abdomen: Soft, non-tender. \
Extremities: No edema. No skin breakdown or ulceration. Sensation intact to \
monofilament testing bilaterally. Pedal pulses palpable.

LABORATORY
HbA1c: {hba1c}% (goal <7.5% for this patient)
Fasting glucose: {glucose} mg/dL
Creatinine: {creatinine} mg/dL (stable, eGFR >60 — metformin safe to continue)
LDL: {ldl} mg/dL
Urine microalbumin/creatinine ratio: within normal limits — no microalbuminuria

ASSESSMENT AND PLAN
1. Type 2 diabetes mellitus — HbA1c above goal. No evidence of end-organ damage \
   at this visit. Reinforce dietary modifications. Continue metformin 1000 mg BID. \
   Consider adding a GLP-1 receptor agonist to improve glycemic control and support \
   weight loss given BMI of {bmi}. Patient agreeable to trial.
2. Hypertension — blood pressure at goal, no medication change.
3. Preventive care: Annual dilated eye exam — overdue. Podiatry referral placed. \
   Influenza vaccine administered today.

Follow-up in 3 months with repeat HbA1c and CMP.
"""

# ---------------------------------------------------------------------------
# PROGRESS NOTE — Hypertension primary care (hypertension)
# NLP targets: positive HTN; negated diabetes, no cardiac history;
#              historical borderline glucose; family CAD
# ---------------------------------------------------------------------------

PN_HTN_1 = """\
PROGRESS NOTE — HYPERTENSION MANAGEMENT

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Provider: Dr. {provider}

CHIEF COMPLAINT
Hypertension follow-up and annual wellness visit.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with essential hypertension managed on \
lisinopril 10 mg daily and amlodipine 5 mg daily. {he_she.capitalize()} has \
been adherent to {his_her} antihypertensive regimen. Home blood pressure \
monitoring logs show readings consistently in the range of 130-140/80-88 mmHg. \
{he_she.capitalize()} denies headache, visual changes, or epistaxis.

REVIEW OF SYSTEMS
POSITIVE: Occasional mild headaches in the morning.
NEGATIVE: No chest pain. No dyspnea. No palpitations. No lower extremity swelling. \
No polyuria or polydipsia. Denies diabetes mellitus. No history of stroke or TIA. \
Denies angina or known coronary artery disease.

MEDICATIONS
  1. Lisinopril 10 mg PO daily
  2. Amlodipine 5 mg PO daily

VITAL SIGNS
BP {systolic}/{diastolic} mmHg (right arm, seated) | HR {hr} bpm | \
Weight {weight} kg | BMI {bmi} kg/m²

PHYSICAL EXAMINATION
Alert, in no distress. Cardiovascular: Regular rate and rhythm. No murmurs, \
rubs, or gallops. Carotid without bruits. Pulmonary: Clear. \
Fundoscopy: No arteriovenous nicking or papilledema.

LABORATORY
Creatinine: {creatinine} mg/dL (baseline, stable)
Potassium: 4.2 mEq/L (within normal limits on ACE inhibitor)
Fasting glucose: {glucose} mg/dL — borderline elevated. No prior history \
of diabetes. Will recheck in 3 months. Rule out pre-diabetes vs stress response.
LDL: {ldl} mg/dL

ASSESSMENT AND PLAN
1. Essential hypertension — blood pressure mildly above goal (target <130/80). \
   Uptitrate amlodipine from 5 mg to 10 mg daily. Reinforce sodium restriction (<2 g/day) \
   and DASH diet. Recheck BP in 4 weeks.
2. Borderline fasting glucose — no diagnosis of diabetes mellitus at this time. \
   Lifestyle counseling provided regarding risk of progression to Type 2 diabetes. \
   Fasting glucose and HbA1c to be rechecked in 3 months.
3. Hyperlipidemia, borderline — LDL above goal given cardiovascular risk factors. \
   Will initiate low-intensity statin (rosuvastatin 5 mg) after discussing risks/benefits.

FAMILY HISTORY NOTE: Patient reports father had a heart attack at age 65 and maternal \
uncle has Type 2 diabetes. Family history of premature cardiovascular disease noted.

Follow-up in 4 weeks for BP recheck; 3 months for labs.
"""

# ---------------------------------------------------------------------------
# PROGRESS NOTE — General population (general)
# NLP targets: mixed positive mentions, negated conditions, uncertainty
# ---------------------------------------------------------------------------

PN_GENERAL_1 = """\
PROGRESS NOTE — ACUTE CARE VISIT

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Provider: Dr. {provider}

CHIEF COMPLAINT
Cough and low-grade fever for 5 days.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with no significant past medical history presenting \
with a 5-day history of productive cough with yellow-green sputum, low-grade fever \
up to 38.2°C, and rhinorrhea. {he_she.capitalize()} denies shortness of breath at rest \
or with exertion. No hemoptysis. {he_she.capitalize()} has not required any \
hospitalizations for respiratory illness in the past.

REVIEW OF SYSTEMS
POSITIVE: Cough, nasal congestion, mild sore throat, low-grade fever, myalgia.
NEGATIVE: No shortness of breath. No chest pain. No wheezing. No rash. No diarrhea. \
No dysuria. Denies diabetes mellitus. No known asthma or COPD. Denies tobacco use.

MEDICATIONS: None

ALLERGIES: No known drug allergies.

VITAL SIGNS
Temp 37.9°C | BP {systolic}/{diastolic} mmHg | HR {hr} bpm | SpO2 97% on room air | \
Weight {weight} kg | BMI {bmi} kg/m²

PHYSICAL EXAMINATION
General: Alert, mild distress. Oropharynx: Mild erythema, no tonsillar exudate. \
Cervical lymphadenopathy: Small, tender anterior cervical nodes bilaterally. \
Pulmonary: Mild scattered expiratory rhonchi bilaterally, clearing with cough. \
No focal consolidation. No wheezing.

ASSESSMENT AND PLAN
1. Acute upper respiratory infection / community-acquired bronchitis — \
   Clinical picture is most consistent with viral bronchitis. \
   No evidence of bacterial pneumonia on clinical examination. \
   Chest X-ray not ordered at this time — low pretest probability for pneumonia. \
   Symptomatic treatment: guaifenesin, saline nasal rinse, rest, and hydration. \
   Patient advised to return if dyspnea develops, fever persists >5 more days, \
   or cough worsens.
2. Rule out early pneumonia — return precautions discussed. If symptoms not improving \
   in 72 hours, patient should return for chest radiograph.

No antibiotics indicated at this time. Patient counseled on expected viral course.
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. History & Physical Notes

# COMMAND ----------

# ---------------------------------------------------------------------------
# H&P — T2DM patient with comorbidities (t2dm_only)
# NLP targets: positive T2DM + hypertension; family history CVD + diabetes;
#              historical foot ulcer; negated retinopathy
# ---------------------------------------------------------------------------

HP_T2DM_ONLY_1 = """\
HISTORY AND PHYSICAL

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Admitting Provider: Dr. {provider}
Facility: {facility}

CHIEF COMPLAINT
Poorly controlled blood sugar and elective surgical pre-operative assessment.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with a 12-year history of Type 2 diabetes mellitus \
currently treated with metformin 500 mg twice daily and glipizide 5 mg twice daily. \
{he_she.capitalize()} presents for pre-operative medical evaluation ahead of elective \
right total knee arthroplasty. {his_her.capitalize()} most recent HbA1c was {hba1c}%, \
which is above {his_her} goal of 7.5%. {he_she.capitalize()} denies acute illness.

PAST MEDICAL HISTORY
  1. Type 2 diabetes mellitus (diagnosed age {age_at_dx})
  2. Essential hypertension
  3. Hyperlipidemia
  4. Osteoarthritis, bilateral knees (right > left)
  5. History of right great toe ulcer (fully healed, 3 years prior — Grade 1 Wagner)

PAST SURGICAL HISTORY
  1. Appendectomy (age 32)
  2. Cholecystectomy (laparoscopic, 7 years ago)

FAMILY HISTORY
  - Father: Type 2 diabetes, hypertension, died of myocardial infarction at age 71
  - Mother: Alive, age 84, hypertension, osteoporosis
  - Sibling: One brother with Type 2 diabetes

SOCIAL HISTORY
Former smoker — quit 10 years ago (approximately 15 pack-year history). \
Occasional alcohol. No illicit drug use. Retired.

MEDICATIONS
  1. Metformin 500 mg PO BID
  2. Glipizide 5 mg PO BID
  3. Lisinopril 10 mg PO daily
  4. Atorvastatin 40 mg PO nightly

ALLERGIES: Penicillin — rash (moderate)

REVIEW OF SYSTEMS
POSITIVE: Right knee pain limiting ambulation. Fatigue. Nocturia x2.
NEGATIVE: No chest pain. No dyspnea at rest or on exertion. No palpitations. \
No hypoglycemic episodes in the past 3 months. Denies blurred vision — \
no known diabetic retinopathy. No current foot ulcers or skin breakdown. \
No lower extremity edema.

PHYSICAL EXAMINATION
VITAL SIGNS: BP {systolic}/{diastolic} mmHg | HR {hr} bpm | \
Weight {weight} kg | BMI {bmi} kg/m²
General: Alert, obese, no acute distress.
HEENT: Normal.
Cardiovascular: Regular rate and rhythm. No murmurs. Peripheral pulses intact bilaterally.
Pulmonary: Clear to auscultation bilaterally.
Abdomen: Soft, non-tender, non-distended. No organomegaly.
Extremities: Right knee with medial joint line tenderness, crepitus, and reduced range \
of motion (0-95° flexion). Left knee with mild crepitus only. No lower extremity edema. \
Bilateral dorsalis pedis and posterior tibial pulses palpable. Sensation intact \
to 10g monofilament bilaterally. No active ulceration.

LABORATORY (TODAY)
HbA1c: {hba1c}% | Fasting glucose: {glucose} mg/dL | Creatinine: {creatinine} mg/dL | \
LDL: {ldl} mg/dL | CBC within normal limits

ASSESSMENT AND PLAN
1. Type 2 diabetes mellitus, suboptimally controlled — HbA1c {hba1c}%. \
   Surgery should ideally proceed with HbA1c <8%; current level is acceptable. \
   Hold metformin 48 hours prior to surgery (contrast risk). Hold glipizide morning \
   of surgery.
2. Hypertension — controlled. Continue antihypertensives perioperatively.
3. Pre-operative cardiac clearance — low risk by Revised Cardiac Risk Index (RCRI = 1). \
   No further cardiac workup indicated at this time.

Cleared for elective surgery pending anesthesia evaluation.
"""

# ---------------------------------------------------------------------------
# H&P — General patient, including negation and uncertainty (general)
# NLP targets: positive GERD; negated diabetes, cancer, CVD;
#              uncertain etiology abdominal pain; family history colon cancer
# ---------------------------------------------------------------------------

HP_GENERAL_1 = """\
HISTORY AND PHYSICAL

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Provider: Dr. {provider}

CHIEF COMPLAINT
Epigastric pain, 3-week duration.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} presenting with a 3-week history of intermittent \
epigastric burning pain, worse after meals and when lying flat. {he_she.capitalize()} \
describes the pain as 5/10, non-radiating, associated with regurgitation of sour fluid. \
No dysphagia. No odynophagia. No melena or hematochezia. No involuntary weight loss. \
{he_she.capitalize()} tried over-the-counter omeprazole 20 mg for 1 week with partial \
improvement. {he_she.capitalize()} denies NSAID use.

PAST MEDICAL HISTORY
  None significant.

PAST SURGICAL HISTORY
  Tonsillectomy (childhood).

FAMILY HISTORY
  Father: Colon cancer (diagnosed age 62, deceased).
  Mother: Alive, hypertension, hypothyroidism.
  No family history of esophageal cancer or Barrett's esophagus known.

SOCIAL HISTORY
No tobacco use. Drinks 1-2 glasses of wine per week. No illicit substances. Works as \
a software engineer. Reports high work-related stress.

MEDICATIONS
  1. Omeprazole 20 mg PO daily (started 1 week ago, OTC)

ALLERGIES: No known drug allergies.

REVIEW OF SYSTEMS
POSITIVE: Epigastric burning, regurgitation, occasional nausea.
NEGATIVE: No chest pain or pressure. No shortness of breath. No palpitations. \
Denies diabetes mellitus or history of high blood sugar. No polyuria or polydipsia. \
No jaundice. No hematemesis or melena. Denies weight loss. No fever or chills. \
No diarrhea or constipation change. No blood in stool.

VITAL SIGNS
BP {systolic}/{diastolic} mmHg | HR {hr} bpm | \
Weight {weight} kg | BMI {bmi} kg/m²

PHYSICAL EXAMINATION
General: Alert, in no distress, well-appearing.
Abdominal: Soft. Mild epigastric tenderness to deep palpation. No rigidity. \
No rebound. No palpable masses. No hepatosplenomegaly. Bowel sounds normal.
Rectal: Deferred.

ASSESSMENT AND PLAN
1. Gastroesophageal reflux disease (GERD) — most likely diagnosis given symptom pattern \
   and partial response to PPI. Initiate omeprazole 20 mg PO twice daily for 8 weeks. \
   Lifestyle counseling: avoid late evening meals, elevate head of bed, reduce alcohol.
2. Rule out H. pylori — send H. pylori stool antigen. If positive, initiate \
   triple therapy per guidelines.
3. Rule out peptic ulcer disease — if symptoms fail to resolve after 8 weeks of PPI \
   therapy, upper endoscopy will be warranted.
4. Colorectal cancer screening — family history of colon cancer in first-degree relative \
   under age 65. Recommend colonoscopy in the next 12 months (earlier than standard \
   age 45 guideline given family history).

Follow-up in 8 weeks; sooner if symptoms worsen.
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Consult Notes

# COMMAND ----------

# ---------------------------------------------------------------------------
# CONSULT NOTE — Cardiology for risk stratification (t2dm_cvd)
# NLP targets: positive CAD, CHF; uncertain new symptoms;
#              family history premature CAD; negated prior MI
# ---------------------------------------------------------------------------

CN_CARDIOLOGY_1 = """\
CARDIOLOGY CONSULTATION NOTE

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Consulting Provider: Dr. {provider}
Requesting Service: Internal Medicine
Reason for Consult: Evaluation of exertional dyspnea and pre-operative cardiac risk \
assessment in a patient with Type 2 diabetes and multiple cardiovascular risk factors.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with a 10-year history of Type 2 diabetes mellitus \
on metformin 500 mg BID, essential hypertension, and hyperlipidemia who presents \
for pre-operative cardiac risk stratification. {he_she.capitalize()} reports new-onset \
exertional dyspnea over the past 4 months, limiting {his_her} activity to one flight \
of stairs before needing to rest. No known history of myocardial infarction. \
No prior coronary artery catheterization. {he_she.capitalize()} has not had an \
echocardiogram in the past 3 years.

CARDIOVASCULAR RISK FACTORS
  - Type 2 diabetes mellitus (10 years)
  - Essential hypertension
  - Hyperlipidemia (LDL {ldl} mg/dL on atorvastatin)
  - Former smoker (quit 5 years ago, 20 pack-year history)
  - Family history: father with premature coronary artery disease (MI at age 55)
  - Male sex and age >55

REVIEW OF SYSTEMS
POSITIVE: Exertional dyspnea (NYHA Class II). Occasional mild ankle swelling \
in the evenings.
NEGATIVE: No chest pain at rest. No orthopnea or paroxysmal nocturnal dyspnea. \
No syncope or presyncope. Denies palpitations. No claudication. \
No known prior myocardial infarction. Patient denies prior cardiac catheterization.

CURRENT MEDICATIONS
  1. Metformin 500 mg PO BID
  2. Lisinopril 20 mg PO daily
  3. Atorvastatin 40 mg PO nightly
  4. Aspirin 81 mg PO daily

VITAL SIGNS
BP {systolic}/{diastolic} mmHg | HR {hr} bpm | Weight {weight} kg | BMI {bmi} kg/m²

PHYSICAL EXAMINATION
Cardiovascular: Regular rate and rhythm. Distant heart sounds. No S3 or S4. \
No significant murmur. JVP normal. No carotid bruits.
Pulmonary: Mild bibasilar crackles — uncertain clinical significance in the \
setting of exertional symptoms; may represent early pulmonary congestion vs \
atelectasis.
Extremities: 1+ pitting edema bilateral ankles.

ASSESSMENT AND PLAN
1. Exertional dyspnea — etiology uncertain at this time. Differential includes \
   early coronary artery disease with ischemia, early diastolic dysfunction \
   in the setting of hypertension and diabetes, or deconditioning.
2. Pre-operative cardiac risk — RCRI score = 2 (insulin-dependent diabetes, \
   though {name} is not insulin-dependent; adjusting to 1 for metformin use + \
   planned major procedure). Recommend stress echocardiogram to evaluate for \
   inducible ischemia and assess left ventricular function prior to proceeding \
   with surgery.
3. If stress echo demonstrates reduced EF or ischemia, cardiac catheterization \
   may be warranted before elective surgery.

Will follow up after stress echocardiogram results are available.
"""

# ---------------------------------------------------------------------------
# CONSULT NOTE — Endocrinology for diabetes optimization (t2dm_alt_med)
# NLP targets: positive T2DM; negated metformin (contraindicated);
#              hypothetical future insulin; historical pancreatitis
# ---------------------------------------------------------------------------

CN_ENDO_1 = """\
ENDOCRINOLOGY CONSULTATION NOTE

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Consulting Provider: Dr. {provider}
Requesting Service: Nephrology
Reason for Consult: Diabetes management in the setting of stage 3b chronic \
kidney disease where metformin is contraindicated.

HISTORY OF PRESENT ILLNESS
{name} is a {age}-year-old {sex} with a 15-year history of Type 2 diabetes mellitus, \
now complicated by chronic kidney disease (CKD stage 3b, eGFR 36 mL/min/1.73m²) \
and hypertension who is referred for optimization of diabetes management. \
Metformin was appropriately discontinued 6 months ago given eGFR <45. \
{he_she.capitalize()} was transitioned to sitagliptin (Januvia) 50 mg daily but \
HbA1c has risen from 7.8% to {hba1c}% over the past 6 months. \
{he_she.capitalize()} is not currently on insulin.

RELEVANT HISTORY
History of acute pancreatitis 3 years ago (attributed to hypertriglyceridemia, \
not alcohol-related). This creates a relative contraindication to GLP-1 receptor \
agonists and DPP-4 inhibitors given uncertainty about mechanism; however, current \
evidence does not establish a causal link between these agents and pancreatitis, \
and the risk-benefit profile may still favor their use.

REVIEW OF SYSTEMS
POSITIVE: Fatigue, polyuria, blurred vision (new, 2 weeks — referred to ophthalmology).
NEGATIVE: No hypoglycemia. No abdominal pain. No nausea or vomiting. \
No foot ulcers or wounds. {he_she.capitalize()} is not currently on metformin \
and has not taken it in 6 months.

MEDICATIONS
  1. Sitagliptin (Januvia) 50 mg PO daily (renally dosed)
  2. Lisinopril 10 mg PO daily
  3. Furosemide 20 mg PO daily
  4. Atorvastatin 20 mg PO nightly

VITAL SIGNS
BP {systolic}/{diastolic} mmHg | HR {hr} bpm | Weight {weight} kg | BMI {bmi} kg/m²

LABORATORY
HbA1c: {hba1c}% | Fasting glucose: {glucose} mg/dL | Creatinine: {creatinine} mg/dL \
eGFR: 36 mL/min/1.73m² | Urine ACR: 220 mg/g (moderately elevated)

ASSESSMENT AND PLAN
1. Type 2 diabetes mellitus, suboptimally controlled in the setting of CKD 3b. \
   Metformin contraindicated and appropriately held. Sitagliptin appropriately \
   renally dosed.
2. Recommend adding a SGLT2 inhibitor — specifically canagliflozin or \
   empagliflozin, both of which have demonstrated renal-protective and \
   cardiovascular-protective effects in trials and are labeled for use \
   with eGFR ≥30.
3. If HbA1c remains above 8.5% despite SGLT2 inhibitor, will consider \
   initiating basal insulin (insulin glargine). Patient counseled on \
   hypothetical scenario of insulin initiation and expressed willingness.
4. GLP-1 receptor agonist — relative contraindication given history of \
   pancreatitis; will defer for now pending further evidence.

Follow-up in 8 weeks with repeat HbA1c and CMP.
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. User-Provided Clinical Note Samples
# MAGIC
# MAGIC Three note types supplied by the clinical team. Expanded into full templates
# MAGIC with {variable} substitution while preserving the original clinical language verbatim.

# COMMAND ----------

# ---------------------------------------------------------------------------
# H&P — New Patient Presentation, Undiagnosed Diabetes (undiagnosed)
# Source: user-provided clinical note sample #1
# NLP targets: positive polydipsia, nocturia, fatigue, polyphagia, glycosuria;
#              uncertain T1DM vs T2DM; positive slow-healing wound;
#              negated prior diabetes diagnosis
# ---------------------------------------------------------------------------

HP_UNDIAGNOSED_1 = """\
HISTORY AND PHYSICAL — NEW PATIENT

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Provider: Dr. {provider}

CHIEF COMPLAINT
Excessive thirst, frequent urination, fatigue, and unintentional weight loss for 3 weeks.

SUBJECTIVE
Patient reports excessive thirst (polydipsia) and needing to urinate multiple times \
throughout the night (nocturia) for the past 3 weeks. Complains of generalized fatigue \
and unintentional 10-lb weight loss over the last month despite an increased appetite \
(polyphagia). {he_she.capitalize()} also notes blurry vision over the past week. \
No prior diagnosis of diabetes mellitus.

OBJECTIVE
Vital Signs: BP {systolic}/{diastolic} mmHg | HR {hr} bpm | \
Weight {weight} kg | BMI {bmi} kg/m²
General: Alert, appears fatigued, no acute distress.
HEENT: Visual acuity mildly reduced bilaterally. No papilledema.
Skin: Slow-healing laceration noted on the right great toe — approximately 1.5 cm, \
  wound bed granulating but progress slow. No signs of deep infection. \
  Surrounding skin warm; sensation intact to light touch.
Extremities: No peripheral edema. Bilateral dorsalis pedis pulses palpable.

LABORATORY AND DIAGNOSTICS
  Urine dipstick: Positive for significant glycosuria and ketones.
  Fasting blood glucose (point-of-care): {glucose} mg/dL.
  HbA1c (sent): Pending.
  Complete metabolic panel: Pending.

ASSESSMENT
New-onset hyperglycemia; rule out Type 1 vs. Type 2 Diabetes Mellitus. \
Clinical picture with age, BMI {bmi} kg/m², insidious onset, and glycosuria \
with ketones warrants further evaluation. Presence of ketones may indicate \
insulinopenic state but does not definitively distinguish T1DM from T2DM at this visit.

PLAN
1. Draw fasting HbA1c, C-peptide, GAD-65 antibodies, and anti-islet antibodies \
   to differentiate T1DM from T2DM.
2. Initiate IV fluids if clinically indicated pending labs.
3. Right great toe wound: clean and dress wound; refer to podiatry if no improvement \
   in 1 week.
4. Patient counseled on hyperglycemia symptoms and instructed to return immediately \
   if polyuria worsens, nausea develops, or {he_she} feels confused.
5. Ophthalmology referral for blurry vision — rule out early diabetic retinopathy \
   vs refractive change secondary to osmotic lens shift.

Follow-up within 48-72 hours after lab results available.
"""

# ---------------------------------------------------------------------------
# PROGRESS NOTE — Routine Follow-Up / Monitoring, Established T2DM (t2dm_only)
# Source: user-provided clinical note sample #2
# NLP targets: positive peripheral neuropathy; positive T2DM; positive metformin;
#              negated retinopathy; negated severe hypoglycemia
# ---------------------------------------------------------------------------

PN_T2DM_FOLLOWUP_1 = """\
PROGRESS NOTE — DIABETES MONITORING

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Provider: Dr. {provider}

CHIEF COMPLAINT
Established Type 2 Diabetes Mellitus — routine monitoring visit.

SUBJECTIVE
Patient reports some tingling and numbness in bilateral feet (peripheral neuropathy) \
primarily at night. {he_she.capitalize()} is adherent to current medication regimen \
(Metformin 1000 mg BID), with no episodes of severe hypoglycemia. \
{he_she.capitalize()} denies chest pain, shortness of breath, or lower extremity edema. \
Home blood glucose readings average 130-150 mg/dL fasting per {his_her} log.

OBJECTIVE
Vital Signs: BP {systolic}/{diastolic} mmHg | HR {hr} bpm | \
Weight {weight} kg | BMI {bmi} kg/m²
Neurological: Reduced vibratory sensation bilateral distal lower extremities. \
Monofilament (10g) sensation reduced at first metatarsal heads bilaterally. \
Pedal pulses palpable bilaterally. No foot ulcers.
Ophthalmologic (funduscopic): Funduscopic exam shows no signs of diabetic retinopathy.

LABORATORY
HbA1c: {hba1c}% (at goal for this patient: target <7.5%)
Microalbuminuria test ordered to screen for nephropathy (results pending).
Fasting glucose: {glucose} mg/dL
Creatinine: {creatinine} mg/dL | eGFR adequate for continuation of Metformin

ASSESSMENT
Type 2 Diabetes Mellitus with early-stage peripheral neuropathy. \
No evidence of diabetic retinopathy on funduscopic exam today. \
Glycemic control at goal on current regimen.

PLAN
1. Continue current pharmacological management: Metformin 1000 mg BID. \
   No dose adjustment indicated.
2. Emphasize tight glycemic control to slow neuropathy progression.
3. Refer to neurology for formal nerve conduction study to characterize \
   neuropathy severity.
4. Prescribe gabapentin 100 mg PO TID for symptomatic neuropathic pain — \
   titrate as tolerated.
5. Annual dilated eye exam — schedule with ophthalmology.
6. Await microalbuminuria result; if elevated, add ACE inhibitor for renoprotection.
7. Foot care education reinforced. Podiatry referral placed for regular nail care \
   and protective footwear evaluation.

Return to clinic in 3 months with repeat HbA1c and CMP.
"""

# ---------------------------------------------------------------------------
# PROGRESS NOTE — Asymptomatic / Prediabetes, Incidental Finding (prediabetes)
# Source: user-provided clinical note sample #3
# NLP targets: negated fatigue, polyuria, polydipsia; positive prediabetes;
#              family history T2DM (mother); positive lifestyle counseling
# ---------------------------------------------------------------------------

PN_PREDIABETES_1 = """\
PROGRESS NOTE — ANNUAL WELLNESS VISIT / PREDIABETES COUNSELING

Date: {service_date}    Patient: {name}    MRN: {mrn}
Age: {age}    Sex: {sex}    Provider: Dr. {provider}

CHIEF COMPLAINT
Annual wellness visit; abnormal fasting glucose on routine labs.

SUBJECTIVE
Patient denies fatigue, polyuria, or polydipsia. {he_she.capitalize()} is asymptomatic. \
Family history is positive for Type 2 Diabetes Mellitus in {his_her} mother. \
No prior history of diabetes mellitus or gestational diabetes. \
{he_she.capitalize()} reports a sedentary lifestyle and a diet high in refined carbohydrates.

OBJECTIVE
Vital Signs: BP {systolic}/{diastolic} mmHg | HR {hr} bpm | \
Weight {weight} kg | BMI {bmi} kg/m²
General: Well-appearing, no acute distress.
Physical exam: Within normal limits. No acanthosis nigricans noted.

LABORATORY
Fasting Plasma Glucose (FPG): {glucose} mg/dL
HbA1c: {hba1c}%
(Reference: Prediabetes defined as FPG 100-125 mg/dL or HbA1c 5.7-6.4%)

ASSESSMENT
Prediabetes. Incidentally identified on routine laboratory screening. \
No symptoms of diabetes mellitus at this time. Patient has multiple risk factors \
for progression to Type 2 Diabetes Mellitus: family history (mother), \
BMI {bmi} kg/m², and sedentary lifestyle.

PLAN
1. Counseled extensively on lifestyle modifications: structured weight loss program \
   targeting 5-7% body weight reduction, minimum 150 minutes moderate-intensity \
   aerobic exercise per week, and dietary changes (Mediterranean or low-glycemic diet).
2. Refer to Diabetes Prevention Program (DPP) — evidence-based structured \
   lifestyle intervention; proven to reduce progression to T2DM by ~58%.
3. Metformin not initiated at this time; lifestyle modification trial first.
4. Repeat FPG and HbA1c in 6 months to monitor for progression.
5. Patient educated on warning signs of diabetes: polydipsia, polyuria, unexplained \
   weight loss, blurry vision. Instructed to return sooner if symptoms develop.

Follow-up in 6 months with repeat fasting labs.
"""

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Notes Library (for use by the generator)

# COMMAND ----------

NOTES_LIBRARY = {
    "discharge_summary": {
        "t2dm_cvd": [
            DS_T2DM_CVD_1,
            DS_T2DM_CVD_2,
        ],
        "t2dm_only": [
            DS_T2DM_ONLY_1,
        ],
        "general": [
            DS_T2DM_ONLY_1,   # fallback; add general DS templates here as needed
        ],
    },
    "progress": {
        "t2dm_cvd": [
            PN_T2DM_CVD_1,
        ],
        "t2dm_only": [
            PN_T2DM_ONLY_1,
            PN_T2DM_FOLLOWUP_1,   # user-provided: routine follow-up with neuropathy
        ],
        "t2dm_alt_med": [
            PN_T2DM_ONLY_1,       # reuses T2DM note; generator substitutes different meds
        ],
        "hypertension": [
            PN_HTN_1,
        ],
        "prediabetes": [
            PN_PREDIABETES_1,     # user-provided: asymptomatic prediabetes catch
        ],
        "general": [
            PN_GENERAL_1,
        ],
    },
    "hp": {
        "undiagnosed": [
            HP_UNDIAGNOSED_1,     # user-provided: new patient presentation, rule-out DM
        ],
        "t2dm_only": [
            HP_T2DM_ONLY_1,
        ],
        "t2dm_cvd": [
            HP_T2DM_ONLY_1,       # extended by generator with CVD history
        ],
        "general": [
            HP_GENERAL_1,
        ],
        "hypertension": [
            HP_GENERAL_1,         # reuses general H&P; generator swaps chief complaint
        ],
    },
    "consult": {
        "t2dm_cvd": [
            CN_CARDIOLOGY_1,
        ],
        "t2dm_alt_med": [
            CN_ENDO_1,
        ],
        "general": [
            CN_CARDIOLOGY_1,      # fallback
        ],
    },
}

# Convenience: flat list of all templates for quick inspection
ALL_TEMPLATES = [t for cat in NOTES_LIBRARY.values() for pheno in cat.values() for t in pheno]

print(f"Notes library loaded: {len(NOTES_LIBRARY)} categories, {len(ALL_TEMPLATES)} total templates.")
print()
for cat, phenotypes in NOTES_LIBRARY.items():
    n = sum(len(v) for v in phenotypes.values())
    print(f"  {cat:<20s}  {n} templates  ({', '.join(phenotypes.keys())})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. NLP Entity Expectations (for test validation)
# MAGIC
# MAGIC Expected entities the NLP pipeline should extract from these notes.
# MAGIC Used to validate that the NLP layer is working correctly.
# MAGIC
# MAGIC | Entity | certainty | negation | temporality | Subject | Source notes |
# MAGIC |---|---|---|---|---|---|
# MAGIC | Type 2 diabetes mellitus (E11.9) | positive | false | current | patient | All t2dm_* |
# MAGIC | Metformin (RxNorm 860975) | positive | false | current | patient | t2dm_cvd, t2dm_only |
# MAGIC | Coronary artery disease (I25.10) | positive | false | current | patient | t2dm_cvd |
# MAGIC | Heart failure (I50.9) | positive | false | current | patient | t2dm_cvd |
# MAGIC | Pulmonary embolism | positive | **true** | current | patient | DS_T2DM_CVD_1 |
# MAGIC | Myocardial infarction | positive | **true** | current | patient | DS_T2DM_CVD_1 |
# MAGIC | Chest pain | positive | **true** | current | patient | multiple |
# MAGIC | Coronary artery disease | positive | false | **family** | family | DS_T2DM_CVD_1, PN_HTN_1, HP_T2DM_ONLY_1 |
# MAGIC | Type 2 diabetes mellitus | positive | false | **family** | family | DS_T2DM_ONLY_1 |
# MAGIC | Foot ulcer | positive | false | **historical** | patient | DS_T2DM_ONLY_1, HP_T2DM_ONLY_1 |
# MAGIC | Pneumonia | positive | **true** | current | patient | DS_T2DM_CVD_1 |
# MAGIC | Diabetes mellitus | positive | **true** | current | patient | PN_HTN_1, HP_GENERAL_1 |
# MAGIC | Pancreatitis (historical) | positive | false | **historical** | patient | CN_ENDO_1 |
# MAGIC | Insulin (hypothetical) | positive | false | **hypothetical** | patient | CN_ENDO_1 |
# MAGIC | Peptic ulcer / pneumonia (rule-out) | positive | false | **uncertain** | patient | HP_GENERAL_1, PN_GENERAL_1 |
# MAGIC | Polydipsia / nocturia / polyphagia | positive | false | current | patient | HP_UNDIAGNOSED_1 |
# MAGIC | Type 1 / Type 2 DM (rule-out) | positive | false | **uncertain** | patient | HP_UNDIAGNOSED_1 |
# MAGIC | Diabetic retinopathy | positive | **true** | current | patient | PN_T2DM_FOLLOWUP_1 |
# MAGIC | Peripheral neuropathy | positive | false | current | patient | PN_T2DM_FOLLOWUP_1 |
# MAGIC | Severe hypoglycemia | positive | **true** | current | patient | PN_T2DM_FOLLOWUP_1 |
# MAGIC | Fatigue / polyuria / polydipsia | positive | **true** | current | patient | PN_PREDIABETES_1 |
# MAGIC | Type 2 diabetes mellitus | positive | false | **family** | family | PN_PREDIABETES_1 |
# MAGIC | Prediabetes | positive | false | current | patient | PN_PREDIABETES_1 |
