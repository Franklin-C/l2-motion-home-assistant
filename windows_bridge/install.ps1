[CmdletBinding()]
param(
    [int]$Port = 8765,
    [string]$DeviceName = 'HHC0051745CDEF',
    [string]$BedAddress = '57:4C:54:08:A6:74'
)

$ErrorActionPreference = 'Stop'
$bridgeRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = Join-Path $bridgeRoot '.venv'
$dataPath = Join-Path $env:LOCALAPPDATA 'L2MotionBridge'
$configPath = Join-Path $dataPath 'config.json'
$pythonwPath = Join-Path $venvPath 'Scripts\pythonw.exe'
$appPath = Join-Path $bridgeRoot 'app.py'

New-Item -ItemType Directory -Path $dataPath -Force | Out-Null

if (-not (Test-Path -LiteralPath $venvPath)) {
    & py -3.13 -m venv $venvPath
}
& (Join-Path $venvPath 'Scripts\python.exe') -m pip install --upgrade -r (Join-Path $bridgeRoot 'requirements.txt')

$tokenBytes = New-Object byte[] 32
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $random.GetBytes($tokenBytes)
}
finally {
    $random.Dispose()
}
$token = -join ($tokenBytes | ForEach-Object { $_.ToString('x2') })
$config = [ordered]@{
    token = $token
    host = '0.0.0.0'
    port = $Port
    device_name = $DeviceName
    address = $BedAddress
}
$config | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8

$acl = Get-Acl -LiteralPath $configPath
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "$env:USERDOMAIN\$env:USERNAME",
    'FullControl',
    'Allow'
)
$acl.SetAccessRule($rule)
Set-Acl -LiteralPath $configPath -AclObject $acl

$taskName = 'L2 Motion Windows Bridge'
$argument = '"{0}" --config "{1}"' -f $appPath, $configPath
$action = New-ScheduledTaskAction -Execute $pythonwPath -Argument $argument
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "L2 Motion bridge installed and started on port $Port."
Write-Host "Home Assistant host: $env:COMPUTERNAME"
Write-Host "Home Assistant token: $token"
Write-Host "If Windows asks about network access, allow Private networks only."
