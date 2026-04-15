param(
    [Parameter(Mandatory = $true)]
    [string]$AssemblyPath,
    [Parameter(Mandatory = $true)]
    [string]$TypeName,
    [Parameter(Mandatory = $true)]
    [string]$MethodName,
    [int]$ParameterCount = -1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-OperandSize {
    param(
        [System.Reflection.Emit.OperandType]$OperandType,
        [byte[]]$IL,
        [int]$Position
    )

    switch ($OperandType) {
        ([System.Reflection.Emit.OperandType]::InlineNone) { return 0 }
        ([System.Reflection.Emit.OperandType]::ShortInlineBrTarget) { return 1 }
        ([System.Reflection.Emit.OperandType]::ShortInlineI) { return 1 }
        ([System.Reflection.Emit.OperandType]::ShortInlineVar) { return 1 }
        ([System.Reflection.Emit.OperandType]::InlineVar) { return 2 }
        ([System.Reflection.Emit.OperandType]::InlineI) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineBrTarget) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineField) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineMethod) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineSig) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineString) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineTok) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineType) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineI8) { return 8 }
        ([System.Reflection.Emit.OperandType]::InlineR) { return 8 }
        ([System.Reflection.Emit.OperandType]::ShortInlineR) { return 4 }
        ([System.Reflection.Emit.OperandType]::InlineSwitch) {
            $count = [BitConverter]::ToInt32($IL, $Position)
            return 4 + (4 * $count)
        }
        default { throw "Unhandled operand type: $OperandType" }
    }
}

function Resolve-OperandDisplay {
    param(
        [System.Reflection.Module]$Module,
        [System.Reflection.Emit.OpCode]$OpCode,
        [byte[]]$OperandBytes
    )

    $operandType = $OpCode.OperandType
    switch ($operandType) {
        ([System.Reflection.Emit.OperandType]::InlineNone) { return "" }
        ([System.Reflection.Emit.OperandType]::ShortInlineBrTarget) { return [sbyte]$OperandBytes[0] }
        ([System.Reflection.Emit.OperandType]::ShortInlineI) { return [sbyte]$OperandBytes[0] }
        ([System.Reflection.Emit.OperandType]::ShortInlineVar) { return $OperandBytes[0] }
        ([System.Reflection.Emit.OperandType]::InlineVar) { return [BitConverter]::ToUInt16($OperandBytes, 0) }
        ([System.Reflection.Emit.OperandType]::InlineI) { return [BitConverter]::ToInt32($OperandBytes, 0) }
        ([System.Reflection.Emit.OperandType]::InlineBrTarget) { return [BitConverter]::ToInt32($OperandBytes, 0) }
        ([System.Reflection.Emit.OperandType]::InlineI8) { return [BitConverter]::ToInt64($OperandBytes, 0) }
        ([System.Reflection.Emit.OperandType]::InlineR) { return [BitConverter]::ToDouble($OperandBytes, 0) }
        ([System.Reflection.Emit.OperandType]::ShortInlineR) { return [BitConverter]::ToSingle($OperandBytes, 0) }
        ([System.Reflection.Emit.OperandType]::InlineField) {
            $token = [BitConverter]::ToInt32($OperandBytes, 0)
            return $Module.ResolveField($token).ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineMethod) {
            $token = [BitConverter]::ToInt32($OperandBytes, 0)
            return $Module.ResolveMethod($token).ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineSig) {
            return ('0x{0:X8}' -f [BitConverter]::ToInt32($OperandBytes, 0))
        }
        ([System.Reflection.Emit.OperandType]::InlineString) {
            $token = [BitConverter]::ToInt32($OperandBytes, 0)
            return '"' + $Module.ResolveString($token) + '"'
        }
        ([System.Reflection.Emit.OperandType]::InlineTok) {
            $token = [BitConverter]::ToInt32($OperandBytes, 0)
            return $Module.ResolveMember($token).ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineType) {
            $token = [BitConverter]::ToInt32($OperandBytes, 0)
            return $Module.ResolveType($token).ToString()
        }
        ([System.Reflection.Emit.OperandType]::InlineSwitch) {
            $count = [BitConverter]::ToInt32($OperandBytes, 0)
            $targets = for ($i = 0; $i -lt $count; $i++) {
                [BitConverter]::ToInt32($OperandBytes, 4 + ($i * 4))
            }
            return '[' + ($targets -join ', ') + ']'
        }
        default { return ('0x{0}' -f ([BitConverter]::ToString($OperandBytes))) }
    }
}

$singleByteOpCodes = @{}
$doubleByteOpCodes = @{}
[System.Reflection.Emit.OpCodes].GetFields([System.Reflection.BindingFlags] 'Public,Static') |
    ForEach-Object {
        $opCode = [System.Reflection.Emit.OpCode]$_.GetValue($null)
        $value = [int]$opCode.Value -band 0xFFFF
        if ($value -le 0xFF) {
            $singleByteOpCodes[[byte]$value] = $opCode
        } elseif (($value -band 0xFF00) -eq 0xFE00) {
            $doubleByteOpCodes[[byte]($value -band 0xFF)] = $opCode
        }
    }

$assembly = [Reflection.Assembly]::LoadFrom($AssemblyPath)
$type = $assembly.GetType($TypeName, $true)
$members = if ($MethodName -in @('.ctor', '.cctor')) {
    @($type.GetConstructors([Reflection.BindingFlags] 'Public,NonPublic,Instance,Static') | Where-Object { $_.Name -eq $MethodName })
} else {
    @($type.GetMethods([Reflection.BindingFlags] 'Public,NonPublic,Instance,Static') | Where-Object { $_.Name -eq $MethodName })
}
if ($members.Count -eq 0) {
    throw "Method not found: $TypeName::$MethodName"
}
if ($ParameterCount -ge 0) {
    $members = @($members | Where-Object { $_.GetParameters().Count -eq $ParameterCount })
}
if ($members.Count -eq 0) {
    throw "No overload of $TypeName::$MethodName matched ParameterCount=$ParameterCount"
}
if ($members.Count -gt 1) {
    throw "Multiple overloads found for $TypeName::$MethodName"
}

$method = $members[0]
$body = $method.GetMethodBody()
if ($null -eq $body) {
    throw "Method has no IL body: $($method.ToString())"
}

$il = $body.GetILAsByteArray()
$module = $method.Module
$position = 0

Write-Output "Method: $($method.ToString())"
Write-Output "Locals: $($body.LocalVariables.Count)"
Write-Output ""

while ($position -lt $il.Length) {
    $offset = $position
    $first = $il[$position]
    $position += 1

    if ($first -eq 0xFE) {
        $second = $il[$position]
        $position += 1
        $opCode = $doubleByteOpCodes[$second]
    } else {
        $opCode = $singleByteOpCodes[$first]
    }

    if ($null -eq $opCode) {
        throw "Unknown opcode at IL offset $offset"
    }

    $operandSize = Get-OperandSize -OperandType $opCode.OperandType -IL $il -Position $position
    $operandBytes = if ($operandSize -gt 0) { $il[$position..($position + $operandSize - 1)] } else { @() }
    $position += $operandSize

    $display = Resolve-OperandDisplay -Module $module -OpCode $opCode -OperandBytes $operandBytes
    if ([string]::IsNullOrEmpty([string]$display)) {
        '{0:X4}: {1}' -f $offset, $opCode.Name
    } else {
        '{0:X4}: {1} {2}' -f $offset, $opCode.Name, $display
    }
}
