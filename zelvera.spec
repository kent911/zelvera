# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для Zelvera.

Переносится между платформами: на Windows собирает оконное приложение
(console=False), на Linux/macOS — консольный запуск для отладки.

Сборка:
    pyinstaller --clean --noconfirm zelvera.spec
Результат: dist/Zelvera/
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH)

chroma_sub = [m for m in collect_submodules("chromadb") if not m.startswith("chromadb.test")]
app_sub = collect_submodules("app")
hiddenimports = sorted(
    set(
        chroma_sub
        + app_sub
        + collect_submodules("uvicorn")
        + [
            "fitz",
            "multipart",
        ]
    )
)

datas = collect_data_files("chromadb", excludes=["**/test/**", "**/*.md"])
datas += copy_metadata("chromadb")
datas += [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "backend" / "fonts"), "fonts"),
]

is_windows = sys.platform == "win32"

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT), str(ROOT / "backend")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "tkinter",
        "torch",
        "sentence_transformers",
        "onnxruntime.transformers",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Zelvera",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=not is_windows,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Zelvera",
)
