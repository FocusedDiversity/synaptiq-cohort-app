"""
Database connection manager.

Inside Databricks Apps, DATABRICKS_HOST and DATABRICKS_TOKEN are injected
automatically by the runtime. Only DATABRICKS_HTTP_PATH needs to be set
in app.yaml (already configured).

For local dev, create a .env file from .env.example.
"""

from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource(show_spinner="Connecting to Databricks…")
def _connection():
    host      = os.getenv("DATABRICKS_HOST")
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    token     = os.getenv("DATABRICKS_TOKEN")

    if not host or not http_path or not token:
        missing = [k for k, v in {
            "DATABRICKS_HOST": host,
            "DATABRICKS_HTTP_PATH": http_path,
            "DATABRICKS_TOKEN": token,
        }.items() if not v]
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return sql.connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
    )


def run_query(query: str, params: list | None = None) -> pd.DataFrame:
    conn = _connection()
    with conn.cursor() as cur:
        cur.execute(query, params or [])
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def execute(statement: str) -> None:
    conn = _connection()
    with conn.cursor() as cur:
        cur.execute(statement)
