import sys
from pathlib import Path
root = Path(SPECPATH)

datas = [
    (str(root / 'StatCraft.ico'), '.'),
    (str(root / 'StatCraft.png'), '.'),
    (str(root / 'notices'), 'notices')
]

a = Analysis(
    [str(root / 'installer_main.py')],
    pathex=[str(root)],
    datas=datas,
    excludes=['tkinter', '_tkinter', 'pandas', 'matplotlib', 'IPython', 'pytest']
)

if sys.platform == 'win32':
    qt_dlls = {'qt6core.dll', 'qt6gui.dll', 'qt6widgets.dll', 'qt6network.dll'}
    plugins = {'qwindows.dll', 'qoffscreen.dll', 'qminimal.dll', 'qmodernwindowsstyle.dll', 'qico.dll'}

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

icon_file = str(root / 'StatCraft.ico') if (sys.platform == 'win32' and (root / 'StatCraft.ico').exists()) else None
version_file = str(root / 'installer_version.txt') if (root / 'installer_version.txt').exists() else None
manifest_file = str(root / 'installer_manifest.xml') if (root / 'installer_manifest.xml').exists() else None

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StatCraft-Setup',
    console=False,
    icon=icon_file,
    version=version_file,
    manifest=manifest_file,
    upx=False
)
