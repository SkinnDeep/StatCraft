"""Resource-guided individual-value/interval galleries, roles and working options."""
from copy import deepcopy
from PySide6.QtCore import Qt,QSize,QPointF
from PySide6.QtGui import QColor,QPainter,QPen,QPixmap,QIcon
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QGroupBox,QToolButton,QButtonGroup,QDialogButtonBox,
    QCheckBox,QLabel,QComboBox,QDoubleSpinBox,QPushButton)
from .boxplot_dialogs import BoxplotDialog,MODES
from .categorical_points import validate_parameters,validate_display,validate_interval,build_points
from .dialog_theme import dialog_stylesheet, gallery_button_stylesheet, is_dark_active
from .variable_dialogs import resolve_variables,format_variable_reference


def plot_name(plot_type):return 'Individual Value Plot' if plot_type=='individual' else 'Interval Plot'


def point_icon(mode,plot_type,dark=False):
    pix=QPixmap(240,160);pix.setDevicePixelRatio(2);pix.fill(QColor('#18181b' if dark else 'white'));p=QPainter(pix);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#a1a1aa' if dark else '#64717c'),1));p.drawLine(12,68,112,68);p.drawLine(12,68,12,8)
    count=1 if mode=='one' else 3 if mode=='one_groups' else 2 if mode=='multiple' else 4
    for i in range(count):
        center=60 if count==1 else 27+i*72/(count-1);mid=36+(i%2)*9;color=QColor('#3e739b' if i%2==0 else '#b46e39');p.setPen(QPen(color,1.5));p.setBrush(color)
        if plot_type=='interval':
            p.drawLine(QPointF(center,mid-18),QPointF(center,mid+18));p.drawLine(QPointF(center-4,mid-18),QPointF(center+4,mid-18));p.drawLine(QPointF(center-4,mid+18),QPointF(center+4,mid+18));p.drawEllipse(QPointF(center,mid),3,3)
        else:
            for j in range(6):p.drawEllipse(QPointF(center+(j%3-1)*4,mid+(j-3)*5),2.2,2.2)
    p.end();return QIcon(pix)


class CategoricalTypeDialog(QDialog):
    def __init__(self,plot_type,parent=None):
        super().__init__(parent);self.setWindowTitle(plot_name(plot_type)+'s');self.mode='one';self.buttons=QButtonGroup(self);self.mode_buttons={};outer=QVBoxLayout(self)
        dark = is_dark_active(parent or self)
        self.setStyleSheet(dialog_stylesheet(dark))
        self.setSizeGripEnabled(True)
        for heading,keys in (('One Y',('one','one_groups')),('Multiple Y’s',('multiple','multiple_groups'))):
            group=QGroupBox(heading);row=QHBoxLayout(group)
            for key in keys:
                button=QToolButton();button.setText('With Groups' if key.endswith('groups') else 'Simple');button.setIcon(point_icon(key,plot_type,dark=dark));button.setIconSize(QSize(120,80))
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon);button.setCheckable(True);button.setChecked(key=='one');button.setMinimumSize(165,125)
                button.setStyleSheet(gallery_button_stylesheet(dark))
                button.clicked.connect(lambda checked=False,key=key:setattr(self,'mode',key));self.buttons.addButton(button);self.mode_buttons[key]=button;row.addWidget(button)
            outer.addWidget(group)
        self.actions=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);self.actions.accepted.connect(self.accept);self.actions.rejected.connect(self.reject);outer.addWidget(self.actions)


class IntervalOptionsDialog(QDialog):
    def __init__(self,options,parent=None):
        super().__init__(parent);self.setWindowTitle('Interval Options');options=validate_interval(options);outer=QVBoxLayout(self);form=QFormLayout()
        self.setSizeGripEnabled(True)
        self.method=QComboBox();self.method.addItem('Confidence interval','confidence');self.method.addItem('Standard error','standard_error');self.method.setCurrentIndex(self.method.findData(options['method']));form.addRow('Type of interval:',self.method)
        self.confidence=QDoubleSpinBox();self.confidence.setDecimals(3);self.confidence.setRange(.1,99.999);self.confidence.setValue(options['confidence']*100);self.confidence.setSuffix('%');form.addRow('Confidence level:',self.confidence)
        self.multiple=QDoubleSpinBox();self.multiple.setRange(.001,100);self.multiple.setDecimals(3);self.multiple.setValue(options['multiple']);form.addRow('Standard-error multiple:',self.multiple)
        self.side=QComboBox();self.side.addItem('Two-sided','two-sided');self.side.addItem('Upper one-sided','upper');self.side.addItem('Lower one-sided','lower');self.side.setCurrentIndex(self.side.findData(options['side']));form.addRow('Side:',self.side)
        self.pooled=QCheckBox('Pool error across groups within each response');self.pooled.setChecked(options['pooled']);form.addRow(self.pooled)
        self.bonferroni=QCheckBox('Bonferroni within each response');self.bonferroni.setChecked(options['bonferroni']);form.addRow(self.bonferroni)
        outer.addLayout(form);self.error=QLabel();outer.addWidget(self.error)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);self.buttons.accepted.connect(self.validate);self.buttons.rejected.connect(self.reject);outer.addWidget(self.buttons)
        self.method.currentIndexChanged.connect(self.method_changed);self.method_changed()

    def method_changed(self):
        confidence=self.method.currentData()=='confidence';self.confidence.setEnabled(confidence);self.multiple.setEnabled(not confidence);self.side.setEnabled(confidence);self.bonferroni.setEnabled(confidence)
        if not confidence:self.side.setCurrentIndex(0);self.bonferroni.setChecked(False)

    def validate(self):
        try:self.options=validate_interval(dict(method=self.method.currentData(),confidence=self.confidence.value()/100,multiple=self.multiple.value(),side=self.side.currentData(),pooled=self.pooled.isChecked(),bonferroni=self.bonferroni.isChecked()))
        except ValueError as exc:self.error.setText(str(exc));return False
        self.accept();return True


class CategoricalPlotDialog(BoxplotDialog):
    def __init__(self,parent,worksheet,plot_type='individual',mode='one',parameters=None,lock_variables=False):
        parameters=deepcopy(parameters or {});plot_type=parameters.get('plot_type',plot_type)
        if plot_type not in ('individual','interval'):raise ValueError('Unsupported plot type.')
        base={k:v for k,v in parameters.items() if k in ('variant','response_indices','group_indices','variable_position','layout')}
        super().__init__(parent,worksheet,mode,parameters=base,lock_variables=lock_variables)
        self.plot_type=plot_type;self.display=validate_display(parameters.get('display'),plot_type);self.interval_options=validate_interval(parameters.get('interval_options'));self.jitter=parameters.get('jitter',.12);self.color_levels=parameters.get('color_levels')
        self.setWindowTitle(plot_name(plot_type)+': '+MODES[self.mode]);self.group.setPlaceholderText('C3 C4 or quoted column names')
        for label in self.findChildren(QLabel):
            if label.text().startswith('Up to 32 observed boxes'):label.setText('Up to 32 observed categories. Individual symbols support 10,000 retained observations.')

    def values(self):
        return validate_parameters(self.worksheet,resolve_variables(self.variables.text(),self.worksheet),self.plot_type,self.mode,
            resolve_variables(self.group.text(),self.worksheet,('number','text')) if self.grouped else [],self.scale_order.currentData(),self.arrangement.currentData(),self.display,self.interval_options,self.jitter,self.color_levels)

    def validate(self):
        try:parameters=self.values();build_points(self.worksheet,**parameters)
        except (ValueError,TypeError,ArithmeticError) as exc:self.error.setText(str(exc));return False
        self._settings=parameters;self.error.clear();self.accept();return True

    def edit_interval(self):
        dialog=IntervalOptionsDialog(self.interval_options,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.interval_options=dialog.options

    def edit_data_view(self):
        try:groups=resolve_variables(self.group.text(),self.worksheet,('number','text')) if self.grouped else []
        except ValueError as exc:self.error.setText(str(exc));return
        dialog=QDialog(self);dialog.setWindowTitle(plot_name(self.plot_type)+': Data View');layout=QVBoxLayout(dialog);dialog.controls={}
        for key,text in (('interval','Interval bar'),('bar','Bar'),('individual','Individual symbols'),('mean_symbol','Mean symbol'),('mean_connect','Mean connect line'),('median_symbol','Median symbol'),('median_connect','Median connect line')):
            check=QCheckBox(text);check.setChecked(self.display[key]);dialog.controls[key]=check;layout.addWidget(check)
        interval=QPushButton('Interval Options…');interval.setAutoDefault(False);interval.clicked.connect(self.edit_interval);layout.addWidget(interval)
        jitter=QDoubleSpinBox();jitter.setDecimals(2);jitter.setRange(0,.4);jitter.setSingleStep(.02);jitter.setValue(self.jitter);form=QFormLayout();form.addRow('Jitter in category direction:',jitter);layout.addLayout(form);dialog.jitter=jitter
        dialog.colors=[]
        if groups:
            layout.addWidget(QLabel('Categorical variables for attribute assignment:'))
            for i,index in enumerate(groups):
                check=QCheckBox(format_variable_reference(index,self.worksheet));check.setChecked(self.color_levels is None or i in self.color_levels);dialog.colors.append(check);layout.addWidget(check)
        error=QLabel();layout.addWidget(error);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);layout.addWidget(buttons)
        original_options=deepcopy(self.interval_options)
        def accept():
            try:validate_display({key:c.isChecked() for key,c in dialog.controls.items()},self.plot_type)
            except ValueError as exc:error.setText(str(exc));return
            dialog.accept()
        buttons.accepted.connect(accept);buttons.rejected.connect(dialog.reject)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.display={key:c.isChecked() for key,c in dialog.controls.items()};self.jitter=jitter.value();self.color_levels=[i for i,c in enumerate(dialog.colors) if c.isChecked()]
        else:self.interval_options=original_options
