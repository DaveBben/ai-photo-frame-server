#!/usr/bin/env bash
set -euo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"
. "$root/.claude/hooks/_slots.sh"

file="$(read_json_field file_path)"

# This repo only. A session can hold other working directories.
case "$file" in "$root"/*) ;; *) exit 0 ;; esac
matches "$file" || exit 0
[ -f "$file" ] || exit 0

cd "$root"
fast_fix "$file"

set +e
output="$(fast_check "$file" 2>&1)"; code=$?
set -e

# ruff exits 1 for findings and 2 when it cannot run.
if [ "$code" -eq 1 ]; then
  echo "Issues in $file that need a real fix (not auto-fixable):" >&2
  echo "$output" >&2
  exit 2
elif [ "$code" -ne 0 ]; then
  echo "fast-check: the checker failed to run (exit $code), not a finding:" >&2
  echo "$output" >&2
fi
exit 0
