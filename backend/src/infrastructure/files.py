import asyncio
import os
import tempfile
from pathlib import Path


class InvalidFileNameError(ValueError):
    pass


class TextFileDirectory:
    """한 디렉터리 바로 아래의 UTF-8 텍스트 파일만 읽고 쓴다. 하위·상위 경로는 거부한다."""

    def __init__(self, root: Path) -> None:
        self._root = root

    async def read(self, name: str) -> str:
        path = self._path(name)
        return await asyncio.to_thread(path.read_text, encoding="utf-8")

    async def read_many(self, pattern: str) -> dict[str, str]:
        return await asyncio.to_thread(self._read_many, pattern)

    async def write(self, name: str, text: str) -> None:
        await asyncio.to_thread(self._write, self._path(name), text)

    def _path(self, name: str) -> Path:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise InvalidFileNameError(name)
        return self._root / name

    def _read_many(self, pattern: str) -> dict[str, str]:
        return {path.name: path.read_text(encoding="utf-8") for path in self._root.glob(pattern)}

    @staticmethod
    def _write(path: Path, text: str) -> None:
        # 쓰는 도중 실패해도 원본이 반쯤 잘린 채 남지 않게 임시 파일을 바꿔 끼운다.
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(text)
            os.replace(temp, path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise


class MediaDirectory:
    """한 디렉터리 아래(하위 폴더 포함)의 미디어 파일을 찾는다.

    루트 밖을 가리키는 경로, 숨김 파일, 허용하지 않은 확장자는 없는 파일로 본다.
    """

    def __init__(self, root: Path, extensions: frozenset[str]) -> None:
        self._root = root
        self._extensions = extensions

    async def find(self, name: str) -> Path | None:
        return await asyncio.to_thread(self._find, name)

    def _find(self, name: str) -> Path | None:
        root = self._root.resolve()
        path = (root / name).resolve()
        if (
            not path.is_relative_to(root)
            or path.name.startswith(".")
            or path.suffix.lower() not in self._extensions
            or not path.is_file()
        ):
            return None
        return path
