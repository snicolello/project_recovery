"""Focused tests for the synthetic transition rehearsal."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("rehearse_transition", REPO / "scripts" / "rehearse_transition.py")
assert SPEC and SPEC.loader
rehearsal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rehearsal)


class TransitionRehearsalTests(unittest.TestCase):
    def test_paths_are_pairwise_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            rehearsal.assert_isolated(base / "vault", base / "state", base / "output")
            with self.assertRaises(rehearsal.RehearsalError):
                rehearsal.assert_isolated(base / "vault", base / "vault" / "state", base / "output")
            with self.assertRaises(rehearsal.RehearsalError):
                rehearsal.assert_isolated(base / "vault", base / "state", base / "state" / "output")

    def test_verified_copy_rejects_source_drift_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source, destination = base / "source", base / "destination"
            (source / "project").mkdir(parents=True)
            note = source / "project" / "Note.md"
            note.write_text("synthetic\n", encoding="utf-8")
            expected = {"project/Note.md": rehearsal.sha256_file(note)}
            rehearsal.copy_verified_vault(source, destination, expected)
            self.assertEqual(rehearsal.verify_tree(destination, expected), expected)
            with self.assertRaises(rehearsal.RehearsalError):
                rehearsal.copy_verified_vault(source, destination, expected)
            note.write_text("changed\n", encoding="utf-8")
            with self.assertRaises(rehearsal.RehearsalError):
                rehearsal.verify_tree(source, expected)

    def test_parent_and_link_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = rehearsal.trust_root_probes(Path(tmp))
            self.assertEqual(result["parent_traversal"], "rejected")
            self.assertIn(result["link_escape"], {"rejected", "not_available"})

    def test_mutating_names_use_real_unentered_session_and_never_reach_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = rehearsal.McpSession(Path(tmp))
            self.assertIsNone(session._proc)
            self.assertEqual(rehearsal.reject_mutating_tools(session), list(rehearsal.MUTATING_TOOLS))
            self.assertEqual(session.calls, [])

    def test_mutating_guard_fails_when_allowlist_is_deliberately_widened(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = rehearsal.McpSession(Path(tmp))
            widened = frozenset(set(rehearsal.qmd_client.ALLOWED_TOOLS) | {"write"})
            with mock.patch.object(rehearsal.qmd_client, "ALLOWED_TOOLS", widened), \
                    mock.patch.object(session, "_rpc", return_value={}):
                with self.assertRaisesRegex(rehearsal.RehearsalError, "mutating tool was callable: write"):
                    rehearsal.reject_mutating_tools(session)

    def test_poisoned_advertisement_is_precise_and_falsifiable_without_qmd(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "output"
            result = rehearsal.poisoned_advertisement_probe(output)
            self.assertEqual(result["result"], "rejected")
            self.assertEqual(
                result["error"],
                "QMD advertises tools outside the read-only allowlist: "
                "['get', 'multi_get', 'query', 'status', 'write']",
            )
            widened = frozenset(set(rehearsal.qmd_client.ALLOWED_TOOLS) | {"write"})
            with mock.patch.object(rehearsal.qmd_client, "ALLOWED_TOOLS", widened):
                accepted = rehearsal.poisoned_advertisement_probe(Path(tmp) / "widened")
            self.assertEqual(accepted["result"], "accepted")
            self.assertIn("write", accepted["advertised"])

    def test_state_overlap_is_the_only_rejection_and_is_falsifiable(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / ".qmd"
            vault = base / "probe" / "vault"
            vault.mkdir(parents=True)
            state = vault / "derived-state"
            with mock.patch.object(rehearsal.recipe, "STATE_BASE", base):
                result = rehearsal.state_directory_probe(vault, state)
            self.assertEqual(
                result,
                {
                    "result": "rejected",
                    "error": "state dir must not equal, contain, or sit inside the vault root",
                },
            )
            with mock.patch.object(rehearsal.recipe, "check_state_dir", return_value=None):
                self.assertEqual(rehearsal.state_directory_probe(vault, state), {"result": "accepted"})

    def test_configuration_hook_rejection_is_precise(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            fake_state = base / ".qmd"
            with mock.patch.object(rehearsal.recipe, "STATE_BASE", fake_state), \
                    mock.patch.object(rehearsal, "REPO", base):
                result = rehearsal.configuration_probes(base / "output" / "run")
            self.assertEqual(
                result["update_hook"],
                {
                    "result": "rejected",
                    "error": "QMD config defines an update hook; refusing to run: index.yml",
                },
            )

    def test_isolated_storage_observation_fails_when_cache_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            state, vault = base / ".qmd" / "state", base / "vault"
            state.mkdir(parents=True)
            vault.mkdir()
            (state / "index.sqlite").write_bytes(b"synthetic index")
            (state / "config").mkdir()
            with self.assertRaisesRegex(rehearsal.RehearsalError, "isolated QMD cache directory is missing"):
                rehearsal.observe_isolated_storage(state, vault)
            (state / "xdg-cache").mkdir()
            with mock.patch.object(rehearsal, "REPO", base):
                observed = rehearsal.observe_isolated_storage(state, vault)
            self.assertEqual(observed["result"], "pass")
            self.assertTrue(observed["cache"]["exists"])

    def test_default_home_observation_detects_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            before = rehearsal.observe_default_home(home)
            cache = home / ".cache" / "qmd"
            cache.mkdir(parents=True)
            (cache / "unexpected").write_text("synthetic\n", encoding="utf-8")
            after = rehearsal.observe_default_home(home)
            with self.assertRaisesRegex(rehearsal.RehearsalError, "default QMD home paths changed: cache"):
                rehearsal.assert_default_home_unchanged(before, after)

    def test_preflight_inputs_retention_and_audit(self):
        expected = rehearsal.expected_hashes()
        self.assertEqual(len(expected), 16)
        self.assertEqual(rehearsal.verify_tree(rehearsal.FIXTURE_ROOT, expected), expected)
        self.assertEqual(rehearsal.repository_path(rehearsal.FIXTURE_ROOT), "fixtures/synthetic-vault")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            paths = {"output": base / "output", "vault": base / "vault", "state": base / "state"}
            paths["output"].mkdir()
            marker = paths["output"] / "retained.txt"
            marker.write_text("retain\n", encoding="utf-8")
            with self.assertRaisesRegex(rehearsal.RehearsalError, "preserve them.*output"):
                rehearsal.require_fresh_run_paths(paths)
            self.assertEqual(marker.read_text(encoding="utf-8"), "retain\n")

    def test_snippet_label_mismatch_is_bounded_and_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            note = vault / "atlas" / "Queue Archive.md"
            note.parent.mkdir()
            note.write_text("---\ntitle: Queue Archive\n---\n# Queue Archive\n"
                            "Atlas queue originally used Redis.\n", encoding="utf-8")
            hits = [{"file": "atlas/Queue Archive.md", "line": 5,
                     "snippet": "5: @@ -4,2 @@\n6: # Queue Archive\n7: Atlas queue originally used Redis."}]
            result = rehearsal.snippet_line_probe(hits, vault)
            self.assertEqual(result["result"], "reproduced")
            self.assertEqual((result["rendered_heading_label"], result["actual_heading_line"]), (6, 4))
            self.assertEqual((result["match_line_field"], result["actual_match_line"]), (5, 5))

    def test_keyboard_interrupt_is_not_caught(self):
        source = (REPO / "scripts" / "rehearse_transition.py").read_text(encoding="utf-8")
        self.assertNotIn("except BaseException", source)
        with mock.patch.object(rehearsal, "run", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                rehearsal.main(["--run-id", "interrupt-probe"])

    def test_run_id_is_bounded(self):
        self.assertIsNotNone(rehearsal.RUN_ID.fullmatch("consumer-check-01"))
        for invalid in ("", "../escape", "space here", "x" * 65):
            with self.subTest(invalid=invalid):
                self.assertIsNone(rehearsal.RUN_ID.fullmatch(invalid))


if __name__ == "__main__":
    unittest.main()
