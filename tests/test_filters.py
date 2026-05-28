from core.filters import aplicar
from core.models import Lead


def _lead(row_id, estado="SP", cidade="São Paulo", categoria="Academia",
          origem="Wellhub", modalidade="Presencial"):
    return Lead(
        row_id=row_id,
        empresa=f"Empresa {row_id}",
        telefone_raw="(11) 99999-9999",
        estado=estado,
        cidade=cidade,
        categoria=categoria,
        origem=origem,
        modalidade=modalidade,
    )


LEADS = [
    _lead(1, estado="SP", cidade="São Paulo",    categoria="Academia",  origem="Wellhub",   modalidade="Presencial"),
    _lead(2, estado="SP", cidade="Campinas",     categoria="Nutrição",  origem="Orgânico",  modalidade="Online"),
    _lead(3, estado="RJ", cidade="Rio de Janeiro", categoria="Academia", origem="Wellhub",  modalidade="Presencial"),
    _lead(4, estado="Bahia", cidade="Salvador",   categoria="Yoga",      origem="Orgânico",  modalidade="Presencial"),
]


def test_filtro_vazio_retorna_todos():
    assert aplicar(LEADS, {}) == LEADS


def test_filtro_por_estado():
    resultado = aplicar(LEADS, {"estados": ["SP"]})
    assert len(resultado) == 2
    assert all(l.estado == "SP" for l in resultado)


def test_multiplos_filtros_intersecao():
    resultado = aplicar(LEADS, {"estados": ["SP"], "modalidades": ["Online"]})
    assert len(resultado) == 1
    assert resultado[0].row_id == 2


def test_filtro_valor_inexistente_retorna_vazio():
    assert aplicar(LEADS, {"estados": ["AM"]}) == []


def test_case_insensitive():
    assert aplicar(LEADS, {"estados": ["bahia"]}) == aplicar(LEADS, {"estados": ["Bahia"]})
    assert aplicar(LEADS, {"estados": ["BAHIA"]}) == aplicar(LEADS, {"estados": ["Bahia"]})
    assert len(aplicar(LEADS, {"estados": ["bahia"]})) == 1
