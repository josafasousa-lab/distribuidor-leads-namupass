import json
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.activecampaign import ActiveCampaignClient
from core.config import RATE_LIMIT_SLEEP
from core.distributor import distribuir
from core.filters import aplicar
from core.logger import gerar_run_id, make_run_logger
from core.models import Consultor, Lead, RunReport
from core.phone import normalizar
from core.sheets import ler_leads_pendentes, ler_todos_leads, marcar_importado


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalizar_telefones(leads: list[Lead]) -> tuple[list[Lead], list[Lead]]:
    for lead in leads:
        lead.telefone = normalizar(lead.telefone_raw)
    validos = [l for l in leads if l.telefone is not None]
    invalidos = [l for l in leads if l.telefone is None]
    return validos, invalidos


def _deduplicar(leads: list[Lead]) -> list[Lead]:
    seen: set[str] = set()
    result: list[Lead] = []
    for lead in sorted(leads, key=lambda l: l.row_id):
        if lead.telefone not in seen:
            seen.add(lead.telefone)
            result.append(lead)
    return result


def _salvar_failures(run_id: str, falhas: list[dict]) -> None:
    if not falhas:
        return
    path = Path("data/logs/failures") / f"run_{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for falha in falhas:
            f.write(json.dumps(falha, ensure_ascii=False) + "\n")


def executar_job(
    filtros: dict,
    qtd: int,
    consultores_ativos: list[Consultor],
    dry_run: bool = False,
    progress_callback=None,  # callable(atual: int, total: int) | None
) -> RunReport:
    run_id = gerar_run_id()
    logger = make_run_logger(run_id)

    # 1. Leads pendentes
    leads = ler_leads_pendentes()

    # 2. Filtros
    leads = aplicar(leads, filtros)
    total_elegiveis = len(leads)

    # 3. Normalizar telefones
    validos, invalidos = _normalizar_telefones(leads)
    total_invalidos = len(invalidos)

    # 4. Deduplicar por telefone normalizado
    validos = _deduplicar(validos)

    # 5. Truncar
    selecionados = validos[:qtd]
    total_selecionados = len(selecionados)

    # 6. Distribuir
    pares = distribuir(selecionados, consultores_ativos)

    # 7. Dry run — retorna preview sem executar
    if dry_run:
        return RunReport(
            run_id=run_id,
            dry_run=True,
            total_elegiveis=total_elegiveis,
            total_selecionados=total_selecionados,
            total_invalidos=total_invalidos,
            sucessos=[
                {
                    "lead_row": lead.row_id,
                    "empresa": lead.empresa,
                    "telefone": lead.telefone,
                    "consultor": consultor.nome,
                    "valido": True,
                }
                for lead, consultor in pares
            ],
            falhas=[
                {
                    "lead_row": lead.row_id,
                    "empresa": lead.empresa,
                    "telefone_raw": lead.telefone_raw,
                    "valido": False,
                    "reason": "telefone inválido",
                }
                for lead in invalidos
            ],
            executado=False,
        )

    # 8. Executar
    ac = ActiveCampaignClient()
    sucessos: list[dict] = []
    falhas: list[dict] = []
    total_pares = len(pares)

    for i, (lead, consultor) in enumerate(pares):
        ts = _ts()
        try:
            contact_id = ac.sync_contact(lead)
            logger.info(json.dumps({
                "ts": ts, "run_id": run_id, "lead_row": lead.row_id,
                "empresa": lead.empresa, "consultor": consultor.nome,
                "action": "contact_synced", "contact_id": contact_id, "ok": True,
            }, ensure_ascii=False))

            deal_id = ac.create_deal(contact_id, consultor, lead)
            logger.info(json.dumps({
                "ts": ts, "run_id": run_id, "lead_row": lead.row_id,
                "action": "deal_created", "deal_id": deal_id, "ok": True,
            }, ensure_ascii=False))

            marcar_importado(lead.row_id, consultor.nome)

            sucessos.append({
                "lead_row": lead.row_id,
                "empresa": lead.empresa,
                "consultor": consultor.nome,
                "contact_id": contact_id,
                "deal_id": deal_id,
            })

        except Exception as exc:
            error_msg = str(exc)
            logger.error(json.dumps({
                "ts": ts, "run_id": run_id, "lead_row": lead.row_id,
                "empresa": lead.empresa, "consultor": consultor.nome,
                "action": "failed", "ok": False, "error": error_msg,
            }, ensure_ascii=False))
            falhas.append({
                "run_id": run_id,
                "lead_row": lead.row_id,
                "empresa": lead.empresa,
                "consultor": consultor.nome,
                "error": error_msg,
            })

        if progress_callback is not None:
            progress_callback(i + 1, total_pares)
        time.sleep(RATE_LIMIT_SLEEP)

    # 9. Salvar failures para retry
    _salvar_failures(run_id, falhas)

    # 10. Retornar
    return RunReport(
        run_id=run_id,
        dry_run=False,
        total_elegiveis=total_elegiveis,
        total_selecionados=total_selecionados,
        total_invalidos=total_invalidos,
        sucessos=sucessos,
        falhas=falhas,
        executado=True,
    )


def retry_falhas(run_id: str) -> RunReport:
    failures_path = Path("data/logs/failures") / f"run_{run_id}.jsonl"
    if not failures_path.exists():
        raise FileNotFoundError(f"Arquivo de falhas não encontrado: {failures_path}")

    retry_run_id = gerar_run_id()
    logger = make_run_logger(retry_run_id)
    ac = ActiveCampaignClient()

    with open("data/consultores.yaml", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)
    consultores_map: dict[str, Consultor] = {
        c["nome"]: Consultor(**c) for c in yaml_data["consultores"]
    }

    todos = ler_todos_leads()
    leads_por_row: dict[int, Lead] = {lead.row_id: lead for lead in todos}

    with failures_path.open(encoding="utf-8") as f:
        entries = [json.loads(linha) for linha in f if linha.strip()]

    sucessos: list[dict] = []
    falhas_exec: list[dict] = []  # falhas de execução (salvas para novo retry)
    falhas_all: list[dict] = []   # todas as falhas (para o RunReport)

    for entry in entries:
        row_id: int = entry["lead_row"]
        consultor_nome: str = entry["consultor"]
        ts = _ts()

        lead = leads_por_row.get(row_id)
        if lead is None:
            msg = "lead não encontrado na planilha"
            logger.warning(json.dumps({
                "ts": ts, "run_id": retry_run_id, "lead_row": row_id,
                "action": "skipped", "reason": msg, "ok": False,
            }))
            falhas_all.append({"lead_row": row_id, "error": msg})
            continue

        if lead.data_importacao:
            logger.info(json.dumps({
                "ts": ts, "run_id": retry_run_id, "lead_row": row_id,
                "empresa": lead.empresa, "action": "skipped",
                "reason": "already imported", "ok": True,
            }, ensure_ascii=False))
            continue

        consultor = consultores_map.get(consultor_nome)
        if consultor is None:
            msg = f"consultor '{consultor_nome}' não encontrado no yaml"
            logger.error(json.dumps({
                "ts": ts, "run_id": retry_run_id, "lead_row": row_id,
                "action": "skipped", "reason": msg, "ok": False,
            }))
            falhas_all.append({"lead_row": row_id, "error": msg})
            continue

        lead.telefone = normalizar(lead.telefone_raw)
        if lead.telefone is None:
            msg = "telefone inválido"
            logger.error(json.dumps({
                "ts": ts, "run_id": retry_run_id, "lead_row": row_id,
                "empresa": lead.empresa, "action": "skipped", "reason": msg, "ok": False,
            }, ensure_ascii=False))
            falhas_all.append({"lead_row": row_id, "empresa": lead.empresa, "error": msg})
            continue

        try:
            contact_id = ac.sync_contact(lead)
            deal_id = ac.create_deal(contact_id, consultor, lead)
            marcar_importado(lead.row_id, consultor.nome)

            logger.info(json.dumps({
                "ts": ts, "run_id": retry_run_id, "lead_row": lead.row_id,
                "empresa": lead.empresa, "consultor": consultor.nome,
                "action": "retry_success",
                "contact_id": contact_id, "deal_id": deal_id, "ok": True,
            }, ensure_ascii=False))

            sucessos.append({
                "lead_row": lead.row_id,
                "empresa": lead.empresa,
                "consultor": consultor.nome,
                "contact_id": contact_id,
                "deal_id": deal_id,
            })

        except Exception as exc:
            error_msg = str(exc)
            logger.error(json.dumps({
                "ts": ts, "run_id": retry_run_id, "lead_row": lead.row_id,
                "empresa": lead.empresa, "consultor": consultor.nome,
                "action": "retry_failed", "ok": False, "error": error_msg,
            }, ensure_ascii=False))
            entry_falha = {
                "run_id": retry_run_id,
                "lead_row": lead.row_id,
                "empresa": lead.empresa,
                "consultor": consultor.nome,
                "error": error_msg,
            }
            falhas_exec.append(entry_falha)
            falhas_all.append(entry_falha)

        time.sleep(RATE_LIMIT_SLEEP)

    _salvar_failures(retry_run_id, falhas_exec)

    return RunReport(
        run_id=retry_run_id,
        dry_run=False,
        total_elegiveis=len(entries),
        total_selecionados=len(entries),
        total_invalidos=0,
        sucessos=sucessos,
        falhas=falhas_all,
        executado=True,
    )
