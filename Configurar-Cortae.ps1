param([string]$PythonPath = '')

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'Backend'
$frontendPath = Join-Path $projectRoot 'Frontend'
. (Join-Path $projectRoot 'Python-Cortae.ps1')
$backendPython = Initialize-CortaePythonEnvironment $backendPath $PythonPath
$requirementsPath = Join-Path $backendPath 'requirements-lock.txt'
if (-not (Test-Path -LiteralPath $requirementsPath)) { $requirementsPath = Join-Path $backendPath 'requirements.txt' }
& $backendPython -m pip install -r $requirementsPath
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências do backend.' }
& $backendPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependencias Python inconsistentes; consulte a saida de pip check.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Instale Node.js 22 ou superior com npm.' }
Push-Location $frontendPath
try {
    & npm.cmd ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências do frontend.' }
} finally { Pop-Location }
if (-not (Test-Path -LiteralPath (Join-Path $backendPath '.env'))) {
    Copy-Item -LiteralPath (Join-Path $backendPath '.env.example') -Destination (Join-Path $backendPath '.env')
    Write-Host 'Preencha Backend\.env antes de iniciar.'
}
. (Join-Path $projectRoot 'Firebird-Cortae.ps1')
Initialize-CortaeFirebird $projectRoot $backendPython
Write-Host 'Dependências instaladas. Execute Iniciar-Cortae.cmd.'
