from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.core.container import AppContainer
from src.interfaces.dependencies import ClientIP
from src.modules.visitor.schema import VisitorToken
from src.modules.visitor.service import VisitorService

router = APIRouter(tags=["visitors"])


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def issue_visitor_token(
    client_ip: ClientIP,
    service: VisitorService = Depends(Provide[AppContainer.visitor.service]),
) -> VisitorToken:
    """첫 방문 때 한 번 받는다. 이미 토큰이 있으면 다시 받지 않고 그대로 쓴다."""
    return await service.issue(client_ip)
