import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
INTERFACES = SRC / "interfaces"
MODULES = SRC / "modules"
WEB_PACKAGES = {"fastapi", "starlette"}
DB_PACKAGES = {"sqlalchemy", "asyncpg"}


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_web_framework_stays_out_of_business_layer() -> None:
    """FastAPI는 라우터와 interfaces 에서만 쓴다. 서비스 아래로 내려가지 않는다."""
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if path.name != "router.py"
        and not path.is_relative_to(INTERFACES)
        and _imported_roots(path) & WEB_PACKAGES
    ]

    assert offenders == []


def test_agui_protocol_stays_in_router() -> None:
    """AG-UI 이벤트·인코딩은 HTTP 표현이다. 서비스는 SDK 와 무관한 결과만 돌려준다."""
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if path.name != "router.py" and "ag_ui" in _imported_roots(path)
    ]

    assert offenders == []


def test_router_does_not_touch_repository_or_orm() -> None:
    """라우터는 서비스만 호출하고 repository·ORM을 직접 쓰지 않는다."""
    offenders = []
    for path in SRC.rglob("router.py"):
        source = path.read_text(encoding="utf-8")
        if _imported_roots(path) & DB_PACKAGES or any(
            marker in source for marker in ("repository import", "models import")
        ):
            offenders.append(str(path.relative_to(SRC)))

    assert offenders == []


def test_repository_never_commits() -> None:
    """트랜잭션 경계는 서비스가 갖는다. repository 는 commit·rollback 하지 않는다."""
    offenders = []
    for path in [*MODULES.rglob("repository.py"), SRC / "infrastructure/database/repository.py"]:
        source = path.read_text(encoding="utf-8")
        if ".commit()" in source or ".rollback()" in source:
            offenders.append(str(path.relative_to(SRC)))

    assert offenders == []


def test_business_layer_does_not_import_interfaces() -> None:
    """service·repository·models 는 interfaces 계층을 모른다."""
    offenders = []
    for path in MODULES.rglob("*.py"):
        if path.name == "router.py":
            continue
        if "src.interfaces" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(SRC)))

    assert offenders == []


def test_modules_do_not_import_each_others_repository_or_models() -> None:
    """모듈 간에는 service 를 통해서만 연결한다."""
    offenders = []
    for path in MODULES.rglob("*.py"):
        module_name = path.relative_to(MODULES).parts[0]
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("from src.modules."):
                continue
            other = line.removeprefix("from src.modules.").split(".")[0]
            if other != module_name and (" repository " in line or " models " in line):
                offenders.append(f"{path.relative_to(SRC)}: {line.strip()}")

    assert offenders == []


def test_infrastructure_has_no_domain_knowledge() -> None:
    """infrastructure 는 기술 어댑터만 둔다. 도메인 모듈을 import 하지 않는다."""
    offenders = [
        str(path.relative_to(SRC))
        for path in (SRC / "infrastructure").rglob("*.py")
        if "src.modules" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
