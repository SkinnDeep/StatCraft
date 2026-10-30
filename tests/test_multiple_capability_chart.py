"""Correct raw-space Box-Cox density and composed capability capture tests."""
import copy
import math
from pathlib import Path
from unittest import TestCase
from zipfile import ZipFile
import numpy as np
from scipy import stats
from scipy.integrate import quad
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication
from test_mpx import scratch
from statcraft.capability_nonnormal_chart import fitted_density, NonnormalCapabilityPlotWidget
from statcraft.capability_chart import CapabilityPlotWidget
from statcraft.multiple_capability_chart import MultipleCapabilityChartWidget
from statcraft.capability_engine import run_normal_capability
from statcraft.capability_nonnormal_engine import run_nonnormal_capability
from statcraft.graph_frame import GraphFrame
from statcraft.office_export import OfficeSnapshot, export_docx, export_pptx, png_size


def fit(lam, mu=.1, sigma=.7):
    return {'method': 'box_cox', 'fit_info': {'lambda': lam, 'mean_trans': mu, 'std_trans': sigma}}


def transform(x, lam):
    return math.log(x) if abs(lam) < 1e-6 else math.expm1(lam * math.log(x)) / lam


def entry(method='normal', columns=2, count=3):
    series = []
    for i in range(count):
        values = [10 + .8 * math.sin(j) + .03 * j + i for j in range(30)]
        if method == 'normal':
            result = run_normal_capability(values, subgroup_spec=3, lsl=7., usl=16., variable_name='Measure ' + str(i + 1))
        else:
            result = run_nonnormal_capability(values, dist_or_transform='box_cox', box_cox_lambda=0., lsl=7., usl=16.)
        series.append({'label': 'Measure ' + str(i + 1), 'variable_name': 'Measure ' + str(i + 1), 'result': result})
    return {'title': 'Multiple capability', 'result': {'analysis': 'multiple_capability', 'method': method,
            'series': series, 'options': {'columns': columns}, 'summary': []}}


class BoxCoxDensityTests(TestCase):
    def test_log_case_is_fitted_lognormal_density(self):
        xs = np.array([.1, .5, 1., 2., 10.])
        np.testing.assert_allclose(fitted_density(fit(0), xs), stats.lognorm.pdf(xs, .7, scale=math.exp(.1)), rtol=1e-12)

    def test_pdf_matches_derivative_of_engine_transformed_cdf(self):
        for lam in (-1., -.5, 0., .5, 1., 2.):
            for x in (.2, 1., 3., 8.):
                with self.subTest(lam=lam, x=x):
                    h = x * 1e-5
                    derivative = (stats.norm.cdf(transform(x + h, lam), loc=.1, scale=.7) - stats.norm.cdf(transform(x - h, lam), loc=.1, scale=.7)) / (2 * h)
                    self.assertAlmostEqual(float(fitted_density(fit(lam), [x])[0]), derivative, delta=1e-8)

    def test_quadrature_matches_transformed_cdf_probability_mass(self):
        for lam in (-1., -.5, 0., .5, 1.):
            with self.subTest(lam=lam):
                actual = quad(lambda x: float(fitted_density(fit(lam), [x])[0]), 0., np.inf, epsabs=1e-9)[0]
                if lam > 0:
                    expected = stats.norm.sf(-1 / lam, loc=.1, scale=.7)
                elif lam < 0:
                    expected = stats.norm.cdf(-1 / lam, loc=.1, scale=.7)
                else:
                    expected = 1.
                self.assertAlmostEqual(actual, expected, places=8)

    def test_nonpositive_support_is_zero(self):
        np.testing.assert_array_equal(fitted_density(fit(.5), [-10., -1., 0.]), [0., 0., 0.])

    def test_bad_saved_fit_does_not_fall_back_to_raw_normal(self):
        for result in ({'method': 'box_cox'}, fit(0, sigma=0), {'method': 'unknown'}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                fitted_density(result, [1., 2., 3.])

    def test_actual_engine_parameters_are_used(self):
        values = [1., 1.5, 2., 3., 6., 12.]
        result = run_nonnormal_capability(values, dist_or_transform='box_cox', box_cox_lambda=0., lsl=.5, usl=20.)
        xs = np.array([1., 2., 3., 6.])
        expected = stats.norm.pdf(np.log(xs), loc=np.mean(np.log(values)), scale=np.std(np.log(values), ddof=1)) / xs
        np.testing.assert_allclose(fitted_density(result, xs), expected, rtol=1e-12)
        self.assertGreater(np.max(np.abs(expected - stats.norm.pdf(xs, loc=np.mean(values), scale=np.std(values, ddof=1)))), .01)


class MultipleCapabilityChartTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def frame(self, data):
        chart = MultipleCapabilityChartWidget(data)
        frame = GraphFrame(chart, data)
        frame.resize(frame.minimumWidth(), frame.minimumHeight() + 30)
        frame.show()
        self.app.processEvents()
        self.addCleanup(frame.close)
        return chart, frame

    def test_normal_panels_are_actual_child_reports_in_grid(self):
        data = entry()
        before = copy.deepcopy(data)
        chart, frame = self.frame(data)
        self.assertEqual((chart.layout_rows, chart.layout_columns), (2, 2))
        self.assertEqual(len(chart.child_charts), 3)
        self.assertTrue(all(isinstance(child, CapabilityPlotWidget) for child in chart.child_charts))
        self.assertGreaterEqual(chart.child_charts[1].x(), chart.child_charts[0].width())
        self.assertGreater(chart.child_charts[2].y(), chart.child_charts[0].y())
        self.assertEqual(data, before)
        self.assertGreater(frame.capture().width(), 1500)

    def test_nonnormal_children_use_their_own_fitted_results(self):
        data = entry('nonnormal', columns=1, count=2)
        chart, frame = self.frame(data)
        self.assertTrue(all(isinstance(child, NonnormalCapabilityPlotWidget) for child in chart.child_charts))
        self.assertEqual(chart.layout_columns, 1)
        self.assertGreater(frame.capture().height(), 1000)
        self.assertNotEqual(chart.child_charts[0].result['fit_info']['mean_trans'], chart.child_charts[1].result['fit_info']['mean_trans'])

    def test_annotations_and_office_capture_include_every_live_child(self):
        data = entry(count=2)
        data['graph_presentation'] = {'title': 'Inspection capability comparison', 'subtitle': 'Before and after', 'subtitle_enabled': True,
                                     'footnote': 'Two independent fitted variables', 'footnote_enabled': True}
        chart, frame = self.frame(data)
        self.assertEqual(frame.title_label.text(), 'Inspection capability comparison')
        self.assertEqual(frame.subtitle_label.text(), 'Before and after')
        self.assertEqual(frame.footnote_label.text(), 'Two independent fitted variables')
        image = frame.capture()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self.assertTrue(image.save(buffer, 'PNG'))
        png = bytes(buffer.data())
        self.assertEqual(png_size(png), (image.width(), image.height()))
        with scratch() as folder:
            for ext, export, member in [('.docx', export_docx, 'word/media/graph.png'), ('.pptx', export_pptx, 'ppt/media/graph.png')]:
                path = Path(folder) / ('multiple' + ext)
                export(path, OfficeSnapshot(data['title'], 'Comparison report', png))
                with ZipFile(path) as package:
                    self.assertEqual(package.read(member), png)
        self.assertEqual(chart.editable_objects(), [])

    def test_invalid_layout_and_empty_series_rejected(self):
        for data in [entry(columns=0), entry(columns=True), entry(count=0)]:
            with self.subTest(columns=data['result']['options']['columns']), self.assertRaises(ValueError):
                MultipleCapabilityChartWidget(data)

    def test_layout_refresh_rebuilds_with_requested_columns(self):
        data = entry(count=3)
        chart, frame = self.frame(data)
        data['result']['options']['columns'] = 1
        frame.apply_appearance()
        self.app.processEvents()
        self.assertEqual((chart.layout_rows, chart.layout_columns), (3, 1))
        self.assertEqual(len(chart.child_charts), 3)
