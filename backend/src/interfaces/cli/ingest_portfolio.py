"""포트폴리오 원본(projects.json + md)을 수집해 화면용 섹션과 캐릭터 기억 청크로 저장한다.

다시 실행하면 포트폴리오 문서만 지우고 다시 넣는다. 관리자 화면에서 넣은 기억은 그대로 둔다.

uv run python -m src.interfaces.cli.ingest_portfolio [--dir ../content/portfolio]
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from src.core.exceptions import AppError
from src.interfaces.cli.runtime import app_container
from src.modules.portfolio.schema import IngestResult, PortfolioSource, SourceCatalog


def load_source(directory: Path) -> PortfolioSource:
    catalog = SourceCatalog.model_validate(
        json.loads((directory / "projects.json").read_text(encoding="utf-8"))
    )
    files = {path.name: path.read_text(encoding="utf-8") for path in directory.glob("*.md")}
    return PortfolioSource(catalog=catalog, files=files)


async def ingest_portfolio(directory: Path) -> IngestResult:
    source = load_source(directory)
    async with app_container() as container:
        return await container.portfolio.service().ingest(source)


def main() -> int:
    parser = argparse.ArgumentParser(description="포트폴리오 콘텐츠를 수집한다.")
    parser.add_argument("--dir", type=Path, default=Path("../content/portfolio"))
    args = parser.parse_args()

    try:
        result = asyncio.run(ingest_portfolio(args.dir))
    except (OSError, ValidationError) as exc:
        print(f"원본을 읽지 못했다: {exc}", file=sys.stderr)
        return 1
    except AppError as exc:
        print(exc.message, file=sys.stderr)
        return 1

    print(
        f"프로젝트 {result.projects}, 문서 {result.documents}, "
        f"섹션 {result.sections}, 청크 {result.chunks}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
