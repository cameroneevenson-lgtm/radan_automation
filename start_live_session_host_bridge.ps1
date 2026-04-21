param(
    [string]$PythonExe = "",
    [string]$BridgeDir = "",
    [double]$PollSeconds = 0.2,
    [switch]$Background
)

$repoRoot = Split-Path $PSScriptRoot -Parent
$preferredPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$scriptPath = Join-Path $PSScriptRoot "serve_live_session_bridge.py"

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if (Test-Path $preferredPython) {
        $PythonExe = $preferredPython
    }
    else {
        $PythonExe = "python"
    }
}

$arguments = @($scriptPath, "--poll-seconds", "$PollSeconds")
if (-not [string]::IsNullOrWhiteSpace($BridgeDir)) {
    $arguments += @("--bridge-dir", $BridgeDir)
}

if ($Background) {
    Start-Process -FilePath $PythonExe -ArgumentList $arguments | Out-Null
    Write-Output "Started live session host bridge."
}
else {
    & $PythonExe @arguments
}
