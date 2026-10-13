"""Focused tests for the synthetic transition rehearsal."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

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

    def test_mutating_names_never_reach_transport(self):
        class FakeSession:
            calls: list[str] = []

            def call_tool(self, name, arguments):
                if name not in rehearsal.ALLOWED_TOOLS:
                    raise rehearsal.QmdError("refused")
                self.calls.append(name)

        session = FakeSession()
        self.assertEqual(rehearsal.reject_mutating_tools(session), list(rehearsal.MUTATING_TOOLS))
        self.assertEqual(session.calls, [])

    def test_configuration_and_poisoned_advertisement_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault = base / "vault"
            vault.mkdir()
            result = rehearsal.configuration_probes(vault, base / "output")
            self.assertEqual(result, {"state_dir_inside_source": "rejected", "update_hook": "rejected"})
            self.assertEqual(rehearsal.poisoned_advertisement_probe(base / "output"), "rejected")

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

    def test_run_id_is_bounded(self):
        self.assertIsNotNone(rehearsal.RUN_ID.fullmatch("consumer-check-01"))
        for invalid in ("", "../escape", "space here", "x" * 65):
            with self.subTest(invalid=invalid):
                self.assertIsNone(rehearsal.RUN_ID.fullmatch(invalid))


if __name__ == "__main__":
    unittest.main()
