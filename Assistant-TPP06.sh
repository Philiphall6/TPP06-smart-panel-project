#!/bin/sh
# Run from any directory; the complete source package must remain together.
set -eu
assistant_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -x "$assistant_dir/.venv-assistant/bin/python" ]; then
    exec "$assistant_dir/.venv-assistant/bin/python" "$assistant_dir/tools/tpp06_assistant.py"
fi
exec python3 "$assistant_dir/tools/tpp06_assistant.py"
