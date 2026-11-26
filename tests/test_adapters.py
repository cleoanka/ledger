import json
import tempfile
import unittest
from pathlib import Path

from ledger.adapters import extract
from ledger.compare import check_guards

FIX = Path(__file__).parent / "fixtures"


class Adapters(unittest.TestCase):
    def test_json_select_rows_and_dotted(self):
        f = FIX / "atlas_results.json"
        self.assertAlmostEqual(extract("json_select", f, "rows[name=contrastive].diffusion", ""), 0.9468616666666667)
        self.assertAlmostEqual(extract("json_select", f, "rows[name=raw].diffusion", ""), 0.7135349999999999)
        self.assertEqual(extract("json_select", f, "config.k", ""), 10.0)

    def test_json_select_filter_min_and_scale(self):
        f = FIX / "e5_rows.json"
        self.assertEqual(extract("json_select", f, "min([case=b,track=3].err)", ""), 1e-15)
        self.assertEqual(extract("json_select", f, "max([case=b].err)", ""), 1e-6)
        self.assertAlmostEqual(extract("json_select", FIX / "zeno_bench.json", "results[qubits=26].sim_time_ms*0.001", ""), 0.951)

    def test_json_select_errors(self):
        f = FIX / "atlas_results.json"
        for key in ("rows[name=nope].diffusion", "config.missing", "rows.diffusion", "rows[name=raw].label"):
            with self.assertRaises(ValueError, msg=key):
                extract("json_select", f, key, "")
        with self.assertRaises(ValueError):  # ambiguous filter without an aggregate
            extract("json_select", FIX / "e5_rows.json", "[case=b].err", "")

    def test_md_table_turkish_header_and_markup(self):
        f = FIX / "results.md"
        self.assertEqual(extract("md_table", f, "Permuted-digits|BWT|bölgesel (CAS)", ""), 0.0)
        self.assertEqual(extract("md_table", f, "Permuted-digits|BWT|ablasyon (naive-SGD)", ""), -0.657)
        self.assertEqual(extract("md_table", f, "Split-digits|BWT|bölgesel (CAS)", ""), -0.608)
        with self.assertRaises(ValueError):
            extract("md_table", f, "Permuted-digits|nope|bölgesel (CAS)", "")

    def test_junit_failures_counts_errors(self):
        self.assertEqual(extract("junit_failures", FIX / "junit_one_error.xml", "failures", ""), 1.0)
        self.assertEqual(extract("junit_failures", FIX / "junit_pass.xml", "failures", ""), 0.0)
        self.assertEqual(extract("junit_failures", FIX / "junit_node.xml", "failures", ""), 2.0)

    def test_junit_without_tests_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "empty.xml"
            p.write_text('<?xml version="1.0"?><testsuites></testsuites>')
            with self.assertRaises(ValueError):
                extract("junit_failures", p, "failures", "")

    def test_zeno_counts(self):
        self.assertAlmostEqual(extract("zeno_counts", FIX / "zeno_run.json", "101", ""), 0.94512)

    def test_stdout_regex(self):
        out = "  ✓  Beats naive-long on RANGE         5/5 seeds\n"
        self.assertEqual(extract("stdout_regex", None, r"Beats naive-long on RANGE\s+(\d+)/\d+ seeds", out), 5.0)
        out2 = "=== digits-perm10 (n=5 seed) ===\n  REGIONAL  A_N=0.865±0.032  BWT=-0.000±0.001  n_reg=10.2±0.4\n"
        key = json.loads((Path(__file__).parent.parent / "claims" / "aura-mind-003.json").read_text(encoding="utf-8"))["result_key"]
        self.assertEqual(extract("stdout_regex", None, key, out2), 0.0)
        with self.assertRaises(ValueError):
            extract("stdout_regex", None, r"nothing (\d+)", out)

    def test_unknown_adapter(self):
        with self.assertRaises(ValueError):
            extract("csv", None, "x", "")

    def test_guards(self):
        claim = {"adapter": "json_select", "guards": [
            {"key": "control.leak_steps", "comparator": "ge", "tolerance": 1},
            {"key": "control.missing", "comparator": "ge", "tolerance": 1}]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps({"control": {"leak_steps": 280}}))
            g = check_guards(p, claim)
        self.assertEqual(g[0], {"key": "control.leak_steps", "value": 280.0, "passed": True})
        self.assertEqual(g[1]["passed"], False)
        self.assertIsNone(g[1]["value"])

    def test_no_guards(self):
        self.assertEqual(check_guards(None, {"adapter": "json_select"}), [])


if __name__ == "__main__":
    unittest.main()
