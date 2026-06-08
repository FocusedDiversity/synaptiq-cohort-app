"""
Synaptiq Cohort Builder — main entry / home dashboard.

Run locally:
    cd app
    pip install -r requirements.txt
    cp .env.example .env   # fill in credentials
    streamlit run app.py

Deployed as Databricks App:
    Upload the app/ folder to a Databricks workspace and configure
    the Service Principal in the App settings.
"""

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()   # load .env when running locally

import config
from db import run_query

# ---------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------
with st.sidebar:
    st.markdown(f"## {config.APP_ICON} {config.APP_TITLE}")
    st.caption(config.APP_VERSION)
    st.divider()
    st.page_link("app.py",                               label="🏠 Home",             icon=None)
    st.page_link("pages/01_cohort_builder.py",           label="🔬 Cohort Builder",   icon=None)
    st.page_link("pages/02_cohort_review.py",            label="📋 My Cohorts",       icon=None)
    st.page_link("pages/03_patient_explorer.py",         label="🧑‍⚕️ Patient Explorer", icon=None)
    st.divider()
    st.caption(
        f"**Silver:** `{config.CATALOG}.{config.SILVER_SCHEMA}`\n\n"
        f"**Gold:** `{config.CATALOG}.{config.GOLD_SCHEMA}`"
    )

# ---------------------------------------------------------------
# Home dashboard
# ---------------------------------------------------------------
st.title(f"{config.APP_ICON} {config.APP_TITLE}")
st.markdown(
    "Build patient cohorts using structured criteria, natural-language queries, "
    "or NLP-derived clinical findings from free-text notes."
)
st.divider()

# ---------------------------------------------------------------
# Population KPIs
# ---------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner="Loading population stats…")
def load_kpis() -> dict:
    rows = run_query(f"""
        SELECT
            (SELECT COUNT(*)  FROM {config.T_PATIENT})           AS n_patients,
            (SELECT COUNT(*)  FROM {config.T_ENCOUNTER})         AS n_encounters,
            (SELECT COUNT(*)  FROM {config.T_CONDITION})         AS n_conditions,
            (SELECT COUNT(*)  FROM {config.T_CLINICAL_NOTE})     AS n_notes,
            (SELECT COUNT(*)  FROM {config.T_COHORT_DEF})        AS n_cohorts,
            (SELECT COUNT(*)  FROM {config.T_COHORT_MEMBER})     AS n_members
    """)
    return rows.iloc[0].to_dict() if not rows.empty else {}

try:
    kpis = load_kpis()

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Patients",   f"{int(kpis.get('n_patients', 0)):,}")
    col2.metric("Encounters", f"{int(kpis.get('n_encounters', 0)):,}")
    col3.metric("Conditions", f"{int(kpis.get('n_conditions', 0)):,}")
    col4.metric("Notes",      f"{int(kpis.get('n_notes', 0)):,}")
    col5.metric("Cohorts",    f"{int(kpis.get('n_cohorts', 0)):,}")
    col6.metric("Members",    f"{int(kpis.get('n_members', 0)):,}")

except Exception as e:
    st.warning(
        f"⚠️ Could not load population stats. Check your connection credentials.\n\n`{e}`",
        icon="⚠️",
    )
    st.info(
        "**Getting started:**  \n"
        "1. Copy `.env.example` → `.env` and fill in credentials (local dev)  \n"
        "2. Or set `DATABRICKS_HTTP_PATH` in app.yaml (Databricks Apps — already configured)  \n"
        "3. `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are injected automatically at runtime",
        icon="ℹ️",
    )

st.divider()

# ---------------------------------------------------------------
# Recent cohorts
# ---------------------------------------------------------------
st.subheader("Recent Cohorts")

@st.cache_data(ttl=60)
def load_recent_cohorts() -> pd.DataFrame:
    return run_query(f"""
        SELECT
            cohort_sk,
            name,
            cohort_type,
            cohort_category,
            status,
            created_by,
            created_at
        FROM {config.T_COHORT_DEF}
        ORDER BY created_at DESC
        LIMIT 10
    """)

try:
    recent = load_recent_cohorts()
    if recent.empty:
        st.info("No cohorts saved yet. Head to **Cohort Builder** to create your first one.", icon="💡")
    else:
        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True,
            column_config={
                "cohort_sk":     st.column_config.NumberColumn("ID",       width="small"),
                "name":          st.column_config.TextColumn("Cohort Name", width="large"),
                "cohort_type":   st.column_config.TextColumn("Type"),
                "cohort_category":st.column_config.TextColumn("Category"),
                "status":        st.column_config.TextColumn("Status",    width="small"),
                "created_by":    st.column_config.TextColumn("Created By"),
                "created_at":    st.column_config.DatetimeColumn("Created", format="YYYY-MM-DD HH:mm"),
            },
        )
except Exception:
    st.info("Connect to Databricks to see recent cohorts.", icon="🔌")

# ---------------------------------------------------------------
# Quick-launch tiles
# ---------------------------------------------------------------
st.divider()
st.subheader("Quick Actions")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("### 🔬 Build a Cohort")
    st.markdown("Define inclusion/exclusion criteria using ICD-10 codes, medications, lab values, or natural-language queries.")
    st.page_link("pages/01_cohort_builder.py", label="Open Cohort Builder →")

with c2:
    st.markdown("### 📋 Manage Cohorts")
    st.markdown("Review saved cohorts, inspect member lists with qualifying evidence, and export for downstream analysis.")
    st.page_link("pages/02_cohort_review.py", label="Open My Cohorts →")

with c3:
    st.markdown("### 🧑‍⚕️ Explore Patients")
    st.markdown("Search for a patient by MRN and view their full clinical timeline — encounters, diagnoses, labs, and notes.")
    st.page_link("pages/03_patient_explorer.py", label="Open Patient Explorer →")
