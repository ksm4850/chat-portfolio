from redis.asyncio import Redis


def create_redis(url: str) -> Redis:
    """연결은 첫 명령 때 맺는다. 문자열로 주고받도록 decode_responses 를 켠다."""
    return Redis.from_url(url, decode_responses=True)
