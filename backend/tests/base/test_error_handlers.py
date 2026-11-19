from fastapi.testclient import TestClient


def test_unknown_route_uses_common_error_format(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_wrong_method_uses_common_error_format(client: TestClient) -> None:
    response = client.get("/api/v1/auth/login")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "allow" in response.headers


def test_validation_error_does_not_echo_input(client: TestClient) -> None:
    """검증 실패 응답에 비밀번호 같은 입력 원문이 되돌아가지 않는다."""
    response = client.post("/api/v1/users", json={"email": "a@example.com", "password": "secret1"})

    body = response.json()
    assert response.status_code == 422
    assert body["error"]["code"] == "validation_error"
    assert "secret1" not in response.text
    assert set(body["error"]["details"][0]) == {"loc", "msg", "type"}
