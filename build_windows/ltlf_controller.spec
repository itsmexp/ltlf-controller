# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

custom_datas = [
    ('../parser/almanac/almanac_grammar.lark', 'parser/almanac'),
    ('../parser/config/config_grammar.lark', 'parser/config')
]
custom_datas += collect_data_files('ltlf2dfa')

a = Analysis(
    ['entry_point.py'],
    pathex=['..'],
    binaries=[('mona.exe', '.'), ('cygwin1.dll', '.')],
    datas=custom_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ltlf_controller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
