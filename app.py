import json
from pathlib import Path

import streamlit as st
import yaml

from core.importer import executar_job, retry_falhas
from core.models import Consultor
from core.sheets import get_valores_unicos, ler_leads_pendentes, ler_todos_leads

st.set_page_config(page_title="Distribuidor de Leads", layout="centered")
st.title("Distribuidor de Leads")

# ── Status ───────────────────────────────────────────────────────
try:
    total_base = len(ler_todos_leads())
    total_pendentes = len(ler_leads_pendentes())
    st.info(f"📊 **{total_base}** leads na base | **{total_pendentes}** não importados")
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

# ── Consultores ──────────────────────────────────────────────────
with open("data/consultores.yaml", encoding="utf-8") as _f:
    _yaml = yaml.safe_load(_f)
_consultores_ativos = [Consultor(**c) for c in _yaml["consultores"] if c.get("ativo")]

# ── Filtros ──────────────────────────────────────────────────────
st.subheader("Filtros")
col_a, col_b = st.columns(2)
with col_a:
    f_estados = st.multiselect("Estados", get_valores_unicos("estado"))
    f_cidades = st.multiselect("Cidades", get_valores_unicos("cidade"))
    f_categorias = st.multiselect("Categorias", get_valores_unicos("categoria"))
with col_b:
    f_origens = st.multiselect("Origens", get_valores_unicos("origem"))
    f_modalidades = st.multiselect("Modalidades", get_valores_unicos("modalidade"))

filtros = {
    "estados": f_estados,
    "cidades": f_cidades,
    "categorias": f_categorias,
    "origens": f_origens,
    "modalidades": f_modalidades,
}

qtd = st.number_input("Quantidade total", min_value=1, value=100, step=1)

# ── Seleção de consultores ───────────────────────────────────────
st.subheader("Consultores")
consultores_selecionados: list[Consultor] = []
for c in _consultores_ativos:
    if st.checkbox(c.nome, value=True, key=f"cons_{c.nome}"):
        consultores_selecionados.append(c)

# ── Gerar Preview ────────────────────────────────────────────────
if st.button("🔍 Gerar Preview"):
    if not consultores_selecionados:
        st.error("Selecione pelo menos um consultor.")
    else:
        with st.spinner("Calculando preview..."):
            try:
                preview = executar_job(filtros, int(qtd), consultores_selecionados, dry_run=True)
            except Exception as e:
                st.error(f"Erro ao gerar preview: {e}")
                st.stop()
        st.session_state.preview = preview
        st.session_state.exec_filtros = filtros
        st.session_state.exec_qtd = int(qtd)
        st.session_state.exec_consultores = consultores_selecionados

# ── Seção de Preview ─────────────────────────────────────────────
if "preview" in st.session_state:
    preview = st.session_state.preview
    st.divider()

    # Sumário
    c1, c2, c3 = st.columns(3)
    c1.metric("Elegíveis", preview.total_elegiveis)
    c2.metric("Selecionados", preview.total_selecionados)
    c3.metric("Inválidos", preview.total_invalidos)

    # Distribuição por consultor
    dist: dict[str, int] = {}
    for s in preview.sucessos:
        dist[s["consultor"]] = dist.get(s["consultor"], 0) + 1
    if dist:
        st.write("**Distribuição:** " + "  |  ".join(f"{k} → {v}" for k, v in dist.items()))

    # Tabela de leads
    linhas = [
        {
            "Empresa": s["empresa"],
            "Telefone": s["telefone"] or "",
            "Consultor": s["consultor"],
            "Válido": "✅",
        }
        for s in preview.sucessos
    ] + [
        {
            "Empresa": f["empresa"],
            "Telefone": f["telefone_raw"],
            "Consultor": "—",
            "Válido": "❌",
        }
        for f in preview.falhas
    ]

    if not linhas:
        st.warning("Nenhum lead encontrado com os filtros aplicados.")
    else:
        st.dataframe(linhas, use_container_width=True, hide_index=True)

    # Avisos de edge cases
    if preview.total_selecionados == 0 and preview.total_invalidos > 0:
        st.warning(
            f"Todos os {preview.total_invalidos} leads encontrados têm telefone inválido. "
            "Nenhum será importado."
        )
    elif preview.total_selecionados > 0 and preview.total_selecionados < st.session_state.exec_qtd:
        st.info(
            f"ℹ️ Apenas **{preview.total_selecionados}** leads disponíveis "
            f"(solicitados: {st.session_state.exec_qtd}). Todos serão importados."
        )

    # Modo simulação + Executar (só aparece quando há leads válidos)
    if preview.total_selecionados > 0:
        dry_run_mode = st.checkbox(
            "Modo simulação (dry-run — não executa, não escreve na planilha)",
            value=False,
            key="dry_run_mode",
        )
    else:
        dry_run_mode = False

    if preview.total_selecionados > 0 and st.button("🚀 Executar Importação", type="primary"):
        if not st.session_state.exec_consultores:
            st.error("Nenhum consultor selecionado.")
        else:
            total_sel = preview.total_selecionados
            progress_bar = st.progress(0.0)
            status_txt = st.empty()

            def _on_progress(atual: int, total: int) -> None:
                pct = atual / total if total > 0 else 1.0
                progress_bar.progress(min(pct, 1.0))
                status_txt.text(f"Processando {atual} / {total}...")

            try:
                resultado = executar_job(
                    st.session_state.exec_filtros,
                    st.session_state.exec_qtd,
                    st.session_state.exec_consultores,
                    dry_run=dry_run_mode,
                    progress_callback=None if dry_run_mode else _on_progress,
                )
            except Exception as e:
                st.error(f"Erro durante a importação: {e}")
                st.stop()

            progress_bar.progress(1.0)
            status_txt.empty()

            st.session_state.last_run = resultado
            del st.session_state.preview
            st.rerun()

# ── Resultado da última execução ─────────────────────────────────
if "last_run" in st.session_state:
    resultado = st.session_state.last_run
    st.divider()
    st.subheader("Resultado da última execução")

    if resultado.dry_run:
        st.info(
            f"🔵 Simulação concluída — {resultado.total_selecionados} leads seriam importados "
            f"(nenhuma alteração realizada)"
        )
    else:
        r1, r2 = st.columns(2)
        r1.metric("✅ Importados", len(resultado.sucessos))
        r2.metric("⚠️ Falhas", len(resultado.falhas))

        for falha in resultado.falhas:
            st.error(
                f"Linha {falha.get('lead_row')} — "
                f"{falha.get('empresa', '')}  |  {falha.get('error', '')}"
            )

    # Logs completos
    log_path = Path("data/logs/runs") / f"run_{resultado.run_id}.jsonl"
    if log_path.exists():
        with st.expander("📋 Ver logs completos"):
            st.code(log_path.read_text(encoding="utf-8"), language="json")

    # Retry falhas
    failures_path = Path("data/logs/failures") / f"run_{resultado.run_id}.jsonl"
    if not resultado.dry_run and failures_path.exists():
        if st.button("🔁 Retry falhas", key="btn_retry"):
            with st.spinner("Retentando falhas..."):
                try:
                    retry_result = retry_falhas(resultado.run_id)
                except Exception as e:
                    st.error(f"Erro no retry: {e}")
                    st.stop()
            st.session_state.last_run = retry_result
            st.rerun()
