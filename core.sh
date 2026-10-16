#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python3"
fi

COMMAND="${1:-run}"

case "$COMMAND" in
    run|console)
        "$PYTHON" main.py
        ;;
    start)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); ok, msg = s.start(in_new_terminal=False, extra_args=['--headless']); print(msg)"
        ;;
    setup)
        "$PYTHON" interfaces/install/setup_service.py
        ;;
    stop)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); ok, msg = s.stop(); print(msg)"
        ;;
    restart)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); s.stop(); ok, msg = s.start(in_new_terminal=False, extra_args=['--headless']); print(msg)"
        ;;
    status)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); s.print_status_card()"
        ;;
    metrics|vitals)
        "$PYTHON" -m core.service metrics
        ;;
    scan)
        "$PYTHON" -m core.mesh_client scan
        ;;
    version|-v|--version)
        "$PYTHON" interfaces/cli/client.py version
        ;;
    config|settings)
        shift
        "$PYTHON" interfaces/cli/settings.py "$@"
        ;;
    edit)
        shift
        "$PYTHON" interfaces/cli/settings.py edit "$@"
        ;;
    audio|mics|speakers)
        "$PYTHON" interfaces/cli/settings.py audio
        ;;
    mic)
        shift
        "$PYTHON" interfaces/cli/settings.py mic "$@"
        ;;
    speaker)
        shift
        "$PYTHON" interfaces/cli/settings.py speaker "$@"
        ;;
    satellite|voice-satellite)
        shift
        "$PYTHON" interfaces/voice/satellite.py "$@"
        ;;
    mobile)
        shift
        "$PYTHON" -m interfaces.mobile.companion "$@"
        ;;
    glyph)
        shift
        "$PYTHON" -m interfaces.mobile.companion glyph "$@"
        ;;
    speak)
        shift
        "$PYTHON" interfaces/cli/client.py speak "$@"
        ;;
    models|model)
        shift
        "$PYTHON" interfaces/cli/settings.py model "$@"
        ;;
    dashboard|ui)
        echo "[*] Launching Sovereign Mesh Master Dashboard at http://localhost:8000 ..."
        "$PYTHON" -m webbrowser "http://localhost:8000"
        ;;
    account)
        if [ "$2" = "setup" ] || [ "$2" = "init" ]; then
            "$PYTHON" interfaces/install/setup_service.py
        elif [ "$2" = "reset" ]; then
            "$PYTHON" interfaces/cli/setup_wizard.py reset
        else
            "$PYTHON" interfaces/cli/setup_wizard.py status
        fi
        ;;
    clean|clean-setup|factory-reset|purge)
        shift
        "$PYTHON" interfaces/install/clean_setup.py "$@"
        ;;
    reset)
        shift
        "$PYTHON" interfaces/install/clean_setup.py "$@"
        ;;
    logo|anim)
        "$PYTHON" -m core.animation
        ;;
    backup)
        "$PYTHON" -c "from core.updater import CoreUpdater; u = CoreUpdater(); d, e = u.create_state_snapshot(); print(f'[OK] Snapshot preserved:\n  Database: {d}\n  Config:   {e}')"
        ;;
    update)
        git checkout -- core.sh install.sh 2>/dev/null || true
        shift
        "$PYTHON" -c "import sys; from core.updater import CoreUpdater; u = CoreUpdater(); force = any(arg in ['--force', '-f', '--skip-tests'] for arg in sys.argv); ok, msg = u.apply_update(force=force); print(msg); sys.exit(0 if ok else 1)" "$@"
        chmod +x core.sh install.sh 2>/dev/null || true
        ;;
    test)
        "$PYTHON" -m pytest tests
        ;;
    autostart)
        "$PYTHON" -m core.service autostart "$2"
        ;;
    watchdog)
        shift
        "$PYTHON" -m core.watchdog "$@"
        ;;
    mesh)
        shift
        "$PYTHON" -m core.mesh_client "$@"
        ;;
    uninstall)
        "$PYTHON" interfaces/install/uninstall.py
        ;;
    help)
        echo ""
        echo "======================================================================="
        echo "  CORE AI :: SOVEREIGN LIFE OS COMMAND CLI"
        echo "======================================================================="
        echo "  Usage: ./core.sh <command> or ./core.sh <goal>"
        echo ""
        echo "  Lifecycle Commands:"
        echo "    [no args]   - Launch Core AI Unified Terminal & Interactive Shell"
        echo "    run         - Launch Core AI Unified Terminal & Interactive Shell"
        echo "    start       - Start Core AI in background daemon mode (24/7 Service)"
        echo "    stop        - Stop running background server suite & free GPU/RAM"
        echo "    restart     - Restart Core AI background daemon"
        echo "    status      - Inspect running server status card, PID, and health"
        echo "    metrics     - Inspect full server telemetry & hardware vitals (RAM/CPU/DB/LAN)"
        echo "    config      - System settings, operator identity, tone, & custom preferences"
        echo "    models      - Dedicated easy AI model selector (interactive picker & roles)"
        echo "    dashboard   - Launch dedicated Sovereign Mesh Master Dashboard in browser"
        echo "    scan        - Scan local network for active Sovereign Main Servers"
        echo "    version     - Display kernel version, codename, node role, and commit"
        echo "    account     - View Sovereign Operator Account identity & security card"
        echo "    clean       - Clean server state wipe (delete DB, config, logs; keep files/venv)"
        echo "    reset       - Clean slate factory reset back to Day-Zero"
        echo "    logo / anim - Launch interactive 3D Sovereign Core holographic viewer"
        echo "    update      - Self-update from GitHub with state backup & test guard"
        echo "    test        - Run automated test suite (pytest)"
        echo "    autostart   - Configure 24/7 boot autostart (./core.sh autostart on|off|status|visible|systemd)"
        echo "    watchdog    - Run self-healing supervisor (auto-revives crashes with backoff)"
        echo "    mesh        - Intercontinental mesh pairing (./core.sh mesh connect <url> | status)"
        echo "    setup       - Run interactive bootstrap & autostart setup"
        echo "    satellite   - Run distributed voice satellite perception daemon"
        echo "    mobile      - Mobile Companion operations (./core.sh mobile glance|enroll|ask|glyph)"
        echo "    glyph       - Trigger Nothing OS rear Glyph LED patterns (./core.sh glyph reasoning_pulse)"
        echo "    speak       - Synthesize and speak text locally or across mesh"
        echo "    uninstall   - Clean zero-residue uninstallation"
        echo ""
        echo "  Daily One-Shot Execution:"
        echo "    ./core.sh <goal> - Execute any goal directly (e.g. ./core.sh 'open discord')"
        echo ""
        ;;
    *)
        "$PYTHON" interfaces/cli/client.py "$@"
        ;;
esac
