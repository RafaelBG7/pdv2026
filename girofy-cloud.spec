# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_cloud_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('desktop_cloud/resources', 'desktop_cloud/resources'),
        ('app/static/favicon-v2.png', 'desktop_cloud/resources/logo.png'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'flask',
        'sqlalchemy',
        'pymysql',
        'werkzeug',
        'jinja2',
        'app',
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
    name='Girofy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='desktop_cloud/resources/girofy.ico',
    version='desktop_cloud/resources/version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Girofy',
)
