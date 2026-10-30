"""Original fitted-mixture contour and constrained response optimizer forms.

Authenticated RT_DIALOG4375/4376/4388/2927 guides labels and roles. These forms
use raw amounts and one fitted response; native runtime/layout parity is not
claimed. Model-position ordinals stay separate from worksheet column indices.
"""
import copy
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,
    QSpinBox,QTableWidget,QTableWidgetItem,QHeaderView,QLabel,QDialogButtonBox,QCheckBox)
from .variable_dialogs import format_variable_reference


def _finite(raw,label):
    try:value=float(raw)
    except (ValueError,TypeError,OverflowError) as error:raise ValueError(label+' must be a finite number.') from error
    if not math.isfinite(value):raise ValueError(label+' must be a finite number.')
    return value


class _MixtureModelDialog(QDialog):
    def __init__(self,worksheet,entries,parent,title):
        super().__init__(parent);self.setWindowTitle(title);self.resize(770,650)
        self.worksheet=worksheet;self.entries=list(entries);self.parameters=None
        self.outer=QVBoxLayout(self);self.form=QFormLayout();self.model=QComboBox()
        for entry in self.entries:self.model.addItem(entry['title']+' — '+entry.get('time',''))
        if self.entries:self.model.setCurrentIndex(len(self.entries)-1)
        self.form.addRow('Fitted mixture model:',self.model);self.outer.addLayout(self.form)
        self.note=QLabel();self.note.setWordWrap(True);self.outer.addWidget(self.note)
        self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate);self.buttons.rejected.connect(self.reject)

    def _finish(self):
        self.outer.addWidget(self.error);self.outer.addWidget(self.buttons)
        self.model.currentIndexChanged.connect(self._model_changed);self._model_changed()

    def _selected(self):
        if not self.entries:raise ValueError('Analyze a mixture design before using this command.')
        index=self.model.currentIndex()
        if not 0<=index<len(self.entries):raise ValueError('Select a fitted mixture model.')
        entry=self.entries[index]
        if entry.get('source_unavailable'):raise ValueError('A model source column was deleted. Undo the deletion or fit a new model.')
        if entry.get('recipe',{}).get('action')!='analyze_mixture':raise ValueError('Select a fitted mixture model.')
        indices=entry['recipe']['parameters']['component_indices']
        if any(type(i) is not int or not 0<=i<len(self.worksheet.columns) for i in indices):raise ValueError('Select a model with existing component columns.')
        return entry

    def _labels(self,entry):
        return [format_variable_reference(i,self.worksheet) for i in entry['recipe']['parameters']['component_indices']]

    def validate(self):
        self.parameters=None
        try:self.parameters=self.values()
        except (ValueError,TypeError,KeyError,IndexError,OverflowError) as error:self.error.setText(str(error));return
        self.error.clear();self.accept()


class MixtureContourDialog(_MixtureModelDialog):
    def __init__(self,worksheet,entries,parent=None):
        super().__init__(worksheet,entries,parent,'Mixture Contour Plot')
        self.axes=[]
        for name in ('X-axis component:','Y-axis component:','Z-axis component:'):
            combo=QComboBox();self.axes.append(combo);self.form.addRow(name,combo)
            combo.currentIndexChanged.connect(self._axes_changed)
        self.resolution=QSpinBox();self.resolution.setRange(8,80);self.resolution.setValue(32)
        self.levels=QSpinBox();self.levels.setRange(2,20);self.levels.setValue(8)
        self.title=QLineEdit();self.form.addRow('Contour levels:',self.levels);self.form.addRow('Grid resolution:',self.resolution);self.form.addRow('Title:',self.title)
        self.outer.addWidget(QLabel('Hold other components at these amounts:'))
        self.hold_table=QTableWidget(0,2);self.hold_table.setHorizontalHeaderLabels(['Component','Amount'])
        self.hold_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.hold_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.outer.addWidget(self.hold_table);self._holds={};self._changing=False
        self._finish()

    def _model_changed(self,*args):
        self._changing=True
        try:
            self._holds={};self.hold_table.setRowCount(0)
            for combo in self.axes:combo.clear()
            if not self.entries:self.note.setText('Analyze a mixture design before creating a contour plot.');return
            entry=self._selected();labels=self._labels(entry);bounds=entry['result']['component_bounds']
            for combo in self.axes:combo.addItems(labels)
            for position,combo in enumerate(self.axes):combo.setCurrentIndex(position if position<len(labels) else -1)
            self.hold_table.setRowCount(len(labels))
            for row,(label,bound) in enumerate(zip(labels,bounds)):
                self._holds[row]=str(bound['low']);item=QTableWidgetItem(label);item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable)
                self.hold_table.setItem(row,0,item);self.hold_table.setItem(row,1,QTableWidgetItem(self._holds[row]))
            self.note.setText(f"Select three components for a ternary slice. All amounts sum to {entry['result']['total']:g}; the remaining components are held fixed. The saved component bounds restrict the plotted region.")
        except (ValueError,TypeError,KeyError,IndexError) as error:self.error.setText(str(error))
        finally:self._changing=False
        self._axes_changed()

    def _axes_changed(self,*args):
        if self._changing:return
        displayed={combo.currentIndex() for combo in self.axes}
        for row in range(self.hold_table.rowCount()):
            item=self.hold_table.item(row,1)
            if item is None:continue
            if item.flags()&Qt.ItemFlag.ItemIsEditable:self._holds[row]=item.text()
            if row in displayed:
                item.setText('Varies');item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable)
            else:
                item.setFlags(item.flags()|Qt.ItemFlag.ItemIsEditable);item.setText(self._holds.get(row,''))

    def values(self):
        entry=self._selected();positions=[combo.currentIndex() for combo in self.axes]
        if any(position<0 for position in positions) or len(set(positions))!=3:raise ValueError('Select three distinct component axes. At least three fitted components are required.')
        holds=[]
        for row in range(self.hold_table.rowCount()):
            if row not in positions:
                holds.append({'position':row,'value':_finite(self.hold_table.item(row,1).text(),'Held component amount')})
        options={'resolution':self.resolution.value(),'levels':self.levels.value(),'title':self.title.text().strip()}
        from .mixture_exploration import contour
        contour(entry['result'],positions,holds,options)
        return {'model_recipe':copy.deepcopy(entry['recipe']),'component_positions':positions,'hold_values':holds,'options':options}


class MixtureOptimizerDialog(_MixtureModelDialog):
    def __init__(self,worksheet,entries,parent=None):
        super().__init__(worksheet,entries,parent,'Mixture Response Optimizer')
        self.goal=QComboBox();self.goal.addItems(['Maximize','Minimize','Target'])
        self.target=QLineEdit();self.confidence=QLineEdit('95');self.title=QLineEdit()
        self.form.addRow('Goal:',self.goal);self.form.addRow('Target response:',self.target)
        self.form.addRow('Confidence level (%):',self.confidence)
        self.starts=QSpinBox();self.starts.setRange(1,64);self.starts.setValue(16)
        self.max_iterations=QSpinBox();self.max_iterations.setRange(10,2000);self.max_iterations.setValue(300)
        self.use_start_values=QCheckBox('Use these starting component amounts')
        self.form.addRow('Search starts:',self.starts);self.form.addRow('Maximum iterations:',self.max_iterations)
        self.form.addRow('',self.use_start_values);self.form.addRow('Title:',self.title)
        self.goal.currentIndexChanged.connect(self._goal_changed);self._goal_changed()
        self.outer.addWidget(QLabel('Component limits (amounts; may tighten the fitted region):'))
        self.bounds_table=QTableWidget(0,4);self.bounds_table.setHorizontalHeaderLabels(['Component','Lower','Upper','Start'])
        self.bounds_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in (1,2,3):self.bounds_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.outer.addWidget(self.bounds_table);self.use_start_values.toggled.connect(self._start_changed);self._finish()

    def _goal_changed(self,*args):self.target.setEnabled(self.goal.currentIndex()==2)

    def _start_changed(self,*args):
        enabled=self.use_start_values.isChecked()
        for row in range(self.bounds_table.rowCount()):
            item=self.bounds_table.item(row,3)
            if item is not None:item.setFlags((Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsEditable) if enabled else Qt.ItemFlag.ItemIsSelectable)

    def _model_changed(self,*args):
        self.bounds_table.setRowCount(0)
        if not self.entries:self.note.setText('Analyze a mixture design before optimizing its response.');return
        try:
            entry=self._selected();labels=self._labels(entry);bounds=entry['result']['component_bounds']
            self.bounds_table.setRowCount(len(labels))
            for row,(label,bound) in enumerate(zip(labels,bounds)):
                item=QTableWidgetItem(label);item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable);self.bounds_table.setItem(row,0,item)
                for column,key in ((1,'low'),(2,'high')):self.bounds_table.setItem(row,column,QTableWidgetItem(str(bound[key])))
                self.bounds_table.setItem(row,3,QTableWidgetItem(''))
            self._start_changed()
            self.note.setText(f"Optimize one fitted response with component amounts summing to {entry['result']['total']:g}. Bounds may be tightened or components fixed. Nonlinear results are a bounded numerical search, not a guaranteed global optimum.")
        except (ValueError,TypeError,KeyError,IndexError) as error:self.error.setText(str(error))

    def values(self):
        entry=self._selected();confidence=_finite(self.confidence.text(),'Confidence level')
        if not 0<confidence<100:raise ValueError('Confidence level must be between 0 and 100.')
        bounds=[];original=entry['result']['component_bounds'];total=entry['result']['total']
        for row,saved in enumerate(original):
            low=_finite(self.bounds_table.item(row,1).text(),'Lower bound');high=_finite(self.bounds_table.item(row,2).text(),'Upper bound')
            if low<saved['low'] or high>saved['high'] or low>high:raise ValueError('Limits must satisfy fitted lower <= lower <= upper <= fitted upper.')
            bounds.append({'low':low,'high':high})
        if math.fsum(item['low']/total for item in bounds)>1+1e-12 or math.fsum(item['high']/total for item in bounds)<1-1e-12:raise ValueError('Component bounds must contain a feasible blend with the fixed mixture total.')
        goal=('maximize','minimize','target')[self.goal.currentIndex()]
        target=_finite(self.target.text(),'Target response') if goal=='target' else None
        start_values=None
        if self.use_start_values.isChecked():
            start_values=[_finite(self.bounds_table.item(row,3).text(),'Starting amount') for row in range(len(bounds))]
            if abs(math.fsum(value/total for value in start_values)-1)>1e-10 or any(not bound['low']/total-1e-12<=value/total<=bound['high']/total+1e-12 for value,bound in zip(start_values,bounds)):
                raise ValueError('Starting amounts must satisfy the fixed total and optimizer bounds.')
        return {'model_recipe':copy.deepcopy(entry['recipe']),'goal':goal,'target':target,'bounds':bounds,
                'options':{'confidence':confidence/100,'title':self.title.text().strip(),'starts':self.starts.value(),
                           'max_iterations':self.max_iterations.value(),'start_values':start_values}}
