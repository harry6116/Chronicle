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

echo ---- Refresh Build Stamp ----
powershell -NoProfile -Command "Set-Content -Path '%SCRIPT_DIR%build_stamp.txt' -Value (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') -Encoding UTF8"
if errorlevel 1 (
    echo ERROR: Could not update build_stamp.txt
    exit /b 12
)
type "%SCRIPT_DIR%build_stamp.txt"
echo.

echo ---- Local Cleanup ----
for %%D in ("build" "dist" ".pyinstaller-cache" "Chronicle.spec") do (
    if exist %%~D (
        echo Removing %%~D
        rmdir /s /q %%~D 2>nul
        del /f /q %%~D 2>nul
    ) else (
        echo Not present: %%~D
    )
)
echo.

set "LOCAL_PYI_CACHE=%SCRIPT_DIR%.pyinstaller-cache"
mkdir "%LOCAL_PYI_CACHE%" 2>nul
set "PYINSTALLER_CONFIG_DIR=%LOCAL_PYI_CACHE%"
set "PYTHONFAULTHANDLER=1"
set "PYTHONUNBUFFERED=1"
set "PYTHONWARNINGS=ignore:Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater."

echo ---- PyInstaller Version ----
"%PYTHON_BIN%" -X faulthandler -m PyInstaller --version
if errorlevel 1 (
    echo ERROR: PyInstaller version probe failed.
    exit /b 11
)
echo.

echo ---- Diagnostic Build Command ----
set "PYI_ARGS=-m PyInstaller --noconfirm --windowed --disable-windowed-traceback --name Chronicle --additional-hooks-dir "%SCRIPT_DIR%hooks" --icon "%SCRIPT_DIR%assets\icons\chronicle_option3.ico" --add-data "%SCRIPT_DIR%assets;assets" --add-data "%SCRIPT_DIR%docs;docs" --add-data "%SCRIPT_DIR%build_stamp.txt;." --hidden-import wx --hidden-import wx.adv --hidden-import wx.dataview --hidden-import wx._adv --hidden-import wx.html --hidden-import wx.xml --hidden-import pydantic --hidden-import pydantic_core --hidden-import pydantic_core._pydantic_core --hidden-import httpx --hidden-import anyio --hidden-import certifi --hidden-import google.genai --hidden-import google.genai.types --hidden-import google.genai.errors --hidden-import fitz --hidden-import setuptools._vendor.jaraco.text --collect-submodules chronicle_app --collect-submodules google.auth --collect-submodules google.oauth2 --collect-all anthropic --collect-all openai --collect-all fitz --collect-all docx --collect-all lxml --collect-all openpyxl --collect-all cv2 --collect-all ebooklib --collect-all fpdf --collect-all PIL --collect-all pydantic --collect-all httpx --collect-all setuptools --exclude-module google.genai.tests --exclude-module setuptools.tests --exclude-module numpy.tests --exclude-module numpy.f2py.tests --exclude-module wx.lib.pubsub --exclude-module wx.lib.pubsub.core.datamsg --exclude-module wx.lib.pubsub.core.kwargs --exclude-module pycparser.lextab --exclude-module pycparser.yacctab --exclude-module charset_normalizer.md__mypyc --exclude-module pydantic.v1 "%SCRIPT_DIR%chronicle_gui.py""
echo "%PYTHON_BIN%" -X faulthandler %PYI_ARGS%
echo.

echo ---- Running Diagnostic Build ----
"%PYTHON_BIN%" -X faulthandler %PYI_ARGS%
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
