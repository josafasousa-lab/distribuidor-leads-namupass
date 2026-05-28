"""
Ferramenta de consulta one-shot — não faz parte do projeto.
Uso: python discovery_ac.py
Requer .env com ACTIVECAMPAIGN_URL e ACTIVECAMPAIGN_API_KEY.
"""

import os
import sys

try:
    from dotenv import load_dotenv
    import httpx
except ImportError:
    print("Instale as dependências: pip install python-dotenv httpx")
    sys.exit(1)

load_dotenv()

BASE_URL = os.environ.get("ACTIVECAMPAIGN_URL", "").rstrip("/")
API_KEY = os.environ.get("ACTIVECAMPAIGN_API_KEY", "")

if not BASE_URL or not API_KEY:
    print("Erro: ACTIVECAMPAIGN_URL e ACTIVECAMPAIGN_API_KEY precisam estar no .env")
    sys.exit(1)

HEADERS = {"Api-Token": API_KEY}


def get(path: str, params: dict = None) -> dict:
    url = f"{BASE_URL}/api/3{path}"
    r = httpx.get(url, headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def secao(titulo: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {titulo}")
    print('═' * 60)


# ── Usuários ────────────────────────────────────────────────────

secao("USUÁRIOS  (GET /api/3/users)")

data = get("/users")
usuarios = data.get("users", [])

if not usuarios:
    print("  (nenhum usuário encontrado)")
else:
    print(f"  {'ID':<8} {'Nome':<30} Email")
    print(f"  {'-'*7} {'-'*29} {'-'*30}")
    for u in usuarios:
        print(f"  {u['id']:<8} {u['firstName'] + ' ' + u['lastName']:<30} {u.get('email', '')}")

# ── Pipelines e stages ──────────────────────────────────────────

secao("PIPELINES E STAGES  (GET /api/3/dealGroups)")

data = get("/dealGroups")
pipelines = data.get("dealGroups", [])

if not pipelines:
    print("  (nenhum pipeline encontrado)")
else:
    for p in pipelines:
        print(f"\n  Pipeline  id={p['id']}  →  {p['title']}")

        stages_data = get("/dealStages", params={"filters[d_groupid]": p["id"]})
        stages = stages_data.get("dealStages", [])

        if not stages:
            print("    (sem stages)")
        else:
            for s in stages:
                print(f"    Stage  id={s['id']}  →  {s['title']}")

# ── Campos customizados ─────────────────────────────────────────

secao("CAMPOS CUSTOMIZADOS  (GET /api/3/fields)")

data = get("/fields", params={"limit": 100})
fields = data.get("fields", [])

if not fields:
    print("  (nenhum campo encontrado)")
else:
    print(f"  {'ID':<8} {'Tipo':<12} Título")
    print(f"  {'-'*7} {'-'*11} {'-'*35}")
    for f in fields:
        print(f"  {f['id']:<8} {f.get('type', ''):<12} {f['title']}")

print(f"\n{'═' * 60}\n")
