from pathlib import Path
root = Path(SPECPATH)
a = Analysis(
    [str(root / 'installer_main.py')],
    pathex=[str(root)],
    datas=[
        (str(root / 'StatCraft.ico'), '.'),
        (str(root / 'notices'), 'notices')
    ],
    excludes=['tkinter', '_tkinter', 'pandas', 'matplotlib', 'IPython', 'pytest']
)

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
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='StatCraft-Setup',
    console=False,
    icon=str(root / 'StatCraft.ico'),
    upx=False
)
