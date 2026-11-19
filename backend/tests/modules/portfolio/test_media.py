import json
import re

import pytest
from dependency_injector import providers

from src.modules.portfolio.service import MEDIA_DIR
from tests.modules.portfolio.support import CONTENT, portfolio_service

MEDIA = "/api/v1/portfolio/medias"
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


@pytest.fixture
def client_with_content(container, client):
    container.portfolio.service.override(providers.Object(portfolio_service()))
    return client


def _references() -> list[str]:
    catalog = json.loads((CONTENT / "projects.json").read_text(encoding="utf-8"))
    paths = [path for project in catalog["projects"] for path in project.get("media", [])]
    for md in CONTENT.glob("*.md"):
        paths += MARKDOWN_IMAGE.findall(md.read_text(encoding="utf-8"))
    return paths


def test_every_media_reference_points_to_file_in_content() -> None:
    references = _references()

    assert references
    for path in references:
        assert path.startswith(f"{MEDIA_DIR}/"), path
        assert (CONTENT / path).is_file(), path


def test_serves_media_with_cache_headers(client_with_content) -> None:
    response = client_with_content.get(f"{MEDIA}/play/infra_ecs.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == (CONTENT / "medias/play/infra_ecs.png").read_bytes()


@pytest.mark.parametrize(
    "path", ["play/nope.png", "..%2Fprojects.json", "%2E%2E/cq-overview.md", "play/.DS_Store"]
)
def test_unknown_or_outside_media_is_404(client_with_content, path: str) -> None:
    response = client_with_content.get(f"{MEDIA}/{path}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "media_not_found"
