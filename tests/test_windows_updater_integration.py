import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from chronicle_app.services.update_service import build_windows_updater_script


POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(POWERSHELL, "PowerShell is unavailable")
class WindowsUpdaterIntegrationTest(unittest.TestCase):
    """Exercise real PowerShell file operations with isolated download/launch adapters."""

    def run_update(self, fault="", members=None, running=False):
        with tempfile.TemporaryDirectory(prefix="ChronicleUpdaterTest-") as directory:
            root = Path(directory)
            installed = root / "installed app"
            installed.mkdir()
            (installed / "Chronicle.exe").write_text("old executable")
            (installed / "old-only.txt").write_text("old file")
            (installed / "Settings").mkdir()
            (installed / "Settings/preferences.json").write_text('{"sample": true}')
            archive = root / "fixture.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                for name, text in (members if members is not None else {
                    "Chronicle/Chronicle.exe": "new executable",
                    "Chronicle/_internal/runtime.txt": "sample runtime",
                    "Chronicle/Settings/preferences.json": "untrusted packaged settings",
                }).items():
                    zf.writestr(name, text)
            if fault == "backup":
                backup = root / "installed app.previous-update"
                backup.mkdir()
                (backup / "retained.txt").write_text("keep this backup")
            script = build_windows_updater_script(
                asset_url="https://downloads.example/fixture.zip",
                target_dir=str(installed), executable_path=str(installed / "Chronicle.exe"),
                wait_pid=os.getpid() if running else 0,
            )
            # Suppress only the platform alert and shorten the wait in this fixture.
            script = script.replace("-Timeout 45", "-Timeout 1")
            script = script.replace("Add-Type -AssemblyName PresentationFramework", "")
            script = script.replace(
                '[System.Windows.MessageBox]::Show("Chronicle update failed.`n`n" + $Failure, "Chronicle Update") | Out-Null',
                'Write-Output "Fixture update failed."',
            )
            adapters = f"""
$env:APPDATA = {ps_quote(root / 'app data')}
$env:TEMP = {ps_quote(root)}
$FixtureZip = {ps_quote(archive)}
$FixtureFault = {ps_quote(fault)}
function Invoke-WebRequest {{
    param($Uri, $OutFile, $Headers, [switch]$UseBasicParsing, $TimeoutSec)
    if ($FixtureFault -eq 'download') {{ throw 'fixture download failure' }}
    Microsoft.PowerShell.Management\\Copy-Item -LiteralPath $FixtureZip -Destination $OutFile
}}
function Start-Process {{
    param($FilePath, $WorkingDirectory, $ErrorAction)
    if ($FixtureFault -eq 'launch') {{ throw 'fixture launch failure' }}
    Set-Content -LiteralPath {ps_quote(root / 'launched.txt')} -Value 'launched'
}}
$script:MoveCount = 0
function Move-Item {{
    param($LiteralPath, $Destination)
    $script:MoveCount++
    if ($FixtureFault -eq 'swap' -and $script:MoveCount -eq 2) {{ throw 'fixture swap failure' }}
    Microsoft.PowerShell.Management\\Move-Item -LiteralPath $LiteralPath -Destination $Destination
}}
function Copy-Item {{
    param($LiteralPath, $Destination, [switch]$Recurse, [switch]$Force)
    if ($FixtureFault -eq 'copy') {{ throw 'fixture copy failure' }}
    Microsoft.PowerShell.Management\\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Recurse:$Recurse -Force:$Force
}}
"""
            script_path = root / "apply.ps1"
            script_path.write_text(adapters + script, encoding="utf-8")
            result = subprocess.run(
                [POWERSHELL, "-NoProfile", "-NonInteractive", "-File", str(script_path)],
                capture_output=True, text=True, timeout=30,
            )
            log_path = root / "app data/Chronicle/logs/Updater.log"
            log = log_path.read_text(encoding="utf-8-sig") if log_path.exists() else ""
            successful = not fault and members is None and not running
            self.assertEqual(result.returncode, 0 if successful else 1, result.stdout + result.stderr + log)
            self.assertTrue(installed.is_dir(), log)
            self.assertEqual((installed / "Chronicle.exe").read_text(), "new executable" if successful else "old executable", log)
            self.assertEqual((installed / "Settings/preferences.json").read_text(), '{"sample": true}', log)
            self.assertEqual((root / "launched.txt").exists(), successful, log)
            self.assertEqual((installed / "old-only.txt").exists(), not successful, log)
            if fault == "backup":
                self.assertEqual((root / "installed app.previous-update/retained.txt").read_text(), "keep this backup")
            else:
                self.assertFalse((root / "installed app.previous-update").exists(), log)
            self.assertEqual(list(root.glob(".ChronicleUpdate_*")), [], log)
            if fault in {"swap", "launch"}:
                self.assertIn("Previous app restored", log)
            if running:
                self.assertIn("Chronicle is still running", log)

    def test_success_preserves_settings_and_removes_stale_files(self):
        self.run_update()

    def test_download_failure_preserves_installation(self):
        self.run_update(fault="download")

    def test_copy_failure_preserves_installation(self):
        self.run_update(fault="copy")

    def test_swap_failure_restores_installation(self):
        self.run_update(fault="swap")

    def test_launch_failure_restores_installation(self):
        self.run_update(fault="launch")

    def test_existing_backup_is_preserved(self):
        self.run_update(fault="backup")

    def test_running_app_blocks_update(self):
        self.run_update(running=True)

    def test_missing_runtime_is_rejected(self):
        self.run_update(members={"Chronicle/Chronicle.exe": "sample executable"})

    def test_unsafe_archive_path_is_rejected(self):
        self.run_update(members={"../escape.txt": "sample text"})


if __name__ == "__main__":
    unittest.main()
