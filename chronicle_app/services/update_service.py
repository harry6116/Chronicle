from __future__ import annotations

import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_URL = "https://github.com/harry6116/Chronicle"
RELEASES_API_URL = "https://api.github.com/repos/harry6116/Chronicle/releases?per_page=100"
USER_AGENT = "Chronicle updater"
WINDOWS_ASSET_NAME = "Chronicle.windows.zip"
MAC_ASSET_NAME = "Chronicle.mac.zip"


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    browser_download_url: str


@dataclass(frozen=True)
class ReleaseInfo:
    tag_name: str
    html_url: str
    body: str
    assets: tuple[ReleaseAsset, ...]


@dataclass(frozen=True)
class UpdateCheckResult:
    status: str
    current_version: str
    latest_version: str = ""
    release: ReleaseInfo | None = None
    asset: ReleaseAsset | None = None
    notes: str = ""
    message: str = ""


def platform_asset_name(system_name: str | None = None) -> str:
    system = system_name or platform.system()
    if system == "Windows":
        return WINDOWS_ASSET_NAME
    if system == "Darwin":
        return MAC_ASSET_NAME
    return ""


def platform_supports_automatic_install(system_name: str | None = None) -> bool:
    return (system_name or platform.system()) in {"Windows", "Darwin"}


def parse_version(value: str) -> tuple[int, ...] | None:
    text = (value or "").strip()
    if text.lower().startswith("v"):
        text = text[1:]
    match = re.match(r"^(\d+(?:\.\d+){0,3})", text)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def compare_versions(left: str, right: str) -> int:
    left_parts = parse_version(left)
    right_parts = parse_version(right)
    if left_parts is None or right_parts is None:
        raise ValueError("Could not parse version.")
    width = max(len(left_parts), len(right_parts))
    normalized_left = left_parts + (0,) * (width - len(left_parts))
    normalized_right = right_parts + (0,) * (width - len(right_parts))
    if normalized_left < normalized_right:
        return -1
    if normalized_left > normalized_right:
        return 1
    return 0


def pending_update_reminder(settings: dict, current_version: str) -> str:
    version = str(settings.get("update_reminder_version") or "").strip()
    if not version:
        return ""
    try:
        return version if compare_versions(version, current_version) > 0 else ""
    except ValueError:
        return ""


def fetch_releases(urlopen=urllib.request.urlopen) -> list[ReleaseInfo]:
    request = urllib.request.Request(RELEASES_API_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=20) as response:
        payload = response.read().decode("utf-8")
    return parse_releases(payload)


def parse_releases(payload: str) -> list[ReleaseInfo]:
    rows = json.loads(payload or "[]")
    releases: list[ReleaseInfo] = []
    if not isinstance(rows, list):
        return releases
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("draft") or row.get("prerelease"):
            continue
        assets = []
        for asset in row.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            assets.append(
                ReleaseAsset(
                    name=str(asset.get("name") or ""),
                    browser_download_url=str(asset.get("browser_download_url") or ""),
                )
            )
        releases.append(
            ReleaseInfo(
                tag_name=str(row.get("tag_name") or ""),
                html_url=str(row.get("html_url") or ""),
                body=str(row.get("body") or ""),
                assets=tuple(assets),
            )
        )
    return releases


def find_platform_asset(release: ReleaseInfo, system_name: str | None = None) -> ReleaseAsset | None:
    expected = platform_asset_name(system_name)
    if not expected:
        return None
    for asset in release.assets:
        if asset.name.lower() == expected.lower() and asset.browser_download_url:
            return asset
    return None


def release_version(release: ReleaseInfo) -> tuple[int, ...] | None:
    return parse_version(release.tag_name)


def latest_platform_release(releases: list[ReleaseInfo], system_name: str | None = None) -> tuple[ReleaseInfo, ReleaseAsset] | tuple[None, None]:
    candidates = []
    for release in releases:
        version = release_version(release)
        asset = find_platform_asset(release, system_name)
        if version is not None and asset is not None:
            candidates.append((version, release, asset))
    if not candidates:
        return None, None
    _, release, asset = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
    return release, asset


def check_for_updates(current_version: str, system_name: str | None = None, urlopen=urllib.request.urlopen) -> UpdateCheckResult:
    asset_name = platform_asset_name(system_name)
    if not asset_name:
        return UpdateCheckResult(
            status="unsupported_platform",
            current_version=current_version,
            message="Built-in update checks are currently available for Windows and macOS releases only.",
        )
    try:
        releases = fetch_releases(urlopen=urlopen)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            message=f"Could not check GitHub releases: {exc}",
        )
    release, asset = latest_platform_release(releases, system_name)
    if release is None or asset is None:
        return UpdateCheckResult(
            status="no_platform_release",
            current_version=current_version,
            message=f"No Chronicle release with {asset_name} was found.",
        )
    latest = (release.tag_name or "").strip().lstrip("vV")
    try:
        comparison = compare_versions(current_version, latest)
    except ValueError:
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            latest_version=latest,
            release=release,
            asset=asset,
            message="Could not compare the current Chronicle version with the latest release version.",
        )
    notes = build_update_release_notes(releases, current_version, latest, system_name=system_name)
    if comparison >= 0:
        return UpdateCheckResult(
            status="up_to_date",
            current_version=current_version,
            latest_version=latest,
            release=release,
            asset=asset,
            notes=notes,
            message=f"Chronicle is up to date. Current version: {current_version}.",
        )
    return UpdateCheckResult(
        status="available",
        current_version=current_version,
        latest_version=latest,
        release=release,
        asset=asset,
        notes=notes,
        message=f"Chronicle {latest} is available.",
    )


def build_update_release_notes(
    releases: list[ReleaseInfo],
    current_version: str,
    latest_version: str,
    *,
    system_name: str | None = None,
) -> str:
    current = parse_version(current_version)
    latest = parse_version(latest_version)
    lines = [
        f"Your version: {current_version}",
        f"New version: {latest_version}",
        "",
        f"Changes between {current_version} and {latest_version}",
    ]
    if current is None or latest is None:
        lines.extend(["", "No release notes were provided for this update."])
        return "\n".join(lines).strip()
    newer = []
    for release in releases:
        version = release_version(release)
        if version is None or find_platform_asset(release, system_name) is None:
            continue
        width = max(len(current), len(latest), len(version))
        normalized_version = version + (0,) * (width - len(version))
        normalized_current = current + (0,) * (width - len(current))
        normalized_latest = latest + (0,) * (width - len(latest))
        if normalized_current < normalized_version <= normalized_latest:
            newer.append((normalized_version, release))
    if not newer:
        lines.extend(["", "No release notes were provided for this update."])
        return "\n".join(lines).strip()
    for _, release in sorted(newer, key=lambda item: item[0]):
        lines.extend(["", release.tag_name, format_release_notes_for_dialog(remove_duplicate_release_heading(release.body, release.tag_name))])
    return "\n".join(lines).strip()


def format_release_notes_for_dialog(markdown: str, empty_text: str = "No release notes were provided for this update.") -> str:
    if not (markdown or "").strip():
        return empty_text
    formatted = []
    for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        text = line.rstrip()
        if text.startswith("#"):
            text = text.lstrip("#").strip()
        elif text.startswith("- ") or text.startswith("* "):
            text = "  " + text[2:]
        formatted.append(text)
    return "\n".join(formatted).strip() or empty_text


def remove_duplicate_release_heading(markdown: str, tag_name: str) -> str:
    if not markdown or not tag_name:
        return markdown
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    first = next((idx for idx, line in enumerate(lines) if line.strip()), -1)
    if first < 0:
        return markdown
    first_line = lines[first].strip()
    if not first_line.startswith("#"):
        return markdown
    heading = _normalize_release_heading(first_line.lstrip("#").strip())
    tag = _normalize_release_heading(tag_name)
    if heading and tag and (heading == tag or heading in tag or tag in heading):
        del lines[first]
        return "\n".join(lines).lstrip("\n")
    return markdown


def _normalize_release_heading(value: str) -> str:
    text = (value or "").strip().lower()
    for prefix in ("what's new in", "whats new in", "what is new in", "version"):
        text = text.replace(prefix, "")
    text = text.strip()
    return text[1:] if text.startswith("v") else text


def start_windows_update(asset_url: str, *, target_dir: str, executable_path: str, wait_pid: int | None = None) -> Path:
    if platform.system() != "Windows":
        raise RuntimeError("Automatic update installation is currently supported on Windows only.")
    updater_root = Path(tempfile.mkdtemp(prefix="ChronicleUpdater-"))
    script_path = updater_root / "Apply-ChronicleUpdate.ps1"
    script_path.write_text(
        build_windows_updater_script(
            asset_url=asset_url,
            target_dir=target_dir,
            executable_path=executable_path,
            wait_pid=wait_pid or os.getpid(),
        ),
        encoding="utf-8",
    )
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ],
        cwd=str(updater_root),
        close_fds=True,
    )
    return script_path


def start_mac_update(asset_url: str, *, app_bundle_path: str, wait_pid: int | None = None) -> Path:
    if platform.system() != "Darwin":
        raise RuntimeError("Mac update installation is available only on macOS.")
    updater_root = Path(tempfile.mkdtemp(prefix="ChronicleUpdater-"))
    script_path = updater_root / "apply_chronicle_update.sh"
    script_path.write_text(
        build_mac_updater_script(
            asset_url=asset_url,
            app_bundle_path=app_bundle_path,
            wait_pid=wait_pid or os.getpid(),
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o700)
    subprocess.Popen(
        ["/bin/bash", str(script_path)],
        cwd=str(updater_root),
        close_fds=True,
    )
    return script_path


def start_platform_update(asset_url: str, *, wait_pid: int | None = None) -> Path:
    system = platform.system()
    if system == "Windows":
        target_dir, executable_path = installed_app_target()
        return start_windows_update(
            asset_url,
            target_dir=target_dir,
            executable_path=executable_path,
            wait_pid=wait_pid,
        )
    if system == "Darwin":
        return start_mac_update(
            asset_url,
            app_bundle_path=resolve_mac_app_bundle(),
            wait_pid=wait_pid,
        )
    raise RuntimeError("Automatic update installation is currently supported on Windows and macOS only.")


def build_windows_updater_script(*, asset_url: str, target_dir: str, executable_path: str, wait_pid: int) -> str:
    payload = {
        "asset_url": asset_url,
        "target_dir": target_dir,
        "executable_path": executable_path,
        "wait_pid": int(wait_pid or 0),
    }
    return textwrap.dedent(
        f"""
        $ErrorActionPreference = "Stop"
        $Payload = ConvertFrom-Json @'
        {json.dumps(payload)}
        '@
        $LogDir = Join-Path $env:APPDATA "Chronicle\\logs"
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        $LogPath = Join-Path $LogDir "Updater.log"
        $WorkRoot = $null
        $CandidateDir = $null
        $BackupCreated = $false
        $ReplacementInstalled = $false
        $BackupPath = $Payload.target_dir + ".previous-update"
        function Write-ChronicleUpdateLog([string]$Message) {{
            Add-Content -Path $LogPath -Value ("{{0}} {{1}}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message) -Encoding UTF8
        }}
        function Assert-ChronicleStopped {{
            if ($Payload.wait_pid -gt 0 -and (Get-Process -Id $Payload.wait_pid -ErrorAction SilentlyContinue)) {{
                throw "Chronicle is still running. The installed app was not changed."
            }}
        }}
        try {{
            Write-ChronicleUpdateLog "Update command received."
            if (-not (Test-Path -LiteralPath $Payload.target_dir -PathType Container)) {{
                throw "The installed app folder is missing."
            }}
            if ((Get-Item -LiteralPath $Payload.target_dir).Attributes -band [IO.FileAttributes]::ReparsePoint) {{
                throw "The installed app folder must not be a link."
            }}
            if (Test-Path -LiteralPath $BackupPath) {{
                throw "A previous update backup already exists; resolve that recovery copy before updating."
            }}
            if ($Payload.wait_pid -gt 0) {{
                $Running = Get-Process -Id $Payload.wait_pid -ErrorAction SilentlyContinue
                if ($Running) {{
                    Write-ChronicleUpdateLog "Waiting for Chronicle to exit."
                    Wait-Process -Id $Payload.wait_pid -Timeout 45 -ErrorAction SilentlyContinue
                }}
            }}
            Assert-ChronicleStopped
            $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ChronicleUpdate_" + [guid]::NewGuid().ToString("N"))
            $ZipPath = Join-Path $WorkRoot "update.zip"
            $StageDir = Join-Path $WorkRoot "stage"
            New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
            Write-ChronicleUpdateLog "Downloading update ZIP."
            Invoke-WebRequest -Uri $Payload.asset_url -OutFile $ZipPath -Headers @{{"User-Agent" = "Chronicle updater"}} -UseBasicParsing -TimeoutSec 300
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $Archive = [IO.Compression.ZipFile]::OpenRead($ZipPath)
            try {{
                foreach ($Entry in $Archive.Entries) {{
                    if ($Entry.FullName -match '(^[/\\\\]|(^|[/\\\\])\\.\\.([/\\\\]|$)|:)') {{
                        throw "The update ZIP contains unsafe paths."
                    }}
                }}
            }} finally {{
                $Archive.Dispose()
            }}
            Write-ChronicleUpdateLog "Extracting update ZIP."
            Expand-Archive -LiteralPath $ZipPath -DestinationPath $StageDir -Force
            $SourceExes = @(Get-ChildItem -LiteralPath $StageDir -Filter "Chronicle.exe" -Recurse -File)
            if ($SourceExes.Count -ne 1 -or $SourceExes[0].Length -eq 0) {{
                throw "The update ZIP must contain exactly one non-empty Chronicle.exe."
            }}
            $SourceDir = $SourceExes[0].Directory.FullName
            if (-not (Test-Path -LiteralPath (Join-Path $SourceDir "_internal") -PathType Container)) {{
                throw "The update ZIP is missing Chronicle's runtime files."
            }}
            $CandidateDir = Join-Path (Split-Path -Parent $Payload.target_dir) (".ChronicleUpdate_" + [guid]::NewGuid().ToString("N"))
            New-Item -ItemType Directory -Path $CandidateDir | Out-Null
            Get-ChildItem -LiteralPath $SourceDir -Force | ForEach-Object {{
                Copy-Item -LiteralPath $_.FullName -Destination $CandidateDir -Recurse -Force
            }}
            foreach ($Name in @("Settings", "Logs", "Backups")) {{
                $SavedState = Join-Path $Payload.target_dir $Name
                $CandidateState = Join-Path $CandidateDir $Name
                if (Test-Path -LiteralPath $CandidateState) {{
                    Remove-Item -LiteralPath $CandidateState -Recurse -Force
                }}
                if (Test-Path -LiteralPath $SavedState) {{
                    Copy-Item -LiteralPath $SavedState -Destination $CandidateDir -Recurse -Force
                }}
            }}
            Assert-ChronicleStopped
            Write-ChronicleUpdateLog "Applying update files."
            Move-Item -LiteralPath $Payload.target_dir -Destination $BackupPath
            $BackupCreated = $true
            Move-Item -LiteralPath $CandidateDir -Destination $Payload.target_dir
            $ReplacementInstalled = $true
            Write-ChronicleUpdateLog "Update applied. Restarting Chronicle."
            Start-Process -FilePath $Payload.executable_path -WorkingDirectory $Payload.target_dir -ErrorAction Stop
            $BackupCreated = $false
            Remove-Item -LiteralPath $BackupPath -Recurse -Force -ErrorAction SilentlyContinue
            Write-ChronicleUpdateLog "Update completed."
        }} catch {{
            $Failure = $_.Exception.Message
            Write-ChronicleUpdateLog ("ERROR: " + $Failure)
            if ($BackupCreated) {{
                try {{
                    if ($ReplacementInstalled) {{
                        Remove-Item -LiteralPath $Payload.target_dir -Recurse -Force
                    }}
                    Move-Item -LiteralPath $BackupPath -Destination $Payload.target_dir
                    Write-ChronicleUpdateLog "Previous app restored."
                }} catch {{
                    Write-ChronicleUpdateLog "ERROR: automatic restoration failed; the previous app remains in the backup."
                }}
            }}
            Add-Type -AssemblyName PresentationFramework
            [System.Windows.MessageBox]::Show("Chronicle update failed.`n`n" + $Failure, "Chronicle Update") | Out-Null
            exit 1
        }} finally {{
            if ($WorkRoot) {{ Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue }}
            if ($CandidateDir) {{ Remove-Item -LiteralPath $CandidateDir -Recurse -Force -ErrorAction SilentlyContinue }}
        }}
        """
    ).strip() + "\n"


def build_mac_updater_script(
    *, asset_url: str, app_bundle_path: str, wait_pid: int,
    log_dir: str | None = None, wait_timeout_seconds: int = 45, show_alerts: bool = True,
) -> str:
    if not 1 <= int(wait_timeout_seconds) <= 3600:
        raise ValueError("The process wait timeout must be between 1 and 3600 seconds.")
    log_assignment = shlex.quote(str(log_dir)) if log_dir is not None else '"$HOME/Library/Application Support/Chronicle/logs"'
    return textwrap.dedent(
        f"""
        #!/bin/bash
        set -euo pipefail

        asset_url={shlex.quote(str(asset_url))}
        app_bundle_path={shlex.quote(str(app_bundle_path))}
        wait_pid={int(wait_pid or 0)}
        wait_timeout={int(wait_timeout_seconds)}
        log_dir={log_assignment}
        mkdir -p "$log_dir"
        log_path="$log_dir/Updater.log"
        work_root=""
        candidate_root=""
        backup_created=0
        replacement_installed=0
        parent_dir="$(dirname "$app_bundle_path")"
        backup_path="$parent_dir/Chronicle.app.previous-update"

        log() {{
          printf '%s %s\\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$log_path"
        }}

        fail() {{
          log "ERROR: $1"
          exit 1
        }}

        cleanup() {{
          result=$?
          trap - EXIT
          if [[ "$result" -ne 0 ]]; then
            if [[ "$backup_created" -eq 1 ]]; then
              log "Restoring the previous Chronicle app."
              if [[ "$replacement_installed" -eq 1 ]]; then
                rm -rf "$app_bundle_path"
              fi
              if mv "$backup_path" "$app_bundle_path"; then
                log "Previous app restored."
              else
                log "ERROR: automatic restoration failed; the previous app remains in the backup."
              fi
            fi
            log "ERROR: update did not complete."
            if [[ {1 if show_alerts else 0} -eq 1 ]]; then
              /usr/bin/osascript -e 'display alert "Chronicle update failed" message "Chronicle could not finish updating. See the updater log for recovery details." as critical' || true
            fi
          fi
          [[ -z "$work_root" ]] || rm -rf "$work_root"
          [[ -z "$candidate_root" ]] || rm -rf "$candidate_root"
          exit "$result"
        }}
        trap cleanup EXIT

        log "Update command received."
        [[ -d "$app_bundle_path" && ! -L "$app_bundle_path" ]] || fail "The installed app is missing or is a symbolic link."
        [[ ! -e "$backup_path" && ! -L "$backup_path" ]] || fail "A previous update backup already exists; resolve that recovery copy before updating."
        if [[ "$wait_pid" =~ ^[0-9]+$ ]] && [[ "$wait_pid" -gt 0 ]]; then
          log "Waiting for Chronicle to exit."
          for ((attempt=0; attempt<wait_timeout; attempt++)); do
            if ! kill -0 "$wait_pid" 2>/dev/null; then
              break
            fi
            sleep 1
          done
          if kill -0 "$wait_pid" 2>/dev/null; then
            fail "Chronicle is still running. The installed app was not changed."
          fi
        fi

        temp_parent="${{TMPDIR:-/tmp}}"
        work_root="$(mktemp -d "$temp_parent/ChronicleUpdate.XXXXXX")"
        zip_path="$work_root/update.zip"
        stage_dir="$work_root/stage"
        mkdir -p "$stage_dir"
        log "Downloading update ZIP."
        /usr/bin/curl -fsSL --retry 3 --connect-timeout 20 --max-time 300 -A "Chronicle updater" -o "$zip_path" "$asset_url" || fail "The update download failed."
        log "Extracting update ZIP."
        /usr/bin/zipinfo -1 "$zip_path" > "$work_root/entries.txt" || fail "The update ZIP is not readable."
        if /usr/bin/grep -Eq '(^/|(^|/)\\.\\.(/|$)|\\\\)' "$work_root/entries.txt"; then
          fail "The update ZIP contains unsafe paths."
        fi
        /usr/bin/ditto -x -k "$zip_path" "$stage_dir" || fail "The update ZIP could not be extracted."

        source_app="$(/usr/bin/find "$stage_dir" -name 'Chronicle.app' -type d -print -quit)"
        [[ -n "$source_app" ]] || fail "The update ZIP does not contain Chronicle.app."
        source_executable=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$source_app/Contents/Info.plist") || fail "The update app has no valid executable metadata."
        [[ "$source_executable" != */* && -n "$source_executable" ]] || fail "The update app executable name is invalid."
        [[ -x "$source_app/Contents/MacOS/$source_executable" ]] || fail "The update app executable is missing."

        log "Preparing the replacement app."
        candidate_root="$(mktemp -d "$parent_dir/.ChronicleUpdate.XXXXXX")" || fail "The app folder is not writable."
        candidate_app="$candidate_root/Chronicle.app"
        /usr/bin/ditto "$source_app" "$candidate_app" || fail "The replacement app could not be prepared."
        /usr/bin/xattr -rd com.apple.quarantine "$candidate_app" 2>/dev/null || true

        log "Applying update files."
        mv "$app_bundle_path" "$backup_path"
        backup_created=1
        mv "$candidate_app" "$app_bundle_path"
        replacement_installed=1
        log "Update applied. Restarting Chronicle."
        /usr/bin/open -g -n "$app_bundle_path" || fail "The updated app could not be launched."
        rm -rf "$backup_path"
        backup_created=0
        log "Update completed."
        """
    ).strip() + "\n"


def resolve_mac_app_bundle(executable_path: str | None = None) -> str:
    path = Path(executable_path or sys.executable).resolve()
    for candidate in [path, *path.parents]:
        if candidate.name.endswith(".app"):
            return str(candidate)
    raise RuntimeError("Could not locate Chronicle.app for the Mac updater.")


def installed_app_target() -> tuple[str, str]:
    executable_path = sys.executable
    if platform.system() == "Windows":
        return str(Path(executable_path).resolve().parent), executable_path
    return str(Path(executable_path).resolve().parent), executable_path


def extract_update_zip(zip_path: str, destination: str) -> str:
    stage = Path(destination)
    stage.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(stage)
    return str(stage)


def remove_update_temp(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)
