#!/bin/bash
set -e

echo "Updating NODEBLE..."

cd "$(dirname "$0")/.."

# Pull latest code
git pull --ff-only

# Reinstall deps (in case they changed)
.venv/bin/pip install -e ".[dev]"

# Run a dry-run scan to verify nothing is broken
echo "Running verification scan (dry-run)..."
.venv/bin/python -m nodeble --mode scan --dry-run --force

echo "Update complete. Cron jobs will use the new code on next run."
