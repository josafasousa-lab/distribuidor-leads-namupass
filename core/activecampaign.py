import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from core.config import (
    AC_API_KEY,
    AC_BASE_URL,
    FIELD_CATEGORIA,
    FIELD_ESTADO,
    FIELD_MODALIDADE,
    PIPELINE_ID,
    STAGE_INICIAL_ID,
)
from core.models import Consultor, Lead


def _transitorio(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return isinstance(exc, httpx.HTTPError)


_RETRY = dict(
    retry=retry_if_exception(_transitorio),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=8),
    reraise=True,
)


class ActiveCampaignClient:
    def __init__(self, base_url: str = AC_BASE_URL, api_key: str = AC_API_KEY) -> None:
        self._base = base_url.rstrip("/")
        self._http = httpx.Client(
            headers={"Api-Token": api_key, "Content-Type": "application/json"},
            timeout=15,
        )

    def _url(self, path: str) -> str:
        return f"{self._base}/api/3{path}"

    @retry(**_RETRY)
    def sync_contact(self, lead: Lead) -> int:
        telefone = lead.telefone or lead.telefone_raw
        email = f"{telefone.lstrip('+')}@placeholder.local"

        payload = {
            "contact": {
                "email": email,
                "firstName": lead.empresa,
                "phone": telefone,
                "fieldValues": [
                    {"field": str(FIELD_CATEGORIA), "value": lead.categoria},
                    {"field": str(FIELD_MODALIDADE), "value": lead.modalidade},
                    {"field": str(FIELD_ESTADO), "value": lead.estado},
                ],
            }
        }

        r = self._http.post(self._url("/contact/sync"), json=payload)
        r.raise_for_status()
        return int(r.json()["contact"]["id"])

    @retry(**_RETRY)
    def create_deal(self, contact_id: int, consultor: Consultor, lead: Lead) -> int:
        payload = {
            "deal": {
                "title": f"{lead.empresa} — {lead.categoria}",
                "value": "0",
                "currency": "brl",
                "group": str(PIPELINE_ID),
                "stage": str(STAGE_INICIAL_ID),
                "owner": str(consultor.ac_user_id),
                "contact": str(contact_id),
            }
        }

        r = self._http.post(self._url("/deals"), json=payload)
        r.raise_for_status()
        return int(r.json()["deal"]["id"])
