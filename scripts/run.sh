#!/bin/sh
# Read the active Codex configuration on every invocation.
set -eu
skill_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v python3 >/dev/null 2>&1 && python3 -c 'import tomllib' >/dev/null 2>&1; then
  exec python3 "$skill_dir/scripts/run.py" "$@"
fi
runtime_python="${XDG_CACHE_HOME:-$HOME/.cache}/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [ -x "$runtime_python" ]; then
  exec "$runtime_python" "$skill_dir/scripts/run.py" "$@"
fi
echo "Python 3.11+ with tomllib or the bundled Codex Python runtime is required." >&2
exit 1
