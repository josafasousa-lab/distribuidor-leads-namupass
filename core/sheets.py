import time
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from core.config import SHEET_ID, SHEET_NAME
from core.models import Lead

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Cabeçalho da planilha (lowercase) → campo interno
# Campos de leitura: populam o modelo Lead
# Campos de escrita: novo_responsavel e fase_subida_active (só usados em marcar_importado)
_COLUMN_MAP: dict[str, str] = {
    "empresa": "empresa",
    "telefone estabelecimento": "telefone_raw",
    "estado": "estado",
    "cidade": "cidade",
    "endereço": "endereco",
    "categoria": "categoria",
    "origem do lead": "origem",
    "principal modalidade": "modalidade",
    "data de importação (active)": "data_importacao",
    "novo responsável": "novo_responsavel",
    "fase de subida (active)": "fase_subida_active",
}

_CACHE_TTL = 60.0
_cache: dict | None = None  # {"leads": list[Lead], "col_idx": dict[str, int], "ts": float}


def _connect() -> gspread.Worksheet:
    try:
        creds = Credentials.from_service_account_file("credentials.json", scopes=_SCOPES)
    except FileNotFoundError:
        import streamlit as st
        info = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)


def _fetch() -> dict:
    sheet = _connect()
    values = sheet.get_all_values()

    if not values:
        return {"leads": [], "col_idx": {}, "ts": time.time()}

    # Linha 1: título mesclado; linha 2: vazia; linha 3: cabeçalho; dados a partir da linha 4
    if len(values) < 3:
        return {"leads": [], "col_idx": {}, "ts": time.time()}

    header = [h.strip().lower() for h in values[2]]

    # campo interno → índice de coluna 1-based (para uso direto no gspread)
    col_idx: dict[str, int] = {}
    for i, h in enumerate(header):
        field = _COLUMN_MAP.get(h)
        if field:
            col_idx[field] = i + 1

    leads: list[Lead] = []
    for row_num, row in enumerate(values[3:], start=4):

        def cell(field: str, _row=row, _col_idx=col_idx) -> str:
            idx = _col_idx.get(field)
            if idx is None:
                return ""
            zero = idx - 1
            return _row[zero].strip() if zero < len(_row) else ""

        empresa = cell("empresa")
        if not empresa:
            continue

        leads.append(Lead(
            row_id=row_num,
            empresa=empresa,
            telefone_raw=cell("telefone_raw"),
            estado=cell("estado"),
            cidade=cell("cidade"),
            endereco=cell("endereco"),
            categoria=cell("categoria"),
            origem=cell("origem"),
            modalidade=cell("modalidade"),
            data_importacao=cell("data_importacao"),
        ))

    return {"leads": leads, "col_idx": col_idx, "ts": time.time()}


def _get_cache() -> dict:
    global _cache
    if _cache is None or (time.time() - _cache["ts"]) >= _CACHE_TTL:
        _cache = _fetch()
    return _cache


def _invalidar_cache() -> None:
    global _cache
    _cache = None


def ler_todos_leads() -> list[Lead]:
    return _get_cache()["leads"]


def ler_leads_pendentes() -> list[Lead]:
    return [lead for lead in ler_todos_leads() if not lead.data_importacao]


def _a1(row: int, col: int) -> str:
    """Converte row/col 1-based para notação A1 (ex: row=4, col=3 → 'C4')."""
    col_str = ""
    c = col
    while c > 0:
        c, rem = divmod(c - 1, 26)
        col_str = chr(65 + rem) + col_str
    return f"{col_str}{row}"


def marcar_importado(row_id: int, consultor_nome: str) -> None:
    cache = _get_cache()
    col_idx = cache["col_idx"]

    col_data = col_idx.get("data_importacao")
    if col_data is None:
        raise ValueError("Coluna 'data_importacao' não encontrada na planilha")

    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")

    updates = [{"range": _a1(row_id, col_data), "values": [[data_hora]]}]

    col_resp = col_idx.get("novo_responsavel")
    if col_resp is not None:
        updates.append({"range": _a1(row_id, col_resp), "values": [[consultor_nome]]})

    col_fase = col_idx.get("fase_subida_active")
    if col_fase is not None:
        updates.append({"range": _a1(row_id, col_fase), "values": [["Novo Lead"]]})

    sheet = _connect()
    sheet.batch_update(updates)
    _invalidar_cache()


def get_valores_unicos(campo: str) -> list[str]:
    valores = {
        getattr(lead, campo, "")
        for lead in ler_todos_leads()
    }
    return sorted(v for v in valores if v)
