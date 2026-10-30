"""Real planner configuration, fresh preview, goal selection and export workflows."""
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QTableWidgetItem,QDialog
from statcraft.doe_planner_dialog import DOEPlannerDialog,FAMILIES
from statcraft.doe_catalog_designs import PB_RUNS,TAGUCHI_ARRAYS


class DOEPlannerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def setUp(self):self.dialogs=[]

    def tearDown(self):
        for dialog in self.dialogs:dialog.preview_timer.stop();dialog.close()
        self.app.processEvents()

    def dialog(self,kind='full_factorial',export_callback=None):
        dialog=DOEPlannerDialog(export_callback=export_callback);self.dialogs.append(dialog)
        dialog.family.setCurrentIndex(dialog.family.findData(kind));dialog.show();self.app.processEvents();return dialog

    def test_all_families_exposed_and_actual_catalog_options(self):
        dialog=self.dialog()
        self.assertEqual({dialog.family.itemData(i) for i in range(dialog.family.count())},{item[0] for item in FAMILIES})
        self.assertEqual([dialog.pb_runs.itemData(i) for i in range(1,dialog.pb_runs.count())],list(PB_RUNS))
        self.assertEqual({dialog.array.itemData(i) for i in range(1,dialog.array.count())},set(TAGUCHI_ARRAYS))

    def test_goal_selects_family_and_only_relevant_controls_visible(self):
        dialog=self.dialog();dialog.goal.setCurrentIndex(dialog.goal.findData('optimize'));self.app.processEvents()
        self.assertEqual(dialog.family.currentData(),'central_composite');self.assertGreaterEqual(dialog.centers.value(),1)
        self.assertIn('per replicate',dialog.centers_label.text())
        self.assertTrue(dialog.alpha.isVisible());self.assertFalse(dialog.array.isVisible())
        dialog.goal.setCurrentIndex(dialog.goal.findData('mixture'));self.app.processEvents()
        self.assertEqual(dialog.family.currentData(),'simplex_centroid')
        self.assertTrue(dialog.factor_table.isColumnHidden(2));self.assertFalse(dialog.factor_table.isColumnHidden(3))
        dialog.family.setCurrentIndex(dialog.family.findData('plackett_burman'));self.assertFalse(dialog.blocks.isEnabled())

    def test_numeric_and_text_levels_and_generator_parameters(self):
        dialog=self.dialog('general_factorial');dialog.factor_table.cellWidget(0,1).setCurrentIndex(1)
        dialog.factor_table.setItem(0,2,QTableWidgetItem('Cold, Room temperature, Hot'))
        values=dialog.values();self.assertEqual(values['factors'][0]['levels'],['Cold','Room temperature','Hot'])
        dialog.family.setCurrentIndex(dialog.family.findData('fractional_factorial'))
        dialog.factor_table.setItem(0,2,QTableWidgetItem('-1, 1'));dialog.generators.setText('C=AB')
        self.assertEqual(dialog.values()['options']['generators'],{'C':'AB'})
        self.assertEqual(dialog.values()['factors'][0],{'name':'A','low':-1,'high':1})

    def test_custom_excluded_combinations_are_typed_and_blank_wildcards(self):
        dialog=self.dialog('custom_optimal');QTest.mouseClick(dialog.add_forbidden,Qt.MouseButton.LeftButton)
        dialog.forbidden_table.setItem(0,0,QTableWidgetItem('-1'));dialog.forbidden_table.setItem(0,1,QTableWidgetItem('-1'))
        self.assertEqual(dialog.values()['options']['forbidden'],[{'A':-1,'B':-1}])
        self.assertEqual(dialog.values()['options']['model'],'main_effects')
        self.assertEqual(dialog.values()['centers'],0)

    def test_live_preview_and_create_uses_fresh_current_parameters(self):
        dialog=self.dialog();QTest.qWait(400)
        self.assertIsNotNone(dialog.preview_sheet)
        self.assertEqual(dialog.preview_sheet.row_count,8)
        first=dialog.preview_sheet
        dialog.replicates.setValue(2)
        self.assertIsNone(dialog.preview_sheet)
        QTest.mouseClick(dialog.create_button,Qt.MouseButton.LeftButton)
        # The button is disabled while a delayed preview is pending; Enter/Create
        # after the preview runs must use the updated run plan.
        QTest.qWait(400);QTest.mouseClick(dialog.create_button,Qt.MouseButton.LeftButton)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.parameters['replicates'],2)
        self.assertEqual(dialog.preview_sheet.row_count,16)
        self.assertEqual(first.row_count,8)

    def test_all_eleven_families_build_actual_previews(self):
        expected={'full_factorial':8,'fractional_factorial':4,'general_factorial':8,'plackett_burman':4,
                  'central_composite':15,'box_behnken':13,'taguchi':4,'simplex_centroid':7,
                  'simplex_lattice':6,'extreme_vertices':3,'custom_optimal':8}
        for kind,count in expected.items():
            with self.subTest(kind=kind):
                dialog=self.dialog(kind)
                self.assertTrue(dialog.refresh_preview(),dialog.error.text())
                self.assertEqual(dialog.preview_sheet.row_count,count)
                self.assertEqual(dialog.preview_table.rowCount(),count)
                dialog.close()

    def test_invalid_factor_input_clears_preview_and_blocks_create(self):
        dialog=self.dialog();self.assertTrue(dialog.refresh_preview())
        dialog.factor_table.setItem(1,0,QTableWidgetItem('A'))
        self.assertFalse(dialog.refresh_preview());self.assertIsNone(dialog.parameters);self.assertIsNone(dialog.preview_sheet)
        self.assertFalse(dialog.create_button.isEnabled());self.assertIn('distinct',dialog.error.text())
        dialog.factor_table.setItem(1,0,QTableWidgetItem('B'));dialog.factor_table.setItem(0,2,QTableWidgetItem('nan, 1'))
        self.assertFalse(dialog.refresh_preview());self.assertIn('finite',dialog.error.text())

    def test_export_uses_current_preview_and_callback_without_accepting(self):
        captured=[];dialog=self.dialog(export_callback=lambda path,sheets:captured.append((path,sheets)))
        dialog.replicates.setValue(2)
        with patch('statcraft.doe_planner_dialog.QFileDialog.getSaveFileName',return_value=('design.xlsx','Excel Workbook (*.xlsx)')):
            dialog.export_excel()
        self.assertEqual(len(captured),1);self.assertEqual(captured[0][0],'design.xlsx');self.assertEqual(captured[0][1][0].row_count,16)
        self.assertNotEqual(dialog.result(),QDialog.DialogCode.Accepted)

    def test_one_factor_quadratic_custom_design(self):
        dialog=self.dialog('custom_optimal');dialog.factor_count.setValue(1)
        dialog.factor_table.setItem(0,2,QTableWidgetItem('-1, 0, 1'))
        dialog.model.setCurrentIndex(dialog.model.findData('quadratic'));dialog.optimal_runs.setValue(3)
        self.assertTrue(dialog.refresh_preview(),dialog.error.text())
        self.assertEqual(dialog.preview_sheet.row_count,3)
        dialog.family.setCurrentIndex(dialog.family.findData('full_factorial'))
        self.assertEqual(dialog.factor_count.value(),2)
        self.assertEqual(dialog.factor_count.minimum(),2)

    def test_custom_run_budget_above_sixteen_has_exact_preview_and_parameters(self):
        dialog=self.dialog('custom_optimal')
        for row in range(3):dialog.factor_table.setItem(row,2,QTableWidgetItem('-1, 0, 1'))
        for runs in (17,19,24):
            with self.subTest(runs=runs):
                dialog.optimal_runs.setValue(runs)
                self.assertTrue(dialog.refresh_preview(),dialog.error.text())
                self.assertEqual(dialog.preview_sheet.row_count,runs)
                self.assertEqual(dialog.preview_table.rowCount(),runs)
                self.assertEqual(dialog.parameters['options']['runs'],runs)
                self.assertTrue(dialog.create_button.isEnabled())
        self.assertIn('no 16-run limit',dialog.guidance.text())

    def test_full_factorial_above_sixteen_and_custom_budget_guidance(self):
        dialog=self.dialog('full_factorial');dialog.factor_count.setValue(5)
        self.assertTrue(dialog.refresh_preview(),dialog.error.text())
        self.assertEqual(dialog.preview_sheet.row_count,32)
        self.assertIn('Custom optimal',dialog.guidance.text())

    def test_cancel_does_not_accept_or_mutate_a_project(self):
        dialog=self.dialog();self.assertTrue(dialog.refresh_preview());QTest.mouseClick(dialog.cancel_button,Qt.MouseButton.LeftButton)
        self.assertEqual(dialog.result(),QDialog.DialogCode.Rejected)
        self.assertFalse(hasattr(dialog,'presenter'))
        self.assertFalse(dialog.preview_timer.isActive())


if __name__=='__main__':unittest.main()
