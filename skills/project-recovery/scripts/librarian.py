"""Model-independent preparation seam for a future optional Librarian.

The Librarian proposal is untrusted JSON.  It may suggest bounded retrieval queries and
state a raw claim (or abstain) for each mandatory recovery field.  Claim text is never
used to assemble a packet and is never copied into the result.  Queries are run through
the existing deterministic recipe; the resulting candidate is then re-derived with a
fresh ``hits=requery`` validation.  Only that validator-produced packet can be returned.

This module deliberately contains no model client, runtime transport, prompt execution,
download, installation, or alternate retrieval implementation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import packet as pk
import recipe
import rederive
from qmd_client import McpSession, QmdError

MAX_PROPOSAL_BYTES = 32_768
MAX_QUERIES = 4
MAX_QUERY_CHARS = 512
MAX_CLAIM_CHARS = 2_048
CLAIM_FIELDS = (
    "objective",
    "authority",
    "accepted_decisions",
    "current_state",
    "blockers",
    "next_action",
)


@dataclass(frozen=True)
class Proposal:
    """A structurally accepted proposal.  Values remain untrusted raw model output."""

    queries: tuple[str, ...]
    claims: dict[str, str | None]


class ProposalError(ValueError):
    pass


def _reject_constant(value: str):
    raise ProposalError(f"non-finite JSON value {value!r} is not allowed")


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ProposalError(f"duplicate JSON key {key!r}")
        out[key] = value
    return out


def _clean_text(value, label: str, limit: int, *, allow_null: bool = False) -> str | None:
    if allow_null and value is None:
        return None
    if not isinstance(value, str):
        raise ProposalError(f"{label} must be a string" + (" or null" if allow_null else ""))
    if not value or value.strip() != value:
        raise ProposalError(f"{label} must be non-empty and have no leading or trailing whitespace")
    if len(value) > limit:
        raise ProposalError(f"{label} exceeds the {limit}-character limit")
    if any(ord(ch) < 32 or 0xD800 <= ord(ch) <= 0xDFFF for ch in value):
        raise ProposalError(f"{label} contains a control character or lone surrogate")
    return value


def parse_proposal(data: bytes | str) -> Proposal:
    """Strictly parse the small raw-proposal envelope, or raise ``ProposalError``.

    All six claim keys are required.  A string means "the proposer claims this field is
    answerable"; ``null`` is an explicit abstention.  The strings are deliberately not
    interpreted here.  Exact keys prevent a proposal from smuggling a packet, receipt,
    source locator, tool instruction, or out-of-contract field into the trusted path.
    """
    if isinstance(data, str):
        try:
            raw_bytes = data.encode("utf-8")
        except UnicodeError as exc:
            raise ProposalError(f"proposal is not valid UTF-8: {exc}") from exc
    elif isinstance(data, bytes):
        raw_bytes = data
    else:
        raise ProposalError("proposal must be UTF-8 JSON bytes or text")
    if len(raw_bytes) > MAX_PROPOSAL_BYTES:
        raise ProposalError(f"proposal exceeds the {MAX_PROPOSAL_BYTES}-byte limit")
    try:
        text = raw_bytes.decode("utf-8")
        obj = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except ProposalError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ProposalError(f"proposal is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ProposalError("proposal must be one JSON object")
    if set(obj) != {"queries", "claims"}:
        extra = sorted(set(obj) - {"queries", "claims"})
        missing = sorted({"queries", "claims"} - set(obj))
        raise ProposalError(f"proposal keys must be exactly queries and claims; extra={extra}, missing={missing}")
    queries = obj["queries"]
    if not isinstance(queries, list) or not 1 <= len(queries) <= MAX_QUERIES:
        raise ProposalError(f"queries must contain from 1 to {MAX_QUERIES} strings")
    cleaned = tuple(_clean_text(q, f"queries[{i}]", MAX_QUERY_CHARS) for i, q in enumerate(queries))
    if len(cleaned) != len(set(cleaned)):
        raise ProposalError("queries must be unique")
    claims = obj["claims"]
    if not isinstance(claims, dict) or set(claims) != set(CLAIM_FIELDS):
        extra = sorted(set(claims) - set(CLAIM_FIELDS)) if isinstance(claims, dict) else []
        missing = sorted(set(CLAIM_FIELDS) - set(claims)) if isinstance(claims, dict) else list(CLAIM_FIELDS)
        raise ProposalError(f"claims keys must be exactly the recovery fields; extra={extra}, missing={missing}")
    return Proposal(cleaned, {
        name: _clean_text(claims[name], f"claims.{name}", MAX_CLAIM_CHARS, allow_null=True)
        for name in CLAIM_FIELDS
    })


def _implicates(value, field: str) -> bool:
    if not isinstance(value, str):
        return False
    expected = f"fields.{field}"
    return (value == field or value.startswith(field + ".")
            or value == expected or value.startswith(expected + "."))


def score_abstention(claims: dict[str, str | None], packet: dict) -> dict:
    """Score claim-versus-abstain posture; never judge or retain the raw claim text.

    A deterministic field is answerable only when its assembled node is established and
    no unknown or conflict names that field.  This deliberately measures abstention only:
    a raw string on an answerable field is *not* evidence that the string is correct.
    """
    unknowns = packet.get("unknowns") if isinstance(packet.get("unknowns"), list) else []
    conflicts = packet.get("conflicts") if isinstance(packet.get("conflicts"), list) else []
    fields = packet.get("fields") if isinstance(packet.get("fields"), dict) else {}
    rows = []
    counts = {"claim_on_answerable": 0, "correct_abstention": 0,
              "false_abstention": 0, "claim_on_unknown_or_conflict": 0}
    for name in CLAIM_FIELDS:
        node = fields.get(name) if isinstance(fields.get(name), dict) else {}
        named_unknowns = [u.get("reason", "unknown") for u in unknowns
                          if isinstance(u, dict) and _implicates(u.get("field"), name)]
        named_conflicts = [c.get("kind", "conflict") for c in conflicts
                           if isinstance(c, dict) and _implicates(c.get("field"), name)]
        answerable = node.get("status") == "established" and not named_unknowns and not named_conflicts
        claimed = claims[name] is not None
        if answerable and claimed:
            outcome = "claim_on_answerable"
        elif not answerable and not claimed:
            outcome = "correct_abstention"
        elif answerable:
            outcome = "false_abstention"
        else:
            outcome = "claim_on_unknown_or_conflict"
        counts[outcome] += 1
        rows.append({
            "field": name,
            "deterministic_posture": "answerable" if answerable else "abstain",
            "raw_posture": "claim" if claimed else "abstain",
            "outcome": outcome,
            "unknown_reasons": named_unknowns,
            "conflict_kinds": named_conflicts,
        })
    correct = counts["claim_on_answerable"] + counts["correct_abstention"]
    return {"fields": rows, "counts": counts, "correct_posture": correct,
            "total_fields": len(CLAIM_FIELDS), "rate": correct / len(CLAIM_FIELDS),
            "claim_text_correctness_established": False}


def rejected(reason: str, problems: list[dict] | None = None) -> dict:
    return {"status": "rejected", "reason": reason, "problems": problems or [], "packet": None}


def prepare(m: recipe.Manifest, project: str, raw_proposal: bytes | str, *,
            transport: str | None = None, snapshot_dir: Path | None = None,
            max_tokens: int | None = None,
            assembly_session_factory: Callable[[str], object] | None = None,
            validation_session_factory: Callable[[str], object] | None = None) -> dict:
    """Prepare and validate every proposed query without executing a model.

    Session factories are dependency seams for deterministic tests and the existing QMD
    client.  Each call must return a new context-managed read-only session.  A result's
    ``packet`` is populated only from ``rederive.validate`` after a successful requery
    validation and a complete freshness result.
    """
    try:
        proposal = parse_proposal(raw_proposal)
    except ProposalError as exc:
        return {"status": "rejected", "proposal": {"status": "rejected", "reason": str(exc)},
                "results": [], "packets": []}
    if project not in m.projects:
        return {"status": "rejected",
                "proposal": {"status": "structurally_accepted_untrusted", "query_count": len(proposal.queries)},
                "results": [rejected(f"project {project!r} is not in the manifest")], "packets": []}
    make_assembly = assembly_session_factory or (lambda _query: McpSession(m.state_dir))
    make_validation = validation_session_factory or (lambda _query: McpSession(m.state_dir))
    results = []
    packets = []
    for index, query in enumerate(proposal.queries):
        try:
            with make_assembly(query) as session:
                candidate = recipe.assemble(m, project, query, session, max_tokens,
                                            recipe.make_verifier(m, transport, snapshot_dir))
            checked = rederive.validate(
                m, pk.compact(candidate), transport, snapshot_dir, "requery",
                session_factory=lambda q=query: make_validation(q),
            )
        except (QmdError, OSError, recipe.RecipeError, ValueError, UnicodeError) as exc:
            results.append({"query_index": index, **rejected(
                f"deterministic preparation failed: {type(exc).__name__}: {str(exc)[:240]}")})
            continue
        trusted = checked.get("packet")
        if checked.get("result") != "equal_to_rederived" or not isinstance(trusted, dict):
            results.append({"query_index": index, **rejected(
                f"fresh hits=requery validation returned {checked.get('result')!r}", checked.get("problems", []))})
            continue
        gap = (trusted.get("freshness") or {}).get("generation_gap")
        if trusted.get("status") != "complete" or gap:
            results.append({"query_index": index, **rejected(
                "validator re-derived an incomplete packet; refresh and retry")})
            continue
        score = score_abstention(proposal.claims, trusted)
        result = {"query_index": index, "status": "validated", "reason": None,
                  "problems": [], "abstention": score, "packet": trusted}
        results.append(result)
        packets.append(trusted)
    return {
        "status": "prepared" if packets else "rejected",
        "proposal": {"status": "structurally_accepted_untrusted", "query_count": len(proposal.queries),
                     "claim_fields": list(CLAIM_FIELDS), "raw_claim_text_returned": False},
        "results": results,
        "packets": packets,
    }
