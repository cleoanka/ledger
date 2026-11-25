#!/usr/bin/env python3
"""Re-run ledger claims and record the result.

    python3 runner/ledger_run.py --class nightly [--runs-on ubuntu-24.04] [--head]
    python3 runner/ledger_run.py --claim zeno-001 [--claim atlas-001] [--assign-initial]
    python3 runner/ledger_run.py --class weekly --dry-run

For each selected claim the runner fetches the claim's repo at the pinned commit (or, with --head,
at the default branch's latest commit), runs `setup` and `command` in a fresh work directory with
`budget_min` as a hard timeout, reads the number with the claim's adapter and compares it with the
pass rule. Claims that share (repo, commit, setup, command) run once.

Writes, under --root (default: this checkout):
  runs/<id>/<date>[-head][-N].json   one record per run, never overwritten
  status/<id>.json                   current status and the last run summaries (for every claim)
  claims/<id>.json                   only when the status changes (history is append-only)

Status rules: CI only switches standing <-> drifting; weakened, refuted and retracted are never
touched; a manual claim only gets last_verified; --assign-initial (owner only) moves a manual
nightly/weekly claim to standing on a passing pinned run. HEAD runs never change the status.
Exit code: 0 when every pinned run passed, 1 when any failed, 2 on a usage or ledger error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LEDGER))

from ledger.adapters import extract  # noqa: E402
from ledger.compare import check_guards, within  # noqa: E402
from ledger.schema import load_claims, validate_claim  # noqa: E402

TAIL = 2000
HOME = os.path.expanduser("~")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def runner_label(explicit: str | None) -> str:
    if explicit:
        return explicit
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github-actions:" + os.environ.get("LEDGER_RUNS_ON", platform.system().lower())
    if os.environ.get("LEDGER_RUNNER"):
        return os.environ["LEDGER_RUNNER"]
    name = platform.machine()
    if sys.platform == "darwin":
        try:
            name = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True,
                                  text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            pass
    return "local:" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "machine")


def repo_url(claim: dict) -> str:
    base = os.environ.get("LEDGER_GIT_BASE")
    if base:
        return base.rstrip("/") + "/" + claim["repo"].rsplit("/", 1)[1]
    return "https://" + claim["repo"]


def git(*args, cwd=None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def head_commit(url: str) -> str:
    line = git("ls-remote", url, "HEAD").split("\n")[0]
    sha = line.split()[0] if line else ""
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError(f"cannot resolve HEAD of {url}")
    return sha


class Scrubber:
    """Replace machine paths in anything written to the ledger."""

    def __init__(self, work: Path, root: Path):
        self.pairs = []
        for path, label in ((work, "$WORK"), (root, "$LEDGER"), (LEDGER, "$LEDGER"),
                            (Path(os.environ.get("TMPDIR", "/nonexistent")), "$TMPDIR"), (Path(HOME), "~")):
            for p in {str(path), str(path.resolve()) if path.exists() else str(path)}:
                if len(p) > 1:
                    self.pairs.append((p.rstrip("/"), label))
        self.pairs.sort(key=lambda x: -len(x[0]))

    def __call__(self, text: str) -> str:
        for p, label in self.pairs:
            text = text.replace(p, label)
        return re.sub(r"/(?:Users|home)/[^/\s]+", "~", text)


def run_shell(cmd: str, cwd: Path, env: dict, deadline: float) -> tuple[int | None, str, str, bool]:
    """Run cmd in bash; returns (exit_code or None on timeout, stdout, combined tail, timed_out)."""
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None, "", "", True
    proc = subprocess.Popen(["bash", "-c", cmd], cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, errors="replace", start_new_session=True)
    try:
        out, err = proc.communicate(timeout=remaining)
        return proc.returncode, out, (out + err), False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        out, err = proc.communicate()
        return None, out or "", (out or "") + (err or ""), True


def needs_python(claim: dict) -> bool:
    return bool(re.search(r"\bpip\b", claim["setup"]) or re.search(r"\bpython3?\b", claim["command"]))


def execute(group: list[dict], target: str, commit: str, work: Path, args) -> dict:
    """Fetch, set up and run one (repo, commit, setup, command) group once."""
    first = group[0]
    budget_s = min(c["rerun"]["budget_min"] for c in group) * 60 * args.budget_scale
    tag = hashlib.sha256(f"{first['repo']}|{commit}|{first['setup']}|{first['command']}".encode()).hexdigest()[:8]
    gdir = work / f"{first['repo'].rsplit('/', 1)[1]}-{commit[:7]}-{target}-{tag}"
    if gdir.exists():
        shutil.rmtree(gdir)
    src = gdir / "src"
    src.mkdir(parents=True)
    env = dict(os.environ)
    env.update({
        "LEDGER": str(LEDGER), "PIP_CACHE_DIR": str(gdir / "cache" / "pip"),
        "XDG_CACHE_HOME": str(gdir / "cache"), "MPLCONFIGDIR": str(gdir / "cache" / "mpl"),
        "SCIKIT_LEARN_DATA": str(gdir / "cache" / "sklearn"), "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "Agg", "NO_COLOR": "1",
    })
    t0 = time.monotonic()
    deadline = t0 + budget_s
    result = {"exit_code": None, "stdout": "", "tail": "", "error": None, "src": src, "gdir": gdir}
    try:
        git("init", "-q", cwd=src)
        git("fetch", "-q", "--depth", "1", repo_url(first), commit, cwd=src)
        git("checkout", "-q", "FETCH_HEAD", cwd=src)
        if needs_python(first):
            subprocess.run([args.python, "-m", "venv", str(gdir / "venv")], check=True, capture_output=True)
            env["VIRTUAL_ENV"] = str(gdir / "venv")
            env["PATH"] = str(gdir / "venv" / "bin") + os.pathsep + env["PATH"]
        logs = ""
        if first["setup"]:
            code, _, tail, timed_out = run_shell(first["setup"], src, env, deadline)
            logs += tail
            if timed_out:
                result["error"] = f"timeout after {budget_s / 60:g} min (setup)"
            elif code != 0:
                result.update(exit_code=code, error=f"setup failed with exit code {code}")
        if result["error"] is None:
            code, out, tail, timed_out = run_shell(first["command"], src, env, deadline)
            logs += tail
            result["stdout"] = out
            if timed_out:
                result["error"] = f"timeout after {budget_s / 60:g} min"
            else:
                result["exit_code"] = code
                if code != 0:
                    result["error"] = f"command exited with code {code}"
        result["tail"] = logs
    except (subprocess.CalledProcessError, OSError, RuntimeError) as e:
        detail = getattr(e, "stderr", "") or ""
        result["error"] = f"checkout or environment failed: {e.__class__.__name__}: {str(detail)[-300:] or e}"
    result["duration_s"] = round(time.monotonic() - t0, 1)
    return result


def measure(claim: dict, res: dict) -> tuple[float | None, list[dict], str | None]:
    if res["error"] and res["exit_code"] is None:
        return None, [], res["error"]
    rfile = (res["src"] / claim["result_path"]) if claim["result_path"] else None
    try:
        value = extract(claim["adapter"], rfile, claim["result_key"], res["stdout"])
    except (ValueError, OSError) as e:
        return None, check_guards(rfile, claim, res["stdout"]) if rfile else [], res["error"] or f"result: {e}"
    return value, check_guards(rfile, claim, res["stdout"]), res["error"]


def record_path(root: Path, cid: str, date: str, target: str) -> Path:
    d = root / "runs" / cid
    stem = date + ("-head" if target == "head" else "")
    p, n = d / f"{stem}.json", 2
    while p.exists():
        p, n = d / f"{stem}-{n}.json", n + 1
    return p


def summary(rec: dict, path: str) -> dict:
    s = {k: v for k, v in rec.items() if k not in ("command", "stdout_tail")}
    s["path"] = path
    return s


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def ledger_commit(root: Path) -> str | None:
    try:
        sha = git("rev-parse", "HEAD", cwd=root)
        return sha if re.fullmatch(r"[0-9a-f]{40}", sha) else None
    except (subprocess.CalledProcessError, OSError):
        return None


REASONS = {
    "drifting": ("Sabitlenmiş commit'teki yeniden çalıştırma kuralın dışında kaldı ya da tamamlanmadı ({run}).",
                 "The re-run at the pinned commit fell outside the rule or did not complete ({run})."),
    "standing": ("Sabitlenmiş commit'teki yeniden çalıştırma yine kuralın içinde ({run}).",
                 "The re-run at the pinned commit is within the rule again ({run})."),
    "initial": ("İlk atama: sabitlenmiş commit'teki yeniden çalıştırma kuralın içinde ({run}).",
                "First assignment: the re-run at the pinned commit is within the rule ({run})."),
}


def apply_status(claim: dict, passed: bool, date: str, run_rel: str, assign_initial: bool) -> bool:
    """Mutate claim per the status rules; return True when the claim file changed."""
    cur = claim["status"]
    new, by, key = cur, "ci", None
    if cur in ("standing", "drifting"):
        new = "standing" if passed else "drifting"
        key = new
    elif cur == "manual" and assign_initial and passed and claim["rerun"]["class"] in ("nightly", "weekly"):
        new, by, key = "standing", "cleoanka", "initial"
    if new == cur:
        return False
    tr, en = REASONS[key]
    claim["status"] = new
    claim["history"].append({"date": date, "status": new,
                             "reason": {"tr": tr.format(run=run_rel), "en": en.format(run=run_rel)}, "by": by})
    return True


def sync_status(root: Path, claims: dict, lcommit: str | None, touched: set[str], now: str) -> None:
    for cid, claim in claims.items():
        p = root / "status" / f"{cid}.json"
        st = load_json(p) or {"id": cid, "status": claim["status"], "last_verified": None, "last_run": None,
                               "head_last_run": None, "ledger_commit": lcommit, "updated": now}
        if st["status"] != claim["status"] or cid in touched or not p.exists():
            st["status"] = claim["status"]
            st["ledger_commit"] = lcommit
            st["updated"] = now
            dump(p, st)


def select(claims: dict, args) -> list[dict]:
    if args.claim:
        missing = [c for c in args.claim if c not in claims]
        if missing:
            raise SystemExit(f"unknown claim(s): {', '.join(missing)}")
        chosen = [claims[c] for c in args.claim]
    else:
        chosen = [c for c in claims.values() if c["rerun"]["class"] == args.cls]
    if args.runs_on:
        chosen = [c for c in chosen if c["rerun"]["runs_on"] == args.runs_on]
    return sorted(chosen, key=lambda c: c["id"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sel = ap.add_mutually_exclusive_group(required=True)
    sel.add_argument("--class", dest="cls", choices=("nightly", "weekly", "manual"))
    sel.add_argument("--claim", action="append", metavar="ID")
    ap.add_argument("--head", action="store_true", help="also run head_check claims at the default branch's HEAD")
    ap.add_argument("--head-only", action="store_true", help="run only the HEAD checks")
    ap.add_argument("--runs-on", help="only claims whose rerun.runs_on equals this")
    ap.add_argument("--workdir", default=str(LEDGER / "work"))
    ap.add_argument("--root", default=str(LEDGER), help="ledger data dir with claims/, runs/, status/")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--assign-initial", action="store_true", help="owner only: manual -> standing on a pass")
    ap.add_argument("--keep-work", action="store_true", help="keep each work directory after its run")
    ap.add_argument("--python", default=os.environ.get("LEDGER_PYTHON", sys.executable))
    ap.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--runner-label")
    ap.add_argument("--budget-scale", type=float, default=1.0, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    try:
        claims = load_claims(root / "claims")
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    chosen = select(claims, args)
    jobs = []  # (target, claims) ; target pinned|head
    if not args.head_only:
        jobs.append(("pinned", chosen))
    if args.head or args.head_only:
        jobs.append(("head", [c for c in chosen if c["head_check"]]))

    plan = []
    for target, cs in jobs:
        groups: dict[tuple, list[dict]] = {}
        for c in cs:
            groups.setdefault((c["repo"], c["commit"], c["setup"], c["command"]), []).append(c)
        plan += [(target, g) for g in groups.values()]

    if args.dry_run:
        for target, g in plan:
            c = g[0]
            where = c["commit"][:7] if target == "pinned" else "HEAD"
            print(f"[{target}] {', '.join(x['id'] for x in g)}  {c['repo']}@{where}"
                  f"  setup: {c['setup'] or '-'}  command: {c['command']}  budget: {c['rerun']['budget_min']} min")
        if not plan:
            print("nothing selected")
        return 0

    work = Path(args.workdir).resolve()
    work.mkdir(parents=True, exist_ok=True)
    scrub = Scrubber(work, root)
    label = runner_label(args.runner_label)
    lcommit = ledger_commit(root)
    touched: set[str] = set()
    failed = False
    for target, g in plan:
        try:
            commit = g[0]["commit"] if target == "pinned" else head_commit(repo_url(g[0]))
        except (RuntimeError, subprocess.CalledProcessError) as e:
            print(f"[{target}] {g[0]['repo']}: {e}", file=sys.stderr)
            commit = None
        res = execute(g, target, commit, work, args) if commit else {
            "exit_code": None, "stdout": "", "tail": "", "error": "cannot resolve HEAD", "duration_s": 0.0,
            "src": work, "gdir": None}
        for c in g:
            claim = load_json(root / "claims" / f"{c['id']}.json")
            value, guards, error = measure(claim, res) if commit else (None, [], res["error"])
            passed = (error is None and res["exit_code"] == 0 and within(value, claim)
                      and all(x["passed"] for x in guards))
            rec = {
                "id": claim["id"], "date": args.date, "target": target, "commit": commit,
                "runner": label, "command": scrub(claim["command"]), "duration_s": res["duration_s"],
                "exit_code": res["exit_code"], "value": value, "guards": guards, "passed": passed,
                "error": scrub(error) if error else None, "stdout_tail": scrub(res["tail"])[-TAIL:],
            }
            rpath = record_path(root, claim["id"], args.date, target)
            rel = rpath.relative_to(root).as_posix()
            dump(rpath, rec)
            st = load_json(root / "status" / f"{claim['id']}.json") or {
                "id": claim["id"], "status": claim["status"], "last_verified": None, "last_run": None,
                "head_last_run": None, "ledger_commit": lcommit, "updated": None}
            if target == "head":
                st["head_last_run"] = summary(rec, rel)
            else:
                failed |= not passed
                st["last_run"] = summary(rec, rel)
                if passed and claim["status"] in ("standing", "drifting", "manual"):
                    st["last_verified"] = args.date
                if apply_status(claim, passed, args.date, rel, args.assign_initial):
                    problems = validate_claim(claim)
                    if problems:
                        print("\n".join(problems), file=sys.stderr)
                        return 2
                    dump(root / "claims" / f"{claim['id']}.json", claim)
                    claims[claim["id"]] = claim
            st["status"] = claim["status"]
            dump(root / "status" / f"{claim['id']}.json", st)
            touched.add(claim["id"])
            mark = "PASS" if passed else "FAIL"
            print(f"{mark} [{target}] {claim['id']}  value={value}  {res['duration_s']}s"
                  + (f"  error: {rec['error']}" if rec["error"] else ""), flush=True)
        if res.get("gdir") and not args.keep_work:
            shutil.rmtree(res["gdir"], ignore_errors=True)
    sync_status(root, claims, lcommit, touched, utc_now())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
