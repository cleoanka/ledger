# cleoanka/ledger

> **Özet (TR):** cleoanka projelerinden çıkan, yeniden çalıştırılabilir iddiaların defteri. Her iddia
> `claims/<id>.json` içinde durur: cümlesi, yayımlanmış sayısı, toleransı, sabitlenmiş commit'i ve tam
> komutu. Gece ve haftalık iş akışları komutları sabitlenmiş commit'te yeniden çalıştırır, sonucu
> `runs/` altına yazar ve durumu `status/` altında günceller. CI yalnız "ayakta" ile "sapmada" arasında
> geçiş yapabilir; zayıfladı, çürütüldü ve geri çekildi kararlarını sahibi gerekçesiyle verir. Bir
> iddiayı çürütmek için `CONTRIBUTING.md`'deki kurallara bakın.

A public ledger of re-runnable claims from the [cleoanka](https://www.cleoanka.com/) projects. Each
claim is one JSON file with the sentence it makes, the number that was published, a pass rule, the
pinned commit and the exact command that produces the number. A runner re-runs the command, compares
the result with the rule and writes an append-only run record. The site reads a pinned snapshot of
this repo; live status and badges come from `https://www.cleoanka.com/api/status/<id>` and
`https://www.cleoanka.com/badge/<id>.svg`.

## Claims

| claim | published | re-run | status |
|---|---|---|---|
| [`atlas-001`](claims/atlas-001.json) | 94.7% | nightly | ![atlas-001](https://www.cleoanka.com/badge/atlas-001.svg) |
| [`atlas-002`](claims/atlas-002.json) | 71.4% | weekly | ![atlas-002](https://www.cleoanka.com/badge/atlas-002.svg) |
| [`atlas-003`](claims/atlas-003.json) | 62% | manual | ![atlas-003](https://www.cleoanka.com/badge/atlas-003.svg) |
| [`aura-mind-001`](claims/aura-mind-001.json) | +0.000 | weekly | ![aura-mind-001](https://www.cleoanka.com/badge/aura-mind-001.svg) |
| [`aura-mind-002`](claims/aura-mind-002.json) | 0 leaks | nightly | ![aura-mind-002](https://www.cleoanka.com/badge/aura-mind-002.svg) |
| [`aura-mind-003`](claims/aura-mind-003.json) | −0.000 ± 0.001 | manual | ![aura-mind-003](https://www.cleoanka.com/badge/aura-mind-003.svg) |
| [`kairos-001`](claims/kairos-001.json) | 0 | weekly | ![kairos-001](https://www.cleoanka.com/badge/kairos-001.svg) |
| [`kairos-002`](claims/kairos-002.json) | 5/5 | weekly | ![kairos-002](https://www.cleoanka.com/badge/kairos-002.svg) |
| [`unscratchable-001`](claims/unscratchable-001.json) | 0 | nightly | ![unscratchable-001](https://www.cleoanka.com/badge/unscratchable-001.svg) |
| [`volterra-001`](claims/volterra-001.json) | 9×10⁻¹⁶ | nightly | ![volterra-001](https://www.cleoanka.com/badge/volterra-001.svg) |
| [`volterra-002`](claims/volterra-002.json) | ~10⁻¹⁵ | manual | ![volterra-002](https://www.cleoanka.com/badge/volterra-002.svg) |
| [`zeno-001`](claims/zeno-001.json) | 94.5% | nightly | ![zeno-001](https://www.cleoanka.com/badge/zeno-001.svg) |
| [`zeno-002`](claims/zeno-002.json) | 0.95 s | manual | ![zeno-002](https://www.cleoanka.com/badge/zeno-002.svg) |

A badge for any claim: `https://www.cleoanka.com/badge/<id>.svg`.

## Layout

| path | what |
|---|---|
| `schema/claim.schema.json` | JSON Schema (2020-12) for a claim |
| `claims/<id>.json` | one claim; ids are `<project>-<nnn>` and are never reused |
| `runs/<id>/<date>[-head].json` | one run record per re-run, append-only |
| `status/<id>.json` | current status, last verification and the last run summaries |
| `ledger/` | pass rules (`compare.py`), result adapters (`adapters.py`), validator (`schema.py`) |
| `runner/ledger_run.py` | the runner used by CI and by `scripts/run-local.sh` |
| `adapters/` | small helper scripts a claim's command may call (`$LEDGER` points at this checkout) |

## Pass rules

| comparator | passes when |
|---|---|
| `approx` | `abs(measured - value) <= tolerance` |
| `le` | `measured <= tolerance` |
| `ge` | `measured >= tolerance` |
| `eq` | `measured == value` (tolerance is always 0) |

`value` is always the number published at the pinned commit. A re-run never changes it: measured
values appear only in run records. Optional `guards` check more keys of the same result file with
`le`, `ge` or `eq` against their own tolerance.

## Statuses

| status | meaning | who sets it |
|---|---|---|
| `standing` | the last run was within the rule | CI keeps it; the owner sets it first |
| `drifting` | the number left the rule at the pinned commit, or the command failed | CI |
| `weakened` | true only under narrower conditions; sentence and conditions updated | owner, with a written reason |
| `refuted` | false under the stated conditions | owner, with a written reason |
| `retracted` | withdrawn by the owner without an outside refutation | owner |
| `manual` | does not fit the CI budget; verified by hand, last verification shown | owner |

Every claim starts as `manual` with no verification date. Only the owner's first passing run moves a
nightly or weekly claim to `standing` (`--assign-initial`). After that CI can only switch between
`standing` and `drifting`. A HEAD run (`--head`) checks the default branch's latest commit and is
recorded next to the pinned run; it never changes the status.

## Run it

```sh
python3 -m unittest discover -s tests            # unit tests, stdlib only
python3 runner/ledger_run.py --claim zeno-001 --dry-run
python3 runner/ledger_run.py --class nightly      # what CI runs every night
scripts/run-local.sh nightly                      # same, on your machine, then commits locally
```

Each claim runs in its own work directory (and Python virtual environment) under `work/`, with the
claim's `budget_min` as a hard timeout. Requirements: Python 3.11+, git, and whatever the claim's
own setup needs (Node 22 for unscratchable, a Rust toolchain for zeno).

CI (`.github/workflows/nightly.yml`) runs `ubuntu-24.04` claims on Ubuntu and `macos-15` claims on
macOS, then one job commits the new records. `scripts/run-local.sh` is the same thing on your own
machine when Actions are unavailable: it runs one class (or `claim <id>`), commits the records locally
and prints the push command; it never pushes. Claims with a `local:<label>` runner (GPU timings,
large downloads) are run this way by the owner.

## Refuting a claim

Open an issue with the **Refutation** form. Rules and response times are in
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT © 2026 cleoanka
