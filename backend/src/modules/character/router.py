import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.core.container import AppContainer
from src.modules.character.schema import (
    CharacterCreate,
    CharacterPublic,
    CharacterRead,
    CharacterUpdate,
)
from src.modules.character.service import CharacterService

router = APIRouter(tags=["characters"])

# 인증은 조립 지점(api/v1)의 admin 라우터가 건다.
admin_router = APIRouter(tags=["admin: characters"])


@router.get("/{slug}")
@inject
async def read_public_character(
    slug: str,
    service: CharacterService = Depends(Provide[AppContainer.character.service]),
) -> CharacterPublic:
    """방문자용. 공개된 캐릭터의 이름·인사말."""
    return await service.get_public(slug)


@admin_router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_character(
    payload: CharacterCreate,
    service: CharacterService = Depends(Provide[AppContainer.character.service]),
) -> CharacterRead:
    return await service.create(payload)


@admin_router.get("")
@inject
async def list_characters(
    service: CharacterService = Depends(Provide[AppContainer.character.service]),
) -> list[CharacterRead]:
    return await service.list_all()


@admin_router.get("/{character_id}")
@inject
async def read_character(
    character_id: uuid.UUID,
    service: CharacterService = Depends(Provide[AppContainer.character.service]),
) -> CharacterRead:
    return await service.get(character_id)


@admin_router.patch("/{character_id}")
@inject
async def update_character(
    character_id: uuid.UUID,
    payload: CharacterUpdate,
    service: CharacterService = Depends(Provide[AppContainer.character.service]),
) -> CharacterRead:
    return await service.update(character_id, payload)


@admin_router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_character(
    character_id: uuid.UUID,
    service: CharacterService = Depends(Provide[AppContainer.character.service]),
) -> None:
    """캐릭터의 기억 문서도 함께 지운다."""
    await service.delete(character_id)
