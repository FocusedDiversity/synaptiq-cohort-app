"""
Cohort Builder page.

Lets users define a patient cohort through:
  - Structured criteria (ICD-10, RxNorm, LOINC, demographics)
  - Free-text natural-language query (Genie integration — TODO)
  - NLP-derived findings from clinical notes

Workflow:
  1. Choose cohort type + category
  2. Build inclusion / exclusion criteria
  3. Preview count (dry-run SQL)
  4. Save to gold.cohort_definition + gold.cohort_member
"""

import datetime
import json
import streamlit as st
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from db import run_query, execute
from ui import inject_css, brand_header, sidebar_nav

st.set_page_config(
    page_title=f"Cohort Builder — {config.APP_TITLE}",
    page_icon="🔬",
    layout="wide",
)
inject_css()
sidebar_nav()
brand_header("Cohort Builder")
st.markdown(
    "<p style='color:#6B8EAD;margin-top:-0.5rem;margin-bottom:0.8rem;'>"
    "Define a patient cohort using structured criteria, NLP findings, or natural language.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# Step 1 — Cohort metadata
# ---------------------------------------------------------------
st.subheader("Step 1 — Cohort Identity")

meta_col1, meta_col2 = st.columns(2)
with meta_col1:
    cohort_name = st.text_input(
        "Cohort name *",
        placeholder="e.g. T2DM Patients on Metformin with CVD — 2022-2024",
    )
    cohort_description = st.text_area(
        "Description",
        placeholder="Brief description of the research or operational purpose of this cohort.",
        height=80,
    )

with meta_col2:
    cohort_type = st.selectbox(
        "Cohort type *",
        options=list(config.COHORT_TYPES.keys()),
        format_func=lambda k: f"{k.capitalize()} — {config.COHORT_TYPES[k].split(' — ')[1] if ' — ' in config.COHORT_TYPES[k] else config.COHORT_TYPES[k]}",
    )
    cohort_category = st.selectbox(
        "Study design / category *",
        options=list(config.COHORT_CATEGORIES.keys()),
        format_func=lambda k: config.COHORT_CATEGORIES[k],
    )
    created_by = st.text_input("Created by", placeholder="your.name@organization.com")

st.divider()

# ---------------------------------------------------------------
# Step 2 — Inclusion criteria
# ---------------------------------------------------------------
st.subheader("Step 2 — Inclusion Criteria")

tab_structured, tab_nlp, tab_nl = st.tabs([
    "📊 Structured (ICD / RxNorm / LOINC)",
    "📝 NLP-derived (from clinical notes)",
    "💬 Natural Language (Genie)",
])

# ---------- Structured tab ----------
with tab_structured:
    inc_col1, inc_col2 = st.columns(2)

    with inc_col1:
        st.markdown("**Diagnoses (ICD-10-CM)**")
        icd_codes = st.text_input(
            "ICD-10-CM codes (comma-separated)",
            placeholder="E11.9, I25.10, I50.9",
            help="Patients must have AT LEAST ONE of these conditions (active or problem-list-item).",
        )
        icd_status = st.multiselect(
            "Clinical status",
            ["active", "resolved", "inactive"],
            default=["active"],
        )

        st.markdown("**Medications (RxNorm)**")
        med_codes = st.text_input(
            "RxNorm codes (comma-separated)",
            placeholder="860975, 861007",
            help="860975 = Metformin 500 mg  |  861007 = Metformin 1000 mg",
        )
        med_status = st.multiselect(
            "Order status",
            ["active", "completed", "discontinued"],
            default=["active"],
        )

    with inc_col2:
        st.markdown("**Lab / Vital Thresholds (LOINC)**")
        lab_code = st.text_input(
            "LOINC code",
            placeholder="4548-4  (HbA1c)",
        )
        lab_col1, lab_col2 = st.columns(2)
        lab_min = lab_col1.number_input("Min value", value=None, placeholder="e.g. 7.0")
        lab_max = lab_col2.number_input("Max value", value=None, placeholder="e.g. 13.0")

        st.markdown("**Temporal window**")
        date_col1, date_col2 = st.columns(2)
        date_from = date_col1.date_input(
            "Criteria from",
            value=datetime.date(2025, 1, 1),
        )
        date_to = date_col2.date_input(
            "Criteria to",
            value=datetime.date(2026, 12, 31),
        )

        st.markdown("**Demographics**")
        age_col1, age_col2 = st.columns(2)
        min_age = age_col1.number_input("Min age (years)", min_value=0, max_value=120, value=18)
        max_age = age_col2.number_input("Max age (years)", min_value=0, max_value=120, value=89)
        sex_filter = st.multiselect("Sex", ["male", "female", "other"], default=[])

# ---------- NLP tab ----------
with tab_nlp:
    st.markdown(
        "Include patients whose clinical notes contain **positively-asserted** mentions of a "
        "concept — filtering out negated, historical, and family-history mentions. "
        "Search by clinical **term** (matches the extracted note text and the normalized "
        "concept name), by standardized **code**, or both."
    )
    nlp_terms = st.text_input(
        "Search terms (comma-separated — a patient qualifies if ANY term matches)",
        placeholder="upper respiratory, cough, shortness of breath",
        help="Case-insensitive substring match against the verbatim note text span "
             "(covered_text) and the normalized concept name (concept_display).",
    )
    nlp_concept = st.text_input(
        "Concept code — optional (SNOMED / ICD-10 / RxNorm / LOINC)",
        placeholder="E11.9  or  860975  or  73211009 (SNOMED T2DM)",
        help="Exact code match, OR'd together with the search terms above.",
    )
    nlp_filter_col1, nlp_filter_col2 = st.columns(2)
    with nlp_filter_col1:
        nlp_certainty = st.multiselect(
            "Certainty filter",
            ["positive", "uncertain", "hypothetical"],
            default=["positive"],
            help="'positive' = confirmed mention. Negated mentions are always excluded.",
        )
        nlp_entity_types = st.multiselect(
            "Entity types (empty = all)",
            ["problem", "medication", "procedure", "lab", "anatomy", "finding"],
            default=[],
            help="Restrict matches to certain entity types, e.g. only problems/findings "
                 "so a term like 'cough' can't match a medication name.",
        )
    with nlp_filter_col2:
        nlp_temporality = st.multiselect(
            "Temporality filter",
            ["current", "historical", "family"],
            default=["current"],
        )
        nlp_patient_only = st.checkbox(
            "Patient mentions only",
            value=True,
            help="Exclude mentions attributed to a family member or another person "
                 "(e.g. \"mother has Type 2 diabetes\").",
        )
    st.caption(
        "Queries `dev.test_silver_ehr_clinical.note_nlp_entity` where `negation = false`, "
        "filtered by certainty, temporality, entity type, and subject."
    )

# ---------- Natural Language tab ----------
with tab_nl:
    st.info(
        "**Genie integration coming soon.**\n\n"
        "This tab will send your natural-language query to a Databricks Genie Space "
        "configured over the silver tables, translate it to SQL, and return the matching "
        "patient set. For now, use the Structured tab to build your criteria.",
        icon="🤖",
    )
    nl_query = st.text_area(
        "Describe your cohort",
        placeholder='e.g. "Find patients with Type 2 diabetes on metformin who had a '
                    'cardiovascular event in the last 2 years"',
        height=100,
        disabled=True,
    )

st.divider()

# ---------------------------------------------------------------
# Step 3 — Exclusion criteria
# ---------------------------------------------------------------
with st.expander("Step 3 — Exclusion Criteria (optional)"):
    exc_icd = st.text_input(
        "Exclude patients with these ICD-10 codes (comma-separated)",
        placeholder="N18.4, N18.5  (stage 4-5 CKD — contraindication to metformin)",
    )
    exc_meds = st.text_input(
        "Exclude patients on these RxNorm codes",
        placeholder="285129  (insulin glargine — may indicate T1DM)",
    )

st.divider()

# ---------------------------------------------------------------
# Step 4 — Preview + Save
# ---------------------------------------------------------------
st.subheader("Step 4 — Preview & Save")

def build_inclusion_sql() -> str:
    """
    Assemble a SQL query from the structured criteria above.
    Returns a SELECT patient_sk ... query ready to be wrapped in a COUNT or JOIN.
    """
    parts = []
    params_note = []

    # ICD conditions
    if icd_codes.strip():
        codes = [c.strip().upper() for c in icd_codes.split(",") if c.strip()]
        status_list = ", ".join(f"'{s}'" for s in icd_status) if icd_status else "'active'"
        codes_list  = ", ".join(f"'{c}'" for c in codes)
        parts.append(f"""
            patient_sk IN (
                SELECT DISTINCT patient_sk
                FROM   {config.T_CONDITION}
                WHERE  condition_code IN ({codes_list})
                AND    clinical_status IN ({status_list})
                AND    recorded_date BETWEEN '{date_from}' AND '{date_to}'
            )""")

    # Medications
    if med_codes.strip():
        codes = [c.strip() for c in med_codes.split(",") if c.strip()]
        codes_list   = ", ".join(f"'{c}'" for c in codes)
        status_list  = ", ".join(f"'{s}'" for s in med_status) if med_status else "'active'"
        parts.append(f"""
            patient_sk IN (
                SELECT DISTINCT patient_sk
                FROM   {config.T_MEDICATION_ORDER}
                WHERE  med_code IN ({codes_list})
                AND    order_status IN ({status_list})
                AND    start_datetime BETWEEN '{date_from}' AND '{date_to}'
            )""")

    # Lab thresholds
    if lab_code.strip():
        threshold_clauses = []
        if lab_min is not None:
            threshold_clauses.append(f"value_numeric >= {lab_min}")
        if lab_max is not None:
            threshold_clauses.append(f"value_numeric <= {lab_max}")
        thresh_sql = (" AND " + " AND ".join(threshold_clauses)) if threshold_clauses else ""
        parts.append(f"""
            patient_sk IN (
                SELECT DISTINCT patient_sk
                FROM   {config.T_OBSERVATION}
                WHERE  observation_code = '{lab_code.strip()}'
                {thresh_sql}
                AND    effective_datetime BETWEEN '{date_from}' AND '{date_to}'
            )""")

    # NLP entities — term search (covered_text / concept_display) and/or exact code
    nlp_match_clauses = []
    if nlp_terms.strip():
        for term in [t.strip() for t in nlp_terms.split(",") if t.strip()]:
            safe_term = term.replace("'", "''")
            nlp_match_clauses.append(
                f"(covered_text ILIKE '%{safe_term}%' OR concept_display ILIKE '%{safe_term}%')"
            )
    if nlp_concept.strip():
        safe_code = nlp_concept.strip().replace("'", "''")
        nlp_match_clauses.append(f"concept_code = '{safe_code}'")

    if nlp_match_clauses:
        match_sql  = "\n                    OR ".join(nlp_match_clauses)
        cert_list  = ", ".join(f"'{c}'" for c in nlp_certainty)  if nlp_certainty  else "'positive'"
        temp_list  = ", ".join(f"'{t}'" for t in nlp_temporality) if nlp_temporality else "'current'"
        extra = ""
        if nlp_entity_types:
            type_list = ", ".join(f"'{t}'" for t in nlp_entity_types)
            extra += f"\n                AND    entity_type IN ({type_list})"
        if nlp_patient_only:
            extra += "\n                AND    subject = 'patient'"
        parts.append(f"""
            patient_sk IN (
                SELECT DISTINCT patient_sk
                FROM   {config.T_NLP_ENTITY}
                WHERE  ( {match_sql} )
                AND    negation = false
                AND    certainty IN ({cert_list})
                AND    temporality IN ({temp_list}){extra}
            )""")

    # Demographics — age
    age_clause = f"""
            patient_sk IN (
                SELECT patient_sk
                FROM   {config.T_PATIENT}
                WHERE  DATEDIFF(CURRENT_DATE(), birth_date) / 365.25
                       BETWEEN {min_age} AND {max_age}"""
    if sex_filter:
        sex_list = ", ".join(f"'{s}'" for s in sex_filter)
        age_clause += f"\n                AND    sex IN ({sex_list})"
    age_clause += "\n            )"
    parts.append(age_clause)

    # Exclusions
    if exc_icd.strip():
        codes = [c.strip().upper() for c in exc_icd.split(",") if c.strip()]
        parts.append(f"""
            patient_sk NOT IN (
                SELECT DISTINCT patient_sk
                FROM   {config.T_CONDITION}
                WHERE  condition_code IN ({', '.join(f"'{c}'" for c in codes)})
            )""")
    if exc_meds.strip():
        codes = [c.strip() for c in exc_meds.split(",") if c.strip()]
        parts.append(f"""
            patient_sk NOT IN (
                SELECT DISTINCT patient_sk
                FROM   {config.T_MEDICATION_ORDER}
                WHERE  med_code IN ({', '.join(f"'{c}'" for c in codes)})
            )""")

    where = "\n            AND ".join(parts) if parts else "1=1"
    return f"""
        SELECT DISTINCT p.patient_sk, p.mrn, p.birth_date, p.sex, p.race
        FROM   {config.T_PATIENT} p
        WHERE  {where}
    """


preview_col1, preview_col2 = st.columns([1, 3])

with preview_col1:
    preview_btn = st.button("▶ Preview Cohort", type="primary", use_container_width=True)
    save_btn    = st.button("💾 Save Cohort",   type="secondary", use_container_width=True,
                             disabled=not cohort_name.strip())

if preview_btn or save_btn:
    try:
        inclusion_sql = build_inclusion_sql()
        count_sql     = f"SELECT COUNT(*) AS n FROM ({inclusion_sql})"

        with st.spinner("Running cohort query…"):
            count_df = run_query(count_sql)
            n = int(count_df.iloc[0]["n"]) if not count_df.empty else 0

        st.metric("Patients matching criteria", f"{n:,}")

        # Always show SQL — essential for debugging zero-result queries
        with st.expander("View generated SQL", expanded=(n == 0)):
            st.code(inclusion_sql.strip(), language="sql")

        if n > 0:
            with st.spinner("Loading preview sample…"):
                sample_df = run_query(f"{inclusion_sql} LIMIT {config.PAGE_SIZE}")
            st.dataframe(
                sample_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "patient_sk": st.column_config.NumberColumn("ID",       width="small"),
                    "mrn":        st.column_config.TextColumn("MRN",       width="medium"),
                    "birth_date": st.column_config.DateColumn("DOB",       format="YYYY-MM-DD"),
                    "sex":        st.column_config.TextColumn("Sex",       width="small"),
                    "race":       st.column_config.TextColumn("Race"),
                },
            )
        else:
            st.warning("No patients match the current criteria. Try broadening the filters.")

        # ---- Save ----
        if save_btn and cohort_name.strip() and n > 0:
            nlp_used        = bool(nlp_terms.strip() or nlp_concept.strip())
            structured_used = bool(icd_codes.strip() or med_codes.strip() or lab_code.strip())

            logic_json = json.dumps({
                "icd_codes":        icd_codes,
                "icd_status":       icd_status,
                "med_codes":        med_codes,
                "med_status":       med_status,
                "lab_code":         lab_code,
                "lab_min":          lab_min,
                "lab_max":          lab_max,
                "nlp_terms":        nlp_terms,
                "nlp_concept":      nlp_concept,
                "nlp_certainty":    nlp_certainty,
                "nlp_temporality":  nlp_temporality,
                "nlp_entity_types": nlp_entity_types,
                "nlp_patient_only": nlp_patient_only,
                "exc_icd":          exc_icd,
                "exc_meds":         exc_meds,
                "date_from":        str(date_from),
                "date_to":          str(date_to),
                "min_age":          min_age,
                "max_age":          max_age,
                "sex_filter":       sex_filter,
            })

            primary_code   = (icd_codes.split(",")[0].strip() if icd_codes.strip()
                              else med_codes.split(",")[0].strip() if med_codes.strip()
                              else nlp_concept.strip()
                              or (nlp_terms.split(",")[0].strip() if nlp_terms.strip() else ""))
            primary_system = ("ICD-10-CM" if icd_codes.strip()
                              else "RxNorm" if med_codes.strip()
                              else "SNOMED" if nlp_concept.strip()
                              else "NLP-term")

            # Insert cohort definition
            safe_name  = cohort_name.replace("'", "''")
            safe_desc  = cohort_description.replace("'", "''")
            safe_by    = (created_by or "unknown").replace("'", "''")
            safe_logic = logic_json.replace("'", "''")

            execute(f"""
                INSERT INTO {config.T_COHORT_DEF}
                    (name, description, cohort_type, cohort_category,
                     primary_concept_code, primary_concept_system,
                     definition_logic, is_nlp_derived,
                     index_event_description, min_age_years, max_age_years,
                     status, version, created_by)
                VALUES (
                    '{safe_name}', '{safe_desc}', '{cohort_type}', '{cohort_category}',
                    '{primary_code}', '{primary_system}',
                    '{safe_logic}', {'true' if nlp_used else 'false'},
                    'Structured criteria — see definition_logic',
                    {min_age}, {max_age},
                    'active', 1, '{safe_by}'
                )
            """)

            # Get the new cohort_sk
            new_cohort = run_query(f"""
                SELECT cohort_sk FROM {config.T_COHORT_DEF}
                WHERE  name = '{safe_name}'
                ORDER  BY created_at DESC LIMIT 1
            """)
            cohort_sk = int(new_cohort.iloc[0]["cohort_sk"])

            # Insert cohort members
            qual_source = ("nlp" if nlp_used and not structured_used
                           else "mixed" if nlp_used
                           else "coded")
            members_df = run_query(inclusion_sql)
            if not members_df.empty:
                member_values = ", ".join(
                    f"({cohort_sk}, {int(row['patient_sk'])}, CURRENT_DATE(), '{qual_source}', CURRENT_TIMESTAMP())"
                    for _, row in members_df.iterrows()
                )
                execute(f"""
                    INSERT INTO {config.T_COHORT_MEMBER}
                        (cohort_sk, patient_sk, index_date, qualifying_source, qualified_at)
                    VALUES {member_values}
                """)

            st.success(
                f"✅ Cohort **{cohort_name}** saved with **{n:,}** members (cohort_sk = {cohort_sk}).",
                icon="✅",
            )
            st.cache_data.clear()

    except Exception as e:
        st.error(f"Query error: {e}", icon="❌")
