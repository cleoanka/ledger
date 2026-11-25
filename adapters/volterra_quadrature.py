"""volterra-001: the setup of aura-volterra-engine's tests/test_physics.py::test_chebyshev_is_spectral.

    python -I adapters/volterra_quadrature.py --repo <checkout> --out result.json

Writes {"chebyshev_max_err", "trapezoid_max_err", "M"} for the double integral of sin(2t) on
[0, 3] at M = 40: the Chebyshev operator K2 against t/2 - sin(2t)/4, and the trapezoid operator
Kt from build_integral_operators on M + 1 equally spaced nodes against the same closed form.
Only numpy is needed; the engine's own operators are imported from the checkout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.repo).resolve()))
    import numpy as np
    from aura_engine.operators import build_integral_operators, chebyshev_operators

    t0, t1, M = 0.0, 3.0, 40
    t, C, K2 = chebyshev_operators(t0, t1, M)
    a_t = np.sin(2 * t)
    r_an = t / 2 - np.sin(2 * t) / 4
    cheb_err = float(np.max(np.abs(K2 @ a_t - r_an)))

    tt = np.linspace(t0, t1, M + 1)
    Ct, Kt = build_integral_operators(tt)
    trap_err = float(np.max(np.abs(Kt @ np.sin(2 * tt) - (tt / 2 - np.sin(2 * tt) / 4))))

    out = {"chebyshev_max_err": cheb_err, "trapezoid_max_err": trap_err, "M": M}
    Path(a.out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
