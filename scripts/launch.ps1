param(
    [switch]$PrepareOnly,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ApplicationArguments
)

$ErrorActionPreference = 'Stop'

function Test-PythonExecutable {
    param([string]$Executable)
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
    # No quoted Python strings: Windows PowerShell 5.1 passes this -c argument
    # intact under its legacy native-argument rules.
    $probe = 'import json, sys, venv; print(json.dumps(dict(version=list(sys.version_info[:3]), executable=sys.executable, implementation=sys.implementation.name, prefix=sys.prefix, base_prefix=sys.base_prefix, details=sys.version, releaselevel=sys.version_info.releaselevel)))'
    try {
        $output = & $Executable -I -c $probe 2>$null
        if ($LASTEXITCODE -ne 0) { return $null }
        $info = ($output -join "`n") | ConvertFrom-Json
        if ($info.implementation -ne 'cpython' -or $info.releaselevel -ne 'final') { return $null }
        if ($info.version[0] -ne 3 -or $info.version[1] -lt 13) { return $null }
        if ($info.details -match 'free.threading') { return $null }
        if ($info.executable -match '\\WindowsApps\\') { return $null }
        return $info
    } catch {
        return $null
    }
}

function Get-PythonCandidates {
    foreach ($commandName in @('python.exe', 'python3.exe')) {
        foreach ($command in @(Get-Command $commandName -All -ErrorAction SilentlyContinue)) {
            # Skip Store aliases; probing them can open the Store or install a
            # runtime. py --list-paths below also supports Python Install Manager.
            if ($command.Source -notmatch '\\Microsoft\\WindowsApps\\') { $command.Source }
        }
    }
    foreach ($commandName in @('py.exe', 'pymanager.exe')) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command) {
            try {
                $paths = & $command.Source --list-paths 2>$null
                if ($LASTEXITCODE -eq 0) {
                    foreach ($line in $paths) {
                        if ($line -match '(?i)([a-z]:\\.*\\python(?:\d+(?:\.\d+)*)?\.exe)\s*$') {
                            $Matches[1]
                        }
                    }
                }
            } catch { }
        }
    }
    # PEP 514 registrations include custom install locations and installations
    # that are not on PATH. Inspect both registry views on 64-bit Windows.
    foreach ($hive in @([Microsoft.Win32.RegistryHive]::CurrentUser, [Microsoft.Win32.RegistryHive]::LocalMachine)) {
        foreach ($view in @([Microsoft.Win32.RegistryView]::Registry64, [Microsoft.Win32.RegistryView]::Registry32)) {
            $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($hive, $view)
            try {
                $pythonKey = $base.OpenSubKey('Software\Python')
                if (-not $pythonKey) { continue }
                try {
                    foreach ($companyName in $pythonKey.GetSubKeyNames()) {
                        $company = $pythonKey.OpenSubKey($companyName)
                        try {
                            foreach ($tag in $company.GetSubKeyNames()) {
                                $install = $company.OpenSubKey($tag + '\InstallPath')
                                if ($install) {
                                    try {
                                        $executable = $install.GetValue('ExecutablePath')
                                        if ($executable) { [string]$executable }
                                        $prefix = $install.GetValue('')
                                        if ($prefix) { Join-Path ([string]$prefix) 'python.exe' }
                                    } finally { $install.Dispose() }
                                }
                            }
                        } finally { $company.Dispose() }
                    }
                } finally { $pythonKey.Dispose() }
            } finally { $base.Dispose() }
        }
    }
    if ($env:LOCALAPPDATA) {
        foreach ($pattern in @('Programs\Python\Python*\python.exe', 'Python\pythoncore-*\python.exe')) {
            Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA $pattern) -File -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty FullName
        }
    }
}

function Find-Python {
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $usable = foreach ($candidate in Get-PythonCandidates) {
        if ($seen.Add($candidate)) {
            $info = Test-PythonExecutable $candidate
            if ($info) { $info }
        }
    }
    $usable | Sort-Object -Property @{Expression = { [version]($_.version -join '.') }; Descending = $true} |
        Select-Object -First 1
}

function Install-Python {
    Write-Host 'No suitable Python found. Installing CPython 3.13 for the current user...'
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if ($winget) {
        & $winget.Source install --exact --id Python.Python.3.13 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
        $python = Find-Python
        if ($python) { return $python }
        Write-Host 'WinGet did not provide a usable Python. Trying the official installer...'
    }
    # Fallback for systems without App Installer/WinGet. Keep this maintenance
    # release current; verify the publisher before running the downloaded file.
    $version = '3.13.15'
    $architecture = 'amd64'
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') {
        $architecture = 'arm64'
    }
    $installer = Join-Path ([IO.Path]::GetTempPath()) ('vmopt-python-' + [Guid]::NewGuid().ToString('N') + '.exe')
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri "https://www.python.org/ftp/python/$version/python-$version-$architecture.exe" -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(CN|O)=Python Software Foundation(,|$)') {
            throw 'The Python installer signature could not be verified.'
        }
        $process = Start-Process -FilePath $installer -ArgumentList '/quiet InstallAllUsers=0 Include_pip=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_test=0 PrependPath=1 Shortcuts=0' -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) { throw "Python installer exited with code $($process.ExitCode)." }
    } finally {
        if (Test-Path -LiteralPath $installer) { Remove-Item -LiteralPath $installer -Force }
    }
    $python = Find-Python
    if (-not $python) { throw 'Install CPython 3.13+ from https://www.python.org/downloads/windows/ and run start.bat again.' }
    return $python
}

function Invoke-Launcher {
    param([string]$ProjectRoot, [switch]$SetupOnly, [string[]]$Arguments)
    $ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
    Set-Location -LiteralPath $ProjectRoot
    $venvPath = Join-Path $ProjectRoot '.venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    $existing = Test-PythonExecutable $venvPython
    if (-not $existing) {
        $python = Find-Python
        if (-not $python) { $python = Install-Python }
        if (Test-Path -LiteralPath $venvPath) {
            # Preserve incompatible/broken environments instead of deleting
            # local packages. Refuse to move a junction or an external path.
            $item = Get-Item -LiteralPath $venvPath -Force
            $backupPath = Join-Path $ProjectRoot ('.venv.backup-' + [Guid]::NewGuid().ToString('N'))
            $rootPrefix = $ProjectRoot.TrimEnd('\') + '\'
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
                -not $item.FullName.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -or
                -not [IO.Path]::GetFullPath($backupPath).StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Cannot replace .venv: it resolves outside the project or is a junction.'
            }
            Move-Item -LiteralPath $item.FullName -Destination $backupPath
            Write-Host 'The previous .venv was preserved in' $backupPath
        }
        Write-Host 'Using Python' ($python.version -join '.') 'at' $python.executable
        & $python.executable -m venv $venvPath | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the project virtual environment.' }
    } else {
        Write-Host 'Using the project environment at' $venvPython
    }
    & $venvPython -m jetbrains_vmoptions_tuner.bootstrap | Out-Host
    if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed. Fix the error above and run start.bat again.' }
    if ($SetupOnly) { return 0 }
    & $venvPython (Join-Path $ProjectRoot 'main.py') @Arguments | Out-Host
    return $LASTEXITCODE
}

# Dot-sourcing exposes discovery/setup functions to the Windows test script.
if ($MyInvocation.InvocationName -ne '.') {
    try {
        $result = Invoke-Launcher -ProjectRoot (Split-Path -Parent $PSScriptRoot) -SetupOnly:$PrepareOnly -Arguments $ApplicationArguments
        exit $result
    } catch {
        Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
        exit 1
    }
}
