#!/bin/zsh

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
"$repo_root/.venv/bin/python" "$repo_root/scripts/run_phase4_pilot_session.py"
status=$?
printf "\nPress Return to close this window."
read -r
exit $status
