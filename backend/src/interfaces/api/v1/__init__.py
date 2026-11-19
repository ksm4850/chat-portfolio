"""v1 API 조립.

각 모듈이 자기 `router.py`에서 선언한 라우터를 여기서 하나로 모은다.
URL prefix 는 모듈이 아니라 이 조립 지점에서 정한다.
관리자 라우터(`admin_router`)는 `/admin` 아래에 모으고 superuser 인증을 한 곳에서 건다.
"""

from fastapi import APIRouter, Depends

from src.interfaces.dependencies import get_current_superuser
from src.modules.auth.router import router as auth_router
from src.modules.character.router import admin_router as character_admin_router
from src.modules.character.router import router as character_router
from src.modules.chat.router import admin_router as chat_admin_router
from src.modules.chat.router import router as chat_router
from src.modules.guide.router import admin_router as guide_admin_router
from src.modules.guide.router import router as guide_router
from src.modules.knowledge.router import admin_router as knowledge_admin_router
from src.modules.portfolio.router import admin_router as portfolio_admin_router
from src.modules.portfolio.router import router as portfolio_router
from src.modules.users.router import router as users_router
from src.modules.visitor.router import router as visitor_router
from src.modules.voice.router import router as voice_router

admin = APIRouter(prefix="/admin", dependencies=[Depends(get_current_superuser)])
admin.include_router(character_admin_router, prefix="/characters")
admin.include_router(knowledge_admin_router, prefix="/characters/{character_id}")
admin.include_router(chat_admin_router)
admin.include_router(portfolio_admin_router, prefix="/portfolio")
admin.include_router(guide_admin_router, prefix="/guide")

router = APIRouter(prefix="/v1")

router.include_router(auth_router, prefix="/auth")
router.include_router(users_router, prefix="/users")
router.include_router(visitor_router, prefix="/visitors")
router.include_router(character_router, prefix="/characters")
router.include_router(chat_router, prefix="/chat")
router.include_router(voice_router, prefix="/voice")
router.include_router(portfolio_router, prefix="/portfolio")
router.include_router(guide_router, prefix="/agui")
router.include_router(admin)
