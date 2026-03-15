def test_register_and_login_customer(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"name": "Alice", "email": "alice@example.com", "password": "pass12345", "role": "customer"},
    )
    assert response.status_code == 201

    login = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "pass12345"})
    assert login.status_code == 200
    payload = login.get_json()
    assert payload["user"]["role"] == "customer"
    assert payload["access_token"]
    assert payload["refresh_token"]
