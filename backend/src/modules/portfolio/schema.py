from pydantic import Field

from src.shared.schema import CamelModel


class Profile(CamelModel):
    name: str


class Career(CamelModel):
    company: str
    period: str
    description: str
    roles: list[str]
    project_ids: list[str]


class SkillGroup(CamelModel):
    category: str
    items: list[str]


class Tab(CamelModel):
    id: str
    label: str


class SourceTab(Tab):
    """projects.json 의 탭. `file` 은 수집할 때만 쓰고 응답에 내보내지 않는다."""

    file: str


class ProjectBase(CamelModel):
    id: str
    company: str
    title: str
    period: str
    summary: str
    stacks: list[str]
    url: str | None = None
    media: list[str] = Field(default_factory=list)


class SourceProject(ProjectBase):
    tabs: list[SourceTab]
    # 화면에 탭으로 보이지 않고 안내 챗봇만 쓰는 md. 첫 탭의 첫 섹션 위치를 빌린다.
    notes: list[str] = Field(default_factory=list)


class SourceCatalog(CamelModel):
    """content/portfolio/projects.json"""

    profile: Profile
    careers: list[Career]
    projects: list[SourceProject]
    skills: list[SkillGroup]


class PortfolioSource(CamelModel):
    """수집 입력. 파일은 CLI 가 읽어 넘긴다."""

    catalog: SourceCatalog
    # 파일명 → markdown
    files: dict[str, str]


class ProjectSummary(ProjectBase):
    tabs: list[Tab]


class Portfolio(CamelModel):
    profile: Profile
    careers: list[Career]
    projects: list[ProjectSummary]
    skills: list[SkillGroup]


class SectionRead(CamelModel):
    anchor: str
    level: int
    title: str
    body: str


class TabDetail(Tab):
    sections: list[SectionRead]


class ProjectDetail(ProjectBase):
    tabs: list[TabDetail]


class SourceFileRead(CamelModel):
    """원본 md 하나 = 프로젝트의 탭 하나. `source` 는 수집된 기억 문서의 source 와 같다."""

    file: str
    source: str
    project_id: str
    project_title: str
    tab_id: str
    tab_label: str


class SourceFileContent(SourceFileRead):
    content: str


class SourceFileUpdate(CamelModel):
    content: str = Field(min_length=1)


class IngestResult(CamelModel):
    projects: int
    documents: int
    sections: int
    chunks: int


class SectionLocation(CamelModel):
    """다른 모듈(guide)이 화면 위치를 검증할 때 쓰는 내부 값."""

    anchor: str
    project_id: str
    project_title: str
    tab: str
    tab_label: str
    title: str
    body: str
    plain: str
