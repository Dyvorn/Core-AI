@echo off
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if "%~1"=="" goto run
if /i "%~1"=="run" goto run
if /i "%~1"=="console" goto run
if /i "%~1"=="start" goto start_daemon
if /i "%~1"=="help" goto help
if /i "%~1"=="setup" goto setup
if /i "%~1"=="stop" goto stop
if /i "%~1"=="restart" goto restart
if /i "%~1"=="status" goto status
if /i "%~1"=="models" goto models
if /i "%~1"=="model" goto models
if /i "%~1"=="account" goto account
if /i "%~1"=="reset" goto reset
if /i "%~1"=="logo" goto logo
if /i "%~1"=="anim" goto logo
if /i "%~1"=="backup" goto backup
if /i "%~1"=="update" goto update
if /i "%~1"=="test" goto test
if /i "%~1"=="uninstall" goto uninstall

goto quick_solve

:logo
"%PYTHON%" -m core.animation
goto :eof

:run
"%PYTHON%" main.py
goto :eof

:quick_solve
"%PYTHON%" main.py %*
goto :eof

:start_daemon
"%PYTHON%" -c "from core.service import ServiceManager; s = ServiceManager(); ok, msg = s.start(in_new_terminal=False, extra_args=['--headless']); print(msg)"
goto :eof

:stop
"%PYTHON%" -c "from core.service import ServiceManager; s = ServiceManager(); ok, msg = s.stop(); print(msg)"
goto :eof

:restart
"%PYTHON%" -c "from core.service import ServiceManager; s = ServiceManager(); s.stop(); ok, msg = s.start(in_new_terminal=False, extra_args=['--headless']); print(msg)"
goto :eof

:status
"%PYTHON%" -c "from core.service import ServiceManager; s = ServiceManager(); s.print_status_card()"
goto :eof

:models
"%PYTHON%" -c "from brain.model_router import ModelRouter; from core.state import StateManager; r = ModelRouter(StateManager()); s = r.get_status_summary(); print('\n--- Configured AI Providers & Models ---'); [print(f'  - {p:<16}: [ONLINE]' if v else f'  - {p:<16}: [OFFLINE]') for p, v in s['configured_providers'].items()]; m_list = s.get('ollama_models', []); (lambda: print(f'    Installed in Ollama: {\", \".join(m_list)}'))() if m_list else None; print('\n--- Active Model Roles ---'); [print(f'  - {role:<16}: {info[\"model\"]}') for role, info in s['roles'].items()]; print()"
goto :eof

:account
if /i "%~2"=="setup" goto setup
if /i "%~2"=="init" goto setup
if /i "%~2"=="reset" goto reset
"%PYTHON%" interfaces\cli\setup_wizard.py status
goto :eof

:reset
"%PYTHON%" interfaces\cli\setup_wizard.py reset
goto :eof

:backup
"%PYTHON%" -c "from core.updater import CoreUpdater; u = CoreUpdater(); d, e = u.create_state_snapshot(); print('[OK] Snapshot preserved:\n  Database: ' + str(d) + '\n  Config:   ' + str(e))"
goto :eof

:update
"%PYTHON%" -c "from core.updater import CoreUpdater; u = CoreUpdater(); ok, msg = u.apply_update(); print(msg)"
goto :eof

:test
"%PYTHON%" -m pytest tests
goto :eof

:setup
"%PYTHON%" interfaces\install\setup_service.py
goto end

:uninstall
"%PYTHON%" interfaces\install\uninstall.py
goto end

:help
echo.
echo =======================================================================
echo   CORE AI :: SOVEREIGN LIFE OS COMMAND CLI
echo =======================================================================
echo   Usage: core ^<command^> or core ^<goal^>
echo.
echo   Lifecycle Commands:
echo     [no args]   - Launch Core AI Unified Terminal ^& Interactive Shell
echo     run         - Launch Core AI Unified Terminal ^& Interactive Shell
echo     start       - Start Core AI in background daemon mode (24/7 Service)
echo     stop        - Stop running background server suite ^& free GPU/RAM
echo     restart     - Restart Core AI background daemon
echo     status      - Inspect running server status card, PID, and health
echo     account     - View Sovereign Operator Account identity ^& security card
echo     reset       - Reset local account database to clean Day-Zero state
echo     logo / anim - Launch interactive 3D Sovereign Core holographic viewer
echo     update      - Self-update from GitHub with state backup ^& test guard
echo     test        - Run automated test suite (pytest)
echo     setup       - Run interactive bootstrap ^& autostart setup
echo     uninstall   - Clean zero-residue uninstallation
echo.
echo   Daily One-Shot Execution:
echo     core ^<goal^> - Execute any goal directly (e.g. core "open discord")
echo.
goto end

:end
endlocal
