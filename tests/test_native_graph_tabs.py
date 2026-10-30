import unittest
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow
from statcraft.app import Presenter
from statcraft.verification_fonts import load_verification_fonts
from statcraft.native_output_chart import NativeOutputChart


class NativeGraphTabsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        load_verification_fonts(cls.app)
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.p = Presenter()
        self.p.load('C:/Users/funny/Downloads/MFGEN 401 HW 07 - Minitab Solution KEY - Water Absorption in Paper.mpx')
        self.w = ModernWindow(self.p)
        self.w.resize(1000, 700)
        self.w.show()
        self.app.processEvents()

    def tearDown(self):
        self.p.dirty = False
        self.w.close()
        self.w.deleteLater()
        self.app.processEvents()

    def test_multi_graph_dedicated_tabs_and_navigator_children(self):
        reg_entry = next(e for e in self.p.history if 'Factorial Regression' in e.get('title', ''))
        self.w.show_result(reg_entry)
        self.app.processEvents()

        # Check tabs created
        tab_names = [self.w.result_tabs.tabText(i) for i in range(self.w.result_tabs.count())]
        self.assertIn('Report', tab_names)
        self.assertIn('Effects Pareto', tab_names)
        self.assertIn('Normplot of Residuals', tab_names)
        self.assertIn('Residuals vs Fits', tab_names)
        self.assertIn('Residuals vs Order', tab_names)
        self.assertIn('Text export', tab_names)

        # Factorial Regression has text report, so default tab is Report
        self.assertEqual(self.w.result_tabs.tabText(self.w.result_tabs.currentIndex()), 'Report')

        # Check Navigator child items
        nav = self.w.navigator
        cmd_node = None
        for i in range(nav.topLevelItemCount()):
            top = nav.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if 'Factorial Regression' in child.text(0):
                    cmd_node = child
                    break
        self.assertIsNotNone(cmd_node)
        sub_titles = [cmd_node.child(k).text(0) for k in range(cmd_node.childCount())]
        self.assertIn('Report', sub_titles)
        self.assertTrue(any('Effects Pareto' in t for t in sub_titles))
        self.assertTrue(any('Normplot of Residuals' in t for t in sub_titles))

        # Test clicking child graph in Navigator switches to that tab
        pareto_child = next(cmd_node.child(k) for k in range(cmd_node.childCount()) if 'Effects Pareto' in cmd_node.child(k).text(0))
        self.w._navigate(pareto_child, 0)
        self.app.processEvents()
        self.assertEqual(self.w.result_tabs.tabText(self.w.result_tabs.currentIndex()), 'Effects Pareto')

    def test_entry_without_report_defaults_to_first_graph_tab(self):
        plots_entry = next(e for e in self.p.history if 'Factorial Plots' in e.get('title', ''))
        self.w.show_result(plots_entry)
        self.app.processEvents()

        tab_names = [self.w.result_tabs.tabText(i) for i in range(self.w.result_tabs.count())]
        self.assertIn('Main Effects Plot', tab_names)
        self.assertIn('Interaction Plot', tab_names)

        # Factorial Plots has no report text, so it defaults to the first graph tab
        self.assertEqual(self.w.result_tabs.tabText(self.w.result_tabs.currentIndex()), 'Main Effects Plot')

    def test_native_output_chart_optional_graph_index(self):
        reg_entry = next(e for e in self.p.history if 'Factorial Regression' in e.get('title', ''))
        chart0 = NativeOutputChart(reg_entry, graph_index=0)
        self.assertEqual(chart0.graph_index, 0)
        chart2 = NativeOutputChart(reg_entry, graph_index=2)
        self.assertEqual(chart2.graph_index, 2)


if __name__ == '__main__':
    unittest.main()
