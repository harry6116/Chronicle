@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"

call :say Chronicle Windows launcher
call :say Bundle root: "%SCRIPT_DIR%"
call :say

if /I "%~1"=="--diagnostics" goto diagnostics

call :resolve_powershell
if defined POWERSHELL_EXE goto run_powershell
call :say ERROR: Neither PowerShell 7 nor Windows PowerShell was found.
call :say Checked Program Files, Windows system folders, Sysnative, hardcoded C:\Windows, and PATH.
exit /b 9009

:diagnostics
shift /1
if exist "%SCRIPT_DIR%capture_windows_build_diagnostics.bat" goto run_diagnostics
call :say ERROR: Diagnostic builder not found:
call :say "%SCRIPT_DIR%capture_windows_build_diagnostics.bat"
exit /b 3

:run_diagnostics
call :say Diagnostic builder: "%SCRIPT_DIR%capture_windows_build_diagnostics.bat"
call "%SCRIPT_DIR%capture_windows_build_diagnostics.bat" %*
set "BUILD_EXIT=%ERRORLEVEL%"

if not "%BUILD_EXIT%"=="0" (
    call :say
    call :say Build failed with exit code %BUILD_EXIT%.
    if "%CI%"=="" if "%GITHUB_ACTIONS%"=="" pause
)

exit /b %BUILD_EXIT%

:run_powershell
call :say PowerShell builder: "%POWERSHELL_EXE%"
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_windows.ps1" %*
goto after_build

:resolve_powershell
set "POWERSHELL_EXE="
if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "POWERSHELL_EXE=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined POWERSHELL_EXE if defined ProgramW6432 if exist "%ProgramW6432%\PowerShell\7\pwsh.exe" set "POWERSHELL_EXE=%ProgramW6432%\PowerShell\7\pwsh.exe"
if not defined POWERSHELL_EXE if defined SystemRoot if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE if defined SystemRoot if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE if defined WINDIR if exist "%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE if defined WINDIR if exist "%WINDIR%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=%WINDIR%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE if exist "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE if exist "C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL_EXE=C:\Windows\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
if not defined POWERSHELL_EXE for /f "delims=" %%P in ('where pwsh.exe 2^>nul') do if not defined POWERSHELL_EXE set "POWERSHELL_EXE=%%P"
if not defined POWERSHELL_EXE for /f "delims=" %%P in ('where powershell.exe 2^>nul') do if not defined POWERSHELL_EXE set "POWERSHELL_EXE=%%P"
exit /b 0

:say
echo(%*
if defined CHRONICLE_SYNC_TRACE_LOG >> "%CHRONICLE_SYNC_TRACE_LOG%" echo(%*
exit /b 0

:after_build
set "BUILD_EXIT=%ERRORLEVEL%"

if not "%BUILD_EXIT%"=="0" (
    call :say
    call :say Build failed with exit code %BUILD_EXIT%.
    if "%CI%"=="" if "%GITHUB_ACTIONS%"=="" pause
)

exit /b %BUILD_EXIT%
