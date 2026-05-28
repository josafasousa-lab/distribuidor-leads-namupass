from core.models import Lead

# filtros dict key → campo do Lead
_FILTRO_PARA_CAMPO: dict[str, str] = {
    "estados": "estado",
    "cidades": "cidade",
    "categorias": "categoria",
    "origens": "origem",
    "modalidades": "modalidade",
}


def aplicar(leads: list[Lead], filtros: dict) -> list[Lead]:
    result = leads
    for chave, campo in _FILTRO_PARA_CAMPO.items():
        valores = filtros.get(chave, [])
        if not valores:
            continue
        norm = {v.strip().lower() for v in valores}
        result = [
            lead for lead in result
            if getattr(lead, campo, "").strip().lower() in norm
        ]
    return result
