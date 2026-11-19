class UniqueViolationError(Exception):
    """unique 제약 위반. 서비스는 이를 자기 도메인 예외로 번역한다."""

    def __init__(self, constraint: str | None = None) -> None:
        super().__init__(constraint or "unique violation")
        self.constraint = constraint
