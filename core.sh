#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
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
    account)
        if [ "$2" = "setup" ] || [ "$2" = "init" ]; then
            "$PYTHON" interfaces/install/setup_service.py
        elif [ "$2" = "reset" ]; then
            "$PYTHON" interfaces/cli/setup_wizard.py reset
        else
            "$PYTHON" interfaces/cli/setup_wizard.py status
        fi
        ;;
    reset)
        "$PYTHON" interfaces/cli/setup_wizard.py reset
        ;;
    logo|anim)
        "$PYTHON" -m core.animation
        ;;
    backup)
        "$PYTHON" -c "from core.updater import CoreUpdater; u = CoreUpdater(); d, e = u.create_state_snapshot(); print(f'[OK] Snapshot preserved:\n  Database: {d}\n  Config:   {e}')"
        ;;
    update)
        "$PYTHON" -c "from core.updater import CoreUpdater; u = CoreUpdater(); ok, msg = u.apply_update(); print(msg)"
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
        echo "    account     - View Sovereign Operator Account identity & security card"
        echo "    reset       - Reset local account database to clean Day-Zero state"
        echo "    logo / anim - Launch interactive 3D Sovereign Core holographic viewer"
        echo "    update      - Self-update from GitHub with state backup & test guard"
        echo "    test        - Run automated test suite (pytest)"
        echo "    autostart   - Configure 24/7 boot autostart (./core.sh autostart on|off|status|visible)"
        echo "    watchdog    - Run self-healing supervisor (auto-revives crashes with backoff)"
        echo "    setup       - Run interactive bootstrap & autostart setup"
        echo "    uninstall   - Clean zero-residue uninstallation"
        echo ""
        echo "  Daily One-Shot Execution:"
        echo "    ./core.sh <goal> - Execute any goal directly (e.g. ./core.sh 'open discord')"
        echo ""
        ;;
    *)
        "$PYTHON" main.py "$@"
        ;;
esac
