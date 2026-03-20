#!/bin/bash
set -e

echo "========================================="
echo "  NODEBLE Iron Condor Bot — Deployment"
echo "========================================="
echo ""

# 1. Check Python 3.12+
PYTHON=""
for cmd in python3.13 python3.12 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.12+ not found."
    echo "Install with: sudo apt install python3.12 python3.12-venv"
    exit 1
fi
echo "Using Python: $PYTHON ($($PYTHON --version))"

# 2. Set up project directory
NODEBLE_DIR="$HOME/nodeble"
if [ ! -d "$NODEBLE_DIR" ]; then
    echo "ERROR: Project not found at $NODEBLE_DIR"
    echo "Clone it first: git clone <repo-url> ~/nodeble"
    exit 1
fi
cd "$NODEBLE_DIR"

# 3. Create venv + install deps
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi
echo "Installing dependencies..."
.venv/bin/pip install -e ".[dev]" -q

# 4. Create ~/.nodeble/ directory structure
NODEBLE_DATA="$HOME/.nodeble"
mkdir -p "$NODEBLE_DATA/config"
mkdir -p "$NODEBLE_DATA/data"
mkdir -p "$NODEBLE_DATA/logs"

# 5. Interactive prompts
echo ""
echo "--- Tiger Brokers Configuration ---"
read -p "Tiger ID: " TIGER_ID
read -p "Account number: " ACCOUNT_NUM

echo ""
echo "Private key options:"
echo "  1) Paste the key content"
echo "  2) Provide path to existing .pem file"
read -p "Choose [1/2]: " KEY_CHOICE

PEM_PATH="$NODEBLE_DATA/config/tiger_private_key.pem"
if [ "$KEY_CHOICE" = "1" ]; then
    echo "Paste your private key (end with Ctrl+D on empty line):"
    cat > "$PEM_PATH"
    chmod 600 "$PEM_PATH"
    echo "Key saved to $PEM_PATH"
elif [ "$KEY_CHOICE" = "2" ]; then
    read -p "Path to .pem file: " SRC_PEM
    cp "$SRC_PEM" "$PEM_PATH"
    chmod 600 "$PEM_PATH"
    echo "Key copied to $PEM_PATH"
else
    echo "Invalid choice"
    exit 1
fi

echo ""
echo "--- Telegram Configuration ---"
read -p "Telegram bot token: " TG_TOKEN
read -p "Telegram chat ID: " TG_CHAT_ID

echo ""
echo "--- Strategy Template ---"
echo "  1) Conservative (low risk, fewer trades)"
echo "  2) Moderate (balanced)"
echo "  3) Aggressive (more trades, wider deltas)"
read -p "Choose [1/2/3]: " STRATEGY_CHOICE

case "$STRATEGY_CHOICE" in
    1) TEMPLATE="strategy.yaml.example" ;;
    2) TEMPLATE="strategy-moderate.yaml.example" ;;
    3) TEMPLATE="strategy-aggressive.yaml.example" ;;
    *) echo "Invalid choice"; exit 1 ;;
esac

# 6. Write config files
cp "$NODEBLE_DIR/config/$TEMPLATE" "$NODEBLE_DATA/config/strategy.yaml"
cp "$NODEBLE_DIR/config/risk.yaml.example" "$NODEBLE_DATA/config/risk.yaml"

cat > "$NODEBLE_DATA/config/broker.yaml" << EOF
tiger_id: "$TIGER_ID"
account: "$ACCOUNT_NUM"
private_key_path: "$PEM_PATH"
sandbox: false
language: "en_US"
EOF
chmod 600 "$NODEBLE_DATA/config/broker.yaml"

cat > "$NODEBLE_DATA/config/notify.yaml" << EOF
telegram:
  bot_token: "$TG_TOKEN"
  chat_id: "$TG_CHAT_ID"
  enabled: true
EOF
chmod 600 "$NODEBLE_DATA/config/notify.yaml"

echo ""
echo "Config files written to $NODEBLE_DATA/config/"

# 7. Test broker connection
echo ""
echo "Testing broker connection..."
if .venv/bin/python -m nodeble --test-broker; then
    echo "Broker connection OK!"
else
    echo ""
    echo "WARNING: Broker connection failed."
    echo "Check your Tiger ID, account number, and private key."
    echo "You can edit: $NODEBLE_DATA/config/broker.yaml"
    echo "Then re-run: .venv/bin/python -m nodeble --test-broker"
fi

# 8. Set timezone to US Eastern (cron jobs run on ET schedule)
echo ""
CURRENT_TZ=$(timedatectl show -p Timezone --value 2>/dev/null || echo "unknown")
if [ "$CURRENT_TZ" != "America/New_York" ]; then
    echo "VPS timezone is $CURRENT_TZ. Cron jobs need US Eastern time."
    read -p "Set timezone to America/New_York? [Y/n]: " SET_TZ
    if [ "$SET_TZ" != "n" ] && [ "$SET_TZ" != "N" ]; then
        sudo timedatectl set-timezone America/New_York
        echo "Timezone set to America/New_York"
    else
        echo "WARNING: Cron times are in ET. Adjust manually if your VPS uses a different timezone."
    fi
fi

# 9. Install cron jobs
echo ""
echo "Installing cron jobs..."
# Remove existing nodeble crons
crontab -l 2>/dev/null | grep -v "nodeble" > /tmp/crontab_clean || true
# Add scan + manage crons (ET times)
cat >> /tmp/crontab_clean << CRON
# NODEBLE scan — weekdays 10:00 AM ET
0 10 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode scan >> $NODEBLE_DATA/logs/cron.log 2>&1
# NODEBLE manage — weekdays 10:30 AM and 3:00 PM ET
30 10 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode manage >> $NODEBLE_DATA/logs/cron.log 2>&1
0 15 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode manage --force >> $NODEBLE_DATA/logs/cron.log 2>&1
CRON
crontab /tmp/crontab_clean
rm /tmp/crontab_clean
echo "Cron jobs installed."

# 10. Run first dry-run
echo ""
echo "Running first dry-run scan..."
.venv/bin/python -m nodeble --mode scan --dry-run --force

echo ""
echo "========================================="
echo "  DEPLOYMENT COMPLETE!"
echo "========================================="
echo ""
echo "Bot is running in DRY-RUN mode."
echo "Check Telegram for status messages."
echo ""
echo "To switch to live trading:"
echo "  1. Complete the pre-flight checklist"
echo "  2. Edit $NODEBLE_DATA/config/strategy.yaml"
echo "  3. Change 'mode: dry_run' to 'mode: live'"
echo ""
echo "To update: bash $NODEBLE_DIR/deploy/update.sh"
echo "To check status: .venv/bin/python -m nodeble --mode scan --dry-run"
