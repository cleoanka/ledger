#!/usr/bin/env bash
# Local fallback for the nightly/weekly workflow: run one class on this machine, then commit the
# records locally. Never pushes; prints the push command instead.
#
#   scripts/run-local.sh nightly            # or weekly / manual
#   LEDGER_PYTHON=python3.13 scripts/run-local.sh weekly
#   LEDGER_WORK=/some/dir scripts/run-local.sh nightly   (default: $TMPDIR/ledger-work)
set -euo pipefail

class="${1:-}"
case "$class" in
  nightly|weekly|manual) ;;
  *) echo "usage: $0 nightly|weekly|manual [extra runner args]" >&2; exit 2 ;;
esac
shift

cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain -- claims runs status)" ]; then
  echo "run-local: claims/, runs/ or status/ has uncommitted changes; commit or stash them first" >&2
  exit 2
fi

work="${LEDGER_WORK:-${TMPDIR:-/tmp}/ledger-work}"
date_utc="$(date -u +%Y-%m-%d)"
rc=0
python3 runner/ledger_run.py --class "$class" --workdir "$work" "$@" || rc=$?
rmdir "$work" 2>/dev/null || true

if [ "$rc" -ge 2 ]; then
  echo "run-local: runner error (exit $rc); nothing committed" >&2
  exit "$rc"
fi
git add runs status claims
if git diff --cached --quiet; then
  echo "run-local: nothing to record"
else
  git commit -q -m "Record $class runs $date_utc"
  echo "run-local: committed $(git rev-parse --short HEAD). Review it, then push with:"
  echo "  git push origin main"
fi
exit "$rc"
