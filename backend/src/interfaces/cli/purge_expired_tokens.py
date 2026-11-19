"""만료된 refresh 토큰 정리. cron, k8s CronJob 등으로 주기 실행한다.

uv run python -m src.interfaces.cli.purge_expired_tokens
"""

import asyncio
import sys

from src.interfaces.cli.runtime import app_container


async def purge_expired_tokens() -> int:
    async with app_container() as container:
        return await container.auth.service().purge_expired_tokens()


def main() -> int:
    deleted = asyncio.run(purge_expired_tokens())
    print(f"삭제한 토큰: {deleted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
