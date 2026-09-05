#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

COMMAND="${1:-help}"

case "$COMMAND" in
    setup)
        "$PYTHON" interfaces/install/setup_service.py
        ;;
    start)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); ok, msg = s.start(in_new_terminal=True); print(msg)"
        ;;
    stop)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); ok, msg = s.stop(); print(msg)"
        ;;
    restart)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); s.stop(); ok, msg = s.start(in_new_terminal=True); print(msg)"
        ;;
    status)
        "$PYTHON" -c "from core.service import ServiceManager; s = ServiceManager(); st = s.status(); print('Running:', st['is_running'], '| PID:', st['pid'], '| Gateway:', 'ONLINE' if st['gateway_healthy'] else 'OFFLINE', '| Memory:', st.get('memory_mb', 'N/A'), 'MB')"
        ;;
    update)
        "$PYTHON" -c "from core.updater import CoreUpdater; u = CoreUpdater(); ok, msg = u.apply_update(); print(msg)"
        ;;
    console)
        "$PYTHON" interfaces/cli/core_console.py
        ;;
    test)
        "$PYTHON" -m pytest tests
        ;;
    uninstall)
        "$PYTHON" interfaces/install/uninstall.py
        ;;
    *)
        echo ""
        echo "======================================================================="
        echo "  CORE AI :: SOVEREIGN LIFE OS COMMAND CLI"
        echo "======================================================================="
        echo "  Usage: ./core.sh <command>"
        echo ""
        echo "  Commands:"
        echo "    setup       - Run interactive bootstrap and autostart setup (Y/N)"
        echo "    start       - Start Core AI Server Suite"
        echo "    stop        - Stop server suite and free RAM / GPU"
        echo "    restart     - Restart Core AI Server Suite"
        echo "    status      - Inspect running server status, PID, memory, and health"
        echo "    update      - Check GitHub for updates with automated test guard"
        echo "    console     - Launch interactive Cyber Operator Console"
        echo "    test        - Run automated test suite (pytest)"
        echo "    uninstall   - Clean zero-residue uninstallation"
        echo ""
        ;;
esac
