# Transaction Ledger API

A REST API for creating accounts, recording credits and debits, checking
balances and transaction history, and transferring money between accounts.


## Tech stack

- Python and FastAPI
- Pydantic request validation
- SQLAlchemy ORM
- SQLite (`ledger.db`)
- Alembic migrations

## Run locally

From the project directory, in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive Swagger docs are
available at `http://127.0.0.1:8000/docs`.

For endpoint details, request/response examples, and error formats, see
[API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

## Run tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```
