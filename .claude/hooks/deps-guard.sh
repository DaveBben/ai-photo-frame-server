#!/usr/bin/env bash
set -euo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"
. "$root/.claude/hooks/_slots.sh"

file="$(read_json_field file_path)"
case "$file" in "$root/$deps_file"|"$deps_file") ;; *) exit 0 ;; esac
[ -f "$file" ] || exit 0
cd "$root"

if ! output="$(deps_check 2>&1)"; then
  echo "$deps_file no longer matches the lockfile:" >&2
  echo "$output" >&2
  echo "Change dependencies with $deps_fix, never by editing $deps_file by" >&2
  echo "hand. If this edit was intentional and not a dependency change," >&2
  echo "regenerate the lockfile with 'uv lock'." >&2
  exit 2
fi
exit 0
