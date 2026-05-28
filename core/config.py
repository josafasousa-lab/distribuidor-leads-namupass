from dotenv import load_dotenv
import os

load_dotenv()

AC_BASE_URL: str = os.environ["ACTIVECAMPAIGN_URL"]
AC_API_KEY: str = os.environ["ACTIVECAMPAIGN_API_KEY"]

SHEET_ID: str = os.environ["SHEET_ID"]
SHEET_NAME: str = os.environ["SHEET_NAME"]

FIELD_CATEGORIA: int = int(os.environ["AC_FIELD_CATEGORIA"])
FIELD_MODALIDADE: int = int(os.environ["AC_FIELD_MODALIDADE"])
FIELD_ESTADO: int = int(os.environ["AC_FIELD_ESTADO"])

PIPELINE_ID: int = int(os.environ["AC_PIPELINE_ID"])
STAGE_INICIAL_ID: int = int(os.environ["AC_STAGE_INICIAL_ID"])

RATE_LIMIT_SLEEP: float = 0.25
