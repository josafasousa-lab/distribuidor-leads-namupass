from core.models import Consultor, Lead


def distribuir(leads: list[Lead], consultores: list[Consultor]) -> list[tuple[Lead, Consultor]]:
    if not consultores:
        raise ValueError("Lista de consultores não pode ser vazia")
    ordenados = sorted(leads, key=lambda l: l.row_id)
    return [(lead, consultores[i % len(consultores)]) for i, lead in enumerate(ordenados)]
