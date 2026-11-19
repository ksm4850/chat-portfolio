from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import BaseRepository
from src.modules.portfolio.models import PortfolioCatalog, PortfolioSection

CATALOG_ID = 1


class CatalogRepository(BaseRepository[PortfolioCatalog]):
    model = PortfolioCatalog


class SectionRepository(BaseRepository[PortfolioSection]):
    model = PortfolioSection

    async def delete_all(self, session: AsyncSession) -> None:
        await session.execute(delete(PortfolioSection))

    async def list_ordered(
        self, session: AsyncSession, project_id: str | None = None
    ) -> Sequence[PortfolioSection]:
        statement = select(PortfolioSection).order_by(
            PortfolioSection.project_id, PortfolioSection.tab, PortfolioSection.position
        )
        if project_id is not None:
            statement = statement.where(PortfolioSection.project_id == project_id)
        return (await session.execute(statement)).scalars().all()
