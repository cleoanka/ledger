"""Runner behaviour against a local fixture repo (file://), no network."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent
RUNNER = LEDGER / "runner" / "ledger_run.py"
DATE = "2026-11-26"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def make_claim(cid, command, *, status="standing", cls="nightly", value=0.95, comparator="approx",
               tolerance=0.01, adapter="json_select", result_path="r.json", key="v", budget=1, commit=None):
    return {
        "id": cid, "project": "zeno", "lab_page": "/lab/zeno/",
        "sentence": {"tr": "t", "en": "e"}, "value": value, "display": {"tr": "t", "en": "e"},
        "unit": {"tr": "t", "en": "e"}, "comparator": comparator, "tolerance": tolerance,
        "conditions": {"tr": "t", "en": "e"}, "repo": "github.com/cleoanka/fixture", "commit": commit,
        "setup": "", "command": command, "result_path": result_path, "result_key": key, "adapter": adapter,
        "rerun": {"class": cls, "budget_min": budget, "runs_on": "ubuntu-24.04"}, "status": status,
        "history": [{"date": "2026-11-01", "status": status, "reason": {"tr": "t", "en": "e"}, "by": "cleoanka"}],
        "head_check": cls == "nightly", "refutations": [], "sources": ["zeno@493eed8:README.md"],
    }


class Runner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repos = t / "repos"
        repo = self.repos / "fixture"
        repo.mkdir(parents=True)
        git(repo, "init", "-q", "-b", "main")
        git(repo, "config", "user.email", "fixture@example.invalid")
        git(repo, "config", "user.name", "fixture")
        (repo / "value.txt").write_text("0.95\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "fixture")
        self.commit = git(repo, "rev-parse", "HEAD")
        self.root = t / "ledger"
        (self.root / "claims").mkdir(parents=True)
        self.work = t / "work"
        self.mark = t / "mark.txt"
        self.env = dict(os.environ, LEDGER_GIT_BASE=f"file://{self.repos}", LEDGER_TEST_MARK=str(self.mark))
        self.env.pop("GITHUB_ACTIONS", None)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, claim):
        claim["commit"] = claim["commit"] or self.commit
        (self.root / "claims" / f"{claim['id']}.json").write_text(json.dumps(claim, indent=2) + "\n")

    def run_ledger(self, *args, check=True):
        p = subprocess.run([sys.executable, str(RUNNER), "--root", str(self.root), "--workdir", str(self.work),
                            "--date", DATE, "--runner-label", "local:test", *args],
                           env=self.env, capture_output=True, text=True, timeout=120)
        if check and p.returncode not in (0, 1):
            self.fail(p.stdout + p.stderr)
        return p

    def read(self, rel):
        return json.loads((self.root / rel).read_text())

    VALUE_CMD = 'printf \'{"v": %s}\' "$(cat value.txt)" > r.json'

    def test_pass_writes_run_and_status(self):
        self.put(make_claim("zeno-901", self.VALUE_CMD))
        self.run_ledger("--class", "nightly")
        rec = self.read(f"runs/zeno-901/{DATE}.json")
        self.assertEqual(rec["value"], 0.95)
        self.assertTrue(rec["passed"])
        self.assertEqual(rec["exit_code"], 0)
        self.assertEqual(rec["target"], "pinned")
        self.assertEqual(rec["commit"], self.commit)
        self.assertEqual(rec["runner"], "local:test")
        self.assertIsNone(rec["error"])
        for k in ("id", "date", "command", "duration_s", "guards", "stdout_tail"):
            self.assertIn(k, rec)
        st = self.read("status/zeno-901.json")
        self.assertEqual(st["status"], "standing")
        self.assertEqual(st["last_verified"], DATE)
        self.assertEqual(st["last_run"]["path"], f"runs/zeno-901/{DATE}.json")
        self.assertNotIn("command", st["last_run"])
        self.assertNotIn("stdout_tail", st["last_run"])
        self.assertIsNone(st["head_last_run"])
        self.assertEqual(set(st), {"id", "status", "last_verified", "last_run", "head_last_run", "ledger_commit", "updated"})

    def test_fail_flips_to_drifting_and_back(self):
        self.put(make_claim("zeno-901", 'printf \'{"v": 0.5}\' > r.json'))
        p = self.run_ledger("--class", "nightly")
        self.assertEqual(p.returncode, 1)
        claim = self.read("claims/zeno-901.json")
        self.assertEqual(claim["status"], "drifting")
        self.assertEqual(claim["history"][-1]["by"], "ci")
        self.assertEqual(claim["history"][-1]["status"], "drifting")
        self.assertEqual(self.read("status/zeno-901.json")["status"], "drifting")
        claim["command"] = self.VALUE_CMD
        (self.root / "claims" / "zeno-901.json").write_text(json.dumps(claim, indent=2) + "\n")
        self.run_ledger("--class", "nightly", "--date", "2026-11-27")
        claim = self.read("claims/zeno-901.json")
        self.assertEqual(claim["status"], "standing")
        self.assertEqual([h["status"] for h in claim["history"]], ["standing", "drifting", "standing"])
        self.assertEqual(claim["history"][-1]["date"], "2026-11-27")

    def test_never_touches_refuted(self):
        for st in ("refuted", "weakened", "retracted"):
            self.put(make_claim(f"zeno-9{len(st)}1", 'printf \'{"v": 0.1}\' > r.json', status=st))
        self.run_ledger("--class", "nightly")
        for p in (self.root / "claims").glob("*.json"):
            c = json.loads(p.read_text())
            self.assertIn(c["status"], ("refuted", "weakened", "retracted"))
            self.assertEqual(len(c["history"]), 1)

    def test_manual_status_only_gets_last_verified(self):
        self.put(make_claim("zeno-901", self.VALUE_CMD, status="manual"))
        self.run_ledger("--class", "nightly")
        self.assertEqual(self.read("claims/zeno-901.json")["status"], "manual")
        st = self.read("status/zeno-901.json")
        self.assertEqual((st["status"], st["last_verified"]), ("manual", DATE))

    def test_dedupes_shared_command(self):
        cmd = 'echo run >> "$LEDGER_TEST_MARK"; ' + self.VALUE_CMD
        self.put(make_claim("zeno-901", cmd))
        self.put(make_claim("zeno-902", cmd, value=0.95, comparator="le", tolerance=1))
        self.run_ledger("--class", "nightly")
        self.assertEqual(self.mark.read_text().count("run"), 1)
        self.assertTrue(self.read(f"runs/zeno-901/{DATE}.json")["passed"])
        self.assertTrue(self.read(f"runs/zeno-902/{DATE}.json")["passed"])

    def test_timeout_marks_error(self):
        self.put(make_claim("zeno-901", "sleep 30", budget=1))
        p = self.run_ledger("--claim", "zeno-901", "--budget-scale", "0.02")
        self.assertEqual(p.returncode, 1)
        rec = self.read(f"runs/zeno-901/{DATE}.json")
        self.assertFalse(rec["passed"])
        self.assertIn("timeout", rec["error"])
        self.assertIsNone(rec["exit_code"])
        self.assertLess(rec["duration_s"], 10)
        self.assertEqual(self.read("claims/zeno-901.json")["status"], "drifting")

    def test_record_has_no_home_path(self):
        home = os.path.expanduser("~")
        self.put(make_claim("zeno-901", f'echo "{home}/x and $PWD"; ' + self.VALUE_CMD))
        self.run_ledger("--class", "nightly")
        rec = self.read(f"runs/zeno-901/{DATE}.json")
        self.assertIn("~/x", rec["stdout_tail"])
        self.assertNotIn(home, rec["command"])
        for p in [*(self.root / "runs").rglob("*.json"), *(self.root / "status").rglob("*.json")]:
            text = p.read_text()
            self.assertNotIn("/Users/", text, p)
            self.assertNotIn(home, text, p)
            self.assertNotIn(str(self.work), text, p)

    def test_assign_initial_only_on_pass(self):
        self.put(make_claim("zeno-901", self.VALUE_CMD, status="manual"))
        self.put(make_claim("zeno-902", 'printf \'{"v": 0.1}\' > r.json', status="manual"))
        self.put(make_claim("zeno-903", self.VALUE_CMD, status="manual", cls="manual"))
        self.run_ledger("--claim", "zeno-901", "--claim", "zeno-902", "--claim", "zeno-903", "--assign-initial")
        a, b, c = (self.read(f"claims/zeno-90{i}.json") for i in (1, 2, 3))
        self.assertEqual(a["status"], "standing")
        self.assertEqual(a["history"][-1]["by"], "cleoanka")
        self.assertEqual(b["status"], "manual")
        self.assertEqual(c["status"], "manual")  # manual-class claims stay manual

    def test_head_run_never_changes_status(self):
        self.put(make_claim("zeno-901", 'printf \'{"v": 0.1}\' > r.json'))
        self.run_ledger("--class", "nightly", "--head-only")
        self.assertEqual(self.read("claims/zeno-901.json")["status"], "standing")
        self.assertFalse((self.root / "runs" / "zeno-901" / f"{DATE}.json").exists())
        rec = self.read(f"runs/zeno-901/{DATE}-head.json")
        self.assertEqual(rec["target"], "head")
        st = self.read("status/zeno-901.json")
        self.assertEqual(st["head_last_run"]["path"], f"runs/zeno-901/{DATE}-head.json")
        self.assertFalse(st["head_last_run"]["passed"])

    def test_runs_are_append_only(self):
        self.put(make_claim("zeno-901", self.VALUE_CMD))
        self.run_ledger("--claim", "zeno-901")
        self.run_ledger("--claim", "zeno-901")
        names = sorted(p.name for p in (self.root / "runs" / "zeno-901").iterdir())
        self.assertEqual(names, [f"{DATE}-2.json", f"{DATE}.json"])
        self.assertEqual(self.read("status/zeno-901.json")["last_run"]["path"], f"runs/zeno-901/{DATE}-2.json")

    def test_dry_run_writes_nothing(self):
        self.put(make_claim("zeno-901", 'echo run >> "$LEDGER_TEST_MARK"'))
        p = self.run_ledger("--class", "nightly", "--dry-run", check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("zeno-901", p.stdout)
        self.assertFalse(self.mark.exists())
        self.assertFalse((self.root / "runs").exists())

    def test_status_file_for_every_claim(self):
        self.put(make_claim("zeno-901", self.VALUE_CMD, cls="weekly"))
        self.put(make_claim("zeno-902", self.VALUE_CMD, status="manual", cls="manual"))
        self.run_ledger("--class", "nightly")  # selects nothing, still syncs status files
        self.assertEqual(self.read("status/zeno-902.json")["status"], "manual")
        self.assertIsNone(self.read("status/zeno-902.json")["last_run"])
        self.assertEqual(self.read("status/zeno-901.json")["status"], "standing")

    def test_runs_on_filter(self):
        c = make_claim("zeno-901", 'echo run >> "$LEDGER_TEST_MARK"; ' + self.VALUE_CMD)
        c["rerun"]["runs_on"] = "macos-14"
        self.put(c)
        self.run_ledger("--class", "nightly", "--runs-on", "ubuntu-24.04")
        self.assertFalse(self.mark.exists())


if __name__ == "__main__":
    unittest.main()
