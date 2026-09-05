@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if "%1"=="" goto run
if "%1"=="run" goto run
if "%1"=="console" goto run
if "%1"=="start" goto run
if "%1"=="help" goto help
if "%1"=="setup" goto setup
if "%1"=="stop" goto stop
if "%1"=="restart" goto restart
if "%1"=="status" goto status
if "%1"=="update" goto update
if "%1"=="test" goto test
if "%1"=="uninstall" goto uninstall

:run
"%PYTHON%" main.py %*
goto end

:help
echo.
echo =======================================================================
echo   CORE AI :: SOVEREIGN LIFE OS COMMAND CLI
echo =======================================================================
echo   Usage: core ^<command^>
echo.
echo   Commands:
echo     [no args]   - Launch Core AI Unified Terminal ^& Gateway Server
echo     run         - Launch Core AI Unified Terminal ^& Gateway Server
echo     setup       - Run interactive bootstrap ^& autostart setup (Y/N)
echo     status      - Inspect running server status, PID, memory, and health
echo     stop        - Stop running background server suite
echo     update      - Check GitHub for updates with automated test guard
echo     test        - Run automated test suite (pytest)
echo     uninstall   - Clean zero-residue uninstallation
echo.
goto end

:setup
"%PYTHON%" interfaces\install\setup_service.py
goto end

:stop
"%PYTHON%" -c "from core.service import ServiceManager; s = ServiceManager(); ok, msg = s.stop(); print(msg)"
goto end

:restart
"%PYTHON%" -c "from core.service import ServiceManager; s = ServiceManager(); s.stop(); ok, msg = s.start(in_new_terminal=True); print(msg)"
goto end

:status
"%PYTHON%" -c "from core.service import ServiceManager; s = ServiceManager(); st = s.status(); print('Running:', st['is_running'], '| PID:', st['pid'], '| Gateway:', 'ONLINE' if st['gateway_healthy'] else 'OFFLINE', '| Memory:', st.get('memory_mb', 'N/A'), 'MB')"
goto end

:update
"%PYTHON%" -c "from core.updater import CoreUpdater; u = CoreUpdater(); ok, msg = u.apply_update(); print(msg)"
goto end

:test
"%PYTHON%" -m pytest tests
goto end

:uninstall
"%PYTHON%" interfaces\install\uninstall.py
goto end

:end
endlocal
