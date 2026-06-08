"""
Shared Synaptiq brand theme for the Cohort Builder app.

Usage in every page:
    from ui import inject_css, brand_header, sidebar_nav
    inject_css()
    brand_header()
    sidebar_nav()
"""

import os
import streamlit as st
import config

# ── palette constants (for use in inline styles elsewhere) ─────────────────
BRAND_BLUE  = "#8BA4BD"
BRAND_AMBER = "#C8956A"
DARK_TEXT   = "#2D3748"
LIGHT_BG    = "#EEF3F8"
MED_BLUE    = "#6B8EAD"

# ── full CSS ────────────────────────────────────────────────────────────────
_CSS = """
<style>

/* ── Brand header bar ──────────────────────────────────────────────────── */
.synaptiq-header {
    background: linear-gradient(135deg, #8BA4BD 0%, #6B8EAD 100%);
    padding: 1.1rem 2rem 0.9rem 2rem;
    border-radius: 8px;
    margin-bottom: 1.2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
}
.synaptiq-wordmark {
    color: #FFFFFF;
    font-size: 1.35rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    line-height: 1;
}
.synaptiq-tagline {
    color: rgba(255,255,255,0.72);
    font-size: 0.72rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 2px;
}
.synaptiq-product {
    margin-left: auto;
    text-align: right;
}
.synaptiq-product-name {
    color: #FFFFFF;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

/* ── Hide Streamlit's auto-generated page nav (we use our own) ─────────── */
[data-testid="stSidebarNav"] {
    display: none;
}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #8BA4BD 0%, #7A96B0 100%);
}
section[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] .streamlit-expanderHeader {
    color: rgba(255,255,255,0.85) !important;
}
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] textarea {
    color: #2D3748 !important;
    background: #FFFFFF !important;
}
section[data-testid="stSidebar"] input::placeholder,
section[data-testid="stSidebar"] textarea::placeholder {
    color: #9AA5B4 !important;
}
section[data-testid="stSidebar"] button {
    background: rgba(200,149,106,0.75) !important;
    border: none !important;
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] button:hover {
    background: #C8956A !important;
}
section[data-testid="stSidebar"] button p,
section[data-testid="stSidebar"] button span {
    color: #FFFFFF !important;
}
/* code tags in sidebar get a white bg by default — override it */
section[data-testid="stSidebar"] code {
    background: rgba(255,255,255,0.15) !important;
    color: #FFFFFF !important;
    border: none !important;
}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
div[data-testid="stTabs"] button[role="tab"] {
    font-weight: 600;
    font-size: 0.92rem;
    letter-spacing: 0.03em;
    color: #6B8EAD;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #C8956A !important;
    border-bottom: 3px solid #C8956A;
}

/* ── Metric tiles ──────────────────────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: #EEF3F8;
    border-left: 4px solid #8BA4BD;
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
}
div[data-testid="metric-container"] label {
    color: #6B8EAD;
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="metric-container"] div[data-testid="metric-value"] {
    color: #2D3748;
    font-weight: 700;
}

/* ── Primary buttons ───────────────────────────────────────────────────── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: #C8956A;
    border: none;
    color: white;
    font-weight: 600;
    border-radius: 6px;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #B8845A;
    border: none;
}

/* ── Headings ──────────────────────────────────────────────────────────── */
h3 { color: #8BA4BD; }
h4 { color: #6B8EAD; }

/* ── Dividers ──────────────────────────────────────────────────────────── */
hr { border-top: 1px solid #C8956A33; }

/* ── Success / alert boxes ─────────────────────────────────────────────── */
div[data-testid="stAlert"][data-type="success"] {
    border-left: 4px solid #C8956A;
    background: #FDF5EE;
}

</style>
"""


def inject_css() -> None:
    """Inject Synaptiq brand CSS. Call immediately after set_page_config()."""
    st.markdown(_CSS, unsafe_allow_html=True)


_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "Synaptiq_001.png")


def brand_header(product_name: str = "Cohort Builder") -> None:
    """Render the Synaptiq logo row (white bg) then the blue gradient brand banner."""

    # ── Logo row — white background, sits above the blue banner ────────────
    if os.path.exists(_LOGO_PATH):
        import base64
        with open(_LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f"<div style='background:#FFFFFF;padding:6px 0 8px 0;'>"
            f"<img src='data:image/png;base64,{b64}' width='140'/>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div style='background:#FFFFFF;padding:6px 0 8px 0;font-size:1.3rem;"
            "font-weight:800;letter-spacing:0.05em;color:#2D3748;'>Synaptiq.</div>",
            unsafe_allow_html=True,
        )

    # ── Blue gradient banner ────────────────────────────────────────────────
    st.markdown(
        f"""
        <div class="synaptiq-header">
          <div>
            <div class="synaptiq-wordmark">Synaptiq</div>
            <div class="synaptiq-tagline">The Humankind of AI</div>
          </div>
          <div class="synaptiq-product">
            <div class="synaptiq-product-name">{product_name}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_nav() -> None:
    """Render the styled sidebar with Synaptiq branding and navigation links."""
    with st.sidebar:
        st.markdown(
            """
            <div style='text-align:center;padding:0.5rem 0 0.8rem 0;'>
              <div style='font-size:1.1rem;font-weight:700;letter-spacing:0.05em;
                          color:#FFFFFF;'>Synaptiq</div>
              <div style='font-size:0.62rem;letter-spacing:0.14em;text-transform:uppercase;
                          color:rgba(255,255,255,0.65);margin-top:2px;'>Cohort Builder</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.page_link("app.py",                       label="🏠  Home")
        st.page_link("pages/01_cohort_builder.py",   label="🔬  Cohort Builder")
        st.page_link("pages/02_cohort_review.py",    label="📋  My Cohorts")
        st.page_link("pages/03_patient_explorer.py", label="🧑‍⚕️  Patient Explorer")
        st.divider()
        st.markdown(
            f"<div style='font-size:0.7rem;opacity:0.7;padding:0 0.3rem;'>"
            f"<b>Silver</b><br><code style='font-size:0.65rem;'>"
            f"{config.CATALOG}.{config.SILVER_SCHEMA}</code><br><br>"
            f"<b>Gold</b><br><code style='font-size:0.65rem;'>"
            f"{config.CATALOG}.{config.GOLD_SCHEMA}</code>"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.caption(config.APP_VERSION)
