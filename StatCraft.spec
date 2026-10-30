import sys
from pathlib import Path

root = Path(SPECPATH)

datas = [
    (str(root / 'notices'), 'notices'),
    (str(root / 'StatCraft.ico'), '.'),
    (str(root / 'StatCraft.png'), '.'),
    (str(root / 'statcraft' / 'office-template.pptx'), 'statcraft'),
]

a = Analysis(
    [str(root / 'launch_modern.py')],
    pathex=[str(root)],
    datas=datas,
    excludes=['tkinter', '_tkinter', 'pandas', 'matplotlib', 'IPython', 'pytest']
)

# On Windows, optimize Qt runtime DLLs
if sys.platform == 'win32':
    qt_dlls = {'qt6core.dll', 'qt6gui.dll', 'qt6widgets.dll', 'qt6network.dll', 'qt6printsupport.dll'}
    plugins = {
        'qwindows.dll', 'qoffscreen.dll', 'qminimal.dll', 'qmodernwindowsstyle.dll',
        'qico.dll', 'qgif.dll', 'qjpeg.dll'
    }

    def wanted(entry):
        dest, source, kind = entry
        name = Path(dest).name.lower()
        if name in {'ucrtbase.dll', 'icuuc.dll', 'icuin.dll', 'icu.dll'} or name.startswith(('api-ms-win-', 'ext-ms-win-', 'icudt')):
            return False
        if name.startswith('qt6') and name.endswith('.dll') and name not in qt_dlls:
            return False
        if 'plugins' in dest.replace('\\', '/').lower() and name.endswith('.dll') and name not in plugins:
            return False
        return True

    a.binaries = [entry for entry in a.binaries if wanted(entry)]

pyz = PYZ(a.pure)

icon_file = None
if sys.platform == 'win32' and (root / 'StatCraft.ico').exists():
    icon_file = str(root / 'StatCraft.ico')
elif sys.platform == 'darwin' and (root / 'StatCraft.icns').exists():
    icon_file = str(root / 'StatCraft.icns')

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StatCraft',
    console=False,
    icon=icon_file,
    upx=False
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='StatCraft.app',
        icon=icon_file,
        bundle_identifier='com.statcraft.desktop',
        info_plist={
            'CFBundleName': 'StatCraft',
            'CFBundleDisplayName': 'StatCraft',
            'CFBundleIdentifier': 'com.statcraft.desktop',
            'CFBundleVersion': '104.0.0',
            'CFBundleShortVersionString': '104.0.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        }
    )
