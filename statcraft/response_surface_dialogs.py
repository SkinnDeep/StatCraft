"""Native-informed response-surface design and analysis dialogs."""
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (QApplication,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,
    QGridLayout,QLabel,QPushButton,QComboBox,QSpinBox,QDoubleSpinBox,QCheckBox,
    QLineEdit,QTableWidget,QTableWidgetItem,QHeaderView,QDialogButtonBox,QRadioButton,QGroupBox,QAbstractItemView,QMessageBox)
from .variable_dialogs import ProcedureDialog,format_variable_reference,format_variable_list
from .glm_dialogs import ModelTermsDialog,ModelSettingsDialog
from .glm import settings
from .response_surface import create,default_coding,full_terms,validate_terms
from .response_surface_catalog import catalog
from .model import finite_number
from .data_prep_dialogs import destinations


def footer(dialog,layout,accept=None):
    b=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    b.accepted.connect(accept or dialog.accept);b.rejected.connect(dialog.reject);layout.addWidget(b)


def _family(spec):
    return 'Box-Behnken' if spec['kind']=='box_behnken' else {1:'Full',2:'Half',4:'Quarter',8:'Eighth'}[spec['fraction']]


def _matching(spec,kind,count,fraction=1,blocks=1):
    return spec['kind']==kind and spec['factors']==count and spec['fraction']==fraction and spec['blocks']==blocks


class CreateSurfaceDialog(QDialog):
    def __init__(self,window):
        self.setSizeGripEnabled(True)
        super().__init__(window);self.window=window;self.setWindowTitle('Create Response Surface Design');self.setMinimumWidth(700)
        self.factors=[dict(name=chr(65+i),low=-1.,high=1.) for i in range(10)]
        self.centers=6;self.replicates=1;self.alpha_mode='rotatable';self.alpha=2**.5;self.randomize=True;self.seed=1;self.levels_define='cube';self.display='summary';self.target=None;self.entry=None
        self.fraction=1;self.blocks=1;self.center_cube=None;self.center_axial=None;self.block_replicates=False;self._configuring=False
        layout=QVBoxLayout(self);body=QHBoxLayout();left=QVBoxLayout();types=QGroupBox('Type of Design');choices=QVBoxLayout(types)
        self.central=QRadioButton('Central composite');self.box=QRadioButton('Box-Behnken');self.central.setChecked(True);choices.addWidget(self.central);choices.addWidget(self.box);left.addWidget(types)
        form=QFormLayout();self.count=QComboBox();self.count.addItems([str(k) for k in sorted({s['factors'] for s in catalog() if s['kind']=='central_composite'})]);form.addRow('Number of continuous factors:',self.count);left.addLayout(form);left.addStretch();body.addLayout(left,3)
        right=QVBoxLayout();self.option_buttons={}
        for text in ['Display Available Designs','Designs','Factors','Options','Results']:
            button=QPushButton(text+'…');button.setAutoDefault(False);button.clicked.connect(lambda checked=False,text=text:self.configure(text));self.option_buttons[text]=button;right.addWidget(button)
        right.addStretch();body.addLayout(right,2);layout.addLayout(body)
        self.box.toggled.connect(self.change_kind);self.count.currentTextChanged.connect(self._change_count)
        self.design_description=QLabel();self.design_description.setWordWrap(True);layout.addWidget(self.design_description)
        note=QLabel('Select a cell in Display Available Designs, or choose a design and blocking arrangement in Designs. Cube-defined central composite levels can produce axial settings outside the entered low/high range.');note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();self.name=QLineEdit('Response surface design');self.destination=QComboBox();self.destination.addItems(destinations(window.presenter));form.addRow('New worksheet name:',self.name);form.addRow('Store in:',self.destination);layout.addLayout(form)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color:#a02020');layout.addWidget(self.error);footer(self,layout,self.validate)
        self._update_summary()

    def change_kind(self,box):
        if self._configuring:return
        kind='box_behnken' if box else 'central_composite';old=int(self.count.currentText() or 2)
        counts=sorted({s['factors'] for s in catalog() if s['kind']==kind})
        with QSignalBlocker(self.count):self.count.clear();self.count.addItems([str(k) for k in counts]);self.count.setCurrentText(str(old if old in counts else counts[0]))
        options=[s for s in catalog() if s['kind']==kind and s['factors']==int(self.count.currentText())]
        self.apply_design(next((s for s in options if s['blocks']==1),options[0]))

    def _change_count(self,text):
        if self._configuring or not text:return
        options=[s for s in catalog() if s['kind']==('central_composite' if self.central.isChecked() else 'box_behnken') and s['factors']==int(text)]
        chosen=next((s for s in options if s['fraction']==self.fraction and s['blocks']==self.blocks),next((s for s in options if s['blocks']==1),options[0]))
        self.apply_design(chosen)

    def apply_design(self,spec):
        self._configuring=True
        try:
            self.central.setChecked(spec['kind']=='central_composite');self.box.setChecked(spec['kind']=='box_behnken')
            counts=sorted({s['factors'] for s in catalog() if s['kind']==spec['kind']})
            with QSignalBlocker(self.count):self.count.clear();self.count.addItems([str(k) for k in counts]);self.count.setCurrentText(str(spec['factors']))
            for key in ('fraction','blocks','centers','center_cube','center_axial'):setattr(self,key,spec[key])
            self.alpha_mode='default';self.alpha=spec['alpha'];self.replicates=1;self.block_replicates=False
        finally:self._configuring=False
        self._update_summary()

    def parameters(self):
        return dict(factors=[dict(f) for f in self.factors[:int(self.count.currentText())]],kind='box_behnken' if self.box.isChecked() else 'central_composite',centers=self.centers,replicates=self.replicates,alpha_mode=self.alpha_mode,alpha=self.alpha,levels_define=self.levels_define,randomize=self.randomize,seed=self.seed,name=self.name.text() if hasattr(self,'name') else 'Response surface design',fraction=self.fraction,blocks=self.blocks,center_cube=self.center_cube,center_axial=self.center_axial,block_replicates=self.block_replicates)

    def _update_summary(self):
        try:
            sheet=create(**self.parameters());d=sheet.metadata['doe'];family='Box-Behnken' if self.box.isChecked() else _family(dict(kind='central_composite',fraction=self.fraction))+' central composite'
            self.design_description.setText(f"{family} · {len(self.factors[:int(self.count.currentText())])} factors · {sheet.row_count} runs · {d['blocks']} block"+('s' if d['blocks']!=1 else ''))
        except (ValueError,TypeError,AttributeError,KeyError):self.design_description.setText('Choose a supported design and valid settings.')

    def configure(self,section):
        child=CreateSurfaceSettings(self,section)
        if child.exec():
            values=dict(child.changes)
            if 'selected_design' in values:self.apply_design(values.pop('selected_design'))
            for key,value in values.items():setattr(self,key,value)
            self._update_summary()

    def validate(self):
        try:
            self.target,self.entry=self.window.presenter.create_response_surface(**self.parameters(),destination='worksheet' if self.destination.currentText()=='New worksheet' else 'project',display=self.display)
            if self.target is self.window.presenter:target_window=self.window;target_window.page=0
            else:
                from .modern_app import ModernWindow
                app=QApplication.instance()
                if not hasattr(app,'_prepared_windows'):app._prepared_windows=[]
                target_window=ModernWindow(self.target);app._prepared_windows.append(target_window);target_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                target_window.destroyed.connect(lambda *args:app._prepared_windows.remove(target_window) if target_window in app._prepared_windows else None)
                target_window.showMaximized()
            target_window.refresh()
            if self.entry:target_window.show_result(self.entry)
        except (ValueError,TypeError,IndexError,ArithmeticError) as exc:self.error.setText(str(exc));return
        self.accept()


class CreateSurfaceSettings(QDialog):
    def __init__(self,parent,section):
        self.setSizeGripEnabled(True)
        super().__init__(parent);self.owner=parent;self.section=section;self.changes={};self.controls={};self.setWindowTitle('Create Response Surface Design: '+section);self.setMinimumWidth(500)
        self.body_layout=layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form);p=parent
        if section=='Display Available Designs':self._build_catalog(layout)
        elif section=='Designs':self._build_designs(layout)
        elif section=='Factors':
            if p.central.isChecked():
                c=QComboBox();c.addItems(['Cube points','Axial points']);c.setCurrentIndex(0 if p.levels_define=='cube' else 1);self.controls['levels_define']=c;form.addRow('Levels define:',c)
            table=QTableWidget(int(p.count.currentText()),3);table.setHorizontalHeaderLabels(['Name','Low','High']);self.controls['factors']=table
            for row,f in enumerate(p.factors[:table.rowCount()]):
                for col,key in enumerate(['name','low','high']):table.setItem(row,col,QTableWidgetItem(str(f[key])))
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(table)
        elif section=='Options':
            c=QCheckBox('Randomize runs');c.setChecked(p.randomize);self.controls['randomize']=c;form.addRow(c)
            seed=QLineEdit(str(p.seed));self.controls['seed']=seed;form.addRow('Base for random data generator:',seed)
        elif section=='Results':
            c=QComboBox();c.addItems(['None','Summary table','Summary table and design table']);c.setCurrentIndex(['none','summary','full'].index(p.display));self.controls['display']=c;form.addRow('Printed results:',c)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color:#a02020');layout.addWidget(self.error);footer(self,layout,self.validate)

    def _build_catalog(self,layout):
        self.resize(870,510);p=self.owner
        heading=QLabel('Available Response Surface Designs');heading.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(heading)
        table=QTableWidget(12,11);self.available_table=table;table.setObjectName('responseSurfaceAvailableDesigns')
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().hide();table.verticalHeader().hide();table.verticalHeader().setDefaultSectionSize(25)
        table.setSpan(0,0,2,2);table.setSpan(0,2,1,9)
        def cell(row,col,text,header=False,spec=None):
            item=QTableWidgetItem(str(text));item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col!=1 else Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled|(Qt.ItemFlag.ItemIsSelectable if spec else Qt.ItemFlag.NoItemFlags))
            if header:font=item.font();font.setBold(True);item.setFont(font)
            if spec:
                item.setData(Qt.ItemDataRole.UserRole,spec);item.setToolTip(f"Create {_family(spec)} with {spec['factors']} factors, {spec['runs']} runs, {spec['blocks']} blocks. Select the cell and click OK.")
            else:item.setToolTip('No design in this catalog cell.' if row>=2 and col>=2 else '')
            table.setItem(row,col,item)
        cell(0,0,'Design',True);cell(0,2,'Continuous Factors',True)
        for col,k in enumerate(range(2,11),2):cell(1,col,k,True)
        for group,name in enumerate(('Central composite full','Central composite half','Central composite quarter','Central composite eighth','Box-Behnken')):
            row=2+2*group;table.setSpan(row,0,2,1);cell(row,0,name,True)
            for offset in (0,1):
                cell(row+offset,1,'blocked' if offset else 'unblocked',True)
                for k in range(2,11):
                    specs=[s for s in catalog() if s['factors']==k and (s['kind']=='box_behnken' if group==4 else s['kind']=='central_composite' and s['fraction']==(1,2,4,8)[group]) and (s['blocks']>1)==bool(offset)]
                    chosen=min(specs,key=lambda s:(s['runs'],s['blocks'])) if specs else None
                    cell(row+offset,k,chosen['runs'] if chosen else '',spec=chosen)
        table.setColumnWidth(0,245);table.setColumnWidth(1,100)
        for col in range(2,11):table.setColumnWidth(col,48)
        table.horizontalHeader().setStretchLastSection(True);table.setMinimumHeight(310);layout.addWidget(table)
        self.selection_label=QLabel();self.selection_label.setWordWrap(True);layout.addWidget(self.selection_label)
        self.selected_spec=None
        def select(row,column,*unused):
            item=table.item(row,column);spec=item.data(Qt.ItemDataRole.UserRole) if item else None
            if not spec:return
            self.selected_spec=dict(spec);self.selection_label.setText(f"{_family(spec)} — {spec['factors']} factors, {spec['runs']} runs, {spec['blocks']} block"+('s' if spec['blocks']!=1 else '')+'. Click OK to use this design.')
        table.currentCellChanged.connect(select);table.cellClicked.connect(select);table.cellDoubleClicked.connect(lambda row,col:self.validate() if table.item(row,col) and table.item(row,col).data(Qt.ItemDataRole.UserRole) else None)
        kind='central_composite' if p.central.isChecked() else 'box_behnken';count=int(p.count.currentText())
        current=next((s for s in catalog() if _matching(s,kind,count,p.fraction,p.blocks)),next(s for s in catalog() if s['kind']==kind and s['factors']==count))
        row=10 if kind=='box_behnken' else 2+2*(1,2,4,8).index(current['fraction']);row+=int(current['blocks']>1)
        table.setCurrentCell(row,count);select(row,count)
        help_button=QPushButton('Help');help_button.setAutoDefault(False)
        help_button.clicked.connect(lambda:QMessageBox.information(self,'Available Response Surface Designs','Every numbered cell creates a design with the displayed run count and factor count. Select a cell and click OK. Designs contains all available blocking arrangements for the selected factor count. Default run counts include center points; custom centers and replicates can change the total.'))
        layout.addWidget(help_button,alignment=Qt.AlignmentFlag.AlignLeft)

    def _build_designs(self,layout):
        self.resize(680,590);p=self.owner;k=int(p.count.currentText());central=p.central.isChecked();kind='central_composite' if central else 'box_behnken'
        self.design_choices=[dict(s) for s in catalog() if s['kind']==kind and s['factors']==k]
        table=QTableWidget(len(self.design_choices),7);self.design_table=table;table.setObjectName('responseSurfaceDesignChoices')
        table.setHorizontalHeaderLabels(['Designs','Runs','Blocks','Center Points\nTotal','Cube','Axial','Default\nAlpha']);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide();table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);table.setMinimumHeight(150)
        for row,spec in enumerate(self.design_choices):
            for col,value in enumerate((_family(spec),spec['runs'],spec['blocks'],spec['centers'],spec['center_cube'],spec['center_axial'],format(spec['alpha'],'.4f') if central else '—')):
                item=QTableWidgetItem(str(value));item.setData(Qt.ItemDataRole.UserRole,spec);table.setItem(row,col,item)
        selected=next((i for i,s in enumerate(self.design_choices) if s['fraction']==p.fraction and s['blocks']==p.blocks),0);self.selected_spec=self.design_choices[selected];table.selectRow(selected);layout.addWidget(table)
        center_group=QGroupBox('Number of Center Points');center_layout=QVBoxLayout(center_group)
        self.default_centers=QRadioButton('Default');self.custom_centers=QRadioButton('Custom');center_layout.addWidget(self.default_centers);center_layout.addWidget(self.custom_centers)
        center_form=QFormLayout();center_layout.addLayout(center_form)
        cube=QSpinBox();cube.setRange(0,200);cube.setValue(p.center_cube if p.center_cube is not None else p.centers);axial=QSpinBox();axial.setRange(0,200);axial.setValue(p.center_axial or 0)
        self.controls['centers']=cube;self.controls['center_cube']=cube;self.controls['center_axial']=axial
        cube.setToolTip('Total center points across the cube blocks; centers are distributed as evenly as possible.')
        axial.setToolTip('Center points in the axial block.')
        center_form.addRow('Cube block:' if central else 'Center points:',cube)
        if central:center_form.addRow('Axial block:',axial)
        self.custom_centers.setChecked((cube.value(),axial.value())!=(self.selected_spec['center_cube'],self.selected_spec['center_axial']));self.default_centers.setChecked(not self.custom_centers.isChecked())
        layout.addWidget(center_group)
        bottom=QHBoxLayout();alpha_group=QGroupBox('Value of Alpha');alpha_layout=QVBoxLayout(alpha_group);self.alpha_buttons={}
        mode=QComboBox(self);mode.addItems(['Default','Face centered','Custom']);mode.setCurrentIndex(1 if p.alpha_mode=='face' else 2 if p.alpha_mode=='custom' else 0);mode.hide();self.controls['alpha_mode']=mode
        for index,label in enumerate(('Default','Face Centered','Custom')):
            radio=QRadioButton(label);self.alpha_buttons[index]=radio;alpha_layout.addWidget(radio);radio.toggled.connect(lambda checked,index=index:mode.setCurrentIndex(index) if checked else None)
        self.alpha_buttons[mode.currentIndex()].setChecked(True);mode.currentIndexChanged.connect(lambda index:self.alpha_buttons[index].setChecked(True))
        a=QDoubleSpinBox();a.setRange(1,5);a.setDecimals(6);a.setValue(p.alpha);self.controls['alpha']=a;alpha_layout.addWidget(a)
        self.effective_alpha=QLabel();alpha_layout.addWidget(self.effective_alpha);alpha_group.setVisible(central);bottom.addWidget(alpha_group)
        replicate_form=QFormLayout();r=QSpinBox();r.setRange(1,100);r.setValue(p.replicates);self.controls['replicates']=r;replicate_form.addRow('Number of replicates:',r)
        block_replicates=QCheckBox('Block on replicates');block_replicates.setChecked(p.block_replicates);self.controls['block_replicates']=block_replicates;replicate_form.addRow(block_replicates)
        self.run_count=QLabel();self.block_count=QLabel();replicate_form.addRow('Number of runs:',self.run_count);replicate_form.addRow('Total blocks:',self.block_count)
        bottom.addLayout(replicate_form);layout.addLayout(bottom)
        self.preview_warning=QLabel();self.preview_warning.setWordWrap(True);self.preview_warning.setStyleSheet('color:#7a5a10');layout.addWidget(self.preview_warning)
        self.preview_error=QLabel();self.preview_error.setWordWrap(True);self.preview_error.setStyleSheet('color:#a02020');layout.addWidget(self.preview_error)
        def update(*unused):
            cube.setEnabled(self.custom_centers.isChecked());axial.setEnabled(self.custom_centers.isChecked() and central and self.selected_spec['blocks']>1);a.setEnabled(mode.currentIndex()==2);block_replicates.setEnabled(r.value()>1)
            self.effective_alpha.setText('Effective alpha: '+format(self.selected_spec['alpha'] if mode.currentIndex()==0 else 1. if mode.currentIndex()==1 else a.value(),'.6g'))
            try:
                params=self.owner.parameters();params.update(self._design_values());sheet=create(**params)
                metadata=sheet.metadata['doe'];self.run_count.setText(str(sheet.row_count));self.block_count.setText(str(metadata['blocks']));self.preview_error.clear()
                self.effective_alpha.setText('Effective alpha: '+format(metadata['alpha'],'.6g'));self.preview_warning.setText('\n'.join(metadata.get('warnings',[])))
            except (ValueError,TypeError,AttributeError,KeyError) as exc:self.run_count.setText('—');self.block_count.setText('—');self.preview_warning.clear();self.preview_error.setText(str(exc))
        def defaults(checked):
            if checked:
                with QSignalBlocker(cube):cube.setValue(self.selected_spec['center_cube'])
                with QSignalBlocker(axial):axial.setValue(self.selected_spec['center_axial'])
            update()
        self.default_centers.toggled.connect(defaults);self.custom_centers.toggled.connect(update)
        for control in (cube,axial,r,a):control.valueChanged.connect(update)
        mode.currentIndexChanged.connect(update);block_replicates.toggled.connect(update)
        def choose(row,*unused):
            if row<0:return
            self.selected_spec=self.design_choices[row];self.default_centers.setChecked(True);defaults(True);mode.setCurrentIndex(0);update()
        table.currentCellChanged.connect(choose);table.cellClicked.connect(choose);update()

    def _design_values(self):
        c=self.controls;cube=c['center_cube'].value();axial=c['center_axial'].value() if self.selected_spec['kind']=='central_composite' and self.selected_spec['blocks']>1 else 0
        return dict(fraction=self.selected_spec['fraction'],blocks=self.selected_spec['blocks'],centers=cube+axial,center_cube=cube,center_axial=axial,replicates=c['replicates'].value(),block_replicates=c['block_replicates'].isChecked(),alpha_mode=['default','face','custom'][c['alpha_mode'].currentIndex()],alpha=c['alpha'].value())

    def validate(self):
        try:
            if self.section=='Display Available Designs':
                if self.selected_spec is None:raise ValueError('Select a numbered design cell.')
                self.changes={'selected_design':dict(self.selected_spec)};self.accept();return
            self.setFocus();QApplication.processEvents();c=self.controls;values=self._design_values() if self.section=='Designs' else {}
            if self.section!='Designs':
                for key,control in c.items():
                    if key=='factors':
                        factors=[dict(name=control.item(r,0).text().strip(),low=finite_number(float(control.item(r,1).text())),high=finite_number(float(control.item(r,2).text()))) for r in range(control.rowCount())]
                        values[key]=factors+[dict(f) for f in self.owner.factors[len(factors):]]
                    elif key=='levels_define':values[key]=['cube','axial'][control.currentIndex()]
                    elif key=='display':values[key]=['none','summary','full'][control.currentIndex()]
                    elif key=='randomize':values[key]=control.isChecked()
                    elif key=='seed':values[key]=int(control.text())
            parameters=self.owner.parameters();parameters['name']='Response surface design';parameters.update({k:v[:int(self.owner.count.currentText())] if k=='factors' else v for k,v in values.items() if k!='display'})
            create(**parameters);self.changes=values
        except (ValueError,TypeError,AttributeError) as exc:self.error.setText(str(exc));return
        self.accept()


class SurfaceTermsDialog(ModelTermsDialog):
    def __init__(self,parent,names,terms):
        super().__init__(parent,names,terms);self.setWindowTitle('Analyze Response Surface Design: Terms');self.available.clear();self.order.setRange(1,2);self.order.setValue(2)
        for term in full_terms(len(names)):self.item(self.available,term)

    def add_order(self):
        for term in (full_terms(len(self.names)) if self.order.value()==2 else [[i] for i in range(len(self.names))]):
            if term not in self.chosen():self.item(self.selected,term)

    def validate(self):
        try:self.terms=validate_terms(self.chosen(),len(self.names))
        except ValueError as exc:self.error.setText(str(exc));return
        self.accept()


class SurfaceCodingDialog(QDialog):
    def __init__(self,parent,names,coding):
        self.setSizeGripEnabled(True)
        super().__init__(parent);self.setWindowTitle('Analyze Response Surface Design: Low/High');self.coding=None;layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Low and high settings define coded −1 and +1.'))
        self.table=QTableWidget(len(names),3);self.table.setHorizontalHeaderLabels(['Factor','Low','High'])
        for r,(name,c) in enumerate(zip(names,coding)):
            for col,value in enumerate([name,c['low'],c['high']]):
                item=QTableWidgetItem(str(value))
                if col==0:item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r,col,item)
        layout.addWidget(self.table);self.error=QLabel();layout.addWidget(self.error);footer(self,layout,self.validate)

    def validate(self):
        try:
            self.setFocus();QApplication.processEvents();from .doe import _coding
            self.coding=[dict(low=finite_number(float(self.table.item(r,1).text())),high=finite_number(float(self.table.item(r,2).text()))) for r in range(self.table.rowCount())]
            for c in self.coding:_coding('',c['low'],c['high'])
        except (ValueError,TypeError,AttributeError) as exc:self.error.setText(str(exc));return
        self.accept()


class AnalyzeSurfaceDialog(ProcedureDialog):
    def __init__(self,window):
        super().__init__(window,'Analyze Response Surface Design',window.presenter.worksheet,[dict(key='response_index',label='Response:',kinds=('number',)),dict(key='factor_indices',label='Continuous factors:',multiple=True,minimum=2,maximum=10,kinds=('number',)),dict(key='block_index',label='Blocks (optional):',multiple=True,minimum=0,maximum=1,kinds=('number','text'))],(),
            'Choose a numeric response and continuous factors. Select Blocks for a blocked design. Low/High defines coding for custom worksheets; created designs retain their original coding.')
        self.window=window;self.options=settings();self.terms=None;self.coding=None;self.signature=None;self.entry=None;self.option_buttons={}
        grid=QGridLayout()
        for i,name in enumerate(['Terms','Low/High','Options','Graphs','Results']):
            b=QPushButton(name+'…');b.setAutoDefault(False);b.clicked.connect(lambda checked=False,name=name:self.configure(name));self.option_buttons[name]=b;grid.addWidget(b,i//3,i%3)
        self.layout().insertLayout(self.layout().count()-2,grid)
        auto=[i for i,c in enumerate(self.worksheet.columns) if 'rsm_coding' in c.metadata]
        if 2<=len(auto)<=10:self.controls['factor_indices'].setText(format_variable_list(auto,self.worksheet))
        if self.worksheet.metadata.get('doe',{}).get('blocks',1)>1:
            block=next((i for i,c in enumerate(self.worksheet.columns) if c.name.casefold()=='blocks'),None)
            if block is not None:self.controls['block_index'].setText(format_variable_reference(block,self.worksheet))
        p=window.presenter;identifier=p.native_project.worksheet_ids[p.native_project.active_index] if p.native_project else None
        for entry in reversed(p.history):
            if entry.get('source_unavailable') or entry.get('recipe',{}).get('action')!='analyze_response_surface' or entry.get('worksheet_id')!=identifier or entry.get('worksheet_name')!=p.worksheet.name:continue
            v=entry['recipe']['parameters'];self.controls['response_index'].setText(format_variable_reference(v['response_index'],self.worksheet));self.controls['factor_indices'].setText(format_variable_list(v['factor_indices'],self.worksheet));self.signature=tuple(v['factor_indices']);self.terms=[list(t) for t in v['terms']];self.coding=[dict(c) for c in v['coding']];self.options=settings(v['options']);block=v.get('block_index');self.controls['block_index'].setText(format_variable_reference(block,self.worksheet) if block is not None else '');break

    def values(self):
        values=super().values();selected=values['block_index'];values['block_index']=selected[0] if selected else None
        return values

    def roles(self):
        v=self.values();f=v['factor_indices']
        if v['response_index'] in f:raise ValueError('Choose a response separate from the factors.')
        if v['block_index'] is not None and v['block_index'] in f+[v['response_index']]:raise ValueError('Choose a block variable separate from the response and continuous factors.')
        if tuple(f)!=self.signature:self.signature=tuple(f);self.terms=full_terms(len(f));self.coding=default_coding(self.worksheet,f)
        return v,[self.worksheet.columns[i].name for i in f]

    def configure(self,name):
        try:
            if name in ('Terms','Low/High'):
                values,names=self.roles();d=SurfaceTermsDialog(self,names,self.terms) if name=='Terms' else SurfaceCodingDialog(self,names,self.coding)
                if d.exec():
                    if name=='Terms':self.terms=d.terms
                    else:self.coding=d.coding
            else:
                d=ModelSettingsDialog(self,name,self.options);d.setWindowTitle('Analyze Response Surface Design: '+name)
                if d.exec():self.options=d.options
        except (ValueError,TypeError,IndexError) as exc:self.error.setText(str(exc))

    def validate(self):
        try:
            values,names=self.roles();self.entry=self.window.presenter.analyze_response_surface(**values,coding=self.coding,terms=self.terms,options=self.options)
            self.window.refresh();self.window.show_result(self.entry)
        except (ValueError,TypeError,IndexError,ArithmeticError) as exc:self.error.setText(str(exc));return
        self.accept()
