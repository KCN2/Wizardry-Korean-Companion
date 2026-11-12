# -*- mode: python ; coding: utf-8 -*-
import os


a = Analysis(
    ['wiz_overlay.py'],
    pathex=[],
    binaries=[],
    datas=[('wiz1_ko_data.json', '.'), ('wiz1_hashed.json', '.'), ('wiz2_monsters.json', '.'), ('wiz2_items.json', '.'), ('wiz2_sentences.json', '.'),
           ('wiz3_monsters.json', '.'), ('wiz3_items.json', '.'), ('wiz3_sentences.json', '.'),
           ('wiz4_monsters.json', '.'), ('wiz4_items.json', '.'), ('wiz4_sentences.json', '.'),
           ('wiz5_monsters.json', '.'), ('wiz5_items.json', '.'), ('wiz5_sentences.json', '.'),
           ('wiz5_glyphs.json', '.'),
           ('neodgm.ttf', '.'), ('wiz_icon.ico', '.')],
    hiddenimports=['cga_text_extractor', 'wiz_screen', 'wiz1_state', 'wiz_hook', 'wiz_build_flags', 'tools.wiz_krn_decode'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy'],   # nothing uses it; PIL pulled it in (larger exe, slower unpack)
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
    name='Wiz1_Korean_Overlay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
    icon=os.path.join(SPECPATH, 'wiz_icon.ico'),
)
