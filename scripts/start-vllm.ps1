# Inicia el servidor vLLM para GLM-OCR en Windows (RTX / CUDA).
# Requiere vllm-windows en .venv y VS Build Tools (cl.exe) para FlashInfer en RTX 50.
#
# Uso:
#   .\scripts\start-vllm.ps1
#   .\scripts\start-vllm.ps1 -GpuMemory 0.65 -MaxModelLen 4096

param(
    [double]$GpuMemory = 0.70,
    [int]$MaxModelLen = 8192,
    [switch]$EnableSpeculative
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $ProjectRoot ".venv"
$CudaRoot = Join-Path $Venv "Lib\site-packages\nvidia\cu13"
$X64Link = Join-Path $CudaRoot "bin\x64"
$X86Dir = Join-Path $CudaRoot "bin\x86_64"

# FlashInfer JIT necesita cl.exe (MSVC) en PATH — RTX 50 / sm_120
$MsvcRoots = @(
    "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\BuildTools\VC\Tools\MSVC",
    "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC"
)
$ClDir = $null
foreach ($root in $MsvcRoots) {
    if (Test-Path $root) {
        $found = Get-ChildItem $root -Recurse -Filter cl.exe -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\Hostx64\\x64\\cl\.exe$' } |
            Select-Object -First 1
        if ($found) {
            $ClDir = $found.Directory.FullName
            break
        }
    }
}
if ($ClDir) {
    $env:PATH = "$ClDir;$env:PATH"
    Write-Host "MSVC cl.exe: $ClDir"
} else {
    Write-Warning "No se encontró cl.exe. FlashInfer puede fallar en RTX 50. Instala VS Build Tools (C++)."
}

if (-not (Test-Path $CudaRoot)) {
    Write-Error "No se encontró CUDA en el venv ($CudaRoot). Reinstala vllm-windows."
}

if (-not (Test-Path $X64Link) -and (Test-Path $X86Dir)) {
    cmd /c mklink /J "$X64Link" "$X86Dir" | Out-Null
}

$env:CUDA_HOME = $CudaRoot
$env:CUDA_PATH = $CudaRoot
$env:CUDA_LIB_PATH = Join-Path $CudaRoot "bin\x64"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:VLLM_HOST_IP = "127.0.0.1"

$Vllm = Join-Path $Venv "Scripts\vllm.exe"
if (-not (Test-Path $Vllm)) {
    Write-Error "No se encontró vllm.exe en $Vllm"
}

$Port = if ($env:VLLM_PORT) { $env:VLLM_PORT } else { "8080" }
if ($env:VLLM_GPU_MEMORY_UTILIZATION) {
    $GpuMemory = [double]$env:VLLM_GPU_MEMORY_UTILIZATION
}
if ($env:VLLM_MAX_MODEL_LEN) {
    $MaxModelLen = [int]$env:VLLM_MAX_MODEL_LEN
}

$StalePids = @(
    Get-NetTCPConnection -LocalPort $Port,29550,29520 -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    Get-Process python,vllm -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "$Venv*" } |
        Select-Object -ExpandProperty Id
) | Select-Object -Unique

foreach ($ProcId in $StalePids) {
    if ($ProcId -and $ProcId -ne $PID) {
        Write-Host "Deteniendo proceso vLLM anterior (PID $ProcId)..."
        Stop-Process -Id $ProcId -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

Write-Host "Iniciando vLLM GLM-OCR en :$Port (GPU mem=$GpuMemory, max-len=$MaxModelLen)..."

$VllmArgs = @(
    "serve", "zai-org/GLM-OCR",
    "--host", "127.0.0.1",
    "--port", $Port,
    "--served-model-name", "glm-ocr",
    "--gpu-memory-utilization", "$GpuMemory",
    "--max-model-len", "$MaxModelLen"
)

if ($EnableSpeculative) {
    $SpecFile = Join-Path $env:TEMP "vllm-spec-glm-ocr.json"
    '{"method":"mtp","num_speculative_tokens":3}' | Set-Content -Path $SpecFile -Encoding ascii
    $VllmArgs += @("--speculative-config", $SpecFile)
    Write-Host "Speculative decoding MTP activado"
}

& $Vllm @VllmArgs @args
