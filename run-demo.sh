#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export DEMO=1
export DATABASE="$PWD/instance/demo.sqlite"
if [ ! -f "$DATABASE" ]; then
  .venv/bin/flask --app app seed-demo
fi
exec .venv/bin/python app.py
