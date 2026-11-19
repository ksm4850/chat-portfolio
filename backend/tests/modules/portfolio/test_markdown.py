from src.modules.portfolio.markdown import (
    best_quote,
    contains_quote,
    plain_text,
    split_sections,
)
from tests.modules.portfolio.support import CONTENT

DOC = """# 개요

H1 아래 본문

## 배경
배경 본문

## 빈 섹션
### 하위
```bash
# 주석이지 heading 이 아니다
```
"""


def test_sections_follow_heading_order_and_anchor_rule() -> None:
    sections = split_sections(DOC, "cq", "overview")

    assert [(s.anchor, s.level, s.title) for s in sections] == [
        ("cq-overview-1", 1, "개요"),
        ("cq-overview-2", 2, "배경"),
        ("cq-overview-3", 2, "빈 섹션"),
        ("cq-overview-4", 3, "하위"),
    ]
    assert sections[0].body == "H1 아래 본문"
    # 본문이 빈 섹션도 번호를 차지한다.
    assert sections[2].body == ""
    assert "# 주석이지" in sections[3].body


def test_h1_without_body_is_not_a_section() -> None:
    sections = split_sections("# 제목\n\n## 첫 섹션\n본문", "p", "t")

    assert [s.anchor for s in sections] == ["p-t-1"]
    assert sections[0].title == "첫 섹션"


def test_plain_text_removes_markdown_but_keeps_inner_underscore() -> None:
    markdown = (
        "- **문제** - `with_decryption` 을 _켰다_\n> [링크 글자](https://x.y) ![그림](a.png)\n1. 끝"
    )

    assert plain_text(markdown) == "문제 - with_decryption 을 켰다 링크 글자 끝"


def test_contains_quote_compares_normalized_text() -> None:
    section = plain_text("- **결정** - 방향을 뒤집어\n  런타임 통신을 처리")

    assert contains_quote(section, "방향을 뒤집어 런타임 통신을")
    assert contains_quote(section, "**결정** - 방향을")
    assert not contains_quote(section, "없는 문장")
    assert not contains_quote(section, "  ")


def test_best_quote_picks_line_with_most_overlap() -> None:
    body = "- 첫 줄은 상관없는 이야기입니다\n- 워커는 아웃바운드로만 NATS 에 연결합니다\n- 짧음"

    assert (
        best_quote("워커는 어떻게 NATS 에 붙나요?", body)
        == "워커는 아웃바운드로만 NATS 에 연결합니다"
    )
    assert best_quote("질문", "짧음") is None


def test_contract_example_quotes_exist_in_real_content() -> None:
    """프론트 시연 답변에 쓴 quote 가 실제 수집 결과에서도 검증을 통과한다."""
    files = {"ecs-migration.md": ("ecs", "overview"), "cq-decisions.md": ("cq", "decisions")}
    sections = {
        s.anchor: plain_text(s.body)
        for name, (project, tab) in files.items()
        for s in split_sections((CONTENT / name).read_text(encoding="utf-8"), project, tab)
    }

    assert contains_quote(sections["ecs-overview-2"], "서버마다 각자 운영하던 Nginx를 없애고")
    assert contains_quote(
        sections["cq-decisions-2"], "방향을 뒤집어 런타임 통신을 전부 NATS 위에서 처리"
    )
