import re
import uuid
from datetime import date, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

from .config import get_settings

settings = get_settings()


def fy_of(d: date) -> str:
    """Indian financial year label, e.g. 2026-27 (April to March)."""
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def iso(d: date | datetime | None) -> str | None:
    return d.isoformat() if d else None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        raise HTTPException(422, f"Invalid date: {value}")


def safe_name(name: str | None, default: str = "file") -> str:
    name = Path(name or default).name
    name = re.sub(r"[^\w.\- ()]+", "_", name).strip(" .") or default
    return name[:200]


def save_upload(file: UploadFile, allowed: set[str] | None = None) -> tuple[str, str, bytes]:
    """Validate + persist an upload. Returns (stored_filename, original_name, bytes)."""
    original = safe_name(file.filename)
    ext = Path(original).suffix.lower()
    if allowed is not None and ext not in allowed:
        raise HTTPException(415, f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}")
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
    if not data:
        raise HTTPException(400, "The file is empty")
    if ext == ".pdf" and not data.lstrip().startswith(b"%PDF"):
        raise HTTPException(415, "That file is not a valid PDF")
    stored = f"{uuid.uuid4().hex}{ext}"
    (settings.upload_dir / stored).write_bytes(data)
    return stored, original, data


def remove_file(stored: str | None) -> None:
    if stored:
        try:
            (settings.upload_dir / Path(stored).name).unlink(missing_ok=True)
        except OSError:
            pass


def file_response(stored: str | None, download_name: str) -> FileResponse:
    path = settings.upload_dir / Path(stored or "").name
    if not stored or not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=download_name)
