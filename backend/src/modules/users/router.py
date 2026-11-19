import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, status

from src.core.container import AppContainer
from src.interfaces.dependencies import CurrentSuperUser, CurrentUser
from src.modules.users.schema import (
    PasswordUpdate,
    UserAdminUpdate,
    UserCreate,
    UserPage,
    UserRead,
    UserUpdate,
)
from src.modules.users.service import UserService

router = APIRouter(tags=["users"])


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_user(
    payload: UserCreate,
    service: UserService = Depends(Provide[AppContainer.users.service]),
) -> UserRead:
    """회원 가입."""
    return await service.create_user(payload)


@router.get("/me")
async def read_me(current_user: CurrentUser) -> UserRead:
    return current_user


@router.patch("/me")
@inject
async def update_me(
    payload: UserUpdate,
    current_user: CurrentUser,
    service: UserService = Depends(Provide[AppContainer.users.service]),
) -> UserRead:
    return await service.update_user(current_user.id, payload)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def change_my_password(
    payload: PasswordUpdate,
    current_user: CurrentUser,
    service: UserService = Depends(Provide[AppContainer.users.service]),
) -> None:
    await service.change_password(current_user.id, payload)


@router.get("")
@inject
async def list_users(
    _: CurrentSuperUser,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    service: UserService = Depends(Provide[AppContainer.users.service]),
) -> UserPage:
    return await service.list_users(offset=offset, limit=limit)


@router.get("/{user_id}")
@inject
async def read_user(
    user_id: uuid.UUID,
    _: CurrentSuperUser,
    service: UserService = Depends(Provide[AppContainer.users.service]),
) -> UserRead:
    return await service.get_user(user_id)


@router.patch("/{user_id}")
@inject
async def update_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    _: CurrentSuperUser,
    service: UserService = Depends(Provide[AppContainer.users.service]),
) -> UserRead:
    return await service.update_user(user_id, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_user(
    user_id: uuid.UUID,
    _: CurrentSuperUser,
    service: UserService = Depends(Provide[AppContainer.users.service]),
) -> None:
    await service.delete_user(user_id)
