"""Original desktop Graph Builder: named drag/drop roles and isolated live previews."""
import copy
import json
from PySide6.QtCore import Qt,QMimeData,QTimer,QSize
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QListWidget,QListWidgetItem,
    QLineEdit,QPushButton,QGroupBox,QSplitter,QWidget,QScrollArea,QDialogButtonBox,QCheckBox,QSpinBox,QDoubleSpinBox,QComboBox,QAbstractItemView)
from .graph_builder import TYPES,DEFAULTS,validate_mapping,compute_builder
from .variable_dialogs import format_variable_reference
from .modern_icons import tool_icon

MIME='application/x-statcraft-columns'


class ColumnList(QListWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);self.setDragEnabled(True)

    def startDrag(self,actions):
        indices=[item.data(Qt.ItemDataRole.UserRole) for item in self.selectedItems()]
        if not indices:return
        mime=QMimeData();mime.setData(MIME,json.dumps(indices).encode('utf-8'));drag=QDrag(self);drag.setMimeData(mime);drag.exec(Qt.DropAction.CopyAction)


class RoleList(ColumnList):
    def __init__(self,role,owner):
        super().__init__();self.role=role;self.owner=owner;self.setAcceptDrops(True);self.setMinimumHeight(64);self.setMaximumHeight(100)

    def focusInEvent(self,event):
        self.owner.active_role=self.role;super().focusInEvent(event)

    def dragEnterEvent(self,event):
        if event.mimeData().hasFormat(MIME):event.acceptProposedAction()
        else:event.ignore()

    def dragMoveEvent(self,event):self.dragEnterEvent(event)

    def dropEvent(self,event):
        try:
            data=bytes(event.mimeData().data(MIME))
            if len(data)>8192:raise ValueError('Too many dropped columns.')
            values=json.loads(data.decode('utf-8'))
            if self.owner.assign_columns(self.role,values):event.acceptProposedAction()
            else:event.ignore()
        except (ValueError,UnicodeError,TypeError):self.owner.show_error('Drop valid columns from this worksheet.');event.ignore()

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace):self.owner.remove_selected(self.role);event.accept();return
        super().keyPressEvent(event)


class GraphBuilderDialog(QDialog):
    def __init__(self,parent,worksheet,parameters=None,lock_variables=False):
        self.setSizeGripEnabled(True)
        super().__init__(parent);self.worksheet=worksheet;self.lock_variables=lock_variables;self.setWindowTitle('Graph Builder');self.resize(1180,740)
        p=copy.deepcopy(parameters or {});self.graph_type=p.get('graph_type','histogram');self.mapping={key:list(p.get(key,[])) for key in ('response_indices','group_indices')};self.mapping['x_index']=[] if p.get('x_index') is None else [p['x_index']]
        self.active_role='response_indices';self.parameters=None;self.preview_entry=None;self.preview_chart=None;self.preview_frame=None;self._loading=True
        outer=QVBoxLayout(self);split=QSplitter();outer.addWidget(split,1)
        left=QWidget();ll=QVBoxLayout(left);ll.setContentsMargins(0,0,0,0);ll.addWidget(QLabel('Worksheet columns'))
        self.search=QLineEdit();self.search.setPlaceholderText('Find a column');self.search.textChanged.connect(self.filter_columns);ll.addWidget(self.search)
        self.available=ColumnList();self.available.setMinimumWidth(190);ll.addWidget(self.available,2)
        for index,column in enumerate(worksheet.columns):
            item=QListWidgetItem(format_variable_reference(index,worksheet));item.setData(Qt.ItemDataRole.UserRole,index);item.setToolTip(item.text()+' — '+column.kind);self.available.addItem(item)
        self.available.itemDoubleClicked.connect(lambda item:self.assign_columns(self.active_role,[item.data(Qt.ItemDataRole.UserRole)]))
        self.add_button=QPushButton('Add selected →');self.add_button.clicked.connect(self.add_selected);ll.addWidget(self.add_button);ll.addWidget(QLabel('Graph type'))
        self.gallery=QListWidget();self.gallery.setIconSize(QSize(22,22));self.gallery.setMinimumHeight(200)
        for kind,title in TYPES.items():
            item=QListWidgetItem(tool_icon({'individual_value':'individual','interval_plot':'interval'}.get(kind,kind)),title);item.setData(Qt.ItemDataRole.UserRole,kind);self.gallery.addItem(item)
            if kind==self.graph_type:self.gallery.setCurrentItem(item)
        self.gallery.currentItemChanged.connect(self.change_type);ll.addWidget(self.gallery,2);split.addWidget(left)
        center=QWidget();cl=QVBoxLayout(center);cl.setContentsMargins(4,0,4,0);role_row=QHBoxLayout();self.roles={};self.role_groups={};self.role_buttons={}
        for key,title in (('response_indices','Y variables'),('x_index','X variable'),('group_indices','Categorical variables')):
            group=QGroupBox(title);layout=QVBoxLayout(group);role=RoleList(key,self);self.roles[key]=role;self.role_groups[key]=group;layout.addWidget(role)
            button=QPushButton('Remove selected');button.clicked.connect(lambda checked=False,key=key:self.remove_selected(key));layout.addWidget(button);self.role_buttons[key]=button;role_row.addWidget(group)
        cl.addLayout(role_row);cl.addWidget(QLabel('Drag columns into a role, or select a role and use Add selected.'))
        self.preview_scroll=QScrollArea();self.preview_scroll.setWidgetResizable(True);cl.addWidget(self.preview_scroll,1);split.addWidget(center)
        right=QWidget();rl=QVBoxLayout(right);rl.setContentsMargins(0,0,0,0);rl.addWidget(QLabel('Graph Options'));form=QFormLayout();self.option_fields={}
        def field(key,label,control):self.option_fields[key]=(label,control);form.addRow(label,control);return control
        options=dict(DEFAULTS,**p.get('options',{}))
        self.title=field('title','Title:',QLineEdit(options['title']));self.title.setMaxLength(145)
        self.bins=field('bins','Intervals:',QSpinBox());self.bins.setRange(2,200);self.bins.setValue(options['bins'])
        self.fit=field('fit','',QCheckBox('Normal fit'));self.fit.setChecked(options['fit'])
        self.stack=field('stack','',QCheckBox('Stack dots'));self.stack.setChecked(options['stack'])
        self.order=field('variable_position','Variable order:',QComboBox());self.order.addItem('Outermost','outer');self.order.addItem('Innermost','inner');self.order.setCurrentIndex(self.order.findData(options['variable_position']))
        self.arrangement=field('layout','Display:',QComboBox());self.arrangement.addItem('Combined','combined');self.arrangement.addItem('Separate panels','panels');self.arrangement.setCurrentIndex(self.arrangement.findData(options['layout']))
        self.confidence=field('confidence','Confidence:',QDoubleSpinBox());self.confidence.setRange(50.001,99.999);self.confidence.setDecimals(3);self.confidence.setSuffix('%');self.confidence.setValue(options['confidence']*100)
        self.pooled=field('pooled','',QCheckBox('Pool error within response'));self.pooled.setChecked(options['pooled'])
        self.bonferroni=field('bonferroni','',QCheckBox('Bonferroni within response'));self.bonferroni.setChecked(options['bonferroni'])
        rl.addLayout(form);rl.addStretch();split.addWidget(right);split.setSizes([220,700,240]);self.form=form
        for control in (self.bins,self.confidence):control.valueChanged.connect(self.schedule_preview)
        for control in (self.fit,self.stack,self.pooled,self.bonferroni):control.toggled.connect(self.schedule_preview)
        for control in (self.order,self.arrangement):control.currentIndexChanged.connect(self.schedule_preview)
        self.title.textChanged.connect(self.schedule_preview)
        self.error=QLabel();self.error.setWordWrap(True);outer.addWidget(self.error)
        bottom=QHBoxLayout();self.reset_button=QPushButton('Clear mappings');self.reset_button.clicked.connect(self.clear_mappings);bottom.addWidget(self.reset_button);bottom.addStretch()
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Create');self.buttons.accepted.connect(self.validate);self.buttons.rejected.connect(self.reject);bottom.addWidget(self.buttons);outer.addLayout(bottom)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(180);self.timer.timeout.connect(self.update_preview)
        self._loading=False;self.configure_type();self.refresh_roles();self.update_preview()
        if lock_variables:
            for widget in (self.available,self.gallery,self.add_button,self.reset_button,*self.roles.values(),*self.role_buttons.values()):widget.setEnabled(False)

    def filter_columns(self,text):
        self.available.clearSelection()
        for i in range(self.available.count()):self.available.item(i).setHidden(text.casefold() not in self.available.item(i).text().casefold())

    def show_error(self,message):self.error.setText(message);self.error.setStyleSheet('color:#b3261e;')

    def allowed_kinds(self,role):
        return ('number','text') if role=='group_indices' or role=='response_indices' and self.graph_type=='bar_chart' else ('number','date') if role=='x_index' and self.graph_type=='time_series' else ('number',)

    def maximum(self,role):
        if role=='x_index':return 1
        if role=='group_indices':return 0 if self.graph_type in ('bar_chart','matrix_plot') else 1 if self.graph_type in ('scatter','histogram','time_series') else 4
        return 1 if self.graph_type in ('scatter','bar_chart') else 8 if self.graph_type in ('time_series','matrix_plot') else 16

    def assign_columns(self,role,indices):
        if self.lock_variables:return False
        if role not in self.roles or not isinstance(indices,list) or not indices or any(type(i) is not int or not 0<=i<len(self.worksheet.columns) for i in indices):self.show_error('Choose valid worksheet columns.');return False
        if any(self.worksheet.columns[i].kind not in self.allowed_kinds(role) for i in indices):self.show_error('That column type is not valid for this role.');return False
        combined=list(dict.fromkeys(self.mapping[role]+indices))
        if len(combined)>self.maximum(role):self.show_error('This role accepts at most '+str(self.maximum(role))+' column(s).');return False
        self.mapping[role]=combined
        for key in self.mapping:
            if key!=role:self.mapping[key]=[i for i in self.mapping[key] if i not in indices]
        self.active_role=role;self.refresh_roles();self.schedule_preview();return True

    def add_selected(self):self.assign_columns(self.active_role,[item.data(Qt.ItemDataRole.UserRole) for item in self.available.selectedItems()])

    def remove_selected(self,role):
        if self.lock_variables:return
        selected={item.data(Qt.ItemDataRole.UserRole) for item in self.roles[role].selectedItems()};self.mapping[role]=[i for i in self.mapping[role] if i not in selected];self.refresh_roles();self.schedule_preview()

    def clear_mappings(self):
        if self.lock_variables:return
        self.mapping=dict(response_indices=[],x_index=[],group_indices=[]);self.refresh_roles();self.schedule_preview()

    def refresh_roles(self):
        for key,widget in self.roles.items():
            widget.clear()
            for index in self.mapping[key]:
                item=QListWidgetItem(format_variable_reference(index,self.worksheet));item.setData(Qt.ItemDataRole.UserRole,index);widget.addItem(item)

    def set_graph_type(self,kind):
        if kind not in TYPES:raise ValueError('Unsupported graph type.')
        for i in range(self.gallery.count()):
            if self.gallery.item(i).data(Qt.ItemDataRole.UserRole)==kind:self.gallery.setCurrentRow(i);return

    def change_type(self,current,previous):
        if self._loading or current is None:return
        self.graph_type=current.data(Qt.ItemDataRole.UserRole)
        for key in self.mapping:self.mapping[key]=[i for i in self.mapping[key] if self.worksheet.columns[i].kind in self.allowed_kinds(key)][:self.maximum(key)]
        if self.graph_type not in ('scatter','time_series'):self.mapping['x_index']=[]
        self.configure_type();self.refresh_roles();self.schedule_preview()

    def configure_type(self):
        kind=self.graph_type
        if self.active_role=='x_index' and kind not in ('scatter','time_series') or self.active_role=='group_indices' and kind in ('bar_chart','matrix_plot'):self.active_role='response_indices'
        self.role_groups['response_indices'].setTitle('Categorical variable' if kind=='bar_chart' else 'Continuous variables' if kind not in ('scatter',) else 'Y variable')
        self.role_groups['x_index'].setVisible(kind in ('scatter','time_series'));self.role_groups['x_index'].setTitle('X / time variable (optional)' if kind=='time_series' else 'X variable')
        self.role_groups['group_indices'].setVisible(kind not in ('bar_chart','matrix_plot'))
        for key,(label,control) in self.option_fields.items():
            visible=key=='title' or key=='bins' and kind in ('histogram','dotplot') or key=='fit' and kind in ('histogram','scatter') or key=='stack' and kind=='dotplot' or key in ('variable_position','layout') and kind in ('histogram','boxplot','dotplot','individual_value','interval_plot') or key in ('confidence','pooled','bonferroni') and kind=='interval_plot'
            control.setVisible(visible)
            if self.form.labelForField(control):self.form.labelForField(control).setVisible(visible)
        self.fit.setText('Linear regression fit' if kind=='scatter' else 'Normal fit')

    def values(self):
        options=dict(title=self.title.text(),bins=self.bins.value(),fit=self.fit.isChecked(),stack=self.stack.isChecked(),variable_position=self.order.currentData(),layout=self.arrangement.currentData(),confidence=self.confidence.value()/100,pooled=self.pooled.isChecked(),bonferroni=self.bonferroni.isChecked())
        return validate_mapping(self.graph_type,self.mapping['response_indices'],self.mapping['x_index'][0] if self.mapping['x_index'] else None,self.mapping['group_indices'],options)

    def schedule_preview(self,*args):
        if self._loading:return
        self.parameters=None;self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False);self.timer.start()

    def update_preview(self):
        self.timer.stop();self.preview_entry=None;self.preview_chart=None;self.preview_frame=None
        try:
            parameters,title,result=compute_builder(self.worksheet,**self.values());entry=dict(title=title,result=result)
            from .modern_charts import ChartWidget
            from .modern_expanded_charts import ExpandedChartWidget
            from .graph_frame import GraphFrame
            chart=ExpandedChartWidget(entry) if result.get('graph')=='expanded' else ChartWidget(entry)
            if chart.error:raise ValueError(chart.error)
            frame=GraphFrame(chart,entry);self.preview_scroll.setWidget(frame);frame.grab()
            if chart.error:raise ValueError(chart.error)
            self.preview_entry=entry;self.preview_chart=chart;self.preview_frame=frame;self.parameters=parameters
            self.error.setStyleSheet('');self.error.setText('Preview updates when variables or options change. Create adds one tracked graph to the project.')
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True);return True
        except (ValueError,TypeError,KeyError,IndexError,ArithmeticError) as exc:
            self.parameters=None;empty=QLabel('Add compatible columns to see the graph.');empty.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview_scroll.setWidget(empty);self.show_error(str(exc));self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False);return False

    def settings(self):return copy.deepcopy(self.parameters if self.parameters is not None else self.values())

    def validate(self):
        if self.update_preview():self.accept();return True
        return False
