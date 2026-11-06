"""Original MSA forms with persistent, typed worksheet-variable selection.

Input roles follow the implemented analyses. Native ordinary-dialog geometry and
option completeness have not been established by these forms.
"""
from __future__ import annotations
import math
from PySide6.QtCore import Qt,QEvent
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,
    QFormLayout,QLabel,QLineEdit,QPushButton,QListWidget,QListWidgetItem)
from .variable_dialogs import format_variable_reference,resolve_variables


def _positive(value,label,optional=False,default=None):
    if value is None or isinstance(value,str) and not value.strip():
        if optional:return None
        value=default
    if isinstance(value,bool):raise ValueError(label+' must be a positive finite number.')
    try:number=float(value)
    except (ValueError,TypeError,OverflowError) as error:
        raise ValueError(label+' must be a positive finite number.') from error
    if not math.isfinite(number) or number<=0:
        raise ValueError(label+' must be a positive finite number.')
    return number


def _nested_options(options):
    return {'study_multiplier':_positive(options.get('study_multiplier'),'Study variation',default=6),
            'tolerance':_positive(options.get('tolerance'),'Process tolerance',optional=True),
            'process_stdev':_positive(options.get('process_stdev'),'Historical standard deviation',optional=True)}


class GageRRNestedOptionsDialog(QDialog):
    def __init__(self,current_options=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Gage R&R Study (Nested): Options')
        self.setModal(True)
        self.setMinimumSize(440, 280)
        self.resize(440, 280)
        self.setSizeGripEnabled(True)
        self.selected_options=None
        options=current_options or {};layout=QVBoxLayout(self);form=QFormLayout()
        for attr,key,label,placeholder in [
            ('edit_multiplier','study_multiplier','Study variation (number of SDs):','6'),
            ('edit_tolerance','tolerance','Process tolerance:','Optional: USL - LSL'),
            ('edit_process_stdev','process_stdev','Historical standard deviation:','Optional')]:
            value=options.get(key,6 if key=='study_multiplier' else None)
            control=QLineEdit('' if value is None else str(value));control.setPlaceholderText(placeholder)
            setattr(self,attr,control);form.addRow(label,control)
        layout.addLayout(form);self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QHBoxLayout();buttons.addStretch()
        self.btn_ok=QPushButton('OK');self.btn_ok.setDefault(True);self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel=QPushButton('Cancel');self.btn_cancel.setAutoDefault(False);self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_ok);buttons.addWidget(self.btn_cancel);layout.addLayout(buttons)

    def _on_ok(self):
        self.selected_options=None
        try:
            self.selected_options=_nested_options({'study_multiplier':self.edit_multiplier.text(),
                'tolerance':self.edit_tolerance.text(),'process_stdev':self.edit_process_stdev.text()})
        except ValueError as error:self.error.setText(str(error));return
        self.error.clear();self.accept()


class _MsaColumnDialog(QDialog):
    """Retain the last variable role when focus moves to the list or Select."""
    def __init__(self,worksheet,parent,title,roles,first,size=(680,370),scalar_fields=()):
        super().__init__(parent);self.worksheet=worksheet;self.selected_params=None
        self.setWindowTitle(title);self.setModal(True);self.resize(*size)
        self._roles={attr:(key,kinds,optional) for attr,key,label,kinds,optional in roles}
        layout=QVBoxLayout(self);body=QHBoxLayout();left=QVBoxLayout()
        left.addWidget(QLabel('Columns:'));self.col_list=QListWidget();self.col_list.setMinimumWidth(210)
        self.col_list.itemDoubleClicked.connect(self._on_col_double_clicked);left.addWidget(self.col_list)
        self.btn_select=QPushButton('Select');self.btn_select.setAutoDefault(False)
        self.btn_select.clicked.connect(self._on_select_clicked)
        self.col_list.itemSelectionChanged.connect(lambda:self.btn_select.setEnabled(self.col_list.currentItem() is not None))
        left.addWidget(self.btn_select);body.addLayout(left,1)
        self.form_layout=QFormLayout()
        for attr,key,label,kinds,optional in roles:
            field=QLineEdit();field.setPlaceholderText('Optional' if optional else 'Select a column, or enter C1')
            setattr(self,attr,field);field.installEventFilter(self);self.form_layout.addRow(label,field)
        for attr,label,placeholder in scalar_fields:
            field=QLineEdit();field.setPlaceholderText(placeholder);setattr(self,attr,field);self.form_layout.addRow(label,field)
        right=QVBoxLayout();right.addLayout(self.form_layout);right.addStretch();body.addLayout(right,2);layout.addLayout(body)
        self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QHBoxLayout();buttons.addStretch()
        self.btn_ok=QPushButton('OK');self.btn_ok.setDefault(True);self.btn_ok.clicked.connect(self._on_ok)
        self.btn_cancel=QPushButton('Cancel');self.btn_cancel.setAutoDefault(False);self.btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(self.btn_ok);buttons.addWidget(self.btn_cancel);layout.addLayout(buttons)
        self._active_field=getattr(self,first);self._activate_field(self._active_field);self._active_field.setFocus()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.FocusIn and any(watched is getattr(self,attr) for attr in self._roles):
            self._activate_field(watched)
        return super().eventFilter(watched,event)

    def _activate_field(self,field):
        if getattr(self,'_active_field',None) is field and self.col_list.count():return
        self._active_field=field
        role=next(self._roles[attr] for attr in self._roles if getattr(self,attr) is field)
        previous=self.col_list.currentItem()
        previous_index=previous.data(Qt.ItemDataRole.UserRole) if previous else None
        self.col_list.clear()
        for index,column in enumerate(self.worksheet.columns):
            if column.kind in role[1]:
                text=format_variable_reference(index,self.worksheet);item=QListWidgetItem(text)
                item.setToolTip(text);item.setData(Qt.ItemDataRole.UserRole,index);self.col_list.addItem(item)
                if index==previous_index:self.col_list.setCurrentItem(item)
        self.btn_select.setEnabled(self.col_list.currentItem() is not None)

    def _get_active_field(self):return self._active_field

    def _on_col_double_clicked(self,item):self._transfer(item)

    def _on_select_clicked(self):
        item=self.col_list.currentItem()
        if item is not None:self._transfer(item)

    def _transfer(self,item):
        index=item.data(Qt.ItemDataRole.UserRole)
        self._active_field.setText(format_variable_reference(index,self.worksheet))
        self._active_field.setFocus();self.error.clear()

    def _parameters(self):
        params={}
        for attr,(key,kinds,optional) in self._roles.items():
            text=getattr(self,attr).text().strip()
            if not text and optional:params[key]=None;continue
            indices=resolve_variables(text,self.worksheet,kinds)
            if len(indices)!=1:raise ValueError('Select exactly one column for '+key.replace('_',' ')+'.')
            params[key]=indices[0]
        return params

    def _on_ok(self):
        self.selected_params=None
        try:params=self._parameters()
        except (ValueError,TypeError,OverflowError) as error:self.error.setText(str(error));return
        self.selected_params=params;self.error.clear();self.accept()


_CATEGORICAL=('number','text')
_NUMERIC=('number',)


class GageRRNestedDialog(_MsaColumnDialog):
    def __init__(self,worksheet,parent=None):
        super().__init__(worksheet,parent,'Gage R&R Study (Nested)',[
            ('edit_part','part_col','Part numbers:',_CATEGORICAL,False),
            ('edit_op','operator_col','Operators:',_CATEGORICAL,False),
            ('edit_meas','measurement_col','Measurement data:',_NUMERIC,False)],'edit_part')
        self.options={'study_multiplier':6.0,'tolerance':None,'process_stdev':None}
        self.btn_options=QPushButton('Options…');self.btn_options.setAutoDefault(False)
        self.btn_options.clicked.connect(self._on_options_clicked);self.form_layout.addRow('',self.btn_options)

    def _on_options_clicked(self):
        dialog=GageRRNestedOptionsDialog(self.options,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.options=dialog.selected_options

    def _parameters(self):return dict(super()._parameters(),options=_nested_options(self.options))


class GageLinearityDialog(_MsaColumnDialog):
    def __init__(self,worksheet,parent=None):
        super().__init__(worksheet,parent,'Gage Linearity and Bias Study',[
            ('edit_part','part_col','Part numbers (optional):',_CATEGORICAL,True),
            ('edit_ref','reference_col','Reference values:',_NUMERIC,False),
            ('edit_meas','measurement_col','Measurement data:',_NUMERIC,False)],'edit_ref',
            scalar_fields=[('edit_pv','Process variation:','Optional (or 6 * Process SD)')])

    def _parameters(self):return dict(super()._parameters(),process_variation=_positive(self.edit_pv.text(),'Process variation',optional=True))


class AttributeAgreementDialog(_MsaColumnDialog):
    def __init__(self,worksheet,parent=None):
        super().__init__(worksheet,parent,'Attribute Agreement Analysis',[
            ('edit_meas','attribute_col','Appraisal results:',_CATEGORICAL,False),
            ('edit_sample','sample_col','Test items (Samples):',_CATEGORICAL,False),
            ('edit_app','appraiser_col','Appraisers:',_CATEGORICAL,False),
            ('edit_std','standard_col','Known standards:',_CATEGORICAL,True),
            ('edit_trial','trial_col','Trials:',_CATEGORICAL,True)],'edit_meas',size=(700,410))

