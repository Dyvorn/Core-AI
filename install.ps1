# Core AI Sovereign Life OS - Windows One-Line Bootstrap Installer
# Usage: irm https://raw.githubusercontent.com/Dyvorn/Core-AI/master/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host "  CORE AI :: SOVEREIGN LIFE OS - TERMINAL BOOTSTRAP INSTALLER" -ForegroundColor Cyan
Write-Host "  Zero corporate telemetry. 100% self-hosted. Lead: Dyvorn" -ForegroundColor Cyan
Write-Host "=======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Resolve Target Directory
$TargetDir = ""
if (Test-Path "main.py" -PathType Leaf -And (Test-Path "requirements.txt" -PathType Leaf)) {
    $TargetDir = (Get-Location).Path
    Write-Host "[+] Running inside existing Core AI repository: $TargetDir" -ForegroundColor Green
} else {
    $InstallParent = [System.IO.Path]::Combine($env:USERPROFILE, "Core-AI")
    $TargetDir = $InstallParent
    if (-Not (Test-Path $TargetDir)) {
        Write-Host "[*] Cloning Core AI from GitHub into: $TargetDir" -ForegroundColor Yellow
        if (-Not (Get-Command git -ErrorAction SilentlyContinue)) {
            Write-Host "[ERROR] Git is not installed on this system. Please install Git: https://git-scm.com" -ForegroundColor Red
            Exit 1
        }
        git clone https://github.com/Dyvorn/Core-AI.git $TargetDir
    } else {
        Write-Host "[+] Found existing installation at: $TargetDir" -ForegroundColor Green
    }
    Set-Location $TargetDir
}

# 2. Check Python 3.10+
$PythonCmd = ""
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonCmd = "py -3"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonCmd = "python"
} elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
    $PythonCmd = "python3"
} else {
    Write-Host "[ERROR] Python 3 was not detected on your system." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://python.org or via: winget install Python.Python.3.13" -ForegroundColor Yellow
    Exit 1
}

Write-Host "[+] Using system Python: $PythonCmd" -ForegroundColor Green

# 3. Virtual Environment Setup
$VenvPython = Join-Path $TargetDir ".venv\Scripts\python.exe"
if (-Not (Test-Path $VenvPython)) {
    Write-Host "[*] Creating isolated Python virtual environment (.venv)..." -ForegroundColor Yellow
    Invoke-Expression "$PythonCmd -m venv .venv"
}

if (-Not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Virtual environment creation failed." -ForegroundColor Red
    Exit 1
}

Write-Host "[+] Virtual environment active: $VenvPython" -ForegroundColor Green

# 4. Install Dependencies
Write-Host "[*] Installing and verifying Core AI dependencies from requirements.txt..." -ForegroundColor Yellow
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r requirements.txt --quiet
Write-Host "[+] Dependencies verified successfully." -ForegroundColor Green

# 5. Execute Interactive Setup Wizard & Launch
Write-Host ""
Write-Host "[*] Launching Core AI Setup Wizard..." -ForegroundColor Cyan
& $VenvPython interfaces\install\setup_service.py
