"""관리자 계정 생성.

    uv run python -m src.interfaces.cli.create_superuser --email admin@example.com

비밀번호는 셸 기록에 남지 않도록 프롬프트로 받는다.
"""

import argparse
import asyncio
import getpass
import sys

from pydantic import ValidationError

from src.core.exceptions import AppError
from src.interfaces.cli.runtime import app_container
from src.modules.users.schema import UserCreate, UserRead


async def create_superuser(email: str, password: str, full_name: str | None = None) -> UserRead:
    payload = UserCreate(email=email, password=password, full_name=full_name)
    async with app_container() as container:
        return await container.users.service().create_user(payload, is_superuser=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="관리자 계정을 만든다.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name")
    args = parser.parse_args()

    password = getpass.getpass("비밀번호: ")
    if password != getpass.getpass("비밀번호 확인: "):
        print("비밀번호가 일치하지 않는다.", file=sys.stderr)
        return 1

    try:
        user = asyncio.run(create_superuser(args.email, password, args.full_name))
    except ValidationError as exc:
        fields = ", ".join(str(error["loc"][0]) for error in exc.errors())
        print(f"입력 값이 올바르지 않다: {fields}", file=sys.stderr)
        return 1
    except AppError as exc:
        print(exc.message, file=sys.stderr)
        return 1

    print(f"관리자 생성 완료: {user.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
