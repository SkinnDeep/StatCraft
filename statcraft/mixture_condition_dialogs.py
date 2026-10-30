"""Conditional mixture contours and optimization with explicit holding settings.

Native process holds are coded; the reversible display mode converts to raw
worksheet values for saved recipes. Covariates are an authored actual-unit
extension. Retained static resources do not establish native runtime defaults.
"""
import copy
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget,QTableWidgetItem,QHeaderView,QLabel,QCheckBox,QComboBox
from .mixture_exploration_dialogs import MixtureContourDialog,MixtureOptimizerDialog,_finite
from .variable_dialogs import format_variable_reference


class _ConditionSettings:
    def _selected(self):
        if not self.entries:raise ValueError('Analyze a mixture/process model before using this command.')
        index=self.model.currentIndex()
        if not 0<=index<len(self.entries):raise ValueError('Select a fitted mixture/process model.')
        entry=self.entries[index]
        if entry.get('source_unavailable'):raise ValueError('A model source column was deleted. Undo the deletion or fit a new model.')
        recipe=entry.get('recipe',{})
        if recipe.get('action')!='analyze_mixture_process':raise ValueError('Select a fitted mixture/process model.')
        from .recipes import columns
        refs=columns(recipe)
        if any(i>=len(self.worksheet.columns) for i in refs):raise ValueError('Select a model with existing source columns.')
        return entry

    def _install_condition(self):
        self._condition_ready=True;self._condition_syncing=False;self._display_coded=True;self._condition_roles=[]
        self.coded_process=QCheckBox('Use coded process values');self.coded_process.setChecked(True)
        self.condition_note=QLabel('Process values use coded units (−1 = coding low, +1 = coding high). Covariates use worksheet units. The read-only preview shows the actual values saved in the recipe. All these settings remain fixed.')
        self.condition_note.setWordWrap(True)
        self.condition_table=QTableWidget(0,3)
        self.condition_table.setObjectName('fixedModelSettings')
        self.condition_table.setHorizontalHeaderLabels(['Variable','Value','Worksheet value'])
        self.condition_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in (1,2):self.condition_table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.condition_table.setMinimumHeight(100);self.condition_table.setMaximumHeight(170)
        self.outer.insertWidget(2,self.coded_process);self.outer.insertWidget(3,self.condition_note);self.outer.insertWidget(4,self.condition_table)
        self.condition_table.itemChanged.connect(self._update_condition_preview)
        self.coded_process.toggled.connect(self._units_changed)
        self.resize(950,810)
        self._populate_condition()

    def _model_changed(self,*args):
        super()._model_changed(*args)
        if getattr(self,'_condition_ready',False):self._populate_condition()

    def _populate_condition(self):
        self._condition_syncing=True
        try:
            self.condition_table.setRowCount(0);self._condition_roles=[];self.coded_process.setEnabled(False)
            entry=self._selected();params=entry['recipe']['parameters'];result=entry['result']
            for role,key,codes in [('process','process_indices',result['process_coding']),('covariate','covariate_indices',result['covariate_coding'])]:
                for index,code in zip(params.get(key) or [],codes):self._condition_roles.append((role,index,code))
            if params.get('block_index') is not None:self._condition_roles.append(('block',params['block_index'],None))
            self.condition_table.setRowCount(len(self._condition_roles))
            for row,(role,index,code) in enumerate(self._condition_roles):
                item=QTableWidgetItem(role.title()+' '+format_variable_reference(index,self.worksheet));item.setToolTip(item.text()+((' — Coding low: '+str(code['low'])+'; high: '+str(code['high'])) if role=='process' else ''));item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable);self.condition_table.setItem(row,0,item)
                preview=QTableWidgetItem('');preview.setFlags(preview.flags()&~Qt.ItemFlag.ItemIsEditable);self.condition_table.setItem(row,2,preview)
                if role=='block':
                    combo=QComboBox()
                    levels=result['block_levels']
                    for level in levels:combo.addItem(str(level),level)
                    if result['block_reference'] in levels:combo.setCurrentIndex(levels.index(result['block_reference']))
                    combo.currentIndexChanged.connect(self._update_condition_preview);self.condition_table.setCellWidget(row,1,combo)
                else:
                    midpoint=code['low']/2+code['high']/2
                    value=0. if role=='process' and self.coded_process.isChecked() else midpoint
                    self.condition_table.setItem(row,1,QTableWidgetItem(format(value,'.15g')))
            self._display_coded=self.coded_process.isChecked()
            self.coded_process.setEnabled(any(role=='process' for role,index,code in self._condition_roles))
            self.note.setText(self.note.text()+' Process, covariate and block settings below are held fixed; they are not optimized.')
        except (ValueError,TypeError,KeyError,IndexError) as error:self.error.setText(str(error))
        finally:self._condition_syncing=False
        self._update_condition_preview()

    def _actual(self,role,code,value,coded):
        if role=='process' and coded:
            center=code['low']/2+code['high']/2;scale=code['high']/2-code['low']/2
            value=center+scale*value
            if not math.isfinite(value):raise ValueError('Converted process value exceeds the supported finite range.')
        return value

    def _units_changed(self,coded):
        if self._condition_syncing:return
        self._condition_syncing=True
        try:
            for row,(role,index,code) in enumerate(self._condition_roles):
                if role!='process':continue
                item=self.condition_table.item(row,1)
                try:
                    value=self._actual(role,code,_finite(item.text(),'Process value'),self._display_coded)
                    if coded:value=(value-(code['low']/2+code['high']/2))/(code['high']/2-code['low']/2)
                    if not math.isfinite(value):raise ValueError('Coded process value exceeds supported finite range.')
                    item.setText(format(value,'.15g'))
                except (ValueError,TypeError,OverflowError) as error:self.error.setText(str(error))
            self._display_coded=bool(coded)
            self.condition_note.setText(('Process values use coded units (−1 = coding low, +1 = coding high). ' if coded else 'Process values use worksheet units. ')+ 'Covariates use worksheet units. The read-only preview shows actual saved values. All these settings remain fixed.')
        finally:self._condition_syncing=False
        self._update_condition_preview()

    def _update_condition_preview(self,*args):
        if self._condition_syncing:return
        self._condition_syncing=True
        try:
            for row,(role,index,code) in enumerate(self._condition_roles):
                try:
                    if role=='block':
                        combo=self.condition_table.cellWidget(row,1);value=combo.currentData() if combo is not None and combo.currentIndex()>=0 else None
                        text=str(value) if value is not None else 'Select a block'
                    else:value=self._actual(role,code,_finite(self.condition_table.item(row,1).text(),'Setting'),self._display_coded);text=format(value,'.12g')
                except (ValueError,TypeError,OverflowError):text='Invalid value'
                self.condition_table.item(row,2).setText(text)
        finally:self._condition_syncing=False

    def _fixed_values(self):
        self._selected();process=[];covariates=[];block=None
        for row,(role,index,code) in enumerate(self._condition_roles):
            if role=='block':
                combo=self.condition_table.cellWidget(row,1)
                if combo is None or combo.currentIndex()<0:raise ValueError('Select a known block level.')
                block=combo.currentData()
            else:
                value=self._actual(role,code,_finite(self.condition_table.item(row,1).text(),format_variable_reference(index,self.worksheet)),self.coded_process.isChecked())
                (process if role=='process' else covariates).append(value)
        return {'process_values':process or None,'covariate_values':covariates or None,'block_value':block}


class MixtureProcessContourDialog(_ConditionSettings,MixtureContourDialog):
    def __init__(self,worksheet,entries,parent=None):
        self._condition_ready=False
        super().__init__(worksheet,entries,parent)
        self.setWindowTitle('Mixture Contour Plot — Fixed Process Settings');self._install_condition()

    def values(self):
        entry=self._selected();positions=[combo.currentIndex() for combo in self.axes]
        if any(position<0 for position in positions) or len(set(positions))!=3:raise ValueError('Select three distinct component axes. At least three fitted components are required.')
        holds=[]
        for row in range(self.hold_table.rowCount()):
            if row not in positions:holds.append({'position':row,'value':_finite(self.hold_table.item(row,1).text(),'Held component amount')})
        fixed=self._fixed_values();options={'resolution':self.resolution.value(),'levels':self.levels.value(),'title':self.title.text().strip()}
        from .mixture_condition import contour
        contour(entry['result'],**fixed,component_positions=positions,hold_values=holds,options=options)
        return {'model_recipe':copy.deepcopy(entry['recipe']),**fixed,'component_positions':positions,'hold_values':holds,'options':options}


class MixtureProcessOptimizerDialog(_ConditionSettings,MixtureOptimizerDialog):
    def __init__(self,worksheet,entries,parent=None):
        self._condition_ready=False
        super().__init__(worksheet,entries,parent)
        self.setWindowTitle('Mixture Response Optimizer — Fixed Process Settings');self._install_condition()

    def values(self):
        values=super().values();fixed=self._fixed_values()
        from .mixture_condition import condition
        condition(self._selected()['result'],**fixed)
        return dict(values,**fixed)
