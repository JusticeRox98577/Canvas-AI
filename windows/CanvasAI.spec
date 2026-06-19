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
# Bake built-in defaults into the exe (the Settings menu overrides them).
# Prefer .env.dist (clean distribution defaults with NO personal info); fall back
# to your personal .env. Either way, sanitize out secrets/personal fields so a
# published exe never ships tokens, keys, Canvas URL leakage, or your voice.
_DENY = ("TOKEN", "KEY", "SECRET", "PASSWORD", "WRITING_SAMPLE", "CANVAS_BASE_URL")
_envsrc = R(".env.dist") if os.path.isfile(R(".env.dist")) else R(".env")
if os.path.isfile(_envsrc):
    safe_lines = []
    with open(_envsrc, encoding="utf-8") as _fh:
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
# Prefer the clean folder build.ps1 installs into (PLAYWRIGHT_BROWSERS_PATH);
# else the global %LOCALAPPDATA%\ms-playwright cache. Only bundle Chromium dirs
# (skip Firefox/WebKit/old revisions) so the exe stays lean. At runtime
# desktop.py points PLAYWRIGHT_BROWSERS_PATH at the bundled ms-playwright.
_local = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
_ms = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or os.path.join(_local, "ms-playwright")
if os.path.isdir(_ms):
    for entry in os.listdir(_ms):
        full_entry = os.path.join(_ms, entry)
        if not os.path.isdir(full_entry):
            continue
        if not entry.lower().startswith("chromium"):
            continue  # skip firefox/webkit/ffmpeg to keep the exe small
        for root, _dirs, files in os.walk(full_entry):
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
