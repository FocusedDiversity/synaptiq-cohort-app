"""
Central configuration — schema names, table references, and app settings.
All SQL queries import from here so a schema rename is a one-line change.
"""

# ---------------------------------------------------------------
# Unity Catalog topology
# ---------------------------------------------------------------
CATALOG       = "dev"
SILVER_SCHEMA = "test_silver_ehr_clinical"
GOLD_SCHEMA   = "test_gold_ehr_cohort"

def _t(schema: str, table: str) -> str:
    return f"`{CATALOG}`.`{schema}`.`{table}`"

# Silver tables
T_PATIENT          = _t(SILVER_SCHEMA, "patient")
T_ENCOUNTER        = _t(SILVER_SCHEMA, "encounter")
T_CONDITION        = _t(SILVER_SCHEMA, "condition")
T_OBSERVATION      = _t(SILVER_SCHEMA, "observation")
T_MEDICATION_ORDER = _t(SILVER_SCHEMA, "medication_order")
T_PROCEDURE        = _t(SILVER_SCHEMA, "procedure")
T_CLINICAL_NOTE    = _t(SILVER_SCHEMA, "clinical_note")
T_NLP_RUN          = _t(SILVER_SCHEMA, "nlp_run")
T_NLP_ENTITY       = _t(SILVER_SCHEMA, "note_nlp_entity")

# Gold tables
T_COHORT_DEF     = _t(GOLD_SCHEMA, "cohort_definition")
T_COHORT_MEMBER  = _t(GOLD_SCHEMA, "cohort_member")
T_PATIENT_FEATURE= _t(GOLD_SCHEMA, "patient_feature")

# ---------------------------------------------------------------
# Cohort classification value sets
# ---------------------------------------------------------------
COHORT_TYPES = {
    "condition":      "Disease / Condition — patients sharing a clinical diagnosis",
    "exposure":       "Exposure — patients on a specific drug, procedure, or intervention",
    "control":        "Control — patients WITHOUT the condition/exposure (comparator arm)",
    "operational":    "Operational — high-cost, risk stratification, care management",
    "administrative": "Administrative — trial recruitment, quality reporting, billing",
}

COHORT_CATEGORIES = {
    "retrospective": "Retrospective — built from historical EHR data",
    "prospective":   "Prospective — defined on current criteria; captures new data over time",
}

COHORT_STATUSES = ["draft", "active", "archived"]

# ---------------------------------------------------------------
# App settings
# ---------------------------------------------------------------
APP_TITLE      = "Synaptiq Cohort Builder"
APP_ICON       = "🏥"
APP_VERSION    = "0.1.0 — POC"
PAGE_SIZE      = 50       # rows per table display
MAX_EXPORT     = 10_000   # max rows for CSV export
