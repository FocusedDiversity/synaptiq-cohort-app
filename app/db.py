"""
Database connection manager.

Auth priority (first found wins):
  1. Service Principal OAuth  — DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET
  2. Personal Access Token    — DATABRICKS_TOKEN
  3. Streamlit secrets        — st.secrets["DATABRICKS_TOKEN"]

All three read DATABRICKS_HOST and DATABRICKS_HTTP_PATH from the same sources.

Usage:
    from db import run_query
    df = run_query("SELECT * FROM dev.test_silver_ehr_clinical.patient LIMIT 10")
"""

from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from databricks import sql


def _cfg(key: str) -> str | None:
    """Read a setting from st.secrets first, then env vars."""
    try:
        return st.secrets.get(key)
    except Exception:
        pass
    return os.getenv(key)


def _get_token() -> str:
    """
    Return a bearer token using SP OAuth if credentials are present,
    otherwise fall back to a PAT.
    Raises RuntimeError if no credentials are configured.
    """
    client_id     = _cfg("DATABRICKS_CLIENT_ID")
    client_secret = _cfg("DATABRICKS_CLIENT_SECRET")
    host          = _cfg("DATABRICKS_HOST") or ""

    if client_id and client_secret:
        # Service Principal OAuth 2.0 client-credentials flow
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.config import Config
        cfg = Config(
            host=host,
            client_id=client_id,
            client_secret=client_secret,
        )
        return WorkspaceClient(config=cfg).config.token  # type: ignore[return-value]

    pat = _cfg("DATABRICKS_TOKEN")
    if pat:
        return pat

    raise RuntimeError(
        "No Databricks credentials found.\n"
        "Set DATABRICKS_TOKEN (PAT) or DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET "
        "(Service Principal) via environment variables or .streamlit/secrets.toml."
    )


@st.cache_resource(show_spinner="Connecting to Databricks…")
def _connection():
    """Cached SQL warehouse connection (one per app session)."""
    host      = _cfg("DATABRICKS_HOST")
    http_path = _cfg("DATABRICKS_HTTP_PATH")
    token     = _get_token()

    if not host or not http_path:
        raise RuntimeError(
            "DATABRICKS_HOST and DATABRICKS_HTTP_PATH must be set.\n"
            "Copy .env.example → .env and fill in your warehouse details."
        )

    return sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
    )


def run_query(query: str, params: list | None = None) -> pd.DataFrame:
    """
    Execute a SQL query against the Unity Catalog warehouse and return
    a pandas DataFrame. Results are NOT cached — call st.cache_data on
    the calling function if caching is desired.
    """
    conn = _connection()
    with conn.cursor() as cur:
        cur.execute(query, params or [])
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def execute(statement: str) -> None:
    """Execute a non-SELECT statement (INSERT, UPDATE, CREATE, etc.)."""
    conn = _connection()
    with conn.cursor() as cur:
        cur.execute(statement)
