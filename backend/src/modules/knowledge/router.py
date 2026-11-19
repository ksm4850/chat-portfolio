import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.core.container import AppContainer
from src.modules.knowledge.schema import (
    DocumentCreate,
    DocumentDetail,
    DocumentRead,
    DocumentUpdate,
    SearchHit,
    SearchRequest,
)
from src.modules.knowledge.service import KnowledgeService

# 기억 관리는 관리자 전용이다.
# 인증과 `/characters/{character_id}` prefix 는 조립 지점(api/v1)이 준다.
admin_router = APIRouter(tags=["admin: knowledge"])


@admin_router.post("/documents", status_code=status.HTTP_201_CREATED)
@inject
async def add_document(
    character_id: uuid.UUID,
    payload: DocumentCreate,
    service: KnowledgeService = Depends(Provide[AppContainer.knowledge.service]),
) -> DocumentRead:
    return await service.add_document(character_id, payload)


@admin_router.get("/documents")
@inject
async def list_documents(
    character_id: uuid.UUID,
    service: KnowledgeService = Depends(Provide[AppContainer.knowledge.service]),
) -> list[DocumentRead]:
    return await service.list_documents(character_id)


@admin_router.get("/documents/{document_id}")
@inject
async def read_document(
    character_id: uuid.UUID,
    document_id: uuid.UUID,
    service: KnowledgeService = Depends(Provide[AppContainer.knowledge.service]),
) -> DocumentDetail:
    """원문과 청크(meta 포함)."""
    return await service.get_document(character_id, document_id)


@admin_router.patch("/documents/{document_id}")
@inject
async def update_document(
    character_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    service: KnowledgeService = Depends(Provide[AppContainer.knowledge.service]),
) -> DocumentRead:
    """본문을 바꾸면 청크를 다시 나누고 임베딩한다. 포트폴리오 문서는 409."""
    return await service.update_document(character_id, document_id, payload)


@admin_router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_document(
    character_id: uuid.UUID,
    document_id: uuid.UUID,
    service: KnowledgeService = Depends(Provide[AppContainer.knowledge.service]),
) -> None:
    await service.delete_document(character_id, document_id)


@admin_router.post("/search")
@inject
async def search(
    character_id: uuid.UUID,
    payload: SearchRequest,
    service: KnowledgeService = Depends(Provide[AppContainer.knowledge.service]),
) -> list[SearchHit]:
    """검색 품질 확인용. 채팅은 같은 검색 결과를 프롬프트에 넣는다."""
    return await service.search(character_id, payload.query, limit=payload.limit)
