"""Palette and 3D camera controls for imported saved graph appearance."""
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QDoubleSpinBox,QLabel,QDialogButtonBox,QGroupBox
from .native_graph_view import validate_view

PALETTES={
 'Original saved colors':None,
 'Blue–green':['#d4e7ef','#acd5df','#7cbac4','#4aa1a3','#36937d','#69aa63','#a1c450','#d4d94a','#e8be43'],
 'Blue':['#edf4fc','#c6dbef','#9ecae1','#6baed6','#4292c6','#2171b5','#084594'],
 'Heat':['#ffffcc','#ffeda0','#fed976','#feb24c','#fd8d3c','#fc4e2a','#e31a1c','#b10026'],
 'Grayscale':['#f7f7f7','#dedede','#bdbdbd','#969696','#737373','#525252','#252525'],
}

class NativeGraphAppearanceDialog(QDialog):
    def __init__(self,view,has_surface=False,parent=None):
        super().__init__(parent);self.setWindowTitle('Graph Appearance');self.setMinimumWidth(420)
        self.view=validate_view(view);self.settings=None;layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.palette=QComboBox();self.palette.addItems(list(PALETTES)+['Custom']);self.colors=QLineEdit()
        form.addRow('Color palette:',self.palette);form.addRow('Palette colors:',self.colors)
        self.colors.setToolTip('Comma-separated #RRGGBB colors. Leave blank to retain saved native colors.')
        current=self.view.get('palette');match=next((k for k,v in PALETTES.items() if v==current),'Custom')
        self.palette.setCurrentText(match);self.colors.setText(', '.join(current or []));self.palette.currentTextChanged.connect(self._palette)
        camera=QGroupBox('3D View');camera.setEnabled(has_surface);camera_form=QFormLayout(camera);self.camera={}
        defaults=self.view.get('camera',{'azimuth':-35.,'elevation':25.,'zoom':1.})
        for key,label,low,high,step in [('azimuth','Rotation:',-180,180,5),('elevation','Elevation:',-89,89,5),('zoom','Zoom:',.4,2.5,.1)]:
            control=QDoubleSpinBox();control.setRange(low,high);control.setDecimals(2);control.setSingleStep(step);control.setValue(defaults[key]);self.camera[key]=control;camera_form.addRow(label,control)
        layout.addWidget(camera);self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color:#a02020');layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def _palette(self,name):
        if name in PALETTES:self.colors.setText(', '.join(PALETTES[name] or []))
    def validate(self):
        try:
            colors=[c.strip() for c in self.colors.text().split(',') if c.strip()]
            self.settings=validate_view({'palette':colors or None,'camera':{k:v.value() for k,v in self.camera.items()}})
        except ValueError as exc:self.error.setText(str(exc));return
        self.accept()
