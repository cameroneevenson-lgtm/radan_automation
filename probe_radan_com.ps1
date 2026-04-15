param(
    [string[]]$ProgIds = @(
        "Radan.RasterToVector",
        "Radan.RasterToVector.1",
        "Radraft.Application"
    ),
    [int]$MaxMembers = 40
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RegistryValueOrNull {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if (-not (Test-Path $Path)) {
        return $null
    }

    $item = Get-ItemProperty -Path $Path -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        return $null
    }

    $prop = $item.PSObject.Properties[$Name]
    if ($null -eq $prop) {
        return $null
    }

    return $prop.Value
}

function Show-ProgIdInfo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProgId
    )

    Write-Host ""
    Write-Host ("=" * 72)
    Write-Host "ProgID: $ProgId"

    $progIdPath = "Registry::HKEY_CLASSES_ROOT\$ProgId"
    if (Test-Path $progIdPath) {
        Write-Host "Registry: present"
        $clsid = Get-RegistryValueOrNull -Path $progIdPath -Name "CLSID"
        if ($clsid) {
            Write-Host "CLSID: $clsid"
            $localServer = Get-RegistryValueOrNull -Path "Registry::HKEY_CLASSES_ROOT\\CLSID\\$clsid\\LocalServer32" -Name "(default)"
            if (-not $localServer) {
                $localServer = Get-RegistryValueOrNull -Path "Registry::HKEY_CLASSES_ROOT\\WOW6432Node\\CLSID\\$clsid\\LocalServer32" -Name "(default)"
            }
            if ($localServer) {
                Write-Host "LocalServer32: $localServer"
            }
        }
    } else {
        Write-Host "Registry: missing"
    }

    $comObject = $null
    try {
        $comObject = New-Object -ComObject $ProgId
        Write-Host "Activation: success"
        Write-Host ("COM type: " + $comObject.GetType().FullName)

        $members = $comObject |
            Get-Member -MemberType Method, Property |
            Sort-Object Name |
            Select-Object -First $MaxMembers

        if ($members) {
            Write-Host ""
            Write-Host "Members:"
            $members | Format-Table -AutoSize | Out-String | Write-Host
        } else {
            Write-Host "Members: none returned by Get-Member"
        }
    } catch {
        Write-Host "Activation: FAILED"
        Write-Host ("Exception: " + $_.Exception.GetType().FullName)
        Write-Host ("Message: " + $_.Exception.Message)
        if ($_.Exception.HResult) {
            Write-Host ("HResult: 0x{0:X8}" -f $_.Exception.HResult)
        }
    } finally {
        if ($null -ne $comObject) {
            [void][Runtime.InteropServices.Marshal]::ReleaseComObject($comObject)
        }
    }
}

foreach ($progId in $ProgIds) {
    Show-ProgIdInfo -ProgId $progId
}
