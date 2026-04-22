param(
    [double]$Width = 25.0,
    [double]$Height = 25.0,
    [double]$Gap = 10.0,
    [double]$X,
    [double]$Y,
    [switch]$CenterOnBounds,
    [switch]$UseExplicitPosition
)

$repoRoot = Split-Path $PSScriptRoot -Parent
$preferredPythons = @(
    "C:\Tools\.venv\Scripts\python.exe",
    (Join-Path $repoRoot ".venv\Scripts\python.exe")
)
$pythonExe = "python"
foreach ($candidate in $preferredPythons) {
    if (Test-Path $candidate) {
        $pythonExe = $candidate
        break
    }
}
$scriptPath = Join-Path $PSScriptRoot "draw_live_rectangle.py"
$arguments = @(
    $scriptPath,
    "--width",
    "$Width",
    "--height",
    "$Height",
    "--gap",
    "$Gap"
)

if ($PSBoundParameters.ContainsKey("X")) {
    $arguments += @("--x", "$X")
}
if ($PSBoundParameters.ContainsKey("Y")) {
    $arguments += @("--y", "$Y")
}
if ($CenterOnBounds) {
    $arguments += "--center-on-bounds"
}
if ($UseExplicitPosition) {
    $arguments += "--use-explicit-position"
}

& $pythonExe @arguments
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
