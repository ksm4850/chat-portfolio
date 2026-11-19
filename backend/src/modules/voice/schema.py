from src.shared.schema import CamelModel


class TranscriptSegment(CamelModel):
    text: str
    # False 면 인식 도중의 중간 결과라 다음 결과로 바뀔 수 있다.
    is_final: bool
