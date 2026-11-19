"""관리자 API 는 조립 지점에서 한 번에 막는다. 새 관리자 라우트가 빠지지 않았는지 확인한다."""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from src.interfaces.dependencies import get_current_user
from src.modules.users.schema import UserRead


def _admin_operations(app) -> list[tuple[str, str]]:
    paths = app.openapi()["paths"]
    operations = [
        (
            method,
            path.replace("{character_id}", str(uuid.uuid4())).replace(
                "{document_id}", str(uuid.uuid4())
            ),
        )
        for path, ops in paths.items()
        if path.startswith("/api/v1/admin")
        for method in ops
    ]
    assert operations, "관리자 라우트를 하나도 찾지 못했다"
    return operations


def test_admin_routes_reject_anonymous(app, client: TestClient) -> None:
    for method, path in _admin_operations(app):
        response = client.request(method, path, json={})
        assert response.status_code == 401, (method, path)


def test_admin_routes_reject_normal_user(app, client: TestClient) -> None:
    now = datetime.now(UTC)
    app.dependency_overrides[get_current_user] = lambda: UserRead(
        id=uuid.uuid4(),
        email="user@example.com",
        full_name=None,
        is_active=True,
        is_superuser=False,
        created_at=now,
        updated_at=now,
    )

    for method, path in _admin_operations(app):
        response = client.request(method, path, json={})
        assert response.status_code == 403, (method, path)
