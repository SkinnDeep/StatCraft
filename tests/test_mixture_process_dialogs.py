"""Actual role selection, coding edits and typed saved-model prediction dialogs."""
import copy,math,unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QTableWidgetItem,QDialogButtonBox
from statcraft.model import Worksheet,Column
from statcraft.doe_planner import build_plan
from statcraft.mixture_process_dialogs import MixtureProcessDialog,MixtureProcessPredictionDialog
from statcraft.mixture_process_model import fit,predict
from statcraft.verification_fonts import load_verification_fonts


def sheet(numeric_block=False):
    rows=[]
    for repeat in range(2):
        for a in (.15,.35,.65,.85):
            for temp in (100.,150.,200.):
                for block in (1,2):
                    cov=math.sin(len(rows)*1.3)+.2*(len(rows)%3)
                    z=(temp-150)/50
                    response=10*a+20*(1-a)+2*a*z-3*(1-a)*z+1.2*cov+4*(block==2)+.01*math.sin(len(rows)*.7)
                    rows.append((a,1-a,temp,block if numeric_block else ('First' if block==1 else 'Second'),cov,response))
    columns=[Column(name,kind,[row[i] for row in rows]) for i,(name,kind) in enumerate([('A','number'),('B','number'),('Temperature','number'),('Batch','number' if numeric_block else 'text'),('Purity','number'),('Strength','number')])]
    columns.append(Column('Strength',values=[v+.2 for v in columns[5].values]))
    return Worksheet('Process study',columns)


def fit_entry(ws=None,process=True,block=True,covariate=True):
    ws=ws or sheet()
    params=dict(response_index=5,component_indices=[0,1],process_indices=[2] if process else [],
                block_index=3 if block else None,covariate_indices=[4] if covariate else [],model='linear',total=1.,
                options={'process_coding':[{'low':100.,'high':200.}] if process else None})
    result=fit(ws,**params);params['options']=copy.deepcopy(result['options'])
    return ws,dict(title=result['title'],time='2026-10-28',result=result,recipe={'action':'analyze_mixture_process','parameters':params})


class MixtureProcessDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def setUp(self):self.widgets=[]
    def tearDown(self):
        for widget in self.widgets:widget.close();widget.deleteLater()
        self.app.processEvents()

    def dialog(self,ws=None):
        d=MixtureProcessDialog(ws or sheet());self.widgets.append(d);return d

    def configured(self,ws=None):
        d=self.dialog(ws)
        for key,text in [('response_index','C6'),('component_indices','C1 C2'),('process_indices','C3'),('block_index','C4'),('covariate_indices','C5')]:d.controls[key].setText(text)
        d.controls['model'].setCurrentText('Linear');return d

    def prediction(self,ws,e):
        d=MixtureProcessPredictionDialog(ws,[e]);self.widgets.append(d)
        for column,value in enumerate((.3,.7,150.,.2) if e['recipe']['parameters']['process_indices'] and e['recipe']['parameters']['covariate_indices'] else []):d.table.setItem(0,column,QTableWidgetItem(str(value)))
        return d

    def select(self,d,key,index):
        d.show();QTest.mouseClick(d.controls[key],Qt.MouseButton.LeftButton);self.app.processEvents()
        item=next(d.available.item(i) for i in range(d.available.count()) if d.available.item(i).data(Qt.ItemDataRole.UserRole)==index)
        QTest.mouseClick(d.available.viewport(),Qt.MouseButton.LeftButton,pos=d.available.visualItemRect(item).center())
        QTest.mouseClick(d.select_button,Qt.MouseButton.LeftButton);self.app.processEvents()

    def test_mouse_named_role_transfer_keeps_positional_identity_with_duplicate_headers(self):
        d=self.dialog();self.select(d,'response_index',6);self.select(d,'component_indices',0);self.select(d,'component_indices',1)
        self.select(d,'process_indices',2);self.select(d,'block_index',3);self.select(d,'covariate_indices',4)
        values=d.values();self.assertEqual(values['response_index'],6);self.assertEqual(values['component_indices'],[0,1])
        self.assertEqual(values['block_index'],3);self.assertIn('Batch',d.controls['block_index'].text());self.assertIn('C4-T',d.controls['block_index'].text())

    def test_components_metadata_autofills_only_verified_positions_and_bounds(self):
        ws=build_plan('simplex_lattice',[dict(name=n,low=.1,high=.8) for n in ('Binder','Resin','Additive')],options={'degree':3})
        ws.columns.extend([Column('Temperature',values=[100+i for i in range(ws.row_count)]),Column('Response',values=[10+i for i in range(ws.row_count)])])
        d=self.dialog(ws);self.assertIn('C5: "Binder"',d.controls['component_indices'].text())
        d.controls['response_index'].setText('C9');d.controls['process_indices'].setText('C8')
        self.assertEqual(d.values()['options']['bounds'],[{'low':.1,'high':.8}]*3)
        ws.columns[4].name='Changed';other=self.dialog(ws);self.assertEqual(other.controls['component_indices'].text(),'')

    def test_optional_roles_and_overlap_errors_are_inline(self):
        d=self.configured()
        for key in ('process_indices','block_index','covariate_indices'):d.controls[key].clear()
        d.validate();self.assertIsNone(d.parameters);self.assertIn('process variable, block or covariate',d.error.text())
        d.controls['process_indices'].setText('C1');d.validate();self.assertIsNone(d.parameters);self.assertIn('separate',d.error.text())
        d.controls['process_indices'].setText('C3');d.controls['block_index'].setText('C4 C5');d.validate();self.assertIn('at most 1',d.error.text())

    def test_fit_form_executes_actual_engine_and_preserves_options(self):
        d=self.configured();d.controls['confidence'].setText('90');d.controls['show_graphs'].setChecked(False);d.controls['title'].setText('Blend at temperature')
        d.validate();self.assertEqual(d.result(),1,d.error.text());result=fit(d.worksheet,**d.parameters)
        self.assertEqual(result['analysis'],'mixture_process_model');self.assertEqual(result['process_indices'],[2])
        self.assertEqual(result['block_index'],3);self.assertEqual(result['covariate_indices'],[4]);self.assertEqual(result['confidence'],.9)

    def test_custom_process_coding_keyboard_edit_and_reorder_follow_columns(self):
        ws=sheet();ws.columns.append(Column('Pressure',values=[i%5 for i in range(ws.row_count)]))
        d=self.configured(ws);d.controls['process_indices'].setText('C3 C8');d.custom_coding.setChecked(True);d.show();self.app.processEvents()
        item=d.coding_table.item(0,1);QTest.mouseClick(d.coding_table.viewport(),Qt.MouseButton.LeftButton,pos=d.coding_table.visualItemRect(item).center());d.coding_table.editItem(item);self.app.processEvents()
        QTest.keyClick(d.coding_table.focusWidget(),Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier);QTest.keyClicks(d.coding_table.focusWidget(),'90');QTest.keyClick(d.coding_table.focusWidget(),Qt.Key.Key_Return);self.app.processEvents()
        d.coding_table.item(0,2).setText('210');d.coding_table.item(1,1).setText('-1');d.coding_table.item(1,2).setText('5')
        d.controls['process_indices'].setText('C8 C3');values=d.values()
        self.assertEqual(values['options']['process_coding'],[{'low':-1.,'high':5.},{'low':90.,'high':210.}])

    def test_bad_process_ranges_total_confidence_and_component_model_rejected(self):
        d=self.configured();d.custom_coding.setChecked(True);d.coding_table.item(0,1).setText('200');d.validate()
        self.assertIsNone(d.parameters);self.assertIn('less than',d.error.text())
        d.coding_table.item(0,1).setText('100')
        for key,value in [('total','0'),('total','nan'),('confidence','100')]:
            d.controls['total'].setText('1');d.controls['confidence'].setText('95');d.controls[key].setText(value);d.validate();self.assertIsNone(d.parameters)
        d.controls['total'].setText('1');d.controls['confidence'].setText('95');d.controls['model'].setCurrentText('Special cubic');d.validate();self.assertIn('three',d.error.text())

    def test_prediction_named_role_headers_known_block_and_real_intervals(self):
        ws,e=fit_entry();d=self.prediction(ws,e);d.confidence.setText('90');d.validate();self.assertEqual(d.result(),1,d.error.text())
        headers=[d.table.horizontalHeaderItem(i).text() for i in range(d.table.columnCount())]
        self.assertIn('Component C1',headers[0]);self.assertIn('Temperature',headers[2]);self.assertIn('Purity',headers[3]);self.assertIn('Batch',headers[4])
        result=predict(e['result'],d.parameters['component_rows'],d.parameters['process_rows'],d.parameters['covariate_rows'],d.parameters['block_values'],d.parameters['confidence'])
        row=result['rows'][0];self.assertLess(row['prediction_low'],row['ci_low']);self.assertLess(row['ci_low'],row['fit']);self.assertLess(row['fit'],row['ci_high'])

    def test_prediction_rejects_bad_sum_missing_process_and_unknown_block(self):
        ws,e=fit_entry();d=self.prediction(ws,e);d.table.item(0,0).setText('.9');d.validate();self.assertIsNone(d.parameters);self.assertIn('sum',d.error.text())
        d.table.item(0,0).setText('.3');d.table.item(0,2).setText('nan');d.validate();self.assertIsNone(d.parameters);self.assertIn('finite',d.error.text())
        d.table.item(0,2).setText('150');combo=d.table.cellWidget(0,4);combo.addItem('Unknown','Unknown');combo.setCurrentIndex(combo.count()-1);d.validate();self.assertIsNone(d.parameters);self.assertIn('block',d.error.text().lower())

    def test_prediction_numeric_blocks_preserve_type_and_new_rows_keep_known_levels(self):
        ws,e=fit_entry(sheet(True));d=self.prediction(ws,e);combo=d.table.cellWidget(0,4);combo.setCurrentIndex(0);first=combo.currentData()
        d.row_count.setValue(2)
        for column,value in enumerate((.4,.6,175.,.1)):d.table.setItem(1,column,QTableWidgetItem(str(value)))
        d.validate();self.assertEqual(d.result(),1,d.error.text());self.assertIsInstance(d.parameters['block_values'][0],(int,float));self.assertEqual(d.parameters['block_values'][0],first)
        self.assertEqual(len(d.parameters['process_rows']),2)

    def test_covariate_only_and_block_only_prediction_roles_are_optional_arrays(self):
        for block,cov in ((False,True),(True,False)):
            ws,e=fit_entry(process=False,block=block,covariate=cov);d=self.prediction(ws,e)
            for column,value in enumerate((.3,.7,.2) if cov else (.3,.7)):d.table.setItem(0,column,QTableWidgetItem(str(value)))
            d.validate();self.assertEqual(d.result(),1,d.error.text());self.assertIsNone(d.parameters['process_rows'])
            self.assertEqual(d.parameters['covariate_rows'],[[.2]] if cov else None)
            self.assertIsNone(d.parameters['block_values'] if not block else None)

    def test_prediction_empty_models_deleted_sources_and_wrong_model_kind(self):
        ws=sheet();d=MixtureProcessPredictionDialog(ws,[]);self.widgets.append(d);d.validate();self.assertIsNone(d.parameters);self.assertIn('Analyze',d.error.text())
        ws,e=fit_entry();e['source_unavailable']='deleted';d=self.prediction(ws,e);d.validate();self.assertIsNone(d.parameters);self.assertIn('deleted',d.error.text())
        e=copy.deepcopy(e);e.pop('source_unavailable');e['recipe']['action']='analyze_mixture';d=self.prediction(ws,e);d.validate();self.assertIsNone(d.parameters);self.assertIn('mixture/process',d.error.text())

    def test_prediction_current_physical_headers_follow_saved_recipe_after_column_move(self):
        ws,e=fit_entry();ws.columns[0],ws.columns[1]=ws.columns[1],ws.columns[0];e['recipe']['parameters']['component_indices']=[1,0]
        d=self.prediction(ws,e);self.assertIn('C2: "A"',d.table.horizontalHeaderItem(0).text());self.assertIn('C1: "B"',d.table.horizontalHeaderItem(1).text())
        d.validate();self.assertEqual(d.result(),1,d.error.text());self.assertEqual(d.parameters['model_recipe']['parameters']['component_indices'],[1,0])

    def test_finite_process_extrapolation_is_not_silently_clipped(self):
        ws,e=fit_entry();d=self.prediction(ws,e);d.table.item(0,2).setText('250');d.validate();self.assertEqual(d.result(),1,d.error.text())
        self.assertEqual(d.parameters['process_rows'],[[250.]])
        result=predict(e['result'],d.parameters['component_rows'],d.parameters['process_rows'],d.parameters['covariate_rows'],d.parameters['block_values'])
        self.assertTrue(any('outside' in warning.lower() or 'extrapolat' in warning.lower() for warning in result['warnings']))
