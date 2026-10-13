"""Opt-in actual-QMD integration for the Librarian preparation seam.

The caller refreshes the committed synthetic fixture index first, then sets
``PROJECT_RECOVERY_QMD_INTEGRATION=1``.  No model, network, or live GitHub is used.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "skills" / "project-recovery" / "scripts"))

import librarian  # noqa: E402
import recipe  # noqa: E402
from qmd_client import McpSession  # noqa: E402


def proposal() -> bytes:
    return json.dumps({
        "queries": ["Atlas project"],
        "claims": {name: None for name in librarian.CLAIM_FIELDS},
    }).encode("utf-8")


class DropFirstQuerySession:
    """Still queries actual QMD, then supplies a conflicting fresh requery result."""

    def __init__(self, state_dir):
        self.inner = McpSession(state_dir)

    def __enter__(self):
        self.inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self.inner.__exit__(*exc)

    def query(self, *args, **kwargs):
        return self.inner.query(*args, **kwargs)[1:]

    def get(self, *args, **kwargs):
        return self.inner.get(*args, **kwargs)

    def multi_get(self, *args, **kwargs):
        return self.inner.multi_get(*args, **kwargs)


@unittest.skipUnless(os.environ.get("PROJECT_RECOVERY_QMD_INTEGRATION") == "1",
                     "set PROJECT_RECOVERY_QMD_INTEGRATION=1 after refreshing the fixture index")
class LibrarianQmdIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = recipe.load_manifest(REPO / "manifest" / "fixture-vault.json")

    def test_actual_qmd_positive_returns_rederived_packet(self):
        result = librarian.prepare(self.m, "atlas", proposal(), transport="offline", max_tokens=10 ** 6)
        self.assertEqual(result["status"], "prepared", result["results"])
        self.assertEqual(result["results"][0]["status"], "validated")
        self.assertEqual((result["packets"][0]["status"], result["packets"][0]["project"]),
                         ("complete", "atlas"))
        self.assertGreater(len(result["packets"][0]["query_hits"]), 0)

    def test_actual_qmd_requery_difference_returns_no_packet(self):
        result = librarian.prepare(
            self.m, "atlas", proposal(), transport="offline", max_tokens=10 ** 6,
            validation_session_factory=lambda _q: DropFirstQuerySession(self.m.state_dir),
        )
        self.assertEqual((result["status"], result["packets"]), ("rejected", []))
        self.assertEqual((result["results"][0]["status"], result["results"][0]["packet"]),
                         ("rejected", None))


if __name__ == "__main__":
    unittest.main()
