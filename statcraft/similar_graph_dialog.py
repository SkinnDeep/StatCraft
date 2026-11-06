"""Editable Make Similar Graph setup with explicit, tracked source recipes.

This is an original workflow. Native dialog/default parity remains unverified.
"""
import copy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QTableWidgetItem, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTableWidget,
    QHeaderView, QDialogButtonBox)
from .recipes import columns, fingerprints, run
from .compositions import appearance_from_entry, validate_appearance
from .variable_dialogs import (ProcedureDialog, ScatterDialog,
    format_variable_list, format_variable_reference, resolve_variables)


_ACTIONS = ('graph_builder','categorical_points','dotplot_graphs','boxplot_graphs','histogram_graphs','graph', 'scatter_plot', 'expanded_graph')


def supports_similar(entry):
    if not isinstance(entry, dict) or entry.get('origin') != 'statcraft' or entry.get('source_unavailable'):
        return False
    try:
        recipe = entry.get('recipe')
        columns(recipe)
        return recipe['action'] in _ACTIONS
    except (ValueError, TypeError, KeyError):
        return False


def _source_recipe(entry, worksheet):
    if isinstance(entry,dict) and entry.get('source_unavailable'):raise ValueError(entry['source_unavailable'])
    if not supports_similar(entry):
        raise ValueError('Make Similar Graph requires a supported tracked graph recipe.')
    recipe = copy.deepcopy(entry['recipe'])
    fingerprints(worksheet, columns(recipe))
    return recipe


def _retain_control(dialog):
    dialog.retain_appearance = QCheckBox('Retain graph appearance (annotations, scales and object styles)')
    dialog.retain_appearance.setChecked(True)
    dialog.layout().insertWidget(dialog.layout().count()-1, dialog.retain_appearance)


def _selector(key, label, multiple=False, minimum=1, maximum=None, kinds=('number',)):
    return dict(key=key, label=label, multiple=multiple, minimum=minimum,
                maximum=maximum, kinds=kinds)


def _numeric(key, label, default, integer=False):
    return dict(key=key, label=label, default=default, numeric=True, integer=integer)


class SimilarScatterDialog(ScatterDialog):
    def __init__(self, parent, worksheet, entry):
        recipe = _source_recipe(entry, worksheet)
        p = recipe['parameters']
        super().__init__(parent, worksheet, p['mode'])
        self.setWindowTitle('Make Similar Graph — '+self.windowTitle())
        self.source_entry = copy.deepcopy(entry)
        for column, index in ((0,p['y_index']), (1,p['x_index'])):
            self.roles.setItem(0, column, QTableWidgetItem(format_variable_reference(index,worksheet)))
        if p['group_index'] is not None:
            self.group_entry.setText(format_variable_reference(p['group_index'],worksheet))
        self.order.setCurrentText(p['order'])
        self.labels = {key:p[key] for key in ('title','x_label','y_label')}
        _retain_control(self)

    def recipes(self):
        if self.settings is None or self.pairs is None:
            raise ValueError('Accept the variable selections first.')
        return [dict(action='scatter_plot', parameters=dict(x_index=x, y_index=y, **self.settings))
                for y,x in self.pairs]

    def appearance_settings(self):
        return appearance_from_entry(self.source_entry) if self.retain_appearance.isChecked() else {}


class SimilarProcedureDialog(ProcedureDialog):
    def __init__(self, parent, worksheet, entry):
        recipe = _source_recipe(entry, worksheet)
        action, p = recipe['action'], recipe['parameters']
        selectors=[]; fields=[]; role_keys=[]
        if action == 'graph':
            method=p['method']; title=method.title()
            if method=='scatter':
                selectors=[_selector('x_index','X variable'),_selector('y_index','Y variable')]
            else:
                selectors=[_selector('indices','Variable',True,1,1)]
            if method=='histogram':
                bins=entry.get('histogram_settings',{}).get('bins',p['bins'])
                fields=[_numeric('bins','Equal-width bins',bins,True)]
        else:
            from .expanded_graphs import METHODS
            method=p['method']; spec=METHODS[method]; title=spec['label']
            if len(spec['roles'])>1:
                role_keys=['variable'+str(i) for i in range(len(spec['roles']))]
                order=([2,1,0] if len(role_keys)==3 and method!='bubble'
                    else [1,0,2] if len(role_keys)==3 else [1,0])
                selectors=[_selector(role_keys[i],spec['roles'][i]) for i in order]
            elif spec['maximum']:
                title_role=('Responses, or date axis then responses' if method=='time_series'
                    else 'Y variable, or X then Y' if method in ('line_plot','area_graph') else 'Variables')
                selectors=[_selector('indices',title_role,True,spec['minimum'],spec['maximum'],tuple(spec['kinds']))]
            if spec['group_allowed']:
                selectors.append(_selector('groups','By variable (optional)',True,0,1,('number','text')))
            if method in ('binned_scatter','marginal','matrix_plot'):
                fields.append(_numeric('bins','Bins',p['bins'],True))
            if method=='interval_plot':fields.append(_numeric('confidence','Confidence level',p['confidence']))
            if method=='distribution_plot':
                fields=[dict(key='distribution',label='Distribution',choices=['Normal','Uniform','Exponential'],default=p['distribution'])]
                for key,label,default in (('mean','Mean (Normal)',0),('stdev','Standard deviation (Normal)',1),
                        ('lower','Lower bound (Uniform)',0),('upper','Upper bound (Uniform)',1),('rate','Rate (Exponential)',1)):
                    fields.append(_numeric(key,label,p['parameters'].get(key,default)))
        super().__init__(parent,'Make Similar Graph — '+title,worksheet,selectors,fields,
            'Original variable roles and settings are preloaded. Change variables to create a new graph from this worksheet.')
        self.source_recipe=recipe; self.source_entry=copy.deepcopy(entry); self.role_keys=role_keys
        values=copy.deepcopy(p)
        if action=='graph' and method=='scatter':values.update(x_index=p['indices'][0],y_index=p['indices'][1])
        if role_keys:values.update({key:p['indices'][i] for i,key in enumerate(role_keys)})
        values['groups']=[] if p.get('group_index') is None else [p['group_index']]
        for spec in selectors:
            value=values[spec['key']]
            self.controls[spec['key']].setText(format_variable_list(value if isinstance(value,list) else [value],worksheet))
        _retain_control(self)

    def recipes(self):
        values=self.values(); action=self.source_recipe['action']; p=copy.deepcopy(self.source_recipe['parameters'])
        if action=='graph':
            p['indices']=([values['x_index'],values['y_index']] if p['method']=='scatter' else values['indices'])
            if p['method']=='histogram':
                if not 1<=values['bins']<=1000:raise ValueError('Equal-width bins must lie between 1 and 1000.')
                p['bins']=min(200,values['bins'])
        else:
            p['indices']=[values[key] for key in self.role_keys] if self.role_keys else values.get('indices',[])
            p['group_index']=next(iter(values.get('groups',[])),None)
            for key in ('bins','confidence','distribution'):
                if key in values:p[key]=values[key]
            if p['method']=='distribution_plot':
                names={'Normal':('mean','stdev'),'Uniform':('lower','upper'),'Exponential':('rate',)}[p['distribution']]
                p['parameters']={name:values[name] for name in names}
        recipe=dict(action=action,parameters=p); columns(recipe)
        return [recipe]

    def appearance_settings(self):
        appearance=appearance_from_entry(self.source_entry) if self.retain_appearance.isChecked() else {}
        if self.source_recipe['action']=='graph' and self.source_recipe['parameters']['method']=='histogram':
            bins=self.values()['bins']
            if bins>200 or 'histogram_settings' in appearance:
                if bins<2:raise ValueError('Custom histogram settings require at least 2 bins.')
                appearance.setdefault('histogram_settings',{})['bins']=bins
        return validate_appearance(appearance)

    def validate(self):
        try:
            self.parameters=self.values(); self.recipes(); self.appearance_settings()
        except (ValueError,TypeError,OverflowError) as exc:
            self.error.setText(str(exc)); return
        self.accept()


def create_options_dialog(parent, worksheet, entry):
    recipe=_source_recipe(entry,worksheet)
    if recipe['action']=='graph_builder':
        from .graph_builder_dialog import GraphBuilderDialog
        dialog=GraphBuilderDialog(parent,worksheet,parameters=recipe['parameters'],lock_variables=True)
        dialog.retain_appearance=QCheckBox(dialog)
        dialog.recipes=lambda:[{'action':'graph_builder','parameters':dialog.settings()}]
        dialog.appearance_settings=lambda:appearance_from_entry(entry)
        return dialog
    if recipe['action'] in ('categorical_points','dotplot_graphs','boxplot_graphs','histogram_graphs'):
        from .graph_presentation import graph_presentation
        if recipe['action']=='categorical_points':
            from .categorical_points_dialogs import CategoricalPlotDialog
            dialog=CategoricalPlotDialog(parent,worksheet,parameters=recipe['parameters'],lock_variables=True)
            presentation=graph_presentation(entry);dialog.axis_limits={key:presentation[key] for key in ('y_min','y_max')}
        elif recipe['action']=='dotplot_graphs':
            from .dotplot_dialogs import DotplotDialog
            dialog=DotplotDialog(parent,worksheet,parameters=recipe['parameters'],lock_variables=True)
            presentation=graph_presentation(entry);dialog.axis_limits={key:presentation[key] for key in ('x_min','x_max')}
        elif recipe['action']=='boxplot_graphs':
            from .boxplot_dialogs import BoxplotDialog
            dialog=BoxplotDialog(parent,worksheet,parameters=recipe['parameters'],lock_variables=True)
            presentation=graph_presentation(entry);dialog.axis_limits={key:presentation[key] for key in ('y_min','y_max')}
        else:
            from .histogram_dialogs import HistogramDialog
            dialog=HistogramDialog(parent,worksheet,recipe['parameters']['variant'],parameters=recipe['parameters'],lock_variables=True)
        dialog.retain_appearance=QCheckBox(dialog)
        dialog.recipes=lambda:[{'action':recipe['action'],'parameters':dialog.settings()}]
        def appearance():
            result=appearance_from_entry(entry)
            if dialog.presentation_settings():
                presentation=graph_presentation(entry);presentation.update(dialog.presentation_settings())
                result['graph_presentation']=presentation
            return result
        dialog.appearance_settings=appearance
        return dialog
    cls=SimilarScatterDialog if recipe['action']=='scatter_plot' else SimilarProcedureDialog
    return cls(parent,worksheet,entry)


def _roles(recipe):
    """Each original occurrence keeps its role, including repeated columns."""
    action,p=recipe['action'],recipe['parameters']; roles=[]
    if action=='graph_builder':
        kinds=('number','text') if p['graph_type']=='bar_chart' else ('number',)
        roles=[('Graph variable '+str(i+1),'response_indices',i,kinds) for i in range(len(p['response_indices']))]
        if p['x_index'] is not None:roles.append(('X variable','x_index',None,('number','date') if p['graph_type']=='time_series' else ('number',)))
    elif action in ('categorical_points','dotplot_graphs','boxplot_graphs','histogram_graphs'):
        roles=[('Graph variable '+str(i+1),'response_indices',i,('number',)) for i in range(len(p['response_indices']))]
    elif action=='scatter_plot':
        roles=[('Y variable','y_index',None,('number',)),('X variable','x_index',None,('number',))]
    elif action=='graph':
        labels=['X variable','Y variable'] if p['method']=='scatter' else ['Variable']
        roles=[(label,'indices',i,('number',)) for i,label in enumerate(labels)]
    else:
        from .expanded_graphs import METHODS
        spec=METHODS[p['method']]
        for i in range(len(p['indices'])):
            label=spec['roles'][i] if len(spec['roles'])>1 else 'Variable '+str(i+1)
            # Date axes are supported by this engine only in time series.
            kinds=('number','date') if p['method']=='time_series' and i==0 else tuple(spec['kinds'])
            if p['method']=='time_series' and i>0:kinds=('number',)
            roles.append((label,'indices',i,kinds))
    if p.get('group_index') is not None:
        roles.append(('Grouping variable','group_index',None,('number','text')))
    for index in range(len(p.get('group_indices',[]))):roles.append(('Grouping variable '+str(index+1),'group_indices',index,('number','text')))
    return roles


def _role_index(parameters,role):
    value=parameters[role[1]]
    return value[role[2]] if role[2] is not None else value


class SimilarGraphDialog(QDialog):
    """Native-evidenced replacement grid; optional setup extension is original."""
    def __init__(self,parent,worksheet,entry):
        self.setSizeGripEnabled(True)
        super().__init__(parent)
        self.source_recipe=_source_recipe(entry,worksheet)
        self.source_entry=copy.deepcopy(entry);self.worksheet=worksheet
        self._options_recipe=copy.deepcopy(self.source_recipe)
        self._options_appearance=appearance_from_entry(entry)
        self.role_specs=_roles(self.source_recipe)
        self.parameters=None
        self.setWindowTitle('Make Similar Graph');self.resize(850,440)
        outer=QVBoxLayout(self)
        original=QLabel('Original graph: '+str(entry.get('title','Graph')))
        original.setWordWrap(True);outer.addWidget(original)
        body=QHBoxLayout();left=QVBoxLayout()
        self.available=QListWidget();self.available.setMinimumWidth(190)
        left.addWidget(self.available)
        self.select_button=QPushButton('Select');self.select_button.setAutoDefault(False)
        self.select_button.clicked.connect(self.transfer)
        self.available.itemDoubleClicked.connect(lambda item:self.transfer())
        left.addWidget(self.select_button);body.addLayout(left,1)
        self.roles=QTableWidget(len(self.role_specs),3)
        self.roles.setHorizontalHeaderLabels(['Role','Original Variable','New Variable'])
        self.roles.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row,role in enumerate(self.role_specs):
            index=_role_index(self.source_recipe['parameters'],role)
            reference=format_variable_reference(index,worksheet)
            for column,text in enumerate((role[0],reference,reference)):
                item=QTableWidgetItem(text);item.setToolTip(text)
                if column<2:item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.roles.setItem(row,column,item)
        self.roles.currentCellChanged.connect(lambda row,column,*args:self.activate(row))
        body.addWidget(self.roles,3);outer.addLayout(body)
        self.retain_appearance=QCheckBox('Retain graph appearance (annotations, scales and object styles)')
        self.retain_appearance.setChecked(True);outer.addWidget(self.retain_appearance)
        self.error=QLabel();self.error.setObjectName('error');self.error.setWordWrap(True);outer.addWidget(self.error)
        bottom=QHBoxLayout();self.options_button=QPushButton('Options…')
        self.options_button.setAutoDefault(False);self.options_button.clicked.connect(self.edit_options)
        bottom.addWidget(self.options_button);bottom.addStretch()
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate);self.buttons.rejected.connect(self.reject)
        bottom.addWidget(self.buttons);outer.addLayout(bottom)
        if self.role_specs:self.roles.setCurrentCell(0,2)
        else:self.select_button.setEnabled(False)

    def activate(self,row):
        self.available.clear()
        if not 0<=row<len(self.role_specs):return
        for index,column in enumerate(self.worksheet.columns):
            if column.kind in self.role_specs[row][3]:
                label=format_variable_reference(index,self.worksheet)
                item=QListWidgetItem(label);item.setToolTip(label)
                item.setData(Qt.ItemDataRole.UserRole,index);self.available.addItem(item)

    def transfer(self):
        row=self.roles.currentRow();item=self.available.currentItem()
        if item is None or row<0:return
        text=format_variable_reference(item.data(Qt.ItemDataRole.UserRole),self.worksheet)
        self.roles.setItem(row,2,QTableWidgetItem(text));self.roles.setCurrentCell(row,2)

    def recipes(self):
        recipe=copy.deepcopy(self._options_recipe);parameters=recipe['parameters']
        for row,role in enumerate(self.role_specs):
            item=self.roles.item(row,2)
            indices=resolve_variables(item.text() if item else '',self.worksheet,role[3])
            if len(indices)!=1:raise ValueError(role[0]+': select exactly one new variable.')
            if role[2] is None:parameters[role[1]]=indices[0]
            else:parameters[role[1]][role[2]]=indices[0]
        columns(recipe)
        return [recipe]

    def appearance_settings(self):
        if self.retain_appearance.isChecked():return validate_appearance(self._options_appearance)
        # More than 200 bins use the separate histogram drawing settings. Keep
        # the chosen count even when the original appearance is reset.
        histogram=self._options_appearance.get('histogram_settings',{})
        if histogram.get('bins',0)>200:
            return validate_appearance({'histogram_settings':{'bins':histogram['bins']}})
        return {}

    def edit_options(self):
        try:
            entry=copy.deepcopy(self.source_entry);entry['recipe']=self.recipes()[0]
            for key in ('graph_styles','graph_presentation','histogram_settings'):entry.pop(key,None)
            entry.update({key:value for key,value in self.appearance_settings().items() if key!='series_labels'})
            dialog=create_options_dialog(self,self.worksheet,entry)
            # Replacements are edited in the main role grid. This extension
            # exposes the original graph's calculation and label options only.
            dialog.available.setEnabled(False)
            if getattr(dialog,'lock_variables',False) or hasattr(dialog,'variables'):
                pass
            elif hasattr(dialog,'controls'):
                for spec in dialog.selectors:dialog.controls[spec['key']].setEnabled(False)
                dialog.select_button.setEnabled(False)
            else:
                dialog.roles.setEnabled(False);dialog.group_entry.setEnabled(False)
            dialog.retain_appearance.setChecked(self.retain_appearance.isChecked())
            dialog.retain_appearance.hide()
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self._options_recipe=dialog.recipes()[0]
                self._options_appearance=dialog.appearance_settings()
            dialog.deleteLater()
        except (ValueError,TypeError,OverflowError) as exc:self.error.setText(str(exc))

    def validate(self):
        self.roles.setFocus()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        try:self.parameters=self.recipes();self.appearance_settings()
        except (ValueError,TypeError,OverflowError) as exc:self.error.setText(str(exc));return
        self.accept()


def create_similar_dialog(parent, worksheet, entry):
    return SimilarGraphDialog(parent,worksheet,entry)


def run_similar_graphs(presenter, entry, recipes, *, copy_appearance=True, appearance=None):
    """Create new tracked results on the original sheet; roll back on any error.

    GUI callers pass dialog.appearance_settings() explicitly. Otherwise the
    source appearance is retained by default. Source result/history are never
    rewritten. The original active sheet is restored if calculation fails.
    """
    source=presenter.result_worksheet(entry)
    _source_recipe(entry,source)
    if not isinstance(recipes,list) or not 1<=len(recipes)<=8:
        raise ValueError('Choose from 1 to 8 graph specifications.')
    normalized=[]
    for recipe in recipes:
        if not isinstance(recipe,dict) or recipe.get('action')!=entry['recipe']['action']:
            raise ValueError('A similar graph must use the original graph procedure.')
        fingerprints(source,columns(recipe))
        if recipe['parameters'].get('graph_type')!=entry['recipe']['parameters'].get('graph_type'):raise ValueError('A similar graph must use the original graph type.')
        if recipe['parameters'].get('method')!=entry['recipe']['parameters'].get('method'):
            raise ValueError('A similar graph must use the original graph type.')
        normalized.append(copy.deepcopy(recipe))
    appearance=validate_appearance(appearance if appearance is not None else appearance_from_entry(entry) if copy_appearance else {})
    before_history=list(presenter.history); before_dirty=presenter._results_dirty
    before_sheet=presenter.worksheet
    before_index=presenter.native_project.active_index if presenter.native_project else None
    try:
        presenter.worksheet=source
        if presenter.native_project:
            presenter.native_project.active_index=next(i for i,sheet in enumerate(presenter.native_project.worksheets) if sheet is source)
        results=[]
        for recipe in normalized:
            created=run(presenter,recipe)
            for key,value in appearance.items():
                if key=='series_labels':continue
                if key=='histogram_settings':
                    from .histogram_options import build_histogram_panel
                    build_histogram_panel(created['result'].get('histogram_source'),value)
                created[key]=copy.deepcopy(value)
            results.append(created)
        presenter._results_dirty=True
        return results
    except Exception:
        presenter.history[:]=before_history; presenter._results_dirty=before_dirty
        presenter.worksheet=before_sheet
        if presenter.native_project:presenter.native_project.active_index=before_index
        raise
