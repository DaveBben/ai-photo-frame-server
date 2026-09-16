#!/usr/bin/env bash
set -euo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"
. "$root/.claude/hooks/_slots.sh"
cd "$root"

# stdout, not stderr: on SessionStart only stdout reaches the agent.
env_check

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  dirty="$(git status --short)"
  [ -n "$dirty" ] && { echo "Uncommitted changes at session start:"; echo "$dirty"; }
fi
exit 0
