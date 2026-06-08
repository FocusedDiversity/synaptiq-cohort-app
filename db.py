"""
Database connection manager.

Inside Databricks Apps the SDK picks up ambient credentials automatically —
no token or service principal config needed. Only DATABRICKS_HTTP_PATH
must be set as an App environment variable.

For local dev, create a .env file from .env.example.
"""

from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.config import Config

from dotenv import load_dotenv
load_dotenv()


@st.cache_resource(show_spinner="Connecting to Databricks…")
def _connection():
    http_path = os.getenv("DATABRICKS_HTTP_PATH")
    if not http_path:
        raise RuntimeError(
            "DATABRICKS_HTTP_PATH is not set.\n"
            "Add it as an environment variable in the Databricks App configuration."
        )

    cfg = Config()  # picks up ambient Databricks Apps token, or local env/.databrickscfg

    return sql.connect(
        server_hostname=cfg.host,
        http_path=http_path,
        credentials_provider=cfg.authenticate,
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
