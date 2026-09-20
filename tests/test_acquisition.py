"""Guard against incomplete registry downloads and undetected raw-data changes."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _common

spec = importlib.util.spec_from_file_location("get_trials", Path(_common.ROOT) / "scripts/02_get_trials.py")
trials = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trials)


def study(nct_id):
    return {"protocolSection": {"identificationModule": {"nctId": nct_id}}}


class TrialPaginationTests(unittest.TestCase):
    def test_follows_tokens_and_keeps_filters(self):
        calls = []

        def fetch(url):
            params = parse_qs(urlparse(url).query)
            calls.append(params)
            if "pageToken" not in params:
                return json.dumps({"totalCount": 2, "studies": [study("NCT00000001")],
                                   "nextPageToken": "a token + /"}).encode()
            self.assertEqual(params["pageToken"], ["a token + /"])
            return json.dumps({"studies": [study("NCT00000002")]}).encode()

        snapshot, pages = trials.download_studies(fetch)
        self.assertEqual(pages, 2)
        self.assertEqual(len(snapshot["studies"]), 2)
        for params in calls:
            self.assertEqual(params["filter.advanced"], [trials.PARAMS["filter.advanced"]])

    def test_rejects_incomplete_response(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            trials.download_studies(lambda _: json.dumps({"totalCount": 2, "studies": [study("NCT00000001")]}))

    def test_rejects_duplicate_studies(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            trials.download_studies(lambda _: json.dumps({"totalCount": 2, "studies": [study("NCT00000001")] * 2}))

    def test_rejects_repeated_token(self):
        with self.assertRaisesRegex(ValueError, "repeated"):
            trials.download_studies(lambda _: json.dumps({"totalCount": 3, "studies": [study("NCT00000001")],
                                                          "nextPageToken": "again"}))

    def test_rejects_changing_total(self):
        pages = iter([{"totalCount": 2, "studies": [study("NCT00000001")], "nextPageToken": "next"},
                      {"totalCount": 3, "studies": [study("NCT00000002")]}])
        with self.assertRaisesRegex(ValueError, "count changed"):
            trials.download_studies(lambda _: json.dumps(next(pages)))


class SnapshotTests(unittest.TestCase):
    def test_cache_detects_mutation_and_preserves_other_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(_common, "RAW", root), patch.object(_common, "MANIFEST", root / "manifest.json"):
                _common.save_snapshot("one", {"one.csv": b"fips\n01001\n"}, {"source_url": "test"})
                _common.save_snapshot("two", {"two.json": b"[]\n"}, {"source_url": "test"})
                self.assertEqual(set(_common.read_manifest()["sources"]), {"one", "two"})
                self.assertTrue(_common.use_cached("one", False))
                (root / "one.csv").write_bytes(b"fips\n1001\n")
                with self.assertRaisesRegex(ValueError, "modified snapshot"):
                    _common.use_cached("one", False)
                self.assertFalse(_common.use_cached("one", True))


if __name__ == "__main__":
    unittest.main()
