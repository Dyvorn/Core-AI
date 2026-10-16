#!/usr/bin/env bash
# ==============================================================================
# C.O.R.E. AI :: 24/7 Dedicated Linux Laptop Server Stabilizer
# Fixes:
# 1. Disables 802.11 Wi-Fi Power Save (prevents packet drops and random timeouts)
# 2. Masks Systemd Sleep & Suspend (prevents laptop from sleeping when idle or lid closed)
# 3. Configures systemd-logind to ignore lid switches and idle actions
# 4. Installs production-grade 24/7 systemd service with automatic watchdog recovery
# ==============================================================================

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo "[!] Error: This stabilization script requires root privileges."
    echo "    Please run with: sudo bash $0"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." >/dev/null 2>&1 && pwd )"
ACTUAL_USER="${SUDO_USER:-$(logname 2>/dev/null || echo vyrn)}"

echo ""
echo "======================================================================="
echo "  CORE AI :: 24/7 LINUX LAPTOP SERVER STABILIZATION TOOL"
echo "  Configuring target: $SCRIPT_DIR for user: $ACTUAL_USER"
echo "======================================================================="
echo ""

# 1. Disable Wi-Fi Power Save in NetworkManager
echo "[1/4] Disabling Wi-Fi Power Save..."
NM_CONF_DIR="/etc/NetworkManager/conf.d"
mkdir -p "$NM_CONF_DIR"

cat << 'EOF' > "$NM_CONF_DIR/99-disable-wifi-powersave.conf"
[connection]
wifi.powersave = 2
EOF

# Apply live if iw / nmcli exists
if command -v iw >/dev/null 2>&1; then
    for iface in $(iw dev 2>/dev/null | awk '$1=="Interface"{print $2}'); do
        echo "  ↳ Disabling power save on interface '$iface'..."
        iw dev "$iface" set power_save off 2>/dev/null || true
    done
fi

if command -v nmcli >/dev/null 2>&1; then
    for conn in $(nmcli -t -f NAME,TYPE con show --active 2>/dev/null | grep -E "wireless|802-11-wireless|wifi" | cut -d: -f1); do
        echo "  ↳ Setting powersave=2 on connection '$conn'..."
        nmcli connection modify "$conn" 802-11-wireless.powersave 2 2>/dev/null || true
    done
    systemctl restart NetworkManager 2>/dev/null || true
fi

# 2. Disable Sleep, Suspend, Hibernate & Hybrid Sleep
echo "[2/4] Masking OS Sleep & Suspend targets..."
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null 2>&1 || true

# 3. Configure systemd-logind to ignore lid closes and idle timeouts
echo "[3/4] Configuring logind for headless laptop server..."
LOGIND_CONF="/etc/systemd/logind.conf"
if [ -f "$LOGIND_CONF" ]; then
    # Backup original logind.conf if not already backed up
    if [ ! -f "$LOGIND_CONF.core.bak" ]; then
        cp "$LOGIND_CONF" "$LOGIND_CONF.core.bak"
    fi

    # Update or append lid switch settings
    for opt in HandleLidSwitch HandleLidSwitchExternalPower HandleLidSwitchDocked IdleAction; do
        if grep -q "^#\?${opt}=" "$LOGIND_CONF"; then
            sed -i "s/^#\?${opt}=.*/${opt}=ignore/" "$LOGIND_CONF"
        else
            echo "${opt}=ignore" >> "$LOGIND_CONF"
        fi
    done
    systemctl restart systemd-logind >/dev/null 2>&1 || true
fi

# Enable user session lingering
if command -v loginctl >/dev/null 2>&1 && [ -n "$ACTUAL_USER" ]; then
    loginctl enable-linger "$ACTUAL_USER" >/dev/null 2>&1 || true
fi

# 4. Install & Launch Dedicated Systemd 24/7 Service
echo "[4/4] Installing Core AI system-level 24/7 service..."
# Stop old user service if running to avoid port conflict
su - "$ACTUAL_USER" -c "systemctl --user stop core-ai 2>/dev/null || true; systemctl --user disable core-ai 2>/dev/null || true" 2>/dev/null || true

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

SYSTEMD_SERVICE="/etc/systemd/system/core-ai.service"
cat << EOF > "$SYSTEMD_SERVICE"
[Unit]
Description=Core AI Sovereign Microkernel & Universal Gateway (24/7 Always-On)
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ACTUAL_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_BIN -m core.watchdog --port 8000
Restart=always
RestartSec=3
KillMode=process
TimeoutStopSec=10
Environment=PYTHONUNBUFFERED=1
Environment=CORE_PORT=8000
Environment=CORE_HOST=0.0.0.0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now core-ai

echo ""
echo "======================================================================="
echo "  [SUCCESS] 24/7 LAPTOP SERVER CONFIGURATION COMPLETE!"
echo "======================================================================="
echo "  Wi-Fi Power Save:      PERMANENTLY DISABLED (No more dropped packets)"
echo "  Sleep / Suspend:       MASKED (Laptop stays awake 24/7, lid can close)"
echo "  Systemd Service:       ACTIVE (Managed by systemd with auto-restart)"
echo "  Service Status:        sudo systemctl status core-ai"
echo "  View Server Logs:      tail -f $SCRIPT_DIR/logs/watchdog.log"
echo "======================================================================="
echo ""
