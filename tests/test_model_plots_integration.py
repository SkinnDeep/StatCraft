import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication
from statcraft.model import Column, Worksheet
from statcraft.model_plot_dialogs import (
    ContourLevelsDialog,
    FactorialPlotsDialog,
    FactorialPlotsGraphsDialog,
    FactorialPlotsOptionsDialog,
    HoldSettingsDialog,
    ModelContourPlotDialog,
    ModelSurfacePlotDialog,
    SurfaceOptionsDialog,
)
from statcraft.model_plots import contour_plot_settings
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget, supported
from statcraft.office_export import export_docx, export_pptx
from statcraft.prediction_dialogs import PredictDialog


class TestModelPlotsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _populate_window(self):
        win = ModernWindow()
        win.presenter.worksheet = Worksheet(
            'CatalystRSM',
            [
                Column('Temp', 'number', [150, 150, 150, 150, 200, 200, 200, 200, 175, 175, 160, 190]),
                Column('Pressure', 'number', [10, 10, 20, 20, 10, 10, 20, 20, 15, 15, 15, 18]),
                Column('Time', 'number', [30, 60, 30, 60, 30, 60, 30, 60, 45, 55, 40, 50]),
                Column('Catalyst', 'text', ['A', 'B', 'B', 'A', 'B', 'A', 'A', 'B', 'A', 'B', 'A', 'B']),
                Column('Yield', 'number', [62.0, 68.5, 71.0, 79.0, 74.5, 82.0, 86.0, 94.5, 78.0, 80.5, 70.0, 88.0]),
            ],
        )
        win.refresh()
        return win

    def _close_window(self, win):
        win.presenter.dirty = False
        win.presenter._results_dirty = False
        win.close()

    def test_menu_enablement_by_model_and_continuous_count(self):
        win = self._populate_window()
        try:
            for act in win.factorial_plot_actions.values():
                self.assertFalse(act.isEnabled())
            for act in win.contour_plot_actions.values():
                self.assertFalse(act.isEnabled())
            for act in win.surface_plot_actions.values():
                self.assertFalse(act.isEnabled())

            # Fit GLM with 1 factor + 1 covariate (< 2 continuous predictors)
            win.presenter.general_linear_model(4, [3], [0], terms=[[0], [1]])
            win.refresh()
            self.assertTrue(win.factorial_plot_actions['general_linear_model'].isEnabled())
            self.assertFalse(win.contour_plot_actions['general_linear_model'].isEnabled())
            self.assertFalse(win.surface_plot_actions['general_linear_model'].isEnabled())

            # Fit GLM with 1 factor + 2 covariates (>= 2 continuous predictors)
            win.presenter.general_linear_model(4, [3], [0, 1], terms=[[0], [1], [2]])
            win.refresh()
            self.assertTrue(win.contour_plot_actions['general_linear_model'].isEnabled())
            self.assertTrue(win.surface_plot_actions['general_linear_model'].isEnabled())
        finally:
            self._close_window(win)

    def test_dialogs_and_chart_rendering(self):
        win = self._populate_window()
        try:
            win.presenter.analyze_response_surface(
                4,
                [0, 1, 2],
                [{'low': 150.0, 'high': 200.0}, {'low': 10.0, 'high': 20.0}, {'low': 30.0, 'high': 60.0}],
                terms=[[0], [1], [2], [0, 1], [0, 0], [1, 1]],
            )
            win.refresh()

            # 1. FactorialPlotsDialog
            fp_dlg = FactorialPlotsDialog(win, family='response_surface')
            self.assertEqual(fp_dlg.selected.count(), 3)
            g_sub = FactorialPlotsGraphsDialog(fp_dlg, fp_dlg.options)
            g_sub.matrix_mode.setCurrentIndex(g_sub.matrix_mode.findData('full'))
            g_sub.validate()
            fp_dlg.options = g_sub.options
            o_sub = FactorialPlotsOptionsDialog(fp_dlg, win.presenter.worksheet, fp_dlg.bundle, fp_dlg.options)
            o_sub.title_edit.setText('Custom Factorial Plots')
            o_sub.validate()
            fp_dlg.options = o_sub.options
            fp_dlg.validate()
            self.assertIsNotNone(fp_dlg.entry)
            self.assertTrue(supported(fp_dlg.entry))
            chart_fp = ChartWidget(fp_dlg.entry)
            self.assertIsNone(chart_fp.error)
            self.assertEqual(len(chart_fp.panels), 2)

            # Restore previous in FactorialPlotsDialog
            fp_dlg2 = FactorialPlotsDialog(win, family='response_surface')
            self.assertEqual(fp_dlg2.options['title'], 'Custom Factorial Plots')
            self.assertEqual(fp_dlg2.options['matrix_display'], 'full')
            fp_dlg2.reject()

            # 2. ModelContourPlotDialog
            cp_dlg = ModelContourPlotDialog(win, family='response_surface')
            c_sub = ContourLevelsDialog(cp_dlg, cp_dlg.options)
            c_sub.design_points.setChecked(True)
            c_sub.level_mode.setCurrentIndex(c_sub.level_mode.findData('number'))
            c_sub.level_count.setText('6')
            c_sub.validate()
            cp_dlg.options = c_sub.options
            h_sub = HoldSettingsDialog(
                cp_dlg,
                'Contour Plot: Settings',
                win.presenter.worksheet,
                cp_dlg.bundle,
                cp_dlg.options,
                contour_plot_settings,
            )
            h_sub.table.item(2, 2).setText('48')
            h_sub.validate()
            cp_dlg.options = h_sub.options
            cp_dlg.validate()
            self.assertIsNotNone(cp_dlg.entry)
            self.assertTrue(supported(cp_dlg.entry))
            chart_cp = ChartWidget(cp_dlg.entry)
            self.assertIsNone(chart_cp.error)
            self.assertEqual(len(chart_cp.panels), 1)

            # 3. ModelSurfacePlotDialog
            sp_dlg = ModelSurfacePlotDialog(win, family='response_surface')
            s_sub = SurfaceOptionsDialog(sp_dlg, sp_dlg.options)
            s_sub.style_combo.setCurrentIndex(s_sub.style_combo.findData('shaded'))
            s_sub.title_edit.setText('3D Response Surface')
            s_sub.validate()
            sp_dlg.options = s_sub.options
            sp_dlg.validate()
            self.assertIsNotNone(sp_dlg.entry)
            self.assertTrue(supported(sp_dlg.entry))
            chart_sp = ChartWidget(sp_dlg.entry)
            self.assertIsNone(chart_sp.error)
            self.assertEqual(len(chart_sp.panels), 1)
        finally:
            self._close_window(win)

    def test_factorial_predict_dialog_and_mpx_roundtrip_and_office_export(self):
        win = ModernWindow()
        try:
            win.presenter.create_factorial(
                [{'name': 'Temp', 'low': 150.0, 'high': 200.0}, {'name': 'Pressure', 'low': 10.0, 'high': 20.0}],
                replicates=2,
                randomize=False,
            )
            win.presenter.worksheet.columns.append(
                Column('Yield', 'number', [60.0, 72.0, 68.0, 84.0, 61.0, 71.0, 67.0, 85.0])
            )
            win.presenter.analyze_factorial(6, [4, 5], max_order=2)
            win.refresh()
            self.assertTrue(win.predict_actions['analyze_factorial'].isEnabled())
            self.assertTrue(win.factorial_plot_actions['analyze_factorial'].isEnabled())
            self.assertTrue(win.contour_plot_actions['analyze_factorial'].isEnabled())
            self.assertTrue(win.surface_plot_actions['analyze_factorial'].isEnabled())

            p_dlg = PredictDialog(win, family='factorial')
            from PySide6.QtWidgets import QTableWidgetItem
            p_dlg.values_grid.setItem(0, 0, QTableWidgetItem('175'))
            p_dlg.values_grid.setItem(0, 1, QTableWidgetItem('15'))
            p_dlg.validate()
            self.assertIsNotNone(p_dlg.entry)
            self.assertAlmostEqual(p_dlg.entry['result']['rows'][0]['fit'], 71.0, places=4)

            fp_entry = win.presenter.factorial_plots(win.presenter.history[1]['recipe'])
            cp_entry = win.presenter.model_contour_plot(win.presenter.history[1]['recipe'])
            sp_entry = win.presenter.model_surface_plot(win.presenter.history[1]['recipe'])
            win.show_result(cp_entry)

            with tempfile.TemporaryDirectory() as tmp:
                mpx_path = Path(tmp) / 'model_plots_roundtrip.mpx'
                docx_path = Path(tmp) / 'model_plots.docx'
                pptx_path = Path(tmp) / 'model_plots.pptx'

                win.save_path(str(mpx_path))
                self.assertTrue(mpx_path.exists())

                snap = win._office_snapshot(cp_entry)
                self.assertIsNotNone(snap)
                self.assertTrue(len(snap.png) > 500)
                export_docx(str(docx_path), snap)
                export_pptx(str(pptx_path), snap)
                self.assertTrue(docx_path.exists())
                self.assertTrue(pptx_path.exists())

                win2 = ModernWindow()
                try:
                    win2.load_path(str(mpx_path))
                    actions = [e.get('recipe', {}).get('action') for e in win2.presenter.history]
                    self.assertIn('factorial_plots', actions)
                    self.assertIn('model_contour_plot', actions)
                    self.assertIn('model_surface_plot', actions)
                    self.assertIn('predict_model', actions)

                    # Mutate worksheet cell -> verify stale -> rerun
                    loaded_sp = [e for e in win2.presenter.history if e.get('recipe', {}).get('action') == 'model_surface_plot'][-1]
                    self.assertFalse(win2.presenter.result_stale(loaded_sp))
                    win2.presenter.set_cell(0, 6, '62.0')
                    self.assertTrue(win2.presenter.result_stale(loaded_sp))
                    win2.show_result(loaded_sp)
                    rerun_sp = win2.rerun_selected()
                    self.assertFalse(win2.presenter.result_stale(rerun_sp))
                finally:
                    self._close_window(win2)
        finally:
            self._close_window(win)


if __name__ == '__main__':
    unittest.main()
