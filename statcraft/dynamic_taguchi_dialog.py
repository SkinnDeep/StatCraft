"""Original dynamic Taguchi form informed by authenticated RT_DIALOG5672.

Response columns are explicitly paired with signal constants. This wide data
layout is an authored workflow; native signal-column metadata/runtime parity
and the native mean-at-signal reference mode are not claimed.
"""
import math
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView
from .variable_dialogs import ProcedureDialog,format_variable_list,format_variable_reference,resolve_variables
from .doe_analysis_dialogs import _verified_factors


class BuildAnalyzeDynamicTaguchiDialog(ProcedureDialog):
    def __init__(self,worksheet,parent=None):
        super().__init__(parent,'Analyze Taguchi Design (Dynamic)',worksheet,
            selectors=(
                {'key':'response_indices','label':'Response data are in:','multiple':True,'minimum':2,'maximum':40},
                {'key':'factor_indices','label':'Control factors:','multiple':True,'minimum':1,'maximum':8,'kinds':('number','text')}),
            fields=(
                {'key':'reference_method','label':'Dynamic signal-to-noise ratio:','choices':['Fit lines with no reference point','Fit all lines through a fixed reference point'],'default':'Fit lines with no reference point'},
                {'key':'reference_signal','label':'Signal reference value:','numeric':True,'default':0},
                {'key':'reference_response','label':'Response reference value:','numeric':True,'default':0},
                {'key':'adjusted','label':'','boolean':True,'text':'Use adjusted formula for signal to noise','default':False},
                {'key':'log_stdev','label':'','boolean':True,'text':'Use ln(s) for all standard deviation output','default':False},
                {'key':'confidence','label':'Confidence level (%):','numeric':True,'default':95},
                {'key':'fit_models','label':'','boolean':True,'text':'Fit main-effects models','default':True},
                {'key':'show_graphs','label':'','boolean':True,'text':'Display main effects plots','default':True},
                {'key':'show_signal_plots','label':'','boolean':True,'text':'Scatterplots of response versus signal with fitted lines','default':False}),
            note='Each worksheet row is one control-factor setting. Select response columns, then enter the signal value for each measurement below. Repeated signal values represent measurements under different noise conditions.')
        self.resize(870,780)
        self._signal_by_column={}
        self.signal_table=QTableWidget(0,2,self)
        self.signal_table.setObjectName('dynamicSignalMapping')
        self.signal_table.setHorizontalHeaderLabels(['Response column','Signal value'])
        self.signal_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.signal_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.signal_table.setMinimumHeight(130);self.signal_table.setMaximumHeight(200)
        self.signal_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.signal_table.itemChanged.connect(self._remember_signal)
        layout=self.layout();index=layout.indexOf(self.error)
        label=QLabel('Signal values, in response-column order:');layout.insertWidget(index,label);layout.insertWidget(index+1,self.signal_table)
        limitation=QLabel('Average-response-at-signal reference and interaction models are not available. Signal scatterplots show at most the first 24 complete runs.')
        limitation.setWordWrap(True);limitation.setObjectName('secondary');layout.insertWidget(index+2,limitation)
        self.controls['response_indices'].textChanged.connect(self.sync_signal_table)
        self.controls['reference_method'].currentIndexChanged.connect(self._reference_changed)
        self._reference_changed()
        known=_verified_factors(worksheet,'statcraft-catalog-design-v1',{'taguchi'})
        if known and 1<=len(known[0])<=8 and all(worksheet.columns[index].kind in ('number','text') for index in known[0]):
            self.controls['factor_indices'].setText(format_variable_list(known[0],worksheet))

    def _reference_changed(self,*args):
        fixed=self.controls['reference_method'].currentIndex()==1
        for key in ('reference_signal','reference_response'):self.controls[key].setEnabled(fixed)

    def _remember_signal(self,item):
        if item.column()!=1:return
        column=self.signal_table.item(item.row(),0)
        if column is not None:self._signal_by_column[column.data(Qt.ItemDataRole.UserRole)]=item.text()

    def sync_signal_table(self,*args):
        try:indices=resolve_variables(self.controls['response_indices'].text(),self.worksheet)
        except ValueError:return
        self.signal_table.blockSignals(True)
        try:
            self.signal_table.setRowCount(len(indices))
            for row,index in enumerate(indices):
                label=QTableWidgetItem(format_variable_reference(index,self.worksheet));label.setData(Qt.ItemDataRole.UserRole,index)
                label.setFlags(label.flags()&~Qt.ItemFlag.ItemIsEditable);self.signal_table.setItem(row,0,label)
                self.signal_table.setItem(row,1,QTableWidgetItem(self._signal_by_column.get(index,'')))
        finally:self.signal_table.blockSignals(False)

    def set_signal_values(self,values):
        """Set explicit mapping in the current selected-response order."""
        self.sync_signal_table()
        if len(values)!=self.signal_table.rowCount():raise ValueError('Enter one signal value for each response column.')
        for row,value in enumerate(values):self.signal_table.item(row,1).setText(str(value))

    def values(self):
        # Disabled reference entries do not affect a free-intercept model.
        fixed=self.controls['reference_method'].currentIndex()==1
        saved={key:self.controls[key].text() for key in ('reference_signal','reference_response')}
        try:
            if not fixed:
                for key in saved:self.controls[key].setText('0')
            values=super().values()
        finally:
            if not fixed:
                for key,text in saved.items():self.controls[key].setText(text)
        responses=values['response_indices'];factors=values['factor_indices']
        if set(responses)&set(factors):raise ValueError('Choose separate response and control factor columns.')
        if not fixed and len(responses)<3:raise ValueError('No-reference fitting requires at least three response measurements per run.')
        if not 0<values['confidence']<100:raise ValueError('Confidence level must be between 0 and 100.')
        self.sync_signal_table();signal_values=[]
        for row,index in enumerate(responses):
            raw=self.signal_table.item(row,1).text().strip()
            try:value=float(raw)
            except (ValueError,OverflowError) as error:raise ValueError('Enter a numeric signal value for '+format_variable_reference(index,self.worksheet)+'.') from error
            if not math.isfinite(value):raise ValueError('Signal values must be finite.')
            signal_values.append(value)
        if len(set(signal_values))<2:raise ValueError('Enter at least two distinct signal values.')
        return {'response_indices':responses,'signal_values':signal_values,'factor_indices':factors,
                'options':{'reference_method':'fixed' if fixed else 'none',
                    'reference_signal':values['reference_signal'],'reference_response':values['reference_response'],
                    'adjusted':values['adjusted'],'log_stdev':values['log_stdev'],'confidence':values['confidence']/100,
                    'fit_models':values['fit_models'],'show_graphs':values['show_graphs'],'show_signal_plots':values['show_signal_plots']}}

    def validate(self):
        self.parameters=None
        super().validate()
