"""Original multi-response mixture goals and shared-constraint dialog.

Native RT_DIALOG2925/2927/4388/4389 establish response selection, goals and
options. Dynamic native grids, defaults and execution remain unobserved.
"""
import copy
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QTableWidget,QTableWidgetItem,QComboBox,QPushButton,QHeaderView,QSpinBox,
    QLineEdit,QCheckBox,QDialogButtonBox,QScrollArea,QWidget)
from .variable_dialogs import format_variable_reference
from .mixture_exploration_dialogs import _finite


class MixtureMultiOptimizerDialog(QDialog):
    def __init__(self,worksheet,entries,parent=None):
        super().__init__(parent);self.setWindowTitle('Mixture Response Optimizer — Multiple Responses');self.resize(960,640);self.setMinimumSize(640,480);self.setSizeGripEnabled(True)
        self.worksheet=worksheet;self.entries=list(entries);self.parameters=None;self._changing=False
        root_layout=QVBoxLayout(self)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll_content=QWidget();scroll.setWidget(scroll_content)
        outer=QVBoxLayout(scroll_content)
        self.note=QLabel('Choose two to eight fitted responses with the same component columns, order and total. Weight changes each desirability curve; importance changes its contribution to the composite desirability.');self.note.setWordWrap(True);outer.addWidget(self.note)
        self.response_table=QTableWidget(0,7);self.response_table.setHorizontalHeaderLabels(['Fitted response','Goal','Lower','Target','Upper','Weight','Importance'])
        self.response_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for c in range(1,7):self.response_table.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeMode.ResizeToContents)
        self.response_table.setMinimumHeight(180);outer.addWidget(self.response_table)
        row=QHBoxLayout();self.add_button=QPushButton('Add Response');self.remove_button=QPushButton('Remove Response');row.addWidget(self.add_button);row.addWidget(self.remove_button);row.addStretch();outer.addLayout(row)
        self.add_button.clicked.connect(self.add_response);self.remove_button.clicked.connect(self.remove_response)
        form=QFormLayout();self.confidence=QLineEdit('95');self.starts=QSpinBox();self.starts.setRange(1,64);self.starts.setValue(16)
        self.max_iterations=QSpinBox();self.max_iterations.setRange(10,2000);self.max_iterations.setValue(300);self.title=QLineEdit()
        self.use_start_values=QCheckBox('Use these starting component amounts')
        form.addRow('Confidence level (%):',self.confidence);form.addRow('Search starts:',self.starts);form.addRow('Maximum iterations:',self.max_iterations);form.addRow('',self.use_start_values);form.addRow('Title:',self.title);outer.addLayout(form)
        outer.addWidget(QLabel('Shared component limits (intersection of the fitted regions; may be tightened):'))
        self.bounds_table=QTableWidget(0,4);self.bounds_table.setHorizontalHeaderLabels(['Component','Lower','Upper','Start'])
        self.bounds_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for c in (1,2,3):self.bounds_table.horizontalHeader().setSectionResizeMode(c,QHeaderView.ResizeMode.ResizeToContents)
        self.bounds_table.setMinimumHeight(140);outer.addWidget(self.bounds_table)
        self.use_start_values.toggled.connect(self._start_changed)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setObjectName('error');outer.addWidget(self.error)
        limitation=QLabel('The search balances fitted response means under the fixed mixture total. Nonlinear global optimality and native optimizer equivalence are unverified.');limitation.setWordWrap(True);outer.addWidget(limitation)
        root_layout.addWidget(scroll)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);self.buttons.accepted.connect(self.validate);self.buttons.rejected.connect(self.reject);root_layout.addWidget(self.buttons)
        # Prefer newest distinct response models while preserving a useful row order.
        chosen=[];seen=set()
        for index in reversed(range(len(self.entries))):
            recipe=self.entries[index].get('recipe',{});response=recipe.get('parameters',{}).get('response_index')
            if recipe.get('action')=='analyze_mixture' and response not in seen:
                chosen.append(index);seen.add(response)
                if len(chosen)==2:break
        chosen.reverse()
        for i in range(2):self.add_response(chosen[i] if i<len(chosen) else 0)
        self._rebuild_bounds()

    def _entry_label(self,entry):
        p=entry.get('recipe',{}).get('parameters',{});index=p.get('response_index')
        label=format_variable_reference(index,self.worksheet) if type(index) is int and 0<=index<len(self.worksheet.columns) else entry.get('title','Unavailable model')
        return label+' ('+str(p.get('model','model')).replace('_',' ')+') — '+entry.get('time','')

    def add_response(self,model_index=None):
        if self.response_table.rowCount()>=8:return
        # QPushButton.clicked supplies a bool; treat that as a request for a free model.
        if type(model_index) is not int:
            used={self.response_table.cellWidget(r,0).currentIndex() for r in range(self.response_table.rowCount())}
            model_index=next((i for i in reversed(range(len(self.entries))) if i not in used),0)
        row=self.response_table.rowCount();self.response_table.insertRow(row)
        model=QComboBox();model.setMinimumWidth(270)
        for e in self.entries:model.addItem(self._entry_label(e))
        if self.entries:model.setCurrentIndex(min(model_index,len(self.entries)-1))
        goal=QComboBox();goal.addItems(['Maximize','Minimize','Target'])
        self.response_table.setCellWidget(row,0,model);self.response_table.setCellWidget(row,1,goal)
        for c in range(2,7):self.response_table.setItem(row,c,QTableWidgetItem(''))
        model.currentIndexChanged.connect(lambda unused,m=model:self._response_changed(m))
        goal.currentIndexChanged.connect(lambda unused,g=goal:self._goal_changed(g))
        self._response_changed(model);self._buttons_changed()

    def remove_response(self):
        if self.response_table.rowCount()<=2:return
        row=self.response_table.currentRow()
        if row<0:row=self.response_table.rowCount()-1
        self.response_table.removeRow(row);self._buttons_changed();self._rebuild_bounds()

    def _buttons_changed(self):
        self.add_button.setEnabled(self.response_table.rowCount()<8);self.remove_button.setEnabled(self.response_table.rowCount()>2)

    def _row_of(self,widget,column):
        return next((r for r in range(self.response_table.rowCount()) if self.response_table.cellWidget(r,column) is widget),None)

    def _response_changed(self,model):
        row=self._row_of(model,0)
        if row is None:return
        index=model.currentIndex();lo=0.;hi=1.
        if 0<=index<len(self.entries):
            observed=self.entries[index].get('result',{}).get('observations',[])
            values=[float(v) for v in observed if type(v) in (int,float) and math.isfinite(v)]
            if values:
                lo=min(values);hi=max(values)
                if lo==hi:
                    pad=max(1.,abs(lo)*.1);lo-=pad;hi+=pad
        self.response_table.cellWidget(row,1).setProperty('default_low',lo)
        self.response_table.cellWidget(row,1).setProperty('default_high',hi)
        for c in (5,6):self.response_table.item(row,c).setText('1')
        self._goal_changed(self.response_table.cellWidget(row,1));self._rebuild_bounds()

    def _goal_changed(self,goal):
        row=self._row_of(goal,1)
        if row is None:return
        low=goal.property('default_low');high=goal.property('default_high')
        if low is None or high is None:low,high=0.,1.
        which=goal.currentIndex();target=high if which==0 else low if which==1 else low/2+high/2
        data={2:low,3:target,4:high};unused=4 if which==0 else 2 if which==1 else None
        for c,value in data.items():
            item=self.response_table.item(row,c)
            item.setFlags((Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable) if c==unused else (Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
            item.setText('' if c==unused else format(value,'.12g'))

    def _selected_entries(self):
        if not self.entries:raise ValueError('Fit at least two mixture responses before optimizing them together.')
        selected=[];signature=None;seen=set()
        for row in range(self.response_table.rowCount()):
            index=self.response_table.cellWidget(row,0).currentIndex()
            if not 0<=index<len(self.entries):raise ValueError('Select a fitted model for every response.')
            entry=self.entries[index];recipe=entry.get('recipe',{})
            if entry.get('source_unavailable'):raise ValueError('A selected model source column was deleted. Undo the deletion or fit a new model.')
            if recipe.get('action')!='analyze_mixture':raise ValueError('Select only fitted mixture models.')
            p=recipe['parameters'];components=p['component_indices'];response=p['response_index'];total=p['total']
            if not isinstance(components,list) or any(type(i) is not int or not 0<=i<len(self.worksheet.columns) for i in components+[response]):raise ValueError('Select models with existing source columns.')
            if response in seen:raise ValueError('Select a different physical response column for each response goal.')
            if signature is None:signature=(components,total)
            elif components!=signature[0] or not math.isclose(total,signature[1],rel_tol=1e-12,abs_tol=0):raise ValueError('Selected models must use the same component columns in the same order and the same total.')
            seen.add(response);selected.append(entry)
        if not 2<=len(selected)<=8:raise ValueError('Select two to eight fitted mixture responses.')
        return selected

    def _shared_bounds(self,entries):
        n=len(entries[0]['recipe']['parameters']['component_indices']);bounds=[]
        for i in range(n):
            low=max(e['result']['component_bounds'][i]['low'] for e in entries);high=min(e['result']['component_bounds'][i]['high'] for e in entries)
            if low>high:raise ValueError('Selected fitted component regions do not intersect.')
            bounds.append({'low':low,'high':high})
        total=entries[0]['recipe']['parameters']['total']
        if math.fsum(b['low']/total for b in bounds)>1+1e-12 or math.fsum(b['high']/total for b in bounds)<1-1e-12:raise ValueError('Selected fitted regions have no shared fixed-total mixture.')
        return bounds

    def _rebuild_bounds(self):
        if self._changing:return
        self._changing=True
        try:
            entries=self._selected_entries();bounds=self._shared_bounds(entries);indices=entries[0]['recipe']['parameters']['component_indices']
            self.bounds_table.setRowCount(len(bounds))
            for row,(index,bound) in enumerate(zip(indices,bounds)):
                item=QTableWidgetItem(format_variable_reference(index,self.worksheet));item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable);self.bounds_table.setItem(row,0,item)
                for column,key in ((1,'low'),(2,'high')):self.bounds_table.setItem(row,column,QTableWidgetItem(str(bound[key])))
                self.bounds_table.setItem(row,3,QTableWidgetItem(''))
            self._start_changed();self.error.clear()
        except (ValueError,TypeError,KeyError,IndexError,OverflowError) as error:
            self.bounds_table.setRowCount(0);self.error.setText(str(error))
        finally:self._changing=False

    def _start_changed(self,*args):
        enabled=self.use_start_values.isChecked()
        for row in range(self.bounds_table.rowCount()):
            item=self.bounds_table.item(row,3)
            if item is not None:item.setFlags((Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsEditable) if enabled else Qt.ItemFlag.ItemIsSelectable)

    def values(self):
        entries=self._selected_entries();original=self._shared_bounds(entries);total=entries[0]['recipe']['parameters']['total'];responses=[]
        for row,entry in enumerate(entries):
            goal=('maximize','minimize','target')[self.response_table.cellWidget(row,1).currentIndex()]
            number=lambda column:_finite(self.response_table.item(row,column).text(),'Response row '+str(row+1))
            lower=None if goal=='minimize' else number(2);target=number(3);upper=None if goal=='maximize' else number(4)
            weight=number(5);importance=number(6)
            if not .1<=weight<=10 or not .1<=importance<=10:raise ValueError('Weight and importance must be between 0.1 and 10.')
            if goal=='maximize' and not lower<target or goal=='minimize' and not target<upper or goal=='target' and not lower<target<upper:raise ValueError('Goals require lower < target for maximize, target < upper for minimize, or lower < target < upper for target.')
            responses.append({'model_recipe':copy.deepcopy(entry['recipe']),'goal':goal,'lower':lower,'target':target,'upper':upper,'weight':weight,'importance':importance})
        confidence=_finite(self.confidence.text(),'Confidence level')
        if not 0<confidence<100:raise ValueError('Confidence level must be between 0 and 100.')
        if self.bounds_table.rowCount()!=len(original):raise ValueError('Resolve the selected model region before entering limits.')
        bounds=[]
        for row,saved in enumerate(original):
            low=_finite(self.bounds_table.item(row,1).text(),'Lower bound');high=_finite(self.bounds_table.item(row,2).text(),'Upper bound')
            if low<saved['low'] or high>saved['high'] or low>high:raise ValueError('Limits must satisfy shared fitted lower <= lower <= upper <= shared fitted upper.')
            bounds.append({'low':low,'high':high})
        if math.fsum(b['low']/total for b in bounds)>1+1e-12 or math.fsum(b['high']/total for b in bounds)<1-1e-12:raise ValueError('Component bounds must contain a feasible blend with the fixed mixture total.')
        start_values=None
        if self.use_start_values.isChecked():
            start_values=[_finite(self.bounds_table.item(row,3).text(),'Starting amount') for row in range(len(bounds))]
            if abs(math.fsum(v/total for v in start_values)-1)>1e-10 or any(not b['low']/total-1e-12<=v/total<=b['high']/total+1e-12 for v,b in zip(start_values,bounds)):raise ValueError('Starting amounts must satisfy the fixed total and optimizer bounds.')
        return {'responses':responses,'bounds':bounds,'options':{'confidence':confidence/100,'starts':self.starts.value(),'max_iterations':self.max_iterations.value(),'start_values':start_values,'title':self.title.text().strip()}}

    def validate(self):
        self.parameters=None
        try:self.parameters=self.values()
        except (ValueError,TypeError,KeyError,IndexError,OverflowError) as error:self.error.setText(str(error));return
        self.error.clear();self.accept()
