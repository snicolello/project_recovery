"""Evidence receipts (recovery contract section 3).

Cited bytes: lines ``start`` to ``end`` (1-indexed, inclusive) of the source file,
splitting on LF and joining with LF, with no trailing terminator. A CR before an
LF stays part of its line. This is the same convention QMD's ``get`` uses for a
line range, so the bytes QMD serves and the bytes on disk can be compared
directly.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath

RECEIPT_KEYS = ("source", "span", "content_sha", "generation", "revision", "observed_at")


class SourceError(ValueError):
    """A source locator is outside the allowlisted root, escapes it, or is missing."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def span_bytes(data: bytes, start: int, end: int) -> bytes:
    lines = data.split(b"\n")
    if not (1 <= start <= end <= len(lines)):
        raise SourceError(f"span {start}-{end} outside 1-{len(lines)}")
    return b"\n".join(lines[start - 1:end])


def safe_resolve(root: Path, source: str) -> Path:
    """Resolve a root-relative POSIX locator, rejecting traversal and link escape.

    Rejects absolute paths, drive letters, backslashes, empty or ``..`` parts, and any
    symlink or junction between the root and the file (the real path must equal the
    lexical path).
    """
    if not source or "\\" in source or ":" in source:
        raise SourceError(f"invalid locator: {source!r}")
    pure = PurePosixPath(source)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in source.split("/")):
        raise SourceError(f"traversal rejected: {source!r}")
    base = Path(os.path.realpath(root))
    lexical = base.joinpath(*pure.parts)
    real = Path(os.path.realpath(lexical))
    if os.path.normcase(str(real)) != os.path.normcase(str(lexical)):
        raise SourceError(f"link escape rejected: {source!r}")
    try:
        real.relative_to(base)
    except ValueError:
        raise SourceError(f"outside root: {source!r}") from None
    return real


def read_source(root: Path, source: str) -> bytes:
    path = safe_resolve(root, source)
    if not path.is_file():
        raise SourceError(f"missing source: {source!r}")
    return path.read_bytes()


def make_receipt(source: str, start: int, end: int, cited: bytes, generation: str, observed_at: str) -> dict:
    return {
        "source": source,
        "span": [start, end],
        "content_sha": sha256_hex(cited),
        "generation": generation,
        "revision": "unknown",
        "observed_at": observed_at,
    }


def validate_receipt(receipt: dict, root: Path, cited: bytes | None = None) -> tuple[bool, str]:
    """Check a receipt against the source bytes under root (and the cited bytes, if given)."""
    if any(k not in receipt for k in RECEIPT_KEYS):
        return False, "receipt missing required keys"
    try:
        start, end = receipt["span"]
        disk = span_bytes(read_source(root, receipt["source"]), int(start), int(end))
    except (SourceError, TypeError, ValueError) as exc:
        return False, str(exc)
    if sha256_hex(disk) != receipt["content_sha"]:
        return False, "content_sha does not match source bytes"
    if cited is not None and sha256_hex(cited) != receipt["content_sha"]:
        return False, "content_sha does not match cited bytes"
    return True, "ok"


def normalize_text(cited: bytes) -> str:
    """Display text for cited bytes: UTF-8, CRLF shown as LF, trailing CR dropped."""
    return cited.decode("utf-8").replace("\r\n", "\n").rstrip("\r")


def cited_text(root: Path, receipt: dict) -> str:
    start, end = receipt["span"]
    return normalize_text(span_bytes(read_source(root, receipt["source"]), int(start), int(end)))
