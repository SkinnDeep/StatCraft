"""Use installed system fonts for offscreen Windows acceptance, without bundling them."""
import os
from pathlib import Path


def load_verification_fonts(app):
    if app.platformName()!='offscreen' or os.name!='nt':return
    from PySide6.QtGui import QFontDatabase,QFont
    directory=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    if 'Segoe UI' not in QFontDatabase.families():
        for name in ('segoeui.ttf','segoeuib.ttf','segoeuii.ttf','segoeuiz.ttf'):
            if QFontDatabase.addApplicationFont(str(directory/name))<0:raise RuntimeError('Installed Segoe UI font unavailable for offscreen verification: '+name)
    app.setFont(QFont('Segoe UI',9))
    if 'Consolas' not in QFontDatabase.families():
        for name in ('consola.ttf','consolab.ttf'):
            if QFontDatabase.addApplicationFont(str(directory/name))<0:raise RuntimeError('Installed Consolas font unavailable for print verification: '+name)
