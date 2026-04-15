param(
    [string]$ProgId = "Radraft.Application",
    [switch]$AttachActive,
    [switch]$AttachOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-BridgeResponse {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Payload
    )

    $json = $Payload | ConvertTo-Json -Compress -Depth 8
    [Console]::Out.WriteLine($json)
    [Console]::Out.Flush()
}

function Convert-BridgeResult {
    param(
        [object]$Value
    )

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [string] -or $Value -is [bool] -or $Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal]) {
        return $Value
    }

    if ($Value -is [System.Array]) {
        $items = @()
        foreach ($item in $Value) {
            $items += ,(Convert-BridgeResult $item)
        }
        return $items
    }

    if ($Value.GetType().IsEnum) {
        return [int]$Value
    }

    return [string]$Value
}

function Resolve-BridgePathTarget {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Root,
        [object[]]$Path
    )

    $target = $Root
    foreach ($segment in $Path) {
        $name = [string]$segment
        $target = Get-BridgePropertyValue -Target $target -Name $name
    }
    return $target
}

function Get-BridgePropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Target,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    try {
        $value = $Target.$Name
        if ($null -ne $value) {
            return $value
        }
    } catch {
    }

    return $Target.GetType().InvokeMember(
        $Name,
        [Reflection.BindingFlags]::GetProperty,
        $null,
        $Target,
        @()
    )
}

function Invoke-BridgeMethod {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Target,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [object[]]$Args
    )

    $method = $Target.PSObject.Methods[$Name]
    if ($null -ne $method) {
        return $method.Invoke($Args)
    }

    return $Target.GetType().InvokeMember(
        $Name,
        [Reflection.BindingFlags]::InvokeMethod,
        $null,
        $Target,
        $Args
    )
}

$com = $null
$createdNew = $false
try {
    if ($AttachActive) {
        try {
            $com = [Runtime.InteropServices.Marshal]::GetActiveObject($ProgId)
        } catch {
            $com = $null
        }
    }

    if ($null -eq $com) {
        if ($AttachOnly) {
            throw "No active COM object is registered for $ProgId."
        }
        $com = New-Object -ComObject $ProgId
        $createdNew = $true
    }

    Write-BridgeResponse @{
        ok          = $true
        event       = "ready"
        prog_id     = $ProgId
        created_new = $createdNew
    }

    while (($line = [Console]::In.ReadLine()) -ne $null) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        try {
            $request = $line | ConvertFrom-Json
            $action = [string]$request.action

            switch ($action) {
                "get_property" {
                    $name = [string]$request.name
                    $result = Get-BridgePropertyValue -Target $com -Name $name
                    Write-BridgeResponse @{
                        ok     = $true
                        result = Convert-BridgeResult $result
                    }
                }

                "set_property" {
                    $name = [string]$request.name
                    $com.$name = $request.value
                    Write-BridgeResponse @{
                        ok     = $true
                        result = $null
                    }
                }

                "call_method" {
                    $name = [string]$request.name
                    $args = @()
                    if ($null -ne $request.args) {
                        foreach ($arg in $request.args) {
                            $args += $arg
                        }
                    }
                    $result = Invoke-BridgeMethod -Target $com -Name $name -Args $args
                    Write-BridgeResponse @{
                        ok     = $true
                        result = Convert-BridgeResult $result
                    }
                }

                "get_path_property" {
                    $path = @()
                    if ($null -ne $request.path) {
                        foreach ($segment in $request.path) {
                            $path += [string]$segment
                        }
                    }
                    $target = Resolve-BridgePathTarget -Root $com -Path $path
                    $name = [string]$request.name
                    $result = Get-BridgePropertyValue -Target $target -Name $name
                    Write-BridgeResponse @{
                        ok     = $true
                        result = Convert-BridgeResult $result
                    }
                }

                "call_path_method" {
                    $path = @()
                    if ($null -ne $request.path) {
                        foreach ($segment in $request.path) {
                            $path += [string]$segment
                        }
                    }
                    $target = Resolve-BridgePathTarget -Root $com -Path $path
                    $name = [string]$request.name
                    $args = @()
                    if ($null -ne $request.args) {
                        foreach ($arg in $request.args) {
                            $args += $arg
                        }
                    }
                    $result = Invoke-BridgeMethod -Target $target -Name $name -Args $args
                    Write-BridgeResponse @{
                        ok     = $true
                        result = Convert-BridgeResult $result
                    }
                }

                "dispose" {
                    Write-BridgeResponse @{
                        ok     = $true
                        result = $null
                    }
                    break
                }

                default {
                    Write-BridgeResponse @{
                        ok    = $false
                        error = "Unknown action: $action"
                    }
                }
            }
        } catch {
            Write-BridgeResponse @{
                ok      = $false
                error   = $_.Exception.Message
                hresult = if ($_.Exception.HResult) { "0x{0:X8}" -f $_.Exception.HResult } else { $null }
            }
        }
    }
} catch {
    Write-BridgeResponse @{
        ok      = $false
        event   = "startup_error"
        error   = $_.Exception.Message
        hresult = if ($_.Exception.HResult) { "0x{0:X8}" -f $_.Exception.HResult } else { $null }
    }
    exit 1
} finally {
    if ($null -ne $com) {
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($com)
    }
}
