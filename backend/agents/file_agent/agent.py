import hashlib
import shutil
from pathlib import Path

from backend.core.config import get_settings


class FileAgent:
    def __init__(self) -> None:
        self.settings = get_settings()

    def execute(self, action: str, params: dict) -> dict:
        return getattr(self, action)(**params)

    def _safe_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.settings.allowed_base_path / path
        resolved = path.resolve()
        allowed = self.settings.allowed_base_path.expanduser().resolve()
        if allowed not in resolved.parents and resolved != allowed:
            raise ValueError(f"Path outside allowed base path: {resolved}")
        return resolved

    def create_folder(self, path: str) -> dict:
        target = self._safe_path(path)
        target.mkdir(parents=True, exist_ok=True)
        return {"created": str(target)}

    def create_file(self, path: str, content: str = "") -> dict:
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"created": str(target), "bytes": target.stat().st_size}

    def delete_file(self, path: str) -> dict:
        target = self._safe_path(path)
        if not target.is_file():
            raise FileNotFoundError(str(target))
        target.unlink()
        return {"deleted": str(target)}

    def delete_folder(self, path: str) -> dict:
        target = self._safe_path(path)
        if not target.is_dir():
            raise FileNotFoundError(str(target))
        shutil.rmtree(target)
        return {"deleted": str(target)}

    def rename_file(self, path: str, new_name: str) -> dict:
        source = self._safe_path(path)
        target = source.with_name(new_name)
        source.rename(target)
        return {"renamed": str(source), "target": str(target)}

    def move_file(self, path: str, destination: str) -> dict:
        source = self._safe_path(path)
        dest = self._safe_path(destination)
        if dest.is_dir() or dest.suffix == "":
            dest = dest / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        return {"moved": str(source), "target": str(dest)}

    def search_files(self, query: str, source: str | None = None) -> dict:
        root = self._safe_path(source or Path.home())
        matches = [str(item) for item in root.rglob(f"*{query}*") if item.is_file()]
        return {"matches": matches[:200], "count": len(matches)}

    def move_by_extension(self, extension: str, destination: str, source: str | None = None) -> dict:
        src = self._safe_path(source or Path.home() / "Downloads")
        dest = self._safe_path(Path.home() / destination if destination == "Documents" else destination)
        dest.mkdir(parents=True, exist_ok=True)
        moved = []
        for item in src.glob(f"*{extension}"):
            if item.is_file():
                target = dest / item.name
                shutil.move(str(item), str(target))
                moved.append(str(target))
        return {"moved": moved, "count": len(moved)}

    def find_duplicates(self, source: str | None = None) -> dict:
        root = self._safe_path(source or Path.home() / "Downloads")
        hashes: dict[str, list[str]] = {}
        for file_path in root.rglob("*"):
            if file_path.is_file():
                digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
                hashes.setdefault(digest, []).append(str(file_path))
        duplicates = [paths for paths in hashes.values() if len(paths) > 1]
        return {"duplicates": duplicates, "groups": len(duplicates)}

    def backup_folder(self, command: str, source: str | None = None, destination: str | None = None) -> dict:
        src = self._safe_path(source or Path.cwd())
        backup_root = self._safe_path(destination or Path.home() / "NexaBackups")
        backup_root.mkdir(parents=True, exist_ok=True)
        target = backup_root / f"{src.name}-backup"
        if target == src or src in target.parents:
            raise ValueError("Backup destination must be outside the source tree")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target, ignore=shutil.ignore_patterns("node_modules", ".venv", "__pycache__", ".git"))
        return {"backup": str(target), "command": command}
