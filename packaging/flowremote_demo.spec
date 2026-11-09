from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "src" / "flowremote" / "ui"), "flowremote/ui"),
    (
        str(ROOT / "src" / "flowremote" / "control_plane" / "migrations"),
        "flowremote/control_plane/migrations",
    ),
]

hiddenimports = []
for package in (
    "flowremote",
    "uvicorn",
    "openai",
    "psycopg",
    "cryptography",
    "openpyxl",
    "python_multipart",
):
    hiddenimports += collect_submodules(package)

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FlowRemoteDemo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
