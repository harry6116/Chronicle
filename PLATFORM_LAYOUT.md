# Platform Layout

Chronicle preserves simple root entrypoints while keeping platform-specific helper scripts organized where practical.

## Current Layout

### Root entrypoints

These are the commands most users and testers should continue to use from the repo root:

- `build.command`
- `build_windows.bat`
- `build_windows.ps1`
- `run_a11y_harness.command`
- `run_a11y_harness.bat`
- `run_native_queue_harness.command`
- `stage_windows_bundle.command`
- `chronicle_gui.py`

### macOS helper folder

macOS-specific helper scripts live under:

- `<repo-root>/Mac/`

### Shared runtime and app code

Shared cross-platform code lives at the repo root and under `chronicle_app/`.

Important paths:

- `chronicle.py`
- `chronicle_core.py`
- `chronicle_gui.py`
- `chronicle_app/config.py`
- `chronicle_app/services/`
- `chronicle_app/ui/`

## Modularized GUI Structure

The GUI has been modularized while preserving the main `chronicle_gui.py` entrypoint.

Current extracted UI modules include:

- `chronicle_app/ui/dialogs.py`
- `chronicle_app/ui/menus.py`
- `chronicle_app/ui/queue_panel.py`
- `chronicle_app/ui/queue_support.py`

## Windows Packaging Notes

Windows build and staging flows now expect the following to exist together:

- `build_windows.bat`
- `build_windows.ps1`
- `chronicle_gui.py`
- `chronicle.py`
- `chronicle_core.py`
- `chronicle_app/`
- `assets/`
- `docs/`
- `requirements.txt`

## Validation

Run:

```bash
./tools/check_platform_layout.sh
```

This checks:

- expected wrapper/helper presence
- macOS helper preflight prerequisites
- Windows bundle helper presence
- current repo layout assumptions used by local tooling
