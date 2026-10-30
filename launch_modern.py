"""Qt desktop entry and packaged verification; no StatCraft runtime dependency."""
import json
import sys
import tempfile
from pathlib import Path

_root = Path(__file__).resolve().parent
_deps = _root.parent / 'statcraft-build-deps'
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def smoke(destination):
    def checkpoint(value):Path(str(destination)+'.progress').write_text(value,encoding='utf-8')
    from PySide6.QtWidgets import QApplication, QTableWidget
    from statcraft.modern_app import ModernWindow
    from statcraft.modern_charts import ChartWidget
    from statcraft.app import Presenter
    from statcraft.model import Worksheet, Column
    from statcraft.recipes import run
    app = QApplication.instance() or QApplication([])
    from statcraft.verification_fonts import load_verification_fonts
    load_verification_fonts(app)
    p = Presenter()
    p.worksheet = Worksheet('Verification', [Column('X', values=[1,2,3,4,5]), Column('Y', values=[2,4,5,8,9])])
    w = ModernWindow(p); w.show(); app.processEvents()
    assert w.table.rowCount() >= 5 and w.table.columnCount() == 2
    assert w.column_names.rowCount()==1 and w.column_names.columnCount()==2
    w.column_names.item(0,0).setText('Predictor'); app.processEvents()
    assert p.worksheet.columns[0].name=='Predictor' and p.worksheet.columns[0].values[0]==1
    w.undo(); assert p.worksheet.columns[0].name=='X'
    w.table.item(0,0).setText('42'); app.processEvents()
    assert p.worksheet.columns[0].values[0] == 42
    w.undo(); assert p.worksheet.columns[0].values[0] == 1
    w.show_result(p.describe_columns([0,1])); app.processEvents()
    assert w.result_tabs.count() >= 2
    for method, indices in [('histogram',[0]),('boxplot',[0]),('scatter',[0,1])]:
        entry = run(p, {'action':'graph','parameters':{'method':method,'indices':indices,'bins':3}})
        w.show_result(entry); app.processEvents()
        charts = w.findChildren(ChartWidget)
        assert charts and charts[-1].error is None, charts[-1].error if charts else 'Missing chart'
        assert not charts[-1].grab().isNull()
    for entry in (p.individuals_moving_range(0),p.normal_capability(0,0,6,3),
                  p.xbar_r_rows([0,1]),p.inference('linear_regression',[0,1]),
                  p.multiple_regression(1,[0])):
        w.show_result(entry); app.processEvents()
        charts = w.findChildren(ChartWidget)
        assert charts and charts[-1].error is None
        assert not charts[-1].grab().isNull()
    from statcraft.attribute_quality import p_chart, u_chart
    for result in (p_chart([1,None,8],[20,None,40]),u_chart([2,4,8],[1,2,4])):
        w.show_result({'title':'Attribute verification','time':'Verification','result':result}); app.processEvents()
        chart = w.findChildren(ChartWidget)[-1]; assert chart.error is None
        assert not chart.grab().isNull()
    from PySide6.QtCore import QTimer,Qt
    from statcraft.modern_app import ProcedureDialog
    p.worksheet = Worksheet('Binary samples',[Column('First',values=[1,0,1,0]),Column('Second',values=[0,0,1,0])])
    w.refresh()
    from statcraft.variable_dialogs import ScatterDialog
    from PySide6.QtWidgets import QTableWidgetItem
    scatter=ScatterDialog(w,p.worksheet)
    scatter.roles.setCurrentCell(0,0); scatter.available.setCurrentRow(1); scatter.transfer()
    scatter.roles.setCurrentCell(0,1); scatter.available.setCurrentRow(0); scatter.transfer()
    assert scatter.values()==[(1,0)]
    scatter.roles.setItem(1,0,QTableWidgetItem('C1'))
    try: scatter.values()
    except ValueError: pass
    else: raise AssertionError('Incomplete scatterplot pair was accepted.')
    scatter.deleteLater()
    before=len(p.history)
    def accept_scatter():
        dialog=QApplication.activeModalWidget()
        from statcraft.variable_dialogs import ScatterTypeDialog
        if isinstance(dialog,ScatterTypeDialog):
            dialog.accept(); QTimer.singleShot(0,accept_scatter); return
        dialog.roles.setItem(0,0,QTableWidgetItem('C2'))
        dialog.roles.setItem(0,1,QTableWidgetItem('C1')); dialog.validate()
    QTimer.singleShot(0,accept_scatter); w.graph('scatter'); app.processEvents()
    assert len(p.history)==before+1
    assert p.history[-1]['result']['xlabel']=='First' and p.history[-1]['result']['ylabel']=='Second'
    for callback in (w.correlation,w.one_proportion,w.two_proportions):
        before=len(p.history)
        def accept_procedure():
            dialog=QApplication.activeModalWidget()
            if not isinstance(dialog,ProcedureDialog): raise AssertionError('Procedure dialog did not open.')
            for spec in dialog.selectors:
                key=spec['key']
                dialog.controls[key].setText('C1 C2' if spec.get('multiple') else 'C2' if key=='second_index' else 'C1')
            dialog.validate()
        QTimer.singleShot(0,accept_procedure)
        callback(); app.processEvents()
        assert len(p.history)==before+1
        assert not w.result_tabs.widget(0).grab().isNull()
    normal_sample=[-1.5,-1,-.5,-.1,.1,.5,1,1.5]
    p.worksheet=Worksheet('Normality verification',[Column('X',values=normal_sample)])
    w.refresh()
    for callback in (w.normality,w.one_variance):
        before=len(p.history)
        QTimer.singleShot(0,accept_procedure); callback(); app.processEvents()
        assert len(p.history)==before+1
        if p.history[-1]['recipe']['action']=='normality':
            chart=w.findChildren(ChartWidget)[-1]; assert chart.error is None
            assert len(chart.panels)==1 and not chart.grab().isNull()
    with tempfile.TemporaryDirectory() as temp:
        from statcraft.mpx import load_mpx
        from zipfile import ZipFile
        # Original synthetic fixture, included solely in verification builds.
        from statcraft._mpx_fixture import write_fixture
        source = Path(temp)/'original.mpx'; target = Path(temp)/'copy.mpx'
        write_fixture(source); original = source.read_bytes()
        w.load_path(source); assert len(p.native_project.worksheets) == 2
        w.column_names.item(0,0).setText('Metric'); app.processEvents()
        assert p.worksheet.columns[0].name=='Metric'
        w.table.item(0,0).setText('12'); app.processEvents()
        entry = p.describe_column(0); w.show_result(entry)
        assert p.result_stale(entry) is False
        w.table.item(0,0).setText('13'); app.processEvents()
        assert p.result_stale(entry) is True
        w.rerun_selected(); assert p.result_stale(w.selected_entry) is False
        w.save_path(target); assert source.read_bytes() == original
        w.load_path(target); assert p.worksheet.columns[0].values[0] == 13
        assert p.worksheet.columns[0].name=='Metric'
        own = [e for e in p.history if e.get('origin') == 'statcraft']
        assert len(own) >= 2
        from statcraft._mpx_fixture import write_subgroup_fixture
        binary_source=Path(temp)/'binary-source.mpx'; write_subgroup_fixture(binary_source)
        w.load_path(binary_source)
        for column in range(2):
            for row,value in enumerate([0,1,1,0,1,0]): p.set_cell(row,column,str(value))
        for entry in (p.correlation([0,1]),p.one_proportion(0),p.two_proportions(0,1)):
            w.show_result(entry)
        w.save_path(target)
        w.load_path(target)
        own=[e for e in p.history if e.get('recipe',{}).get('action') in ('correlation','one_proportion','two_proportions')]
        assert len(own)==3
        for entry in own:
            w.show_result(entry); w.rerun_selected()
            assert p.result_stale(w.selected_entry) is False
        with ZipFile(target) as z: assert '/statcraft/session.json' in z.namelist()
        from statcraft._mpx_fixture import write_blob_fixture
        blob_source=Path(temp)/'blob-source.mpx'; blob_target=Path(temp)/'blob-copy.mpx'
        write_blob_fixture(blob_source); w.load_path(blob_source)
        assert p.worksheet.columns[0].values==[1,2,3]
        w.table.item(0,0).setText('7'); app.processEvents(); w.save_path(blob_target)
        w.load_path(blob_target); assert p.worksheet.columns[0].values==[7,2,3]
        with ZipFile(blob_target) as z:
            document=json.loads(z.read('/sheets/0/sheet.json'))
            assert isinstance(document['Data']['Columns'][0]['WorksheetVarBody']['VarData']['VarDataBody']['NumericData'],str)
        normal_source=Path(temp)/'normal-source.mpx'; normal_target=Path(temp)/'normal-copy.mpx'
        write_blob_fixture(normal_source,normal_sample); w.load_path(normal_source)
        for entry in (p.normality(0),p.one_variance(0,2,.9)): w.show_result(entry)
        w.save_path(normal_target); w.load_path(normal_target)
        own=[e for e in p.history if e.get('recipe',{}).get('action') in ('normality','one_variance')]
        assert len(own)==2
        for entry in own:
            w.show_result(entry); w.rerun_selected(); assert p.result_stale(w.selected_entry) is False
        from statcraft._mpx_fixture import write_scatter_fixture
        from statcraft.scatter import MODES
        scatter_source=Path(temp)/'scatter-source.mpx'; scatter_target=Path(temp)/'scatter-copy.mpx'
        write_scatter_fixture(scatter_source); w.load_path(scatter_source)
        for mode in MODES:
            entry=p.scatter_plot(2,0,mode,1 if mode.endswith('groups') else None)
            w.show_result(entry); app.processEvents()
            chart=w.findChildren(ChartWidget)[-1]; assert not chart.grab().isNull()
            assert chart.error is None,chart.error
        w.save_path(scatter_target); w.load_path(scatter_target)
        own=[e for e in p.history if e.get('recipe',{}).get('action')=='scatter_plot']
        assert len(own)==6
        for entry in own:
            w.show_result(entry); w.rerun_selected(); assert p.result_stale(w.selected_entry) is False
        before=len(p.history)
        def accept_grouped_scatter():
            from statcraft.variable_dialogs import ScatterTypeDialog
            dialog=QApplication.activeModalWidget()
            if dialog is None:
                QTimer.singleShot(10,accept_grouped_scatter);return
            if isinstance(dialog,ScatterTypeDialog):
                dialog.mode_buttons['regression_groups'].click(); dialog.accept()
                QTimer.singleShot(0,accept_grouped_scatter); return
            try:
                dialog.roles.setItem(0,0,QTableWidgetItem('C1')); dialog.roles.setItem(0,1,QTableWidgetItem('C3'))
                dialog.activate('group'); dialog.available.setCurrentRow(1); dialog.transfer()
                assert dialog.group_entry.text().startswith('C2'), dialog.group_entry.text()
                dialog.labels['title']='Grouped UI verification'; dialog.validate()
            except Exception:
                dialog.reject(); raise
        QTimer.singleShot(0,accept_grouped_scatter); w.graph('scatter'); app.processEvents()
        assert len(p.history)==before+1 and len(p.history[-1]['result']['fits'])==3
        assert p.history[-1]['title']=='Grouped UI verification'
        before=len(p.history)
        QTimer.singleShot(0,lambda:QApplication.activeModalWidget().reject()); w.graph('scatter')
        assert len(p.history)==before
        from statcraft._mpx_fixture import write_factorial_fixture
        doe_source=Path(temp)/'doe-source.mpx'; doe_target=Path(temp)/'doe-copy.mpx'
        write_factorial_fixture(doe_source); w.load_path(doe_source)
        def accept_factorial_analysis():
            dialog=QApplication.activeModalWidget()
            dialog.factor_indices=[0,1]; dialog.response.setText('C3'); dialog.validate()
            assert not dialog.error.text(),dialog.error.text()
        QTimer.singleShot(0,accept_factorial_analysis); w.analyze_factorial(); app.processEvents()
        assert [round(e['effect'],8) for e in p.history[-1]['result']['effects']]==[4,-6,3]
        chart=w.findChildren(ChartWidget)[-1]; assert not chart.grab().isNull() and chart.error is None
        w.save_path(doe_target); w.load_path(doe_target)
        own=[e for e in p.history if e.get('recipe',{}).get('action')=='analyze_factorial']
        assert len(own)==1
        w.show_result(own[0]); w.rerun_selected(); assert not p.result_stale(w.selected_entry)
        p.dirty=False; p._results_dirty=False
        def accept_factorial_creation():
            dialog=QApplication.activeModalWidget(); dialog.randomize=False; dialog.validate()
            assert not dialog.error.text(),dialog.error.text()
        QTimer.singleShot(0,accept_factorial_creation); w.create_factorial(); app.processEvents()
        assert p.native_project is None and p.worksheet.row_count==8
        assert p.worksheet.headers==['StdOrder','RunOrder','PtType','Blocks','A','B']
        p.add_column('Response')
        for row in range(8):
            a,b=p.worksheet.columns[4].values[row],p.worksheet.columns[5].values[row]
            p.set_cell(row,6,str(10+2*a-3*b+1.5*a*b+(1 if row<4 else -1)))
        w.refresh()
        def accept_created_analysis():
            dialog=QApplication.activeModalWidget()
            assert dialog.factor_indices==[4,5]
            dialog.response.setText('C7'); dialog.validate()
            assert not dialog.error.text(),dialog.error.text()
        QTimer.singleShot(0,accept_created_analysis); w.analyze_factorial(); app.processEvents()
        assert [round(e['effect'],8) for e in p.history[-1]['result']['effects']]==[4,-6,3]
        # A new numeric response column must survive an MPX save and rerun.
        w.load_path(doe_source); p.add_column('Added response')
        for row,value in enumerate([10,12,9,13,8,11,7,14]):p.set_cell(row,3,str(value))
        p.describe_column(3); w.refresh(); w.save_path(doe_target); w.load_path(doe_target)
        assert p.worksheet.columns[3].values==[10,12,9,13,8,11,7,14]
        saved=next(e for e in p.history if e.get('recipe',{}).get('action')=='describe_column')
        assert p.rerun_result(saved)['result']==saved['result']
        # The UI exposes regular fractions through Designs > Generators.
        p.dirty=False; p._results_dirty=False
        def accept_fractional_creation():
            dialog=QApplication.activeModalWidget(); dialog.factor_count.setCurrentText('4')
            dialog.design_types[1].setChecked(True); dialog.randomize=False
            def generator_input():
                child=QApplication.activeModalWidget(); dialog.generator_table.item(3,2).setText('ABC')
                from PySide6.QtWidgets import QDialogButtonBox
                child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
            QTimer.singleShot(0,generator_input); dialog.generator_settings(); dialog.validate()
            assert not dialog.error.text(),dialog.error.text()
        QTimer.singleShot(0,accept_fractional_creation); w.create_factorial(); app.processEvents()
        assert p.worksheet.row_count==16 and p.worksheet.metadata['doe']['resolution']==4
        p.add_column('Response')
        for row in range(16):
            a,b,c,d=p.worksheet.row(row)[4:8]
            p.set_cell(row,8,str(10+2*a-3*b+1.5*c+.5*d+(1 if row<8 else -1)))
        w.refresh()
        def accept_fractional_analysis():
            dialog=QApplication.activeModalWidget(); dialog.response.setText('C9')
            def select_model():
                terms=QApplication.activeModalWidget()
                assert terms.selected.count()==4
                terms.order_combo.setCurrentText('2'); terms.remove_terms(True)
                # Adding AB includes its lower-order terms; removing A removes AB.
                for i in range(terms.available.count()):
                    item=terms.available.item(i)
                    if item.data(Qt.ItemDataRole.UserRole)==[0,1]:item.setSelected(True)
                terms.add_terms(); assert terms.selected.count()==3
                for i in range(terms.selected.count()):
                    item=terms.selected.item(i)
                    if item.data(Qt.ItemDataRole.UserRole)==[0]:item.setSelected(True)
                terms.remove_terms(); assert terms.selected_terms==[[1]]
                terms.order_combo.setCurrentText('1'); terms.defaults(); assert terms.validate()
            QTimer.singleShot(0,select_model); dialog.terms(); dialog.validate()
            assert not dialog.error.text(),dialog.error.text()
        QTimer.singleShot(0,accept_fractional_analysis); w.analyze_factorial(); app.processEvents()
        assert [round(e['effect'],8) for e in p.history[-1]['result']['effects']]==[4,-6,3,1]
        assert p.history[-1]['recipe']['action']=='analyze_factorial_terms'
        assert p.history[-1]['result']['alias_structure']
        from statcraft._mpx_fixture import write_fractional_fixture
        fraction_source=Path(temp)/'fraction.mpx'; fraction_copy=Path(temp)/'fraction-copy.mpx'
        write_fractional_fixture(fraction_source); w.load_path(fraction_source)
        entry=p.analyze_factorial(4,[0,1,2,3],selected_terms=[[0],[1],[2],[3]])
        w.show_result(entry); w.save_path(fraction_copy); w.load_path(fraction_copy)
        entry=next(e for e in p.history if e.get('recipe',{}).get('action')=='analyze_factorial_terms')
        assert p.rerun_result(entry)['result']==entry['result']
        # Numeric growth through the actual Add rows dialog and saved MPX recipe.
        w.load_path(blob_source)
        original_blob_source=blob_source.read_bytes()
        old=p.describe_column(0)
        def accept_rows():
            dialog=QApplication.activeModalWidget(); dialog.setIntValue(2); dialog.accept()
        QTimer.singleShot(0,accept_rows); w.add_rows(); app.processEvents()
        assert p.worksheet.row_count==5 and p.result_stale(old)
        w.table.item(4,0).setText('9'); app.processEvents()
        w.show_result(p.rerun_result(old)); w.save_path(blob_target); w.load_path(blob_target)
        assert p.worksheet.columns[0].values==[1,2,3,None,9]
        entry=next(e for e in reversed(p.history) if e.get('recipe',{}).get('action')=='describe_column')
        assert p.rerun_result(entry)['result']['count']==4
        with ZipFile(blob_target) as archive:
            body=json.loads(archive.read('/sheets/0/sheet.json'))['Data']['Columns'][0]['WorksheetVarBody']['VarData']['VarDataBody']
            assert body['CellCt']==5 and body['NumericData']=='/blobs/blob1?size=5'
            assert len(archive.read('/blobs/blob1'))==40
        assert blob_source.read_bytes()==original_blob_source
        # New MPX workbooks and bottom worksheet tabs use stable source IDs.
        p.dirty=False;p._results_dirty=False;w.new_document();app.processEvents()
        assert w.worksheet_tabs.count()==1 and w.add_sheet_button.isEnabled()
        w.table.item(0,0).setText('4');w.table.item(1,0).setText('6');app.processEvents()
        w.show_result(p.describe_column(0));w.add_sheet_button.click();app.processEvents()
        assert w.worksheet_tabs.count()==2 and p.native_project.statcraft_owned
        w.table.item(0,0).setText('9');app.processEvents()
        def name_sheet():
            dialog=QApplication.activeModalWidget();dialog.setTextValue('Inspection');dialog.accept()
        QTimer.singleShot(0,name_sheet);w.rename_worksheet();app.processEvents()
        assert w.worksheet_tabs.tabText(1)=='Inspection'
        def name_copy():
            dialog=QApplication.activeModalWidget();dialog.setTextValue('Inspection Copy');dialog.accept()
        QTimer.singleShot(0,name_copy);w.duplicate_worksheet();app.processEvents()
        assert w.worksheet_tabs.count()==3 and p.worksheet.columns[0].values==[9]
        w.worksheet_tabs.setCurrentIndex(0);app.processEvents()
        owned_target=Path(temp)/'new-owned.mpx';w.save_path(owned_target);w.load_path(owned_target)
        assert p.native_project.statcraft_owned and w.add_sheet_button.isEnabled()
        assert [w.worksheet_tabs.tabText(i) for i in range(3)]==['Worksheet 1','Inspection','Inspection Copy']
        p.set_cell(2,0,'8');w.refresh();w.save_path(owned_target);w.load_path(owned_target)
        assert p.worksheet.columns[0].values==[4,6,8]
        entry=next(e for e in p.history if e.get('recipe',{}).get('action')=='describe_column')
        w.show_result(entry);w.rerun_selected();assert not p.result_stale(w.selected_entry)
        assert w.selected_entry['result']['mean']==6
        # Type a categorical column in the real grid, then save and rerun its graph.
        p.dirty=False;p._results_dirty=False;w.new_document();app.processEvents()
        for row,(x,y) in enumerate(zip([1,2,3,4,5,6],[2,4,7,9,10,12])):
            w.table.item(row,0).setText(str(x));w.table.item(row,1).setText(str(y))
        for row,label in enumerate(['A','A','B','B']):w.table.item(row,2).setText(label)
        p.set_cell(5,2,'');w.refresh();app.processEvents()
        assert p.worksheet.columns[2].kind=='text'
        assert w.table.horizontalHeaderItem(2).text()=='C3-T'
        entry=p.scatter_plot(0,1,'regression_groups',2);w.show_result(entry)
        text_target=Path(temp)/'text-owned.mpx';w.save_path(text_target);w.load_path(text_target)
        assert p.native_project.statcraft_owned
        assert p.worksheet.columns[2].values==['A','A','B','B',None,'']
        saved=next(e for e in p.history if e.get('recipe',{}).get('action')=='scatter_plot')
        assert p.rerun_result(saved)['result']==saved['result']
        p.add_rows(1);p.set_cell(6,2,'Ω');w.refresh();w.save_path(text_target);w.load_path(text_target)
        assert p.worksheet.columns[2].values==['A','A','B','B',None,'','Ω']
        with ZipFile(text_target) as archive:
            own=json.loads(archive.read('/statcraft/workbook.json'))
            assert own['schema']=='statcraft-owned-mpx-v2'
            assert own['sheets'][0]['missing_text']=={'2':[4]}
        # Select the date type through the UI; raw fractional serials remain exact.
        w.table.setCurrentCell(0,3)
        def select_date_type():
            dialog=QApplication.activeModalWidget();dialog.setTextValue('date');dialog.accept()
        QTimer.singleShot(0,select_date_type);w.change_type();app.processEvents()
        assert p.worksheet.columns[3].kind=='date' and w.table.horizontalHeaderItem(3).text()=='C4-D'
        w.table.item(0,3).setText('2020-01-02T12:30:00');app.processEvents()
        assert w.table.item(0,3).text()=='2020-01-02 12:30:00'
        w.table.item(2,3).setText('45000.123456789');app.processEvents()
        assert p.worksheet.columns[3].values==[43832.520833333336,None,45000.123456789]+[None]*4
        assert p.copy_block(0,0,3,3)=='2020-01-02 12:30:00\n'
        date_target=Path(temp)/'dates-owned.mpx';w.save_path(date_target);w.load_path(date_target)
        assert p.native_project.statcraft_owned and p.worksheet.columns[3].kind=='date'
        assert p.worksheet.columns[3].values==[43832.520833333336,None,45000.123456789]+[None]*4
        p.add_rows(1);w.refresh();w.save_path(date_target);w.load_path(date_target)
        assert p.worksheet.columns[3].values==[43832.520833333336,None,45000.123456789]+[None]*5
        assert w.table.item(1,3).text()=='*'
        with ZipFile(date_target) as archive:
            own=json.loads(archive.read('/statcraft/workbook.json'))
            assert own['schema']=='statcraft-owned-mpx-v3'
            assert own['sheets'][0]['missing_dates']=={'3':[1,3,4,5,6,7]}
        # Stored-data editors commit their staged snapshots and preserve C/K/M layout.
        checkpoint('stored constants')
        def accept_constants():
            dialog=QApplication.activeModalWidget();dialog.add_constant()
            dialog.table.item(0,1).setText('Scale');dialog.table.item(0,2).setText('2')
            assert dialog.validate(),dialog.error_label.text()
        QTimer.singleShot(0,accept_constants);w.stored_constants();app.processEvents()
        assert p.worksheet.constants[0].values==[2]
        checkpoint('stored matrices')
        def accept_matrix():
            dialog=QApplication.activeModalWidget();dialog.add_matrix()
            dialog.name_edit.setText('Weights');dialog.columns_spin.setValue(3)
            assert dialog.resize_matrix(),dialog.error_label.text()
            dialog.table.setCurrentCell(0,0);assert dialog.paste_tsv('1\t3\t5\n2\t4\t6')
            assert dialog.validate(),dialog.error_label.text()
        QTimer.singleShot(0,accept_matrix);w.stored_matrices();app.processEvents()
        assert p.worksheet.matrices[0].as_rows()==[[1,3,5],[2,4,6]]
        collections_target=Path(temp)/'collections-owned.mpx';w.save_path(collections_target);w.load_path(collections_target)
        checkpoint('stored reopen')
        assert p.native_project.statcraft_owned and p.worksheet.constants[0].values==[2]
        assert p.worksheet.matrices[0].as_rows()==[[1,3,5],[2,4,6]]
        p.calculate('C1 * K1','Scaled');assert p.worksheet.columns[-1].values[:6]==[2,4,6,8,10,12]
        # Real key events must commit an editor and navigate without losing data.
        checkpoint('worksheet keys')
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QLineEdit,QMessageBox
        def key(widget,value,modifiers=Qt.KeyboardModifier.NoModifier):
            QApplication.sendEvent(widget,QKeyEvent(QEvent.Type.KeyPress,value,modifiers));app.processEvents()
        w.refresh();w.table.setCurrentCell(0,0);w.table.editItem(w.table.item(0,0));app.processEvents()
        editors=[e for e in w.table.findChildren(QLineEdit) if not e.isHidden()]
        assert len(editors)==1,('Expected one active worksheet editor',len(editors))
        editor=editors[0]
        editor.setText('7');key(editor,Qt.Key.Key_Tab)
        assert p.worksheet.columns[0].values[0]==7 and (w.table.currentRow(),w.table.currentColumn())==(0,1)
        key(w.table,Qt.Key.Key_Return);assert (w.table.currentRow(),w.table.currentColumn())==(1,1)
        key(w.table,Qt.Key.Key_Return,Qt.KeyboardModifier.ShiftModifier);assert w.table.currentRow()==0
        key(w.table,Qt.Key.Key_Backtab,Qt.KeyboardModifier.ShiftModifier);assert w.table.currentColumn()==0
        w.table.setCurrentCell(24,0);key(w.table,Qt.Key.Key_Return);assert w.table.currentRow()==25
        w._navigation_row=299;w.refresh();w.table.setCurrentCell(299,0);key(w.table,Qt.Key.Key_Return)
        assert w.page==1 and w.table.currentRow()==0
        # Delete confirmation cancellation retains data; confirmation removes bound results.
        checkpoint('delete worksheet')
        w.page=0;w.refresh();w.add_sheet_button.click();app.processEvents()
        p.set_cell(0,0,'9');deleted=p.describe_column(0);w.show_result(deleted)
        before_count=len(p.native_project.worksheets)
        original_question=QMessageBox.question;questions=[]
        def answer_no(parent,title,text,*args):questions.append((title,text));return QMessageBox.StandardButton.No
        def answer_yes(parent,title,text,*args):questions.append((title,text));return QMessageBox.StandardButton.Yes
        try:
            QMessageBox.question=answer_no
            w.delete_worksheet();assert len(p.native_project.worksheets)==before_count
            QMessageBox.question=answer_yes
            w.delete_worksheet();assert len(p.native_project.worksheets)==before_count-1 and deleted not in p.history
            assert len(questions)==2 and all('cannot be undone' in text for title,text in questions)
        finally:QMessageBox.question=original_question
        w.save_path(collections_target);w.load_path(collections_target)
        checkpoint('delete saved')
        assert p.worksheet.constants[0].values==[2] and w.selected_entry is None
        checkpoint('expanded graph menu')
        from statcraft.expanded_graphs import METHODS
        from statcraft.modern_expanded_charts import ExpandedChartWidget
        p.native_project=None;p.history=[];p._reset_edits()
        p.worksheet=Worksheet('Graph examples',[Column('X',values=[0,1,0,1]),Column('Y',values=[0,0,1,1]),
            Column('Z',values=[1,2,3,4]),Column('Group','text',['A','A','B','B']),Column('When','date',[43831,43832,43833,43834])])
        w.refresh();assert len(w.graph_actions)==26
        for method,meta in METHODS.items():
            failures=[];before=len(p.history)
            def accept_graph(method=method,meta=meta):
                dialog=QApplication.activeModalWidget()
                if dialog is None:QTimer.singleShot(10,accept_graph);return
                try:
                    if method in ('dotplot','individual_value','interval_plot'):
                        if hasattr(dialog,'mode_buttons'):
                            dialog.accept();QTimer.singleShot(0,lambda:accept_graph(method,meta));return
                        dialog.variables.setText('C3');dialog.validate();return
                    if len(meta['roles'])>1:
                        for i in range(len(meta['roles'])):dialog.controls['variable'+str(i)].setText('C'+str(i+1))
                    elif meta['maximum']:
                        references='C1 C3' if meta['minimum']==2 else 'C4' if method in ('bar_chart','pie_chart') else 'C5 C3' if method=='time_series' else 'C3'
                        dialog.controls['indices'].setText(references)
                    dialog.validate()
                    if dialog.error.text():raise AssertionError(dialog.error.text())
                except Exception as exc:failures.append(str(exc));dialog.reject()
            QTimer.singleShot(0,accept_graph);w.graph_actions[method].trigger();app.processEvents()
            assert not failures,(method,failures)
            assert len(p.history)==before+1,method
            assert w.result_tabs.tabText(w.result_tabs.currentIndex())=='Graph',method
            chart=w._active_chart_widget
            assert chart.error is None,(method,chart.error)
            assert not chart.grab().isNull() and chart.error is None,(method,chart.error)
        # Builder owns named roles and a live, isolated preview.
        def choose_builder():
            dialog=QApplication.activeModalWidget();dialog.set_graph_type('dotplot');dialog.assign_columns('response_indices',[2]);dialog.validate()
        QTimer.singleShot(0,choose_builder);w.graph_actions['builder'].trigger();app.processEvents()
        assert p.history[-1]['recipe']['action']=='graph_builder' and p.history[-1]['result']['builder_graph_type']=='dotplot'
        all_graphs=Path(temp)/'graphs.mpx';w.save_path(all_graphs);w.load_path(all_graphs)
        for entry in list(p.history):assert p.rerun_result(entry)['result']==entry['result']
        checkpoint('expanded graph reruns passed')
        w.load_path(source);assert not w.add_sheet_button.isEnabled()
        # Verify StatCraft UI chrome, 11 menus, 21 toolbar actions, status bar, watermark, and new worksheet workflows
        checkpoint('statcraft 22 ui chrome and workflows')
        p.dirty=False; p._results_dirty=False; w.new_document(); app.processEvents()
        assert len(w.menuBar().actions())==11
        toolbar_buttons=[a for a in w.main_toolbar.actions() if not a.isSeparator()]
        assert len(toolbar_buttons)==21, len(toolbar_buttons)
        assert len(p.worksheet.columns)==16
        assert not w.output_header_bar.isVisible()
        # Toggle entry direction and verify Enter moves right
        w.toggle_entry_direction(); assert w.table.enter_direction=='right'
        w.table.setCurrentCell(0,0); key(w.table,Qt.Key.Key_Return); assert (w.table.currentRow(),w.table.currentColumn())==(0,1)
        w.toggle_entry_direction(); assert w.table.enter_direction=='down'
        # Test Zoom, View Modes, Navigator toggle, Command Line pane
        w.set_zoom(120); assert w._zoom_percent==120; w.set_zoom(100)
        w.set_view_mode('data'); assert not w.output_splitter.isVisible() and w.worksheet_pane.isVisible()
        w.set_view_mode('output'); assert w.output_splitter.isVisible() and not w.worksheet_pane.isVisible()
        w.set_view_mode('both'); assert w.output_splitter.isVisible() and w.worksheet_pane.isVisible()
        w.toggle_command_line(); assert w.command_line_pane.isVisible()
        p.set_cell(0,0,'10'); p.set_cell(1,0,'20'); p.set_cell(2,0,'30'); w.refresh()
        w.command_editor.setPlainText("LET C2 = C1 * 3\nDESCRIBE C1 C2")
        w.run_command_line(); app.processEvents()
        assert p.worksheet.columns[1].values==[30,60,90]
        assert p.history[-1]['title']=='Descriptive Statistics'
        w.toggle_command_line(); assert not w.command_line_pane.isVisible()
        # Insert cells, rows, columns and undo
        w.table.setCurrentCell(1,0); w.insert_cells_action_handler(); assert p.worksheet.columns[0].values==[10,None,20,30]; w.undo()
        w.table.setCurrentCell(1,0); w.insert_rows_action_handler(); assert p.worksheet.columns[1].values==[30,None,60,90]; w.undo()
        w.table.setCurrentCell(0,1); w.insert_columns_action_handler(); assert len(p.worksheet.columns)==17; w.undo()
        # Find next
        w._find_state={'query':'60','match_case':False,'whole_word':True,'direction':'down'}
        assert w.find_next(silent=True) and (w.table.currentRow(),w.table.currentColumn())==(1,1)
        # Verify StatCraft column/row selection highlighting, worksheet context menu (RT_MENU 9839), output context menu (RT_MENU 19209/23702), and Navigator tree
        w.select_worksheet_column(1)
        assert 1 in w._selected_columns and 1 in w.col_header_view.selected_sections
        assert 0 in w.row_header_view.active_sections
        w.select_worksheet_row(2)
        assert 2 in w._selected_rows and 2 in w.row_header_view.selected_sections
        ws_menu = w.build_worksheet_context_menu()
        ws_titles = [a.text().split('\t')[0] for a in ws_menu.actions() if not a.isSeparator()]
        for expected in ('Clear Cells', 'Delete Cells', 'Copy Cells', 'Cut Cells', 'Paste Cells',
                         'Find and Replace', 'Sort Columns', 'Cell Properties', 'Format Column...',
                         'Column Properties', 'Conditional Formatting', 'Formulas',
                         'Subset Worksheet', 'Worksheet Properties',
                         'Insert Cells', 'Insert Rows', 'Insert Columns', 'Move Columns...'):
            assert expected in ws_titles, (expected, ws_titles)
        hist_entry = run(p, {'action': 'graph', 'parameters': {'method': 'histogram', 'indices': [0], 'bins': 5}})
        w.show_result(hist_entry); app.processEvents()
        out_menu = w.build_output_context_menu(hist_entry)
        out_titles = [a.text().split('\t')[0] for a in out_menu.actions() if not a.isSeparator()]
        for expected in ('Send to Microsoft® Word', 'Send to Microsoft® PowerPoint', 'Send to Report',
                         'Copy Graph', 'Make Similar Graph...', 'Edit Graph...', 'Panel...',
                         'Brush Points...', 'Layout Tool...', 'Reset to Default Size',
                         'Save Graph As...', 'Print...', 'Delete'):
            assert expected in out_titles, (expected, out_titles)
        assert not any('StatCraft' in t for t in out_titles), out_titles
        # Verify Navigator top-level nodes are worksheet names (e.g. WORKSHEET 1) with no "Commands" node
        nav_roots = [w.navigator.topLevelItem(i).text(0) for i in range(w.navigator.topLevelItemCount())]
        assert 'WORKSHEET 1' in nav_roots and 'Commands' not in nav_roots, nav_roots
        w.send_output_to_report(hist_entry)
        assert any(w.result_tabs.tabText(i) == 'ReportPad' for i in range(w.result_tabs.count()))
        checkpoint('docked live graph editing')
        import copy
        original_result=copy.deepcopy(hist_entry['result'])
        w.show_result(hist_entry)
        edit_action=next(a for a in w.build_output_context_menu(hist_entry).actions() if a.text()=='Edit Graph...')
        edit_action.trigger();app.processEvents()
        pane=w.graph_options_pane;frame=w._active_graph_frame
        assert pane.isVisible() and QApplication.activeModalWidget() is None
        assert not w.output_header_bar.isVisible()
        pane.controls['title'].setText('Edited strength');pane.controls['title'].textEdited.emit('Edited strength')
        from PySide6.QtCore import QEventLoop
        loop=QEventLoop();QTimer.singleShot(200,loop.quit);loop.exec()
        assert hist_entry['graph_presentation']['title']=='Edited strength'
        assert frame.title_label.text()=='Edited strength' and frame.title_label.isVisible()
        pane.controls['subtitle'].setText('Production sample');pane.controls['subtitle'].textEdited.emit('Production sample')
        pane.controls['footnote'].setText('Checked');pane.controls['footnote'].textEdited.emit('Checked')
        assert pane.flush() and frame.subtitle_label.isVisible() and frame.footnote_label.isVisible()
        pane.controls['title_enabled'].setChecked(False);pane.flush();assert frame.title_label.isHidden()
        pane.controls['x_off'].setChecked(True);pane.flush();assert frame.chart.annotation_positions['x']=='off'
        pane.controls['x_label'].setText('Force (N)');pane.controls['x_label'].textEdited.emit('Force (N)');pane.flush()
        assert pane.controls['x_low'].isChecked() and frame.chart.annotation_axes['x']=='Force (N)'
        pane.controls['x_high'].setChecked(True);pane.flush();assert frame.chart.annotation_positions['x']=='high'
        pane.more_button.click();pane.controls['x_min'].setText('0');pane.controls['x_max'].setText('40')
        pane.controls['grid_enabled'].setChecked(False);assert pane.flush()
        assert frame.chart.annotation_limits['x']==(0.,40.) and not frame.chart.annotation_grid
        last_valid=copy.deepcopy(hist_entry['graph_presentation'])
        pane.controls['x_min'].setText('50');assert not pane.flush()
        assert hist_entry['graph_presentation']==last_valid
        pane.controls['x_min'].setText('0');assert pane.flush()
        assert hist_entry['result']==original_result and frame.chart.error is None
        assert not frame.capture().isNull()
        assert frame.chart.error is None
        assert not w.graph_dropdown_button.isHidden()
        pane.controls['title_enabled'].setChecked(True)
        pane.controls['footnote'].setText('Saved on close');pane.controls['footnote'].textEdited.emit('Saved on close')
        pane.close_button.click();assert pane.isHidden()
        assert hist_entry['graph_presentation']['footnote']=='Saved on close'
        styled=Path(temp)/'styled-graph.mpx';w.save_path(styled);w.load_path(styled)
        saved=next(e for e in p.history if e.get('graph_presentation',{}).get('title')=='Edited strength')
        w.show_result(saved);w.edit_graph_dialog(saved);app.processEvents()
        assert pane.controls['footnote'].text()=='Saved on close' and not w.output_header_bar.isVisible()
        rerun=p.rerun_result(saved);assert rerun['graph_presentation']==saved['graph_presentation']
        # Switching graphs flushes the pending edit against its original entry.
        pane.controls['subtitle'].setText('Bound to old graph');pane.controls['subtitle'].textEdited.emit('Bound to old graph')
        w.show_result(rerun);assert saved['graph_presentation']['subtitle']=='Bound to old graph'
        assert rerun['graph_presentation']['subtitle']=='Production sample'
        w.close_graph_options()
        checkpoint('automatic formulas and dynamic conditional formatting')
        p.new();p.worksheet=Worksheet('Formula checks',[Column('Input',values=[1,2,3]),Column('Total'),Column('Twice')])
        p.assign_formula(2,'C1*2');p.assign_formula(1,'C3+1')
        p.set_cell_highlight([1],[1],'#d4edda')
        p.apply_conditional_formatting(1,'greater_than',10,color='#f8d7da')
        w._show_welcome();w.refresh();app.processEvents()
        w.table.item(1,0).setText('8');app.processEvents()
        assert p.worksheet.columns[1].values[1]==17 and float(w.table.item(1,1).text())==17,([c.values for c in p.worksheet.columns],w.table.item(1,1).text(),w.page)
        from PySide6.QtCore import Qt
        assert w.table.item(1,1).data(Qt.ItemDataRole.BackgroundRole).name()=='#f8d7da'
        w.undo();app.processEvents()
        assert p.worksheet.columns[1].values[1]==5
        assert w.table.item(1,1).data(Qt.ItemDataRole.BackgroundRole).name()=='#d4edda'
        w.redo();app.processEvents();assert p.worksheet.columns[1].values[1]==17
        def formula_menu():
            w._formula_test_menu=w.build_worksheet_context_menu();menu=w._formula_test_menu
            return next(a.menu() for a in menu.actions() if a.text()=='Formulas')
        menu=formula_menu();auto=next(a for a in menu.actions() if a.text()=='Calculate All Formulas Automatically')
        assert auto.isChecked();auto.trigger();assert not p.auto_calculate_formulas
        w.table.item(1,0).setText('9');app.processEvents()
        assert p.worksheet.columns[1].values[1]==17
        next(a for a in formula_menu().actions() if a.text()=='Calculate All Formulas Now').trigger()
        assert p.worksheet.columns[1].values[1]==19
        next(a for a in formula_menu().actions() if a.text()=='Calculate All Formulas Automatically').trigger()
        assert p.auto_calculate_formulas
        w.activateWindow();app.processEvents();w.table.setCurrentCell(0,0);w.table.setFocus();app.processEvents()
        # Windows clipboard ownership can settle after copying a graph image.
        from PySide6.QtCore import QEventLoop
        for clipboard_attempt in range(50):
            QApplication.clipboard().setText('10\n11\n')
            app.processEvents()
            clipboard_loop=QEventLoop();QTimer.singleShot(50,clipboard_loop.quit);clipboard_loop.exec()
            app.processEvents()
            if QApplication.clipboard().text()=='10\n11\n':break
        assert QApplication.clipboard().text()=='10\n11\n', 'Windows clipboard did not accept worksheet test input'
        w.table.setFocus();app.processEvents()
        assert QApplication.focusWidget() is w.table, repr(QApplication.focusWidget())
        w.paste_cells();app.processEvents()
        assert p.worksheet.columns[1].values[:2]==[21,23], ([c.values for c in p.worksheet.columns],repr(QApplication.focusWidget()),w.table.currentRow(),w.table.currentColumn(),w.statusBar().currentMessage(),QApplication.clipboard().text())
        formulas_target=Path(temp)/'dynamic-formulas.mpx';w.save_path(formulas_target);w.load_path(formulas_target)
        w.table.item(1,0).setText('2');app.processEvents()
        assert p.worksheet.columns[1].values[1]==5
        assert w.table.item(1,1).data(Qt.ItemDataRole.BackgroundRole).name()=='#d4edda'
        p.clear_conditional_formatting([1]);w.refresh()
        assert w.table.item(1,1).data(Qt.ItemDataRole.BackgroundRole).name()=='#d4edda'
        checkpoint('value order and independent worksheet tab scrolling')
        p.new();p.worksheet=Worksheet('Category order',[Column('X',values=[1,2,3,4,5,6]),Column('Y',values=[1,2,3,4,5,6]),Column('Grade','text',['B','A','C','B','A','C'])])
        w.page=0;w._show_welcome();w.refresh();w.table.setCurrentCell(0,2)
        from PySide6.QtWidgets import QRadioButton,QPlainTextEdit,QDialogButtonBox
        def enter_value_order():
            dialog=QApplication.activeModalWidget()
            next(r for r in dialog.findChildren(QRadioButton) if r.text().startswith('User-specified')).click()
            dialog.findChild(QPlainTextEdit).setPlainText('C\nB\nA')
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
        QTimer.singleShot(0,enter_value_order);w.column_value_order_dialog()
        assert p.worksheet.columns[2].metadata['value_order']['values']==['C','B','A']
        ordered=p.expanded_graph('bar_chart',[2]);w.show_result(ordered);app.processEvents()
        assert w._active_chart_widget.panels[0]['categories']==['C','B','A']
        target=Path(temp)/'value-order.mpx';w.save_path(target);w.load_path(target)
        saved=next(e for e in p.history if e.get('recipe',{}).get('action')=='expanded_graph')
        assert not p.result_stale(saved)
        p.set_column_value_order(2,'occurrence');assert p.result_stale(saved)
        assert p.rerun_result(saved)['result']['panels'][0]['categories']==['B','A','C']
        p.new();p.worksheet=Worksheet('Long worksheet',[Column('Input',values=list(range(650)))])
        for number in range(24):p.add_worksheet('Worksheet '+str(number+2)+' with a long name')
        p.select_worksheet(0);w.page=0;w._show_welcome();w.refresh();app.processEvents()
        strip=w.worksheet_tab_strip;scroll=strip.horizontalScrollBar();strip.sync();app.processEvents()
        assert scroll.maximum()>0
        w.worksheet_tab_nav[2].click();app.processEvents();assert scroll.value()>0
        assert p.native_project.active_index==0 and w.page==0
        w.worksheet_tab_nav[3].click();app.processEvents();assert scroll.value()==scroll.maximum()
        offset=scroll.value();p.set_cell(0,0,'999');w.refresh();app.processEvents();assert scroll.value()==offset
        assert p.native_project.active_index==0 and w.page==0
        w.worksheet_tab_nav[0].click();app.processEvents();assert scroll.value()==0
        assert not w.worksheet_tab_nav[0].isEnabled() and not w.worksheet_tab_nav[1].isEnabled()
        w.worksheet_tabs.setCurrentIndex(24);app.processEvents();assert p.native_project.active_index==24
        assert strip.tabs.tabRect(24).right()<=scroll.value()+strip.viewport().width()
        w.worksheet_tabs.setCurrentIndex(0);app.processEvents()
        w.table.scrollToBottom();key(w.table,Qt.Key.Key_PageDown);app.processEvents()
        assert w.page==1 and w.table.verticalHeaderItem(0).text()=='301'
        assert w.table.item(0,0).text()=='300'
        w.table.scrollToTop();key(w.table,Qt.Key.Key_PageUp);app.processEvents();assert w.page==0
        # Scrolling tabs never changes active data page or worksheet identity.
        w._scroll_row_page(1);page_before=w.page;sheet_before=p.native_project.active_index
        w.worksheet_tab_nav[3].click();app.processEvents()
        assert w.page==page_before and p.native_project.active_index==sheet_before
        from PySide6.QtCore import QPoint,QPointF
        from PySide6.QtGui import QWheelEvent
        def wheel_rows(delta):
            event=QWheelEvent(QPointF(20,20),QPointF(20,20),QPoint(0,0),QPoint(0,delta),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
            QApplication.sendEvent(w.table.viewport(),event);app.processEvents()
        w.table.scrollToBottom();wheel_rows(-120);assert w.page==2
        w.table.scrollToTop();wheel_rows(120);assert w.page==1
        w.table.setCurrentCell(299,0);key(w.table,Qt.Key.Key_Down);app.processEvents()
        assert w.page==2 and w.table.currentRow()==0
        from statcraft.graph_edit_smoke import verify_graph_editing
        verify_graph_editing(app,p,w,temp,checkpoint)
        from statcraft.composition_smoke import verify_compositions
        verify_compositions(app,p,w,temp,checkpoint)
        from statcraft.column_operations_smoke import verify_column_operations
        verify_column_operations(app,p,w,temp,checkpoint)
        from statcraft.similar_graph_smoke import verify_similar_graph
        verify_similar_graph(app,p,w,temp,checkpoint)
        from statcraft.histogram_creation_smoke import verify_histogram_creation
        verify_histogram_creation(app,p,w,temp,checkpoint)
        from statcraft.output_workspace_smoke import verify_output_workspace
        verify_output_workspace(app,p,w,temp,checkpoint)
        from statcraft.data_prep_smoke import verify_data_preparation
        verify_data_preparation(app,p,w,temp,checkpoint)
        from statcraft.glm_smoke import verify_general_linear_model
        verify_general_linear_model(app,p,w,temp,checkpoint)
        from statcraft.response_surface_smoke import verify_response_surface
        verify_response_surface(app,p,w,temp,checkpoint)
        from statcraft.gage_rr_smoke import verify_gage_rr
        verify_gage_rr(app,p,w,temp,checkpoint)
        from statcraft.prediction_smoke import verify_prediction
        verify_prediction(app,p,w,temp,checkpoint)
        from statcraft.logistic_smoke import verify_binary_logistic
        verify_binary_logistic(app,p,w,temp,checkpoint)
        from statcraft.optimizer_smoke import verify_response_optimizer
        verify_response_optimizer(app,p,w,temp,checkpoint)
        from statcraft.oneway_smoke import verify_oneway_anova
        verify_oneway_anova(app,p,w,temp,checkpoint)
        from statcraft.subgroup_control_smoke import verify_subgroup_control
        verify_subgroup_control(app,p,w,temp,checkpoint)
        from statcraft.equal_variances_smoke import verify_equal_variances
        verify_equal_variances(app,p,w,temp,checkpoint)
        from statcraft.two_sample_t_smoke import verify_two_sample_t
        verify_two_sample_t(app,p,w,temp,checkpoint)
        from statcraft.one_sample_z_smoke import verify_one_sample_z
        verify_one_sample_z(app,p,w,temp,checkpoint)
        from statcraft.one_sample_proportion_smoke import verify_one_sample_proportion
        verify_one_sample_proportion(app,p,w,temp,checkpoint)
        from statcraft.two_sample_proportion_smoke import verify_two_sample_proportion
        verify_two_sample_proportion(app,p,w,temp,checkpoint)
        from statcraft.one_sample_poisson_smoke import verify_one_sample_poisson
        verify_one_sample_poisson(app,p,w,temp,checkpoint)
        from statcraft.two_sample_poisson_smoke import verify_two_sample_poisson
        verify_two_sample_poisson(app,p,w,temp,checkpoint)
        from statcraft.variance_smoke import verify_variances
        verify_variances(app,p,w,temp,checkpoint)
        from statcraft.capability_smoke import verify_capability
        verify_capability(app,p,w,temp,checkpoint)
        from statcraft.sixpack_smoke import verify_sixpack
        verify_sixpack(app,p,w,temp,checkpoint)
        from statcraft.imr_smoke import verify_imr
        verify_imr(app,p,w,temp,checkpoint)
        from statcraft.attribute_control_smoke import verify_attribute_control
        verify_attribute_control(app,p,w,temp,checkpoint)
        from statcraft.time_weighted_control_smoke import verify_time_weighted_control
        verify_time_weighted_control(app,p,w,temp,checkpoint)
        from statcraft.rare_event_control_smoke import verify_rare_event_control
        verify_rare_event_control(app,p,w,temp,checkpoint)
        from statcraft.multivariate_control_smoke import verify_multivariate_control
        verify_multivariate_control(app,p,w,temp,checkpoint)
        from statcraft.pareto_smoke import verify_pareto_chart
        verify_pareto_chart(app,p,w,temp,checkpoint)
        from statcraft.type1_gage_smoke import verify_type1_gage
        verify_type1_gage(app,p,w,temp,checkpoint)
        from statcraft.attribute_capability_smoke import verify_attribute_capability
        verify_attribute_capability(app,p,w,temp,checkpoint)
        from statcraft.capability_between_within_smoke import verify_capability_between_within
        verify_capability_between_within(app,p,w,temp,checkpoint)
        from statcraft.acceptance_smoke import verify_acceptance_control_chart
        verify_acceptance_control_chart(app,p,w,temp,checkpoint)
        from statcraft.capability_aiag_vda_smoke import verify_capability_aiag_vda
        verify_capability_aiag_vda(app,p,w,temp,checkpoint)
        from statcraft.shewhart_extended_limits_smoke import verify_shewhart_extended_limits
        verify_shewhart_extended_limits(app,p,w,temp,checkpoint)
        from statcraft.capability_nonnormal_smoke import verify_capability_nonnormal
        verify_capability_nonnormal(app,p,w,temp,checkpoint)
        from statcraft.reliability_smoke import verify_reliability_distribution
        verify_reliability_distribution(app,p,w,temp,checkpoint)
        from statcraft.capability_automated_smoke import verify_capability_automated
        verify_capability_automated(app,p,w,temp,checkpoint)
        from statcraft.new_analysis_integrity_smoke import verify_new_analysis_integrity
        verify_new_analysis_integrity(app,p,w,temp,checkpoint)
        from statcraft.multiple_capability_smoke import verify_multiple_capability
        verify_multiple_capability(app,p,w,temp,checkpoint)
        from statcraft.doe_planner_excel_smoke import verify_doe_planner_excel
        verify_doe_planner_excel(app,p,w,temp,checkpoint)
        from statcraft.mixture_taguchi_smoke import verify_mixture_taguchi
        verify_mixture_taguchi(app,p,w,temp,checkpoint)
        from statcraft.dynamic_taguchi_smoke import verify_dynamic_taguchi
        verify_dynamic_taguchi(app,p,w,temp,checkpoint)
        from statcraft.mixture_exploration_smoke import verify_mixture_exploration
        verify_mixture_exploration(app,p,w,temp,checkpoint)
        from statcraft.mixture_multi_smoke import verify_mixture_multi
        verify_mixture_multi(app,p,w,temp,checkpoint)
        from statcraft.mixture_process_smoke import verify_mixture_process
        verify_mixture_process(app,p,w,temp,checkpoint)
        from statcraft.mixture_condition_smoke import verify_mixture_condition
        verify_mixture_condition(app,p,w,temp,checkpoint)
        from statcraft.mixture_joint_smoke import verify_mixture_joint
        verify_mixture_joint(app,p,w,temp,checkpoint)
        from statcraft.native_model_smoke import verify_native_model_reconstruction
        verify_native_model_reconstruction(app,p,w,temp,checkpoint)
        from statcraft.response_surface_catalog_smoke import verify_surface_catalog
        verify_surface_catalog(app,p,w,temp,checkpoint)
        from statcraft.chart_hover_smoke import verify_chart_hover
        verify_chart_hover(app,p,w,temp,checkpoint)
        from statcraft.native_output_smoke import verify_native_outputs
        verify_native_outputs(app,p,w,temp,checkpoint)
        from statcraft.msa_advanced_smoke import verify_msa_advanced
        verify_msa_advanced(app,p,w,temp,checkpoint)
        from statcraft.tolerance_intervals_smoke import verify_tolerance_intervals
        verify_tolerance_intervals(app,p,w,temp,checkpoint)
        from statcraft.one_sample_t_smoke import verify_one_sample_t
        verify_one_sample_t(app,p,w,temp,checkpoint)
        from statcraft.paired_t_smoke import verify_paired_t
        verify_paired_t(app,p,w,temp,checkpoint)
        from statcraft.model_plots_smoke import verify_model_plots
        verify_model_plots(app,p,w,temp,checkpoint)
        from statcraft.startup_zoom_smoke import verify_startup_zoom
        verify_startup_zoom(app,p,w,temp,checkpoint)
        from statcraft.office_export_smoke import verify_office_export
        verify_office_export(app,p,w,temp,checkpoint)
        from statcraft.printing_smoke import verify_printing
        verify_printing(app,p,w,temp,checkpoint)
        from statcraft.graph_builder_smoke import verify_graph_builder
        verify_graph_builder(app,p,w,temp,checkpoint)
        from statcraft.categorical_points_smoke import verify_categorical_points
        verify_categorical_points(app,p,w,temp,checkpoint)
        from statcraft.dotplot_creation_smoke import verify_dotplot_creation
        verify_dotplot_creation(app,p,w,temp,checkpoint)
        from statcraft.boxplot_creation_smoke import verify_boxplot_creation
        verify_boxplot_creation(app,p,w,temp,checkpoint)
        from statcraft.time_series_smoke import verify_time_series
        verify_time_series(app,p,w,temp,checkpoint)
        from statcraft.nonparametrics_smoke import verify_nonparametrics
        verify_nonparametrics(app,p,w,temp,checkpoint)
        from statcraft.multivariate_smoke import verify_multivariate
        verify_multivariate(app,p,w,temp,checkpoint)
        from statcraft.equivalence_smoke import verify_equivalence
        verify_equivalence(app,p,w,temp,checkpoint)
        from statcraft.power_smoke import verify_power
        verify_power(app,p,w,temp,checkpoint)
        from statcraft.tables_smoke import verify_tables
        verify_tables(app,p,w,temp,checkpoint)
    result = {'preview':True,'frozen':bool(getattr(sys,'frozen',False)), 'qt_widgets':'passed',
              'worksheet_edit_undo':'passed','embedded_charts':'passed','mpx_save_reopen_rerun':'passed',
              'correlation_proportions_dialogs_reports_mpx':'passed',
              'variable_list_scatter_yx_and_column_name_row':'passed',
              'mpx_binary_blob_load_edit_save':'passed',
              'normality_variance_dialogs_plot_mpx_rerun':'passed',
              'six_scatter_modes_group_fits_mpx_rerun':'passed',
              'doe_create_analyze_dialogs_mpx_rerun':'passed',
              'mpx_append_numeric_column_save_reopen_rerun':'passed',
              'fractional_generators_terms_aliases_mpx_rerun':'passed',
              'mpx_numeric_rows_dialog_blob_save_reopen_rerun':'passed',
              'new_mpx_workbook_tabs_rename_duplicate_save_rerun':'passed',
              'owned_mpx_text_grid_groups_missing_save_rerun':'passed',
              'owned_mpx_dates_type_display_clipboard_precision_save':'passed',
              'stored_constants_matrices_editors_calculator_mpx':'passed',
              'worksheet_tab_enter_editor_navigation_delete_confirmation':'passed',
              'all_26_graph_menu_actions_dialogs_render_graph_first_mpx_rerun':'passed',
              'statcraft_22_toolbar_21_icons_chrome_statusbar_workflows':'passed',
              'statcraft_selection_highlighting_context_menus_navigator_logo':'passed',
              'docked_graph_editor_live_annotations_axes_mpx_and_removed_header':'passed',
              'automatic_formula_dependencies_global_menu_atomic_undo_mpx':'passed',
              'dynamic_conditional_colors_formula_edits_manual_styles_mpx':'passed',
              'value_order_text_modes_counts_groups_tables_mpx_rerun':'passed',
              'worksheet_tab_scroll_preserves_sheet_rows_and_row_page_navigation':'passed',
              'graph_object_hit_testing_doubleclick_styles_undo_export_mpx':'passed',
              'histogram_scales_normal_fit_counts_density_cumulative_mpx':'passed',
              'graph_style_renderers_3d_camera_preserved':'passed',
              'interactive_brushing_source_rows_navigation':'passed',
              'by_variable_panels_styles_shared_scales_mpx_rerun':'passed',
              'ordered_graph_layouts_edit_undo_mpx_snapshots':'passed',
              'column_header_insert_move_delete_formula_mpx_copy':'passed',
              'make_similar_original_new_roles_options_source_mpx':'passed',
              'histogram_variants_group_fits_roles_styles_mpx_similar_layout':'passed',
              'boxplot_variants_group_roles_display_mpx_similar_layout':'passed',
              'dotplot_seven_variants_stacking_roles_brushing_mpx_similar_layout':'passed',
              'individual_interval_eight_variants_display_ci_se_pool_bonferroni_mpx':'passed',
              'graph_builder_live_drop_roles_nine_types_isolation_mpx_similar':'passed',
              'printing_preview_pdf_worksheet_pagination_native_cancel':'passed',
              'office_native_docx_pptx_graph_report_context_cancel':'passed',
              'output_zoom_proxy_geometry_interaction_heatmap_office':'passed',
              'output_workspace_tabs_close_reopen_report_mpx':'passed',
              'typed_data_preparation_dialogs_native_source_mpx':'passed',
              'glm_fixed_factors_interactions_child_dialogs_residuals_mpx':'passed',
              'response_surface_designs_children_quadratic_lof_mpx':'passed',
              'gage_rr_crossed_anova_options_six_graphs_rows_mpx_columns':'passed',
              'prediction_three_models_values_columns_intervals_children_mpx_remapping':'passed',
              'binary_logistic_fit_events_terms_roc_predict_mpx_remapping':'passed',
              'response_optimizer_desirability_constraints_plot_mpx_remapping':'passed',
              'model_plots_factorial_contour_surface_predict_five_models_mpx_remapping':'passed',
              'oneway_anova_stacked_unstacked_comparisons_graphs_mpx':'passed',
              'subgroup_control_charts_xbar_r_xbar_s_eight_tests_mpx':'passed',
              'test_equal_variances_dialog_summary_plot_storage_mpx':'passed',
              'two_sample_t_dialog_plots_mpx':'passed',
              'one_sample_z_dialog_plots_mpx':'passed',
              'one_sample_proportion_dialog_reports_mpx':'passed',
              'two_sample_proportion_dialog_reports_mpx':'passed',
              'one_sample_poisson_dialog_reports_mpx':'passed',
              'two_sample_poisson_dialog_reports_mpx':'passed',
              'one_and_two_variances_dialogs_reports_mpx':'passed',
              'capability_analysis_normal_dialogs_reports_plot_mpx':'passed',
              'capability_sixpack_normal_dialogs_reports_plot_mpx':'passed',
              'imr_control_chart_dialogs_reports_plot_mpx':'passed',
              'attribute_control_charts_p_np_c_u_dialogs_reports_plot_mpx':'passed',
              'time_weighted_control_charts_ewma_ma_cusum_dialogs_reports_plot_mpx':'passed',
              'rare_event_control_charts_g_t_dialogs_reports_plot_mpx':'passed',
              'multivariate_control_charts_tsquared_genvar_mewma_mpx':'passed',
              'pareto_chart_dialog_reports_plot_mpx':'passed',
              'type1_gage_dialog_reports_plot_mpx':'passed',
              'tolerance_intervals_dialog_reports_plot_mpx':'passed',
              'attribute_capability_dialog_graph_mpx_bindings':'passed',
              'capability_between_within_dialog_reports_plot_mpx':'passed',
              'acceptance_control_chart_dialog_reports_plot_mpx':'passed',
              'capability_aiag_vda_machine_dialog_reports_plot_mpx':'passed',
              'shewhart_extended_limits_warning_bands_mpx':'passed',
              'capability_nonnormal_distribution_transform_mpx':'passed',
              'reliability_distribution_analysis_right_censoring_mpx':'passed',
              'capability_nonparametric_and_automated_tournament_mpx':'passed',
              'msa_advanced_nested_linearity_mpx':'passed',
              'new_analysis_graphs_sources_statistical_integrity_mpx':'passed',
              'multiple_variable_capability_dialogs_graphs_sources_mpx':'passed',
              'doe_planner_eleven_families_live_preview_excel_converter_mpx':'passed',
              'mixture_taguchi_models_prediction_dialogs_graphs_sources_mpx':'passed',
              'dynamic_taguchi_slopes_sn_reference_dialog_graphs_sources_mpx':'passed',
              'mixture_contours_optimizer_constraints_dialog_graphs_sources_mpx':'passed',
              'mixture_multiple_desirability_interactive_profiles_reoptimize_sources_mpx':'passed',
              'mixture_process_blocks_covariates_fit_prediction_dialogs_sources_mpx':'passed',
              'mixture_process_conditional_contours_optimizer_coded_holds_intervals_sources_mpx':'passed',
              'mixture_joint_optimizer_mpx':'passed',
              'native_model_reconstruction_mpx':'passed',
              'response_surface_58_catalog_matrix_blocks_prediction_graphs_mpx':'passed',
              'chart_hover_histograms_points_saved_native_layout_capture':'passed',
              'native_mpx_saved_reports_graphs_gallery_capture_copy':'passed',
              'one_sample_t_dialog_plots_mpx':'passed',
              'paired_t_dialog_plots_mpx':'passed',
              'time_series_forecasting_models_mpx':'passed',
              'nonparametrics_statistical_tests_mpx':'passed',
              'multivariate_statistical_analysis_mpx':'passed',
              'equivalence_tests_tost_mpx':'passed',
              'power_and_sample_size_mpx':'passed',
              'tables_and_chi_square_mpx':'passed',
              'style':app.style().objectName(),'qt_platform':app.platformName(),'native_full_parity':False}
    Path(destination).write_text(json.dumps(result,indent=2),encoding='utf-8')
    p.dirty = False; p._results_dirty = False; w.close()
    # Dispose the widget tree before interpreter teardown; no live tab signals.
    from PySide6.QtCore import QCoreApplication,QEvent
    w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    app.processEvents()


def verify_startup(destination, project=None):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from statcraft.modern_app import ModernWindow
    from statcraft.startup import start_window,dispose_startup
    from statcraft.verification_fonts import load_verification_fonts
    app=QApplication([]);load_verification_fonts(app)
    state=start_window(app,ModernWindow,[project] if project else [],minimum_ms=100)
    attempts=[0]
    def finish():
        try:
            window=state['window']
            if (window is None or not window.isMaximized()) and not state['error'] and attempts[0]<100:
                attempts[0]+=1;QTimer.singleShot(50,finish);return
            assert state['ready'] and window.isMaximized() and not state['splash'].isVisible()
            if project:assert window.presenter.worksheet.row_count>0
            window.grab().save(str(Path(destination).with_suffix('.png')))
            result={'frozen':bool(getattr(sys,'frozen',False)),'maximized':True,'splash_dismissed':True,'rows':window.presenter.worksheet.row_count,'project_loaded':bool(project)}
            Path(destination).write_text(json.dumps(result,indent=2),encoding='utf-8')
            window.presenter.dirty=False;window.presenter._results_dirty=False;window.close();app.quit()
        except Exception as exc:
            Path(destination).write_text(json.dumps({'error':str(exc)}),encoding='utf-8');app.exit(1)
    QTimer.singleShot(800,finish)
    result=app.exec();dispose_startup(app);return result


if __name__ == '__main__':
    if len(sys.argv) in (3,4) and sys.argv[1]=='--verify-startup':
        raise SystemExit(verify_startup(sys.argv[2],sys.argv[3] if len(sys.argv)==4 else None))
    elif len(sys.argv)==4 and sys.argv[1]=='--verify-native-output':
        from PySide6.QtWidgets import QApplication
        from statcraft.modern_app import ModernWindow
        from statcraft.native_output_smoke import verify_saved_outputs
        from statcraft.verification_fonts import load_verification_fonts
        app=QApplication([]);load_verification_fonts(app);window=ModernWindow()
        verify_saved_outputs(app,window,sys.argv[2],sys.argv[3])
        window.presenter.dirty=False;window.presenter._results_dirty=False;window.close()
        window.deleteLater()
        from PySide6.QtCore import QCoreApplication,QEvent
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
    elif len(sys.argv)==4 and sys.argv[1]=='--verify-project':
        import hashlib
        from PySide6.QtWidgets import QApplication
        from statcraft.modern_app import ModernWindow
        source=Path(sys.argv[2]); before=hashlib.sha256(source.read_bytes()).hexdigest()
        app=QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(app)
        window=ModernWindow(); window.load_path(source); window.show(); app.processEvents()
        result={'frozen':bool(getattr(sys,'frozen',False)), 'source_sha256':before,
                'worksheets':len(window.presenter.native_project.worksheets),
                'active_rows':window.presenter.worksheet.row_count,
                'active_columns':len(window.presenter.worksheet.columns),
                'ui_rendered':not window.grab().isNull(),'qt_platform':app.platformName(),
                'original_unchanged':before==hashlib.sha256(source.read_bytes()).hexdigest()}
        if window.presenter.worksheet.row_count>=8 and window.presenter.worksheet.columns[0].kind=='number':
            entry=window.presenter.normality(0); window.show_result(entry)
            window.result_tabs.setCurrentIndex(1); app.processEvents()
            from statcraft.modern_charts import ChartWidget
            chart=window.findChildren(ChartWidget)[-1]
            assert chart.error is None and not chart.grab().isNull()
            result['normality_observations']=entry['result']['count']
            result['normal_probability_plot_rendered']=True
            window.presenter.one_variance(0)
            result['one_variance_calculated']=True
        Path(sys.argv[3]).write_text(json.dumps(result,indent=2),encoding='utf-8')
        window.presenter.dirty=False; window.presenter._results_dirty=False; window.close()
    elif len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        try:
            smoke(sys.argv[2])
            import os
            os._exit(0)
        except Exception:
            import traceback
            Path(sys.argv[2]).write_text(traceback.format_exc(),encoding='utf-8')
            if sys.stderr is not None:traceback.print_exc()
            raise SystemExit(1)
    else:
        from statcraft.modern_app import main
        raise SystemExit(main())
