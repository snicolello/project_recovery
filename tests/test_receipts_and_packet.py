"""Unit tests for receipt validation, packet bounding and the read-only surface.

Run: python -I -m unittest discover -s tests -t .
These tests need neither Node nor QMD; they use a temporary synthetic root.
"""
from __future__ import annotations

import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "project-recovery" / "scripts"))

import packet as pk  # noqa: E402
import qmd_client  # noqa: E402
from receipts import (SourceError, make_receipt, normalize_text, safe_resolve, span_bytes,  # noqa: E402
                      validate_receipt)

NOTE = b"---\r\ntitle: T\r\nstatus: accepted\r\n---\r\n# T\r\nObjective: test the verifier.\r\nBlocker: none.\r\n"


def item(root: Path, source: str, start: int, end: int) -> dict:
    cited = span_bytes((root / source).read_bytes(), start, end)
    return {"text": normalize_text(cited), "receipt": make_receipt(source, start, end, cited, "g1", "t")}


def sample_packet(root: Path, hits: int = 0) -> dict:
    return {
        "fields": {
            "objective": {"status": "established", "items": [item(root, "p/Note.md", 6, 6)]},
            "other_decisions": {"decisions": [{"title": f"d{i}", "status": "established",
                                               "items": [item(root, "p/Note.md", 3, 3)]} for i in range(3)]},
        },
        "query_hits": [{"rank": i, "status": "established", "items": [item(root, "p/Note.md", 5, 7)]}
                       for i in range(hits)],
        "conflicts": [{"field": "x", "kind": "pre-existing"}],
        "unknowns": [{"field": "authority.approver", "reason": "none"}],
    }


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "vault"
        (self.root / "p").mkdir(parents=True)
        (self.root / "p" / "Note.md").write_bytes(NOTE)
        (Path(self.tmp.name) / "outside.md").write_bytes(b"secret\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_span_convention_keeps_cr_and_drops_final_lf(self):
        self.assertEqual(span_bytes(NOTE, 6, 7), b"Objective: test the verifier.\r\nBlocker: none.\r")
        with self.assertRaises(SourceError):
            span_bytes(NOTE, 0, 1)
        with self.assertRaises(SourceError):
            span_bytes(NOTE, 7, 99)

    def test_valid_receipt(self):
        it = item(self.root, "p/Note.md", 6, 6)
        self.assertEqual(it["text"], "Objective: test the verifier.")
        self.assertEqual(validate_receipt(it["receipt"], self.root), (True, "ok"))

    def test_corrupted_sha_fails(self):
        it = item(self.root, "p/Note.md", 6, 6)
        it["receipt"]["content_sha"] = "f" * 64
        self.assertFalse(validate_receipt(it["receipt"], self.root)[0])

    def test_cited_bytes_must_match(self):
        it = item(self.root, "p/Note.md", 6, 6)
        ok, why = validate_receipt(it["receipt"], self.root, b"something else")
        self.assertFalse(ok)
        self.assertIn("cited", why)

    def test_shifted_span_fails(self):
        it = item(self.root, "p/Note.md", 6, 6)
        it["receipt"]["span"] = [7, 7]
        self.assertFalse(validate_receipt(it["receipt"], self.root)[0])

    def test_missing_source_and_missing_keys(self):
        r = make_receipt("p/Absent.md", 1, 1, b"x", "g", "t")
        self.assertFalse(validate_receipt(r, self.root)[0])
        self.assertFalse(validate_receipt({"source": "p/Note.md"}, self.root)[0])

    def test_traversal_rejected(self):
        for loc in ("../outside.md", "p/../../outside.md", "/p/Note.md", "C:/p/Note.md", "p\\Note.md", "", "./p/Note.md"):
            with self.subTest(loc=loc), self.assertRaises(SourceError):
                safe_resolve(self.root, loc)

    def test_link_escape_rejected(self):
        link = self.root / "p" / "link.md"
        try:
            os.symlink(Path(self.tmp.name) / "outside.md", link)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted on this host")
        with self.assertRaises(SourceError):
            safe_resolve(self.root, "p/link.md")

    @unittest.skipUnless(sys.platform == "win32", "junctions are Windows-only")
    def test_junction_escape_rejected(self):
        import _winapi
        _winapi.CreateJunction(str(Path(self.tmp.name)), str(self.root / "p" / "junction"))
        self.assertTrue((self.root / "p" / "junction" / "outside.md").exists())
        with self.assertRaises(SourceError):
            safe_resolve(self.root, "p/junction/outside.md")


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "p").mkdir()
        (self.root / "p" / "Note.md").write_bytes(NOTE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_revalidate_corrupted_receipt_yields_unknown_and_conflict(self):
        p = sample_packet(self.root)
        p["fields"]["objective"]["items"][0]["receipt"]["content_sha"] = "0" * 64
        out = pk.revalidate(p, self.root)
        self.assertEqual(out["fields"]["objective"]["status"], "unknown")
        self.assertIn({"field": "fields.objective", "reason": "receipt failed validation"}, out["unknowns"])
        self.assertTrue(any(c["field"] == "fields.objective" and c["kind"] == "receipt_validation_failed"
                            for c in out["conflicts"]))
        self.assertEqual(p["fields"]["objective"]["status"], "established", "input must not be mutated")

    def test_revalidate_text_tamper(self):
        p = sample_packet(self.root)
        p["fields"]["objective"]["items"][0]["text"] = "Objective: deploy now."
        self.assertEqual(pk.revalidate(p, self.root)["fields"]["objective"]["status"], "unknown")
        self.assertEqual(len(pk.unsupported_assertions(p, self.root)), 1)

    def test_clean_packet_has_no_unsupported_assertions(self):
        p = sample_packet(self.root, hits=2)
        self.assertEqual(pk.unsupported_assertions(p, self.root), [])
        self.assertEqual(pk.revalidate(p, self.root), p)

    def test_bound_within_limit_untouched(self):
        p = pk.bound(sample_packet(self.root, hits=2), 4000)
        self.assertFalse(p["budget"]["truncated"])
        self.assertTrue(p["budget"]["within_limit"])
        self.assertEqual(p["budget"]["tokens"], pk.estimate_tokens(p))
        self.assertEqual(p["budget"]["tokenizer"], pk.TOKENIZER)

    def test_bound_trims_hits_first_and_counts(self):
        full = sample_packet(self.root, hits=12)
        limit = pk.estimate_tokens(full) - 300
        p = pk.bound(copy.deepcopy(full), limit)
        self.assertTrue(p["budget"]["truncated"])
        self.assertTrue(p["budget"]["within_limit"])
        self.assertLessEqual(p["budget"]["tokens"], limit)
        self.assertGreater(p["budget"]["omitted"]["query_hits"], 0)
        self.assertEqual(p["budget"]["omitted"]["other_decisions"], 0)
        self.assertEqual(len(p["query_hits"]) + p["budget"]["omitted"]["query_hits"], 12)
        self.assertEqual([h["rank"] for h in p["query_hits"]], list(range(len(p["query_hits"]))),
                         "lowest-ranked hits are dropped first")

    def test_bound_never_drops_conflicts_unknowns_or_fields(self):
        full = sample_packet(self.root, hits=5)
        p = pk.bound(copy.deepcopy(full), 10)
        self.assertFalse(p["budget"]["within_limit"])
        self.assertEqual(p["conflicts"], full["conflicts"])
        self.assertEqual(p["unknowns"], full["unknowns"])
        self.assertEqual(p["fields"]["objective"], full["fields"]["objective"])
        self.assertEqual(p["budget"]["omitted"], {"query_hits": 5, "other_decisions": 3})

    def test_canonical_ignores_wall_clock(self):
        a = sample_packet(self.root)
        b = copy.deepcopy(a)
        b["fields"]["objective"]["items"][0]["receipt"]["observed_at"] = "later"
        b["assembled_at"] = "later"
        self.assertEqual(pk.digest(a), pk.digest(b))
        self.assertEqual(pk.ordered_receipts(a), pk.ordered_receipts(b))
        b["fields"]["objective"]["items"][0]["receipt"]["span"] = [5, 5]
        self.assertNotEqual(pk.digest(a), pk.digest(b))


class ReadOnlySurfaceTests(unittest.TestCase):
    def test_allowlist_is_the_four_read_tools(self):
        self.assertEqual(qmd_client.ALLOWED_TOOLS, {"query", "get", "multi_get", "status"})

    def test_session_refuses_other_tools_before_any_call(self):
        s = qmd_client.McpSession(Path(tempfile.gettempdir()))
        for name in ("write", "edit", "delete", "move", "shell", "update", "embed"):
            with self.subTest(name=name), self.assertRaises(qmd_client.QmdError):
                s.call_tool(name, {})
        self.assertEqual(s.calls, [])

    def test_index_cli_allowlist(self):
        for args in (["collection", "remove", "atlas"], ["embed"], ["mcp"], ["cleanup"], []):
            with self.subTest(args=args), self.assertRaises(qmd_client.QmdError):
                qmd_client.index_cli(Path(tempfile.gettempdir()), args)


if __name__ == "__main__":
    unittest.main()
