import pytest
from core.distributor import distribuir
from core.models import Consultor, Lead


def _leads(n: int) -> list[Lead]:
    return [
        Lead(
            row_id=i,
            empresa=f"Empresa {i}",
            telefone_raw="11999999999",
            estado="SP",
            cidade="São Paulo",
            categoria="Academia",
            origem="Wellhub",
            modalidade="Presencial",
        )
        for i in range(1, n + 1)
    ]


def _consultores(n: int) -> list[Consultor]:
    return [Consultor(nome=f"C{i}", ac_user_id=i) for i in range(1, n + 1)]


def _contagem(pares, consultores):
    nomes = [c.nome for c in consultores]
    counts = {nome: 0 for nome in nomes}
    for _, c in pares:
        counts[c.nome] += 1
    return [counts[nome] for nome in nomes]


def test_300_leads_4_consultores_75_cada():
    pares = distribuir(_leads(300), _consultores(4))
    assert _contagem(pares, _consultores(4)) == [75, 75, 75, 75]


def test_301_leads_4_consultores_distribuicao_extra_no_primeiro():
    pares = distribuir(_leads(301), _consultores(4))
    assert _contagem(pares, _consultores(4)) == [76, 75, 75, 75]


def test_3_leads_4_consultores():
    pares = distribuir(_leads(3), _consultores(4))
    assert _contagem(pares, _consultores(4)) == [1, 1, 1, 0]


def test_zero_consultores_levanta_value_error():
    with pytest.raises(ValueError):
        distribuir(_leads(5), [])


def test_1_consultor_recebe_todos():
    pares = distribuir(_leads(10), _consultores(1))
    assert all(c.nome == "C1" for _, c in pares)


def test_determinismo():
    leads = _leads(10)
    cons = _consultores(3)
    assert distribuir(leads, cons) == distribuir(leads, cons)


def test_ordenacao_por_row_id():
    leads = _leads(5)
    leads_embaralhados = [leads[4], leads[0], leads[2], leads[1], leads[3]]
    pares = distribuir(leads_embaralhados, _consultores(1))
    row_ids = [lead.row_id for lead, _ in pares]
    assert row_ids == sorted(row_ids)
