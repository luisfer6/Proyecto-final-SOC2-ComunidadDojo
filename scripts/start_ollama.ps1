$ErrorActionPreference = 'Stop'
$socRoot = Split-Path -Parent $PSScriptRoot
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_MODELS = Join-Path $socRoot 'artifacts/ollama-models'
$env:OLLAMA_NO_CLOUD = '1'
$socModel = if ($env:OLLAMA_MODEL) { $env:OLLAMA_MODEL } else { 'qwen3:4b' }
$socBinary = Join-Path $socRoot 'artifacts/ollama-runtime/ollama.exe'
if (-not (Test-Path -LiteralPath $socBinary)) {
    $socInstalled = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $socInstalled) { throw 'Instala Ollama desde https://ollama.com/download y descarga qwen3:4b.' }
    $socBinary = $socInstalled.Source
}
try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 }
catch {
    Start-Process -FilePath $socBinary -ArgumentList 'serve' -WorkingDirectory $socRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $socRoot 'artifacts/ollama.out.log') -RedirectStandardError (Join-Path $socRoot 'artifacts/ollama.err.log') | Out-Null
    $socReady = $false
    for ($socAttempt=0; $socAttempt -lt 30; $socAttempt++) {
        try { $null = Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2; $socReady=$true; break }
        catch { Start-Sleep -Seconds 1 }
    }
    if (-not $socReady) { throw 'Ollama no pudo iniciar. Revisa artifacts/ollama.err.log.' }
}
$socTags = Invoke-RestMethod 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
if ($socModel -notin $socTags.models.name) {
    Write-Host "Descargando el modelo local $socModel..."
    & $socBinary pull $socModel
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo descargar Qwen3.' }
}
Write-Host 'Ollama y Qwen3 estan disponibles en este equipo.'
