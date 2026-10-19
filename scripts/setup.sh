#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"
python3 scripts/restore_dependencies.py
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash keyboard_walk/build_policy_runner.sh
printf '\nHotovo. Spusť: bash start_g1_keyboard.sh\n'
