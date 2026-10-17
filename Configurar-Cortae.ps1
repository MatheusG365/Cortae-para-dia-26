$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'Backend'
$frontendPath = Join-Path $projectRoot 'Frontend'
$pythonPath = Join-Path $backendPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $pythonCommand) { throw 'Instale Python 3.12 ou superior e adicione ao PATH.' }
    & $pythonCommand.Source -m venv (Join-Path $backendPath '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o ambiente Python.' }
}
$requirementsPath = Join-Path $backendPath 'requirements-lock.txt'
if (-not (Test-Path -LiteralPath $requirementsPath)) { $requirementsPath = Join-Path $backendPath 'requirements.txt' }
& $pythonPath -m pip install -r $requirementsPath
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências do backend.' }
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
Write-Host 'Dependências instaladas. Execute Iniciar-Cortae.cmd.'
