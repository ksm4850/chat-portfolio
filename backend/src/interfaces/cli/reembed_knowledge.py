"""모든 기억 청크를 현재 임베딩 공급자로 다시 임베딩한다.

OPENAI_EMBEDDING_MODEL 을 바꾼 뒤 한 번 실행한다. 바꾸기 전 벡터와는 서로 비교할 수 없다.

uv run python -m src.interfaces.cli.reembed_knowledge
"""

import asyncio
import sys

from src.interfaces.cli.runtime import app_container


async def reembed_knowledge() -> int:
    async with app_container() as container:
        return await container.knowledge.service().reembed_all()


def main() -> int:
    count = asyncio.run(reembed_knowledge())
    print(f"다시 임베딩한 청크: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
