"""비밀번호 해시 어댑터.

`pwdlib` + Argon2 를 사용한다. 비밀번호 원문은 로그나 오류 메시지에 남기지 않는다.
"""

import secrets

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


class PasswordHasher:
    """비밀번호 해시와 검증만 담당한다."""

    def __init__(self) -> None:
        # 실제 해시와 같은 파라미터로 만들어야 검증 비용이 같아진다.
        self._dummy_hash = _password_hash.hash(secrets.token_urlsafe(16))

    def hash(self, plain_password: str) -> str:
        return _password_hash.hash(plain_password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """일치 여부를 돌려준다. 해시 형식이 깨져 있어도 예외를 올리지 않는다."""
        try:
            return _password_hash.verify(plain_password, hashed_password)
        except Exception:
            return False

    def verify_dummy(self, plain_password: str) -> bool:
        """비교할 해시가 없을 때 같은 비용을 써서 응답 시간 차이를 없앤다. 항상 False."""
        self.verify(plain_password, self._dummy_hash)
        return False
