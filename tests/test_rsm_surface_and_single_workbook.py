import os
import unittest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow
from statcraft.app import Presenter
from statcraft.verification_fonts import load_verification_fonts
from statcraft.native_output_chart import NativeOutputChart


class RSMSurfaceAndSingleWorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_verification_fonts(cls.app)
        cls.app.setQuitOnLastWindowClosed(False)

    def test_rsm_mpx_surface_and_contour_and_single_workbook(self):
        mpx_path = Path('C:/Users/funny/Downloads/MFGEN 401 Lecture 22 - Example Response Surface Design PP pyrolysis yield.mpx')
        if not mpx_path.exists():
            self.skipTest('MFGEN 401 MPX not present in Downloads')

        w = ModernWindow()
        w.load_path(str(mpx_path))
        w.resize(1000, 700)
        w.show()
        self.app.processEvents()

        try:
            # 1. Verify single workbook output tab behavior on load (no table tab explosion)
            tab_names = [w.result_tabs.tabText(i) for i in range(w.result_tabs.count())]
            self.assertIn('Report', tab_names)
            self.assertNotIn('Coded Coefficients', tab_names)
            self.assertNotIn('Model Summary', tab_names)
            self.assertNotIn('Analysis of Variance', tab_names)

            # 2. Verify Contour Plot entry has valid panel and renders
            contour_entry = next(e for e in w.presenter.history if 'Contour Plot' in e.get('title', ''))
            graphs = contour_entry['result'].get('graphs', [])
            self.assertEqual(len(graphs), 1)
            self.assertEqual(graphs[0]['panels'][0]['kind'], 'contour')
            w.show_result(contour_entry)
            self.app.processEvents()
            self.assertTrue(any('Contour Plot' in w.result_tabs.tabText(i) for i in range(w.result_tabs.count())))

            # 3. Verify Surface Plot entry has valid panel and renders
            surf_entry = next(e for e in w.presenter.history if 'Surface Plot' in e.get('title', ''))
            graphs = surf_entry['result'].get('graphs', [])
            self.assertEqual(len(graphs), 1)
            self.assertEqual(graphs[0]['panels'][0]['kind'], 'surface')
            w.show_result(surf_entry)
            self.app.processEvents()
            self.assertTrue(any('Surface Plot' in w.result_tabs.tabText(i) for i in range(w.result_tabs.count())))

            chart = NativeOutputChart(surf_entry, graph_index=0)
            self.assertEqual(len(chart.panels), 1)
            self.assertEqual(chart.panels[0]['kind'], 'surface')
        finally:
            w.presenter.dirty = False
            w.close()
            w.deleteLater()
            self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
