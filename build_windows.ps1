$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appDataBase = if ($env:APPDATA) { $env:APPDATA } else { $rootDir }
$logDir = Join-Path $appDataBase "Chronicle\logs"
$desktopDir = if ($env:USERPROFILE) { Join-Path $env:USERPROFILE "Desktop" } else { $rootDir }
$easyLog = Join-Path $desktopDir "Chronicle_Last_Build_Log.txt"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "windows_build_$timestamp.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-Log {
    param([string]$Message)
    $Message | Tee-Object -FilePath $logFile -Append | Tee-Object -FilePath $easyLog -Append | Out-Host
}

function Fail-Build {
    param([string]$Message, [int]$Code = 1)
    Write-Log ""
    Write-Log "ERROR: $Message"
    Write-Log "Full log: $logFile"
    Write-Log "Desktop log: $easyLog"
    exit $Code
}

function Invoke-PyInstallerBuild {
    param(
        [string]$PythonBin,
        [string[]]$Arguments,
        [hashtable]$Environment
    )

    $previousConfigDir = $env:PYINSTALLER_CONFIG_DIR
    $previousWarnings = $env:PYTHONWARNINGS

    try {
        if ($Environment.ContainsKey("PYINSTALLER_CONFIG_DIR")) {
            $env:PYINSTALLER_CONFIG_DIR = $Environment["PYINSTALLER_CONFIG_DIR"]
        }
        if ($Environment.ContainsKey("PYTHONWARNINGS")) {
            $env:PYTHONWARNINGS = $Environment["PYTHONWARNINGS"]
        }

        & $PythonBin $Arguments 2>&1 |
            Tee-Object -FilePath $logFile -Append |
            Tee-Object -FilePath $easyLog -Append |
            Out-Host
        return $LASTEXITCODE
    } finally {
        $env:PYINSTALLER_CONFIG_DIR = $previousConfigDir
        $env:PYTHONWARNINGS = $previousWarnings
    }
}

Set-Content -Path $easyLog -Value "" -Encoding UTF8
Write-Log "--------------------------------------------------"
Write-Log "CHRONICLE ACCESSIBILITY BUILD (WINDOWS / POWERSHELL)"
Write-Log "--------------------------------------------------"
Write-Log "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Log "Root dir:  $rootDir"
Write-Log "Log file:  $logFile"
Write-Log "Desktop:   $easyLog"
Write-Log ""

$pythonBin = "python"
$venvCandidates = @(
    (Join-Path $rootDir ".venv\Scripts\python.exe"),
    (Join-Path $rootDir "venv311\Scripts\python.exe")
)
foreach ($candidate in $venvCandidates) {
    if (Test-Path $candidate) {
        $pythonBin = $candidate
        break
    }
}

Write-Log "Python: $pythonBin"
try {
    $resolvedPython = (Get-Command $pythonBin -ErrorAction Stop).Source
    Write-Log "Resolved Python: $resolvedPython"
} catch {
    Write-Log "WARNING: Python executable was not resolved by Get-Command."
}

$requiredPaths = @(
    @{ Label = "chronicle_gui.py"; Path = (Join-Path $rootDir "chronicle_gui.py"); Required = $true },
    @{ Label = "chronicle.py"; Path = (Join-Path $rootDir "chronicle.py"); Required = $true },
    @{ Label = "chronicle_core.py"; Path = (Join-Path $rootDir "chronicle_core.py"); Required = $true },
    @{ Label = "chronicle_app"; Path = (Join-Path $rootDir "chronicle_app"); Required = $true },
    @{ Label = "chronicle_app\services"; Path = (Join-Path $rootDir "chronicle_app\services"); Required = $true },
    @{ Label = "chronicle_app\ui"; Path = (Join-Path $rootDir "chronicle_app\ui"); Required = $true },
    @{ Label = "requirements.txt"; Path = (Join-Path $rootDir "requirements.txt"); Required = $true },
    @{ Label = "assets"; Path = (Join-Path $rootDir "assets"); Required = $true },
    @{ Label = "docs"; Path = (Join-Path $rootDir "docs"); Required = $true }
)

foreach ($item in $requiredPaths) {
    if (Test-Path $item.Path) {
        Write-Log "[OK] $($item.Label): $($item.Path)"
    } elseif ($item.Required) {
        Fail-Build "Missing required path: $($item.Path)"
    }
}

$buildStamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Set-Content -Path (Join-Path $rootDir "build_stamp.txt") -Value $buildStamp -Encoding UTF8
Write-Log "Build stamp: $buildStamp"

$staleArtifacts = @(
    (Join-Path $rootDir "build"),
    (Join-Path $rootDir "dist"),
    (Join-Path $rootDir "Chronicle.spec"),
    (Join-Path $rootDir ".pyinstaller-cache")
)
foreach ($artifact in $staleArtifacts) {
    if (Test-Path $artifact) {
        Write-Log "Removing stale build artifact: $artifact"
        Remove-Item -Recurse -Force $artifact
    }
}

Write-Log "Latest resource roots will be bundled from the current workspace:"
Write-Log "- Assets: $(Join-Path $rootDir 'assets')"
Write-Log "- Docs:   $(Join-Path $rootDir 'docs')"

Write-Log ""
Write-Log "Installing requirements..."
& $pythonBin -m pip install -r (Join-Path $rootDir "requirements.txt") 2>&1 |
    Tee-Object -FilePath $logFile -Append |
    Tee-Object -FilePath $easyLog -Append |
    Out-Host
if ($LASTEXITCODE -ne 0) {
    Fail-Build "Dependency install failed."
}

Write-Log ""
Write-Log "PyInstaller version:"
& $pythonBin -m PyInstaller --version 2>&1 |
    Tee-Object -FilePath $logFile -Append |
    Tee-Object -FilePath $easyLog -Append |
    Out-Host
if ($LASTEXITCODE -ne 0) {
    Fail-Build "PyInstaller is not available."
}

$iconPath = Join-Path $rootDir "assets\icons\chronicle_option3.ico"
$hooksDir = Join-Path $rootDir "hooks"
$pyinstallerCache = Join-Path $rootDir ".pyinstaller-cache"
$setuptoolsPath = & $pythonBin -c "import pathlib, setuptools; print(pathlib.Path(setuptools.__file__).resolve().parent)" 2>$null
$jaracoPath = $null
if ($LASTEXITCODE -eq 0 -and $setuptoolsPath) {
    $jaracoPath = Join-Path $setuptoolsPath "_vendor\jaraco"
}

$pyArgs = [System.Collections.Generic.List[string]]::new()
$pyArgs.AddRange([string[]]@(
    "-m", "PyInstaller",
    "--noconfirm",
    "--windowed",
    "--disable-windowed-traceback",
    "--name", "Chronicle"
))
if (Test-Path $hooksDir) {
    $pyArgs.Add("--additional-hooks-dir")
    $pyArgs.Add($hooksDir)
}
if (Test-Path $iconPath) {
    $pyArgs.Add("--icon")
    $pyArgs.Add($iconPath)
} else {
    Write-Log "WARNING: icon not found at $iconPath"
}

$pyArgs.Add("--add-data")
$pyArgs.Add("$rootDir\assets;assets")
$pyArgs.Add("--add-data")
$pyArgs.Add("$rootDir\docs;docs")
$pyArgs.Add("--add-data")
$pyArgs.Add("$rootDir\build_stamp.txt;.")
if ($jaracoPath -and (Test-Path $jaracoPath)) {
    $pyArgs.Add("--add-data")
    $pyArgs.Add("$jaracoPath;setuptools/_vendor/jaraco")
} else {
    Write-Log "WARNING: setuptools jaraco vendor path not found."
}

$pyArgs.AddRange([string[]]@(
    "--hidden-import", "wx",
    "--hidden-import", "wx.adv",
    "--hidden-import", "wx.dataview",
    "--hidden-import", "wx._adv",
    "--hidden-import", "wx.html",
    "--hidden-import", "wx.xml",
    "--hidden-import", "pydantic",
    "--hidden-import", "pydantic_core",
    "--hidden-import", "pydantic_core._pydantic_core",
    "--hidden-import", "httpx",
    "--hidden-import", "anyio",
    "--hidden-import", "certifi",
    "--hidden-import", "google.genai",
    "--hidden-import", "google.genai.types",
    "--hidden-import", "google.genai.errors",
    "--hidden-import", "fitz",
    "--hidden-import", "setuptools._vendor.jaraco.text",
    "--collect-submodules", "chronicle_app",
    "--collect-submodules", "google.auth",
    "--collect-submodules", "google.oauth2",
    "--collect-all", "anthropic",
    "--collect-all", "openai",
    "--collect-all", "fitz",
    "--collect-all", "docx",
    "--collect-all", "lxml",
    "--collect-all", "bs4",
    "--collect-all", "html5lib",
    "--collect-all", "openpyxl",
    "--collect-all", "cv2",
    "--collect-all", "ebooklib",
    "--collect-all", "fpdf",
    "--collect-all", "PIL",
    "--collect-all", "pydantic",
    "--collect-all", "httpx",
    "--collect-all", "setuptools",
    "--exclude-module", "google.genai.tests",
    "--exclude-module", "setuptools.tests",
    "--exclude-module", "numpy.tests",
    "--exclude-module", "numpy.f2py.tests",
    "--exclude-module", "wx.lib.pubsub",
    "--exclude-module", "wx.lib.pubsub.core.datamsg",
    "--exclude-module", "wx.lib.pubsub.core.kwargs",
    "--exclude-module", "pycparser.lextab",
    "--exclude-module", "pycparser.yacctab",
    "--exclude-module", "charset_normalizer.md__mypyc",
    "--exclude-module", "pydantic.v1",
    (Join-Path $rootDir "chronicle_gui.py")
))

New-Item -ItemType Directory -Force -Path $pyinstallerCache | Out-Null
$pyinstallerEnv = @{
    "PYINSTALLER_CONFIG_DIR" = $pyinstallerCache
    "PYTHONWARNINGS" = "ignore:Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater."
}

Write-Log ""
Write-Log "Building frozen Windows executable..."
Write-Log "PyInstaller command:"
Write-Log "$pythonBin $($pyArgs -join ' ')"
Push-Location $rootDir
try {
    New-Item -ItemType Directory -Force -Path (Join-Path $rootDir "dist\Chronicle\_internal\wx") | Out-Null
    $buildExit = Invoke-PyInstallerBuild -PythonBin $pythonBin -Arguments $pyArgs.ToArray() -Environment $pyinstallerEnv
    if ($buildExit -ne 0) {
        Write-Log ""
        Write-Log "First PyInstaller pass failed (exit $buildExit). Retrying once after re-priming wx path..."
        New-Item -ItemType Directory -Force -Path (Join-Path $rootDir "dist\Chronicle\_internal\wx") | Out-Null
        $buildExit = Invoke-PyInstallerBuild -PythonBin $pythonBin -Arguments $pyArgs.ToArray() -Environment $pyinstallerEnv
    }
    if ($buildExit -ne 0) {
        Fail-Build "PyInstaller build failed."
    }
} finally {
    Pop-Location
}

Write-Log ""
Write-Log "SUCCESS: Open the dist folder for Chronicle.exe"
Write-Log "Full log: $logFile"
Write-Log "Desktop log: $easyLog"
exit 0
