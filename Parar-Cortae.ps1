$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
. (Join-Path $projectRoot 'Firebird-Cortae.ps1')
$statePath = Join-Path $projectRoot '.runtime\processes.json'
if (-not (Test-Path -LiteralPath $statePath)) { Stop-CortaeFirebird $projectRoot; Write-Host 'Nenhum processo de API/frontend registrado.'; exit 0 }
$states = @(Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)
$remaining = @()
foreach ($state in $states) {
    $scriptPath = [IO.Path]::GetFullPath($state.Script)
    if (-not $scriptPath.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Warning 'Registro fora deste projeto ignorado.'; $remaining += $state; continue
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($state.Pid)" -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    $nativeProcess = Get-Process -Id $state.Pid -ErrorAction SilentlyContinue
    if (-not $nativeProcess) { continue }
    # ConvertFrom-Json in PowerShell 7 may already materialize ISO timestamps
    # as DateTime. Preserve its timezone instead of parsing its localized text.
    $started = ([DateTimeOffset]$state.Started).UtcDateTime
    $sameStart = [Math]::Abs(($nativeProcess.StartTime.ToUniversalTime() - $started).TotalSeconds) -lt 1
    $ownsScript = $process.CommandLine -and $process.CommandLine.IndexOf($scriptPath, [StringComparison]::OrdinalIgnoreCase) -ge 0
    if ($sameStart -and $ownsScript) {
        try {
            # Windows virtualenv's python.exe is a launcher and can keep the
            # actual interpreter in a child process. Capture the relationship
            # while the verified parent still exists; terminate only children
            # running this exact project script and born after that parent.
            $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId = $($state.Pid)" -ErrorAction Stop)
            foreach ($child in $children) {
                $childProcess = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
                $childOwnsScript = $child.CommandLine -and $child.CommandLine.IndexOf($scriptPath, [StringComparison]::OrdinalIgnoreCase) -ge 0
                $childBornAfterParent = $childProcess -and $childProcess.StartTime.ToUniversalTime() -ge $started
                if ($childOwnsScript -and $childBornAfterParent) {
                    Stop-Process -Id $child.ProcessId -Force -ErrorAction Stop
                    Write-Host "Processo filho Cortaê $($child.ProcessId) encerrado."
                }
            }
            # The virtualenv launcher can exit automatically with its child.
            if (Get-Process -Id $state.Pid -ErrorAction SilentlyContinue) {
                Stop-Process -Id $state.Pid -Force -ErrorAction Stop
            }
            Write-Host "Processo Cortaê $($state.Pid) encerrado."
        } catch {
            $remaining += $state
            Write-Warning "Falha ao encerrar PID $($state.Pid); registro preservado para nova tentativa."
        }
    } else {
        $remaining += $state
        Write-Warning "PID $($state.Pid) não corresponde ao processo registrado; preservado."
    }
}
if ($remaining.Count) {
    $remaining | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
} else {
    Remove-Item -LiteralPath $statePath -Force
    Stop-CortaeFirebird $projectRoot
}
