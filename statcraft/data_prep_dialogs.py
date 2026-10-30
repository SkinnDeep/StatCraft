"""Typed data preparation dialogs using the shared named-variable selector."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,
    QComboBox,QCheckBox,QListWidget,QListWidgetItem,QAbstractItemView,QDialogButtonBox)
from .variable_dialogs import ProcedureDialog,format_variable_reference
from . import data_prep


def destinations(presenter):
    native=presenter.native_project
    return ['New worksheet','New project'] if native is None or getattr(native,'statcraft_owned',False) else ['New project']


def install(window, sheet, destination):
    target=data_prep.store_prepared(window.presenter,sheet,'worksheet' if destination=='New worksheet' else 'project')
    if target is window.presenter:
        window.page=0;window.refresh()
    else:
        from .modern_app import ModernWindow
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance()
        if not hasattr(app,'_prepared_windows'):app._prepared_windows=[]
        child=ModernWindow(target);app._prepared_windows.append(child)
        child.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        child.destroyed.connect(lambda *args:app._prepared_windows.remove(child) if child in app._prepared_windows else None)
        child.refresh();child.showMaximized()
    return target


class ReshapeDialog(ProcedureDialog):
    def __init__(self,window,operation):
        titles={'stack':'Stack Columns','unstack':'Unstack Columns','transpose':'Transpose Columns'}
        selectors=[dict(key='indices',label='Columns to '+operation+':',multiple=True,minimum=2 if operation=='stack' else 1,kinds=('number','text','date'))]
        if operation=='unstack':selectors.append(dict(key='group_index',label='Using subscripts in:',kinds=('number','text','date')))
        fields=[dict(key='name',label='New worksheet name:',default=titles[operation].replace(' Columns','ed') if operation!='transpose' else 'Transposed'),
                dict(key='destination',label='Store in:',choices=destinations(window.presenter))]
        if operation=='stack':fields.append(dict(key='omit_missing',label='Missing data:',boolean=True,text='Omit missing values',default=False))
        if operation=='unstack':fields.append(dict(key='include_missing',label='Subscripts:',boolean=True,text='Include missing subscript group',default=False))
        super().__init__(window,titles[operation],window.presenter.worksheet,selectors,fields,
            'Select variables from the list or type their C numbers. Source data are retained. Derived columns contain values without source formulas or cell formatting.')
        self.window=window;self.operation=operation;self.prepared=None

    def validate(self):
        try:
            values=self.values();destination=values.pop('destination')
            fn={'stack':data_prep.stack_columns,'unstack':data_prep.unstack_columns,'transpose':data_prep.transpose}[self.operation]
            sheet=fn(self.worksheet,**values)
            self.prepared=install(self.window,sheet,destination)
        except (ValueError,TypeError,IndexError) as exc:self.error.setText(str(exc));return
        self.accept()


class CombineDialog(QDialog):
    def __init__(self,window,operation):
        super().__init__(window);self.window=window;self.operation=operation;self.prepared=None
        self.sheets=list(window.presenter.native_project.worksheets) if window.presenter.native_project else [window.presenter.worksheet]
        title='Stack Worksheets' if operation=='stack_worksheets' else 'Merge Worksheets'
        self.setWindowTitle(title);self.resize(660,440);layout=QVBoxLayout(self)
        note=QLabel('Source worksheets are retained. Matched columns must have the same data type.');note.setWordWrap(True);layout.addWidget(note)
        form=QFormLayout();self.controls={}
        self.selection=QListWidget();self.selection.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        if operation=='stack_worksheets':
            layout.addWidget(QLabel('Worksheets to stack (project order):'));layout.addWidget(self.selection)
            for i,s in enumerate(self.sheets):
                item=QListWidgetItem(str(i+1)+'  '+s.name);item.setData(Qt.ItemDataRole.UserRole,i);self.selection.addItem(item)
            self.combo(form,'match','Match columns by:',['Position','Name'])
            self.source=QCheckBox('Store source worksheet names');self.source.setChecked(True);form.addRow(self.source)
        else:
            for role,label in [('left','First worksheet:'),('right','Second worksheet:')]:
                combo=self.combo(form,role,label,[str(i+1)+'  '+s.name for i,s in enumerate(self.sheets)])
                self.combo(form,role+'_key','Key column:',[])
                combo.currentIndexChanged.connect(lambda index,role=role:self.fill_keys(role,index))
                self.fill_keys(role,0)
            self.controls['left'].setCurrentIndex(next(i for i,s in enumerate(self.sheets) if s is window.presenter.worksheet))
            self.controls['right'].setCurrentIndex(1 if len(self.sheets)>1 else 0)
            self.combo(form,'how','Rows to include:',['All rows from first worksheet','Only matching rows','All rows from both worksheets','Combine side by side (row order)'])
            self.controls['how'].currentIndexChanged.connect(self.merge_mode)
            hint=QLabel('Key merges require unique nonmissing keys. Missing keys never match. Repeated column names receive numbered suffixes.');hint.setWordWrap(True);form.addRow(hint)
        self.controls['name']=QLineEdit('Stacked worksheets' if operation=='stack_worksheets' else 'Merged')
        form.addRow('New worksheet name:',self.controls['name'])
        self.combo(form,'destination','Store in:',destinations(window.presenter));layout.addLayout(form)
        self.error=QLabel();self.error.setWordWrap(True);self.error.setStyleSheet('color:#a02020');layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def combo(self,form,key,label,choices):
        c=QComboBox();c.addItems(choices);form.addRow(label,c);self.controls[key]=c;return c

    def fill_keys(self,role,index):
        combo=self.controls[role+'_key'];combo.clear()
        if 0<=index<len(self.sheets):
            s=self.sheets[index];combo.addItems([format_variable_reference(i,s) for i in range(len(s.columns))])

    def merge_mode(self,index):
        for role in ('left','right'):self.controls[role+'_key'].setEnabled(index!=3)

    def validate(self):
        try:
            c=self.controls;name=c['name'].text()
            if self.operation=='stack_worksheets':
                sheets=[self.sheets[self.selection.row(item)] for item in self.selection.selectedItems()]
                sheet=data_prep.stack_worksheets(sheets,name,('position','name')[c['match'].currentIndex()],self.source.isChecked())
            else:
                a=c['left'].currentIndex();b=c['right'].currentIndex()
                if a==b:raise ValueError('Choose two different worksheets.')
                sheet=data_prep.merge_worksheets(self.sheets[a],self.sheets[b],c['left_key'].currentIndex(),c['right_key'].currentIndex(),name,('left','inner','full','position')[c['how'].currentIndex()])
            self.prepared=install(self.window,sheet,c['destination'].currentText())
        except (ValueError,TypeError,IndexError) as exc:self.error.setText(str(exc));return
        self.accept()


def open_dialog(window,operation):
    window._commit_editor()
    dialog=CombineDialog(window,operation) if operation in ('stack_worksheets','merge') else ReshapeDialog(window,operation)
    dialog.exec()
