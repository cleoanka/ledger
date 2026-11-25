"""Pass rules shared by the runner and the tests (stdlib only).

approx: |m - value| <= tolerance
le:     m <= tolerance
ge:     m >= tolerance
eq:     m == value, and the claim's tolerance must be 0

Guards are extra checks on the same result file. They have no reference value, so a guard
uses le, ge or eq against its own tolerance (eq: m == tolerance).
"""
from __future__ import annotations

import math
from pathlib import Path

COMPARATORS = ("approx", "le", "ge", "eq")


def _finite(m) -> bool:
    return isinstance(m, (int, float)) and not isinstance(m, bool) and math.isfinite(m)


def within(measured, claim: dict) -> bool:
    comp, tol = claim["comparator"], claim["tolerance"]
    if comp not in COMPARATORS:
        raise ValueError(f"{claim.get('id', '?')}: unknown comparator {comp!r}")
    if comp == "eq" and tol != 0:
        raise ValueError(f"{claim.get('id', '?')}: eq needs tolerance 0, got {tol!r}")
    if not _finite(measured):
        return False
    if comp == "approx":
        # A tiny epsilon keeps decimal edges (0.952 vs 0.947 ± 0.005) on the passing side.
        return abs(measured - claim["value"]) <= tol + 1e-12 * max(1.0, abs(tol))
    if comp == "le":
        return measured <= tol
    if comp == "ge":
        return measured >= tol
    return measured == claim["value"]


def guard_passes(measured, guard: dict) -> bool:
    comp, tol = guard["comparator"], guard["tolerance"]
    if not _finite(measured):
        return False
    if comp == "le":
        return measured <= tol
    if comp == "ge":
        return measured >= tol
    if comp == "eq":
        return measured == tol
    raise ValueError(f"guard {guard.get('key')!r}: comparator {comp!r} is not allowed (le, ge, eq)")


def check_guards(result_file: Path | None, claim: dict, stdout: str = "") -> list[dict]:
    from ledger.adapters import extract

    out = []
    for g in claim.get("guards", []):
        try:
            value = extract(claim["adapter"], result_file, g["key"], stdout)
        except (ValueError, OSError):
            value = None
        out.append({"key": g["key"], "value": value, "passed": value is not None and guard_passes(value, g)})
    return out
