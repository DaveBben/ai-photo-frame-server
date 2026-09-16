#!/usr/bin/env bash
set -euo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"
. "$root/.claude/hooks/_slots.sh"
cd "$root"

red="$(git config --get agile.redCommit 2>/dev/null || true)"
[ -n "$red" ] || exit 0
git cat-file -e "$red^{commit}" 2>/dev/null || exit 0

file="$(read_json_field file_path)"
case "$file" in "$root"/*) file="${file#"$root"/}" ;; esac

if git diff --name-only "$red^" "$red" | grep -qxF "$file"; then
  echo "$file is an accepted test from red commit $red. It is the contract;" >&2
  echo "the build makes it pass, never changes it. Add a new test file for a" >&2
  echo "case the table missed. If the contract itself is wrong, stop and say so:" >&2
  echo "the user re-accepts the row, then runs 'git config --unset agile.redCommit'." >&2
  exit 2
fi
exit 0
