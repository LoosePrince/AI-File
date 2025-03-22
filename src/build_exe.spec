# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 获取所有需要打包的数据文件
datas = [
    ('config.ini', '.'),
    ('config.py', '.'),
    ('file_organizer.py', '.'),
    ('gui_qt.py', '.'),
    ('pages.py', '.')
]

a = Analysis(
    ['main.pyw'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'PyQt5',
        'configparser',
        'PIL',
        'PIL._imaging',
        'PIL.Image',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'pandas', 'scipy',  # 排除不需要的大型库
        'tkinter', 'PyQt5.QtWebEngine', 'PyQt5.QtMultimedia',  # 排除不需要的Qt模块
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='文脉通',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 设置为False以隐藏控制台窗口
    icon='img/app.ico' if os.path.exists('img/app.ico') else None,  # 如果有图标文件的话
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
) 