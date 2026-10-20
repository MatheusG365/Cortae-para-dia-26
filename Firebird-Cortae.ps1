# Portable application server only; never registers a service or replaces a database.
$script:CortaeFirebirdVersion = '4.0.4.3010'
$script:CortaeFirebirdHash = 'A66C34098FC0BE315C653745B9D4B455B7F1CEC9F556D8F88FBB12919716F533'
$script:CortaeFirebirdUrl = 'https://github.com/FirebirdSQL/firebird/releases/download/v4.0.4/Firebird-4.0.4.3010-0-Win32.zip'

function Get-CortaeSetting([string]$ProjectRoot, [string]$Name, [string]$Default = '') {
    $value = [Environment]::GetEnvironmentVariable($Name, 'Process')
    if ($null -ne $value) { return $value }
    $value = $Default
    $file = Join-Path $ProjectRoot 'Backend\.env'
    if (Test-Path -LiteralPath $file) {
        $pattern = '^\s*(?:export\s+)?' + [regex]::Escape($Name) + '\s*=(.*)$'
        foreach ($line in [IO.File]::ReadLines($file)) {
            if ($line -match $pattern) {
                $candidate = $Matches[1].Trim()
                if ($candidate -match '^["'']([^"'']*)["'']\s*(?:#.*)?$') { $value = $Matches[1] }
                else { $value = ($candidate -replace '\s+#.*$', '').Trim() }
            }
        }
    }
    return $value
}

function Get-CortaeFirebirdHome([string]$ProjectRoot) {
    $configured = Get-CortaeSetting $ProjectRoot 'CORTAE_FIREBIRD_HOME'
    if ($configured) {
        if (-not [IO.Path]::IsPathRooted($configured)) { throw 'CORTAE_FIREBIRD_HOME deve ser um caminho absoluto.' }
        return [IO.Path]::GetFullPath($configured)
    }
    if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA indisponivel; configure CORTAE_FIREBIRD_HOME.' }
    return Join-Path $env:LOCALAPPDATA 'Cortae\runtimes\Firebird-4.0.4.3010-Win32'
}

function Test-CortaeLocalFirebird([string]$ProjectRoot) {
    $auto = Get-CortaeSetting $ProjectRoot 'CORTAE_FIREBIRD_AUTO_START' 'true'
    if ($auto.ToLowerInvariant() -in @('false', '0', 'no', 'nao')) { return $false }
    $mainHost = Get-CortaeSetting $ProjectRoot 'DB_HOST' 'localhost'
    $mainPort = Get-CortaeSetting $ProjectRoot 'DB_PORT' '3054'
    $logHost = Get-CortaeSetting $ProjectRoot 'LOG_DB_HOST' $mainHost
    $logPort = Get-CortaeSetting $ProjectRoot 'LOG_DB_PORT' $mainPort
    return (($mainHost -in @('localhost', '127.0.0.1', '::1') -and $mainPort -eq '3054') -or
            ($logHost -in @('localhost', '127.0.0.1', '::1') -and $logPort -eq '3054'))
}

function Assert-CortaeFirebirdFiles([string]$FirebirdHome) {
    $exe = Join-Path $FirebirdHome 'firebird.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Runtime Firebird ausente. Execute Configurar-Cortae.cmd.' }
    $version = [Diagnostics.FileVersionInfo]::GetVersionInfo($exe).FileVersion
    if ($version -notmatch '(?<!\d)4\.0\.4\.3010(?!\d)') { throw 'Runtime exige Firebird exato 4.0.4.3010.' }
    $stream = [IO.File]::OpenRead($exe)
    $reader = New-Object IO.BinaryReader($stream)
    try {
        if ($reader.ReadUInt16() -ne 0x5A4D) { throw 'Executavel Firebird invalido.' }
        $stream.Position = 0x3C
        $offset = $reader.ReadInt32()
        $stream.Position = $offset
        if ($reader.ReadUInt32() -ne 0x4550 -or $reader.ReadUInt16() -ne 0x14C) { throw 'Firebird deve ser Windows x86 (32 bits).' }
    } finally { $reader.Dispose(); $stream.Dispose() }
    return $exe
}

function Install-CortaeFirebird([string]$ProjectRoot) {
    $firebirdHome = Get-CortaeFirebirdHome $ProjectRoot
    if (Test-Path -LiteralPath $firebirdHome) { $null = Assert-CortaeFirebirdFiles $firebirdHome; return $firebirdHome }
    $parent = Split-Path -Parent $firebirdHome
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $lockPath = $firebirdHome + '.install.lock'
    try { $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None) }
    catch { throw "Instalacao em andamento ou interrompida. Confira o arquivo $lockPath antes de tentar novamente." }
    $stage = Join-Path $parent ('.cortae-firebird-install-' + [Guid]::NewGuid().ToString('N'))
    $zip = $stage + '.zip'
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $script:CortaeFirebirdUrl -OutFile $zip -UseBasicParsing
        if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne $script:CortaeFirebirdHash) { throw 'SHA256 do ZIP Firebird incorreto; arquivo preservado e instalacao interrompida.' }
        Expand-Archive -LiteralPath $zip -DestinationPath $stage
        $null = Assert-CortaeFirebirdFiles $stage
        $configuration = Join-Path $stage 'firebird.conf'
        [IO.File]::AppendAllText($configuration, "`r`nRemoteServicePort = 3054`r`nRemoteBindAddress = 127.0.0.1`r`n", [Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText((Join-Path $stage '.cortae-init-pending.json'), '{"owner":"Cortae","version":"4.0.4.3010","phase":"fresh"}', [Text.UTF8Encoding]::new($false))
        # Both absolute paths are immediate children of the explicit runtime parent.
        if ((Split-Path -Parent ([IO.Path]::GetFullPath($stage))) -ne [IO.Path]::GetFullPath($parent)) { throw 'Destino de instalacao fora do diretorio esperado.' }
        Move-Item -LiteralPath $stage -Destination $firebirdHome
        Write-Host "Firebird 4.0.4.3010 x86 instalado em: $firebirdHome"
        return $firebirdHome
    } finally {
        $lock.Dispose()
        Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    }
}

function Initialize-CortaeFirebird([string]$ProjectRoot, [string]$PythonPath) {
    if (-not (Test-CortaeLocalFirebird $ProjectRoot)) { return }
    $firebirdHome = Install-CortaeFirebird $ProjectRoot
    # Existing operator-managed installations have no marker and are untouched.
    if (Test-Path -LiteralPath (Join-Path $firebirdHome '.cortae-init-pending.json')) {
        & $PythonPath (Join-Path $ProjectRoot 'Backend\firebird_runtime.py') --initialize-home $firebirdHome
        if ($LASTEXITCODE -ne 0) { throw 'Configure a conta privada do runtime conforme a mensagem anterior e execute novamente.' }
    }
}

function Assert-CortaeFirebirdBinding([string]$FirebirdHome) {
    $lines = [IO.File]::ReadAllLines((Join-Path $FirebirdHome 'firebird.conf'))
    $port = @($lines | Where-Object { $_ -match '^\s*RemoteServicePort\s*=' })
    $bind = @($lines | Where-Object { $_ -match '^\s*RemoteBindAddress\s*=' })
    if ($port.Count -ne 1 -or $port[0] -notmatch '^\s*RemoteServicePort\s*=\s*3054\s*(?:#.*)?$' -or
        $bind.Count -ne 1 -or $bind[0] -notmatch '^\s*RemoteBindAddress\s*=\s*127\.0\.0\.1\s*(?:#.*)?$' -or
        @($lines | Where-Object { $_ -match '^\s*RemoteServiceName\s*=\s*[^#\s]' }).Count) {
        throw 'Runtime existente preservado: configure RemoteServicePort=3054 e RemoteBindAddress=127.0.0.1 no firebird.conf; remova RemoteServiceName explicito.'
    }
}

function Start-CortaeFirebird([string]$ProjectRoot) {
    if (-not (Test-CortaeLocalFirebird $ProjectRoot)) { return }
    $firebirdHome = Get-CortaeFirebirdHome $ProjectRoot
    $exe = Assert-CortaeFirebirdFiles $firebirdHome
    if (Test-Path -LiteralPath (Join-Path $firebirdHome '.cortae-init-pending.json')) { throw 'Inicializacao SYSDBA pendente. Execute Configurar-Cortae.cmd.' }
    Assert-CortaeFirebirdBinding $firebirdHome
    $listeners = @(Get-NetTCPConnection -LocalPort 3054 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count) {
        foreach ($listener in $listeners) {
            $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)" -ErrorAction Stop
            if (-not $existing.ExecutablePath -or -not $existing.ExecutablePath.Equals($exe, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Porta 3054 ocupada por outro executavel. Nenhum processo externo sera encerrado.'
            }
        }
        return # A running instance is reused and never claimed for shutdown.
    }
    $runtime = Join-Path $ProjectRoot '.runtime'
    New-Item -ItemType Directory -Path $runtime -Force | Out-Null
    $previousFirebird = [Environment]::GetEnvironmentVariable('FIREBIRD', 'Process')
    try {
        $env:FIREBIRD = $firebirdHome
        $process = Start-Process -FilePath $exe -ArgumentList '-a' -WorkingDirectory $firebirdHome -WindowStyle Hidden -PassThru
    } finally { [Environment]::SetEnvironmentVariable('FIREBIRD', $previousFirebird, 'Process') }
    try {
        @{ Pid=$process.Id; Exe=$exe; Home=$firebirdHome; ProjectRoot=[IO.Path]::GetFullPath($ProjectRoot); Started=$process.StartTime.ToUniversalTime().ToString('o') } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'firebird-process.json') -Encoding UTF8
        for ($attempt=0; $attempt -lt 30; $attempt++) {
            if ($process.HasExited) { throw 'Firebird encerrou antes de abrir a porta 3054. Consulte firebird.log no runtime.' }
            $owned = @(Get-NetTCPConnection -LocalPort 3054 -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -eq $process.Id })
            if ($owned.Count) { return }
            Start-Sleep -Milliseconds 200
        }
        throw 'Firebird nao abriu a porta 3054 no prazo esperado.'
    } catch {
        $startupError = $_
        # Also cover an ownership-file write failure: no unregistered child may
        # survive, and a reused PID or another executable must never be killed.
        try {
            $current = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
            $native = Get-CimInstance Win32_Process -Filter "ProcessId = $($process.Id)" -ErrorAction Stop
            $sameStart = $current -and [Math]::Abs(($current.StartTime.ToUniversalTime() - $process.StartTime.ToUniversalTime()).TotalSeconds) -lt 1
            if ($sameStart -and $native.ExecutablePath -and $native.ExecutablePath.Equals($exe, [StringComparison]::OrdinalIgnoreCase)) {
                Stop-Process -Id $process.Id -ErrorAction Stop
            }
        } catch { Write-Warning 'Falha ao limpar o processo Firebird recem-criado; confira o PID informado pelo iniciador.' }
        throw $startupError
    }
}

function Stop-CortaeFirebird([string]$ProjectRoot) {
    $statePath = Join-Path $ProjectRoot '.runtime\firebird-process.json'
    if (-not (Test-Path -LiteralPath $statePath)) { return }
    $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $expectedHome = Get-CortaeFirebirdHome $ProjectRoot
    if ($state.ProjectRoot -ne [IO.Path]::GetFullPath($ProjectRoot) -or $state.Home -ne $expectedHome -or
        $state.Exe -ne (Join-Path $expectedHome 'firebird.exe')) { Write-Warning 'Registro Firebird de outra instalacao preservado.'; return }
    $native = Get-Process -Id $state.Pid -ErrorAction SilentlyContinue
    if (-not $native) { Remove-Item -LiteralPath $statePath -Force; return }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($state.Pid)" -ErrorAction Stop
    $sameStart = [Math]::Abs(($native.StartTime.ToUniversalTime() - ([DateTimeOffset]$state.Started).UtcDateTime).TotalSeconds) -lt 1
    if ($sameStart -and $process.ExecutablePath -and $process.ExecutablePath.Equals($state.Exe, [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Process -Id $state.Pid -ErrorAction Stop
        Remove-Item -LiteralPath $statePath -Force
        Write-Host 'Firebird iniciado por este projeto encerrado.'
    } else { Write-Warning 'PID Firebird nao corresponde ao registro; processo preservado.' }
}
