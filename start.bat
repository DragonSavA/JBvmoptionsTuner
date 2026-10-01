@echo off
setlocal DisableDelayedExpansion
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch.ps1" %*
set "VMOPT_EXIT_CODE=%ERRORLEVEL%"
if not "%VMOPT_EXIT_CODE%"=="0" (
    echo.
    echo vmoptions Tuner could not start. See the error above.
    if not defined VMOPT_NO_PAUSE pause
)
exit /b %VMOPT_EXIT_CODE%
