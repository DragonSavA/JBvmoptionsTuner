param([Parameter(Mandatory = $true)][string]$PythonExecutable)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $root 'scripts\launch.ps1')

function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}

$realInfo = Test-PythonExecutable $PythonExecutable
Assert-True ($null -ne $realInfo) 'The configured CPython 3.13+ must be discovered.'
Assert-True ($null -eq (Test-PythonExecutable (Join-Path $root 'does-not-exist.exe'))) 'A nonexistent executable must be ignored.'
Write-Host 'PASS: real interpreter probing'

$savedProbe = (Get-Command Test-PythonExecutable).ScriptBlock
$savedCandidates = (Get-Command Get-PythonCandidates).ScriptBlock
$script:probeCalls = 0
try {
    function Get-PythonCandidates { 'old.exe'; 'broken.exe'; 'new.exe'; 'NEW.exe'; 'minimum.exe' }
    function Test-PythonExecutable {
        param([string]$Executable)
        $script:probeCalls++
        switch ($Executable) {
            'new.exe' { return [PSCustomObject]@{version = @(3, 14, 3); executable = 'new.exe'} }
            'minimum.exe' { return [PSCustomObject]@{version = @(3, 13, 15); executable = 'minimum.exe'} }
            default { return $null }
        }
    }
    $selected = Find-Python
    Assert-True ($selected.executable -eq 'new.exe') 'Discovery must select the newest usable Python.'
    Assert-True ($script:probeCalls -eq 4) 'Case-insensitive duplicates must not be probed twice.'
    function Get-PythonCandidates { 'broken.exe'; 'old.exe' }
    Assert-True ($null -eq (Find-Python)) 'No usable Python must trigger the installation path.'
    Write-Host 'PASS: selection, deduplication and missing-Python detection'
} finally {
    Set-Item -Path Function:Test-PythonExecutable -Value $savedProbe
    Set-Item -Path Function:Get-PythonCandidates -Value $savedCandidates
}

foreach ($relative in @('scripts\launch.ps1', 'scripts\build_icon.ps1', 'jetbrains_vmoptions_tuner\install_runtime.ps1')) {
    $tokens = $null
    $errors = $null
    [Management.Automation.Language.Parser]::ParseFile((Join-Path $root $relative), [ref]$tokens, [ref]$errors) | Out-Null
    Assert-True ($errors.Count -eq 0) "Invalid PowerShell syntax in $relative"
}
Write-Host 'PASS: PowerShell script syntax'

# Exercise the real batch launcher without touching user settings: a tiny
# bootstrap stub replaces dependency/desktop setup in this temporary project.
$tempProject = Join-Path ([IO.Path]::GetTempPath()) ('vmopt-launch-' + [Guid]::NewGuid().ToString('N'))
$tempProject = Join-Path $tempProject ('Test ' + [char]0x0422 + [char]0x0435 + [char]0x0441 + [char]0x0442 + " & user's files")
$testParent = Split-Path -Parent $tempProject
$originalLocation = (Get-Location).Path
$savedFinder = (Get-Command Find-Python).ScriptBlock
$savedNoPause = $env:VMOPT_NO_PAUSE
try {
    New-Item -Path (Join-Path $tempProject 'scripts') -ItemType Directory -Force | Out-Null
    New-Item -Path (Join-Path $tempProject 'jetbrains_vmoptions_tuner') -ItemType Directory | Out-Null
    New-Item -Path (Join-Path $tempProject '.venv') -ItemType Directory | Out-Null
    [IO.File]::WriteAllText((Join-Path $tempProject '.venv\preserve.txt'), 'local data')
    Copy-Item -LiteralPath (Join-Path $root 'start.bat') -Destination (Join-Path $tempProject 'start.bat')
    Copy-Item -LiteralPath (Join-Path $root 'scripts\launch.ps1') -Destination (Join-Path $tempProject 'scripts\launch.ps1')
    [IO.File]::WriteAllText((Join-Path $tempProject 'jetbrains_vmoptions_tuner\__init__.py'), '')
    [IO.File]::WriteAllText((Join-Path $tempProject 'jetbrains_vmoptions_tuner\bootstrap.py'), 'raise SystemExit(0)')
    $entry = @'
import json
import sys
from pathlib import Path
Path(__file__).with_name('arguments.json').write_text(json.dumps(sys.argv[1:]))
raise SystemExit(0)
'@
    [IO.File]::WriteAllText((Join-Path $tempProject 'main.py'), $entry)
    function Find-Python { return $realInfo }
    $result = Invoke-Launcher -ProjectRoot $tempProject -SetupOnly
    Assert-True ($result -eq 0) 'Preparing the temporary project failed.'
    $backups = @(Get-ChildItem -LiteralPath $tempProject -Directory -Filter '.venv.backup-*')
    Assert-True ($backups.Count -eq 1) 'An incompatible environment must be backed up exactly once.'
    Assert-True (Test-Path -LiteralPath (Join-Path $backups[0].FullName 'preserve.txt')) 'Local environment files must be preserved.'
    $env:VMOPT_NO_PAUSE = '1'
    & (Join-Path $tempProject 'start.bat') --background
    Assert-True ($LASTEXITCODE -eq 0) 'Batch launch failed for a path containing special characters.'
    $arguments = Get-Content -LiteralPath (Join-Path $tempProject 'arguments.json') -Raw | ConvertFrom-Json
    Assert-True ($arguments[0] -eq '--background') 'Application arguments must survive the batch/PowerShell boundary.'
    Assert-True ((@(Get-ChildItem -LiteralPath $tempProject -Directory -Filter '.venv.backup-*')).Count -eq 1) 'A compatible environment must be reused.'
    Write-Host 'PASS: environment backup, batch argument forwarding and special-character project paths'
} finally {
    Set-Location -LiteralPath $originalLocation
    Set-Item -Path Function:Find-Python -Value $savedFinder
    $env:VMOPT_NO_PAUSE = $savedNoPause
    $resolvedParent = (Resolve-Path -LiteralPath $testParent).Path
    $tempPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($resolvedParent.StartsWith($tempPrefix, [StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path -Leaf $resolvedParent) -match '^vmopt-launch-[a-f0-9]{32}$') {
        Remove-Item -LiteralPath $resolvedParent -Recurse -Force
    }
}
