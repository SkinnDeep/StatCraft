"""Resource-guided boxplot gallery and named categorical variable roles."""
from copy import deepcopy
from PySide6.QtCore import Qt,QSize,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QIcon,QPixmap
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QToolButton,QButtonGroup,
    QDialogButtonBox,QCheckBox,QFormLayout,QLineEdit,QLabel,QComboBox,QPushButton)
from .dialog_theme import dialog_stylesheet, gallery_button_stylesheet, is_dark_active
from .histogram_dialogs import HistogramDialog
from .variable_dialogs import format_variable_reference,resolve_variables
from .boxplot_graphs import validate_parameters,validate_display,build_boxplots

MODES={'one':'One Y, Simple','one_groups':'One Y, With Groups','multiple':'Multiple Y’s, Simple','multiple_groups':'Multiple Y’s, With Groups'}


def box_icon(mode, dark=False):
    pix=QPixmap(120,80);pix.fill(QColor('#18181b' if dark else 'white'));p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#a1a1aa' if dark else '#64717c'),1));p.drawLine(12,68,112,68);p.drawLine(12,68,12,8)
    count=1 if mode=='one' else 3 if mode=='one_groups' else 2 if mode=='multiple' else 4
    for i in range(count):
        x=25+i*75/max(1,count-1) if count>1 else 60;top=20+(i%2)*8
        color=QColor('#3e739b' if i%2==0 else '#b46e39');p.setPen(QPen(color,1.3));p.setBrush(QColor('#b9d0e1' if i%2==0 else '#e5c8ab'))
        p.drawLine(int(x),top-9,int(x),top+34);p.drawLine(int(x-5),top-9,int(x+5),top-9);p.drawLine(int(x-5),top+34,int(x+5),top+34)
        p.drawRect(QRectF(x-7,top,14,23));p.drawLine(int(x-7),top+12,int(x+7),top+12)
    p.end();return QIcon(pix)


class BoxplotTypeDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('Boxplots');self.mode='one'
        dark = is_dark_active(parent or self)
        self.setStyleSheet(dialog_stylesheet(dark))
        self.setSizeGripEnabled(True)
        outer=QVBoxLayout(self);self.mode_buttons={};self.buttons=QButtonGroup(self)
        for heading,keys in (('One Y',('one','one_groups')),('Multiple Y’s',('multiple','multiple_groups'))):
            group=QGroupBox(heading);row=QHBoxLayout(group)
            for key in keys:
                button=QToolButton();button.setText('With Groups' if key.endswith('groups') else 'Simple')
                button.setIcon(box_icon(key, dark=dark));button.setIconSize(QSize(120,80));button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                button.setCheckable(True);button.setChecked(key=='one');button.setMinimumSize(165,125)
                button.setStyleSheet(gallery_button_stylesheet(dark))
                button.clicked.connect(lambda checked=False,key=key:setattr(self,'mode',key));self.buttons.addButton(button);self.mode_buttons[key]=button;row.addWidget(button)
            outer.addWidget(group)
        self.actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.actions.accepted.connect(self.accept);self.actions.rejected.connect(self.reject);outer.addWidget(self.actions)


class BoxplotDialog(HistogramDialog):
    def __init__(self,parent,worksheet,mode='one',parameters=None,lock_variables=False):
        parameters=deepcopy(parameters or {});mode=parameters.get('variant',mode)
        if mode not in MODES:raise ValueError('Unsupported boxplot type.')
        super().__init__(parent,worksheet,'groups' if mode.endswith('groups') else 'simple')
        self.mode=mode;self.display=validate_display(parameters.get('display'));self.axis_limits={'y_min':None,'y_max':None}
        self.setWindowTitle('Boxplot: '+MODES[mode])
        right=self.layout().itemAt(0).layout().itemAt(1).layout();form=right.itemAt(0).layout()
        self.arrangement.clear();self.arrangement.addItem('On the same graph','combined');self.arrangement.addItem('In separate response panels','panels')
        self.arrangement.setCurrentIndex(max(0,self.arrangement.findData(parameters.get('layout','combined'))))
        if form.labelForField(self.arrangement):form.labelForField(self.arrangement).setText('Multiple graphs:')
        else:form.addRow('Multiple graphs:',self.arrangement)
        self.arrangement.setVisible(mode.startswith('multiple'));form.labelForField(self.arrangement).setVisible(mode.startswith('multiple'))
        if mode.endswith('groups'):form.labelForField(self.group).setText('Categorical variables for grouping ('+('1–4' if mode=='one_groups' else '1–3')+', outermost first):')
        self.scale_order=QComboBox();self.scale_order.addItem('Graph variables displayed outermost on scale','outer');self.scale_order.addItem('Graph variables displayed innermost on scale','inner')
        self.scale_order.setCurrentIndex(max(0,self.scale_order.findData(parameters.get('variable_position','outer'))))
        if mode=='multiple_groups':form.addRow('Scale level for graph variables:',self.scale_order)
        else:self.scale_order.hide()
        self.data_button=QPushButton('Data View…');self.data_button.setAutoDefault(False);self.data_button.clicked.connect(self.edit_data_view)
        right.itemAt(right.count()-2).layout().insertWidget(0,self.data_button)
        for label in self.findChildren(QLabel):
            if label.text().startswith('Select up to'):label.setText('Up to 32 observed boxes. Missing responses or incomplete group combinations are omitted.')
        if parameters.get('response_indices'):self.variables.setText(' '.join(format_variable_reference(i,worksheet) for i in parameters['response_indices']))
        if parameters.get('group_indices'):self.group.setText(' '.join(format_variable_reference(i,worksheet) for i in parameters['group_indices']))
        if lock_variables:
            for widget in (self.available,self.select_button,self.variables,self.group):widget.setEnabled(False)

    def transfer(self):
        refs=[format_variable_reference(item.data(Qt.ItemDataRole.UserRole),self.worksheet) for item in self.available.selectedItems()]
        if not refs:return
        target=self.group if self.active=='group' else self.variables
        target.setText((target.text().strip()+' ' if target.text().strip() else '')+' '.join(refs));target.setFocus()

    def values(self):
        return validate_parameters(self.worksheet,resolve_variables(self.variables.text(),self.worksheet),self.mode,
            resolve_variables(self.group.text(),self.worksheet,('number','text')) if self.grouped else [],self.scale_order.currentData(),self.arrangement.currentData(),self.display)

    def validate(self):
        try:
            parameters=self.values();build_boxplots(self.worksheet,**parameters)
        except (ValueError,TypeError,ArithmeticError) as exc:self.error.setText(str(exc));return False
        self._settings=parameters;self.error.clear();self.accept();return True

    def edit_data_view(self):
        dialog=QDialog(self);dialog.setWindowTitle('Boxplot: Data View');layout=QVBoxLayout(dialog);dialog.controls={}
        labels={'iqr_box':'Interquartile range box','whiskers':'Whiskers (1.5 IQR)','outliers':'Outlier symbols','individual':'Individual symbols',
                'median_symbol':'Median symbol','mean_symbol':'Mean symbol','median_connect':'Median connect line','mean_connect':'Mean connect line'}
        for key,text in labels.items():
            control=QCheckBox(text);control.setChecked(self.display[key]);dialog.controls[key]=control;layout.addWidget(control)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.display={key:control.isChecked() for key,control in dialog.controls.items()}

    def edit_scale(self):
        from .graph_presentation import validate_presentation
        dialog=QDialog(self);dialog.setWindowTitle('Boxplot: Scale');layout=QVBoxLayout(dialog);form=QFormLayout();dialog.controls={}
        for key,text in (('y_min','Y minimum:'),('y_max','Y maximum:')):
            edit=QLineEdit('' if self.axis_limits[key] is None else str(self.axis_limits[key]));edit.setPlaceholderText('Automatic');dialog.controls[key]=edit;form.addRow(text,edit)
        layout.addLayout(form);error=QLabel();layout.addWidget(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons)
        def accept():
            try:
                values={key:float(edit.text()) if edit.text().strip() else None for key,edit in dialog.controls.items()};validate_presentation(values)
            except ValueError as exc:error.setText(str(exc));return
            dialog.values=values;dialog.accept()
        buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.axis_limits=dialog.values

    def presentation_settings(self):return dict(self.presentation(),**self.axis_limits)
