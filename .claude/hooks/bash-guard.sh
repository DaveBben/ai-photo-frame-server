#!/usr/bin/env bash
set -euo pipefail
root="${CLAUDE_PROJECT_DIR:-.}"
. "$root/.claude/hooks/_slots.sh"

cmd="$(read_json_field command)"

# Drop quoted segments and heredoc bodies, so a commit message that mentions a
# blocked phrase passes. Cut at the marker so flags before it are still seen.
scan="$(printf '%s' "$cmd" | sed -e "s/'[^']*'//g" -e 's/"[^"]*"//g' -e '/<</{s/<<.*//;q;}')"

case " $scan " in
  *[\ \;\&\|]pip\ install*|*[\ \;\&\|]pip3\ install*|*"uv pip install"*)
    echo "Install dependencies with $deps_fix. A direct pip install desyncs the" >&2
    echo ".venv from uv.lock." >&2
    exit 2 ;;
  *--no-verify*)
    echo "The pre-commit gate is the quality gate. To skip one hook that needs" >&2
    echo "the network, use SKIP=<hook> git commit. Never --no-verify." >&2
    exit 2 ;;
esac
# -n is --no-verify's short form inside a git commit command.
case "$scan" in
  *git*commit*)
    case " $scan " in
      *" -n "*)
        echo "-n is --no-verify. Use SKIP=<hook> git commit to skip one hook." >&2
        exit 2 ;;
    esac ;;
esac
exit 0
