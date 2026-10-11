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


R1_AUTHORITY_STATES = frozenset({"local_only"})


def all_dicts(value, path: str = "") -> list[tuple[str, dict]]:
    """Every dict in the packet in pre-order (receipts excluded), with its path."""
    out: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        out.append((path, value))
        for key, child in value.items():
            if key in ("receipt", "budget"):
                continue
            out.extend(all_dicts(child, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            out.extend(all_dicts(child, f"{path}[{i}]"))
    return out


def scope_prefix(packet: dict) -> str | None:
    root = (packet.get("scope") or {}).get("root") if isinstance(packet.get("scope"), dict) else None
    if not isinstance(root, str) or not root:
        return None
    return "" if root == "." else root.rstrip("/") + "/"


def check_item(item: dict, root: Path, prefix: str | None = "", generations: frozenset = frozenset()) -> tuple[bool, str]:
    """A cited item validates when its receipt source sits under the packet's scope root, its
    generation matches the packet's (and the recorded one, when given), its content_sha matches
    the source bytes, and its text equals those bytes."""
    if not isinstance(item, dict):
        return False, "item is not an object"
    receipt = item.get("receipt")
    if not isinstance(receipt, dict):
        return False, "no receipt"
    if prefix is None:
        return False, "packet has no scope.root"
    source = receipt.get("source")
    if not isinstance(source, str) or not source.startswith(prefix):
        return False, f"source outside scope root {prefix!r}"
    if generations and receipt.get("generation") not in generations:
        return False, "receipt generation differs from the recorded generation"
    ok, why = validate_receipt(receipt, root)
    if not ok:
        return False, why
    if cited_text(root, receipt) != item.get("text"):
        return False, "text differs from cited bytes"
    return True, "ok"


def audit(packet: dict, root: Path, expected_generation: str | None = None,
          scope_root: str | None = None) -> tuple[dict, list[dict]]:
    """Revalidate a packet. Returns (corrected copy, problems).

    Checks: every cited item (receipt bytes, text, scope root, generation); every
    ``established`` node has at least one validating item (or established child decision);
    every ``authority_state`` is ``local_only`` (R1); ``conflicts`` and ``unknowns`` exist.
    Each failure removes the claim, sets the field ``unknown`` and records a conflict.
    """
    out = copy.deepcopy(packet) if isinstance(packet, dict) else {}
    problems: list[dict] = []

    def conflict(field: str, kind: str, reason: str, receipt: dict | None = None) -> None:
        entry = {"field": field, "kind": kind, "reason": reason}
        if receipt is not None:
            entry.update({"source": receipt.get("source"), "span": receipt.get("span"),
                          "claimed_sha": receipt.get("content_sha")})
        out["conflicts"].append(entry)
        problems.append(entry)

    for key in ("conflicts", "unknowns"):
        if not isinstance(out.get(key), list):
            out[key] = []
            if isinstance(packet, dict) and key in packet:
                conflict(key, "structural", f"{key} is not a list")
    prefix = scope_prefix(out)
    if prefix is None:
        conflict("scope", "structural", "packet has no scope.root")
    if scope_root is not None:
        declared = "" if scope_root == "." else scope_root.rstrip("/") + "/"
        if prefix is not None and prefix != declared:
            conflict("scope.root", "scope_mismatch", f"packet scope {prefix!r} differs from the manifest's {declared!r}")
        prefix = declared
    packet_gen = (out.get("freshness") or {}).get("generation") if isinstance(out.get("freshness"), dict) else None
    if expected_generation and packet_gen != expected_generation:
        conflict("freshness.generation", "generation_mismatch",
                 f"packet generation {packet_gen!r} differs from the recorded {expected_generation!r}")
    generations = frozenset(g for g in (expected_generation or packet_gen,) if g)

    for path, node in iter_nodes(out):
        for key in ("items", "evidence"):
            if key not in node:
                continue
            if not isinstance(node[key], list):
                node[key] = []
                conflict(path, "structural", f"{key} is not a list")
                continue
            kept = []
            for item in node[key]:
                ok, why = check_item(item, root, prefix, generations)
                if ok:
                    kept.append(item)
                else:
                    conflict(path, "receipt_validation_failed", why,
                             item.get("receipt") if isinstance(item, dict) and isinstance(item.get("receipt"), dict) else {})
            node[key] = kept

    nodes = all_dicts(out)
    for path, node in nodes:
        if "authority_state" in node and node["authority_state"] not in R1_AUTHORITY_STATES:
            conflict(path, "authority_state_not_permitted",
                     f"authority_state {node['authority_state']!r} is not permitted in R1 (only local_only)")
            node["authority_state"] = "local_only"
    for path, node in reversed(nodes):  # children before parents
        if node.get("status") != "established":
            continue
        has_items = bool(node.get("items"))
        decisions = node.get("decisions") if isinstance(node.get("decisions"), list) else []
        has_child = any(isinstance(d, dict) and d.get("status") == "established" for d in decisions)
        if has_items or has_child:
            continue
        node["status"] = "unknown"
        node["reason"] = "no validating evidence"
        out["unknowns"].append({"field": path, "reason": "no validating evidence"})
        conflict(path, "established_without_valid_items", "field claimed established without a validating receipt")
    return out, problems


def unsupported_assertions(packet: dict, root: Path, expected_generation: str | None = None,
                           scope_root: str | None = None) -> list[dict]:
    """Every claim in the packet that does not validate (see ``audit``)."""
    return audit(packet, root, expected_generation, scope_root)[1]


def revalidate(packet: dict, root: Path, expected_generation: str | None = None,
               scope_root: str | None = None) -> dict:
    """Corrected copy: failing claims removed, their fields ``unknown``, conflicts recorded."""
    return audit(packet, root, expected_generation, scope_root)[0]
