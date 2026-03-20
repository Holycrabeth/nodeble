# NODEBLE — Iron Condor Trading Automation

Automated iron condor strategy for Tiger Brokers. Scans for opportunities based on IV rank, executes with sequential leg placement, manages positions with profit/stop/DTE rules.

## Quick Start (Development)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -v
```

## Deploy for a Friend

```bash
# On the friend's VPS (Ubuntu 22.04+):
git clone <repo-url> ~/nodeble
cd ~/nodeble
bash deploy/deploy.sh
```

The deploy script will:
1. Install dependencies
2. Prompt for Tiger API credentials + Telegram token
3. Let them pick a strategy template (Conservative/Moderate/Aggressive)
4. Test the broker connection
5. Install cron jobs
6. Start in dry-run mode

## CLI Usage

```bash
# Scan for iron condor candidates
python -m nodeble --mode scan --dry-run

# Manage open positions
python -m nodeble --mode manage --dry-run

# Test broker connection
python -m nodeble --test-broker

# Force re-run (bypass dedup guard)
python -m nodeble --mode scan --dry-run --force
```

## Config Files

All config lives under `~/.nodeble/config/`:

| File | Purpose |
|------|---------|
| `strategy.yaml` | Watchlist, delta ranges, DTE, IV rank thresholds |
| `risk.yaml` | Kill switch, cash floor, position limits |
| `broker.yaml` | Tiger API credentials (chmod 600) |
| `notify.yaml` | Telegram bot token + chat ID |

Templates are in `config/*.yaml.example`.

## Safety

- **Dry-run by default** — `mode: dry_run` in strategy.yaml
- **Fail-closed risk checks** — any uncertainty = don't trade
- **Both sides required** — no single-side iron condors (prevents directional bets)
- **Sequential leg execution** — long leg first (prevents naked exposure)
- **Atomic state writes** — tempfile + rename (crash-safe)
- **Kill switch** — set `kill_switch: true` in risk.yaml or send `/kill` via Telegram

## Pre-flight Checklist

Before switching from dry-run to live, complete all 10 checks in `plan/06 - MVP Definition.md` (Pre-flight Checklist section).
