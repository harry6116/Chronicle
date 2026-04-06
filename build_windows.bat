@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

echo Chronicle Windows launcher
echo Bundle root: "%SCRIPT_DIR%"
echo Preferred builder: "%SCRIPT_DIR%capture_windows_build_diagnostics.bat"
echo.

if exist "%SCRIPT_DIR%capture_windows_build_diagnostics.bat" (
    call "%SCRIPT_DIR%capture_windows_build_diagnostics.bat" %*
) else (
    set "POWERSHELL_EXE=powershell"
    where pwsh >nul 2>nul && set "POWERSHELL_EXE=pwsh"
    echo Fallback PowerShell builder: "%POWERSHELL_EXE%"
    "%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_windows.ps1" %*
)
set "BUILD_EXIT=%ERRORLEVEL%"

if not "%BUILD_EXIT%"=="0" (
    echo.
    echo Build failed with exit code %BUILD_EXIT%.
    if "%CI%"=="" if "%GITHUB_ACTIONS%"=="" pause
)

exit /b %BUILD_EXIT%
