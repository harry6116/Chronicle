@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "STAMP="
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format ''yyyyMMdd_HHmmss''"') do set "STAMP=%%I"
if not defined STAMP set "STAMP=%DATE:~-4%%DATE:~4,2%%DATE:~7,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "STAMP=%STAMP: =0%"

set "LOGFILE=%SCRIPT_DIR%windows_build_diagnostic_%STAMP%.log"

call :main > "%LOGFILE%" 2>&1
set "RUN_EXIT=%ERRORLEVEL%"

echo.
echo Diagnostic log written to:
echo %LOGFILE%
echo Exit code: %RUN_EXIT%
echo.
if not "%CI%"=="true" pause
exit /b %RUN_EXIT%

:main
echo ==================================================
echo CHRONICLE WINDOWS BUILD DIAGNOSTICS
echo ==================================================
echo Timestamp: %DATE% %TIME%
echo Script dir: %SCRIPT_DIR%
echo Computer: %COMPUTERNAME%
echo User: %USERNAME%
echo.

echo ---- Directory Snapshot ----
dir /a
echo.

echo ---- Key Files ----
for %%F in (
    "build_windows.bat"
    "build_windows.ps1"
    "chronicle_gui.py"
    "chronicle_runtime.py"
    "chronicle_core.py"
    "requirements.txt"
    "assets"
    "docs"
    "hooks"
) do (
    if exist %%~F (
        echo [OK] %%~F
    ) else (
        echo [MISSING] %%~F
    )
)
echo.

set "PYTHON_BIN=python"
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" set "PYTHON_BIN=%SCRIPT_DIR%.venv\Scripts\python.exe"
if exist "%SCRIPT_DIR%venv311\Scripts\python.exe" set "PYTHON_BIN=%SCRIPT_DIR%venv311\Scripts\python.exe"

echo ---- Python Resolution ----
echo Requested python: %PYTHON_BIN%
where python
echo.
"%PYTHON_BIN%" --version
if errorlevel 1 (
    echo ERROR: Python could not be started.
    exit /b 10
)
echo.

echo ---- Pip / Package Snapshot ----
"%PYTHON_BIN%" -m pip --version
echo.
"%PYTHON_BIN%" -m pip show pyinstaller
echo.
"%PYTHON_BIN%" -m pip show pyinstaller-hooks-contrib
echo.
"%PYTHON_BIN%" -m pip show wxPython
echo.

echo ---- Environment ----
echo APPDATA=%APPDATA%
echo USERPROFILE=%USERPROFILE%
echo PYINSTALLER_CONFIG_DIR=%PYINSTALLER_CONFIG_DIR%
echo PYTHONWARNINGS=%PYTHONWARNINGS%
echo.

set "PYTHONFAULTHANDLER=1"
set "PYTHONUNBUFFERED=1"

echo ---- Running Diagnostic Build ----
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%build_windows.ps1"
set "BUILD_EXIT=%ERRORLEVEL%"
echo.
echo Diagnostic build exit code: %BUILD_EXIT%
echo.

echo ---- Post-Run Snapshot ----
if exist dist (
    echo [dist]
    dir /s /a dist
) else (
    echo dist not created
)
echo.
if exist build (
    echo [build]
    dir /s /a build
) else (
    echo build not created
)
echo.
if exist .pyinstaller-cache (
    echo [.pyinstaller-cache]
    dir /s /a .pyinstaller-cache
) else (
    echo .pyinstaller-cache not created
)
echo.

exit /b %BUILD_EXIT%
