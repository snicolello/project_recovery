"""Packet utilities: token bound, canonical form, receipt revalidation.

Tokenizer: ``approx-utf8-bytes-div-3``. Token count is the ceiling of the packet's
compact UTF-8 JSON length divided by 3. No tokenizer library is used; dividing by 3
rather than the common 4 characters per token over-counts on purpose because packets
are dense with hex digests and paths, which tokenize poorly. Treat the figure as a
conservative estimate, not an exact count for any one model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Iterator

from receipts import cited_text, validate_receipt

TOKENIZER = "approx-utf8-bytes-div-3"
DEFAULT_LIMIT = 4000
VOLATILE_KEYS = frozenset({"observed_at", "refreshed_at", "assembled_at"})
# Droppable lists, in the order they are trimmed (last element first).
# conflicts, unknowns and the mandatory fields are never dropped.
DROPPABLE = ("query_hits", "other_decisions")


def compact(packet: dict) -> bytes:
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def estimate_tokens(packet: dict) -> int:
    return math.ceil(len(compact(packet)) / 3)


def _droppable_list(packet: dict, name: str) -> list:
    if name == "other_decisions":
        return packet["fields"]["other_decisions"]["decisions"]
    return packet[name]


def bound(packet: dict, limit: int = DEFAULT_LIMIT) -> dict:
    """Trim droppable lists until the packet fits, recording what was omitted."""
    omitted = {name: 0 for name in DROPPABLE}
    packet["budget"] = {"limit": limit, "tokenizer": TOKENIZER, "tokens": 0,
                        "truncated": False, "omitted": omitted, "within_limit": True}
    for name in DROPPABLE:
        items = _droppable_list(packet, name)
        while items and estimate_tokens(packet) > limit:
            items.pop()
            omitted[name] += 1
            packet["budget"]["truncated"] = True
    tokens = estimate_tokens(packet)
    # The count itself changes the packet length by a few bytes; settle it.
    for _ in range(3):
        packet["budget"]["tokens"] = tokens
        tokens = estimate_tokens(packet)
    packet["budget"]["tokens"] = tokens
    packet["budget"]["within_limit"] = tokens <= limit
    return packet


def strip_volatile(value):
    if isinstance(value, dict):
        return {k: strip_volatile(v) for k, v in value.items() if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [strip_volatile(v) for v in value]
    return value


def canonical(packet: dict) -> bytes:
    """Packet content without wall-clock fields, keys sorted, compact."""
    return json.dumps(strip_volatile(packet), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(packet: dict) -> str:
    return hashlib.sha256(canonical(packet)).hexdigest()


def iter_nodes(value, path: str = "") -> Iterator[tuple[str, dict]]:
    """Yield (path, node) for every node that carries cited ``items`` or ``evidence``."""
    if isinstance(value, dict):
        if "items" in value or "evidence" in value:
            yield path, value
        for key, child in value.items():
            if key in ("items", "evidence", "budget", "freshness"):
                continue
            yield from iter_nodes(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from iter_nodes(child, f"{path}[{i}]")


def ordered_receipts(packet: dict) -> list[dict]:
    out = []
    for _, node in iter_nodes(packet):
        for key in ("items", "evidence"):
            for item in node.get(key, []):
                out.append(strip_volatile(item["receipt"]))
    return out


def check_item(item: dict, root: Path) -> tuple[bool, str]:
    receipt = item.get("receipt")
    if not isinstance(receipt, dict):
        return False, "no receipt"
    ok, why = validate_receipt(receipt, root)
    if not ok:
        return False, why
    if cited_text(root, receipt) != item.get("text"):
        return False, "text differs from cited bytes"
    return True, "ok"


def unsupported_assertions(packet: dict, root: Path) -> list[dict]:
    """Every cited item whose receipt does not validate against the bytes under root."""
    problems = []
    for path, node in iter_nodes(packet):
        for key in ("items", "evidence"):
            for item in node.get(key, []):
                ok, why = check_item(item, root)
                if not ok:
                    problems.append({"field": path, "source": (item.get("receipt") or {}).get("source"), "reason": why})
    return problems


def revalidate(packet: dict, root: Path) -> dict:
    """Return a copy in which every failing receipt is removed, its field set to
    ``unknown`` when nothing valid remains, and a conflict recorded."""
    out = copy.deepcopy(packet)
    for path, node in iter_nodes(out):
        for key in ("items", "evidence"):
            kept = []
            for item in node.get(key, []):
                ok, why = check_item(item, root)
                if ok:
                    kept.append(item)
                    continue
                receipt = item.get("receipt") or {}
                out["conflicts"].append({
                    "field": path, "kind": "receipt_validation_failed", "source": receipt.get("source"),
                    "span": receipt.get("span"), "claimed_sha": receipt.get("content_sha"), "reason": why,
                })
            if key in node:
                node[key] = kept
        if node.get("status") == "established" and not node.get("items"):
            node["status"] = "unknown"
            node["reason"] = "receipt failed validation"
            out["unknowns"].append({"field": path, "reason": "receipt failed validation"})
    return out
