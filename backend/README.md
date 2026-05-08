# Backend Easy-eSocial-v2 / Explorador

Backend FastAPI dedicado ao Explorador de Arquivos. Conecta no Postgres local
no banco `easy_social_solucoes` (empresa SOLUCOES = `estado_1`).

> **Regras:** não toca em APPA, não toca no V1.

## Setup (Windows / PowerShell)

```powershell
cd C:\Users\xandao\Documents\GitHub\Easy-eSocial-v2\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env  # se ainda não existir
# preencha LOCAL_DB_PASSWORD em .env
```

## Migrations

```powershell
python -m app.migrate
```

Idempotente — pode rodar quantas vezes quiser.

## Rodar API

```powershell
$env:PYTHONIOENCODING='utf-8'
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Healthcheck: GET http://127.0.0.1:8001/health

## Estrutura

```
backend/
├── .env                     # NÃO COMMITAR
├── .env.example
├── requirements.txt
└── app/
    ├── __init__.py
    ├── main.py              # FastAPI app + rotas
    ├── config.py            # Settings (lê .env)
    ├── db.py                # Pool psycopg2
    └── migrate.py           # Aplica SQL de migrations/
└── migrations/
    └── 001_explorador_init.sql
```
