# Directory bundle: Qt stays extracted between launches. Charts use native Qt.
import os
bundle_name = os.environ.get('DECIPLINE_BUNDLE_NAME', 'Decipline')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/icon.ico', 'assets'), ('assets/alarm.wav', 'assets'), ('assets/ui', 'assets/ui')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
)
# Qt 6.11 uses the Windows ICU API. Unrelated SDKs on PATH can supply an
# incompatible icuuc.dll with version-suffixed exports; use the system DLL.
a.binaries = [entry for entry in a.binaries
              if os.path.basename(entry[0]).lower() != 'icuuc.dll']
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Decipline',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='assets/icon.ico',
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False,
    upx=False,
    name=bundle_name,
)
