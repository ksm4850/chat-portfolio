from dependency_injector import containers, providers

from src.infrastructure.rate_limit import RateLimiter
from src.infrastructure.security import TokenService
from src.modules.visitor.service import VisitorService


class VisitorContainer(containers.DeclarativeContainer):
    token_service = providers.Dependency(instance_of=TokenService)
    rate_limiter = providers.Dependency(instance_of=RateLimiter)
    tokens_per_ip_per_hour = providers.Dependency(instance_of=int)

    service = providers.Factory(
        VisitorService,
        token_service=token_service,
        rate_limiter=rate_limiter,
        tokens_per_ip_per_hour=tokens_per_ip_per_hour,
    )
