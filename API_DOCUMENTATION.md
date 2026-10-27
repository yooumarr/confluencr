# Transaction Ledger API Documentation


## Endpoint list

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/v1/accounts` | Create an account |
| `POST` | `/api/v1/accounts/{account_id}/transactions` | Add a credit or debit |
| `GET` | `/api/v1/accounts/{account_id}/balance` | Get the current balance |
| `GET` | `/api/v1/accounts/{account_id}/transactions` | Get transaction history |
| `POST` | `/api/v1/transfers` | Transfer money between accounts |
| `GET` | `/health` | Check API availability |

## Brief setup

From the project directory, run these commands in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. 

Interactive Swagger docs are at
`http://127.0.0.1:8000/docs`. SQLite stores data in `ledger.db`.

## Create an account

`POST /api/v1/accounts`

JSON input:

```json
{
  "name": "Ada Lovelace"
}
```

Returns `201 Created`. The server generates the account ID, initial zero
balance, and creation timestamp. The client cannot provide an initial balance.

Example response:

```json
{
  "id": "00000000-0000-0000-0000-000000000001",
  "name": "Ada Lovelace",
  "balance": "0.00",
  "created_at": "2026-10-27T10:00:00Z"
}
```

## Add a credit or debit

`POST /api/v1/accounts/{account_id}/transactions`

Use `"type": "credit"` to add funds or `"type": "debit"` to spend funds.

JSON input:

```json
{
  "type": "credit",
  "amount": "125.50",
  "description": "Paycheck",
  "reference_id": "paycheck-001"
}
```

For a debit, change the type and use a distinct reference:

```json
{
  "type": "debit",
  "amount": "25.50",
  "description": "Purchase",
  "reference_id": "purchase-001"
}
```

Returns `201 Created` with the recorded transaction:

```json
{
  "id": "00000000-0000-0000-0000-000000000101",
  "account_id": "00000000-0000-0000-0000-000000000001",
  "type": "credit",
  "amount": "125.50",
  "description": "Paycheck",
  "reference_id": "paycheck-001",
  "created_at": "2026-10-27T10:01:00Z"
}
```

Amounts must be positive and have at most two decimal places. A reference ID
can only be used once per account. A duplicate reference or debit without
sufficient funds returns `409 Conflict`; neither request changes the balance.

## Get an account balance

`GET /api/v1/accounts/{account_id}/balance`

Example:
`GET /api/v1/accounts/00000000-0000-0000-0000-000000000001/balance`

Example response:

```json
{
  "account_id": "00000000-0000-0000-0000-000000000001",
  "balance": "125.50"
}
```

## Get transaction history

`GET /api/v1/accounts/{account_id}/transactions`

Optional query parameters:

- `type=credit` or `type=debit` filters by transaction type; omit to include both.
- `page` is the 1-based page number (default `1`).
- `limit` is the number of records per page (default `20`, maximum `100`).

Example:
`GET /api/v1/accounts/00000000-0000-0000-0000-000000000001/transactions?type=credit&page=1&limit=10`

Results are ordered latest-first. The response includes transaction items and
pagination details:

```json
{
  "items": [
    {
      "id": "00000000-0000-0000-0000-000000000101",
      "account_id": "00000000-0000-0000-0000-000000000001",
      "type": "credit",
      "amount": "125.50",
      "description": "Paycheck",
      "reference_id": "paycheck-001",
      "created_at": "2026-10-27T10:01:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "page_size": 10,
    "total_records": 1,
    "total_pages": 1
  }
}
```

## Transfer money

`POST /api/v1/transfers`

JSON input:

```json
{
  "source_account_id": "00000000-0000-0000-0000-000000000001",
  "destination_account_id": "00000000-0000-0000-0000-000000000002",
  "amount": "30.00",
  "description": "Repayment",
  "reference_id": "transfer-001"
}
```

Both accounts must exist and must be different. The source must have enough
funds. A successful transfer returns a debit and credit sharing a transfer ID:

```json
{
  "transfer_id": "00000000-0000-0000-0000-000000000201",
  "debit": {
    "id": "00000000-0000-0000-0000-000000000202",
    "account_id": "00000000-0000-0000-0000-000000000001",
    "type": "debit",
    "amount": "30.00",
    "description": "Repayment",
    "reference_id": "transfer-001",
    "created_at": "2026-10-27T10:02:00Z"
  },
  "credit": {
    "id": "00000000-0000-0000-0000-000000000203",
    "account_id": "00000000-0000-0000-0000-000000000002",
    "type": "credit",
    "amount": "30.00",
    "description": "Repayment",
    "reference_id": "transfer-001",
    "created_at": "2026-10-27T10:02:00Z"
  }
}
```

The debit, credit, and both balance updates happen atomically. If the transfer
fails, none of them are saved.

## Health check

`GET /health`

```json
{
  "status": "ok"
}
```

## Errors

Errors use a consistent JSON structure. Common status codes are:

- `404 Not Found` — account does not exist.
- `409 Conflict` — duplicate reference, insufficient funds, or balance limit.
- `422 Unprocessable Entity` — invalid input, type, or pagination values.

Example insufficient-funds response:

```json
{
  "error": {
    "code": "insufficient_balance",
    "message": "The account does not have sufficient balance for this debit."
  }
}
```

Validation errors also include a `details` array identifying invalid fields.

## Assumptions

- Account IDs are UUIDs.
- Monetary input has up to two decimal places and is stored internally as integer cents.
- A reference ID is unique within one account; another account may reuse it.
- The SQLite database URL is set in `app/config.py`; by default the database
  file is `ledger.db` in the project directory.
