# Every project-specific command the hooks run, defined once.
read_json_field() {
  local field="$1" body
  body="$(cat)"
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$body" | jq -r --arg f "$field" '.tool_input[$f] // .[$f] // ""' 2>/dev/null
  else
    printf '%s' "$body" | sed -n "s/.*\"$field\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -1
  fi
}

ruff_bin() { if [ -x .venv/bin/ruff ]; then .venv/bin/ruff "$@"; else uv run ruff "$@"; fi; }

matches()    { case "$1" in *.py) return 0 ;; *) return 1 ;; esac; }
pathspec=('*.py')
fast_fix()   { ruff_bin check --fix "$1" >/dev/null 2>&1 || true
               ruff_bin format "$1"     >/dev/null 2>&1 || true; }
fast_check() { ruff_bin check --output-format concise "$1"; }
turn_end()   { uv run mypy src && uv run pytest -x; }
deps_file='pyproject.toml'
deps_check() { uv lock --check --offline; }
deps_fix='uv add / uv remove'
env_check()  {
  command -v uv >/dev/null 2>&1 || { echo "NOTE: uv is not on PATH. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"; return; }
  [ -d .venv ] || { echo "NOTE: .venv is missing, run 'uv sync'."; return; }
  uv sync --check >/dev/null 2>&1 || echo "NOTE: .venv is out of sync with uv.lock, run 'uv sync'."
}
