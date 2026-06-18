# PyInstaller spec for Canvas-AI on Windows.
# Build from the repo root:  pyinstaller windows/CanvasAI.spec
#
# Produces a single-file dist/CanvasAI.exe that launches the local backend and
# opens a native window. Login (browser/Playwright) is done once beforehand with
# `canvas-ai login`; the exe reuses the saved .canvas_profile session.

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("webview")
    + ["canvas_ai.web.app"]
)

datas = [
    ("canvas_ai/web/static", "canvas_ai/web/static"),
    ("windows/CanvasAI.ico", "."),  # so the window icon loads when frozen
]
datas += collect_data_files("webview")

a = Analysis(
    ["windows/launch.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # Playwright/Chromium is huge and only needed for one-time login, which is
    # done from the venv. Keep it out of the exe.
    excludes=["playwright"],
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
    icon="windows/CanvasAI.ico",
)
