# Shared interpreter checks for setup and startup. No global Python changes.
function Get-CortaePythonInfo([string]$PythonPath) {
    if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { return $null }
    try {
        $output = & $PythonPath -I -c 'import json,struct,sys; print(json.dumps(dict(bits=struct.calcsize(''P'')*8,major=sys.version_info.major,minor=sys.version_info.minor,version=sys.version.split()[0],executable=sys.executable)))' 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        return ($output | ConvertFrom-Json)
    } catch { return $null }
}

function Test-CortaePythonInfo($Info) {
    return ($null -ne $Info -and $Info.bits -eq 32 -and
        ($Info.major -gt 3 -or ($Info.major -eq 3 -and $Info.minor -ge 12)))
}

function Assert-CortaePython([string]$PythonPath) {
    $info = Get-CortaePythonInfo $PythonPath
    if (-not (Test-CortaePythonInfo $info)) {
        $detected = if ($info) { "$($info.version), $($info.bits) bits" } else { 'indisponivel' }
        throw "Backend exige Python 3.12 ou superior, 32 bits. Encontrado: $detected em '$PythonPath'. Execute Configurar-Cortae.ps1 -PythonPath <python.exe de 32 bits>."
    }
    return $info
}

function Resolve-CortaePython([string]$PythonPath = '') {
    if ($PythonPath) {
        $resolved = (Resolve-Path -LiteralPath $PythonPath -ErrorAction Stop).Path
        $null = Assert-CortaePython $resolved
        return $resolved
    }
    $candidates = @()
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        # Prefer the verified 3.12 x86 series even when the launcher defaults to x64.
        try {
            $preferred = & $launcher.Source -3.12-32 -I -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { $candidates += $preferred }
        } catch { }
        try {
            $installed = & $launcher.Source -0p 2>$null
            if ($LASTEXITCODE -eq 0) {
                foreach ($line in $installed) {
                    if ($line -match '^\s*-\S+\s+\*?\s*(.+?python(?:\d+(?:\.\d+)?)?\.exe)\s*$') {
                        $candidates += $Matches[1]
                    }
                }
            }
        } catch { }
    }
    $candidates += @(Get-Command python.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source })
    if ($env:LOCALAPPDATA) {
        $installRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
        $candidates += @(Get-ChildItem -LiteralPath $installRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^Python\d+-32$' } |
            Sort-Object Name | ForEach-Object { Join-Path $_.FullName 'python.exe' })
    }
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        $info = Get-CortaePythonInfo $candidate
        if (Test-CortaePythonInfo $info) { return [string]$info.executable }
    }
    throw 'Python 3.12 ou superior, 32 bits, nao encontrado. Instale a edicao Windows x86 ou informe -PythonPath <python.exe de 32 bits>.'
}

function New-CortaeVirtualEnvironment([string]$BasePython, [string]$EnvironmentPath) {
    & $BasePython -I -m venv $EnvironmentPath
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python de 32 bits.' }
}

function Initialize-CortaePythonEnvironment([string]$BackendPath, [string]$PythonPath = '') {
    $backend = [IO.Path]::GetFullPath($BackendPath)
    $environment = Join-Path $backend '.venv'
    $interpreter = Join-Path $environment 'Scripts\python.exe'
    # An explicit override is always checked, including when a valid venv exists.
    $basePython = if ($PythonPath) { Resolve-CortaePython $PythonPath } else { $null }
    if (Test-CortaePythonInfo (Get-CortaePythonInfo $interpreter)) { return $interpreter }
    if (-not $basePython) { $basePython = Resolve-CortaePython }
    # Resolve a valid base interpreter before moving an existing environment.
    # A venv cannot be its own migration source because its executable will move.
    if ([IO.Path]::GetFullPath($basePython).StartsWith($environment + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Informe um Python de 32 bits instalado fora de Backend\.venv.'
    }
    $archiveRoot = Join-Path (Split-Path -Parent $backend) '.runtime\python-environments'
    $backup = $null
    if (Test-Path -LiteralPath $environment) {
        New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
        $backup = Join-Path $archiveRoot ('venv-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N'))
        Move-Item -LiteralPath $environment -Destination $backup
        Write-Host "Ambiente anterior preservado em: $backup"
    }
    try {
        New-CortaeVirtualEnvironment $basePython $environment
        $null = Assert-CortaePython $interpreter
    } catch {
        $creationError = $_
        if (Test-Path -LiteralPath $environment) {
            New-Item -ItemType Directory -Path $archiveRoot -Force | Out-Null
            $failed = Join-Path $archiveRoot ('venv-failed-' + [Guid]::NewGuid().ToString('N'))
            Move-Item -LiteralPath $environment -Destination $failed
            Write-Host "Tentativa incompleta preservada em: $failed"
        }
        if ($backup) {
            Move-Item -LiteralPath $backup -Destination $environment
            Write-Host 'Ambiente anterior restaurado em Backend\.venv.'
        }
        throw $creationError
    }
    return $interpreter
}
