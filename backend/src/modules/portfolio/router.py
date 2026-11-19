from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from src.core.container import AppContainer
from src.modules.portfolio.schema import (
    IngestResult,
    Portfolio,
    ProjectDetail,
    SourceFileContent,
    SourceFileRead,
    SourceFileUpdate,
)
from src.modules.portfolio.service import PortfolioService

router = APIRouter(tags=["portfolio"])
admin_router = APIRouter(tags=["admin: portfolio"])


@router.get("")
@inject
async def read_portfolio(
    service: PortfolioService = Depends(Provide[AppContainer.portfolio.service]),
) -> Portfolio:
    """프로필·경력·프로젝트 목록·기술. 프로젝트의 탭 본문은 상세 API 로 받는다."""
    return await service.get_portfolio()


@router.get("/medias/{path:path}", response_class=FileResponse)
@inject
async def read_media(
    path: str,
    service: PortfolioService = Depends(Provide[AppContainer.portfolio.service]),
) -> FileResponse:
    """원본의 `medias/{path}` 이미지·동영상.

    md·projects.json 의 `medias/...` 경로를 이 주소로 바꿔 쓴다.
    """
    return FileResponse(
        await service.media_file(path),
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/projects/{project_id}")
@inject
async def read_project(
    project_id: str,
    service: PortfolioService = Depends(Provide[AppContainer.portfolio.service]),
) -> ProjectDetail:
    """탭별 섹션(markdown 원문).

    섹션 DOM 에 `data-anchor` 를 붙이면 화면 제어가 그 위치를 찾는다.
    """
    return await service.get_project(project_id)


@admin_router.get("/files")
@inject
async def list_source_files(
    service: PortfolioService = Depends(Provide[AppContainer.portfolio.service]),
) -> list[SourceFileRead]:
    """projects.json 에 등록된 탭별 원본 md."""
    return await service.list_source_files()


@admin_router.get("/files/{file}")
@inject
async def read_source_file(
    file: str,
    service: PortfolioService = Depends(Provide[AppContainer.portfolio.service]),
) -> SourceFileContent:
    return await service.read_source_file(file)


@admin_router.put("/files/{file}")
@inject
async def update_source_file(
    file: str,
    payload: SourceFileUpdate,
    service: PortfolioService = Depends(Provide[AppContainer.portfolio.service]),
) -> IngestResult:
    """원본 md 를 저장하고 포트폴리오 전체를 다시 수집한다(화면 섹션 + 기억 청크)."""
    return await service.update_source_file(file, payload.content)


@admin_router.post("/ingest")
@inject
async def reingest(
    service: PortfolioService = Depends(Provide[AppContainer.portfolio.service]),
) -> IngestResult:
    """원본 디렉터리를 다시 수집한다. `make ingest-portfolio` 와 같다."""
    return await service.reingest()
