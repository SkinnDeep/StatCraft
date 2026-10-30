import copy
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QDialog
from statcraft.app import Presenter
from statcraft.model import Column, Worksheet
from statcraft.recipes import run
from statcraft.similar_graph_dialog import (create_similar_dialog,create_options_dialog,run_similar_graphs,supports_similar)
from statcraft.variable_dialogs import format_variable_list


def document():
    p=Presenter();p.worksheet=Worksheet('Source',[
        Column('Input',values=[1,2,3,4,5,6]),
        Column('Strength (N)',values=[3,5,6,9,11,12]),
        Column('Batch','text',['B','A','B','A','B','A']),
        Column('Response two',values=[5,9,12,17,20,24])])
    return p


class SimilarGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def tearDown(self):
        from PySide6.QtCore import QCoreApplication,QEvent
        for widget in self.app.topLevelWidgets():
            widget.close();widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_scatter_role_grid_and_options_preload_and_new_result(self):
        p=document();source=p.scatter_plot(0,1,'connect_groups',2,'Worksheet','Custom','Input label','Response label')
        source['graph_styles']={'p0:s0':{'color':'#de3421'}}
        saved=copy.deepcopy(source);dialog=create_options_dialog(None,p.worksheet,source)
        try:
            self.assertIn('Strength (N)',dialog.roles.item(0,0).text())
            self.assertIn('Input',dialog.roles.item(0,1).text())
            self.assertIn('Batch',dialog.group_entry.text())
            self.assertEqual(dialog.order.currentText(),'Worksheet')
            self.assertEqual(dialog.labels,dict(title='Custom',x_label='Input label',y_label='Response label'))
            dialog.validate();self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
            created=run_similar_graphs(p,source,dialog.recipes(),appearance=dialog.appearance_settings())[0]
            self.assertEqual(created['recipe'],source['recipe'])
            self.assertNotEqual(created['entry_id'],source['entry_id'])
            self.assertEqual(created['graph_styles'],source['graph_styles'])
            created['graph_styles']['p0:s0']['color']='#000000'
            self.assertEqual(source,saved)
        finally:dialog.close()

    def test_histogram_current_bins_preload_and_edit_retains_frequency_options(self):
        p=document();source=run(p,dict(action='graph',parameters=dict(method='histogram',indices=[1],bins=9)))
        source['histogram_settings']=dict(bins=400,scale='Percent',cumulative=True,fit=None)
        dialog=create_options_dialog(None,p.worksheet,source)
        try:
            self.assertEqual(dialog.controls['bins'].text(),'400')
            dialog.controls['indices'].setText(format_variable_list([3],p.worksheet))
            dialog.controls['bins'].setText('333');dialog.validate()
            created=run_similar_graphs(p,source,dialog.recipes(),appearance=dialog.appearance_settings())[0]
            self.assertEqual(created['recipe']['parameters']['indices'],[3])
            self.assertEqual(created['histogram_settings']['bins'],333)
            self.assertEqual(created['histogram_settings']['scale'],'Percent')
            self.assertEqual(source['histogram_settings']['bins'],400)
        finally:dialog.close()

    def test_reset_appearance_and_histogram_big_bins_still_honored(self):
        p=document();source=run(p,dict(action='graph',parameters=dict(method='histogram',indices=[1],bins=9)))
        source['graph_presentation']={'title':'Custom title'}
        dialog=create_options_dialog(None,p.worksheet,source)
        try:
            dialog.retain_appearance.setChecked(False);dialog.controls['bins'].setText('500');dialog.validate()
            created=run_similar_graphs(p,source,dialog.recipes(),appearance=dialog.appearance_settings())[0]
            self.assertNotIn('graph_presentation',created)
            self.assertEqual(created['histogram_settings']['bins'],500)
        finally:dialog.close()

    def test_expanded_roles_groups_and_distribution_parameters_preloaded(self):
        p=document();source=p.expanded_graph('bubble',[0,1,3],2)
        dialog=create_options_dialog(None,p.worksheet,source)
        try:
            self.assertIn('Input',dialog.controls['variable0'].text())
            self.assertIn('Strength (N)',dialog.controls['variable1'].text())
            self.assertIn('Response two',dialog.controls['variable2'].text())
            self.assertIn('Batch',dialog.controls['groups'].text())
            self.assertEqual(dialog.recipes(),[source['recipe']])
        finally:dialog.close()
        source=p.expanded_graph('distribution_plot',[],distribution='Uniform',parameters={'lower':-5,'upper':7})
        dialog=create_options_dialog(None,p.worksheet,source)
        try:
            self.assertEqual(dialog.controls['distribution'].currentText(),'Uniform')
            self.assertEqual(float(dialog.controls['lower'].text()),-5)
            dialog.controls['upper'].setText('10')
            created=run_similar_graphs(p,source,dialog.recipes())[0]
            self.assertEqual(created['recipe']['parameters']['parameters'],{'lower':-5.,'upper':10.})
        finally:dialog.close()

    def test_expanded_univariate_and_confidence_preloaded(self):
        p=document();source=p.expanded_graph('interval_plot',[1,3],2,confidence=.9)
        dialog=create_options_dialog(None,p.worksheet,source)
        try:
            self.assertIn('Strength (N)',dialog.controls['indices'].text())
            self.assertIn('Response two',dialog.controls['indices'].text())
            self.assertEqual(dialog.controls['confidence'].text(),'0.9')
            self.assertEqual(dialog.recipes(),[source['recipe']])
        finally:dialog.close()

    def test_original_sheet_selected_from_multiworksheet_project_and_persists(self):
        p=document();source=p.scatter_plot(0,1)
        p.add_worksheet('Other')
        other=p.worksheet;self.assertIsNot(p.result_worksheet(source),other)
        created=run_similar_graphs(p,source,[source['recipe']])[0]
        self.assertEqual(created['worksheet_id'],source['worksheet_id'])
        self.assertEqual(p.worksheet.name,'Source')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'similar.mpx';p.save(path)
            reopened=Presenter();reopened.load(path)
            loaded=next(e for e in reopened.history if e['entry_id']==created['entry_id'])
            self.assertFalse(reopened.result_stale(loaded))
            self.assertEqual(reopened.result_worksheet(loaded).name,'Source')

    def test_atomic_multigraph_failure_restores_history_dirty_and_active_sheet(self):
        p=document();source=p.scatter_plot(0,1)
        p.add_worksheet('Other');before_sheet=p.worksheet;before_index=p.native_project.active_index
        before_history=list(p.history);before_dirty=p._results_dirty
        valid=copy.deepcopy(source['recipe']);invalid=copy.deepcopy(valid)
        invalid['parameters']['group_index']=2;invalid['parameters']['mode']='regression_groups'
        # Each group has enough data initially. Destroy the source response only
        # for one group, so the first ungrouped graph succeeds and the second fails.
        sheet=p.result_worksheet(source);sheet.columns[1].values=[3,5,6,None,11,None]
        with self.assertRaises(ValueError):run_similar_graphs(p,source,[valid,invalid])
        self.assertEqual(p.history,before_history);self.assertEqual(p._results_dirty,before_dirty)
        self.assertIs(p.worksheet,before_sheet);self.assertEqual(p.native_project.active_index,before_index)

    def test_bad_histogram_fit_is_atomic(self):
        p=document();source=run(p,dict(action='graph',parameters=dict(method='histogram',indices=[1],bins=9)))
        source['histogram_settings']=dict(bins=10,scale='Frequency',cumulative=False,fit='Normal')
        p.worksheet.columns[3].values=[1,1,1,1,1,1]
        recipe=copy.deepcopy(source['recipe']);recipe['parameters']['indices']=[3]
        history=list(p.history)
        with self.assertRaises(ValueError):run_similar_graphs(p,source,[recipe])
        self.assertEqual(p.history,history)

    def test_main_grid_originals_readonly_roles_replacements_and_transfer(self):
        p=document();source=p.scatter_plot(0,1,'groups',2)
        dialog=create_similar_dialog(None,p.worksheet,source)
        try:
            from PySide6.QtCore import Qt
            self.assertEqual([dialog.roles.horizontalHeaderItem(i).text() for i in range(3)],
                ['Role','Original Variable','New Variable'])
            self.assertEqual(dialog.roles.rowCount(),3)
            self.assertIn('Strength (N)',dialog.roles.item(0,1).text())
            for row in range(3):
                self.assertEqual(dialog.roles.item(row,1).text(),dialog.roles.item(row,2).text())
                self.assertFalse(dialog.roles.item(row,0).flags() & Qt.ItemFlag.ItemIsEditable)
                self.assertFalse(dialog.roles.item(row,1).flags() & Qt.ItemFlag.ItemIsEditable)
            dialog.roles.setCurrentCell(0,2)
            self.assertFalse(any('-T' in dialog.available.item(i).text() for i in range(dialog.available.count())))
            for i in range(dialog.available.count()):
                if dialog.available.item(i).data(Qt.ItemDataRole.UserRole)==3:dialog.available.setCurrentRow(i)
            dialog.transfer();dialog.validate()
            self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
            created=run_similar_graphs(p,source,dialog.recipes(),appearance=dialog.appearance_settings())[0]
            self.assertEqual(created['recipe']['parameters']['y_index'],3)
            self.assertEqual(source['recipe']['parameters']['y_index'],1)
            dialog.roles.setCurrentCell(2,2)
            self.assertTrue(any('-T' in dialog.available.item(i).text() for i in range(dialog.available.count())))
        finally:dialog.close()

    def test_main_options_accept_changes_and_cancel_discards_changes(self):
        from PySide6.QtCore import QTimer
        p=document();source=run(p,dict(action='graph',parameters=dict(method='histogram',indices=[1],bins=9)))
        dialog=create_similar_dialog(None,p.worksheet,source)
        try:
            def accept_options():
                active=self.app.activeModalWidget()
                active.controls['bins'].setText('333');active.validate()
            QTimer.singleShot(0,accept_options);dialog.edit_options()
            self.assertEqual(dialog.recipes()[0]['parameters']['bins'],200)
            self.assertEqual(dialog.appearance_settings()['histogram_settings']['bins'],333)
            def cancel_options():
                active=self.app.activeModalWidget()
                active.controls['bins'].setText('500');active.reject()
            QTimer.singleShot(0,cancel_options);dialog.edit_options()
            self.assertEqual(dialog.appearance_settings()['histogram_settings']['bins'],333)
        finally:dialog.close()

    def test_main_replacement_type_validation_and_cancel_are_nonmutating(self):
        p=document();source=p.scatter_plot(0,1);before=copy.deepcopy(p.history)
        dialog=create_similar_dialog(None,p.worksheet,source)
        try:
            from PySide6.QtWidgets import QTableWidgetItem
            dialog.roles.setItem(0,2,QTableWidgetItem('C3'))
            dialog.validate();self.assertNotEqual(dialog.result(),QDialog.DialogCode.Accepted)
            self.assertIn('eligible',dialog.error.text())
            dialog.reject();self.assertEqual(p.history,before)
        finally:dialog.close()

    def test_unsupported_native_and_wrong_procedures_are_explicit(self):
        p=document();source=p.describe_column(0)
        self.assertFalse(supports_similar(source))
        with self.assertRaises(ValueError):create_similar_dialog(None,p.worksheet,source)
        source=p.scatter_plot(0,1);recipe={'action':'graph','parameters':{'method':'histogram','indices':[0],'bins':10}}
        with self.assertRaises(ValueError):run_similar_graphs(p,source,[recipe])
        source['origin']='native';self.assertFalse(supports_similar(source))
        source['origin']='statcraft';source['source_unavailable']='A source column was deleted.'
        self.assertFalse(supports_similar(source))
        with self.assertRaisesRegex(ValueError,'source column was deleted'):create_similar_dialog(None,p.worksheet,source)


if __name__=='__main__':unittest.main()


