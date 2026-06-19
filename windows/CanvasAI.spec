# PyInstaller spec for Canvas-AI on Windows.
# Build from the repo root:  pyinstaller windows/CanvasAI.spec
#
# Produces a single self-contained dist/CanvasAI.exe that launches the local
# backend, opens a native window, and can sign you in on its own (Playwright +
# Chromium are bundled). No Python install needed to run the result.

import os
import tempfile
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

block_cipher = None

# Paths are resolved relative to this spec's folder (windows/), so build them
# from the repo root explicitly. SPECPATH is the directory containing this spec.
ROOT = os.path.dirname(os.path.abspath(SPECPATH))


def R(*parts):
    return os.path.join(ROOT, *parts)

# --- core app ---
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("webview")
    + ["canvas_ai.web.app"]
)

datas = [
    (R("canvas_ai", "web", "static"), "canvas_ai/web/static"),
    (R("windows", "CanvasAI.ico"), "."),  # window/taskbar icon when frozen
]
# Bake the current .env in as built-in defaults (settings menu overrides it),
# but SANITIZE it first so a published exe never ships secrets or personal data.
_DENY = ("TOKEN", "KEY", "SECRET", "PASSWORD", "WRITING_SAMPLE")
if os.path.isfile(R(".env")):
    safe_lines = []
    with open(R(".env"), encoding="utf-8") as _fh:
        for line in _fh:
            name = line.split("=", 1)[0].strip()
            if name and not name.startswith("#") and any(d in name.upper() for d in _DENY):
                continue  # drop secret / personal keys
            safe_lines.append(line)
    _safe_dir = tempfile.mkdtemp(prefix="canvasai_env_")
    _safe_env = os.path.join(_safe_dir, ".env")  # keep the .env basename
    with open(_safe_env, "w", encoding="utf-8") as _out:
        _out.writelines(safe_lines)
    datas.append((_safe_env, "."))  # -> _MEIPASS/.env
datas += collect_data_files("webview")
binaries = []

# --- Playwright (for the browser login) ---
pw_datas, pw_binaries, pw_hidden = collect_all("playwright")
datas += pw_datas
binaries += pw_binaries
hiddenimports += pw_hidden

# --- the Chromium browser Playwright downloaded ---
# `playwright install chromium` puts browsers in %LOCALAPPDATA%\ms-playwright.
# Bundle that folder; at runtime desktop.py points PLAYWRIGHT_BROWSERS_PATH at it.
_local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
_ms = os.path.join(_local, "ms-playwright")
if os.path.isdir(_ms):
    for root, _dirs, files in os.walk(_ms):
        for f in files:
            full = os.path.join(root, f)
            dest = os.path.join("ms-playwright", os.path.relpath(os.path.dirname(full), _ms))
            datas.append((full, dest))

a = Analysis(
    [R("windows", "launch.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CanvasAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,  # no console window; it's a GUI app
    icon=R("windows", "CanvasAI.ico"),
)
