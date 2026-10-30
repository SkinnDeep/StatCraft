"""Integration coverage for the actual new analysis results and output routing."""
import unittest

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet, Column
from statcraft.modern_charts import supported


def make_presenter():
    p = Presenter()
    parts = ['P1']*3 + ['P2']*3 + ['P3']*3 + ['P4']*3
    operators = ['A']*6 + ['B']*6
    reference = [10.0]*3 + [12.0]*3 + [14.0]*3 + [16.0]*3
    values = [10.1,10.2,10.05,12.2,12.3,12.1,14.3,14.4,14.2,16.3,16.5,16.4]
    truth = ['Pass']*3 + ['Fail']*3 + ['Pass']*3 + ['Fail']*3
    p.worksheet = Worksheet('Advanced Quality',[
        Column('Parts','text',parts), Column('Operator','text',operators),
        Column('Measured',values=values), Column('Reference',values=reference),
        Column('Rating','text',truth), Column('Standard','text',truth),
        Column('Lifetime',values=[12,18,21,25,29,33,41,46,52,64,75,91]),
        Column('Samples','text',['S1']*3+['S2']*3+['S1']*3+['S2']*3)])
    return p


def make_entries(p):
    return [
        (p.nested_gage_rr(part_col='Parts', operator_col='Operator', measurement_col='Measured'), 'NestedGageRRChartWidget'),
        (p.gage_linearity(reference_col='Reference', measurement_col='Measured', process_variation=12), 'GageLinearityChartWidget'),
        (p.attribute_agreement(attribute_col='Rating', sample_col='Samples', appraiser_col='Operator', standard_col='Standard'), 'AttributeAgreementChartWidget'),
        (p.reliability_distribution(settings={'column_index':6,'dist_name':'exponential'}), 'ReliabilityPlotWidget'),
        (p.capability_nonparametric(settings={'column_index':2,'lsl':8,'usl':19}), 'NonparametricCapabilityPlotWidget'),
        (p.capability_automated(settings={'column_index':2,'lsl':8,'usl':19}), 'NonparametricCapabilityPlotWidget'),
        (p.capability_nonnormal(settings={'column_index':2,'lsl':8,'usl':19,'dist_or_transform':'lognormal'}), 'NonnormalCapabilityPlotWidget'),
    ]


class Preview77RealOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def test_actual_presenter_outputs_have_supported_dedicated_graphs(self):
        p=make_presenter()
        entries=make_entries(p)
        from statcraft.modern_app import ModernWindow
        w=ModernWindow(p)
        w.resize(1280,900)
        w.show()
        try:
            for entry, expected in entries:
                with self.subTest(analysis=entry['result']['analysis']):
                    self.assertTrue(supported(entry))
                    w.show_result(entry)
                    self.app.processEvents()
                    chart=w._active_chart_widget
                    self.assertIsNotNone(chart)
                    self.assertEqual(type(chart).__name__,expected)
                    self.assertEqual(w.result_tabs.tabText(w.result_tabs.currentIndex()),'Graph')
                    w.graph_options_pane.load_entry(entry)
                    self.assertFalse(w.graph_options_pane.object_button.isEnabled())
                    self.assertFalse(w.graph_options_pane.controls['x_min'].isEnabled())
                    self.assertFalse(w.graph_options_pane.controls['x_label'].isEnabled())
                    self.assertTrue(w.graph_options_pane.controls['title'].isEnabled())
                    image=chart.grab().toImage()
                    self.assertFalse(image.isNull())
                    self.assertGreater(image.width(),100)
                    self.assertGreater(image.height(),100)
        finally:
            w.close()
            w.deleteLater()
            self.app.processEvents()

    def test_explicit_graphs_disabled_does_not_create_chart_tab(self):
        from statcraft.modern_app import ModernWindow
        p=make_presenter()
        entries=make_entries(p)
        w=ModernWindow(p)
        try:
            for entry, _ in entries:
                with self.subTest(analysis=entry['result']['analysis']):
                    entry['result']['show_graphs']=False
                    self.assertFalse(supported(entry))
                    w.show_result(entry)
                    self.assertIsNone(w._active_chart_widget)
                    self.assertNotIn('Graph',[w.result_tabs.tabText(i) for i in range(w.result_tabs.count())])
        finally:
            w.close()
            w.deleteLater()
            self.app.processEvents()

    def test_nested_options_graph_suppression(self):
        for entry, _ in make_entries(make_presenter()):
            entry['result']['options']={'show_graphs':False}
            self.assertFalse(supported(entry))


if __name__=='__main__':
    unittest.main()

