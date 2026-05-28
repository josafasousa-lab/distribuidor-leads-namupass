# SPEC.md — Distribuidor de Leads → ActiveCampaign

> Fonte da verdade do projeto. Qualquer dúvida de implementação, consulte aqui primeiro.

---

## 1. Objetivo

Ferramenta operacional local que automatiza a distribuição e importação de leads de uma planilha Google Sheets para o ActiveCampaign (contatos + deals), eliminando um processo manual feito hoje por uma pessoa.

**Não é um CRM. Não é um SaaS. Não tem overengineering.**

---

## 2. Estrutura de pastas

```
leads-distributor/
├── .env                          # ACTIVECAMPAIGN_URL, API_KEY, SHEET_ID, SHEET_NAME
├── .env.example
├── .gitignore
├── credentials.json              # service account Google (não versionar)
├── requirements.txt
├── README.md
├── SPEC.md
├── DECISIONS.md
├── TODO.md
│
├── app.py                        # Streamlit — único entrypoint da UI
│
├── core/
│   ├── __init__.py
│   ├── config.py                 # carrega .env, constantes
│   ├── models.py                 # Pydantic: Lead, Consultor, ImportJob, RunReport
│   ├── sheets.py                 # ler/escrever planilha (gspread)
│   ├── filters.py                # aplicar filtros de estado/cidade/região/etc
│   ├── distributor.py            # divisão igualitária round-robin
│   ├── phone.py                  # normalização de telefone BR (E.164)
│   ├── activecampaign.py         # client HTTP: sync_contact + create_deal
│   ├── importer.py               # orquestrador do import job
│   └── logger.py                 # config loguru
│
├── data/
│   ├── consultores.yaml          # lista de consultores ativos
│   └── logs/
│       ├── runs/                 # 1 arquivo JSONL por execução
│       └── failures/             # falhas isoladas para retry
│
└── tests/
    ├── test_phone.py
    ├── test_distributor.py
    └── test_filters.py
```

---

## 3. Stack

```
Python 3.11+
streamlit              # UI
gspread                # Google Sheets
google-auth            # autenticação service account
httpx                  # chamadas ActiveCampaign
phonenumbers           # normalização telefone BR
pydantic               # validação de dados (v2)
python-dotenv          # variáveis de ambiente
tenacity               # retry com backoff exponencial
loguru                 # logs estruturados
pyyaml                 # leitura do consultores.yaml
pytest                 # testes
```

---

## 4. Planilha Google Sheets

### Colunas esperadas (ordem pode variar — usar cabeçalho para mapear)

| Coluna | Campo interno | Descrição |
|---|---|---|
| Nome da Empresa | `empresa` | Nome do lead |
| Telefone | `telefone_raw` | Telefone bruto, qualquer formato |
| Estado | `estado` | UF ou nome completo |
| Cidade | `cidade` | Nome da cidade |
| Endereço | `endereco` | Opcional |
| Categoria | `categoria` | Ex: academia, nutrição |
| Origem | `origem` | Ex: Wellhub, orgânico |
| Modalidade | `modalidade` | Ex: presencial, online |
| Região | `regiao` | Ex: interior SP, nordeste |
| Data de importação (Active) | `data_importacao` | **Vazia = não importado** |

### Regras de leitura

- A primeira linha é sempre o cabeçalho.
- Leads elegíveis = linhas onde `data_importacao` está vazia ou é `None`.
- Ao importar com sucesso, escrever na coluna `data_importacao` o valor `DD/MM/YYYY HH:MM — {nome_consultor}`.
- Usar `row_id` (número da linha na planilha, base 1) para referenciar e atualizar linhas.

---

## 5. Modelos de dados (Pydantic)

```python
class Lead(BaseModel):
    row_id: int
    empresa: str
    telefone_raw: str
    telefone: str | None = None   # preenchido após normalização
    estado: str
    cidade: str
    endereco: str = ""
    categoria: str
    origem: str
    modalidade: str
    regiao: str
    data_importacao: str = ""

class Consultor(BaseModel):
    nome: str
    ac_user_id: int               # ID do usuário no ActiveCampaign
    ativo: bool = True

class RunReport(BaseModel):
    run_id: str
    dry_run: bool
    total_elegiveis: int
    total_selecionados: int
    total_invalidos: int
    sucessos: list
    falhas: list
    executado: bool
```

---

## 6. Módulos — responsabilidades

### `core/config.py`
- Carrega `.env` via `python-dotenv`
- Expõe: `AC_BASE_URL`, `AC_API_KEY`, `SHEET_ID`, `SHEET_NAME`
- Expõe IDs de campos customizados do AC: `FIELD_CATEGORIA`, `FIELD_ORIGEM`, `FIELD_CIDADE`, `FIELD_ESTADO` (valores configuráveis via `.env`)
- Expõe: `PIPELINE_ID`, `STAGE_INICIAL_ID` (IDs do pipeline no AC)
- Expõe: `RATE_LIMIT_SLEEP = 0.25` (segundos entre chamadas AC)

### `core/logger.py`
- Configura loguru com dois sinks:
  1. Console (INFO+)
  2. Arquivo `data/logs/runs/run_{run_id}.jsonl` (DEBUG+, formato JSON)
- Expõe função `make_run_logger(run_id: str) -> Logger`
- Expõe função `gerar_run_id() -> str` (formato: `YYYY-MM-DD_HH-MM-SS`)

### `core/sheets.py`
- `ler_todos_leads() -> list[Lead]` — lê toda a planilha, retorna todos os leads
- `ler_leads_pendentes() -> list[Lead]` — filtra `data_importacao` vazia
- `marcar_importado(row_id: int, consultor_nome: str)` — escreve data/hora na coluna correta
- `get_valores_unicos(campo: str) -> list[str]` — retorna valores únicos de uma coluna (para popular filtros da UI)
- Autenticação via `credentials.json` (service account)
- Cache de 60s na leitura (evitar chamadas repetidas ao Sheets na mesma sessão)

### `core/filters.py`
- `aplicar(leads, filtros) -> list[Lead]`
- `filtros` é um dict com chaves opcionais: `estados`, `cidades`, `regioes`, `categorias`, `origens`, `modalidades`
- Cada chave é uma `list[str]`. Lista vazia ou ausente = sem filtro naquele campo.
- Comparação case-insensitive e com strip de espaços.

### `core/phone.py`
- `normalizar(raw: str) -> str | None`
- Usa `phonenumbers.parse(raw, "BR")`
- Retorna E.164 (`+5511999999999`) se válido, `None` se inválido
- Deve lidar com: formatos sujos (`(11) 99999-9999`, `11.99999.9999`, `+55 11 9 9999-9999`), números com 8 dígitos (fixo), DDD faltando (retorna None)

### `core/distributor.py`
- `distribuir(leads, consultores) -> list[tuple[Lead, Consultor]]`
- Round-robin estável: ordena leads por `row_id` antes de distribuir
- Levanta `ValueError` se `consultores` for lista vazia
- 300 leads / 4 consultores = 75 cada (distribuição exata)
- 301 leads / 4 consultores = 76, 75, 75, 75 (determinístico, o extra vai pro primeiro)

### `core/activecampaign.py`
- Classe `ActiveCampaignClient(base_url, api_key)`
- `sync_contact(lead: Lead) -> int` — retorna `contact_id`
  - Usa `POST /api/3/contact/sync`
  - Campo `email`: usar `lead.email` se existir, senão `{telefone_sem_plus}@placeholder.local`
  - Preenche campos customizados via `fieldValues`
- `create_deal(contact_id, consultor, lead) -> int` — retorna `deal_id`
  - Usa `POST /api/3/deals`
  - `title`: `"{empresa} — {categoria}"`
  - `value`: 0, `currency`: "brl"
- Retry automático em ambos os métodos:
  - 3 tentativas máximo
  - Backoff exponencial: 2s, 4s, 8s
  - Só retentar: `httpx.HTTPError`, status `5xx`, status `429`
  - NÃO retentar: outros `4xx` (erro de dado, não de rede)
- `time.sleep(RATE_LIMIT_SLEEP)` é responsabilidade do `importer.py`, não do client

### `core/importer.py`
- `executar_job(filtros, qtd, consultores_ativos, dry_run=False) -> RunReport`
- Fluxo:
  1. Ler leads pendentes da planilha
  2. Aplicar filtros
  3. Normalizar telefones, separar válidos/inválidos
  4. Deduplicar por telefone normalizado (manter primeiro por `row_id`)
  5. Truncar pela quantidade (`qtd`)
  6. Distribuir round-robin
  7. Se `dry_run=True`: retornar `RunReport` sem executar nada
  8. Para cada par (lead, consultor):
     - `sync_contact` → `contact_id`
     - `create_deal` → `deal_id`
     - `marcar_importado` na planilha
     - Logar sucesso ou falha
     - `time.sleep(RATE_LIMIT_SLEEP)`
  9. Salvar falhas em `data/logs/failures/run_{run_id}.jsonl`
  10. Retornar `RunReport`
- `retry_falhas(run_id: str) -> RunReport` — lê JSONL de failures e re-executa

---

## 7. Formato dos logs (JSONL)

Cada linha é um objeto JSON independente.

**Sucesso:**
```json
{"ts":"2026-05-28T14:32:09Z","run_id":"2026-05-28_14-32-07","lead_row":1247,"empresa":"Academia X","consultor":"Ana","action":"contact_synced","contact_id":88421,"ok":true}
{"ts":"2026-05-28T14:32:09Z","run_id":"2026-05-28_14-32-07","lead_row":1247,"action":"deal_created","deal_id":55102,"ok":true}
```

**Falha:**
```json
{"ts":"2026-05-28T14:32:11Z","run_id":"2026-05-28_14-32-07","lead_row":1248,"empresa":"Academia Y","consultor":"Bruno","action":"contact_synced","ok":false,"error":"422 Unprocessable Entity","attempt":3}
```

---

## 8. Anti-duplicidade (3 camadas)

| Camada | Onde | Mecanismo |
|---|---|---|
| 1 | `sheets.py` | Filtrar `data_importacao IS NULL` |
| 2 | `importer.py` | Dedup por telefone normalizado antes de enviar |
| 3 | ActiveCampaign | `contact/sync` é idempotente por email/telefone |

---

## 9. Interface Streamlit (`app.py`)

### Layout — página única, sem rotas

```
┌─ Distribuidor de Leads ───────────────────────────────────────┐
│                                                               │
│  📊 Status: X leads na base | Y não importados               │
│                                                               │
│  ─── Filtros ─────────────────────────────────────────────   │
│  Estados:     multiselect (valores da planilha)               │
│  Cidades:     multiselect (valores da planilha)               │
│  Regiões:     multiselect (valores da planilha)               │
│  Categorias:  multiselect (valores da planilha)               │
│  Origens:     multiselect (valores da planilha)               │
│  Modalidades: multiselect (valores da planilha)               │
│                                                               │
│  Quantidade total: number_input (default 100, min 1)          │
│                                                               │
│  ─── Consultores ─────────────────────────────────────────   │
│  checkboxes: um por consultor ativo no consultores.yaml       │
│                                                               │
│  [🔍 Gerar Preview]                                           │
│                                                               │
│  ─── Preview (após clique) ───────────────────────────────   │
│  Elegíveis: X | Selecionados: Y | Inválidos: Z               │
│  Distribuição: Ana → N | Bruno → N | ...                      │
│  Tabela: empresa | telefone formatado | consultor | válido?   │
│                                                               │
│  [ ] Modo simulação (dry-run — não executa, não escreve)      │
│                                                               │
│  [🚀 Executar Importação]   (só aparece após preview)         │
│                                                               │
│  ─── Resultado da última execução ────────────────────────   │
│  ✅ X importados  ⚠️ Y falhas                                 │
│  [📋 Ver logs completos]  [🔁 Retry falhas]                   │
└───────────────────────────────────────────────────────────────┘
```

### Regras de UX
- Filtros são populados dinamicamente com valores reais da planilha (via `get_valores_unicos`)
- "Executar Importação" só aparece após "Gerar Preview" ser executado
- Durante execução: barra de progresso `st.progress` com contador de leads processados
- Resultado mostra sumário e permite ver log completo em expander
- Botão "Retry falhas" só aparece se houver arquivo de failures do último run
- Mensagens de erro do AC são exibidas em `st.error` inline, não travam a execução

---

## 10. `data/consultores.yaml` — formato

```yaml
consultores:
  - nome: Ana Silva
    ac_user_id: 1001
    ativo: true
  - nome: Bruno Costa
    ac_user_id: 1002
    ativo: true
  - nome: Carla Mendes
    ac_user_id: 1003
    ativo: true
  - nome: Diego Rocha
    ac_user_id: 1004
    ativo: false
```

---

## 11. `.env.example`

```
ACTIVECAMPAIGN_URL=https://suaconta.api-us1.com
ACTIVECAMPAIGN_API_KEY=sua_chave_aqui

SHEET_ID=id_da_planilha_google
SHEET_NAME=Leads

# IDs dos campos customizados no ActiveCampaign (descobrir via GET /api/3/fields)
AC_FIELD_CATEGORIA=10
AC_FIELD_ORIGEM=11
AC_FIELD_CIDADE=12
AC_FIELD_ESTADO=13

# IDs do pipeline e stage inicial no ActiveCampaign
AC_PIPELINE_ID=1
AC_STAGE_INICIAL_ID=1
```

---

## 12. Estratégia de distribuição (round-robin)

```
leads_ordenados = sorted(leads, key=lambda l: l.row_id)
pares = [(lead, consultores[i % len(consultores)]) for i, lead in enumerate(leads_ordenados)]
```

Determinístico: mesma entrada → mesma saída. Auditável.

---

## 13. Como rodar (README)

```bash
# Setup (uma vez)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # preencher com suas chaves
# colocar credentials.json na raiz (service account com acesso à planilha)

# Rodar
streamlit run app.py
# Abre http://localhost:8501
```
