# Distribuidor de Leads → ActiveCampaign

Ferramenta operacional local que lê leads de uma planilha Google Sheets, distribui entre consultores em round-robin e importa contatos + deals no ActiveCampaign.

## Pré-requisitos

- Python 3.11+
- Acesso à planilha Google Sheets (service account)
- Conta ActiveCampaign com API key

## Setup (uma vez)

```bash
# 1. Criar e ativar ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Mac/Linux

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com as chaves reais

# 4. Colocar credentials.json na raiz do projeto
#    (service account Google com acesso de edição à planilha)
```

## Configuração do `.env`

| Variável | Descrição |
|---|---|
| `ACTIVECAMPAIGN_URL` | URL da conta AC (ex: `https://suaconta.api-us1.com`) |
| `ACTIVECAMPAIGN_API_KEY` | Chave de API do ActiveCampaign |
| `SHEET_ID` | ID da planilha Google Sheets |
| `SHEET_NAME` | Nome da aba (ex: `Leads`) |
| `AC_FIELD_CATEGORIA` | ID do campo customizado Categoria no AC |
| `AC_FIELD_MODALIDADE` | ID do campo customizado Modalidade no AC |
| `AC_FIELD_ESTADO` | ID do campo customizado Estado no AC |
| `AC_PIPELINE_ID` | ID do funil no AC |
| `AC_STAGE_INICIAL_ID` | ID do stage inicial no AC |

Para descobrir os IDs do AC, rode uma única vez:
```bash
python discovery_ac.py
```

## Consultores

Edite `data/consultores.yaml` com os consultores ativos. O campo `ac_user_id` é o ID do usuário no ActiveCampaign (visível via `python discovery_ac.py`).

```yaml
consultores:
  - nome: Ana Silva
    ac_user_id: 42
    ativo: true
```

## Rodar

```bash
streamlit run app.py
# Abre http://localhost:8501
```

## Fluxo de uso

1. Ajuste os **filtros** (Estado, Cidade, Categoria, Origem, Modalidade)
2. Defina a **quantidade** de leads a importar
3. Selecione os **consultores** que receberão os leads
4. Clique em **Gerar Preview** — veja a distribuição antes de executar
5. Opcional: marque **Modo simulação** para testar sem importar
6. Clique em **Executar Importação**
7. Se houver falhas, use o botão **Retry falhas**

## Estrutura dos logs

Cada execução gera dois arquivos em `data/logs/`:

- `runs/run_YYYY-MM-DD_HH-MM-SS.jsonl` — log completo (sucessos e falhas)
- `failures/run_YYYY-MM-DD_HH-MM-SS.jsonl` — somente falhas (para retry)

## Testes

```bash
pytest tests/
```
