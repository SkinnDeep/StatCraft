"""Named-variable controls for joint composition and process optimization."""
import copy
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLabel,QComboBox,QLineEdit,QSpinBox,QDoubleSpinBox,QCheckBox,QTableWidget,QTableWidgetItem,QHeaderView,QDialogButtonBox
from .variable_dialogs import format_variable_reference
from .mixture_exploration_dialogs import _finite
from .mixture_condition import _validated,_values
from .mixture_joint_optimizer import _region
from .mixture_exploration import _project,_vertices


class MixtureJointOptimizerDialog(QDialog):
    def __init__(self,worksheet,entries,parent=None):
        super().__init__(parent);self.worksheet=worksheet;self.entries=list(entries);self.parameters=None;self.setWindowTitle('Joint Mixture and Process Response Optimizer');self.resize(900,850)
        self.outer=QVBoxLayout(self);form=QFormLayout();self.model=QComboBox()
        for entry in self.entries:self.model.addItem(entry['title']+' — '+entry.get('time',''))
        if self.entries:self.model.setCurrentIndex(len(self.entries)-1)
        form.addRow('Fitted mixture/process model:',self.model);self.goal=QComboBox();self.goal.addItems(['Maximize','Minimize','Target']);self.target=QLineEdit();self.target.setEnabled(False);self.goal.currentIndexChanged.connect(lambda i:self.target.setEnabled(i==2));form.addRow('Goal:',self.goal);form.addRow('Target:',self.target);self.outer.addLayout(form)
        self.note=QLabel('Components maintain the fitted total. Processes are searched jointly within observed worksheet-unit bounds. Covariates and the selected block stay fixed.');self.note.setWordWrap(True);self.outer.addWidget(self.note)
        self.component_table=self._table('Components — amount bounds and starting values:');self.process_table=self._table('Processes — worksheet-unit bounds and starting values:')
        self.outer.addWidget(QLabel('Hold covariates and block:'));self.hold_table=QTableWidget(0,2);self.hold_table.setHorizontalHeaderLabels(['Variable','Held value']);self.hold_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);self.hold_table.setMaximumHeight(140);self.outer.addWidget(self.hold_table)
        self.use_start_values=QCheckBox('Use starting values from the tables');self.outer.addWidget(self.use_start_values)
        options=QFormLayout();self.starts=QSpinBox();self.starts.setRange(1,64);self.starts.setValue(20);self.max_iterations=QSpinBox();self.max_iterations.setRange(10,2000);self.max_iterations.setValue(300);self.confidence=QDoubleSpinBox();self.confidence.setRange(1.,99.99);self.confidence.setValue(95.);self.title=QLineEdit();options.addRow('Search starts:',self.starts);options.addRow('Maximum iterations:',self.max_iterations);options.addRow('Confidence level (%):',self.confidence);options.addRow('Title:',self.title);self.outer.addLayout(options)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setObjectName('error');self.outer.addWidget(self.error);self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);self.buttons.accepted.connect(self.validate);self.buttons.rejected.connect(self.reject);self.outer.addWidget(self.buttons)
        self.model.currentIndexChanged.connect(self._model_changed);self._model_changed()
    def _table(self,label):
        self.outer.addWidget(QLabel(label));table=QTableWidget(0,4);table.setHorizontalHeaderLabels(['Variable','Lower','Upper','Start']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for i in (1,2,3):table.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        table.setMinimumHeight(120);table.setMaximumHeight(220);self.outer.addWidget(table);return table
    def _selected(self):
        if not self.entries or not 0<=self.model.currentIndex()<len(self.entries):raise ValueError('Analyze a mixture model with continuous processes before using this command.')
        e=self.entries[self.model.currentIndex()];recipe=e.get('recipe',{})
        if e.get('source_unavailable') or recipe.get('action')!='analyze_mixture_process' or not recipe['parameters'].get('process_indices'):raise ValueError('Select an available fitted mixture model with continuous process variables.')
        from .recipes import columns
        if any(i>=len(self.worksheet.columns) for i in columns(recipe)):raise ValueError('A fitted model source column is unavailable.')
        return e
    def _model_changed(self,*unused):
        self.component_table.setRowCount(0);self.process_table.setRowCount(0);self.hold_table.setRowCount(0);self._holds=[]
        try:
            e=self._selected();r,saved,total,cn,pn,vn,bounds,pc,vc,pr,vr,levels,*tail=_validated(e['result']);params=e['recipe']['parameters']
            center=_project([(b['low']+b['high'])/(2*total) for b in bounds],[(b['low']/total,b['high']/total) for b in bounds])*total
            for table,indices,ranges,starts in ((self.component_table,params['component_indices'],bounds,center),(self.process_table,params['process_indices'],pr,[(b['low']+b['high'])/2 for b in pr])):
                table.setRowCount(len(indices))
                for row,(index,pair,start) in enumerate(zip(indices,ranges,starts)):
                    item=QTableWidgetItem(format_variable_reference(index,self.worksheet));item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable);table.setItem(row,0,item)
                    for col,value in ((1,pair['low']),(2,pair['high']),(3,start)):table.setItem(row,col,QTableWidgetItem(format(value,'.15g')))
            for index,code in zip(params.get('covariate_indices') or [],vc):self._holds.append(('covariate',index,(code['low']+code['high'])/2))
            if params.get('block_index') is not None:self._holds.append(('block',params['block_index'],saved['block_reference']))
            self.hold_table.setRowCount(len(self._holds))
            for row,(kind,index,value) in enumerate(self._holds):
                item=QTableWidgetItem(format_variable_reference(index,self.worksheet));item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable);self.hold_table.setItem(row,0,item)
                if kind=='block':
                    combo=QComboBox()
                    for level in levels:combo.addItem(str(level),level)
                    combo.setCurrentIndex(levels.index(value));self.hold_table.setCellWidget(row,1,combo)
                else:self.hold_table.setItem(row,1,QTableWidgetItem(format(value,'.15g')))
            self.note.setText('Fixed mixture total: '+format(total,'.12g')+'. Components and processes are optimized jointly; bounds and starts use worksheet units. Covariates and block remain fixed.');self.error.clear()
        except (ValueError,TypeError,KeyError,IndexError) as error:self.error.setText(str(error))
    def values(self):
        e=self._selected();r,saved,total,cn,pn,vn,bounds,pc,vc,pr,vr,levels,*tail=_validated(e['result'])
        def read(table):
            pairs=[];starts=[]
            for row in range(table.rowCount()):
                pairs.append({'low':_finite(table.item(row,1).text(),'Lower bound'),'high':_finite(table.item(row,2).text(),'Upper bound')});starts.append(_finite(table.item(row,3).text(),'Starting value'))
            return pairs,starts
        component_bounds,components=read(self.component_table);process_bounds,processes=read(self.process_table)
        region=_region(component_bounds,bounds,total,'component');_region(process_bounds,pr,1.,'process')
        if not _vertices(region):raise ValueError('Component bounds contain no fixed-total mixture.')
        covariates=[];block=None
        for row,(kind,index,unused) in enumerate(self._holds):
            if kind=='block':block=self.hold_table.cellWidget(row,1).currentData()
            else:covariates.append(_finite(self.hold_table.item(row,1).text(),'Held covariate'))
        _values(covariates or None,vn,vc,'covariate')
        if levels and block not in levels:raise ValueError('Choose a known block.')
        options={'starts':self.starts.value(),'max_iterations':self.max_iterations.value(),'confidence':self.confidence.value()/100,'title':self.title.text().strip(),'start_components':components if self.use_start_values.isChecked() else None,'start_processes':processes if self.use_start_values.isChecked() else None}
        if self.use_start_values.isChecked():
            if abs(math.fsum(components)-total)>1e-9*max(1.,total) or any(not p['low']<=v<=p['high'] for v,p in zip(components,component_bounds)):raise ValueError('Starting component amounts must satisfy total and bounds.')
            if any(not p['low']<=v<=p['high'] for v,p in zip(processes,process_bounds)):raise ValueError('Starting process values must satisfy bounds.')
        goal=('maximize','minimize','target')[self.goal.currentIndex()];target=_finite(self.target.text(),'Target') if goal=='target' else None
        return {'model_recipe':copy.deepcopy(e['recipe']),'goal':goal,'target':target,'component_bounds':component_bounds,'process_bounds':process_bounds,'covariate_values':covariates or None,'block_value':block,'options':options}
    def validate(self):
        self.parameters=None
        try:self.parameters=self.values()
        except (ValueError,TypeError,AttributeError,KeyError,IndexError) as error:self.error.setText(str(error));return
        self.error.clear();self.accept()
