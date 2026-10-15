"""Structural validation: the exact keys and value shapes an assembled packet may have.

project_recovery #6, required outcome 1 (fifth review F1). Every object in the packet is
checked against an explicit allowlist: an unexpected key, a missing required key or a
value of the wrong type is a failure, never kept. This is structure only. A packet that
passes ``check`` may still say anything a well-formed packet can say; whether its values
are what the vault and the acceptance records support is decided by re-derivation
(``rederive.py``), not here.

``parse`` reads packet text strictly: UTF-8 JSON, one object, no duplicate keys, no NaN,
no infinite number (``1e400`` included), no lone surrogate, no integer beyond Python's
conversion limit, at most ``MAX_PACKET_BYTES`` bytes and ``MAX_DEPTH`` levels of nesting.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re

MAX_PACKET_BYTES = 4_000_000
MAX_PROBLEMS = 100
# Largest integer any packet count, rank, limit or token figure may hold. Far above anything
# assembly produces, small enough that arithmetic on it never nears the integer-conversion
# limit (fourth-review follow-up: a 4,300-digit count plus one could not be printed).
MAX_INT = 10 ** 15
# Deepest nesting a packet may have. Assembled packets nest about a dozen levels; recursive
# checks and comparisons stay far from Python's recursion limit (re-check of f159446).
MAX_DEPTH = 64

TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z")
HEX64 = re.compile(r"[0-9a-f]{64}")


def _timestamp(v) -> bool:
    """A real UTC time, written as the assembler writes it, in ASCII digits (review R7)."""
    if not isinstance(v, str) or not TIMESTAMP.fullmatch(v):
        return False
    try:
        dt.datetime.strptime(v, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        return False
    return True


class Spec:
    def check(self, value, path: str, out: list) -> None:
        raise NotImplementedError


class _ProblemLimitReached(Exception):
    """Stop nested validation after one problem beyond the reporting limit is found."""


def problem(out: list, path: str, kind: str, reason: str) -> None:
    if len(out) >= MAX_PROBLEMS:
        raise _ProblemLimitReached
    out.append({"check": "structure", "field": path or "packet", "kind": kind, "reason": reason})


class Scalar(Spec):
    def __init__(self, name: str, test):
        self.name, self.test = name, test

    def check(self, value, path, out):
        if not self.test(value):
            problem(out, path, "wrong_type", f"expected {self.name}, got {type(value).__name__} {short(value)}")


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


STR = Scalar("a string", lambda v: isinstance(v, str))
BOOL = Scalar("a boolean", lambda v: isinstance(v, bool))
COUNT = Scalar("an integer from 0 to 10^15", lambda v: _int(v) and 0 <= v <= MAX_INT)
POSITIVE = Scalar("an integer from 1 to 10^15", lambda v: _int(v) and 1 <= v <= MAX_INT)
TS = Scalar("a UTC timestamp YYYY-MM-DDTHH:MM:SS.mmmZ", _timestamp)
SHA = Scalar("a lowercase SHA-256 hex digest", lambda v: isinstance(v, str) and HEX64.fullmatch(v))
SPAN = Scalar("[start, end] with 1 <= start <= end",
              lambda v: isinstance(v, list) and len(v) == 2 and all(_int(x) for x in v) and 1 <= v[0] <= v[1])
STR_OR_NULL = Scalar("a string or null", lambda v: v is None or isinstance(v, str))
SPAN_OR_NULL = Scalar("[start, end] or null", lambda v: v is None or SPAN.test(v))


def enum(*values) -> Scalar:
    return Scalar(f"one of {list(values)}", lambda v: isinstance(v, str) and v in values)


class Obj(Spec):
    def __init__(self, required: dict, optional: dict | None = None):
        self.required, self.optional = required, optional or {}

    def check(self, value, path, out):
        if not isinstance(value, dict):
            problem(out, path, "wrong_type", f"expected an object, got {type(value).__name__} {short(value)}")
            return
        for key in value:
            if key not in self.required and key not in self.optional:
                problem(out, join(path, key), "unexpected_key", f"key {key!r} is not allowed here")
        for key, spec in self.required.items():
            if key not in value:
                problem(out, join(path, key), "missing_key", f"required key {key!r} is missing")
            else:
                spec.check(value[key], join(path, key), out)
        for key, spec in self.optional.items():
            if key in value:
                spec.check(value[key], join(path, key), out)


class ListOf(Spec):
    def __init__(self, spec: Spec, unique=None):
        self.spec, self.unique = spec, unique

    def check(self, value, path, out):
        if not isinstance(value, list):
            problem(out, path, "wrong_type", f"expected a list, got {type(value).__name__} {short(value)}")
            return
        seen = set()
        for i, child in enumerate(value):
            self.spec.check(child, f"{path}[{i}]", out)
            if self.unique and isinstance(child, dict) and isinstance(child.get(self.unique), (str, int)):
                if child[self.unique] in seen:
                    problem(out, f"{path}[{i}]", "duplicate", f"{self.unique} {child[self.unique]!r} appears twice")
                seen.add(child[self.unique])


class MapOf(Spec):
    def __init__(self, spec: Spec):
        self.spec = spec

    def check(self, value, path, out):
        if not isinstance(value, dict):
            problem(out, path, "wrong_type", f"expected an object, got {type(value).__name__}")
            return
        for key, child in value.items():
            self.spec.check(child, join(path, key), out)


def join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def short(value) -> str:
    text = json.dumps(value, ensure_ascii=False)[:60] if not isinstance(value, (dict, list)) else ""
    return text


# The packet as recipe.assemble produces it -----------------------------------------

RECEIPT = Obj({"source": STR, "span": SPAN, "content_sha": SHA, "generation": STR, "revision": STR,
               "observed_at": TS})
ITEM = Obj({"text": STR, "receipt": RECEIPT})
ITEMS = ListOf(ITEM)
NODE_STATUS = enum("established", "unknown")
NODE = Obj({"status": NODE_STATUS, "items": ITEMS}, {"reason": STR})
APPROVAL = Obj({"status": NODE_STATUS, "items": ITEMS}, {"reason": STR, "evidence": ITEMS})
AUTHORITY_STATE = enum("verified", "unverified", "local_only", "superseded")
VERIFICATION = Obj(
    {"transport": STR, "result": enum("verified", "unavailable", "invalid", "not_referenced"), "reason": STR},
    {"reference": STR, "kind": enum("pull_merge", "pull_review", "issue_comment"), "revision": STR,
     "verified_at": TS, "actor": STR, "approved_digest": SHA, "note_digest": SHA, "mismatch": BOOL,
     "conflict": enum("approved_text_mismatch", "approval_text_not_approver_authored")})
DECISION = Obj({"title": STR_OR_NULL, "source": STR, "local_status": STR, "authority_state": AUTHORITY_STATE,
                "status": NODE_STATUS, "items": ITEMS},
               {"verification": VERIFICATION, "reason": STR})
OTHER_DECISION = Obj({"title": STR_OR_NULL, "source": STR, "local_status": STR,
                      "authority_state": enum("local_only"), "status": NODE_STATUS, "items": ITEMS},
                     {"reason": STR})
FIELDS = Obj({
    "objective": NODE,
    "authority": Obj({"status": NODE_STATUS, "items": ITEMS, "authority_state": AUTHORITY_STATE,
                      "verification": STR, "approver": NODE, "approvals": MapOf(APPROVAL)},
                     {"reason": STR, "evidence": ITEMS}),
    "accepted_decisions": Obj({"status": NODE_STATUS, "basis": STR, "decisions": ListOf(DECISION, "source")},
                              {"reason": STR}),
    "decision_candidates": Obj({"status": enum("candidate"), "basis": STR, "decisions": ListOf(DECISION)}),
    "other_decisions": Obj({"decisions": ListOf(OTHER_DECISION)}),
    "current_state": NODE,
    "blockers": NODE,
    "next_action": NODE,
})
CONFLICT = Obj({"field": STR, "kind": STR},
               {"source": STR_OR_NULL, "span": SPAN_OR_NULL, "claimed_sha": STR_OR_NULL, "reason": STR,
                "reference": STR_OR_NULL, "revision": STR_OR_NULL, "approved_digest": STR_OR_NULL,
                "current_digest": STR_OR_NULL, "sources": ListOf(STR)})
LAST_CHECKED = Obj({
    "status": enum("historical", "unavailable", "invalid"), "reason": STR, "replayed_at": TS,
    "bundle_sha256": STR, "statement": STR, "trust_root": STR,
    "entries": ListOf(Obj({
        "source": STR, "reference": STR, "revision": STR, "actor": STR, "last_checked_at": TS,
        "approved_digest": SHA, "policy_sha256": SHA,
        "applicability": enum("matches", "note_changed", "policy_changed", "reference_changed", "missing_source"),
        "acceptance_effect": enum("none"),
    }), "source"),
})
PACKET = Obj({
    "contract_version": STR,
    "recipe_version": STR,
    "project": STR,
    "scope": Obj({"collection": STR, "root": STR}),
    "query": STR,
    "status": enum("complete", "incomplete"),
    "assembled_at": TS,
    "freshness": Obj({"generation": STR, "refreshed_at": TS, "statement": STR,
                      "generation_gap": ListOf(Obj({"source": STR_OR_NULL, "change": STR},
                                                   {"detected": enum("during_assembly")}))}),
    "authority_verification": Obj({"transport": STR, "serial": BOOL, "requests": COUNT,
                                   "overlapping_requests": BOOL, "unavailable": COUNT,
                                   "results": MapOf(COUNT), "statement": STR}),
    "fields": FIELDS,
    "query_hits": ListOf(Obj({"rank": POSITIVE, "source": STR, "title": STR_OR_NULL, "status": NODE_STATUS,
                              "items": ITEMS}, {"reason": STR}), "source"),
    "missing_sources": ListOf(Obj({"link": STR, "linked_from": ListOf(STR), "result": STR})),
    "conflicts": ListOf(CONFLICT),
    "unknowns": ListOf(Obj({"field": STR, "reason": STR})),
    "budget": Obj({"limit": POSITIVE, "tokenizer": STR, "tokens": COUNT, "truncated": BOOL,
                   "omitted": Obj({"query_hits": COUNT, "other_decisions": COUNT, "decision_candidates": COUNT},
                                  {"last_checked": COUNT}),
                   "within_limit": BOOL}),
}, {"last_checked": LAST_CHECKED})


def check(packet) -> list[dict]:
    """Every structural problem in ``packet`` (capped at ``MAX_PROBLEMS``)."""
    out: list[dict] = []
    try:
        PACKET.check(packet, "", out)
    except _ProblemLimitReached:
        out.append({"check": "structure", "field": "packet", "kind": "truncated",
                    "reason": "more structural problems exist; the rest were not checked or listed"})
    return out


# Strict parsing --------------------------------------------------------------------

class ParseError(ValueError):
    pass


def _no_duplicates(pairs: list) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ParseError(f"duplicate key {key!r}")
        out[key] = value
    return out


def _no_constant(name: str):
    raise ParseError(f"non-finite number {name} is not JSON")


def depth(value) -> int:
    """Nesting depth of a parsed JSON value, computed without recursion."""
    deepest, stack = 0, [(value, 1)]
    while stack:
        node, level = stack.pop()
        if isinstance(node, (dict, list)):
            deepest = max(deepest, level)
            stack.extend((child, level + 1) for child in (node.values() if isinstance(node, dict) else node))
    return deepest


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ParseError(f"number {text[:20]} is not finite")
    return value


def parse(data: bytes) -> dict:
    """Packet text to an object, or ParseError. A leading UTF-8 byte-order mark is ignored."""
    if len(data) > MAX_PACKET_BYTES:
        raise ParseError(f"packet is {len(data)} bytes; the limit is {MAX_PACKET_BYTES}")
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError(f"packet is not UTF-8: {exc}") from None
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant,
                           parse_float=_finite_float)
    except RecursionError:
        raise ParseError("packet nesting is too deep") from None
    except json.JSONDecodeError as exc:
        raise ParseError(f"packet is not JSON: {exc}") from None
    except ParseError:
        raise
    except ValueError as exc:
        # Python's integer-conversion limit (an integer of more than 4,300 digits) is kept;
        # its error becomes the ordinary rejection (fourth review of efcc4e7, F4-2).
        raise ParseError(f"packet holds a value JSON parsing refuses: {str(exc)[:120]}") from None
    if not isinstance(value, dict):
        raise ParseError(f"packet is a JSON {type(value).__name__}, not an object")
    if depth(value) > MAX_DEPTH:
        raise ParseError(f"packet nests more than {MAX_DEPTH} levels")
    try:  # a \ud800-style escape decodes to a lone surrogate, which no output can encode
        json.dumps(value, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise ParseError("packet holds a string that is not valid Unicode (a lone surrogate)") from None
    return value
