from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root/'launch_modern.py')], pathex=[str(root)],
    datas=[(str(root/'notices'),'notices'),(str(root/'StatCraft.ico'),'.'),(str(root/'statcraft/office-template.pptx'),'statcraft')],
    excludes=['tkinter','_tkinter','pandas','matplotlib','IPython','pytest'])
# Depend on Windows' own UCRT. The shared runtime search path contains an old
# imaging-tool UCRT which must never override the operating system runtime.
qt_dlls = {'qt6core.dll','qt6gui.dll','qt6widgets.dll','qt6network.dll','qt6printsupport.dll'}
plugins = {'qwindows.dll','qoffscreen.dll','qminimal.dll','qmodernwindowsstyle.dll',
           'qico.dll','qgif.dll','qjpeg.dll'}
def wanted(entry):
    dest, source, kind = entry
    name = Path(dest).name.lower()
    if name in {'ucrtbase.dll','icuuc.dll','icuin.dll','icu.dll'} or name.startswith(('api-ms-win-','ext-ms-win-','icudt')): return False
    if name.startswith('qt6') and name.endswith('.dll') and name not in qt_dlls: return False
    if 'plugins' in dest.replace('\\','/').lower() and name.endswith('.dll') and name not in plugins: return False
    return True
a.binaries = [entry for entry in a.binaries if wanted(entry)]
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,a.binaries,a.datas,[],name='StatCraft',console=False,
          icon=str(root/'StatCraft.ico'),upx=False)
