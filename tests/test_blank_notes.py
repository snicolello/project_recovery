"""Refresh with blank notes and empty collections (project_recovery #16). No Node or QMD
needed: QMD's index commands are skipped and its read tools are replaced by a stand-in
that serves exactly what each test says QMD serves. Scenario S9 in run_scenarios.py
covers the same cases against QMD itself.

Run: python -I -m unittest discover -s tests
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import recipe  # noqa: E402
import rederive  # noqa: E402
from receipts import sha256_hex  # noqa: E402

MANIFEST = REPO / "manifest" / "fixture-vault.json"  # projects atlas and beacon
PROBE = REPO / "evidence" / "qmd-blank-notes-2026-10-14" / "results.json"
NOTE = b"---\r\ntitle: T\r\nstatus: active\r\n---\r\n# T\r\nObjective: test blank notes.\r\n"
OTHER = b"# Other\nObjective: a second note.\n"


class IndexableRuleTests(unittest.TestCase):
    """The rule mirrors QMD 2.8.3 as probed, not Python's notion of whitespace."""

    @classmethod
    def setUpClass(cls):
        cls.probe = json.loads(PROBE.read_text(encoding="utf-8"))

    def test_rule_matches_every_probed_file(self):
        for name, r in self.probe["alone"].items():
            with self.subTest(name):
                self.assertEqual(recipe.indexable(bytes.fromhex(r["bytes_hex"])), r["indexed"])
                self.assertEqual(r["in_status"], r["indexed"], "status lists a collection iff it has a document")

    def test_whitespace_set_equals_node_trim(self):
        self.assertEqual(len(recipe.JS_WHITESPACE), 25)
        self.assertTrue(self.probe["trim"]["rule_equals_node"])
        self.assertEqual(sorted(f"U+{ord(c):04X}" for c in recipe.JS_WHITESPACE),
                         self.probe["trim"]["trimmed_code_points"])

    def test_cases_named_by_the_issue(self):
        cases = {b"": False, b"   \t": False, b"\n": False, b"\r\n\r\n": False, b"\xef\xbb\xbf": False,
                 b"---\ntitle: x\n---\n": True, b"\x1c": True, "\u0085".encode(): True, b"\xff": True, b" a ": True}
        for data, expected in cases.items():
            with self.subTest(data=data):
                self.assertEqual(recipe.indexable(data), expected)


class FakeSession:
    """QMD's read tools as a test declares them: ``served`` maps collection -> {rel: text},
    ``roots`` maps collection -> the root path status reports. Like QMD, status lists only
    collections that serve at least one document."""

    def __init__(self, served: dict, roots: dict):
        self.served, self.roots = served, roots

    def __call__(self, state_dir):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def status(self):
        return {"collections": [{"name": c, "path": self.roots[c]} for c, docs in self.served.items() if docs]}

    def multi_get(self, pattern, max_bytes=1_000_000):
        coll = pattern.partition("/")[0]
        return {f"{coll}/{rel}": text for rel, text in self.served.get(coll, {}).items()}


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "vault"
        for d in ("atlas", "beacon"):
            (self.vault / d).mkdir(parents=True)
        self.write("atlas/Project.md", NOTE)
        self.write("atlas/Other.md", OTHER)
        self.write("atlas/Untitled.md", b"")
        self.write("atlas/Bom.md", b"\xef\xbb\xbf\r\n")
        self.write("beacon/Untitled.md", b"\n")
        recipe.STATE_BASE.mkdir(exist_ok=True)
        self.state = recipe.STATE_BASE / f"test-blank-{uuid.uuid4().hex[:8]}"
        self.m = recipe.load_manifest(MANIFEST, self.vault, self.state)
        self.served = {"atlas": {"Project.md": NOTE.decode(), "Other.md": OTHER.decode()}}
        for target, value in (("installed_version", lambda: "2.8.3"), ("index_cli", lambda *a, **k: "")):
            patcher = mock.patch.object(recipe, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.state, ignore_errors=True)
        self.tmp.cleanup()

    def write(self, rel: str, data: bytes) -> None:
        (self.vault / rel).write_bytes(data)

    def refresh(self) -> dict:
        # Status reports the path refresh registered: the manifest's resolved root (on Windows a
        # temporary directory may be an 8.3 short path that resolves to its long form).
        roots = {c: str(self.m.vault_root / c) for c in ("atlas", "beacon")}
        with mock.patch.object(recipe, "McpSession", FakeSession(self.served, roots)):
            return recipe.refresh(self.m)

    def test_blank_notes_recorded_present_not_indexable(self):
        record = self.refresh()
        on_disk = {p.relative_to(self.vault).as_posix(): sha256_hex(p.read_bytes())
                   for p in self.vault.rglob("*.md")}
        self.assertEqual(record["files"], dict(sorted(on_disk.items())), "every Markdown file hashed")
        self.assertEqual(record["not_indexable"], ["atlas/Bom.md", "atlas/Untitled.md", "beacon/Untitled.md"])
        self.assertEqual(record["verified_empty"], ["beacon"])
        self.assertEqual(recipe.load_generation(self.m), record)
        self.assertEqual(recipe.indexed_sources(record), {"atlas/Project.md", "atlas/Other.md"})

    def test_blank_files_are_part_of_the_generation(self):
        first = self.refresh()
        self.assertEqual(recipe.generation_gap(self.m, self.m.projects["atlas"], first), [])
        self.write("atlas/Late.md", b"  ")
        gap = recipe.generation_gap(self.m, self.m.projects["atlas"], first)
        self.assertEqual(gap, [{"source": "atlas/Late.md", "change": "added_since_refresh"}])
        second = self.refresh()
        self.assertNotEqual(second["generation"], first["generation"])
        self.assertIn("atlas/Late.md", second["not_indexable"])

    def test_without_blank_notes_the_generation_is_unchanged(self):
        for rel in ("atlas/Untitled.md", "atlas/Bom.md", "beacon/Untitled.md"):
            (self.vault / rel).unlink()
        record = self.refresh()
        canonical = json.dumps(sorted({"atlas/Project.md": sha256_hex(NOTE), "atlas/Other.md": sha256_hex(OTHER)}
                                      .items()), separators=(",", ":")).encode()
        self.assertEqual(record["generation"], "qmd-2.8.3:" + sha256_hex(canonical)[:16])
        self.assertEqual((record["not_indexable"], record["verified_empty"]), ([], ["beacon"]))

    def assert_refused(self, pattern: str):
        with self.assertRaisesRegex(recipe.RecipeError, pattern):
            self.refresh()
        self.assertFalse(recipe.generation_path(self.m).exists(), "no generation recorded")

    def test_changed_non_blank_note_fails(self):
        self.served["atlas"]["Other.md"] = "# Other\nObjective: stale bytes.\n"
        self.assert_refused("does not match source bytes")

    def test_added_non_blank_note_fails(self):
        self.write("atlas/Added.md", b"New note.\n")
        self.assert_refused("does not match source bytes")

    def test_deleted_non_blank_note_fails(self):
        (self.vault / "atlas" / "Other.md").unlink()
        self.assert_refused("does not match source bytes")

    def test_blank_note_served_by_qmd_fails(self):
        self.served["atlas"]["Untitled.md"] = ""
        self.assert_refused("blank on disk")

    def test_note_emptied_after_indexing_fails_naming_rebuild(self):
        self.write("atlas/Other.md", b"\r\n")
        self.assert_refused(r"atlas/Other\.md\).*--rebuild")

    def test_absent_collection_with_indexable_note_fails(self):
        self.write("beacon/Project.md", NOTE)
        self.assert_refused("collection beacon is not in the index although 1 indexable")

    def test_missing_or_renamed_root_is_never_verified_empty(self):
        first = self.refresh()
        self.assertEqual(first["verified_empty"], ["beacon"])
        shutil.rmtree(self.vault / "beacon")
        with self.assertRaisesRegex(recipe.RecipeError,
                                    "project root 'beacon' for collection beacon does not exist as a directory"):
            self.refresh()
        (self.vault / "beacon").write_bytes(b"")  # a file where the root should be
        with self.assertRaisesRegex(recipe.RecipeError, "does not exist as a directory"):
            self.refresh()
        self.assertEqual(recipe.load_generation(self.m), first, "the earlier generation is kept")

    def test_every_collection_empty(self):
        self.served = {}
        for rel in ("atlas/Project.md", "atlas/Other.md"):
            self.write(rel, b"")
        record = self.refresh()
        self.assertEqual(record["verified_empty"], ["atlas", "beacon"])
        self.assertEqual(len(record["not_indexable"]), len(record["files"]))

    def test_listed_collection_must_still_point_at_the_root(self):
        roots = {"atlas": str(self.m.vault_root / "beacon"), "beacon": str(self.m.vault_root / "beacon")}
        with mock.patch.object(recipe, "McpSession", FakeSession(self.served, roots)):
            with self.assertRaisesRegex(recipe.RecipeError, "does not point at the manifest root"):
                recipe.refresh(self.m)

    def test_packet_mode_reader_serves_only_what_qmd_serves(self):
        reader = rederive.VaultSession(self.m, "atlas", [])
        self.assertEqual(sorted(reader.multi_get("atlas/**/*.md")), ["atlas/Other.md", "atlas/Project.md"])
        self.assertIsNone(reader.get("atlas/Untitled.md"))
        self.assertIsNone(reader.get("atlas/Bom.md", 1, 1))
        self.assertEqual(reader.multi_get("beacon/**/*.md"), {})

    def test_record_without_not_indexable_field(self):
        self.assertEqual(recipe.indexed_sources({"files": {"a.md": "x"}}), {"a.md"})


if __name__ == "__main__":
    unittest.main()
