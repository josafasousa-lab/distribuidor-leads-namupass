import os

from dotenv import load_dotenv

load_dotenv()


def _get(key: str) -> str | None:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key)


AC_BASE_URL: str = _get("ACTIVECAMPAIGN_URL")
AC_API_KEY: str = _get("ACTIVECAMPAIGN_API_KEY")

SHEET_ID: str = _get("SHEET_ID")
SHEET_NAME: str = _get("SHEET_NAME")

FIELD_CATEGORIA: int = int(_get("AC_FIELD_CATEGORIA"))
FIELD_MODALIDADE: int = int(_get("AC_FIELD_MODALIDADE"))
FIELD_ESTADO: int = int(_get("AC_FIELD_ESTADO"))

PIPELINE_ID: int = int(_get("AC_PIPELINE_ID"))
STAGE_INICIAL_ID: int = int(_get("AC_STAGE_INICIAL_ID"))

RATE_LIMIT_SLEEP: float = 0.25
