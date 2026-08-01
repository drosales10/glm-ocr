# Arranca Ollama, pipeline SDK, backend (uvicorn) y frontend (pnpm)
# en ventanas de PowerShell separadas.
# El frontend se lanza DESPUES de que pipeline/backend respondan.
#
# Uso (desde la raiz del repo):
#   .\scripts\start-app.ps1
#   .\scripts\start-app.ps1 -SkipOllama
#   .\scripts\start-app.ps1 -ForceRestart   # mata procesos en 5002/8000/3006 y relanza
#   .\scripts\start-app.ps1 -Config config.ollama.yaml
#   .\scripts\start-app.ps1 -NoBrowser

param(
    [switch]$SkipOllama,
    [string]$Config = "config.yaml",
    [switch]$NoBrowser,
    [switch]$ForceRestart,
    [int]$ReadyTimeoutSec = 120
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "apps\backend"
$FrontendDir = Join-Path $ProjectRoot "apps\frontend"
$ConfigPath = Join-Path $ProjectRoot $Config
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FrontendUrl = "http://localhost:3006"
$PipelineHealth = "http://127.0.0.1:5002/health"
$BackendDocs = "http://127.0.0.1:8000/docs"

$ToolDirs = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama"),
    (Join-Path $env:USERPROFILE ".local\bin"),
    (Join-Path $ProjectRoot ".venv\Scripts"),
    (Join-Path $env:LOCALAPPDATA "pnpm"),
    (Join-Path $env:APPDATA "npm"),
    "C:\Program Files\nodejs",
    (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links")
) | Where-Object { $_ -and (Test-Path $_) }

foreach ($dir in $ToolDirs) {
    if ($env:Path -notlike "*$dir*") {
        $env:Path = "$dir;$env:Path"
    }
}

function Resolve-Tool {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string[]]$Candidates = @()
    )
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }
    foreach ($c in $Candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) {
            return (Resolve-Path -LiteralPath $c).Path
        }
    }
    return $null
}

function Test-PortInUse {
    param([int]$Port)
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Stop-PortListeners {
    param([int[]]$Ports)
    foreach ($port in $Ports) {
        $pids = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
        foreach ($procId in $pids) {
            try {
                $proc = Get-Process -Id $procId -ErrorAction Stop
                Write-Host "Deteniendo PID $procId ($($proc.ProcessName)) en puerto $port ..." -ForegroundColor Yellow
                Stop-Process -Id $procId -Force -ErrorAction Stop
            }
            catch {
                Write-Warning "No se pudo detener PID $procId en puerto $port"
            }
        }
    }
    Start-Sleep -Seconds 2
}

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSec = 120
    )
    Write-Host "Esperando $Name ($Url) ..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                Write-Host "Listo: $Name" -ForegroundColor Green
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    Write-Warning "Timeout esperando $Name tras ${TimeoutSec}s. Se continua igual."
    return $false
}

function Start-ServiceWindow {
    param(
        [string]$Title,
        [string]$WorkingDirectory,
        [string]$Command
    )
    $pathEscaped = $env:Path.Replace("'", "''")
    $psCommand = @"
`$env:Path = '$pathEscaped'
`$Host.UI.RawUI.WindowTitle = '$Title'
Set-Location -LiteralPath '$WorkingDirectory'
Write-Host '=== $Title ===' -ForegroundColor Cyan
Write-Host 'Directorio: $WorkingDirectory'
Write-Host 'Comando: $Command'
Write-Host ''
$Command
"@
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoExit",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", $psCommand
    ) | Out-Null
    Write-Host "Iniciado: $Title" -ForegroundColor Green
}

$OllamaExe = Resolve-Tool -Name "ollama" -Candidates @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe")
)
$UvExe = Resolve-Tool -Name "uv" -Candidates @(
    (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
    (Join-Path $ProjectRoot ".venv\Scripts\uv.exe")
)
$PnpmCmd = Resolve-Tool -Name "pnpm" -Candidates @(
    "C:\Program Files\nodejs\pnpm.CMD",
    "C:\Program Files\nodejs\pnpm.cmd"
)

Write-Host "GLM-OCR - arranque local" -ForegroundColor Cyan
Write-Host "Raiz: $ProjectRoot"
Write-Host ""

if ($ForceRestart) {
    Write-Host "ForceRestart: liberando puertos 5002/8000/3006 ..." -ForegroundColor Yellow
    Stop-PortListeners -Ports @(5002, 8000, 3006)
}

# --- 1) Ollama (:11434) ---
if ($SkipOllama) {
    Write-Host "Ollama omitido (-SkipOllama)." -ForegroundColor Yellow
}
elseif (Test-PortInUse -Port 11434) {
    Write-Host "Ollama ya escucha en :11434 - no se abre otra ventana." -ForegroundColor Yellow
}
else {
    if (-not $OllamaExe) {
        Write-Warning "No se encontro 'ollama'. Instalalo o usa -SkipOllama."
    }
    else {
        Start-ServiceWindow -Title "GLM-OCR Ollama" -WorkingDirectory $ProjectRoot -Command "& '$OllamaExe' serve"
    }
}

# --- 2) Pipeline SDK glmocr.server (:5002) ---
if (-not (Test-Path $ConfigPath)) {
    Write-Error "No se encontro la config: $ConfigPath"
}
if (Test-PortInUse -Port 5002) {
    Write-Warning "El puerto 5002 ya esta en uso. Usa -ForceRestart para relanzar el pipeline."
}
if (Test-Path $VenvPython) {
    $PipelineCmd = "& '$VenvPython' -m glmocr.server --config '$Config'"
}
elseif ($UvExe) {
    $PipelineCmd = "& '$UvExe' run python -m glmocr.server --config '$Config'"
}
else {
    Write-Error "No hay .venv ni 'uv' para arrancar glmocr.server."
}
if (-not (Test-PortInUse -Port 5002)) {
    Start-ServiceWindow `
        -Title "GLM-OCR Pipeline :5002" `
        -WorkingDirectory $ProjectRoot `
        -Command $PipelineCmd
}

# --- 3) Backend uvicorn (:8000) ---
if (-not (Test-Path $BackendDir)) {
    Write-Error "No existe apps\backend: $BackendDir"
}
if (-not $UvExe) {
    Write-Error "No se encontro 'uv'. Ruta esperada: $env:USERPROFILE\.local\bin\uv.exe"
}
if (-not (Test-PortInUse -Port 8000)) {
    Start-ServiceWindow `
        -Title "GLM-OCR Backend :8000" `
        -WorkingDirectory $BackendDir `
        -Command "& '$UvExe' run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
}
else {
    Write-Host "Backend ya escucha en :8000." -ForegroundColor Yellow
}

Write-Host ""
[void](Wait-HttpReady -Name "Pipeline" -Url $PipelineHealth -TimeoutSec $ReadyTimeoutSec)
[void](Wait-HttpReady -Name "Backend" -Url $BackendDocs -TimeoutSec $ReadyTimeoutSec)

# --- 4) Frontend pnpm (:3006) ---
Write-Host ""
Write-Host "Lanzando frontend..." -ForegroundColor Cyan
if (-not (Test-Path $FrontendDir)) {
    Write-Error "No existe apps\frontend: $FrontendDir"
}
if (-not $PnpmCmd) {
    Write-Error "No se encontro 'pnpm' en el PATH ni en Program Files\nodejs."
}
if (-not (Test-PortInUse -Port 3006)) {
    Start-ServiceWindow `
        -Title "GLM-OCR Frontend" `
        -WorkingDirectory $FrontendDir `
        -Command "& '$PnpmCmd' dev"
}
else {
    Write-Host "Frontend ya escucha en :3006." -ForegroundColor Yellow
}

[void](Wait-HttpReady -Name "Frontend" -Url $FrontendUrl -TimeoutSec $ReadyTimeoutSec)

if (-not $NoBrowser) {
    Write-Host "Abriendo navegador: $FrontendUrl" -ForegroundColor Cyan
    Start-Process $FrontendUrl
}

Write-Host ""
Write-Host "Listo. URLs:" -ForegroundColor Cyan
Write-Host "  Ollama:    http://127.0.0.1:11434"
Write-Host "  Pipeline:  $PipelineHealth"
Write-Host "  Backend:   $BackendDocs"
Write-Host "  Frontend:  $FrontendUrl"