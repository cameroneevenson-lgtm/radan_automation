param(
    [double]$Width = 25.0,
    [double]$Height = 25.0,
    [double]$Gap = 10.0,
    [double]$X,
    [double]$Y,
    [switch]$CenterOnBounds,
    [switch]$UseExplicitPosition
)

$scriptPath = Join-Path $PSScriptRoot "live_session_bridge.ps1"
$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $scriptPath,
    "-Action",
    "draw_rectangle",
    "-Width",
    "$Width",
    "-Height",
    "$Height",
    "-Gap",
    "$Gap"
)

if ($PSBoundParameters.ContainsKey("X")) {
    $arguments += @("-X", "$X")
}
if ($PSBoundParameters.ContainsKey("Y")) {
    $arguments += @("-Y", "$Y")
}
if ($CenterOnBounds) {
    $arguments += "-CenterOnBounds"
}
if ($UseExplicitPosition) {
    $arguments += "-UseExplicitPosition"
}

& powershell @arguments
