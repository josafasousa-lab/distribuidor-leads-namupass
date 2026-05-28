# TODO.md — Roadmap de Implementação

> Trabalhar **uma fase por vez**.
> Não começar a próxima fase sem:
> 1. Confirmar que os arquivos criados estão alinhados com o SPEC.md
> 2. Listar divergências encontradas (se houver)
> 3. Receber confirmação explícita para avançar

---

## Fase 1 — Esqueleto e configuração

**Objetivo:** projeto rodável, estrutura criada, dependências instaladas.

- [ ] Criar estrutura de pastas conforme SPEC.md §2
- [ ] `requirements.txt` com todas as dependências do SPEC.md §3
- [ ] `.env.example` conforme SPEC.md §11
- [ ] `.gitignore` (incluir: `.env`, `credentials.json`, `.venv/`, `__pycache__/`, `data/logs/`)
- [ ] `core/__init__.py` (arquivo vazio)
- [ ] `core/config.py` — carrega `.env`, expõe todas as constantes do SPEC.md §6 (config.py)
- [ ] `core/logger.py` — configura loguru, expõe `make_run_logger` e `gerar_run_id`
- [ ] `data/logs/runs/.gitkeep`
- [ ] `data/logs/failures/.gitkeep`
- [ ] `README.md` com instruções de setup do SPEC.md §13

**Critério de conclusão:** `python -c "from core.config import AC_BASE_URL"` roda sem erro (com `.env` preenchido).

---

## Fase 2 — Models e Google Sheets

**Objetivo:** conseguir ler a planilha e retornar objetos `Lead` tipados.

- [ ] `core/models.py` — classes `Lead`, `Consultor`, `ImportJob`, `RunReport` conforme SPEC.md §5
- [ ] `data/consultores.yaml` — arquivo de exemplo com 4 consultores (2 ativos, 2 inativos) conforme SPEC.md §10
- [ ] `core/sheets.py`:
  - [ ] `ler_todos_leads() -> list[Lead]`
  - [ ] `ler_leads_pendentes() -> list[Lead]`
  - [ ] `marcar_importado(row_id, consultor_nome)`
  - [ ] `get_valores_unicos(campo) -> list[str]`
  - [ ] Cache de 60s na leitura

**Critério de conclusão:** `python -c "from core.sheets import ler_leads_pendentes; print(len(ler_leads_pendentes()))"` retorna número sem erro.

---

## Fase 3 — Lógica pura (sem I/O externo)

**Objetivo:** os três módulos de lógica com cobertura de testes.

### `core/phone.py` + `tests/test_phone.py`

- [ ] `normalizar(raw: str) -> str | None`
- [ ] Testes obrigatórios:
  - [ ] `(11) 99999-9999` → `+5511999999999`
  - [ ] `11.99999.9999` → `+5511999999999`
  - [ ] `+55 11 9 9999-9999` → `+5511999999999`
  - [ ] `99999-9999` (sem DDD) → `None`
  - [ ] `""` (vazio) → `None`
  - [ ] `None` → `None`
  - [ ] Número com 8 dígitos fixo válido → normalizado
  - [ ] Sequência inválida `00000-0000` → `None`

### `core/filters.py` + `tests/test_filters.py`

- [ ] `aplicar(leads, filtros) -> list[Lead]`
- [ ] Testes obrigatórios:
  - [ ] Filtro vazio → retorna todos
  - [ ] Filtro por estado → retorna só do estado
  - [ ] Múltiplos filtros combinados → interseção
  - [ ] Filtro com valor inexistente → lista vazia
  - [ ] Case-insensitive: `"bahia"` == `"Bahia"` == `"BAHIA"`

### `core/distributor.py` + `tests/test_distributor.py`

- [ ] `distribuir(leads, consultores) -> list[tuple[Lead, Consultor]]`
- [ ] Testes obrigatórios:
  - [ ] 300 leads / 4 consultores → 75 cada
  - [ ] 301 leads / 4 consultores → 76, 75, 75, 75
  - [ ] 3 leads / 4 consultores → 1, 1, 1, 0
  - [ ] 0 consultores → `ValueError`
  - [ ] 1 consultor → todos pra ele
  - [ ] Ordem é determinística (mesma entrada → mesma saída)

**Critério de conclusão:** `pytest tests/` — todos os testes passam.

---

## Fase 4 — Client ActiveCampaign

**Objetivo:** conseguir criar contato e deal no AC com retry e tratamento de erro.

- [ ] `core/activecampaign.py`:
  - [ ] Classe `ActiveCampaignClient`
  - [ ] `sync_contact(lead) -> int` com retry via tenacity
  - [ ] `create_deal(contact_id, consultor, lead) -> int` com retry via tenacity
  - [ ] Retry só em: `httpx.HTTPError`, `5xx`, `429`
  - [ ] Sem retry em: outros `4xx`
  - [ ] Backoff: 2s, 4s, 8s (3 tentativas)

**Critério de conclusão (manual):** teste com 1 lead real em conta AC de sandbox. Verificar contato criado + deal vinculado + campos customizados preenchidos.

> ⚠️ Antes de implementar: confirmar os IDs reais de campos customizados, pipeline e stage no AC via `GET /api/3/fields` e `GET /api/3/pipelines`. Anotar no `.env`.

---

## Fase 5 — Orquestrador

**Objetivo:** `importer.py` orquestrador completo com dry-run e retry de falhas.

- [ ] `core/importer.py`:
  - [ ] `executar_job(filtros, qtd, consultores_ativos, dry_run=False) -> RunReport`
  - [ ] Fluxo completo conforme SPEC.md §6 (importer.py), itens 1–10
  - [ ] `dry_run=True` retorna RunReport preenchido sem chamar AC nem Sheets
  - [ ] `retry_falhas(run_id: str) -> RunReport`
  - [ ] Salva failures em `data/logs/failures/run_{run_id}.jsonl`
  - [ ] `time.sleep(RATE_LIMIT_SLEEP)` entre cada lead

**Critério de conclusão:** executar `executar_job` com `dry_run=True` sobre planilha real e verificar que o `RunReport` tem os campos corretos.

---

## Fase 6 — Interface Streamlit

**Objetivo:** UI funcional que o operador não-técnico usa sem abrir terminal.

- [ ] `app.py` com layout conforme SPEC.md §9:
  - [ ] Header com contagem de leads (total e pendentes)
  - [ ] Filtros multiselect populados dinamicamente da planilha
  - [ ] Seleção de quantidade com `st.number_input`
  - [ ] Checkboxes de consultores (lidos do `consultores.yaml`, apenas ativos)
  - [ ] Botão "Gerar Preview"
  - [ ] Seção de preview: sumário + tabela + distribuição por consultor
  - [ ] Checkbox "Modo simulação"
  - [ ] Botão "Executar Importação" (só visível após preview)
  - [ ] Barra de progresso durante execução
  - [ ] Seção de resultado: contagem de sucessos e falhas
  - [ ] Botão "Ver logs" (expander com conteúdo do JSONL)
  - [ ] Botão "Retry falhas" (só visível se houver arquivo de failures)

**Critério de conclusão:** operador consegue ir do filtro até o preview sem erros. Botão "Executar" aparece corretamente.

---

## Fase 7 — Polimento e edge cases

**Objetivo:** cobrir casos que aparecem em uso real.

- [ ] Tratamento de dados inválidos na planilha (linha com empresa vazia, categoria faltando)
- [ ] Mensagem clara quando nenhum lead elegível é encontrado com os filtros
- [ ] Mensagem clara quando quantidade pedida > elegíveis disponíveis
- [ ] Retry de falhas funcional de ponta a ponta (ler JSONL → executar → novo JSONL)
- [ ] README com screenshot da UI
- [ ] Testar com planilha real de produção (volume real, formatos reais de telefone)
- [ ] Verificar rate limit: run com 300 leads não gera `429` no AC

**Critério de conclusão:** run completo de 100 leads com planilha real, sem erros inesperados, planilha atualizada, logs gerados.

---

## Ordem de dependências entre módulos

```
config.py
   └── logger.py
   └── models.py
         └── sheets.py
         └── phone.py
               └── filters.py
               └── distributor.py
                     └── activecampaign.py
                           └── importer.py
                                 └── app.py
```

Implemente nessa ordem. Não pule camadas.
