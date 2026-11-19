from datetime import UTC, datetime


def from_epoch_millis(value: int) -> datetime:
    """UTC 밀리초 시각을 timezone 정보를 가진 datetime으로 바꾼다."""
    return datetime.fromtimestamp(value / 1000, tz=UTC)


def to_epoch_millis(value: datetime) -> int:
    return int(value.timestamp() * 1000)
