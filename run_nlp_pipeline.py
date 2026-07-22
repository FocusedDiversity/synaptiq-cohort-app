# Databricks notebook source
# MAGIC %md
# MAGIC # Synaptiq NLP Extraction Pipeline
# MAGIC
# MAGIC Extracts clinical entities from `clinical_note.note_text` using the Claude API
# MAGIC and writes results to `note_nlp_entity` + one `nlp_run` record per execution.
# MAGIC
# MAGIC **Attributes extracted per entity:**
# MAGIC | Attribute | Values | Purpose |
# MAGIC |---|---|---|
# MAGIC | `negation` | true / false | Exclude "no diabetes", "denies chest pain" |
# MAGIC | `certainty` | positive / uncertain / hypothetical / negated | Filter unconfirmed findings |
# MAGIC | `temporality` | current / historical / family | Exclude past and family history |
# MAGIC | `subject` | patient / family / other | Exclude "mother has T2DM" |
# MAGIC
# MAGIC **Run order:** DDL → `generate_ehr_silver.py` → this notebook
# MAGIC
# MAGIC **Resume-safe:** notes already present in `note_nlp_entity` are skipped.

# COMMAND ----------

# MAGIC %md ## Section 1 — Configuration

# COMMAND ----------

import datetime

# ── Target catalog / schema ────────────────────────────────────────────────
CATALOG       = "dev"
SILVER_SCHEMA = "test_silver_ehr_clinical"

# ── Claude model ───────────────────────────────────────────────────────────
# claude-haiku-4-5   →  fastest / cheapest  (good for POC)
# claude-sonnet-5    →  higher accuracy      (recommended for production)
MODEL_NAME    = "claude-haiku-4-5"
MAX_TOKENS    = 16000       # max tokens in Claude response per note
                            # (2048 truncated entity-rich notes → invalid JSON)

# ── Pipeline knobs ─────────────────────────────────────────────────────────
BATCH_SIZE        = 50      # notes per Delta write batch
MAX_NOTES         = None    # set to an int (e.g. 100) to limit for testing; None = all
SLEEP_BETWEEN_S   = 0.3     # seconds between API calls (rate-limit safety margin)

# ── Databricks secret scope / key for Anthropic API key ───────────────────
SECRET_SCOPE = "synaptiq"
SECRET_KEY   = "anthropic_api_key"

# COMMAND ----------

# MAGIC %md ## Section 2 — Imports & API client

# COMMAND ----------

# MAGIC %pip install --upgrade typing_extensions anthropic -q

# COMMAND ----------

import anthropic
import json
import time
import traceback
import pandas as pd
from pyspark.sql import functions as F

# Retrieve API key from Databricks Secrets
api_key = dbutils.secrets.get(scope=SECRET_SCOPE, key=SECRET_KEY)
client  = anthropic.Anthropic(api_key=api_key)

print(f"Anthropic SDK version : {anthropic.__version__}")
print(f"Model                 : {MODEL_NAME}")
print(f"Batch size            : {BATCH_SIZE}")
print(f"Max notes             : {MAX_NOTES or 'all unprocessed'}")

# COMMAND ----------

# MAGIC %md ## Section 3 — Load unprocessed notes

# COMMAND ----------

T_NOTE   = f"`{CATALOG}`.`{SILVER_SCHEMA}`.`clinical_note`"
T_ENTITY = f"`{CATALOG}`.`{SILVER_SCHEMA}`.`note_nlp_entity`"
T_RUN    = f"`{CATALOG}`.`{SILVER_SCHEMA}`.`nlp_run`"

# Notes that have not yet been processed by ANY nlp_run
unprocessed_df = spark.sql(f"""
    SELECT
        n.note_sk,
        n.patient_sk,
        n.encounter_sk,
        n.note_text,
        n.note_category,
        n.note_type_display
    FROM {T_NOTE} n
    WHERE n.note_text IS NOT NULL
      AND n.note_sk NOT IN (
          SELECT DISTINCT note_sk FROM {T_ENTITY}
      )
    ORDER BY n.note_sk
""")

if MAX_NOTES:
    unprocessed_df = unprocessed_df.limit(MAX_NOTES)

notes = unprocessed_df.toPandas()
print(f"Notes to process: {len(notes):,}")

# COMMAND ----------

# MAGIC %md ## Section 4 — Extraction prompt

# COMMAND ----------

SYSTEM_PROMPT = """You are a clinical NLP system. Extract all clinically relevant entities from the note.

Attribute semantics:
- covered_text    : the exact text span from the note (verbatim)
- span_start/end  : character offsets of covered_text in the note (null if unsure)
- concept_code    : best-fit code (ICD-10-CM for problems, RxNorm for medications, LOINC for labs, SNOMED-CT for findings/anatomy, CPT for procedures). Use null if unknown.
- negation        : true if negated ("no diabetes", "denies", "ruled out")
- certainty       : positive    = confirmed, definite assertion
                    uncertain   = "possible", "rule out", "cannot exclude", "suspected"
                    hypothetical = "if this is X", "should X develop"
                    negated     = explicitly denied
- temporality     : current    = active or present condition/finding
                    historical = past history ("history of", "prior", "previous", "former")
                    family     = family member's condition ("mother has", "family history of")
- subject         : patient = pertains to the patient being documented
                    family  = pertains to a family member
                    other   = pertains to another person
- confidence      : your confidence score as a float 0.0–1.0

If no entities are found, return an empty entities array."""

# JSON schema enforced via structured outputs — the API guarantees the response
# text is valid JSON matching this shape, so no fence-stripping or repair needed.
ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity_type":     {"type": "string", "enum": ["problem", "medication", "procedure", "lab", "anatomy", "finding"]},
                    "covered_text":    {"type": "string"},
                    "span_start":      {"type": ["integer", "null"]},
                    "span_end":        {"type": ["integer", "null"]},
                    "concept_code":    {"type": ["string", "null"]},
                    "concept_system":  {"type": ["string", "null"], "enum": ["ICD-10-CM", "RxNorm", "LOINC", "SNOMED-CT", "CPT", None]},
                    "concept_display": {"type": ["string", "null"]},
                    "negation":        {"type": "boolean"},
                    "certainty":       {"type": "string", "enum": ["positive", "uncertain", "hypothetical", "negated"]},
                    "temporality":     {"type": "string", "enum": ["current", "historical", "family"]},
                    "subject":         {"type": "string", "enum": ["patient", "family", "other"]},
                    "confidence":      {"type": "number", "description": "Confidence score 0.0-1.0"},
                },
                "required": ["entity_type", "covered_text", "span_start", "span_end",
                             "concept_code", "concept_system", "concept_display",
                             "negation", "certainty", "temporality", "subject", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entities"],
    "additionalProperties": False,
}


def extract_entities(note_text: str, note_category: str) -> list[dict] | None:
    """Call Claude and return a list of entity dicts, or None on failure.

    None (failure) vs [] (genuinely no entities) matters: failed notes write no
    rows, so the resume-safe NOT IN query picks them up again on the next run.
    """
    user_msg = f"NOTE CATEGORY: {note_category}\n\nNOTE TEXT:\n{note_text}"
    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": ENTITY_SCHEMA}},
            messages=[{"role": "user", "content": user_msg}],
        )
        if response.stop_reason == "max_tokens":
            print(f"  [WARN] response truncated at {MAX_TOKENS} tokens — skipping note")
            return None
        if response.stop_reason == "refusal":
            print("  [WARN] model declined this note — skipping")
            return None
        raw = next((b.text for b in response.content if b.type == "text"), "")
        return json.loads(raw)["entities"]
    except json.JSONDecodeError as je:
        print(f"  [WARN] JSON parse failed: {je}")
        print(f"  [DEBUG] raw response (first 500 chars): {repr(raw[:500])}")
        return None
    except anthropic.RateLimitError:
        print("  [WARN] Rate limit hit — sleeping 30s")
        time.sleep(30)
        return extract_entities(note_text, note_category)  # one retry
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


# COMMAND ----------

# MAGIC %md ## Section 5 — Register nlp_run record

# COMMAND ----------

run_started_at = datetime.datetime.utcnow()

spark.sql(f"""
    INSERT INTO {T_RUN} (model_name, model_version, run_started_at, note_count)
    VALUES (
        '{MODEL_NAME}',
        'anthropic-sdk-{anthropic.__version__}',
        CAST('{run_started_at.isoformat()}' AS TIMESTAMP),
        {len(notes)}
    )
""")

nlp_run_sk = spark.sql(f"""
    SELECT nlp_run_sk FROM {T_RUN}
    ORDER BY run_started_at DESC
    LIMIT 1
""").collect()[0][0]

print(f"nlp_run_sk = {nlp_run_sk}")

# COMMAND ----------

# MAGIC %md ## Section 6 — Extract entities and write in batches

# COMMAND ----------

from pyspark.sql import types as T

# Explicit write schema — pandas/Spark type inference chokes on None values
# (e.g. a null encounter_sk becomes NaN and the column turns float).
ENTITY_SPARK_SCHEMA = T.StructType([
    T.StructField("note_sk",         T.LongType()),
    T.StructField("patient_sk",      T.LongType()),
    T.StructField("encounter_sk",    T.LongType()),
    T.StructField("nlp_run_sk",      T.LongType()),
    T.StructField("entity_type",     T.StringType()),
    T.StructField("covered_text",    T.StringType()),
    T.StructField("span_start",      T.IntegerType()),
    T.StructField("span_end",        T.IntegerType()),
    T.StructField("concept_code",    T.StringType()),
    T.StructField("concept_system",  T.StringType()),
    T.StructField("concept_display", T.StringType()),
    T.StructField("negation",        T.BooleanType()),
    T.StructField("certainty",       T.StringType()),
    T.StructField("temporality",     T.StringType()),
    T.StructField("subject",         T.StringType()),
    T.StructField("confidence",      T.DoubleType()),
])

all_entities = []
processed    = 0
errors       = 0

for idx, row in notes.iterrows():
    note_sk      = int(row["note_sk"])
    patient_sk   = int(row["patient_sk"])
    encounter_sk = int(row["encounter_sk"]) if pd.notna(row["encounter_sk"]) else None
    note_text    = str(row["note_text"])
    note_category= str(row["note_category"] or "unknown")

    entities = extract_entities(note_text, note_category)
    if entities is None:
        errors += 1
        print(f"  [ERROR] note_sk={note_sk} failed — no rows written; will retry next run")
        entities = []

    for ent in entities:
        # Validate and normalise mandatory fields
        certainty  = ent.get("certainty",  "positive")
        negation   = bool(ent.get("negation", False))
        # Keep certainty consistent with negation flag
        if negation and certainty == "positive":
            certainty = "negated"

        all_entities.append({
            "note_sk":        note_sk,
            "patient_sk":     patient_sk,
            "encounter_sk":   encounter_sk,
            "nlp_run_sk":     nlp_run_sk,
            "entity_type":    ent.get("entity_type"),
            "covered_text":   ent.get("covered_text"),
            "span_start":     ent.get("span_start"),
            "span_end":       ent.get("span_end"),
            "concept_code":   ent.get("concept_code"),
            "concept_system": ent.get("concept_system"),
            "concept_display":ent.get("concept_display"),
            "negation":       negation,
            "certainty":      certainty,
            "temporality":    ent.get("temporality", "current"),
            "subject":        ent.get("subject", "patient"),
            "confidence":     float(ent.get("confidence", 0.8)),
        })

    processed += 1

    # Write batch to Delta
    if len(all_entities) >= BATCH_SIZE or (processed == len(notes) and all_entities):
        batch_df = spark.createDataFrame(all_entities, schema=ENTITY_SPARK_SCHEMA)
        batch_df.write.format("delta").mode("append").saveAsTable(
            f"{CATALOG}.{SILVER_SCHEMA}.note_nlp_entity"
        )
        print(f"  Wrote {len(all_entities):>4} entities | notes processed: {processed:>5}/{len(notes)}")
        all_entities = []

    time.sleep(SLEEP_BETWEEN_S)

print(f"\nDone. {processed} notes processed, {errors} errors.")

# COMMAND ----------

# MAGIC %md ## Section 7 — Close nlp_run record

# COMMAND ----------

run_finished_at = datetime.datetime.utcnow()

spark.sql(f"""
    UPDATE {T_RUN}
    SET    run_finished_at = CAST('{run_finished_at.isoformat()}' AS TIMESTAMP)
    WHERE  nlp_run_sk = {nlp_run_sk}
""")

# Summary
summary = spark.sql(f"""
    SELECT
        entity_type,
        COUNT(*)                                        AS n_entities,
        ROUND(AVG(confidence), 3)                       AS avg_confidence,
        SUM(CAST(negation AS INT))                      AS n_negated,
        COUNT(DISTINCT CASE WHEN temporality = 'family'
                            THEN entity_sk END)         AS n_family_history,
        COUNT(DISTINCT CASE WHEN certainty  = 'uncertain'
                            THEN entity_sk END)         AS n_uncertain
    FROM {T_ENTITY}
    WHERE nlp_run_sk = {nlp_run_sk}
    GROUP BY entity_type
    ORDER BY n_entities DESC
""")

print(f"\n=== Run {nlp_run_sk} summary ===")
print(f"Started : {run_started_at}")
print(f"Finished: {run_finished_at}")
print(f"Duration: {run_finished_at - run_started_at}")
display(summary)

# COMMAND ----------

# MAGIC %md ## Section 8 — Quick validation

# COMMAND ----------

# Confirm entities are queryable through the full cohort join path
validation = spark.sql(f"""
    SELECT
        p.mrn,
        e.entity_type,
        e.covered_text,
        e.concept_code,
        e.concept_display,
        e.negation,
        e.certainty,
        e.temporality,
        e.subject,
        e.confidence
    FROM {T_ENTITY} e
    JOIN `{CATALOG}`.`{SILVER_SCHEMA}`.`patient` p USING (patient_sk)
    WHERE e.nlp_run_sk = {nlp_run_sk}
      AND e.negation   = false
      AND e.certainty  = 'positive'
      AND e.temporality = 'current'
      AND e.subject    = 'patient'
    ORDER BY e.confidence DESC
    LIMIT 50
""")

print("Sample positively-asserted, current, patient-attributed entities:")
display(validation)
