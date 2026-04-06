import os
import sys
import shutil
import subprocess
import setuptools
import time

def safe_rmtree(path, retries=5, delay=0.25):
    last_err = None
    for attempt in range(retries):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                raise last_err

def run_build():
    print("--- Chronicle Sledgehammer Build: Mac ---")
    build_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    build_stamp_file = os.path.abspath("build_stamp.txt")
    with open(build_stamp_file, "w", encoding="utf-8") as fh:
        fh.write(build_stamp + "\n")
    print(f"Build stamp: {build_stamp}")

    # 1. Clean previous build artifacts
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            safe_rmtree(folder)
    if os.path.exists('Chronicle.spec'):
        os.remove('Chronicle.spec')

    for required in ("chronicle_gui.py", "chronicle_core.py", "chronicle_app", os.path.join("chronicle_app", "services"), os.path.join("chronicle_app", "ui"), os.path.join("assets", "icons", "chronicle_option3.icns"), "assets", "docs", "build_stamp.txt"):
        if not os.path.exists(required):
            raise FileNotFoundError(f"{required} not found in current directory.")

    # 2. Locate jaraco/setuptools dependencies automatically
    setuptools_path = os.path.dirname(setuptools.__file__)
    jaraco_path = os.path.join(setuptools_path, '_vendor', 'jaraco')

    # 3. Master PyInstaller command with aggressive dependencies
    icon_path = os.path.abspath(os.path.join("assets", "icons", "chronicle_option3.icns"))
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--disable-windowed-traceback",
        "--name", "Chronicle",
        "--additional-hooks-dir", os.path.abspath("hooks"),

        # WX GUI hidden imports
        "--hidden-import", "wx",
        "--hidden-import", "wx.adv",
        "--hidden-import", "wx.dataview",
        "--hidden-import", "wx._adv",
        "--hidden-import", "wx.html",
        "--hidden-import", "wx.xml",

        # Critical AI SDK hidden imports (Pydantic / HTTPX)
        "--hidden-import", "httpx",
        "--hidden-import", "anyio",
        "--hidden-import", "certifi",

        # Vendor / Text processing hidden imports
        "--hidden-import", "setuptools._vendor.jaraco.text",

        # Google GenAI specifics
        "--hidden-import", "google.genai",
        "--hidden-import", "google.genai.types",
        "--hidden-import", "google.genai.errors",
        "--collect-submodules", "chronicle_app",

        # Aggressive collection of complete libraries
        "--collect-submodules", "google.auth",
        "--collect-submodules", "google.oauth2",
        "--collect-all", "anthropic",
        "--collect-all", "openai",
        "--hidden-import", "fitz",
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
        "--collect-all", "httpx",

        # Exclude non-runtime test/deprecated internals that trigger noisy missing-module warnings.
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

        "chronicle_gui.py"
    ]

    # Always bundle the latest local assets/docs from the current workspace.
    for src, dest in (("assets", "assets"), ("docs", "docs"), ("build_stamp.txt", ".")):
        abs_src = os.path.abspath(src)
        cmd[-1:-1] = ["--add-data", f"{abs_src}{os.pathsep}{dest}"]

    if os.path.exists(icon_path):
        # Keep branding centralized in assets/icons.
        cmd[-1:-1] = ["--icon", icon_path]
    else:
        print(f"Warning: icon not found at {icon_path}. Building without a custom icon.")

    if os.path.exists(jaraco_path):
        # Insert before the final script argument to avoid breaking option/value pairs.
        cmd[-1:-1] = ["--add-data", f"{jaraco_path}:setuptools/_vendor/jaraco"]
    else:
        print(f"Warning: setuptools jaraco vendor path not found at {jaraco_path}. Continuing without explicit --add-data.")

    pyinstaller_cache = os.path.abspath(".pyinstaller-cache")
    os.makedirs(pyinstaller_cache, exist_ok=True)
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = pyinstaller_cache
    # PyInstaller probes Pydantic's optional v1 compatibility shim on Python 3.14;
    # Chronicle does not use that shim, so suppress only that known build-time noise.
    env["PYTHONWARNINGS"] = env.get("PYTHONWARNINGS", "") + ("," if env.get("PYTHONWARNINGS") else "") + "ignore:Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater."

    print("Bundling AI frameworks and UI libraries. This will take a few minutes...")
    os.makedirs(os.path.join("dist", "Chronicle", "_internal", "wx"), exist_ok=True)
    first = subprocess.run(cmd, check=False, env=env)
    if first.returncode != 0:
        print(f"\nFirst PyInstaller pass failed (exit {first.returncode}). Retrying once...")
        os.makedirs(os.path.join("dist", "Chronicle", "_internal", "wx"), exist_ok=True)
        second = subprocess.run(cmd, check=False, env=env)
        if second.returncode != 0:
            print(f"\nBUILD FAILED with exit code {second.returncode}.")
            raise SystemExit(second.returncode)
    embedded_stamp = os.path.join("dist", "Chronicle.app", "Contents", "Resources", "build_stamp.txt")
    if os.path.exists(embedded_stamp):
        try:
            with open(embedded_stamp, "r", encoding="utf-8") as fh:
                print(f"Embedded app build stamp: {fh.read().strip()}")
        except Exception:
            print("Warning: failed reading embedded app build stamp.")
    else:
        print(f"Warning: embedded app build stamp not found at {embedded_stamp}")
    print("\nBUILD COMPLETE! Your Mac application is in the 'dist' folder.")

if __name__ == "__main__":
    run_build()
