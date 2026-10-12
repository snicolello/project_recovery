"""Packet utilities: token bound, canonical form, receipt revalidation.

Tokenizer: ``approx-utf8-bytes-div-2.9``. Token count is the ceiling of the packet's
compact UTF-8 JSON length divided by 2.9. No tokenizer library is used. Packets are dense
with hex digests and paths, which tokenize poorly; measured against cl100k_base and
o200k_base (SKILL.md, "Token estimate check") the worst packet ran 2.998 bytes per token,
so the earlier divisor 3 under-counted by 0.1% and was widened to 2.9 (estimate at least
1.034 times the real count on every measured packet). Treat the figure as a conservative
estimate, not an exact count for any one model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Iterator

from receipts import SourceError, cited_text, read_source, validate_receipt

TOKENIZER = "approx-utf8-bytes-div-2.9"
DEFAULT_LIMIT = 4000
VOLATILE_KEYS = frozenset({"observed_at", "refreshed_at", "assembled_at", "verified_at"})
# Droppable lists, in the order they are trimmed (last element first).
# conflicts, unknowns, the mandatory fields and accepted_decisions are never dropped.
DROPPABLE = ("query_hits", "other_decisions", "decision_candidates")


def compact(packet: dict) -> bytes:
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def estimate_tokens(packet: dict) -> int:
    return -(-len(compact(packet)) * 10 // 29)  # ceil(bytes / 2.9) in integers


def _droppable_list(packet: dict, name: str) -> list:
    if name in ("other_decisions", "decision_candidates"):
        node = packet.get("fields", {}).get(name)
        return node["decisions"] if isinstance(node, dict) and isinstance(node.get("decisions"), list) else []
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


AUTHORITY_STATES = frozenset({"verified", "unverified", "local_only", "superseded"})


def frontmatter_status(data: bytes) -> str | None:
    """The ``status`` value in a note's frontmatter, read from source bytes."""
    lines = data.decode("utf-8", errors="replace").split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        return None
    for raw in lines[1:]:
        line = raw.rstrip("\r")
        if line == "---":
            return None
        key, sep, value = line.partition(":")
        if sep and key.strip() == "status":
            return value.strip()
    return None


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
          scope_root: str | None = None, recheck=None) -> tuple[dict, list[dict]]:
    """Revalidate a packet. Returns (corrected copy, problems).

    Checks: every cited item (receipt bytes, text, scope root, generation); every
    ``established`` node has at least one validating item (or established child decision);
    every ``authority_state`` is one of the four contract states, and ``verified`` appears
    only on an entry of ``fields.accepted_decisions``; every accepted decision carries a
    verified result with revision and ``verified_at`` and passes ``recheck(entry) ->
    (ok, reason[, conflict kind])`` (re-verification through a verifier, including the content
    binding: a changed note is ``approved_text_mismatch``). Without ``recheck`` an accepted
    decision cannot be confirmed and is demoted. A decision's ``local_status`` must equal
    the frontmatter status in its source bytes. ``conflicts`` and ``unknowns`` must exist.
    Each failure removes the claim (a demoted decision moves to ``decision_candidates`` as
    ``unverified``), sets the field ``unknown`` where it empties, and records a conflict.
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

    fields = out.get("fields") if isinstance(out.get("fields"), dict) else {}
    acc = fields.get("accepted_decisions") if isinstance(fields.get("accepted_decisions"), dict) else None
    accepted = acc.get("decisions") if acc is not None and isinstance(acc.get("decisions"), list) else []
    for i, entry in reversed(list(enumerate(accepted))):
        path = f"fields.accepted_decisions.decisions[{i}]"
        kind = "authority_not_verified"
        v = entry.get("verification") if isinstance(entry, dict) else None
        if not isinstance(entry, dict):
            ok, why = False, "entry is not an object"
        elif entry.get("authority_state") != "verified" or not isinstance(v, dict) or v.get("result") != "verified":
            ok, why = False, "accepted decision without a verified acceptance result"
        elif not v.get("revision") or not v.get("verified_at") or not v.get("reference"):
            ok, why = False, "verified result lacks reference, revision or verified_at"
        elif recheck is None:
            ok, why = False, "verified authority not re-checked: no verifier given (offline)"
        else:
            result = recheck(entry)  # (ok, reason) or (ok, reason, conflict kind)
            ok, why = result[0], result[1]
            kind = result[2] if len(result) > 2 else kind
        if ok:
            continue
        conflict(path, kind, why)
        accepted.pop(i)
        if isinstance(entry, dict):
            entry["authority_state"] = "unverified"
            entry["verification"] = {**(v if isinstance(v, dict) else {}), "result": "invalid",
                                     "reason": f"demoted by validate: {why}"}
            cands = fields.setdefault("decision_candidates", {"status": "candidate", "decisions": []})
            cands.setdefault("decisions", []).append(entry)
    accepted_ids = {id(e) for e in accepted}

    nodes = all_dicts(out)
    for path, node in nodes:
        if "authority_state" not in node:
            continue
        if node["authority_state"] not in AUTHORITY_STATES:
            conflict(path, "authority_state_not_permitted",
                     f"authority_state {node['authority_state']!r} is not a contract state")
            node["authority_state"] = "unverified"
        elif node["authority_state"] == "verified" and id(node) not in accepted_ids:
            conflict(path, "authority_state_not_permitted",
                     "verified is permitted only on an accepted decision with a verified acceptance record")
            node["authority_state"] = "unverified"
    for path, node in nodes:
        source, status = node.get("source"), node.get("local_status")
        if not isinstance(source, str) or status in (None, "stated_in_baseline") or "authority_state" not in node:
            continue
        try:
            actual = frontmatter_status(read_source(root, source)) if prefix is not None and source.startswith(prefix) else None
        except SourceError:
            actual = None
        if actual != status:
            conflict(path, "local_status_mismatch", f"local_status {status!r} differs from the source's {actual!r}")
            node["local_status"] = "unknown"
            node["items"] = []
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
                           scope_root: str | None = None, recheck=None) -> list[dict]:
    """Every claim in the packet that does not validate (see ``audit``)."""
    return audit(packet, root, expected_generation, scope_root, recheck)[1]


def revalidate(packet: dict, root: Path, expected_generation: str | None = None,
               scope_root: str | None = None, recheck=None) -> dict:
    """Corrected copy: failing claims removed, their fields ``unknown``, conflicts recorded."""
    return audit(packet, root, expected_generation, scope_root, recheck)[0]
