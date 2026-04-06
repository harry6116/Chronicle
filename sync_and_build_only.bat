@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Parallels VM workflow: sync from Mac Documents and build on internal Windows
rem Documents only. No automatic copy-back of dist. Use this when the shared
rem folder is too slow or unreliable for returning the packaged app.

set "MAC_SHARED_ROOT=\\Mac\Home\Documents"
set "MAC_SOURCE=%MAC_SHARED_ROOT%\Chronicle windows Beta"
set "WIN_INTERNAL_ROOT=%USERPROFILE%\Documents"
set "WIN_WORKTREE=%WIN_INTERNAL_ROOT%\Chronicle windows Beta"
set "TRACE_LOG=%WIN_WORKTREE%\SYNC_AND_BUILD_ONLY_TRACE.txt"

echo ==================================================
echo Chronicle VM Sync And Build Only
echo ==================================================
echo Mac source:    %MAC_SOURCE%
echo Windows build: %WIN_WORKTREE%
echo.

if not exist "%MAC_SOURCE%" (
    echo ERROR: Mac source folder is not visible:
    echo %MAC_SOURCE%
    pause
    exit /b 2
)

mkdir "%WIN_WORKTREE%" 2>nul

> "%TRACE_LOG%" (
    echo Chronicle VM Sync And Build Only Trace
    echo Mac source: %MAC_SOURCE%
    echo Windows build: %WIN_WORKTREE%
    echo.
)

echo [1/2] Syncing Mac source into internal Windows Documents...
>> "%TRACE_LOG%" echo [1/2] Syncing Mac source into internal Windows Documents...
robocopy "%MAC_SOURCE%" "%WIN_WORKTREE%" /MIR /R:1 /W:1 /NFL /NDL /NP /XD ^
    ".git" ".venv" "venv311" "build" "dist" ".pyinstaller-cache" "__pycache__" ^
    "artifacts" ".pytest_cache" ".worktrees" >nul
set "SYNC_EXIT=%ERRORLEVEL%"
>> "%TRACE_LOG%" echo robocopy sync exit code: %SYNC_EXIT%
if %SYNC_EXIT% GEQ 8 (
    echo ERROR: Source sync failed with robocopy exit code %SYNC_EXIT%.
    >> "%TRACE_LOG%" echo ERROR: Source sync failed with robocopy exit code %SYNC_EXIT%.
    pause
    exit /b %SYNC_EXIT%
)

if not exist "%WIN_WORKTREE%\build_windows.bat" (
    echo ERROR: build_windows.bat missing after sync.
    >> "%TRACE_LOG%" echo ERROR: build_windows.bat missing after sync.
    pause
    exit /b 4
)

echo [2/2] Building from internal Windows Documents...
>> "%TRACE_LOG%" echo [2/2] Building from internal Windows Documents...
pushd "%WIN_WORKTREE%" || exit /b 5
call "%WIN_WORKTREE%\build_windows.bat"
set "BUILD_EXIT=%ERRORLEVEL%"
popd
>> "%TRACE_LOG%" echo build exit code: %BUILD_EXIT%

echo.
echo Build exit code: %BUILD_EXIT%
echo Internal Windows build folder:
echo %WIN_WORKTREE%
echo Dist folder:
echo %WIN_WORKTREE%\dist
echo Trace log:
echo %TRACE_LOG%
echo.

if exist "%WIN_WORKTREE%\dist" (
    echo dist folder exists.
    >> "%TRACE_LOG%" echo dist folder exists.
) else (
    echo dist folder was not created.
    >> "%TRACE_LOG%" echo dist folder was not created.
)

if not "%BUILD_EXIT%"=="0" (
    echo Build failed.
    pause
    exit /b %BUILD_EXIT%
)

echo Build finished successfully.
echo You can now copy the finished dist folder or a packaged artifact manually.
pause
exit /b 0
