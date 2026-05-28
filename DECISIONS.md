# DECISIONS.md — Decisões Arquiteturais Fechadas

> Este arquivo contém decisões já tomadas e validadas pelo dono do produto.
> **Não revisite, não proponha alternativas, não adicione dependências fora desta lista.**
> Se uma situação parecer justificar uma exceção, sinalize e aguarde confirmação explícita.

---

## Stack (não alterar)

| Componente | Decisão | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | Ecossistema maduro pra Sheets + AC + telefone |
| UI | Streamlit | UI funcional pra não-técnico sem frontend separado |
| Google Sheets | gspread + google-auth | Planilha já existe, é a fonte da verdade |
| HTTP client | httpx (síncrono) | Simples, suficiente pra ~300-500 leads por run |
| Validação | pydantic v2 | Tipagem + validação sem boilerplate |
| Telefone | phonenumbers | Padrão BR, E.164, lida com todos os formatos sujos |
| Retry | tenacity | Backoff exponencial declarativo |
| Logs | loguru | JSONL em arquivo, sem configuração verbosa |
| Config | python-dotenv | .env simples |
| Consultores | YAML | Muda raramente, não precisa de banco |
| Testes | pytest | Padrão, sem overhead |

---

## Decisões de arquitetura

- **Google Sheets É o banco.** Não criar SQLite, Postgres, MongoDB ou qualquer outro banco de dados.
- **UI em página única.** Sem rotas, sem multi-página Streamlit, sem login, sem autenticação.
- **Execução local.** Sem Docker, sem docker-compose, sem CI/CD, sem deployment pipeline.
- **Retry síncrono.** Sem Celery, sem Redis, sem fila de tarefas, sem workers.
- **Logs em arquivo JSONL.** Sem Sentry, sem ELK, sem Datadog, sem logging remoto.
- **Rate limit com sleep.** `time.sleep(0.25)` entre chamadas AC. Sem async, sem semáforo, sem throttler externo.
- **ActiveCampaign via REST puro.** Sem SDK de terceiros para o AC. Apenas httpx direto na API.

---

## Decisões de integração ActiveCampaign

- **Usar `POST /api/3/contact/sync`** (não `POST /api/3/contacts`). O `sync` é idempotente — cria ou atualiza por email/telefone sem duplicar.
- **Não fazer busca prévia** (`GET /api/3/contacts?email=...`) antes de criar. O `sync` já resolve isso.
- **Email placeholder:** se o lead não tiver email, usar `{telefone_sem_mais}@placeholder.local`. Nunca enviar contato sem email pro AC.
- **Campos customizados:** IDs fixados em `.env` (descobertos via `GET /api/3/fields` uma única vez).
- **Retry apenas em erros transitórios:** `httpx.HTTPError`, `5xx`, `429`. Erros `4xx` (exceto 429) são problemas de dado — logar e pular, não retentar.

---

## Decisões de UX

- **Operador não-técnico** — zero terminal visível pra ele. Tudo via UI Streamlit.
- **Preview obrigatório antes de executar** — o botão "Executar" só aparece após "Gerar Preview".
- **Dry-run sempre disponível** — checkbox visível, padrão desmarcado.
- **Falhas não travam o job** — um lead que falha não para os outros. Loga e continua.
- **Retry manual via botão** — operador decide quando retentar, não é automático entre runs.

---

## O que explicitamente NÃO vai existir neste projeto

- ❌ Banco de dados próprio (SQLite, Postgres, etc)
- ❌ API REST / backend separado
- ❌ Frontend separado (React, Vue, etc)
- ❌ Docker / containerização
- ❌ Autenticação / login
- ❌ Multi-usuário / multi-tenant
- ❌ Agendamento automático (cron job, scheduler)
- ❌ Fila de tarefas (Celery, RQ, etc)
- ❌ Cache externo (Redis, Memcached)
- ❌ SDK do ActiveCampaign
- ❌ Testes de integração com AC (apenas unit tests com mock)
- ❌ Dashboard de métricas / analytics
- ❌ Notificações (email, Slack, etc)

> Se qualquer um desses itens parecer necessário durante a implementação,
> pare e sinalize. Não implemente por conta própria.
