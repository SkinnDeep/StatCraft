"""Retain application and library source, build inputs and copyright notices."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json, hashlib
root = Path(__file__).resolve().parent
out = root.parents[1]/'outputs'
notices = root/'notices'
for filename in ('QtBase-6.12.0-source.zip','PySide6-6.12.0-source.zip'):
    with ZipFile(out/filename) as archive:
        parts = []
        for name in archive.namelist():
            if '/LICENSES/' in name and not name.endswith('/'):
                data = archive.read(name)
                parts.append(name+'\n\n'+data.decode('utf-8', errors='replace'))
        (notices/(filename.replace('-source.zip','-licenses.txt'))).write_text('\n\n'.join(parts),encoding='utf-8')
instructions = '''StatCraft modern preview — source and rebuild instructions

This archive contains original StatCraft application source and build inputs.
No StatCraft executable, library, asset or downloaded project is distributed.
You may modify and recombine this application with modified Qt/PySide libraries,
and reverse engineer this combined work to debug those modifications.

Use Windows x64 and Python 3.12. Create a virtual environment, then install:
  python -m pip install PySide6==6.12.0 numpy==2.5.4 scipy==1.18.1 pyinstaller==6.22.3
For source verification only (not needed by the packaged application):
  python -m pip install pypdf==6.10.0 python-docx==1.2.0 python-pptx==1.0.2 openpyxl==3.1.5
From the extracted source folder:
  python verify_tests.py
  python launch_modern.py --self-test qt-smoke.json
  python -m PyInstaller --noconfirm modern.spec
The rebuilt EXE is dist/StatCraft.exe. To substitute a compatible modified Qt
runtime, replace the installed PySide6 package/libraries before rebuilding.
No signing, authentication or license check prevents this recombination.
The one-file EXE extracts libraries at launch; rebuilding is the supported
permanent library replacement route. Source use and rebuilding do not require
a StatCraft installation, account or activation.

Bundled Qt/PySide6/Shiboken6 6.12.0 is used under LGPLv3. Full LGPL/GPL and
third-party notices are in notices/. Unmodified corresponding library source
archives accompany this delivery as QtBase-6.12.0-source.zip and
PySide6-6.12.0-source.zip; keep them with this source archive when redistributing.
Qt upstream source origins:
https://github.com/qt/qtbase/tree/v6.12.0
https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/
Qt source archives include their own build instructions and dependency details.
Only Qt Core/Gui/Widgets/Network/PrintSupport and basic Windows/image plugins are packaged.
Qt Charts, WebEngine, the Qt PDF module and VirtualKeyboard are not packaged.
PDF export is provided by Qt PrintSupport.

Office export uses original Python OOXML writers and an original blank
presentation template generated with the bundled Artifact Tool. Office and the
verification-only document libraries are not required by the packaged app.

Complete StatCraft feature parity is not achieved. MPX editing is conservative
save-copy support for the observed schema, with StatCraft reports in a separate
namespace. Supported native reports and saved graph geometry are displayed as snapshots; native model recalculation remains unsupported.
'''
(root/'REBUILD.txt').write_text(instructions,encoding='utf-8')
(out/'StatCraft-source-and-licenses.txt').write_text(instructions,encoding='utf-8')
with ZipFile(out/'StatCraft-source.zip','w',ZIP_DEFLATED) as archive:
    for directory in ('statcraft','notices','tests'):
        for path in (root/directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                archive.write(path,path.relative_to(root).as_posix())
    for filename in ('launch_modern.py','modern.spec','verify_tests.py','StatCraft.ico','REBUILD.txt'):
        archive.write(root/filename,filename)
print('Application source, rebuild inputs and library licenses retained.')
