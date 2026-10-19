param(
    [ValidateRange(0, 65535)][int]$ApiPort = 0,
    [ValidateRange(1, 65535)][int]$FrontendPort = 5173,
    [string]$ApiHost = '',
    [string]$FrontendHost = '0.0.0.0'
)

$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot

function Get-BackendSetting([string]$Name, [string]$Default) {
    $configured = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ($null -ne $configured) { return $configured }
    $value = $Default
    $envFile = Join-Path $projectRoot 'Backend\.env'
    if (Test-Path -LiteralPath $envFile) {
        $pattern = '^\s*(?:export\s+)?' + [regex]::Escape($Name) + '\s*=(.*)$'
        foreach ($line in [IO.File]::ReadLines($envFile)) {
            if ($line -match $pattern) {
                $candidate = $Matches[1].Trim()
                if ($candidate -match '^["'']([^"'']*)["'']\s*(?:#.*)?$') {
                    $value = $Matches[1]
                } else {
                    $value = ($candidate -replace '\s+#.*$', '').Trim()
                }
            }
        }
    }
    return $value
}

function Restore-ProcessSetting([string]$Name, $Value) {
    if ($null -eq $Value) {
        Remove-Item -LiteralPath "Env:$Name" -ErrorAction SilentlyContinue
    } else {
        [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
    }
}

if ($ApiPort -eq 0) {
    $configuredPort = Get-BackendSetting 'PORT' '5000'
    $parsedPort = 0
    if (-not [int]::TryParse($configuredPort, [ref]$parsedPort) -or $parsedPort -lt 1 -or $parsedPort -gt 65535) {
        throw 'PORT deve ser um número entre 1 e 65535.'
    }
    $ApiPort = $parsedPort
}
if (-not $ApiHost) { $ApiHost = Get-BackendSetting 'API_HOST' '0.0.0.0' }
if (-not $ApiHost.Trim()) { $ApiHost = '0.0.0.0' }
$ApiHost = $ApiHost.Trim()
$FrontendHost = $FrontendHost.Trim()
if (-not $FrontendHost) { throw 'FrontendHost não pode ficar vazio.' }
if ($ApiPort -eq $FrontendPort) { throw 'A API e o frontend precisam usar portas diferentes.' }
$probeHost = switch ($ApiHost) {
    '0.0.0.0' { '127.0.0.1' }
    '::' { '[::1]' }
    default { if ($ApiHost.Contains(':')) { "[$ApiHost]" } else { $ApiHost } }
}
$frontendProbeHost = switch ($FrontendHost) {
    '0.0.0.0' { '127.0.0.1' }
    '::' { '[::1]' }
    default { if ($FrontendHost.Contains(':')) { "[$FrontendHost]" } else { $FrontendHost } }
}
$apiUrl = "http://${probeHost}:$ApiPort"
$frontendUrl = "http://${frontendProbeHost}:$FrontendPort"
$runtimePath = Join-Path $projectRoot '.runtime'
$statePath = Join-Path $runtimePath 'processes.json'
if (Test-Path -LiteralPath $statePath) {
    try { $previousStates = @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json) }
    catch { $previousStates = @() }
    foreach ($state in $previousStates) {
        try {
            $registeredId = [int]$state.Pid
            $registeredScript = [IO.Path]::GetFullPath($state.Script)
            if ($registeredId -lt 1 -or -not $registeredScript.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { continue }
            $existing = Get-Process -Id $registeredId -ErrorAction SilentlyContinue
            if (-not $existing) { continue }
            $registeredStart = ([DateTimeOffset]$state.Started).UtcDateTime
            $sameStart = [Math]::Abs(($existing.StartTime.ToUniversalTime() - $registeredStart).TotalSeconds) -lt 1
            $command = Get-CimInstance Win32_Process -Filter "ProcessId = $registeredId" -ErrorAction SilentlyContinue
            $ownsScript = $command.CommandLine -and $command.CommandLine.IndexOf($registeredScript, [StringComparison]::OrdinalIgnoreCase) -ge 0
        } catch { continue }
        if ($sameStart -and $ownsScript) {
            throw 'Este projeto já está em execução. Execute Parar-Cortae.cmd antes de iniciar novamente.'
        }
    }
    # Keep residual records for inspection, without blocking after a crash or killing PIDs.
    $previousStatePath = Join-Path $runtimePath ('processes-anterior-' + [Guid]::NewGuid().ToString('N') + '.json')
    Copy-Item -LiteralPath $statePath -Destination $previousStatePath
}
$pythonPath = Join-Path $projectRoot 'Backend\.venv\Scripts\python.exe'
. (Join-Path $projectRoot 'Python-Cortae.ps1')
$null = Assert-CortaePython $pythonPath
$mainPath = Join-Path $projectRoot 'Backend\main.py'
$vitePath = Join-Path $projectRoot 'Frontend\node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path -LiteralPath $vitePath)) {
    throw 'Dependências ausentes. Execute Configurar-Cortae.cmd primeiro.'
}
$nodePath = (Get-Command node.exe -ErrorAction Stop).Source
foreach ($port in @($ApiPort, $FrontendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "A porta $port já está em uso. Pare o processo correspondente antes de iniciar."
    }
}
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
$processes = @()
$previousPort = [Environment]::GetEnvironmentVariable('PORT', 'Process')
$previousHost = [Environment]::GetEnvironmentVariable('API_HOST', 'Process')
$previousProxy = [Environment]::GetEnvironmentVariable('CORTAE_API_PROXY_TARGET', 'Process')
try {
    $env:PORT = [string]$ApiPort
    $env:API_HOST = $ApiHost
    $env:CORTAE_API_PROXY_TARGET = $apiUrl
    $backend = Start-Process -FilePath $pythonPath -ArgumentList @('-u', ('"' + $mainPath + '"')) -WorkingDirectory (Join-Path $projectRoot 'Backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'backend.log') -RedirectStandardError (Join-Path $runtimePath 'backend-error.log')
    $processes += @{ Pid = $backend.Id; Script = $mainPath; Started = $backend.StartTime.ToUniversalTime().ToString('o') }
    $processes | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimePath 'processes.json') -Encoding UTF8
    $frontend = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $vitePath + '"'), '--host', $FrontendHost, '--port', [string]$FrontendPort, '--strictPort') -WorkingDirectory (Join-Path $projectRoot 'Frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimePath 'frontend.log') -RedirectStandardError (Join-Path $runtimePath 'frontend-error.log')
    $processes += @{ Pid = $frontend.Id; Script = $vitePath; Started = $frontend.StartTime.ToUniversalTime().ToString('o') }
    $processes | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimePath 'processes.json') -Encoding UTF8
    $ready = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Seconds 1
        try {
            $health = Invoke-RestMethod -Uri "$apiUrl/health" -TimeoutSec 2
            $front = Invoke-WebRequest -Uri "$frontendUrl/" -TimeoutSec 2 -UseBasicParsing
            if ($health.pronto -and $front.StatusCode -eq 200) { $ready = $true; break }
        } catch { }
        if ($backend.HasExited -or $frontend.HasExited) { break }
    }
    if (-not $ready) { throw 'Falha ao iniciar. Consulte .runtime\backend-error.log e frontend-error.log.' }
    Write-Host "Cortaê neste computador: $frontendUrl"
    Write-Host "Saúde: $apiUrl/health"
    Write-Host "Documentação: $apiUrl/docs"
    if ($FrontendHost -eq '0.0.0.0' -or $FrontendHost -eq '::') {
        Write-Host "Na mesma rede: http://<IP-atual-deste-computador>:$FrontendPort"
    }
} catch {
    & (Join-Path $projectRoot 'Parar-Cortae.ps1')
    throw
} finally {
    Restore-ProcessSetting 'PORT' $previousPort
    Restore-ProcessSetting 'API_HOST' $previousHost
    Restore-ProcessSetting 'CORTAE_API_PROXY_TARGET' $previousProxy
}
