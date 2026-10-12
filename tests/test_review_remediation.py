"""Tests for the PR #1 review remediation (B1 state-dir confinement, B2 packet audit,
B3 exact QMD CLI allowlist). No Node or QMD needed.

Run: python -I -m unittest discover -s tests
"""
from __future__ import annotations

import contextlib
import copy
import dataclasses
import io
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
import qmd_client  # noqa: E402
import recipe  # noqa: E402
import recover  # noqa: E402
from receipts import make_receipt, normalize_text, span_bytes  # noqa: E402

MANIFEST = REPO / "manifest" / "fixture-vault.json"
NOTE = b"---\r\ntitle: T\r\nstatus: active\r\n---\r\n# T\r\nObjective: test the audit.\r\nBlocker: none.\r\n"


def listing(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) if root.exists() else []


class StateDirTests(unittest.TestCase):
    """B1: the state dir must be strictly inside <repo>/.qmd/ and disjoint from the vault."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        (self.vault / "atlas").mkdir(parents=True)
        (self.vault / "atlas" / "Project.md").write_bytes(NOTE)
        (Path(self.tmp.name) / "sibling.txt").write_text("keep", encoding="utf-8")
        recipe.STATE_BASE.mkdir(exist_ok=True)
        self.own = recipe.STATE_BASE / f"test-{uuid.uuid4().hex[:8]}"

    def tearDown(self):
        shutil.rmtree(self.own, ignore_errors=True)
        self.tmp.cleanup()

    def assert_rejected(self, state_dir: Path, vault: Path | None = None):
        vault = vault or self.vault
        before = listing(Path(self.tmp.name)), listing(vault)
        existed = state_dir.exists()
        with self.assertRaises(recipe.RecipeError):
            recipe.load_manifest(MANIFEST, vault, state_dir)
        self.assertEqual((listing(Path(self.tmp.name)), listing(vault)), before)
        self.assertEqual(state_dir.exists(), existed)

    def test_equal_to_vault_rejected(self):
        self.assert_rejected(self.vault)

    def test_ancestor_of_vault_rejected(self):
        self.assert_rejected(Path(self.tmp.name))

    def test_outside_repo_rejected(self):
        self.assert_rejected(Path(self.tmp.name) / "elsewhere")

    def test_inside_vault_rejected(self):
        self.assert_rejected(self.vault / "atlas" / "idx")

    def test_qmd_base_itself_and_repo_rejected(self):
        self.assert_rejected(recipe.STATE_BASE)
        self.assert_rejected(REPO)

    def test_vault_under_qmd_overlap_rejected(self):
        vault = self.own / "vault"
        (vault / "atlas").mkdir(parents=True)
        self.assert_rejected(vault, vault)
        self.assert_rejected(vault / "idx", vault)
        self.assert_rejected(self.own, vault)  # ancestor of the vault, inside .qmd

    def test_default_and_explicit_dirs_under_qmd_accepted(self):
        self.assertTrue(str(recipe.load_manifest(MANIFEST, self.vault).state_dir).startswith(str(recipe.STATE_BASE)))
        self.assertEqual(recipe.load_manifest(MANIFEST, self.vault, self.own).state_dir, self.own.resolve())
        self.assertFalse(self.own.exists(), "loading a manifest writes nothing")

    def test_refresh_rechecks_state_dir_before_any_write(self):
        m = dataclasses.replace(recipe.load_manifest(MANIFEST, self.vault, self.own), state_dir=self.vault)
        before = listing(self.vault)
        with self.assertRaises(recipe.RecipeError):
            recipe.refresh(m, rebuild=True)
        self.assertEqual(listing(self.vault), before)

    def test_rebuild_refuses_dir_without_marker(self):
        self.own.mkdir()
        (self.own / "index.sqlite").write_text("x", encoding="utf-8")
        m = recipe.load_manifest(MANIFEST, self.vault, self.own)
        with self.assertRaises(recipe.RecipeError):
            recipe.refresh(m, rebuild=True)
        self.assertEqual(listing(self.own), ["index.sqlite"])

    def test_rebuild_refuses_unknown_entries(self):
        self.own.mkdir()
        (self.own / recipe.STATE_MARKER).write_text("", encoding="utf-8")
        (self.own / "notes.md").write_text("not ours", encoding="utf-8")
        with self.assertRaises(recipe.RecipeError):
            recipe.clear_state(self.own)
        self.assertEqual(listing(self.own), sorted([recipe.STATE_MARKER, "notes.md"]))

    def test_rebuild_deletes_only_tool_files(self):
        (self.own / "config").mkdir(parents=True)
        (self.own / "config" / "index.yml").write_text("collections: {}\n", encoding="utf-8")
        for name in (recipe.STATE_MARKER, "index.sqlite", "generation.json", "mcp-stderr.log"):
            (self.own / name).write_text("", encoding="utf-8")
        recipe.clear_state(self.own)
        self.assertFalse(self.own.exists())


class AuditTests(unittest.TestCase):
    """B2: validate fails tampered packets structurally, not only on receipt bytes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for d in ("atlas", "beacon"):
            (self.root / d).mkdir()
            (self.root / d / "Project.md").write_bytes(NOTE)

    def tearDown(self):
        self.tmp.cleanup()

    def item(self, source: str, line: int, generation: str = "g1") -> dict:
        cited = span_bytes((self.root / source).read_bytes(), line, line)
        return {"text": normalize_text(cited), "receipt": make_receipt(source, line, line, cited, generation, "t")}

    def packet(self) -> dict:
        return {
            "project": "atlas", "scope": {"collection": "atlas", "root": "atlas"},
            "freshness": {"generation": "g1"}, "status": "complete",
            "fields": {
                "objective": {"status": "established", "items": [self.item("atlas/Project.md", 6)]},
                "authority": {"status": "established", "items": [self.item("atlas/Project.md", 3)],
                              "authority_state": "local_only",
                              "approvals": {"rollout_approval": {"status": "unknown", "items": []}}},
                "accepted_decisions": {"status": "unknown", "decisions": []},
                "decision_candidates": {"status": "candidate", "decisions": [
                    {"title": "D", "local_status": "accepted", "authority_state": "local_only",
                     "status": "established", "items": [self.item("atlas/Project.md", 3)]}]},
            },
            "query_hits": [], "conflicts": [], "unknowns": [],
        }

    def kinds(self, p: dict, **kw) -> list[str]:
        return [x["kind"] for x in pk.unsupported_assertions(p, self.root, **kw)]

    def test_clean_packet_passes(self):
        self.assertEqual(self.kinds(self.packet()), [])
        self.assertEqual(self.kinds(self.packet(), expected_generation="g1", scope_root="atlas"), [])

    def test_established_node_without_items_fails(self):
        p = self.packet()
        p["fields"]["authority"]["approvals"]["rollout_approval"] = {"status": "established", "value": "approved"}
        out, problems = pk.audit(p, self.root)
        self.assertEqual([x["kind"] for x in problems], ["established_without_valid_items"])
        self.assertEqual(out["fields"]["authority"]["approvals"]["rollout_approval"]["status"], "unknown")

    def test_empty_items_list_counts_as_failure(self):
        p = self.packet()
        p["fields"]["objective"]["items"] = []
        self.assertEqual(self.kinds(p), ["established_without_valid_items"])

    def test_decision_without_items_fails(self):
        p = self.packet()
        p["fields"]["decision_candidates"]["decisions"][0]["items"] = []
        self.assertEqual(self.kinds(p), ["established_without_valid_items"])

    def test_decision_container_without_established_decision_fails(self):
        p = self.packet()
        p["fields"]["accepted_decisions"] = {"status": "established", "decisions": []}
        self.assertEqual(self.kinds(p), ["established_without_verified_decision"])

    def test_verified_state_on_a_candidate_fails(self):
        p = self.packet()
        p["fields"]["decision_candidates"]["decisions"][0]["authority_state"] = "verified"
        out, problems = pk.audit(p, self.root)
        self.assertEqual([x["kind"] for x in problems], ["authority_state_not_permitted"])
        self.assertEqual(out["fields"]["decision_candidates"]["decisions"][0]["authority_state"], "unverified")

    def test_state_outside_the_contract_fails(self):
        p = self.packet()
        p["fields"]["authority"]["authority_state"] = "approved"
        self.assertEqual(self.kinds(p), ["authority_state_not_permitted"])

    def test_receipt_from_other_project_root_fails(self):
        p = self.packet()
        p["fields"]["objective"]["items"] = [self.item("beacon/Project.md", 6)]
        self.assertEqual(self.kinds(p), ["receipt_validation_failed", "established_without_valid_items"])

    def test_scope_root_cannot_be_widened_by_the_packet(self):
        p = self.packet()
        p["scope"]["root"] = "beacon"
        p["fields"]["objective"]["items"] = [self.item("beacon/Project.md", 6)]
        kinds = self.kinds(p, scope_root="atlas")
        self.assertIn("scope_mismatch", kinds)
        self.assertIn("receipt_validation_failed", kinds)

    def test_missing_conflicts_and_unknowns_keys(self):
        p = self.packet()
        del p["conflicts"], p["unknowns"]
        p["fields"]["objective"]["items"] = []
        out, problems = pk.audit(p, self.root)
        self.assertEqual(len(problems), 1)
        self.assertEqual(len(out["conflicts"]), 1)
        self.assertEqual(out["unknowns"][0]["field"], "fields.objective")

    def test_receipt_generation_must_match(self):
        p = self.packet()
        p["fields"]["objective"]["items"] = [self.item("atlas/Project.md", 6, generation="g2")]
        self.assertEqual(self.kinds(p), ["receipt_validation_failed", "established_without_valid_items"])

    def test_packet_generation_must_match_recorded(self):
        kinds = self.kinds(self.packet(), expected_generation="g9")
        self.assertEqual(kinds[0], "generation_mismatch")
        self.assertIn("receipt_validation_failed", kinds)

    def test_missing_scope_fails_every_receipt(self):
        p = self.packet()
        del p["scope"]
        kinds = self.kinds(p)
        self.assertEqual(kinds[0], "structural")
        self.assertIn("receipt_validation_failed", kinds)

    def test_validate_cli_exit_codes(self):
        state = recipe.STATE_BASE / f"test-{uuid.uuid4().hex[:8]}"
        try:
            good = self.packet()
            bad = copy.deepcopy(good)
            bad["fields"]["authority"]["approvals"]["rollout_approval"] = {"status": "established"}
            for packet, expected in ((good, 0), (bad, 1)):
                path = self.root / "packet.json"
                path.write_text(json.dumps(packet), encoding="utf-8")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = recover.main(["validate", "--manifest", str(MANIFEST), "--vault-root", str(self.root),
                                         "--state-dir", str(state), "--packet", str(path)])
                self.assertEqual(code, expected, buf.getvalue()[:300])
                self.assertEqual(json.loads(buf.getvalue())["failures"], expected)
            self.assertFalse(state.exists(), "validate writes nothing")
        finally:
            shutil.rmtree(state, ignore_errors=True)


class CliAllowlistTests(unittest.TestCase):
    """B3: exact argv for the two index commands; no update hooks."""

    def test_exact_argv(self):
        abs_dir = str(Path(tempfile.gettempdir()).resolve())
        qmd_client.check_cli_args(["update"])
        qmd_client.check_cli_args(["collection", "add", abs_dir, "--name", "atlas"])
        for args in (["update", "--pull"], ["update", "atlas"],
                     ["collection", "add", abs_dir, "--name", "atlas", "--mask", "**"],
                     ["collection", "add", "relative/dir", "--name", "atlas"],
                     ["collection", "add", "--pull", "--name", "atlas"],
                     ["collection", "add", abs_dir, "--name", "a;b"],
                     ["collection", "add", abs_dir, "--pattern", "atlas"]):
            with self.subTest(args=args), self.assertRaises(qmd_client.QmdError):
                qmd_client.index_cli(Path(tempfile.gettempdir()), args)

    def test_update_hook_in_config_refused_before_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state / "config").mkdir()
            cfg = state / "config" / "index.yml"
            cfg.write_text("collections:\n  atlas:\n    path: x\n    pattern: \"**/*.md\"\n", encoding="utf-8")
            qmd_client.check_no_hooks(state)
            cfg.write_text("collections:\n  atlas:\n    path: x\n    update: git pull\n", encoding="utf-8")
            with self.assertRaises(qmd_client.QmdError):
                qmd_client.index_cli(state, ["update"])


if __name__ == "__main__":
    unittest.main()
