import json
import os
import unittest
from pathlib import Path

from ledger.schema import load_claims, validate_claim

ROOT = Path(__file__).resolve().parent.parent
LOCKED = {
    "atlas-001": (0.947, "approx", 0.005, "nightly"),
    "atlas-002": (0.714, "approx", 0.005, "weekly"),
    "atlas-003": (0.62, "approx", 0.01, "manual"),
    "aura-mind-001": (0.0, "approx", 0.005, "weekly"),
    "aura-mind-002": (0, "eq", 0, "nightly"),
    "aura-mind-003": (0.0, "approx", 0.002, "manual"),
    "volterra-001": (9e-16, "le", 1e-14, "nightly"),
    "volterra-002": (1e-15, "le", 1e-14, "manual"),
    "zeno-001": (0.945, "approx", 0.005, "nightly"),
    "zeno-002": (0.95, "approx", 0.15, "manual"),
    "unscratchable-001": (0, "eq", 0, "nightly"),
    "kairos-001": (0, "eq", 0, "weekly"),
    "kairos-002": (5, "eq", 0, "weekly"),
}
SNAPSHOT_ONLY = {"last_verified", "last_run", "head_last_run", "runs"}


class Claims(unittest.TestCase):
    def setUp(self):
        self.claims = load_claims(ROOT / "claims")

    def test_every_claim_validates(self):
        for cid, c in self.claims.items():
            self.assertEqual(validate_claim(c), [], cid)
            self.assertEqual((ROOT / "claims" / f"{cid}.json").name, f"{c['id']}.json")

    def test_locked_ids_and_values(self):
        self.assertEqual(set(self.claims), set(LOCKED))
        for cid, (value, comp, tol, cls) in LOCKED.items():
            c = self.claims[cid]
            self.assertEqual((c["value"], c["comparator"], c["tolerance"], c["rerun"]["class"]),
                             (value, comp, tol, cls), cid)
            self.assertEqual(c["head_check"], cls == "nightly", cid)

    def test_validator_rejects_bad_input(self):
        c = dict(self.claims["atlas-001"])
        c["status"] = "zombie"
        c["commit"] = "a" * 39
        msgs = validate_claim(c)
        self.assertTrue(any("atlas-001" in m and "status" in m for m in msgs), msgs)
        self.assertTrue(any("commit" in m for m in msgs), msgs)
        c = dict(self.claims["atlas-001"]); c["comparator"] = "eq"; c["tolerance"] = 1
        self.assertTrue(any("tolerance" in m for m in validate_claim(c)))
        c = dict(self.claims["atlas-001"]); c.pop("sources")
        self.assertTrue(any("sources" in m for m in validate_claim(c)))
        c = dict(self.claims["atlas-001"]); c["surprise"] = 1
        self.assertTrue(any("surprise" in m for m in validate_claim(c)))

    def test_schema_file_lists_the_same_required_fields(self):
        schema = json.loads((ROOT / "schema" / "claim.schema.json").read_text(encoding="utf-8"))
        from ledger import schema as S
        self.assertEqual(sorted(schema["required"]), sorted(S.REQUIRED))
        self.assertEqual(schema["$defs"]["status"]["enum"], list(S.STATUSES))

    @unittest.skipUnless(os.environ.get("LEDGER_SITE_SNAPSHOT"), "set LEDGER_SITE_SNAPSHOT to compare with the site copy")
    def test_matches_site_snapshot(self):
        snap = json.loads(Path(os.environ["LEDGER_SITE_SNAPSHOT"]).read_text(encoding="utf-8"))
        site = {c["id"]: {k: v for k, v in c.items() if k not in SNAPSHOT_ONLY} for c in snap["claims"]}
        self.assertEqual(set(site), set(self.claims))
        for cid, c in self.claims.items():
            self.assertEqual(c, site[cid], cid)


if __name__ == "__main__":
    unittest.main()
