"""Original multiple-process capability forms using documented data roles.

REA confirms installed menu labels and purpose. Ordinary main-dialog geometry is
unverified; only implemented options are exposed here.
"""
import copy
import math
import re
from PySide6.QtCore import Qt,QEvent
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QLineEdit,QListWidget,QListWidgetItem,QPushButton,QComboBox,QCheckBox,
    QDialogButtonBox,QAbstractItemView)
from .variable_dialogs import format_variable_reference,format_variable_list,resolve_variables


def _numbers(text,label,missing=True,integers=False):
    tokens=[token for token in re.split(r'[\s,]+',text.strip()) if token]
    if not tokens:
        if missing:return None
        raise ValueError(label+' is required.')
    values=[]
    for token in tokens:
        if token=='*' and missing:values.append(None);continue
        try:value=float(token)
        except (ValueError,OverflowError) as error:raise ValueError(label+': enter numbers'+(' or * for a missing limit.' if missing else '.')) from error
        if not math.isfinite(value):raise ValueError(label+' must contain finite numbers.')
        if integers:
            if value<1 or value!=int(value):raise ValueError(label+' must contain positive whole numbers.')
            value=int(value)
        values.append(value)
    return values[0] if len(values)==1 else values


class MultipleCapabilityOptionsDialog(QDialog):
    def __init__(self,options=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Multiple Variables (Normal): Options')
        self.selected_options=None;current=copy.deepcopy(options or {});self.controls={}
        layout=QVBoxLayout(self);form=QFormLayout()
        for key,label,default in [('confidence_level','Confidence level:',95)]:
            control=QLineEdit(str(current.get(key,default)));self.controls[key]=control;form.addRow(label,control)
        for key,label,choices,default in [
            ('ci_type','Confidence intervals:',['two_sided','lower','upper'],'two_sided'),
            ('analysis_mode','Subgroup variation:',['normal','between_within'],'normal'),
            ('estimate_method_gt1','Within standard deviation (subgroups > 1):',['pooled','rbar','sbar'],'pooled'),
            ('estimate_method_eq1','Within standard deviation (subgroup = 1):',['amr','mmr','srmssd'],'amr'),
            ('stats_type','Display statistics:',['capability','zbench'],'capability'),
            ('display_unit','Nonconformance units:',['ppm','percent'],'ppm')]:
            control=QComboBox()
            labels={'two_sided':'Two-sided','lower':'Lower bound','upper':'Upper bound','normal':'Within subgroups','between_within':'Between/Within subgroups','pooled':'Pooled standard deviation','rbar':'Average subgroup range','sbar':'Average subgroup standard deviation','amr':'Average moving range','mmr':'Median moving range','srmssd':'Square root of mean squared successive differences','capability':'Capability statistics','zbench':'Benchmark Z','ppm':'Parts per million','percent':'Percent'}
            for choice in choices:control.addItem(labels[choice],choice)
            control.setCurrentIndex(choices.index(current.get(key,default)));self.controls[key]=control;form.addRow(label,control)
        for key,label,default in [('include_ci','Include confidence intervals',False),('unbiased_within','Use unbiasing constants for within standard deviation',True),('unbiased_overall','Use unbiasing constants for overall standard deviation',False)]:
            control=QCheckBox(label);control.setChecked(current.get(key,default));self.controls[key]=control;form.addRow('',control)
        layout.addLayout(form);self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_ok);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.btn_ok=buttons.button(QDialogButtonBox.StandardButton.Ok)

    def _on_ok(self):
        try:
            opts={}
            for key,control in self.controls.items():
                if isinstance(control,QCheckBox):opts[key]=control.isChecked()
                elif isinstance(control,QComboBox):opts[key]=control.currentData()
                else:
                    value=_numbers(control.text(),key,missing=False)
                    if isinstance(value,list) or value<=0:raise ValueError(key+' must be a positive number.')
                    opts[key]=value
            if opts['confidence_level']>=100:raise ValueError('Confidence level must be between 0 and 100.')
        except (ValueError,TypeError) as error:self.error.setText(str(error));return
        self.selected_options=opts;self.accept()


class MultipleCapabilityDialog(QDialog):
    def __init__(self,worksheet,method='normal',parent=None):
        if method not in ('normal','nonnormal'):raise ValueError('Choose normal or nonnormal capability.')
        super().__init__(parent);self.worksheet=worksheet;self.method=method
        self.selected_params=None;self.parameters=None;self.options={};self._active_field=None
        self.setWindowTitle('Capability Analysis: Multiple Variables ('+method.title()+')');self.resize(810,540)
        layout=QVBoxLayout(self);body=QHBoxLayout();left=QVBoxLayout()
        left.addWidget(QLabel('Columns:'));self.col_list=QListWidget();self.col_list.setMinimumWidth(230)
        self.col_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.col_list.itemDoubleClicked.connect(lambda item:self._transfer([item]));left.addWidget(self.col_list)
        self.btn_select=QPushButton('Select');self.btn_select.setAutoDefault(False);self.btn_select.clicked.connect(lambda:self._transfer(self.col_list.selectedItems()))
        self.col_list.itemSelectionChanged.connect(lambda:self.btn_select.setEnabled(bool(self.col_list.selectedItems())));left.addWidget(self.btn_select);body.addLayout(left,1)
        form=QFormLayout();self._roles={}
        self.edit_variables=self._column_entry('variables',('number',));form.addRow('Variables:',self.edit_variables)
        self.chk_by=QCheckBox('By variables');self.edit_by=self._column_entry('by',('number','text'));form.addRow(self.chk_by,self.edit_by)
        self.chk_by.toggled.connect(self._toggle_by)
        if method=='normal':
            self.subgroup_mode=QComboBox();self.subgroup_mode.addItems(['Subgroup sizes','Columns of subgroup IDs'])
            form.addRow('Subgroup definition:',self.subgroup_mode)
            self.edit_subgroup_sizes=QLineEdit('1');form.addRow('Subgroup sizes:',self.edit_subgroup_sizes)
            self.edit_subgroup_ids=self._column_entry('subgroup',('number','text'));form.addRow('Subgroup ID columns:',self.edit_subgroup_ids)
            self.subgroup_mode.currentIndexChanged.connect(self._toggle_subgroups)
        else:
            self.distribution=QComboBox();self.distribution.addItem('Weibull','weibull');self.distribution.addItem('Lognormal','lognormal');self.distribution.addItem('Gamma','gamma');self.distribution.addItem('Exponential','exponential')
            form.addRow('Fit distribution:',self.distribution)
        for attr,label in [('edit_lower','Lower spec:'),('edit_upper','Upper spec:'),('edit_targets','Targets (optional):')]:
            entry=QLineEdit();entry.setPlaceholderText('One value for all, or one per variable/group; * = missing')
            setattr(self,attr,entry);form.addRow(label,entry)
        self.edit_title=QLineEdit();form.addRow('Title (optional):',self.edit_title)
        self.chk_graphs=QCheckBox('Display graphs');self.chk_graphs.setChecked(True);form.addRow('',self.chk_graphs)
        if method=='normal':
            self.btn_options=QPushButton('Options…');self.btn_options.setAutoDefault(False);self.btn_options.clicked.connect(self._open_options);form.addRow('',self.btn_options)
        right=QVBoxLayout();right.addLayout(form)
        note=QLabel('Enter at least one specification limit for every variable or group. Multiple values follow the variable order or the worksheet group-value order.');note.setWordWrap(True);right.addWidget(note);right.addStretch();body.addLayout(right,2);layout.addLayout(body)
        self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.btn_ok=buttons.button(QDialogButtonBox.StandardButton.Ok);buttons.accepted.connect(self._on_ok);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self._toggle_by(False)
        if method=='normal':self._toggle_subgroups()
        self._activate(self.edit_variables);self.edit_variables.setFocus()

    def _column_entry(self,key,kinds):
        field=QLineEdit();field.setPlaceholderText('Select columns, or enter C1 C2')
        self._roles[field]=(key,kinds);field.installEventFilter(self);return field

    def eventFilter(self,watched,event):
        if watched in self._roles and event.type()==QEvent.Type.FocusIn:self._activate(watched)
        return super().eventFilter(watched,event)

    def _activate(self,field):
        if field is self._active_field:return
        self._active_field=field;self.col_list.clear()
        for index,column in enumerate(self.worksheet.columns):
            if column.kind in self._roles[field][1]:
                text=format_variable_reference(index,self.worksheet);item=QListWidgetItem(text)
                item.setToolTip(text);item.setData(Qt.ItemDataRole.UserRole,index);self.col_list.addItem(item)
        self.btn_select.setEnabled(False)

    def _transfer(self,items):
        if not items or self._active_field is None or not self._active_field.isEnabled():return
        try:indices=resolve_variables(self._active_field.text(),self.worksheet,self._roles[self._active_field][1])
        except ValueError:indices=[]
        for item in items:
            index=item.data(Qt.ItemDataRole.UserRole)
            if index not in indices:indices.append(index)
        self._active_field.setText(format_variable_list(indices,self.worksheet));self._active_field.setFocus();self.error.clear()

    def _toggle_by(self,enabled):
        self.edit_by.setEnabled(enabled)
        if not enabled and self._active_field is self.edit_by:self._activate(self.edit_variables)

    def _toggle_subgroups(self):
        columns=self.subgroup_mode.currentIndex()==1
        self.edit_subgroup_sizes.setEnabled(not columns);self.edit_subgroup_ids.setEnabled(columns)
        if not columns and self._active_field is self.edit_subgroup_ids:self._activate(self.edit_variables)

    def _open_options(self):
        dialog=MultipleCapabilityOptionsDialog(self.options,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:self.options=dialog.selected_options

    def values(self):
        variables=resolve_variables(self.edit_variables.text(),self.worksheet)
        if not variables:raise ValueError('Select at least one numeric process variable.')
        by=resolve_variables(self.edit_by.text(),self.worksheet,('number','text')) if self.chk_by.isChecked() else []
        if self.chk_by.isChecked() and not by:raise ValueError('Select at least one By variable.')
        if by and len(variables)!=1:raise ValueError('Use one process variable when By variables are selected.')
        if set(variables)&set(by):raise ValueError('A process variable cannot also be a By variable.')
        count=len(variables)
        if by:
            cols=[self.worksheet.columns[index] for index in by]
            response=self.worksheet.columns[variables[0]]
            groups=set()
            extent=max([len(response.values)]+[len(col.values) for col in cols])
            for row in range(extent):
                group=tuple(col.values[row] if row<len(col.values) else None for col in cols)
                if None not in group:groups.add(group)
            count=len(groups)
            if not count:raise ValueError('No complete process and grouping rows were found.')
        lower=_numbers(self.edit_lower.text(),'Lower spec');upper=_numbers(self.edit_upper.text(),'Upper spec');targets=_numbers(self.edit_targets.text(),'Targets')
        def broadcast(value,label):
            values=value if isinstance(value,list) else [value]
            if len(values) not in (1,count):raise ValueError(label+' must have one value, or one for each variable/group ('+str(count)+').')
            return values*count if len(values)==1 else values
        lows=broadcast(lower,'Lower spec');highs=broadcast(upper,'Upper spec');broadcast(targets,'Targets')
        for lo,hi in zip(lows,highs):
            if lo is None and hi is None:raise ValueError('Enter at least one specification limit for every variable/group.')
            if lo is not None and hi is not None and lo>=hi:raise ValueError('Lower spec must be less than upper spec.')
        subgroup_sizes=1;subgroup_indices=None
        if self.method=='normal':
            if self.subgroup_mode.currentIndex()==0:
                subgroup_sizes=_numbers(self.edit_subgroup_sizes.text(),'Subgroup sizes',missing=False,integers=True)
                values=subgroup_sizes if isinstance(subgroup_sizes,list) else [subgroup_sizes]
                if len(values) not in (1,len(variables)) or by and len(values)!=1:raise ValueError('Use one subgroup size, or one per process variable.')
            else:
                subgroup_indices=resolve_variables(self.edit_subgroup_ids.text(),self.worksheet,('number','text'))
                if not subgroup_indices or len(subgroup_indices) not in (1,len(variables)) or by and len(subgroup_indices)!=1:raise ValueError('Use one subgroup ID column, or one per process variable.')
                if set(subgroup_indices)&(set(variables)|set(by)):raise ValueError('Use separate process, By and subgroup ID columns.')
        options=copy.deepcopy(self.options);options.update(title=self.edit_title.text().strip(),show_graphs=self.chk_graphs.isChecked())
        return {'method':self.method,'variable_indices':variables,'by_indices':by or None,
                'subgroup_sizes':subgroup_sizes,'subgroup_indices':subgroup_indices,
                'lower_specs':lower,'upper_specs':upper,'targets':targets,
                'distribution':self.distribution.currentData() if self.method=='nonnormal' else 'weibull','options':options}

    def get_configuration(self):return self.values()

    def _on_ok(self):
        self.selected_params=None;self.parameters=None
        try:self.selected_params=self.values()
        except (ValueError,TypeError,OverflowError) as error:self.error.setText(str(error));return
        self.parameters=self.selected_params
        self.error.clear();self.accept()
