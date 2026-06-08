"""
Patient Explorer — search by MRN, view clinical timeline.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from db import run_query
from ui import inject_css, brand_header, sidebar_nav

st.set_page_config(
    page_title=f"Patient Explorer — {config.APP_TITLE}",
    page_icon="🧑‍⚕️",
    layout="wide",
)
inject_css()
sidebar_nav()
brand_header("Patient Explorer")
st.markdown(
    "<p style='color:#6B8EAD;margin-top:-0.5rem;margin-bottom:0.8rem;'>"
    "Search for a patient and explore their full clinical timeline.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# Patient search
# ---------------------------------------------------------------
search_col, _ = st.columns([2, 3])
mrn_input = search_col.text_input("Search by MRN", placeholder="MRN-000042")

if not mrn_input.strip():
    st.info("Enter a patient MRN above to begin.", icon="🔍")
    st.stop()

@st.cache_data(ttl=120)
def load_patient(mrn: str) -> pd.DataFrame:
    return run_query(f"""
        SELECT * FROM {config.T_PATIENT}
        WHERE  mrn = '{mrn.strip()}'
        LIMIT  1
    """)

try:
    patient_df = load_patient(mrn_input.strip())
except Exception as e:
    st.error(f"Query error: {e}", icon="❌")
    st.stop()

if patient_df.empty:
    st.warning(f"No patient found with MRN `{mrn_input.strip()}`.", icon="⚠️")
    st.stop()

pt = patient_df.iloc[0]
patient_sk = int(pt["patient_sk"])

# ---------------------------------------------------------------
# Patient header
# ---------------------------------------------------------------
st.divider()
hdr_col1, hdr_col2, hdr_col3, hdr_col4, hdr_col5 = st.columns(5)
hdr_col1.metric("MRN",      str(pt.get("mrn", "—")))
hdr_col2.metric("Sex",      str(pt.get("sex", "—")).capitalize())
hdr_col3.metric("DOB",      str(pt.get("birth_date", "—")))
hdr_col4.metric("State",    str(pt.get("state", "—")))
hdr_col5.metric("Language", str(pt.get("primary_language", "—")))

st.divider()

# ---------------------------------------------------------------
# Clinical timeline tabs
# ---------------------------------------------------------------
tab_enc, tab_cond, tab_obs, tab_meds, tab_procs, tab_notes = st.tabs([
    "🏥 Encounters",
    "🩺 Conditions",
    "🧪 Labs & Vitals",
    "💊 Medications",
    "🔧 Procedures",
    "📝 Clinical Notes",
])

# ---- Encounters ----
with tab_enc:
    @st.cache_data(ttl=120)
    def load_encounters(pid: int) -> pd.DataFrame:
        return run_query(f"""
            SELECT encounter_sk, encounter_class, encounter_type, status,
                   period_start, period_end, attending_provider_name, facility_name
            FROM   {config.T_ENCOUNTER}
            WHERE  patient_sk = {pid}
            ORDER  BY period_start DESC
            LIMIT  {config.PAGE_SIZE}
        """)

    enc_df = load_encounters(patient_sk)
    st.markdown(f"**{len(enc_df)} encounter(s)** (most recent first)")
    st.dataframe(
        enc_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "encounter_sk":           st.column_config.NumberColumn("ID",        width="small"),
            "encounter_class":        st.column_config.TextColumn("Class"),
            "encounter_type":         st.column_config.TextColumn("Type"),
            "status":                 st.column_config.TextColumn("Status",      width="small"),
            "period_start":           st.column_config.DatetimeColumn("Start",   format="YYYY-MM-DD"),
            "period_end":             st.column_config.DatetimeColumn("End",     format="YYYY-MM-DD"),
            "attending_provider_name":st.column_config.TextColumn("Provider"),
            "facility_name":          st.column_config.TextColumn("Facility"),
        },
    )

# ---- Conditions ----
with tab_cond:
    @st.cache_data(ttl=120)
    def load_conditions(pid: int) -> pd.DataFrame:
        return run_query(f"""
            SELECT condition_sk, condition_code, condition_display,
                   category, clinical_status, is_chronic,
                   onset_date, recorded_date, resolved_date
            FROM   {config.T_CONDITION}
            WHERE  patient_sk = {pid}
            ORDER  BY recorded_date DESC
            LIMIT  {config.PAGE_SIZE}
        """)

    cond_df = load_conditions(patient_sk)

    # Active vs resolved summary
    if not cond_df.empty:
        active_ct   = (cond_df["clinical_status"] == "active").sum()
        resolved_ct = (cond_df["clinical_status"] == "resolved").sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total diagnoses", len(cond_df))
        c2.metric("Active",   active_ct)
        c3.metric("Resolved", resolved_ct)

    st.dataframe(
        cond_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "condition_sk":      st.column_config.NumberColumn("ID",         width="small"),
            "condition_code":    st.column_config.TextColumn("ICD-10",       width="small"),
            "condition_display": st.column_config.TextColumn("Diagnosis",    width="large"),
            "category":          st.column_config.TextColumn("Category"),
            "clinical_status":   st.column_config.TextColumn("Status",       width="small"),
            "is_chronic":        st.column_config.CheckboxColumn("Chronic",  width="small"),
            "onset_date":        st.column_config.DateColumn("Onset",        format="YYYY-MM-DD"),
            "recorded_date":     st.column_config.DateColumn("Recorded",     format="YYYY-MM-DD"),
            "resolved_date":     st.column_config.DateColumn("Resolved",     format="YYYY-MM-DD"),
        },
    )

# ---- Labs & Vitals ----
with tab_obs:
    @st.cache_data(ttl=120)
    def load_observations(pid: int) -> pd.DataFrame:
        return run_query(f"""
            SELECT observation_sk, category, observation_code, observation_display,
                   value_numeric, value_string, unit, interpretation, effective_datetime,
                   parent_observation_sk
            FROM   {config.T_OBSERVATION}
            WHERE  patient_sk = {pid}
            AND    parent_observation_sk IS NULL   -- top-level rows only
            ORDER  BY effective_datetime DESC
            LIMIT  200
        """)

    obs_df = load_observations(patient_sk)
    obs_tab_lab, obs_tab_vital = st.tabs(["🧪 Labs", "📊 Vitals"])

    with obs_tab_lab:
        labs = obs_df[obs_df["category"] == "laboratory"].copy()
        if labs.empty:
            st.info("No lab results found.")
        else:
            # Trend chart for selected LOINC
            loinc_options = labs["observation_code"].unique().tolist()
            selected_loinc = st.selectbox("Chart a lab trend", loinc_options,
                                           format_func=lambda c: f"{c} — {labs[labs['observation_code']==c]['observation_display'].iloc[0]}")
            chart_df = labs[labs["observation_code"] == selected_loinc].dropna(subset=["value_numeric"])
            if not chart_df.empty:
                fig = px.line(
                    chart_df.sort_values("effective_datetime"),
                    x="effective_datetime", y="value_numeric",
                    labels={"effective_datetime": "Date", "value_numeric": str(chart_df["unit"].iloc[0])},
                    markers=True, title=f"{selected_loinc} — {chart_df['observation_display'].iloc[0]}",
                )
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(labs, use_container_width=True, hide_index=True)

    with obs_tab_vital:
        vitals = obs_df[obs_df["category"] == "vital-signs"].copy()
        if vitals.empty:
            st.info("No vital signs found.")
        else:
            st.dataframe(
                vitals,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "observation_display": st.column_config.TextColumn("Vital"),
                    "value_numeric":       st.column_config.NumberColumn("Value", format="%.1f"),
                    "unit":                st.column_config.TextColumn("Unit",   width="small"),
                    "interpretation":      st.column_config.TextColumn("Interp", width="small"),
                    "effective_datetime":  st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD"),
                },
            )

# ---- Medications ----
with tab_meds:
    @st.cache_data(ttl=120)
    def load_meds(pid: int) -> pd.DataFrame:
        return run_query(f"""
            SELECT med_order_sk, med_code, med_display, order_class,
                   dose_quantity, dose_unit, route, frequency,
                   order_status, start_datetime, end_datetime
            FROM   {config.T_MEDICATION_ORDER}
            WHERE  patient_sk = {pid}
            ORDER  BY start_datetime DESC
            LIMIT  {config.PAGE_SIZE}
        """)

    meds_df = load_meds(patient_sk)
    if meds_df.empty:
        st.info("No medication orders found.")
    else:
        active_meds = meds_df[meds_df["order_status"] == "active"]
        if not active_meds.empty:
            st.markdown(f"**{len(active_meds)} active medication order(s)**")
            st.dataframe(
                active_meds,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "med_display":    st.column_config.TextColumn("Medication",    width="large"),
                    "dose_quantity":  st.column_config.TextColumn("Dose"),
                    "dose_unit":      st.column_config.TextColumn("Unit",          width="small"),
                    "route":          st.column_config.TextColumn("Route"),
                    "frequency":      st.column_config.TextColumn("Frequency"),
                    "start_datetime": st.column_config.DatetimeColumn("Start",     format="YYYY-MM-DD"),
                },
            )
        with st.expander("All medication orders"):
            st.dataframe(meds_df, use_container_width=True, hide_index=True)

# ---- Procedures ----
with tab_procs:
    @st.cache_data(ttl=120)
    def load_procs(pid: int) -> pd.DataFrame:
        return run_query(f"""
            SELECT procedure_sk, procedure_code, procedure_display,
                   procedure_category, status, performed_datetime
            FROM   {config.T_PROCEDURE}
            WHERE  patient_sk = {pid}
            ORDER  BY performed_datetime DESC
            LIMIT  {config.PAGE_SIZE}
        """)

    procs_df = load_procs(patient_sk)
    if procs_df.empty:
        st.info("No procedures found.")
    else:
        st.dataframe(
            procs_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "procedure_code":     st.column_config.TextColumn("CPT",       width="small"),
                "procedure_display":  st.column_config.TextColumn("Procedure", width="large"),
                "procedure_category": st.column_config.TextColumn("Category"),
                "status":             st.column_config.TextColumn("Status",    width="small"),
                "performed_datetime": st.column_config.DatetimeColumn("Date",  format="YYYY-MM-DD"),
            },
        )

# ---- Clinical Notes ----
with tab_notes:
    @st.cache_data(ttl=120)
    def load_notes_list(pid: int) -> pd.DataFrame:
        return run_query(f"""
            SELECT note_sk, note_category, note_type_display, author_name,
                   service_date, status
            FROM   {config.T_CLINICAL_NOTE}
            WHERE  patient_sk = {pid}
            ORDER  BY service_date DESC
            LIMIT  50
        """)

    notes_list = load_notes_list(patient_sk)

    if notes_list.empty:
        st.info("No clinical notes found.")
    else:
        note_col1, note_col2 = st.columns([1, 2])

        with note_col1:
            st.markdown(f"**{len(notes_list)} note(s)**")
            selected_note = st.dataframe(
                notes_list[["note_sk", "note_category", "service_date", "author_name"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "note_sk":       st.column_config.NumberColumn("ID",       width="small"),
                    "note_category": st.column_config.TextColumn("Category"),
                    "service_date":  st.column_config.DatetimeColumn("Date",   format="YYYY-MM-DD"),
                    "author_name":   st.column_config.TextColumn("Author"),
                },
            )

        with note_col2:
            rows = selected_note.get("selection", {}).get("rows", []) if selected_note else []
            if rows:
                note_sk = int(notes_list.iloc[rows[0]]["note_sk"])

                @st.cache_data(ttl=120)
                def load_note_text(nsk: int) -> str:
                    df = run_query(f"""
                        SELECT note_text FROM {config.T_CLINICAL_NOTE}
                        WHERE  note_sk = {nsk}
                    """)
                    return df.iloc[0]["note_text"] if not df.empty else ""

                note_text = load_note_text(note_sk)

                # NLP entities for this note
                @st.cache_data(ttl=120)
                def load_note_entities(nsk: int) -> pd.DataFrame:
                    return run_query(f"""
                        SELECT entity_type, covered_text, concept_code,
                               concept_display, certainty, negation,
                               temporality, confidence
                        FROM   {config.T_NLP_ENTITY}
                        WHERE  note_sk = {nsk}
                        ORDER  BY confidence DESC
                        LIMIT  50
                    """)

                st.markdown("**Note text**")
                st.text_area("", value=note_text, height=350, disabled=True, label_visibility="collapsed")

                entities_df = load_note_entities(note_sk)
                if not entities_df.empty:
                    st.markdown("**NLP-extracted entities**")
                    st.dataframe(
                        entities_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "entity_type":    st.column_config.TextColumn("Type"),
                            "covered_text":   st.column_config.TextColumn("Text Span",    width="medium"),
                            "concept_code":   st.column_config.TextColumn("Code",         width="small"),
                            "concept_display":st.column_config.TextColumn("Concept"),
                            "certainty":      st.column_config.TextColumn("Certainty",    width="small"),
                            "negation":       st.column_config.CheckboxColumn("Negated",  width="small"),
                            "temporality":    st.column_config.TextColumn("Temporality",  width="small"),
                            "confidence":     st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1),
                        },
                    )
                else:
                    st.caption("No NLP entities extracted for this note yet. Run the NLP pipeline to populate `note_nlp_entity`.")
            else:
                st.info("Select a note from the list to read it.", icon="👈")
