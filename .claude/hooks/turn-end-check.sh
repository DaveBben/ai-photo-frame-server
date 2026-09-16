#!/usr/bin/env bash
set -euo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"
. "$root/.claude/hooks/_slots.sh"

sid="$(read_json_field session_id)"
counter="${TMPDIR:-/tmp}/claude-turn-end-${sid:-unknown}"
count="$(cat "$counter" 2>/dev/null || true)"
case "$count" in ''|*[!0-9]*) count=0 ;; esac

cd "$root"

# The array stays quoted, or bash expands the pattern before git sees it.
changed="$(git status --porcelain -- "${pathspec[@]}" 2>/dev/null || true)"
[ -z "$changed" ] && exit 0

if ! output="$(turn_end 2>&1)"; then
  if [ "$count" -ge 3 ]; then
    rm -f "$counter"
    echo "turn-end: still failing after 3 blocked stops, letting the stop through." >&2
    exit 0
  fi
  echo $((count + 1)) > "$counter"
  echo "The turn-end check failed. Fix these before finishing:" >&2
  echo "$output" >&2
  exit 2
fi

rm -f "$counter"
exit 0
