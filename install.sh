#!/usr/bin/env bash
# Core AI Sovereign Life OS - Linux / macOS One-Line Bootstrap Installer
# Usage: curl -fsSL https://raw.githubusercontent.com/Dyvorn/Core-AI/master/install.sh | bash
set -e

echo ""
echo "======================================================================="
echo "  CORE AI :: SOVEREIGN LIFE OS - TERMINAL BOOTSTRAP INSTALLER"
echo "  Zero corporate telemetry. 100% self-hosted. Lead: Dyvorn"
echo "======================================================================="
echo ""

# 1. Resolve Target Directory
if [ -f "main.py" ] && [ -f "requirements.txt" ]; then
    TARGET_DIR="$(pwd)"
    echo "[+] Running inside existing Core AI repository: $TARGET_DIR"
else
    TARGET_DIR="$HOME/Core-AI"
    if [ ! -d "$TARGET_DIR" ]; then
        echo "[*] Cloning Core AI from GitHub into: $TARGET_DIR"
        if ! command -v git &> /dev/null; then
            echo "[ERROR] Git is not installed. Please install git: sudo apt install git / brew install git"
            exit 1
        fi
        git clone https://github.com/Dyvorn/Core-AI.git "$TARGET_DIR"
    else
        echo "[+] Found existing installation at: $TARGET_DIR"
    fi
    cd "$TARGET_DIR"
fi

# 2. Check Python 3
PYTHON_BIN=""
if command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
elif command -v python &> /dev/null; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 was not detected on your system."
    echo "Please install Python 3.10+ (e.g. sudo apt install python3 python3-venv python3-pip)"
    exit 1
fi

echo "[+] Using system Python: $PYTHON_BIN"

# 3. Virtual Environment Setup
VENV_PYTHON="$TARGET_DIR/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[*] Creating isolated Python virtual environment (.venv)..."
    "$PYTHON_BIN" -m venv .venv
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[ERROR] Virtual environment creation failed. Make sure python3-venv is installed."
    exit 1
fi

echo "[+] Virtual environment active: $VENV_PYTHON"

# 4. Install Dependencies
echo "[*] Installing and verifying Core AI dependencies from requirements.txt..."
"$VENV_PYTHON" -m pip install --upgrade pip --quiet
"$VENV_PYTHON" -m pip install -r requirements.txt --quiet
echo "[+] Dependencies verified successfully."

# 5. Execute Interactive Setup Wizard & Launch
echo ""
echo "[*] Launching Core AI Setup Wizard..."
"$VENV_PYTHON" interfaces/install/setup_service.py
