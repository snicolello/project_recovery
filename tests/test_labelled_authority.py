"""The governing-record mapping: frontmatter key or labelled line (project_recovery #17).
No Node or QMD needed: rederive.VaultSession serves the vault bytes as QMD would.
Scenario S10 in run_scenarios.py covers the same cases against QMD itself.

Run: python -I -m unittest discover -s tests
"""
from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import packet as pk  # noqa: E402
import recipe  # noqa: E402
import rederive  # noqa: E402
import shape  # noqa: E402
from receipts import sha256_hex  # noqa: E402

AUTH_MANIFEST = REPO / "manifest" / "authority-notes.json"
LABEL = "- **Status:**"
BODY = ("- **Objective:** Test the labelled mapping.\n- **Current state:** Drafted.\n"
        "- **Blocker:** None recorded.\n- **Next action:** Review.\n")


def state_note(*status_lines: str, front: str = "", eol: str = "\n") -> bytes:
    text = (f"---\n{front}---\n" if front else "") + "# State\n\n" + "".join(f"{s}\n" for s in status_lines) + BODY
    return text.replace("\n", eol).encode("utf-8")


class Vault:
    """One project ``p`` in a temporary vault, with a manifest built from authority-notes.json
    and a generation record written as refresh would write it."""

    def __init__(self, test: unittest.TestCase, note: bytes, authority: dict, extra: dict | None = None):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.vault = Path(tmp.name) / "vault"
        (self.vault / "p").mkdir(parents=True)
        for rel, data in {"STATE.md": note, **(extra or {})}.items():
            (self.vault / "p" / rel).write_bytes(data)
        raw = json.loads(AUTH_MANIFEST.read_text(encoding="utf-8"))
        proj = copy.deepcopy(raw["projects"]["delta"])
        proj.update({"collection": "p", "root": "p", "authority": {"record": "STATE.md", **authority}})
        raw["projects"] = {"p": proj}
        raw["authority_policy"]["repositories"][0]["projects"] = ["p"]
        self.raw = raw
        path = Path(tmp.name) / "manifest.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        recipe.STATE_BASE.mkdir(exist_ok=True)
        state = recipe.STATE_BASE / f"test-label-{uuid.uuid4().hex[:8]}"
        test.addCleanup(shutil.rmtree, state, True)
        self.m = recipe.load_manifest(path, self.vault, state)
        state.mkdir()
        files = recipe.disk_files(self.m, self.m.projects["p"])
        recipe.generation_path(self.m).write_text(json.dumps({
            "generation": "qmd-2.8.3:" + sha256_hex(json.dumps(sorted(files.items())).encode())[:16],
            "files": files, "not_indexable": [], "verified_empty": [], "refreshed_at": recipe.now()}),
            encoding="utf-8")

    def session(self):
        return rederive.VaultSession(self.m, "p", [])

    def packet(self) -> dict:
        with self.session() as s:
            return recipe.assemble(self.m, "p", "status", s)

    def validate(self, packet: dict, mode: str) -> dict:
        data = json.dumps(packet, ensure_ascii=False).encode("utf-8")
        return rederive.validate(self.m, data, None, None, mode, session_factory=self.session)


class LabelledLineTests(unittest.TestCase):
    def assemble(self, note: bytes, authority: dict | None = None, extra: dict | None = None):
        v = Vault(self, note, {"record_label": LABEL} if authority is None else authority, extra)
        return v, v.packet()

    def assert_unknown(self, p: dict, reason: str, evidence: int) -> dict:
        a = p["fields"]["authority"]
        self.assertEqual(a["status"], "unknown")
        self.assertEqual(a["items"], [])
        self.assertIn(reason, a["reason"])
        self.assertEqual(len(a.get("evidence", [])), evidence)
        self.assertIn({"field": "authority", "reason": a["reason"]}, p["unknowns"])
        self.assertEqual(a["authority_state"], "local_only")
        return a

    def assert_rederives(self, v: Vault, p: dict) -> None:
        self.assertEqual(shape.check(p), [])
        for mode in rederive.MODES:
            with self.subTest(mode=mode):
                r = v.validate(p, mode)
                self.assertEqual(r["result"], "equal_to_rederived", r["problems"][:2])

    def test_one_labelled_line_establishes_authority_with_a_receipt(self):
        v, p = self.assemble(state_note(f"{LABEL} Pilot accepted; export open."))
        a = p["fields"]["authority"]
        self.assertEqual(a["status"], "established")
        self.assertEqual([i["text"] for i in a["items"]], [f"{LABEL} Pilot accepted; export open."])
        self.assertEqual(a["items"][0]["receipt"]["source"], "p/STATE.md")
        self.assertEqual(a["items"][0]["receipt"]["span"], [3, 3])
        self.assertNotIn("evidence", a)
        self.assertNotIn("authority", {u["field"] for u in p["unknowns"]})
        ok, why = pk.check_item(a["items"][0], v.m.vault_root, "p/", frozenset({p["freshness"]["generation"]}))
        self.assertTrue(ok, why)
        self.assertEqual(pk.unsupported_assertions(p, v.m.vault_root), [])
        self.assert_rederives(v, p)

    def test_crlf_note_cites_the_exact_bytes(self):
        v, p = self.assemble(state_note(f"{LABEL} Active.", eol="\r\n"))
        item = p["fields"]["authority"]["items"][0]
        self.assertEqual(item["text"], f"{LABEL} Active.")
        self.assertEqual(item["receipt"]["content_sha"], sha256_hex(f"{LABEL} Active.\r".encode()))
        self.assert_rederives(v, p)

    def test_two_labelled_lines_are_ambiguous(self):
        v, p = self.assemble(state_note(f"{LABEL} Green.", f"{LABEL} Blocked."))
        a = self.assert_unknown(p, "ambiguous", 2)
        self.assertEqual([i["receipt"]["span"] for i in a["evidence"]], [[3, 3], [4, 4]])
        conflicts = [c for c in p["conflicts"] if c["kind"] == "authority_ambiguous"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["source"], "p/STATE.md")
        self.assertEqual(pk.unsupported_assertions(p, v.m.vault_root), [])
        self.assert_rederives(v, p)

    def test_hand_promoted_ambiguous_authority_is_rejected(self):
        v, p = self.assemble(state_note(f"{LABEL} Green.", f"{LABEL} Blocked."))
        forged = copy.deepcopy(p)
        a = forged["fields"]["authority"]
        a.update({"status": "established", "items": a.pop("evidence")[:1]})
        del a["reason"]
        forged["unknowns"] = [u for u in forged["unknowns"] if u["field"] != "authority"]
        forged["conflicts"] = []
        for mode in rederive.MODES:
            with self.subTest(mode=mode):
                r = v.validate(forged, mode)
                self.assertEqual(r["result"], "rejected")
                self.assertEqual(pk.digest(r["packet"]), pk.digest(p))

    def test_absent_label_is_unknown(self):
        _, p = self.assemble(state_note("- Status: plain label, not the configured one."))
        self.assert_unknown(p, "no line labelled", 0)

    def test_nested_or_indented_label_does_not_match(self):
        _, p = self.assemble(state_note("- Milestones:", f"  {LABEL} first milestone done."))
        self.assert_unknown(p, "no line labelled", 0)

    def test_label_never_falls_back_to_frontmatter(self):
        _, p = self.assemble(state_note(front="title: State\nstatus: active\n"))
        self.assert_unknown(p, "no line labelled", 0)

    def test_unknown_value_is_unknown_with_evidence(self):
        for value in ("UNKNOWN", "UNKNOWN until the owner rules.", "unknown", "**UNKNOWN**", "_Unknown_"):
            with self.subTest(value=value):
                v, p = self.assemble(state_note(f"{LABEL} {value}"))
                a = self.assert_unknown(p, "source states UNKNOWN", 1)
                self.assertEqual(a["evidence"][0]["text"], f"{LABEL} {value}")

    def test_empty_value_is_unknown(self):
        for line in (LABEL, f"{LABEL}   ", f"{LABEL} ** "):
            with self.subTest(line=line):
                _, p = self.assemble(state_note(line))
                self.assert_unknown(p, "states no value", 1)

    def test_label_without_its_closing_markup_still_fails_closed_on_unknown(self):
        _, p = self.assemble(state_note(f"{LABEL} UNKNOWN"), {"record_label": "- **Status"})
        self.assert_unknown(p, "source states UNKNOWN", 1)

    def test_missing_governing_record_is_unknown(self):
        _, p = self.assemble(state_note(f"{LABEL} Active."), {"record": "Absent.md", "record_label": LABEL})
        self.assert_unknown(p, "no governing record found", 0)

    def test_local_prose_and_labels_never_become_acceptance(self):
        note = state_note(f"{LABEL} Accepted by the owner in chat.",
                          "- **Accepted decision:** Use CSV; approved by the owner.")
        decision = (b"---\ntitle: CSV\npermalink: csv\nstatus: accepted\nacceptance_record: "
                    b"https://github.example.test/portfolio/delta/issues/3#issuecomment-301\n---\n# CSV\nUse CSV.\n")
        _, p = self.assemble(note, extra={"CSV.md": decision})
        self.assertEqual(p["fields"]["authority"]["status"], "established")
        acc = p["fields"]["accepted_decisions"]
        self.assertEqual((acc["status"], acc["decisions"]), ("unknown", []))
        states = sorted((d["local_status"], d["authority_state"], d["verification"]["result"])
                        for d in p["fields"]["decision_candidates"]["decisions"])
        self.assertEqual(states, [("accepted", "unverified", "unavailable"),
                                  ("stated_in_baseline", "local_only", "not_referenced")])


class FrontmatterMappingTests(unittest.TestCase):
    """The default mapping keeps its behaviour for one key and now fails closed like the label."""

    def assemble(self, front: str):
        v = Vault(self, state_note(front=front), {"record_key": "status"})
        return v, v.packet()

    def test_one_key_establishes_authority(self):
        v, p = self.assemble("title: State\nstatus: active\n")
        a = p["fields"]["authority"]
        self.assertEqual((a["status"], [i["text"] for i in a["items"]]), ("established", ["status: active"]))
        self.assertEqual(sorted(a), ["approvals", "approver", "authority_state", "items", "status", "verification"])

    def test_absent_key_keeps_its_reason(self):
        _, p = self.assemble("title: State\n")
        a = p["fields"]["authority"]
        self.assertEqual((a["status"], a["reason"]), ("unknown", "no governing record found"))
        self.assertNotIn("evidence", a)

    def test_repeated_key_is_ambiguous(self):
        v, p = self.assemble("title: State\nstatus: active\nstatus: paused\n")
        a = p["fields"]["authority"]
        self.assertEqual(a["status"], "unknown")
        self.assertIn("ambiguous", a["reason"])
        self.assertEqual([i["text"] for i in a["evidence"]], ["status: active", "status: paused"])
        self.assertIn("authority_ambiguous", [c["kind"] for c in p["conflicts"]])
        r = v.validate(p, "packet")
        self.assertEqual(r["result"], "equal_to_rederived", r["problems"][:2])

    def test_unknown_or_empty_value_is_unknown(self):
        for front, reason in (("status: UNKNOWN\n", "source states UNKNOWN"),
                              ('status: "unknown"\n', "source states UNKNOWN"),
                              ("status:\n", "states no value")):
            with self.subTest(front=front):
                _, p = self.assemble(front)
                a = p["fields"]["authority"]
                self.assertEqual(a["status"], "unknown")
                self.assertIn(reason, a["reason"])
                self.assertEqual(len(a["evidence"]), 1)


class ManifestTests(unittest.TestCase):
    def raw(self, **authority) -> dict:
        raw = json.loads(AUTH_MANIFEST.read_text(encoding="utf-8"))
        raw["projects"]["delta"]["authority"] = {"record": "STATE.md", **authority}
        return raw

    def test_committed_manifests_validate(self):
        for name in ("authority-notes.json", "fixture-vault.json", "scenario-vault.json"):
            with self.subTest(name):
                raw = json.loads((REPO / "manifest" / name).read_text(encoding="utf-8"))
                self.assertEqual(recipe.validate_manifest(raw), [])

    def test_both_mappings_are_refused(self):
        errors = recipe.validate_manifest(self.raw(record_key="status", record_label=LABEL))
        self.assertEqual(errors, ["projects.delta.authority: record_key and record_label are exclusive; configure one"])

    def test_both_mappings_refused_at_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            raw = self.raw(record_key="status", record_label=LABEL)
            raw["vault"]["root"] = str(REPO / "fixtures" / "authority-notes")
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(recipe.RecipeError, "exclusive"):
                recipe.load_manifest(path, None, recipe.STATE_BASE / "test-label-refused")

    def test_label_must_be_a_non_empty_string(self):
        for label in ("", "  ", None, 3):
            with self.subTest(label=label):
                self.assertIn("projects.delta.authority.record_label must be a non-empty string",
                              recipe.validate_manifest(self.raw(record_label=label)))

    def test_either_mapping_alone_is_accepted(self):
        self.assertEqual(recipe.validate_manifest(self.raw(record_label=LABEL)), [])
        self.assertEqual(recipe.validate_manifest(self.raw(record_key="status")), [])
        self.assertEqual(recipe.validate_manifest(self.raw()), [])


class LabelReaderTests(unittest.TestCase):
    def test_labelled_fields_still_cite_the_first_match(self):
        note = recipe.parse_note("# N\nObjective: one.\nObjective: two.\n")
        self.assertEqual([ln.number for ln in recipe.label_lines(note, "Objective:")], [2, 3])
        v = Vault(self, state_note(f"{LABEL} Active.", "- **Objective:** An earlier objective line."),
                  {"record_label": LABEL})
        p = v.packet()
        self.assertEqual([i["text"] for i in p["fields"]["objective"]["items"]],
                         ["- **Objective:** An earlier objective line."])

    def test_label_lines_read_the_body_only(self):
        note = recipe.parse_note("---\n- **Status:** in frontmatter\n---\n# N\n- **Status:** in body\n")
        self.assertEqual([ln.number for ln in recipe.label_lines(note, LABEL)], [5])


if __name__ == "__main__":
    unittest.main()
