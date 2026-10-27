from decimal import Decimal

import pytest


def create_account(client, name):
    response = client.post("/api/v1/accounts", json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_transaction(client, account_id, transaction_type, amount, reference_id):
    return client.post(
        f"/api/v1/accounts/{account_id}/transactions",
        json={
            "type": transaction_type,
            "amount": amount,
            "description": "Test transaction",
            "reference_id": reference_id,
        },
    )


def read_balance(client, account_id):
    response = client.get(f"/api/v1/accounts/{account_id}/balance")
    assert response.status_code == 200
    return Decimal(response.json()["balance"])


def test_credit_and_debit_update_balance_atomically(client):
    account_id = create_account(client, "Ada")

    credit = create_transaction(client, account_id, "credit", "100.25", "credit-1")
    debit = create_transaction(client, account_id, "debit", "30.10", "debit-1")

    assert credit.status_code == 201
    assert credit.json()["amount"] == "100.25"
    assert debit.status_code == 201
    assert read_balance(client, account_id) == Decimal("70.15")


def test_insufficient_debit_does_not_change_balance(client):
    account_id = create_account(client, "Ada")
    create_transaction(client, account_id, "credit", "100.00", "credit-1")

    response = create_transaction(client, account_id, "debit", "100.01", "debit-1")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"
    assert "sufficient balance" in response.json()["error"]["message"]
    assert read_balance(client, account_id) == Decimal("100.00")


def test_duplicate_reference_does_not_create_or_change_balance(client):
    account_id = create_account(client, "Ada")
    first = create_transaction(client, account_id, "credit", "25.00", "same-ref")

    duplicate = create_transaction(client, account_id, "credit", "999.00", "same-ref")
    history = client.get(f"/api/v1/accounts/{account_id}/transactions")

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "duplicate_transaction"
    assert read_balance(client, account_id) == Decimal("25.00")
    assert history.json()["pagination"]["total_records"] == 1


def test_reference_id_is_unique_per_account_not_globally(client):
    account_a = create_account(client, "Ada")
    account_b = create_account(client, "Grace")

    assert create_transaction(client, account_a, "credit", "1.00", "shared").status_code == 201
    assert create_transaction(client, account_b, "credit", "2.00", "shared").status_code == 201


def test_history_filter_and_pagination(client):
    account_id = create_account(client, "Ada")
    create_transaction(client, account_id, "credit", "10.00", "c-1")
    create_transaction(client, account_id, "debit", "2.00", "d-1")
    create_transaction(client, account_id, "credit", "5.00", "c-2")

    first_page = client.get(
        f"/api/v1/accounts/{account_id}/transactions",
        params={"type": "credit", "page": 1, "limit": 1},
    )
    second_page = client.get(
        f"/api/v1/accounts/{account_id}/transactions",
        params={"type": "credit", "page": 2, "limit": 1},
    )

    assert first_page.status_code == 200
    assert first_page.json()["pagination"] == {
        "current_page": 1,
        "page_size": 1,
        "total_records": 2,
        "total_pages": 2,
    }
    assert first_page.json()["items"][0]["reference_id"] == "c-2"
    assert second_page.json()["items"][0]["reference_id"] == "c-1"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (
            {"type": "wire", "amount": "1.00", "description": "bad", "reference_id": "x"},
            "body.type",
        ),
        (
            {"type": "credit", "amount": "0", "description": "bad", "reference_id": "x"},
            "body.amount",
        ),
    ],
)
def test_invalid_transaction_data_has_consistent_validation_error(client, payload, field):
    account_id = create_account(client, "Ada")

    response = client.post(f"/api/v1/accounts/{account_id}/transactions", json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert any(item["field"] == field for item in error["details"])


def test_account_not_found_returns_clear_error(client):
    response = client.get("/api/v1/accounts/00000000-0000-0000-0000-000000000001/balance")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "account_not_found"


def test_transfer_moves_funds_and_is_recorded_on_both_accounts(client):
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")
    create_transaction(client, source, "credit", "100.00", "fund-source")

    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source,
            "destination_account_id": destination,
            "amount": "35.25",
            "description": "Payment",
            "reference_id": "transfer-1",
        },
    )

    assert response.status_code == 201
    assert response.json()["debit"]["type"] == "debit"
    assert response.json()["credit"]["type"] == "credit"
    assert response.json()["debit"]["reference_id"] == response.json()["credit"]["reference_id"]
    assert read_balance(client, source) == Decimal("64.75")
    assert read_balance(client, destination) == Decimal("35.25")


def test_failed_transfer_rolls_back_both_balances_and_transactions(client):
    source = create_account(client, "Source")
    destination = create_account(client, "Destination")

    response = client.post(
        "/api/v1/transfers",
        json={
            "source_account_id": source,
            "destination_account_id": destination,
            "amount": "1.00",
            "description": "Payment",
            "reference_id": "transfer-1",
        },
    )
    source_history = client.get(f"/api/v1/accounts/{source}/transactions")
    destination_history = client.get(f"/api/v1/accounts/{destination}/transactions")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_balance"
    assert read_balance(client, source) == Decimal("0.00")
    assert read_balance(client, destination) == Decimal("0.00")
    assert source_history.json()["pagination"]["total_records"] == 0
    assert destination_history.json()["pagination"]["total_records"] == 0


def test_history_rejects_invalid_pagination(client):
    account_id = create_account(client, "Ada")

    response = client.get(
        f"/api/v1/accounts/{account_id}/transactions",
        params={"page": 0},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
