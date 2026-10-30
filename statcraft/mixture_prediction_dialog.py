"""Prediction entry for a selected source-bound mixture model."""
import copy
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QComboBox,QLineEdit,QSpinBox,QTableWidget,QTableWidgetItem,QHeaderView,QLabel,QDialogButtonBox
from .model import finite_number


class MixturePredictionDialog(QDialog):
    def __init__(self,worksheet,entries,parent=None):
        super().__init__(parent);self.setWindowTitle('Predict Mixture Response');self.resize(720,440)
        self.worksheet=worksheet;self.entries=list(entries);self.parameters=None
        layout=QVBoxLayout(self);form=QFormLayout();self.model=QComboBox()
        for entry in entries:self.model.addItem(entry['title']+' — '+entry['time'])
        form.addRow('Fitted mixture model:',self.model)
        self.confidence=QLineEdit('95');form.addRow('Confidence level (%):',self.confidence)
        self.row_count=QSpinBox();self.row_count.setRange(1,100);form.addRow('Prediction rows:',self.row_count);layout.addLayout(form)
        self.note=QLabel();self.note.setWordWrap(True);layout.addWidget(self.note)
        self.table=QTableWidget(1,0);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table)
        self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.row_count.valueChanged.connect(self.table.setRowCount);self.model.currentIndexChanged.connect(self._model_changed)
        self._model_changed()

    def _model_changed(self):
        if not self.entries:self.table.setColumnCount(0);self.note.setText('Analyze a mixture design before predicting.');return
        entry=self.entries[self.model.currentIndex()];params=entry['recipe']['parameters']
        self.table.clear();self.table.setColumnCount(len(params['component_indices']))
        self.table.setHorizontalHeaderLabels([self.worksheet.columns[i].name or 'C'+str(i+1) for i in params['component_indices']])
        self.note.setText(f"Enter component amounts that sum to {params['total']:g} in each row. Predictions refit the selected model with current worksheet data and retain its component bounds.")

    def values(self):
        if not self.entries:raise ValueError('Analyze a mixture design before predicting.')
        entry=self.entries[self.model.currentIndex()];rows=[]
        for row in range(self.table.rowCount()):
            values=[]
            for column in range(self.table.columnCount()):
                item=self.table.item(row,column)
                try:value=finite_number(float(item.text())) if item else None
                except (ValueError,TypeError,OverflowError):value=None
                if value is None:raise ValueError(f'Enter a finite amount for row {row+1}, component {column+1}.')
                values.append(value)
            rows.append(values)
        try:confidence=float(self.confidence.text())/100
        except (ValueError,OverflowError) as error:raise ValueError('Enter a confidence level between 0 and 100.') from error
        from .mixture_analysis import predict
        predict(entry['result'],rows,confidence)
        return {'model_recipe':copy.deepcopy(entry['recipe']),'component_rows':rows,'confidence':confidence}

    def validate(self):
        self.parameters=None
        try:self.parameters=self.values()
        except (ValueError,TypeError,IndexError) as error:self.error.setText(str(error));return
        self.error.clear();self.accept()
