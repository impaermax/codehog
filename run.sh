#!/bin/bash
# Запуск CodeHogwarts в разработке.
set -u
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet -r requirements.txt
exec .venv/bin/uvicorn app.main:приложение --reload --host 127.0.0.1 --port 8000
