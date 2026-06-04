"""
My Cohorts — review saved cohorts, inspect members, export.
"""

import streamlit as st
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import config
from db import run_query, execute

st.set_page_config(
    page_title=f"My Cohorts — {config.APP_TITLE}",
    page_icon="📋",
    layout="wide",
)

with st.sidebar:
    st.markdown(f"## {config.APP_ICON} {config.APP_TITLE}")
    st.caption(config.APP_VERSION)
    st.divider()
    st.page_link("app.py",                       label="🏠 Home")
    st.page_link("pages/01_cohort_builder.py",   label="🔬 Cohort Builder")
    st.page_link("pages/02_cohort_review.py",    label="📋 My Cohorts")
    st.page_link("pages/03_patient_explorer.py", label="🧑‍⚕️ Patient Explorer")

st.title("📋 My Cohorts")

# ---------------------------------------------------------------
# Cohort list with filters
# ---------------------------------------------------------------
filter_col1, filter_col2, filter_col3 = st.columns(3)
type_filter     = filter_col1.multiselect("Cohort type",   list(config.COHORT_TYPES.keys()))
category_filter = filter_col2.multiselect("Category",      list(config.COHORT_CATEGORIES.keys()))
status_filter   = filter_col3.multiselect("Status",        config.COHORT_STATUSES, default=["active"])

@st.cache_data(ttl=30)
def load_cohorts(types: tuple, categories: tuple, statuses: tuple) -> pd.DataFrame:
    where_parts = []
    if types:
        where_parts.append(f"cohort_type IN ({', '.join(repr(t) for t in types)})")
    if categories:
        where_parts.append(f"cohort_category IN ({', '.join(repr(c) for c in categories)})")
    if statuses:
        where_parts.append(f"status IN ({', '.join(repr(s) for s in statuses)})")
    where = "WHERE " + " AND ".join(where_parts) if where_parts else ""

    return run_query(f"""
        SELECT
            cd.cohort_sk,
            cd.name,
            cd.cohort_type,
            cd.cohort_category,
            cd.primary_concept_display,
            cd.status,
            cd.version,
            cd.created_by,
            cd.created_at,
            COUNT(cm.patient_sk) AS member_count
        FROM {config.T_COHORT_DEF} cd
        LEFT JOIN {config.T_COHORT_MEMBER} cm USING (cohort_sk)
        {where}
        GROUP BY ALL
        ORDER BY cd.created_at DESC
    """)

try:
    cohorts_df = load_cohorts(
        tuple(type_filter),
        tuple(category_filter),
        tuple(status_filter),
    )

    if cohorts_df.empty:
        st.info("No cohorts found. Adjust filters or create one in Cohort Builder.", icon="💡")
    else:
        st.markdown(f"**{len(cohorts_df)} cohort(s) found**")

        selected = st.dataframe(
            cohorts_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "cohort_sk":              st.column_config.NumberColumn("ID",        width="small"),
                "name":                   st.column_config.TextColumn("Cohort Name", width="large"),
                "cohort_type":            st.column_config.TextColumn("Type"),
                "cohort_category":        st.column_config.TextColumn("Category"),
                "primary_concept_display":st.column_config.TextColumn("Primary Concept"),
                "status":                 st.column_config.TextColumn("Status",      width="small"),
                "version":                st.column_config.NumberColumn("Ver",       width="small"),
                "created_by":             st.column_config.TextColumn("Created By"),
                "created_at":             st.column_config.DatetimeColumn("Created", format="YYYY-MM-DD"),
                "member_count":           st.column_config.NumberColumn("Members",   format="%d"),
            },
        )

        # ---------------------------------------------------------------
        # Cohort detail panel
        # ---------------------------------------------------------------
        rows = selected.get("selection", {}).get("rows", []) if selected else []
        if rows:
            row     = cohorts_df.iloc[rows[0]]
            csk     = int(row["cohort_sk"])
            c_name  = row["name"]

            st.divider()
            st.subheader(f"📂 {c_name}")

            info_col1, info_col2, info_col3, info_col4 = st.columns(4)
            info_col1.metric("Members",  f"{int(row['member_count']):,}")
            info_col2.metric("Type",     str(row["cohort_type"]).capitalize())
            info_col3.metric("Category", str(row["cohort_category"]).capitalize())
            info_col4.metric("Status",   str(row["status"]).capitalize())

            tab_members, tab_evidence, tab_meta = st.tabs(["👥 Members", "🔍 Qualifying Evidence", "📄 Definition"])

            # ---- Members tab ----
            with tab_members:
                @st.cache_data(ttl=30)
                def load_members(cohort_sk: int) -> pd.DataFrame:
                    return run_query(f"""
                        SELECT
                            p.patient_sk,
                            p.mrn,
                            p.birth_date,
                            p.sex,
                            p.race,
                            p.state,
                            cm.index_date,
                            cm.qualifying_source
                        FROM   {config.T_COHORT_MEMBER} cm
                        JOIN   {config.T_PATIENT} p USING (patient_sk)
                        WHERE  cm.cohort_sk = {cohort_sk}
                        ORDER  BY p.mrn
                        LIMIT  {config.PAGE_SIZE}
                    """)

                members_df = load_members(csk)
                st.dataframe(
                    members_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "patient_sk":        st.column_config.NumberColumn("ID",    width="small"),
                        "mrn":               st.column_config.TextColumn("MRN"),
                        "birth_date":        st.column_config.DateColumn("DOB",     format="YYYY-MM-DD"),
                        "sex":               st.column_config.TextColumn("Sex",     width="small"),
                        "race":              st.column_config.TextColumn("Race"),
                        "state":             st.column_config.TextColumn("State",   width="small"),
                        "index_date":        st.column_config.DateColumn("Index Date", format="YYYY-MM-DD"),
                        "qualifying_source": st.column_config.TextColumn("Source",  width="small"),
                    },
                )

                if len(members_df) == config.PAGE_SIZE:
                    st.caption(f"Showing first {config.PAGE_SIZE} members. Export for full list.")

                # Export
                if st.button("📥 Export full member list (CSV)"):
                    full_df = run_query(f"""
                        SELECT p.patient_sk, p.mrn, p.birth_date, p.sex, p.race,
                               p.state, cm.index_date, cm.qualifying_source
                        FROM   {config.T_COHORT_MEMBER} cm
                        JOIN   {config.T_PATIENT} p USING (patient_sk)
                        WHERE  cm.cohort_sk = {csk}
                        ORDER  BY p.mrn
                        LIMIT  {config.MAX_EXPORT}
                    """)
                    csv = full_df.to_csv(index=False)
                    st.download_button(
                        "⬇ Download CSV",
                        data=csv,
                        file_name=f"cohort_{csk}_{c_name[:30].replace(' ','_')}.csv",
                        mime="text/csv",
                    )

            # ---- Qualifying evidence tab ----
            with tab_evidence:
                @st.cache_data(ttl=30)
                def load_conditions_for_cohort(cohort_sk: int) -> pd.DataFrame:
                    return run_query(f"""
                        SELECT
                            p.mrn,
                            c.condition_code,
                            c.condition_display,
                            c.clinical_status,
                            c.recorded_date,
                            c.category
                        FROM   {config.T_COHORT_MEMBER} cm
                        JOIN   {config.T_PATIENT} p     USING (patient_sk)
                        JOIN   {config.T_CONDITION} c   USING (patient_sk)
                        WHERE  cm.cohort_sk = {cohort_sk}
                        ORDER  BY c.recorded_date DESC
                        LIMIT  200
                    """)

                ev_df = load_conditions_for_cohort(csk)
                st.markdown("**Conditions contributing to cohort membership (sample)**")
                st.dataframe(ev_df, use_container_width=True, hide_index=True)

            # ---- Definition tab ----
            with tab_meta:
                detail_df = run_query(f"""
                    SELECT *
                    FROM   {config.T_COHORT_DEF}
                    WHERE  cohort_sk = {csk}
                """)
                if not detail_df.empty:
                    import json as _json
                    row_detail = detail_df.iloc[0]
                    st.markdown(f"**Description:** {row_detail.get('description','—')}")
                    st.markdown(f"**Index event:** {row_detail.get('index_event_description','—')}")
                    st.markdown(f"**Age range:** {row_detail.get('min_age_years','—')} – {row_detail.get('max_age_years','—')} years")
                    st.markdown("**Definition logic (JSON):**")
                    try:
                        logic = _json.loads(row_detail.get("definition_logic") or "{}")
                        st.json(logic)
                    except Exception:
                        st.code(row_detail.get("definition_logic",""), language="json")

                    # Archive / status change
                    st.divider()
                    new_status = st.selectbox(
                        "Change status",
                        config.COHORT_STATUSES,
                        index=config.COHORT_STATUSES.index(str(row_detail.get("status","draft"))),
                    )
                    if st.button("Update status"):
                        execute(f"""
                            UPDATE {config.T_COHORT_DEF}
                            SET    status = '{new_status}'
                            WHERE  cohort_sk = {csk}
                        """)
                        st.success(f"Status updated to **{new_status}**.")
                        st.cache_data.clear()
                        st.rerun()

except Exception as e:
    st.error(f"Could not load cohorts: {e}", icon="❌")
