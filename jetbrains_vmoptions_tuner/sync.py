"""Read, edit and synchronize ``.vmoptions`` files."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .localization import DEFAULT_LANGUAGE, translate


@dataclass(slots=True)
class TextFile:
    text: str
    encoding: str = "utf-8"
    newline: str = "\r\n"
    bom: bool = False


@dataclass(slots=True)
class SyncItemResult:
    ide_id: str
    path: str
    changed: bool = False
    added_lines: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(slots=True)
class SyncReport:
    items: list[SyncItemResult]

    @property
    def changed(self) -> bool:
        return any(item.changed for item in self.items)

    @property
    def changed_count(self) -> int:
        return sum(item.changed for item in self.items)

    @property
    def errors(self) -> list[SyncItemResult]:
        return [item for item in self.items if item.error]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_option_line(line: str) -> str:
    return line.strip()


def validate_option_lines(
    text_or_lines: str | Iterable[str], language: str = DEFAULT_LANGUAGE
) -> tuple[list[str], list[str]]:
    source = text_or_lines.splitlines() if isinstance(text_or_lines, str) else text_or_lines
    lines: list[str] = []
    errors: list[str] = []
    seen: set[str] = set()
    for number, raw in enumerate(source, start=1):
        line = normalize_option_line(str(raw))
        if not line:
            continue
        if not line.startswith("-"):
            errors.append(translate("line_invalid", language, number=number, line=line))
            continue
        if line not in seen:
            lines.append(line)
            seen.add(line)
    if not lines and not errors:
        errors.append(translate("options_required", language))
    return lines, errors


def read_text_file(path: str | Path) -> TextFile:
    file_path = Path(path)
    data = file_path.read_bytes()
    bom = data.startswith(b"\xef\xbb\xbf")
    payload = data[3:] if bom else data
    try:
        text = payload.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        # vmoptions are normally ASCII/UTF-8, but Windows installations made by
        # older tools can contain ANSI comments.  cp1252 is lossless for bytes.
        text = payload.decode("cp1252")
        encoding = "cp1252"
    newline = "\r\n" if "\r\n" in text else "\n"
    return TextFile(text=text, encoding=encoding, newline=newline, bom=bom)


def _encode_text(content: TextFile) -> bytes:
    data = content.text.encode(content.encoding)
    return (b"\xef\xbb\xbf" + data) if content.bom and content.encoding == "utf-8" else data


def write_text_file(path: str | Path, content: TextFile) -> None:
    file_path = Path(path)
    mode: int | None = None
    try:
        mode = stat.S_IMODE(file_path.stat().st_mode)
    except OSError:
        pass
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{file_path.name}.", suffix=".tmp", dir=file_path.parent
    )
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(_encode_text(content))
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary_name, mode)
        os.replace(temporary_name, file_path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def missing_lines(file_text: str, desired_lines: Iterable[str]) -> list[str]:
    present = {normalize_option_line(line) for line in file_text.splitlines()}
    return [line for line in desired_lines if normalize_option_line(line) not in present]


def append_missing(content: TextFile, desired_lines: Iterable[str]) -> tuple[TextFile, list[str]]:
    missing = missing_lines(content.text, desired_lines)
    if not missing:
        return content, []
    separator = content.newline
    text = content.text
    if text and not text.endswith(("\n", "\r")):
        text += separator
    text += separator.join(missing) + separator
    return TextFile(text, content.encoding, content.newline, content.bom), missing


def group_for_ide(config: dict[str, Any], ide_id: str) -> dict[str, Any] | None:
    for group in config.get("groups", []):
        if ide_id in group.get("ide_ids", []):
            return group
    return None


def synchronize_ide(config: dict[str, Any], ide: dict[str, Any]) -> SyncItemResult:
    ide_id = str(ide.get("id", ""))
    path = str(ide.get("path", ""))
    result = SyncItemResult(ide_id=ide_id, path=path)
    group = group_for_ide(config, ide_id)
    if not group:
        return result
    language = config.get("settings", {}).get("language", DEFAULT_LANGUAGE)
    lines, errors = validate_option_lines(group.get("lines", []), language)
    if errors:
        result.error = "; ".join(errors)
        return result
    try:
        content = read_text_file(path)
        updated, added = append_missing(content, lines)
        if added:
            write_text_file(path, updated)
            result.changed = True
            result.added_lines = added
    except (OSError, UnicodeError) as error:
        result.error = str(error)
    return result


def synchronize_all(config: dict[str, Any]) -> SyncReport:
    return SyncReport([synchronize_ide(config, ide) for ide in config.get("ides", [])])


def save_edited_text(path: str | Path, text: str, original: TextFile | None = None) -> None:
    base = original or read_text_file(path)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\n", base.newline)
    write_text_file(
        path,
        TextFile(normalized, base.encoding, base.newline, base.bom),
    )
