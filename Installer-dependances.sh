#!/bin/sh
set -eu
assistant_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 minimum"; import tkinter'
python3 -m venv "$assistant_dir/.venv-assistant"
"$assistant_dir/.venv-assistant/bin/python" -m pip install -r "$assistant_dir/requirements-assistant.txt"
echo 'Dépendances installées sur le PC. Aucun accès au panneau. Ouvrir Assistant-TPP06.sh.'
