param(
    [ValidateSet("describe", "draw_rectangle")]
    [string]$Action = "describe",
    [int]$ExpectedProcessId = 0,
    [string]$WindowTitleContains = "",
    [switch]$RequirePartEditor,
    [double]$Width = 25.0,
    [double]$Height = 25.0,
    [double]$Gap = 10.0,
    [double]$X,
    [double]$Y,
    [switch]$CenterOnBounds,
    [switch]$UseExplicitPosition
)

$ErrorActionPreference = "Stop"

function Test-ContainsInsensitive {
    param(
        [string]$Value,
        [string]$Needle
    )

    if ([string]::IsNullOrWhiteSpace($Needle)) {
        return $true
    }
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $false
    }

    return $Value.IndexOf($Needle, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Get-SessionResult {
    param(
        [Parameter(Mandatory = $true)]
        [object]$App,
        [Parameter(Mandatory = $true)]
        [string]$WindowTitle,
        [Parameter(Mandatory = $true)]
        [string]$Pattern,
        [Parameter(Mandatory = $true)]
        [bool]$BoundsAvailable,
        [double]$Left,
        [double]$Bottom,
        [double]$Right,
        [double]$Top,
        [double]$RectangleX,
        [double]$RectangleY,
        [double]$RectangleWidth,
        [double]$RectangleHeight
    )

    return [pscustomobject]@{
        ProcessId       = $App.ProcessId
        WindowTitle     = $WindowTitle
        Visible         = $App.Visible
        IsConnected     = $App.IsConnected
        IsRadanInstalled = $App.IsRadanInstalled
        Pattern         = $Pattern
        BoundsAvailable = $BoundsAvailable
        Left            = $Left
        Bottom          = $Bottom
        Right           = $Right
        Top             = $Top
        RectangleX      = $RectangleX
        RectangleY      = $RectangleY
        RectangleWidth  = $RectangleWidth
        RectangleHeight = $RectangleHeight
    }
}

Add-Type -Path "C:\Program Files\Mazak\Mazak\bin\Radan.Shared.LicenseInfoProvider.dll"
Add-Type -Path "C:\Program Files\Mazak\Mazak\bin\Radan.BusinessLogic.Licenses.dll"
Add-Type -Path "C:\Program Files\Mazak\Mazak\bin\Radan.Shared.Radraft.Interop.dll"

$provider = [Radan.BusinessLogic.Licenses.LicenseBusinessContext]::new()
$factory = [Radan.Shared.Radraft.Interop.RadraftApplicationFactory]::new($provider)
$app = $null

try {
    $app = $factory.Create($true)
    if (-not $app.IsConnected) {
        throw "No attachable live RADAN session was found."
    }

    $process = Get-Process -Id $app.ProcessId -ErrorAction SilentlyContinue
    $windowTitle = if ($null -ne $process) { $process.MainWindowTitle } else { "" }

    if ($ExpectedProcessId -gt 0 -and $app.ProcessId -ne $ExpectedProcessId) {
        throw "Attached RADAN PID $($app.ProcessId) does not match expected PID $ExpectedProcessId."
    }
    if (-not (Test-ContainsInsensitive -Value $windowTitle -Needle $WindowTitleContains)) {
        throw "Attached RADAN window '$windowTitle' does not contain '$WindowTitleContains'."
    }

    $isPartEditor = Test-ContainsInsensitive -Value $windowTitle -Needle "Part Editor"
    if ($RequirePartEditor -and -not $isPartEditor) {
        throw "Attached RADAN window is not in Part Editor mode."
    }

    $pattern = ""
    $left = 0.0
    $bottom = 0.0
    $right = 0.0
    $top = 0.0
    $boundsOk = $false

    if ($isPartEditor) {
        try {
            $pattern = [string]$app.PART_PATTERN
        }
        catch {
            $pattern = ""
        }

        if (-not [string]::IsNullOrWhiteSpace($pattern)) {
            try {
                $boundsOk = $app.ElfBounds($pattern, "", [ref]$left, [ref]$bottom, [ref]$right, [ref]$top)
            }
            catch {
                $boundsOk = $false
            }
        }
    }

    $rectangleX = [double]::NaN
    $rectangleY = [double]::NaN
    $rectangleWidth = [double]::NaN
    $rectangleHeight = [double]::NaN

    if ($Action -eq "draw_rectangle") {
        if (-not $isPartEditor) {
            throw "DrawRectangle is only supported when the attached session is in Part Editor mode."
        }

        if ($CenterOnBounds) {
            if (-not $boundsOk) {
                throw "Unable to calculate part bounds for centered placement."
            }
            $X = (($left + $right) / 2.0) - ($Width / 2.0)
            $Y = (($bottom + $top) / 2.0) - ($Height / 2.0)
        }
        elseif (-not $UseExplicitPosition) {
            if ($boundsOk) {
                $X = $right + $Gap
                $Y = $bottom
            }
            else {
                $X = 0.0
                $Y = 0.0
            }
        }

        $app.PartEditor.DrawRectangle($X, $Y, $Width, $Height)
        $rectangleX = $X
        $rectangleY = $Y
        $rectangleWidth = $Width
        $rectangleHeight = $Height
    }

    Get-SessionResult -App $app `
        -WindowTitle $windowTitle `
        -Pattern $pattern `
        -BoundsAvailable $boundsOk `
        -Left $left `
        -Bottom $bottom `
        -Right $right `
        -Top $top `
        -RectangleX $rectangleX `
        -RectangleY $rectangleY `
        -RectangleWidth $rectangleWidth `
        -RectangleHeight $rectangleHeight |
        ConvertTo-Json -Depth 4
}
finally {
    if ($null -ne $app) {
        try {
            $app.Dispose()
        }
        catch {
        }
    }
}
