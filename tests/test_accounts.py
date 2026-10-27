def test_create_account_starts_at_zero_and_generates_fields(client):
    response = client.post("/api/v1/accounts", json={"name": "  Ada Lovelace  "})

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Ada Lovelace"
    assert payload["balance"] == "0.00"
    assert payload["id"]
    assert payload["created_at"].endswith("Z")


def test_create_account_rejects_client_supplied_balance(client):
    response = client.post(
        "/api/v1/accounts",
        json={"name": "Ada Lovelace", "balance": 500},
    )

    assert response.status_code == 422


def test_create_account_rejects_blank_name(client):
    response = client.post("/api/v1/accounts", json={"name": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
