"""Seven resource-guided dotplot choices with original widgets and thumbnails."""
from copy import deepcopy
from PySide6.QtCore import Qt,QSize,QPointF
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap,QIcon
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QGroupBox,QToolButton,QButtonGroup,
    QDialogButtonBox,QCheckBox,QComboBox,QPushButton,QLabel,QFormLayout,QSpinBox,QLineEdit)
from .histogram_dialogs import HistogramDialog
from .boxplot_dialogs import BoxplotDialog
from .dotplot_graphs import validate_parameters,build_dotplots,VARIANTS
from .variable_dialogs import resolve_variables,format_variable_reference

TITLES={'one':'Simple','one_groups':'With Groups','one_stack_groups':'Stack Groups','multiple':'Simple','multiple_stack':'Stack Y’s','multiple_groups':'With Groups','multiple_stack_groups':'Stack Groups'}


def dot_icon(mode):
    pix=QPixmap(240,160);pix.setDevicePixelRatio(2);pix.fill(QColor('white'));p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#64717c'),1));p.drawLine(10,70,113,70)
    stacked='_stack' in mode;count=1 if mode=='one' else 2
    for s in range(count):
        color=QColor('#3e739b' if s==0 else '#b46e39');p.setPen(QPen(color,1));p.setBrush(color)
        for column,height in enumerate((1,2,4,5,3,2,1)):
            for level in range(height):
                p.drawEllipse(QPointF(23+column*12+(s*2 if not stacked else 0),63-level*6-(s*32 if not stacked else s*height*6)),2.1,2.1)
    p.end();return QIcon(pix)


class DotplotTypeDialog(QDialog):
    def __init__(self,parent=None):
        self.setSizeGripEnabled(True)
        super().__init__(parent);self.setWindowTitle('Dotplots');self.mode='one';self.mode_buttons={};self.buttons=QButtonGroup(self);outer=QVBoxLayout(self)
        for title,keys in (('One Y',VARIANTS[:3]),('Multiple Y’s',VARIANTS[3:])):
            group=QGroupBox(title);row=QHBoxLayout(group)
            for key in keys:
                button=QToolButton();button.setText(TITLES[key]);button.setIcon(dot_icon(key));button.setIconSize(QSize(120,80));button.setMinimumSize(145,125)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon);button.setCheckable(True);button.setChecked(key=='one')
                button.setStyleSheet('QToolButton{border:1px solid #bfc5cb;padding:8px;background:white;}QToolButton:checked{border:2px solid #205b92;background:#eaf1f8;}')
                button.clicked.connect(lambda checked=False,key=key:setattr(self,'mode',key));self.buttons.addButton(button);self.mode_buttons[key]=button;row.addWidget(button)
            if title=='One Y':row.addStretch()
            outer.addWidget(group)
        self.actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.actions.accepted.connect(self.accept);self.actions.rejected.connect(self.reject);outer.addWidget(self.actions)


class DotplotDialog(HistogramDialog):
    transfer=BoxplotDialog.transfer

    def __init__(self,parent,worksheet,mode='one',parameters=None,lock_variables=False):
        parameters=deepcopy(parameters or {});mode=parameters.get('variant',mode)
        if mode not in VARIANTS:raise ValueError('Unsupported dotplot type.')
        grouped=mode.endswith('groups');super().__init__(parent,worksheet,'groups' if grouped else 'simple')
        self.mode=mode;self.setWindowTitle('Dotplot: '+('Multiple Y’s, ' if mode.startswith('multiple') else 'One Y, ')+TITLES[mode])
        self.axis_limits={'x_min':None,'x_max':None};self.intervals=parameters.get('intervals');self.color_levels=parameters.get('color_levels')
        right=self.layout().itemAt(0).layout().itemAt(1).layout();form=right.itemAt(0).layout()
        if grouped:
            form.labelForField(self.group).setText('Categorical variables for grouping ('+('1–4' if mode.startswith('one') else '1–3')+', outermost first):')
            self.group.setPlaceholderText('C3 C4 or quoted column names')
        self.arrangement.clear();self.arrangement.addItem('On the same graph','combined');self.arrangement.addItem('In separate response panels','panels')
        self.arrangement.setCurrentIndex(max(0,self.arrangement.findData(parameters.get('layout','combined'))))
        if form.labelForField(self.arrangement):form.labelForField(self.arrangement).setText('Multiple graphs:')
        else:form.addRow('Multiple graphs:',self.arrangement)
        multiple=mode.startswith('multiple') and mode!='multiple_stack'
        self.arrangement.setVisible(multiple);form.labelForField(self.arrangement).setVisible(multiple)
        self.scale_order=QComboBox();self.scale_order.addItem('Graph variables displayed outermost on scale','outer');self.scale_order.addItem('Graph variables displayed innermost on scale','inner')
        self.scale_order.setCurrentIndex(max(0,self.scale_order.findData(parameters.get('variable_position','outer'))))
        if mode.startswith('multiple') and grouped:form.addRow('Scale level for graph variables:',self.scale_order)
        else:self.scale_order.hide()
        self.stack=QCheckBox('Stack dots of graph variables' if mode=='multiple_stack' else 'Stack dots of last categorical variable');self.stack.setChecked(parameters.get('stack',True))
        if '_stack' in mode:form.addRow(self.stack)
        else:self.stack.hide()
        self.data_button=QPushButton('Data View…');self.data_button.setAutoDefault(False);self.data_button.clicked.connect(self.edit_data_view)
        if grouped:right.itemAt(right.count()-2).layout().insertWidget(0,self.data_button)
        else:self.data_button.hide()
        for label in self.findChildren(QLabel):
            if label.text().startswith('Select up to'):label.setText('Each dot represents one observation. Up to 32 series and 10,000 retained observations.')
        for field,key in ((self.variables,'response_indices'),(self.group,'group_indices')):
            if parameters.get(key):field.setText(' '.join(format_variable_reference(i,worksheet) for i in parameters[key]))
        if lock_variables:
            for widget in (self.available,self.select_button,self.variables,self.group):widget.setEnabled(False)

    def values(self):
        return validate_parameters(self.worksheet,resolve_variables(self.variables.text(),self.worksheet),self.mode,
            resolve_variables(self.group.text(),self.worksheet,('number','text')) if self.grouped else [],self.scale_order.currentData(),
            self.arrangement.currentData(),self.stack.isChecked(),self.intervals,self.color_levels)

    def validate(self):
        try:parameters=self.values();build_dotplots(self.worksheet,**parameters)
        except (ValueError,TypeError,ArithmeticError) as exc:self.error.setText(str(exc));return False
        self._settings=parameters;self.error.clear();self.accept();return True

    def edit_data_view(self):
        try:groups=resolve_variables(self.group.text(),self.worksheet,('number','text'))
        except ValueError as exc:self.error.setText(str(exc));return
        if not groups:self.error.setText('Select grouping variables first.');return
        dialog=QDialog(self);dialog.setWindowTitle('Dotplot: Data View');layout=QVBoxLayout(dialog);layout.addWidget(QLabel('Categorical variables for attribute assignment (up to 3):'))
        levels=self.color_levels if self.color_levels is not None else list(range(max(0,len(groups)-3),len(groups)));dialog.controls=[]
        for i,index in enumerate(groups):
            check=QCheckBox(format_variable_reference(index,self.worksheet));check.setChecked(i in levels);dialog.controls.append(check);layout.addWidget(check)
        error=QLabel();layout.addWidget(error);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons)
        def accept():
            if sum(c.isChecked() for c in dialog.controls)>3:error.setText('Choose at most three variables.');return
            dialog.accept()
        buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.color_levels=[i for i,c in enumerate(dialog.controls) if c.isChecked()]

    def edit_scale(self):
        from .graph_presentation import validate_presentation
        dialog=QDialog(self);dialog.setWindowTitle('Dotplot: Scale');layout=QVBoxLayout(dialog);form=QFormLayout();dialog.controls={}
        for key,text in (('x_min','Value scale minimum:'),('x_max','Value scale maximum:')):
            edit=QLineEdit('' if self.axis_limits[key] is None else str(self.axis_limits[key]));edit.setPlaceholderText('Automatic');dialog.controls[key]=edit;form.addRow(text,edit)
        dialog.intervals=QSpinBox();dialog.intervals.setRange(0,200);dialog.intervals.setSpecialValueText('Automatic');dialog.intervals.setValue(self.intervals or 0);form.addRow('Number of dot intervals:',dialog.intervals)
        layout.addLayout(form);error=QLabel();layout.addWidget(error);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons)
        def accept():
            try:values={k:float(e.text()) if e.text().strip() else None for k,e in dialog.controls.items()};validate_presentation(values)
            except ValueError as exc:error.setText(str(exc));return
            dialog.values=values;dialog.accept()
        buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.axis_limits=dialog.values;self.intervals=dialog.intervals.value() or None

    def presentation_settings(self):return dict(self.presentation(),**self.axis_limits)
