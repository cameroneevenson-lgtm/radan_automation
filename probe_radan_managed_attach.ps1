param(
    [switch]$TestCreateNew
)

$ErrorActionPreference = "Stop"

function Get-RadanPids {
    @(Get-Process RADRAFT -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
}

function Show-Result {
    param(
        [string]$Label,
        [object]$App
    )

    [pscustomobject]@{
        Label            = $Label
        ProcessId        = $App.ProcessId
        IsConnected      = $App.IsConnected
        Visible          = $App.Visible
        IsRadanInstalled = $App.IsRadanInstalled
    } | Format-List
}

$before = Get-RadanPids

Add-Type -Path "C:\Program Files\Mazak\Mazak\bin\Radan.Shared.LicenseInfoProvider.dll"
Add-Type -Path "C:\Program Files\Mazak\Mazak\bin\Radan.BusinessLogic.Licenses.dll"
Add-Type -Path "C:\Program Files\Mazak\Mazak\bin\Radan.Shared.Radraft.Interop.dll"

$provider = [Radan.BusinessLogic.Licenses.LicenseBusinessContext]::new()
$factory = [Radan.Shared.Radraft.Interop.RadraftApplicationFactory]::new($provider)

$ctorApp = $null
$factoryApp = $null
$createNewApp = $null

try {
    $ctorApp = [Radan.Shared.Radraft.Interop.RadraftApplication]::new($true)
    Show-Result -Label "Constructor(useExistingInstance=true)" -App $ctorApp

    $factoryApp = $factory.Create($true)
    Show-Result -Label "Factory.Create(useExistingInstance=true)" -App $factoryApp

    if ($TestCreateNew) {
        $createNewApp = $factory.Create($false)
        Show-Result -Label "Factory.Create(useExistingInstance=false)" -App $createNewApp
    }
}
finally {
    foreach ($app in @($ctorApp, $factoryApp, $createNewApp)) {
        if ($null -eq $app) {
            continue
        }

        if ($app.ProcessId -and ($before -notcontains $app.ProcessId)) {
            try {
                $app.Dispose()
            }
            catch {
            }
        }
    }
}

$after = Get-RadanPids

"BeforePids={0}" -f ($before -join ",")
"AfterPids={0}" -f ($after -join ",")
