#Requires -Version 5.1

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Info    { param($msg) Write-Host "  " -NoNewline; Write-Host "[*]" -ForegroundColor Cyan -NoNewline; Write-Host " $msg" }
function Success { param($msg) Write-Host "  " -NoNewline; Write-Host "[+]" -ForegroundColor Green -NoNewline; Write-Host " $msg" }
function Warn    { param($msg) Write-Host "  " -NoNewline; Write-Host "[!]" -ForegroundColor Yellow -NoNewline; Write-Host " $msg" }
function Err     { param($msg) Write-Host "  " -NoNewline; Write-Host "[-]" -ForegroundColor Red -NoNewline; Write-Host " $msg"; exit 1 }
function Section { param($msg) Write-Host ""; Write-Host "── $msg ──" -ForegroundColor Cyan }

Write-Host ""
Write-Host "  ██████╗ ███████╗██╗  ██╗     ██████╗ ███████╗██╗███╗   ██╗████████╗" -ForegroundColor Red
Write-Host "  ██╔══██╗██╔════╝╚██╗██╔╝    ██╔═══██╗██╔════╝██║████╗  ██║╚══██╔══╝" -ForegroundColor Red
Write-Host "  ██████╔╝███████╗ ╚███╔╝     ██║   ██║███████╗██║██╔██╗ ██║   ██║   " -ForegroundColor Red
Write-Host "  ██╔══██╗╚════██║ ██╔██╗     ██║   ██║╚════██║██║██║╚██╗██║   ██║   " -ForegroundColor Red
Write-Host "  ██║  ██║███████║██╔╝ ██╗    ╚██████╔╝███████║██║██║ ╚████║   ██║   " -ForegroundColor Red
Write-Host "  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝    ╚═════╝ ╚══════╝╚═╝╚═╝  ╚═══╝   ╚═╝  " -ForegroundColor Red
Write-Host ""
Write-Host "  Advanced Breach & Dark Web Intelligence Framework" -ForegroundColor Cyan
Write-Host "  Installer v2.0" -ForegroundColor White
Write-Host ""

Section "Detecting environment"
$OS   = [System.Environment]::OSVersion.VersionString
$ARCH = if ([System.Environment]::Is64BitOperatingSystem) { "x64" } else { "x86" }
Info "OS: $OS  |  Arch: $ARCH"

Section "Checking Python"
$PYTHON = $null
foreach ($cmd in @("python3.12", "python3.11", "python3.10", "python3", "python")) {
    try {
        $ver = & $cmd -c "import sys; print('{}.{}'.format(*sys.version_info[:2]))" 2>$null
        if ($ver -match "^(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 10) {
                $PYTHON = $cmd
                Success "Found $cmd ($ver)"
                break
            } else {
                Warn "$cmd is $ver — need 3.10+"
            }
        }
    } catch {}
}
if (-not $PYTHON) {
    Err "Python 3.10+ not found.`n  Download from: https://www.python.org/downloads/`n  Make sure to check 'Add Python to PATH' during install."
}

Section "Checking pip"
try {
    & $PYTHON -m pip --version 2>$null | Out-Null
    $pipVer = & $PYTHON -m pip --version
    Success "pip: $($pipVer -replace '\s+from.*','')"
} catch {
    Err "pip not found. Re-install Python and ensure pip is included."
}

Section "Checking for Tor"
$torPath = Get-Command "tor" -ErrorAction SilentlyContinue
if ($torPath) {
    $torVer = & tor --version 2>&1 | Select-Object -First 1
    Success "Tor found: $torVer"
} else {
    Warn "Tor not found in PATH."
    Warn "Download the Tor Expert Bundle from: https://www.torproject.org/download/tor/"
    Warn "Extract it and add the folder to your PATH, or run tor.exe manually before using dark web mode."
    Warn "Default SOCKS5 port: 127.0.0.1:9050"
}

Section "Setting up virtual environment"
$VENV_DIR = Join-Path (Get-Location) "venv"

if (Test-Path $VENV_DIR) {
    Warn "venv already exists at $VENV_DIR — skipping creation"
} else {
    & $PYTHON -m venv $VENV_DIR
    Success "Created venv at $VENV_DIR"
}

$PYTHON_VENV = Join-Path $VENV_DIR "Scripts\python.exe"
$PIP_VENV    = Join-Path $VENV_DIR "Scripts\pip.exe"

if (-not (Test-Path $PYTHON_VENV)) {
    Err "venv python not found at $PYTHON_VENV — venv creation may have failed."
}

Success "venv ready — using $PYTHON_VENV"

Section "Upgrading pip inside venv"
& $PIP_VENV install --upgrade pip setuptools wheel -q
Success "pip upgraded"

Section "Installing Python dependencies"
if (-not (Test-Path "requirements.txt")) {
    Err "requirements.txt not found. Run this script from the rsx-osint directory."
}
Info "Installing from requirements.txt..."
& $PIP_VENV install -r requirements.txt
Success "All Python packages installed"

Section "Playwright (optional)"
$playwrightEnabled = $false
try {
    $yamlContent = Get-Content "config\settings.yaml" -Raw
    if ($yamlContent -match "use_playwright:\s*true") {
        $playwrightEnabled = $true
    }
} catch {}

$PLAYWRIGHT_EXE = Join-Path $VENV_DIR "Scripts\playwright.exe"
if ($playwrightEnabled) {
    Info "use_playwright is enabled — installing Firefox browser..."
    & $PLAYWRIGHT_EXE install firefox
    Success "Playwright Firefox installed"
} else {
    Info "use_playwright is false in settings.yaml — skipping"
    Info "To enable later: set use_playwright: true then run:  playwright install firefox"
}

Section "Creating output directories"
New-Item -ItemType Directory -Force -Path "output\results" | Out-Null
Success "output\results\ ready"

Section "Verifying Tor connectivity"
if ($torPath) {
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $connect   = $tcpClient.BeginConnect("127.0.0.1", 9050, $null, $null)
        $waited    = $connect.AsyncWaitHandle.WaitOne(5000, $false)
        if ($waited -and $tcpClient.Connected) {
            Success "Tor SOCKS5 is reachable on 127.0.0.1:9050"
        } else {
            Warn "Tor SOCKS5 not reachable on port 9050 — start tor.exe first"
        }
        $tcpClient.Close()
    } catch {
        Warn "Could not test Tor connectivity — start tor.exe before using dark web mode"
    }
} else {
    Warn "Tor not installed — skipping connectivity check"
}

Section "Verifying installation"
$verifyScript = @"
mods = [
    'aiohttp','bs4','rich','yaml','requests',
    'modules.utils.config','modules.utils.tui','modules.utils.dedup',
    'modules.dorking.engines','modules.darkweb.engines','modules.darkweb.crawler',
    'modules.scraper.breach','modules.scraper.paste',
]
ok, fail = [], []
for m in mods:
    try: __import__(m); ok.append(m)
    except Exception as e: fail.append((m, str(e)))
print(f'PASS:{len(ok)} FAIL:{len(fail)}')
for m,e in fail: print(f'  FAIL {m}: {e}')
"@

$verify = & $PYTHON_VENV -c $verifyScript 2>&1
if ($verify -match "FAIL:0") {
    Success "All modules import successfully"
} else {
    Warn "Some modules had import errors:"
    $verify | Where-Object { $_ -match "FAIL" } | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
}

Section "Creating launcher"
$runScript = @"
@echo off
call "%~dp0venv\Scripts\activate.bat"
python "%~dp0main.py" %*
"@
Set-Content -Path "run.bat" -Value $runScript -Encoding ASCII
Success "Created run.bat launcher"

$runPs1 = @"
`$dir = Split-Path -Parent `$MyInvocation.MyCommand.Path
& "`$dir\venv\Scripts\Activate.ps1"
python "`$dir\main.py" @args
"@
Set-Content -Path "run.ps1" -Value $runPs1 -Encoding UTF8
Success "Created run.ps1 launcher"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  Run interactive TUI:" -ForegroundColor White
Write-Host "    .\run.bat" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Or with flags:" -ForegroundColor White
Write-Host "    .\run.bat -q user@example.com -t email --clearnet" -ForegroundColor Cyan
Write-Host "    .\run.bat -q targetuser -t username --both --tor 127.0.0.1:9050" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Optional — add API keys in:" -ForegroundColor White
Write-Host "    config\settings.yaml  (api_keys section)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Optional — add proxies for dork rotation:" -ForegroundColor White
Write-Host "    config\proxies.txt  (one per line)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Tor for Windows:" -ForegroundColor White
Write-Host "    https://www.torproject.org/download/tor/" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
