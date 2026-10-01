$ErrorActionPreference = 'Stop'
try {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($env:VMOPT_SHORTCUT_PATH)
    $shortcut.TargetPath = $env:VMOPT_LAUNCHER_PATH
    $shortcut.WorkingDirectory = Split-Path -Parent $env:VMOPT_LAUNCHER_PATH
    $shortcut.IconLocation = $env:VMOPT_ICON_PATH + ',0'
    $shortcut.Description = 'Launch vmoptions Tuner'
    $shortcut.WindowStyle = 1
    $shortcut.Save()
    exit 0
} catch {
    Write-Error $_
    exit 1
}
