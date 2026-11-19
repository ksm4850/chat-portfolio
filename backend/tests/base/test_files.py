from pathlib import Path

import pytest

from src.infrastructure.files import InvalidFileNameError, MediaDirectory, TextFileDirectory


@pytest.mark.parametrize("name", ["", ".", "..", "../x.md", "sub/x.md", "/etc/passwd"])
async def test_rejects_paths_outside_directory(tmp_path: Path, name: str) -> None:
    files = TextFileDirectory(tmp_path)

    with pytest.raises(InvalidFileNameError):
        await files.write(name, "x")
    with pytest.raises(InvalidFileNameError):
        await files.read(name)


async def test_write_replaces_file_without_leftovers(tmp_path: Path) -> None:
    files = TextFileDirectory(tmp_path)
    (tmp_path / "a.md").write_text("old", encoding="utf-8")

    await files.write("a.md", "새 내용")

    assert await files.read("a.md") == "새 내용"
    assert await files.read_many("*.md") == {"a.md": "새 내용"}
    assert [p.name for p in tmp_path.iterdir()] == ["a.md"]


EXTENSIONS = frozenset({".png"})


@pytest.mark.parametrize(
    "name",
    ["../secret.png", "a/../../secret.png", "/etc/hosts", ".hidden.png", "a/b.txt", "a/x.png"],
)
async def test_media_hides_files_outside_or_not_allowed(tmp_path: Path, name: str) -> None:
    root = tmp_path / "medias"
    (root / "a").mkdir(parents=True)
    (root / "a" / "b.txt").write_text("x")
    (root / ".hidden.png").write_bytes(b"x")
    (tmp_path / "secret.png").write_bytes(b"x")

    assert await MediaDirectory(root, EXTENSIONS).find(name) is None


async def test_media_finds_file_in_subdirectory(tmp_path: Path) -> None:
    (tmp_path / "play").mkdir()
    (tmp_path / "play" / "Graph.PNG").write_bytes(b"x")

    assert (
        await MediaDirectory(tmp_path, EXTENSIONS).find("play/Graph.PNG")
        == (tmp_path / "play" / "Graph.PNG").resolve()
    )


async def test_media_rejects_symlink_out_of_root(tmp_path: Path) -> None:
    root = tmp_path / "medias"
    root.mkdir()
    (tmp_path / "secret.png").write_bytes(b"x")
    (root / "link.png").symlink_to(tmp_path / "secret.png")

    assert await MediaDirectory(root, EXTENSIONS).find("link.png") is None
