"""StatCraft-informed GLM roles and working Model/Options/Coding/Graphs/Results dialogs."""
import itertools
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QListWidget,QListWidgetItem,QPushButton,QDialogButtonBox,QComboBox,QCheckBox,
    QDoubleSpinBox,QSpinBox,QGridLayout)
from .variable_dialogs import ProcedureDialog,format_variable_list,format_variable_reference
from .glm import settings,validate_terms


class ModelTermsDialog(QDialog):
    def __init__(self,parent,names,terms):
        self.setSizeGripEnabled(True)
        super().__init__(parent);self.setWindowTitle('General Linear Model: Model');self.resize(690,430)
        self.names=names;self.terms=None;layout=QVBoxLayout(self);body=QHBoxLayout()
        self.available=QListWidget();self.selected=QListWidget()
        for label,widget in [('Predictors and interactions',self.available),('Terms in the model (in order)',self.selected)]:
            column=QVBoxLayout();column.addWidget(QLabel(label));column.addWidget(widget);body.addLayout(column)
        layout.addLayout(body)
        for size in range(1,min(3,len(names))+1):
            for term in itertools.combinations(range(len(names)),size):self.item(self.available,list(term))
        for term in terms:self.item(self.selected,term)
        buttons=QHBoxLayout()
        for text,callback in [('Add →',self.add),('Remove',self.remove),('Move Up',lambda:self.move(-1)),('Move Down',lambda:self.move(1))]:
            button=QPushButton(text);button.clicked.connect(callback);buttons.addWidget(button)
        layout.addLayout(buttons);row=QHBoxLayout();row.addWidget(QLabel('Interactions through order:'))
        self.order=QSpinBox();self.order.setRange(1,min(3,len(names)));self.order.setValue(min(2,len(names)));row.addWidget(self.order)
        allbutton=QPushButton('Add terms');allbutton.clicked.connect(self.add_order);row.addWidget(allbutton);row.addStretch();layout.addLayout(row)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color:#a02020');layout.addWidget(self.error)
        footer=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);footer.accepted.connect(self.validate);footer.rejected.connect(self.reject);layout.addWidget(footer)
        self.available.itemDoubleClicked.connect(lambda item:self.add())

    def item(self,widget,term):
        item=QListWidgetItem('*'.join(self.names[i] for i in term));item.setData(Qt.ItemDataRole.UserRole,list(term));widget.addItem(item)

    def chosen(self):return [self.selected.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.selected.count())]

    def add(self):
        item=self.available.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole) not in self.chosen():self.item(self.selected,item.data(Qt.ItemDataRole.UserRole))

    def remove(self):
        row=self.selected.currentRow()
        if row>=0:self.selected.takeItem(row)

    def move(self,offset):
        row=self.selected.currentRow();target=row+offset
        if 0<=row<self.selected.count() and 0<=target<self.selected.count():self.selected.insertItem(target,self.selected.takeItem(row));self.selected.setCurrentRow(target)

    def add_order(self):
        for size in range(1,self.order.value()+1):
            for term in itertools.combinations(range(len(self.names)),size):
                if list(term) not in self.chosen():self.item(self.selected,term)

    def validate(self):
        try:self.terms=validate_terms(self.chosen(),len(self.names))
        except ValueError as exc:self.error.setText(str(exc));return
        self.accept()


class ModelSettingsDialog(QDialog):
    def __init__(self,parent,section,options):
        self.setSizeGripEnabled(True)
        super().__init__(parent);self.setWindowTitle('General Linear Model: '+section);self.options=None;self.section=section;self.initial=dict(options);self.controls={}
        self.setMinimumWidth(460);layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        def combo(key,label,choices,values):
            c=QComboBox();c.addItems(choices);c.setCurrentIndex(values.index(options[key]));self.controls[key]=(c,values);form.addRow(label,c)
        if section=='Options':
            confidence=QDoubleSpinBox();confidence.setRange(.01,99.99);confidence.setDecimals(2);confidence.setSuffix(' %');confidence.setValue(options['confidence']*100);self.controls['confidence']=confidence;form.addRow('Confidence level for all intervals:',confidence)
            combo('ss_type','Sum of squares for tests:',['Adjusted (Type III)','Sequential (Type I)'],['adjusted','sequential'])
        elif section=='Coding':
            combo('coding','Coding for factors:',['(-1, 0, +1)','(1, 0)'],['effect','reference'])
            combo('standardize','Standardize covariates:',['Do not standardize','Subtract the mean','Divide by the standard deviation','Subtract the mean, then divide by the standard deviation'],['none','center','scale','standardize'])
            note=QLabel('The final level in the factor value order is the reference level. Factor value order follows the worksheet settings.');note.setWordWrap(True);form.addRow(note)
        elif section=='Graphs':
            combo('graphs','Residual plots:',['None','Four in one','Residuals versus fits','Residuals versus observation order','Normal probability plot','Histogram'],['none','four','fitted','order','normal','histogram'])
        elif section=='Results':
            for key,label in [('method','Method'),('factor_information','Factor information'),('anova','Analysis of variance'),('model_summary','Model summary'),('coefficients','Coefficients')]:
                c=QCheckBox(label);c.setChecked(options[key]);self.controls[key]=c;form.addRow(c)
            combo('diagnostics','Fits and diagnostics:',['Do not display','Only for unusual observations','For all observations'],['none','unusual','all'])
        footer=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);footer.accepted.connect(self.validate);footer.rejected.connect(self.reject);layout.addWidget(footer)

    def validate(self):
        o=dict(self.initial)
        for key,control in self.controls.items():
            if isinstance(control,tuple):o[key]=control[1][control[0].currentIndex()]
            elif key=='confidence':o[key]=control.value()/100
            else:o[key]=control.isChecked()
        self.options=settings(o);self.accept()


class GeneralLinearModelDialog(ProcedureDialog):
    def __init__(self,window):
        specs=[dict(key='response_index',label='Response:',kinds=('number',)),
            dict(key='factor_indices',label='Factors:',multiple=True,minimum=0,kinds=('number','text')),
            dict(key='covariate_indices',label='Covariates:',multiple=True,minimum=0,kinds=('number',))]
        super().__init__(window,'General Linear Model',window.presenter.worksheet,specs,(),
            'Fixed factors and continuous covariates. Select variables, then use Model, Options, Coding, Graphs and Results to configure the analysis.')
        self.window=window;self.options=settings();self.terms=None;self.signature=None;self.entry=None;self.option_buttons={}
        grid=QGridLayout()
        for i,name in enumerate(['Model','Options','Coding','Graphs','Results']):
            button=QPushButton(name+'…');button.setAutoDefault(False);button.clicked.connect(lambda checked=False,name=name:self.configure(name));self.option_buttons[name]=button;grid.addWidget(button,i//3,i%3)
        self.layout().insertLayout(self.layout().count()-2,grid)
        self.model_label=QLabel('Model: main effects');self.model_label.setWordWrap(True);self.layout().insertWidget(self.layout().count()-2,self.model_label)
        self.restore_previous()

    def restore_previous(self):
        p=self.window.presenter
        worksheet_id=p.native_project.worksheet_ids[p.native_project.active_index] if p.native_project else None
        for entry in reversed(p.history):
            if entry.get('source_unavailable') or entry.get('recipe',{}).get('action')!='general_linear_model':continue
            if entry.get('worksheet_id')!=worksheet_id or entry.get('worksheet_name')!=p.worksheet.name:continue
            v=entry['recipe']['parameters']
            try:
                self.controls['response_index'].setText(format_variable_reference(v['response_index'],self.worksheet))
                for key in ('factor_indices','covariate_indices'):self.controls[key].setText(format_variable_list(v[key],self.worksheet))
                self.signature=(tuple(v['factor_indices']),tuple(v['covariate_indices']));self.terms=[list(t) for t in v['terms']];self.options=settings(v['options'])
                self.describe_model(v['factor_indices']+v['covariate_indices'])
            except (IndexError,ValueError,KeyError,TypeError):continue
            break

    def describe_model(self,indices):
        self.model_label.setText('Model: '+' + '.join('*'.join(self.worksheet.columns[indices[i]].name for i in t) for t in self.terms))

    def roles(self):
        v=self.values();indices=v['factor_indices']+v['covariate_indices']
        if not 1<=len(indices)<=8 or len(set(indices+[v['response_index']]))!=len(indices)+1:raise ValueError('Choose 1–8 distinct predictors and a separate response.')
        signature=(tuple(v['factor_indices']),tuple(v['covariate_indices']))
        if signature!=self.signature:self.terms=[[i] for i in range(len(indices))];self.signature=signature;self.describe_model(indices)
        return v,indices

    def configure(self,name):
        try:
            if name=='Model':
                values,indices=self.roles();names=['C'+str(i+1)+': '+self.worksheet.columns[i].name for i in indices]
                dialog=ModelTermsDialog(self,names,self.terms)
                if dialog.exec():self.terms=dialog.terms;self.describe_model(indices)
            else:
                dialog=ModelSettingsDialog(self,name,self.options)
                if dialog.exec():self.options=dialog.options
        except (ValueError,TypeError,IndexError) as exc:self.error.setText(str(exc))

    def validate(self):
        try:
            values,indices=self.roles()
            self.entry=self.window.presenter.general_linear_model(**values,terms=self.terms,options=self.options)
            self.window.refresh();self.window.show_result(self.entry)
        except (ValueError,TypeError,IndexError,ArithmeticError) as exc:self.error.setText(str(exc));return
        self.accept()
