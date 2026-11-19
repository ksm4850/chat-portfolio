from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """요청·응답 JSON 은 camelCase, 내부 필드는 snake_case 로 쓴다."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
