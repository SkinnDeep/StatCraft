"""Named mixture/process model inputs and saved-model predictions.

Authenticated native mixture type/terms/prediction dialogs guide role labels.
The tensor-product preset and additive covariate form are original bounded
workflows; native runtime defaults and complete dialog parity are unverified.
"""
import copy
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,
    QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView,QLabel,QDialogButtonBox,QSpinBox)
from .variable_dialogs import ProcedureDialog,format_variable_list,format_variable_reference,resolve_variables
from .doe_analysis_dialogs import _verified_factors,_MIXTURE_DESIGNS


def _finite(raw,label):
    try:value=float(raw)
    except (ValueError,TypeError,OverflowError) as error:raise ValueError(label+' must be a finite number.') from error
    if not math.isfinite(value):raise ValueError(label+' must be a finite number.')
    return value


class MixtureProcessDialog(ProcedureDialog):
    def __init__(self,worksheet,parent=None):
        super().__init__(parent,'Analyze Mixture Design — Process Variables and Blocks',worksheet,
            selectors=(
                {'key':'response_index','label':'Response:'},
                {'key':'component_indices','label':'Mixture components:','multiple':True,'minimum':2,'maximum':8},
                {'key':'process_indices','label':'Process variables (optional):','multiple':True,'minimum':0,'maximum':3},
                {'key':'block_index','label':'Block column (optional):','multiple':True,'minimum':0,'maximum':1,'kinds':('number','text')},
                {'key':'covariate_indices','label':'Covariates (optional):','multiple':True,'minimum':0,'maximum':4}),
            fields=(
                {'key':'model','label':'Component model:','choices':['Linear','Quadratic','Special cubic'],'default':'Quadratic'},
                {'key':'process_order','label':'Process model order:','choices':['Linear','Quadratic'],'default':'Linear'},
                {'key':'total','label':'Total mixture amount:','numeric':True,'default':1},
                {'key':'confidence','label':'Confidence level (%):','numeric':True,'default':95},
                {'key':'show_graphs','label':'','boolean':True,'text':'Display residual plots','default':True},
                {'key':'title','label':'Title:','optional':True}),
            note='Select component amounts and at least one process variable, block or covariate. The component model is crossed with the process polynomial. Blocks and covariates enter additively.')
        self.resize(940,760);self._process_ranges={};self._syncing=False
        self.custom_coding=QCheckBox('Specify low/high coding values for process variables')
        self.coding_table=QTableWidget(0,3);self.coding_table.setHorizontalHeaderLabels(['Process variable','Low','High'])
        self.coding_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in (1,2):self.coding_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.coding_table.setMinimumHeight(100);self.coding_table.setMaximumHeight(150)
        layout=self.layout();at=layout.indexOf(self.error);layout.insertWidget(at,self.custom_coding);layout.insertWidget(at+1,self.coding_table)
        self.coding_table.itemChanged.connect(self._remember_range)
        self.custom_coding.toggled.connect(self.coding_table.setVisible)
        self.coding_table.hide();self.controls['process_indices'].textChanged.connect(self._sync_process)
        known=_verified_factors(worksheet,'statcraft-special-design-v1',_MIXTURE_DESIGNS)
        if known:
            indices,metadata=known
            if 2<=len(indices)<=8 and all(worksheet.columns[i].kind=='number' for i in indices):
                self.controls['component_indices'].setText(format_variable_list(indices,worksheet))
                value=metadata.get('options',{}).get('total',1)
                if type(value) in (int,float) and math.isfinite(value) and value>0:self.controls['total'].setText(str(value))
        self._sync_process()

    def _remember_range(self,item):
        if self._syncing or item.column() not in (1,2):return
        label=self.coding_table.item(item.row(),0)
        if label is None:return
        index=label.data(Qt.ItemDataRole.UserRole)
        self._process_ranges[index]=[self.coding_table.item(item.row(),column).text() for column in (1,2)]

    def _sync_process(self,*args):
        try:indices=resolve_variables(self.controls['process_indices'].text(),self.worksheet)
        except ValueError:return
        self._syncing=True
        try:
            self.coding_table.setRowCount(len(indices))
            for row,index in enumerate(indices):
                label=QTableWidgetItem(format_variable_reference(index,self.worksheet));label.setData(Qt.ItemDataRole.UserRole,index)
                label.setFlags(label.flags()&~Qt.ItemFlag.ItemIsEditable);self.coding_table.setItem(row,0,label)
                if index not in self._process_ranges:
                    values=[v for v in self.worksheet.columns[index].values if type(v) in (int,float) and math.isfinite(v)]
                    self._process_ranges[index]=[str(min(values)),str(max(values))] if values else ['','']
                for column,value in enumerate(self._process_ranges[index],1):self.coding_table.setItem(row,column,QTableWidgetItem(value))
        finally:self._syncing=False
        self.controls['process_order'].setEnabled(bool(indices));self.custom_coding.setEnabled(bool(indices))

    def values(self):
        for key,maximum,kinds,label in [('process_indices',3,('number',),'process variables'),('block_index',1,('number','text'),'block column'),('covariate_indices',4,('number',),'covariates')]:
            if len(resolve_variables(self.controls[key].text(),self.worksheet,kinds))>maximum:raise ValueError('Select at most '+str(maximum)+' '+label+'.')
        values=super().values();block=values['block_index'][0] if values['block_index'] else None
        processes=values['process_indices'];covariates=values['covariate_indices']
        if not processes and block is None and not covariates:raise ValueError('Select a process variable, block or covariate, or use Analyze Mixture Design for components only.')
        refs=[values['response_index']]+values['component_indices']+processes+covariates+([] if block is None else [block])
        if len(set(refs))!=len(refs):raise ValueError('Choose separate columns for response, components, process variables, blocks and covariates.')
        if values['total']<=0:raise ValueError('Total mixture amount must be positive.')
        if not 0<values['confidence']<100:raise ValueError('Confidence level must be between 0 and 100.')
        if values['model']=='Special cubic' and len(values['component_indices'])<3:raise ValueError('Special cubic requires at least three mixture components.')
        self._sync_process();coding=None
        if processes and self.custom_coding.isChecked():
            coding=[]
            for row in range(len(processes)):
                low=_finite(self.coding_table.item(row,1).text(),'Process low');high=_finite(self.coding_table.item(row,2).text(),'Process high')
                if low>=high:raise ValueError('Each process coding low must be less than its high.')
                coding.append({'low':low,'high':high})
        bounds=None;known=_verified_factors(self.worksheet,'statcraft-special-design-v1',_MIXTURE_DESIGNS)
        if known and known[0]==values['component_indices'] and values['total']==known[1].get('options',{}).get('total',1):
            candidate=[]
            for descriptor in known[1]['factors']:
                low=descriptor.get('low');high=descriptor.get('high')
                if type(low) not in (int,float) or type(high) not in (int,float) or not math.isfinite(low) or not math.isfinite(high) or not 0<=low<high<=values['total']:break
                candidate.append({'low':float(low),'high':float(high)})
            if len(candidate)==len(values['component_indices']):bounds=candidate
        return {'response_index':values['response_index'],'component_indices':values['component_indices'],'process_indices':processes,
                'block_index':block,'covariate_indices':covariates,'model':{'Linear':'linear','Quadratic':'quadratic','Special cubic':'special_cubic'}[values['model']],
                'total':values['total'],'options':{'confidence':values['confidence']/100,'show_graphs':values['show_graphs'],
                    'title':values['title'] or '','bounds':bounds,'process_order':2 if processes and values['process_order']=='Quadratic' else 1,
                    'process_coding':coding,'covariate_coding':None}}

    def validate(self):
        self.parameters=None
        super().validate()


class MixtureProcessPredictionDialog(QDialog):
    def __init__(self,worksheet,entries,parent=None):
        super().__init__(parent);self.setWindowTitle('Predict Mixture and Process Response');self.resize(940,480)
        self.worksheet=worksheet;self.entries=list(entries);self.parameters=None;self._roles=[]
        layout=QVBoxLayout(self);form=QFormLayout();self.model=QComboBox()
        for entry in self.entries:self.model.addItem(entry['title']+' — '+entry.get('time',''))
        if self.entries:self.model.setCurrentIndex(len(self.entries)-1)
        self.confidence=QLineEdit('95');self.row_count=QSpinBox();self.row_count.setRange(1,100)
        form.addRow('Fitted mixture/process model:',self.model);form.addRow('Confidence level (%):',self.confidence);form.addRow('Prediction rows:',self.row_count);layout.addLayout(form)
        self.note=QLabel();self.note.setWordWrap(True);layout.addWidget(self.note)
        self.table=QTableWidget(1,0);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table)
        self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.row_count.valueChanged.connect(self._rows_changed);self.model.currentIndexChanged.connect(self._model_changed);self._model_changed()

    def _selected(self):
        if not self.entries:raise ValueError('Analyze a mixture/process model before predicting.')
        index=self.model.currentIndex()
        if not 0<=index<len(self.entries):raise ValueError('Select a fitted mixture/process model.')
        entry=self.entries[index]
        if entry.get('source_unavailable'):raise ValueError('A source column was deleted. Undo the deletion or fit a new model.')
        if entry.get('recipe',{}).get('action')!='analyze_mixture_process':raise ValueError('Select a fitted mixture/process model.')
        params=entry['recipe']['parameters'];refs=[params['response_index']]+list(params['component_indices'])+list(params.get('process_indices') or [])+list(params.get('covariate_indices') or [])
        if params.get('block_index') is not None:refs.append(params['block_index'])
        if any(type(i) is not int or not 0<=i<len(self.worksheet.columns) for i in refs):raise ValueError('A fitted-model source column is unavailable.')
        return entry

    def _model_changed(self,*args):
        self.table.clear();self._roles=[];self.table.setColumnCount(0)
        if not self.entries:self.note.setText('Analyze a mixture/process model before predicting.');return
        try:
            entry=self._selected();params=entry['recipe']['parameters'];labels=[]
            for role,key in [('component','component_indices'),('process','process_indices'),('covariate','covariate_indices')]:
                for index in params.get(key) or []:
                    self._roles.append((role,index));labels.append(role.title()+' '+format_variable_reference(index,self.worksheet))
            if params.get('block_index') is not None:
                self._roles.append(('block',params['block_index']));labels.append('Block '+format_variable_reference(params['block_index'],self.worksheet))
            self.table.setColumnCount(len(labels));self.table.setHorizontalHeaderLabels(labels)
            for column,label in enumerate(labels):self.table.horizontalHeaderItem(column).setToolTip(label)
            self.note.setText(f"Enter component amounts summing to {params['total']:g} and values for each displayed role. Predictions refit current worksheet data with the saved coding and bounds.")
            self._rows_changed()
        except (ValueError,TypeError,KeyError,IndexError) as error:self.error.setText(str(error))

    def _rows_changed(self,*args):
        self.table.setRowCount(self.row_count.value())
        if not self.entries:return
        try:entry=self._selected()
        except (ValueError,TypeError,KeyError,IndexError):return
        for column,(role,index) in enumerate(self._roles):
            if role!='block':continue
            levels=entry['result'].get('block_levels',[]);reference=entry['result'].get('block_reference')
            for row in range(self.table.rowCount()):
                if self.table.cellWidget(row,column) is None:
                    combo=QComboBox()
                    for level in levels:combo.addItem(str(level),level)
                    if reference in levels:combo.setCurrentIndex(levels.index(reference))
                    self.table.setCellWidget(row,column,combo)

    def values(self):
        entry=self._selected();confidence=_finite(self.confidence.text(),'Confidence level')/100
        if not 0<confidence<1:raise ValueError('Confidence level must be between 0 and 100.')
        groups={'component':[],'process':[],'covariate':[]};blocks=[]
        for row in range(self.table.rowCount()):
            current={key:[] for key in groups}
            for column,(role,index) in enumerate(self._roles):
                if role=='block':
                    combo=self.table.cellWidget(row,column)
                    if combo is None or combo.currentIndex()<0:raise ValueError('Select a known block level for row '+str(row+1)+'.')
                    blocks.append(combo.currentData())
                else:
                    item=self.table.item(row,column)
                    current[role].append(_finite(item.text() if item else None,'Row '+str(row+1)+', '+format_variable_reference(index,self.worksheet)))
            for key in groups:groups[key].append(current[key])
        processes=groups['process'] if any(role=='process' for role,index in self._roles) else None
        covariates=groups['covariate'] if any(role=='covariate' for role,index in self._roles) else None
        block_values=blocks if any(role=='block' for role,index in self._roles) else None
        from .mixture_process_model import predict
        predict(entry['result'],groups['component'],processes,covariates,block_values,confidence)
        return {'model_recipe':copy.deepcopy(entry['recipe']),'component_rows':groups['component'],'process_rows':processes,
                'covariate_rows':covariates,'block_values':block_values,'confidence':confidence}

    def validate(self):
        self.parameters=None
        try:self.parameters=self.values()
        except (ValueError,TypeError,KeyError,IndexError,OverflowError) as error:self.error.setText(str(error));return
        self.error.clear();self.accept()
