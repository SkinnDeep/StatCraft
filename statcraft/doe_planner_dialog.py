"""Original goal-led DOE planning with an isolated, calculated worksheet preview."""
import copy
import math
import re
from .doe_catalog_designs import PB_RUNS,TAGUCHI_ARRAYS
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QWidget,
    QLabel,QLineEdit,QComboBox,QSpinBox,QCheckBox,QPushButton,QTableWidget,
    QTableWidgetItem,QHeaderView,QAbstractItemView,QSplitter,QTabWidget,QFileDialog)


FAMILIES=[
 ('full_factorial','Full factorial','effects'),('fractional_factorial','Fractional factorial','effects'),
 ('general_factorial','General factorial','effects'),('plackett_burman','Plackett–Burman','effects'),
 ('central_composite','Central composite','optimize'),('box_behnken','Box–Behnken','optimize'),
 ('taguchi','Taguchi orthogonal array','robust'),('simplex_centroid','Simplex centroid','mixture'),
 ('simplex_lattice','Simplex lattice','mixture'),('extreme_vertices','Constrained mixture vertices','mixture'),
 ('custom_optimal','Custom optimal','custom')]
_MIXTURE={'simplex_centroid','simplex_lattice','extreme_vertices'}
_CONTINUOUS={'full_factorial','fractional_factorial','central_composite','box_behnken'}


def _finite(text,label):
    try:value=float(text)
    except (ValueError,TypeError,OverflowError) as error:raise ValueError(label+' must be a finite number.') from error
    if not math.isfinite(value):raise ValueError(label+' must be a finite number.')
    return value


class DOEPlannerDialog(QDialog):
    def __init__(self,parent=None,export_callback=None):
        super().__init__(parent);self.setWindowTitle('Design of Experiments Planner');self.resize(1000,640);self.setMinimumSize(780,480);self.setSizeGripEnabled(True)
        self.parameters=None;self.preview_sheet=None;self.export_callback=export_callback;self._updating=False;self._family_state={};self._last_kind=None
        self.preview_timer=QTimer(self);self.preview_timer.setSingleShot(True);self.preview_timer.setInterval(300);self.preview_timer.timeout.connect(self.refresh_preview)
        layout=QVBoxLayout(self);top=QHBoxLayout();top.addWidget(QLabel('Goal:'))
        self.goal=QComboBox()
        for label,key in [('Compare factor effects','effects'),('Optimize a response','optimize'),('Improve robustness','robust'),('Blend ingredients','mixture'),('Choose a custom design','custom')]:self.goal.addItem(label,key)
        top.addWidget(self.goal,1);top.addWidget(QLabel('Design:'));self.family=QComboBox()
        for key,label,goal in FAMILIES:self.family.addItem(label,key)
        top.addWidget(self.family,2);layout.addLayout(top)
        splitter=QSplitter(Qt.Orientation.Vertical);config=QWidget();config_layout=QHBoxLayout(config)
        factor_pane=QWidget();factors_layout=QVBoxLayout(factor_pane);count_row=QHBoxLayout()
        count_row.addWidget(QLabel('Number of factors:'));self.factor_count=QSpinBox();self.factor_count.setRange(2,32);self.factor_count.setValue(3);count_row.addWidget(self.factor_count);count_row.addStretch();factors_layout.addLayout(count_row)
        self.factor_tabs=QTabWidget();self.factor_table=QTableWidget(0,5);self.factor_table.setHorizontalHeaderLabels(['Name','Type','Levels','Lower bound','Upper bound'])
        self.factor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.factor_tabs.addTab(self.factor_table,'Factors')
        constraints=QWidget();constraints_layout=QVBoxLayout(constraints);constraints_layout.addWidget(QLabel('Blank cells match any level. Each row excludes the matching factor combination.'))
        self.forbidden_table=QTableWidget(0,3);self.forbidden_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);constraints_layout.addWidget(self.forbidden_table)
        rules_buttons=QHBoxLayout();self.add_forbidden=QPushButton('Add combination');self.add_forbidden.setAutoDefault(False);self.remove_forbidden=QPushButton('Remove combination');self.remove_forbidden.setAutoDefault(False)
        self.add_forbidden.clicked.connect(self._add_forbidden);self.remove_forbidden.clicked.connect(self._remove_forbidden);rules_buttons.addWidget(self.add_forbidden);rules_buttons.addWidget(self.remove_forbidden);rules_buttons.addStretch();constraints_layout.addLayout(rules_buttons)
        self.factor_tabs.addTab(constraints,'Excluded combinations');factors_layout.addWidget(self.factor_tabs);config_layout.addWidget(factor_pane,3)
        settings=QWidget();form=QFormLayout(settings);self._option_rows={}
        self.name_edit=QLineEdit('DOE plan');form.addRow('Worksheet name:',self.name_edit)
        for attr,label,minimum,maximum,default in [('replicates','Replicates:',1,20,1),('centers','Center points per block:',0,20,0),('blocks','Blocks:',1,20,1),('seed','Random seed:',0,2147483647,1)]:
            control=QSpinBox();control.setRange(minimum,maximum);control.setValue(default);setattr(self,attr,control);form.addRow(label,control);control.valueChanged.connect(self.queue_preview)
        self.centers_label=form.labelForField(self.centers)
        self.randomize=QCheckBox('Randomize run order');self.randomize.setChecked(True);form.addRow('',self.randomize)
        self.generators=QLineEdit('C=AB');self.generators.setPlaceholderText('D=ABC; E=AB');self._row(form,'generators','Generators:',self.generators)
        self.alpha=QComboBox();self.alpha.setEditable(True);self.alpha.addItem('Rotatable','rotatable');self.alpha.addItem('Face-centered','face_centered');self._row(form,'alpha','Axial distance (alpha):',self.alpha)
        self.array=QComboBox()
        for key in ['auto']+list(TAGUCHI_ARRAYS):self.array.addItem('Automatic' if key=='auto' else key.replace('_4',' (4-level)').replace('_MIXED',' (mixed levels)'),key)
        self._row(form,'array','Orthogonal array:',self.array)
        self.pb_runs=QComboBox();self.pb_runs.addItem('Automatic',0)
        for count in PB_RUNS:self.pb_runs.addItem(str(count),count)
        self._row(form,'pb_runs','Base runs:',self.pb_runs)
        self.degree=QSpinBox();self.degree.setRange(1,8);self.degree.setValue(2);self._row(form,'degree','Lattice degree:',self.degree)
        self.total=QLineEdit('1');self._row(form,'total','Mixture total:',self.total)
        self.optimal_runs=QSpinBox();self.optimal_runs.setRange(2,256);self.optimal_runs.setValue(8);self.optimal_runs.setToolTip('Enter any whole-number run count from the model rank through 256, limited by the number of allowed candidate settings. Counts such as 17, 19 or 24 do not need to be powers of two.');self._row(form,'optimal_runs','Selected runs:',self.optimal_runs)
        self.criterion=QComboBox();self.criterion.addItems(['D','I']);self._row(form,'criterion','Optimality criterion:',self.criterion)
        self.model=QComboBox()
        for label,key in [('Main effects','main_effects'),('Two-factor interactions','interactions'),('Main effects and squares','quadratic'),('Full quadratic','full_quadratic')]:self.model.addItem(label,key)
        self._row(form,'model','Model:',self.model)
        config_layout.addWidget(settings,2);splitter.addWidget(config)
        preview=QWidget();preview_layout=QVBoxLayout(preview);self.summary=QLabel('Preparing design preview…');self.summary.setWordWrap(True);preview_layout.addWidget(self.summary)
        self.guidance=QLabel();self.guidance.setWordWrap(True);self.guidance.setObjectName('secondary');preview_layout.addWidget(self.guidance)
        self.preview_table=QTableWidget();self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents);preview_layout.addWidget(self.preview_table);splitter.addWidget(preview);splitter.setSizes([260,240]);layout.addWidget(splitter)
        self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QHBoxLayout();self.export_button=QPushButton('Export to Excel…');self.export_button.setAutoDefault(False);self.export_button.clicked.connect(self.export_excel);buttons.addWidget(self.export_button);buttons.addStretch()
        self.create_button=QPushButton('Create Worksheet');self.create_button.setDefault(True);self.create_button.clicked.connect(self.create);self.cancel_button=QPushButton('Cancel');self.cancel_button.setAutoDefault(False);self.cancel_button.clicked.connect(self.reject);buttons.addWidget(self.create_button);buttons.addWidget(self.cancel_button);layout.addLayout(buttons)
        self.factor_count.valueChanged.connect(self._factor_rows);self.factor_table.itemChanged.connect(self._factor_changed);self.forbidden_table.itemChanged.connect(self.queue_preview)
        self.goal.currentIndexChanged.connect(self._goal_changed);self.family.currentIndexChanged.connect(self._family_changed)
        for control in [self.name_edit,self.generators,self.total]:control.textChanged.connect(self.queue_preview)
        for control in [self.alpha,self.array,self.criterion,self.model,self.pb_runs]:control.currentTextChanged.connect(self.queue_preview)
        for control in [self.degree,self.optimal_runs]:control.valueChanged.connect(self.queue_preview)
        self.randomize.toggled.connect(self.queue_preview);self._factor_rows();self._family_changed()

    def _row(self,form,key,label,control):
        caption=QLabel(label);form.addRow(caption,control);self._option_rows[key]=(caption,control)

    def _factor_rows(self,*args):
        self._updating=True;old=self.factor_table.rowCount();count=self.factor_count.value();self.factor_table.setRowCount(count)
        for row in range(old,count):
            self.factor_table.setItem(row,0,QTableWidgetItem(chr(65+row) if row<26 else 'Factor'+str(row+1)))
            kind=QComboBox();kind.addItem('Numeric','number');kind.addItem('Text','text');kind.currentIndexChanged.connect(self.queue_preview);self.factor_table.setCellWidget(row,1,kind)
            for column,value in [(2,'-1, 1'),(3,'0'),(4,'1')]:self.factor_table.setItem(row,column,QTableWidgetItem(value))
        self._updating=False;self._sync_rules();self._family_changed()

    def _factor_changed(self,*args):
        if self._updating:return
        self._sync_rules();self.queue_preview()

    def _sync_rules(self):
        self.forbidden_table.setColumnCount(self.factor_table.rowCount())
        self.forbidden_table.setHorizontalHeaderLabels([self.factor_table.item(row,0).text() for row in range(self.factor_table.rowCount())])

    def _add_forbidden(self):
        self.forbidden_table.insertRow(self.forbidden_table.rowCount());self.queue_preview()

    def _remove_forbidden(self):
        row=self.forbidden_table.currentRow()
        if row>=0:self.forbidden_table.removeRow(row);self.queue_preview()

    def _goal_changed(self):
        category=self.goal.currentData()
        self.family.setCurrentIndex(next(i for i,item in enumerate(FAMILIES) if item[2]==category))

    def _family_changed(self,*args):
        kind=self.family.currentData();category=next(item[2] for item in FAMILIES if item[0]==kind)
        if kind!=self._last_kind:
            if self._last_kind is not None:self._family_state[self._last_kind]=(self.centers.value(),self.blocks.value())
            centers,blocks=self._family_state.get(kind,(1 if kind in ('central_composite','box_behnken') else 0,1))
            self.centers.setMinimum(1 if kind in ('central_composite','box_behnken') else 0);self.centers.setValue(centers)
            self.blocks.setEnabled(kind!='plackett_burman');self.blocks.setValue(1 if kind=='plackett_burman' else blocks);self._last_kind=kind
        self.goal.blockSignals(True);self.goal.setCurrentIndex(self.goal.findData(category));self.goal.blockSignals(False)
        self.factor_count.setMinimum(1 if kind=='custom_optimal' else 2)
        self.centers_label.setText('Center points per replicate:' if kind in ('central_composite','box_behnken') else 'Center points per block:')
        mixture=kind in _MIXTURE;self.factor_tabs.setTabVisible(1,kind=='custom_optimal')
        for column in (1,2):self.factor_table.setColumnHidden(column,mixture)
        for column in (3,4):self.factor_table.setColumnHidden(column,not mixture)
        for row in range(self.factor_table.rowCount()):
            widget=self.factor_table.cellWidget(row,1);widget.setEnabled(kind not in _CONTINUOUS)
            if kind in _CONTINUOUS:widget.setCurrentIndex(0)
        visible={'generators':kind=='fractional_factorial','alpha':kind=='central_composite','array':kind=='taguchi','pb_runs':kind=='plackett_burman','degree':kind=='simplex_lattice','total':mixture,'optimal_runs':kind=='custom_optimal','criterion':kind=='custom_optimal','model':kind=='custom_optimal'}
        for key,(label,control) in self._option_rows.items():label.setVisible(visible[key]);control.setVisible(visible[key])
        self.centers.setEnabled(kind not in ('taguchi','custom_optimal'))
        guidance={
            'plackett_burman':'Screening estimates main effects; interactions can be confounded. Add independent replication to estimate experimental error.',
            'taguchi':'An orthogonal array balances factor comparisons. Full robustness assessment also requires noise-factor planning and response analysis.',
            'simplex_centroid':'Component amounts sum to the mixture total. Mixture responses require a mixture model.',
            'simplex_lattice':'Lattice degree controls the blend grid. Mixture responses require a mixture model.',
            'extreme_vertices':'These runs are the feasible corner blends under the component bounds; interior augmentation is a separate planning decision.',
            'custom_optimal':'Choose any whole-number run count supported by the model rank and available candidates (up to 256 distinct settings). There is no 16-run limit. D emphasizes coefficient estimation; I emphasizes average prediction variance on the candidate grid.',
            'full_factorial':'A complete two-level factorial uses 2^k corner settings, plus the specified replications and center points. For a different run budget, choose Custom optimal.',
            'fractional_factorial':'Regular two-level fractions use power-of-two corner counts determined by their generators. For a different run budget, choose Custom optimal.'}
        self.guidance.setText(guidance.get(kind,'Review factor ranges and run budget. Replicates and center points serve different purposes.'))
        self.queue_preview()

    def queue_preview(self,*args):
        if self._updating:return
        self.parameters=None;self.preview_sheet=None;self.create_button.setEnabled(False);self.export_button.setEnabled(False);self.summary.setText('Updating design preview…');self.preview_timer.start()

    def values(self):
        kind=self.family.currentData();factors=[];names=set()
        for row in range(self.factor_table.rowCount()):
            name=self.factor_table.item(row,0).text().strip()
            if not name or name in names:raise ValueError('Each factor needs a distinct nonblank name.')
            names.add(name)
            if kind in _MIXTURE:
                factors.append({'name':name,'low':_finite(self.factor_table.item(row,3).text(),'Lower bound'),'high':_finite(self.factor_table.item(row,4).text(),'Upper bound')});continue
            factor_kind=self.factor_table.cellWidget(row,1).currentData();raw=self.factor_table.item(row,2).text().strip()
            parts=[value.strip() for value in raw.split(',')] if ',' in raw else raw.split()
            if len(parts)<2 or any(not part for part in parts):raise ValueError(name+': enter at least two distinct levels, separated by commas.')
            levels=[_finite(value,name+' level') for value in parts] if factor_kind=='number' else parts
            if len(set(levels))!=len(levels):raise ValueError(name+': levels must be distinct.')
            if kind in _CONTINUOUS:
                if len(levels)!=2 or levels[0]>=levels[1]:raise ValueError(name+': enter two numeric levels, lower then upper.')
                factors.append({'name':name,'low':levels[0],'high':levels[1]})
            else:factors.append({'name':name,'kind':factor_kind,'levels':levels})
        options={}
        if kind=='fractional_factorial':
            generators={}
            for item in re.split('[;\\n]+',self.generators.text().strip()):
                if not item.strip():continue
                parts=item.split('=')
                if len(parts)!=2 or not parts[0].strip() or not parts[1].strip():raise ValueError('Enter generators as D=ABC; E=AB.')
                generators[parts[0].strip()]=parts[1].strip()
            if not generators:raise ValueError('Specify at least one fractional generator.')
            options['generators']=generators
        if kind=='central_composite':
            value=self.alpha.currentData() if self.alpha.currentIndex()>=0 and self.alpha.currentText()==self.alpha.itemText(self.alpha.currentIndex()) else None
            options['alpha']=value if value is not None else _finite(self.alpha.currentText(),'Alpha')
        if kind=='taguchi' and self.array.currentData()!='auto':options['array']=self.array.currentData()
        if kind=='plackett_burman' and self.pb_runs.currentData():options['runs']=self.pb_runs.currentData()
        if kind in _MIXTURE:
            options['total']=_finite(self.total.text(),'Mixture total')
            if kind=='simplex_lattice':options['degree']=self.degree.value()
        if kind=='custom_optimal':
            forbidden=[]
            for row in range(self.forbidden_table.rowCount()):
                combination={}
                for column,factor in enumerate(factors):
                    item=self.forbidden_table.item(row,column);value=item.text().strip() if item else ''
                    if value:combination[factor['name']]=_finite(value,'Excluded level') if factor['kind']=='number' else value
                if combination:forbidden.append(combination)
            options.update(runs=self.optimal_runs.value(),criterion=self.criterion.currentText(),model=self.model.currentData(),forbidden=forbidden)
        name=self.name_edit.text().strip()
        if not name:raise ValueError('Enter a worksheet name.')
        return {'kind':kind,'factors':factors,'replicates':self.replicates.value(),'centers':self.centers.value() if self.centers.isEnabled() else 0,'blocks':self.blocks.value() if self.blocks.isEnabled() else 1,'randomize':self.randomize.isChecked(),'seed':self.seed.value(),'options':options,'name':name}

    def refresh_preview(self):
        self.preview_timer.stop();self.parameters=None;self.preview_sheet=None
        try:
            from .doe_planner import build_plan
            parameters=self.values();sheet=build_plan(**parameters)
        except (ValueError,TypeError,KeyError,ImportError,OverflowError) as error:
            self.error.setText(str(error));self.summary.setText('Update the design settings to generate a preview.');self.preview_table.setRowCount(0);self.create_button.setEnabled(False);self.export_button.setEnabled(False);return False
        self.parameters=copy.deepcopy(parameters);self.preview_sheet=sheet;self.error.clear()
        count=sheet.row_count;shown=min(count,100)
        self.summary.setText(f'{self.family.currentText()}: {count} runs, {len(parameters["factors"])} factors, {parameters["blocks"]} block(s).'+(f' Showing the first {shown} runs.' if count>shown else ''))
        diagnostics=sheet.metadata.get('doe',{}).get('diagnostics',{})
        if parameters['kind']=='custom_optimal':
            self.summary.setText(self.summary.text()+f" Model rank: {diagnostics.get('rank')}/{diagnostics.get('model_columns')}; allowed candidates: {diagnostics.get('candidate_count')}."+(' Exchange search converged.' if diagnostics.get('converged') else ' Exchange pass limit reached; review the design.'))
        self.preview_table.setColumnCount(len(sheet.columns));self.preview_table.setHorizontalHeaderLabels([column.name for column in sheet.columns]);self.preview_table.setRowCount(shown)
        for col,column in enumerate(sheet.columns):
            for row in range(shown):
                value=column.values[row] if row<len(column.values) else None
                self.preview_table.setItem(row,col,QTableWidgetItem('*' if value is None else f'{value:.6g}' if isinstance(value,(int,float)) else str(value)))
        self.create_button.setEnabled(True);self.export_button.setEnabled(True);return True

    def reject(self):
        self.preview_timer.stop();super().reject()

    def closeEvent(self,event):
        self.preview_timer.stop();super().closeEvent(event)

    def create(self):
        if self.refresh_preview():self.accept()

    def export_excel(self):
        if not self.refresh_preview():return
        path,_=QFileDialog.getSaveFileName(self,'Export DOE Plan',self.name_edit.text()+'.xlsx','Excel Workbook (*.xlsx)')
        if not path:return
        if not path.lower().endswith('.xlsx'):path+='.xlsx'
        try:
            if self.export_callback:self.export_callback(path,[self.preview_sheet])
            else:
                from .xlsx_export import write_workbook
                write_workbook(path,[self.preview_sheet])
        except (ValueError,OSError,ImportError) as error:self.error.setText(str(error));return
        self.error.clear();self.summary.setText('Exported '+path)
