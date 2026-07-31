# Inicia el servidor vLLM para GLM-OCR en Windows.
# Requiere vllm-windows (no el paquete oficial de PyPI).

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $ProjectRoot ".venv"
$CudaRoot = Join-Path $Venv "Lib\site-packages\nvidia\cu13"
$X64Link = Join-Path $CudaRoot "bin\x64"
$X86Dir = Join-Path $CudaRoot "bin\x86_64"

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

$Vllm = Join-Path $Venv "Scripts\vllm.exe"
if (-not (Test-Path $Vllm)) {
    Write-Error "No se encontró vllm.exe en $Vllm"
}

$Port = if ($env:VLLM_PORT) { $env:VLLM_PORT } else { "8080" }
$GpuMem = if ($env:VLLM_GPU_MEMORY_UTILIZATION) { $env:VLLM_GPU_MEMORY_UTILIZATION } else { "0.85" }

# Detener instancias previas de vLLM que dejen puertos ZMQ/HTTP ocupados.
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

$SpecConfig = '{\"method\": \"mtp\", \"num_speculative_tokens\": 3}'

& $Vllm serve zai-org/GLM-OCR `
    --port $Port `
    --speculative-config $SpecConfig `
    --served-model-name glm-ocr `
    --gpu-memory-utilization $GpuMem `
    @args
