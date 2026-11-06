"""REA-informed binary logistic role selection and effective model settings.

Form evidence: BINARYLOGISTICREGRESSION, OPTIONS and RESULTS resources.
Only independently implemented controls are exposed.
"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QDoubleSpinBox, QPushButton, QDialogButtonBox)
from .variable_dialogs import (ProcedureDialog, resolve_variables,
    format_variable_reference, format_variable_list)
from .glm_dialogs import ModelTermsDialog
from .glm import validate_terms
from .logistic import settings


class LogisticSettingsDialog(QDialog):
    def __init__(self, parent, section, options):
        super().__init__(parent)
        self.setSizeGripEnabled(True)
        self.setWindowTitle('Binary Logistic Regression: '+section)
        self.setMinimumWidth(460)
        self.initial=settings(options); self.options=None; self.controls={}
        layout=QVBoxLayout(self); form=QFormLayout(); layout.addLayout(form)
        if section=='Options':
            confidence=QDoubleSpinBox(); confidence.setRange(.01,99.99)
            confidence.setDecimals(2); confidence.setSuffix(' %')
            confidence.setValue(self.initial['confidence']*100)
            self.controls['confidence']=confidence
            form.addRow('Confidence level for all intervals:',confidence)
            threshold=QDoubleSpinBox(); threshold.setRange(.0001,.9999)
            threshold.setDecimals(4); threshold.setSingleStep(.05)
            threshold.setValue(self.initial['threshold']); self.controls['threshold']=threshold
            form.addRow('Classification probability threshold:',threshold)
            note=QLabel('Logit link; two-sided Wald confidence intervals. The threshold changes classification summaries, not the fitted model.')
            note.setWordWrap(True); form.addRow(note)
        elif section=='Graphs':
            self.combo(form,'graphs','Diagnostic plots:', [('None','none'),('Four-panel diagnostic dashboard','four')])
            note=QLabel('ROC curve, fitted event probabilities, deviance residuals versus fitted probability, and Pearson residuals versus observation order.')
            note.setWordWrap(True); form.addRow(note)
        elif section=='Results':
            for key,label in [('method','Method'),('response_information','Response information'),
                    ('model_summary','Model summary'),('coefficients','Coefficients'),
                    ('odds_ratios','Odds ratios'),('equation','Binary logistic regression equation')]:
                control=QCheckBox(label); control.setChecked(self.initial[key])
                self.controls[key]=control; form.addRow(control)
            self.combo(form,'diagnostics','Fits and diagnostics:',
                [('Do not display','none'),('Only for unusual observations','unusual'),('For all observations','all')])
        else:
            raise ValueError('Unsupported binary logistic settings section.')
        self.error=QLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True); layout.addWidget(self.error)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate); self.buttons.rejected.connect(self.reject); layout.addWidget(self.buttons)

    def combo(self,form,key,label,choices):
        control=QComboBox()
        for text,value in choices: control.addItem(text,value)
        control.setCurrentIndex(control.findData(self.initial[key]))
        self.controls[key]=control; form.addRow(label,control)

    def validate(self):
        values=dict(self.initial)
        for key,control in self.controls.items():
            if isinstance(control,QDoubleSpinBox): values[key]=control.value()/100 if key=='confidence' else control.value()
            elif isinstance(control,QComboBox): values[key]=control.currentData()
            else: values[key]=control.isChecked()
        try: self.options=settings(values)
        except (ValueError,TypeError,OverflowError) as exc: self.error.setText(str(exc)); return
        self.accept()


class BinaryLogisticDialog(ProcedureDialog):
    def __init__(self,window):
        specs=[dict(key='response_index',label='Response:',kinds=('number','text')),
            dict(key='trials_index',label='Number of trials:',multiple=True,minimum=0,maximum=1,kinds=('number',)),
            dict(key='continuous_indices',label='Continuous predictors:',multiple=True,minimum=0,kinds=('number',)),
            dict(key='categorical_indices',label='Categorical predictors:',multiple=True,minimum=0,kinds=('number','text'))]
        super().__init__(window,'Fit Binary Logistic Model',window.presenter.worksheet,specs,(),
            'Fit a logit model using individual binary responses or event/trial counts.')
        self.window=window; self.options=settings(); self.terms=None; self.signature=None; self.entry=None
        mode_row=QHBoxLayout(); mode_row.addWidget(QLabel('Response format:'))
        self.response_format=QComboBox()
        self.response_format.addItem('Response in binary response format','individual')
        self.response_format.addItem('Response in event/trial format','grouped')
        mode_row.addWidget(self.response_format,1); self.layout().insertLayout(1,mode_row)
        event_row=QHBoxLayout(); event_row.addWidget(QLabel('Response event:'))
        self.event=QComboBox(); event_row.addWidget(self.event,1)
        self.layout().insertLayout(self.layout().count()-2,event_row)
        self.option_buttons={}; option_row=QHBoxLayout()
        for name in ('Model','Options','Graphs','Results'):
            button=QPushButton(name+'…'); button.setAutoDefault(False)
            button.clicked.connect(lambda checked=False,name=name:self.configure(name))
            self.option_buttons[name]=button; option_row.addWidget(button)
        self.layout().insertLayout(self.layout().count()-2,option_row)
        self.model_label=QLabel('Model: main effects'); self.model_label.setWordWrap(True)
        self.layout().insertWidget(self.layout().count()-2,self.model_label)
        self.response_format.currentIndexChanged.connect(self.update_mode)
        self.controls['response_index'].textChanged.connect(self.update_events)
        self.update_mode(); self.restore_previous()

    def update_mode(self):
        grouped=self.response_format.currentData()=='grouped'
        self.controls['trials_index'].setEnabled(grouped); self.event.setEnabled(not grouped)
        self.selectors[0]['kinds']=('number',) if grouped else ('number','text')
        # Force refresh of the available variable list when the response role is active.
        if self.active_key=='response_index': self.active_key=None; self.activate('response_index')
        for label in self.findChildren(QLabel):
            if label.text() in ('Response:','Number of events:'): label.setText('Number of events:' if grouped else 'Response:')
        if self.active_key=='trials_index' and not grouped: self.activate('response_index')
        self.update_events()

    def update_events(self):
        old=self.event.currentData(); self.event.clear(); self.event.addItem('Use default response event',None)
        try:
            indices=resolve_variables(self.controls['response_index'].text(),self.worksheet,('number','text'))
            if len(indices)!=1: return
            column=self.worksheet.columns[indices[0]]
            levels=[]
            for value in column.values:
                if value is not None and value not in levels: levels.append(value)
            if len(levels)>2: return
            for value in levels: self.event.addItem(str(value),value)
            self.select_event(old)
        except (ValueError,IndexError,TypeError): pass

    def select_event(self,event):
        for index in range(self.event.count()):
            candidate=self.event.itemData(index)
            if type(candidate) is type(event) and candidate==event:
                self.event.setCurrentIndex(index); return
        self.event.setCurrentIndex(0)

    def values(self):
        grouped=self.response_format.currentData()=='grouped'; values={}
        for spec in self.selectors:
            key=spec['key']
            if key=='trials_index' and not grouped: values[key]=None; continue
            kinds=('number',) if grouped and key=='response_index' else spec['kinds']
            indices=resolve_variables(self.controls[key].text(),self.worksheet,kinds)
            if key in ('response_index','trials_index'):
                if len(indices)!=1: raise ValueError(('Number of trials' if key=='trials_index' else 'Response')+': select one column.')
                values[key]=indices[0]
            else: values[key]=indices
        values['event']=None if grouped else self.event.currentData()
        return values

    def roles(self):
        values=self.values(); indices=values['categorical_indices']+values['continuous_indices']
        reserved=[values['response_index']]+([values['trials_index']] if values['trials_index'] is not None else [])
        if not 1<=len(indices)<=8 or len(set(indices+reserved))!=len(indices+reserved):
            raise ValueError('Choose 1–8 distinct predictors and separate response/trials columns.')
        signature=(tuple(values['categorical_indices']),tuple(values['continuous_indices']))
        if self.signature!=signature:
            self.terms=[[i] for i in range(len(indices))]; self.signature=signature
        self.describe_model(indices)
        return values,indices

    def describe_model(self,indices):
        self.model_label.setText('Model: '+' + '.join('*'.join(self.worksheet.columns[indices[i]].name for i in term) for term in self.terms))

    def configure(self,name):
        try:
            if name=='Model':
                values,indices=self.roles()
                dialog=ModelTermsDialog(self,[format_variable_reference(i,self.worksheet) for i in indices],self.terms)
                dialog.setWindowTitle('Binary Logistic Regression: Model')
                if dialog.exec(): self.terms=dialog.terms; self.describe_model(indices)
            else:
                dialog=LogisticSettingsDialog(self,name,self.options)
                if dialog.exec(): self.options=dialog.options
            self.error.clear()
        except (ValueError,TypeError,IndexError) as exc: self.error.setText(str(exc))

    def restore_previous(self):
        p=self.window.presenter; project=p.native_project
        worksheet_id=project.worksheet_ids[project.active_index] if project else None
        for entry in reversed(p.history):
            recipe=entry.get('recipe',{})
            if entry.get('source_unavailable') or recipe.get('action')!='fit_binary_logistic': continue
            try:
                if hasattr(p,'result_worksheet'):
                    if p.result_worksheet(entry) is not self.worksheet: continue
                elif entry.get('worksheet_id')!=worksheet_id or entry.get('worksheet_name')!=p.worksheet.name: continue
                values=recipe['parameters']; categorical=values['categorical_indices']; continuous=values['continuous_indices']
                indices=categorical+continuous; terms=validate_terms(values['terms'],len(indices)); options=settings(values['options'])
                rendered={key:format_variable_list(values[key],self.worksheet) for key in ('categorical_indices','continuous_indices')}
                rendered['response_index']=format_variable_reference(values['response_index'],self.worksheet)
                trials=values.get('trials_index'); rendered['trials_index']='' if trials is None else format_variable_reference(trials,self.worksheet)
                for key,text in rendered.items(): self.controls[key].setText(text)
                self.response_format.setCurrentIndex(0 if trials is None else 1)
                self.update_events(); self.select_event(values.get('event'))
                self.terms=[list(term) for term in terms]; self.signature=(tuple(categorical),tuple(continuous)); self.options=options
                self.describe_model(indices)
            except (ValueError,TypeError,KeyError,IndexError): continue
            break

    def validate(self):
        try:
            values,indices=self.roles()
            self.entry=self.window.presenter.fit_binary_logistic(**values,terms=self.terms,options=self.options)
            self.window.refresh(); self.window.show_result(self.entry)
        except (ValueError,TypeError,IndexError,ArithmeticError) as exc: self.error.setText(str(exc)); return
        self.accept()
