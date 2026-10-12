@echo off
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else if exist "venv\Scripts\python.exe" (
    set "PYTHON=venv\Scripts\python.exe"
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
if /i "%~1"=="metrics" goto metrics
if /i "%~1"=="vitals" goto metrics
if /i "%~1"=="scan" goto scan
if /i "%~1"=="config" goto config
if /i "%~1"=="settings" goto config
if /i "%~1"=="edit" goto edit
if /i "%~1"=="audio" goto audio
if /i "%~1"=="mics" goto audio
if /i "%~1"=="speakers" goto audio
if /i "%~1"=="mic" goto mic
if /i "%~1"=="speaker" goto speaker
if /i "%~1"=="satellite" goto satellite
if /i "%~1"=="dashboard" goto dashboard
if /i "%~1"=="ui" goto dashboard
if /i "%~1"=="models" goto models
if /i "%~1"=="model" goto models
if /i "%~1"=="account" goto account
if /i "%~1"=="reset" goto reset
if /i "%~1"=="logo" goto logo
if /i "%~1"=="anim" goto logo
if /i "%~1"=="backup" goto backup
if /i "%~1"=="update" goto update
if /i "%~1"=="test" goto test
if /i "%~1"=="autostart" goto autostart
if /i "%~1"=="watchdog" goto watchdog
if /i "%~1"=="mesh" goto mesh
if /i "%~1"=="clean" goto clean
if /i "%~1"=="clean-setup" goto clean
if /i "%~1"=="factory-reset" goto clean
if /i "%~1"=="version" goto version
if /i "%~1"=="-v" goto version
if /i "%~1"=="--version" goto version
if /i "%~1"=="mobile" goto mobile
if /i "%~1"=="glyph" goto glyph
if /i "%~1"=="speak" goto speak
if /i "%~1"=="uninstall" goto uninstall

goto quick_solve

:edit
shift
"%PYTHON%" interfaces\cli\settings.py edit %1 %2 %3 %4 %5
goto :eof

:audio
"%PYTHON%" interfaces\cli\settings.py audio
goto :eof

:mic
shift
"%PYTHON%" interfaces\cli\settings.py mic %1 %2 %3 %4 %5
goto :eof

:speaker
shift
"%PYTHON%" interfaces\cli\settings.py speaker %1 %2 %3 %4 %5
goto :eof

:satellite
shift
"%PYTHON%" interfaces\voice\satellite.py %1 %2 %3 %4 %5 %6 %7 %8 %9
goto :eof

:mobile
shift
"%PYTHON%" -m interfaces.mobile.companion %1 %2 %3 %4 %5 %6 %7 %8 %9
goto :eof

:glyph
shift
"%PYTHON%" -m interfaces.mobile.companion glyph %1 %2 %3 %4 %5 %6 %7 %8 %9
goto :eof

:speak
"%PYTHON%" interfaces\cli\client.py %*
goto :eof

:version
"%PYTHON%" interfaces\cli\client.py version
goto :eof

:logo
"%PYTHON%" -u -m core.animation
goto :eof

:run
if not "%~1"=="" if /i "%~1"=="run" shift
if not "%~1"=="" if /i "%~1"=="console" shift
echo [*] Launching Core AI Sovereign Life OS...
"%PYTHON%" -u main.py %*
if %ERRORLEVEL% neq 0 (
    echo [!] Core AI exited with code %ERRORLEVEL%.
)
goto :eof

:quick_solve
"%PYTHON%" -u interfaces\cli\client.py %*
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

:metrics
"%PYTHON%" -m core.service metrics
goto :eof

:scan
"%PYTHON%" -m core.mesh_client scan
goto :eof

:config
shift
"%PYTHON%" interfaces\cli\settings.py %1 %2 %3 %4 %5 %6
goto :eof

:dashboard
echo [*] Launching Sovereign Mesh Master Dashboard at http://localhost:8000 ...
"%PYTHON%" -m webbrowser "http://localhost:8000"
goto :eof

:models
shift
"%PYTHON%" interfaces\cli\settings.py model %1 %2 %3 %4 %5
goto :eof

:account
if /i "%~2"=="setup" goto setup
if /i "%~2"=="init" goto setup
if /i "%~2"=="reset" goto reset
"%PYTHON%" interfaces\cli\setup_wizard.py status
goto :eof

:clean
shift
"%PYTHON%" interfaces\install\clean_setup.py %1 %2 %3 %4 %5
goto end

:reset
shift
"%PYTHON%" interfaces\install\clean_setup.py %1 %2 %3 %4 %5
goto end

:backup
"%PYTHON%" -c "from core.updater import CoreUpdater; u = CoreUpdater(); d, e = u.create_state_snapshot(); print('[OK] Snapshot preserved:\n  Database: ' + str(d) + '\n  Config:   ' + str(e))"
goto :eof

:update
"%PYTHON%" -c "from core.updater import CoreUpdater; u = CoreUpdater(); ok, msg = u.apply_update(); print(msg)"
goto :eof

:test
"%PYTHON%" -m pytest tests
goto :eof

:autostart
"%PYTHON%" -m core.service autostart %2
goto :eof

:watchdog
"%PYTHON%" -m core.watchdog %2 %3 %4 %5
goto :eof

:mesh
"%PYTHON%" -m core.mesh_client %2 %3 %4 %5
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
echo     metrics     - Inspect full server telemetry ^& hardware vitals (RAM/CPU/DB/LAN)
echo     config      - System settings, operator identity, tone, ^& custom preferences
echo     models      - Dedicated easy AI model selector (interactive picker ^& roles)
echo     dashboard   - Launch dedicated Sovereign Mesh Master Dashboard in browser
echo     scan        - Scan local network for active Sovereign Main Servers
echo     version     - Display kernel version, codename, node role, and commit
echo     clean       - Clean server state wipe (delete DB, config, logs; keep files/venv)
echo     reset       - Clean slate factory reset back to Day-Zero
echo     logo / anim - Launch interactive 3D Sovereign Core holographic viewer
echo     update      - Self-update from GitHub with state backup ^& test guard
echo     test        - Run automated test suite (pytest)
echo     autostart   - Configure 24/7 boot autostart (core autostart on^|off^|status^|visible)
echo     watchdog    - Run self-healing supervisor (auto-revives crashes with backoff)
echo     setup       - Run interactive bootstrap ^& autostart setup
echo     satellite   - Run distributed voice satellite perception daemon
echo     mobile      - Mobile Companion operations (core mobile glance^|enroll^|ask^|glyph)
echo     glyph       - Trigger Nothing OS rear Glyph LED patterns (core glyph reasoning_pulse)
echo     speak       - Synthesize and speak text locally or across mesh
echo     uninstall   - Clean zero-residue uninstallation
echo.
echo   Daily One-Shot Execution:
echo     core ^<goal^> - Execute any goal directly (e.g. core "open discord")
echo.
goto end

:end
endlocal
