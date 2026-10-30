"""Readable diagnostic tick values and retained manual-scale transformations."""
import math,unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QRectF
from statcraft.plot_ticks import nice_limits,tick_values
from statcraft.modern_charts import ChartWidget
from statcraft.verification_fonts import load_verification_fonts


class PlotTickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def test_frequency_labels_are_whole_numbers_and_enclose_counts(self):
        bounds=nice_limits(0,36.04,integer=True)
        self.assertEqual(bounds,(0.,40.));self.assertEqual(tick_values(*bounds,integer=True),[0.,10.,20.,30.,40.])
        self.assertTrue(all(value==int(value) for value in tick_values(0,3.18,integer=True)))

    def test_residual_ranges_use_short_decimal_steps_and_exact_zero(self):
        bounds=nice_limits(-.047312,.045889)
        self.assertLessEqual(bounds[0],-.047312);self.assertGreaterEqual(bounds[1],.045889)
        ticks=tick_values(*bounds);self.assertIn(0.,ticks)
        self.assertGreaterEqual(len(ticks),3);self.assertLessEqual(len(ticks),8)
        step=ticks[1]-ticks[0]
        self.assertTrue(any(math.isclose(step,value,rel_tol=1e-10) for value in (.01,.02,.025,.05)))
        self.assertTrue(all(math.isclose(b-a,step,rel_tol=1e-10) for a,b in zip(ticks,ticks[1:])))
        self.assertTrue(all(not (value==0 and math.copysign(1,value)<0) for value in ticks))

    def test_observation_order_range_never_needs_negative_ticks(self):
        bounds=nice_limits(0,180*1.04)
        self.assertEqual(bounds,(0.,200.));self.assertTrue(all(value>=0 for value in tick_values(*bounds,integer=True)))

    def test_wide_and_narrow_ranges_are_finite_and_contained(self):
        for low,high in ((1e-200,5e-200),(-1e200,3e200),(1000000000.,1000000001.),(-2.,-1.)):
            limits=nice_limits(low,high);self.assertTrue(all(math.isfinite(v) for v in limits))
            self.assertLessEqual(limits[0],low);self.assertGreaterEqual(limits[1],high)
            ticks=tick_values(*limits);self.assertTrue(ticks);self.assertLessEqual(len(ticks),101)
            self.assertTrue(all(limits[0]-abs(high-low)*1e-9<=v<=limits[1]+abs(high-low)*1e-9 for v in ticks))

    def test_subnormal_and_unrepresentable_spans_do_not_overflow(self):
        tiny=float.fromhex('0x0.0000000000001p-1022')
        self.assertEqual(nice_limits(tiny,2*tiny),(tiny,2*tiny))
        self.assertEqual(tick_values(tiny,2*tiny),[tiny,2*tiny])
        self.assertEqual(nice_limits(-1e308,1e308),(-1e308,1e308))

    def test_manual_limits_are_preserved_when_nice_ticks_enabled(self):
        chart=ChartWidget({'title':'','result':{}});chart._panel_index=0
        chart.annotation_limits={'x':[-.025,.035],'y':[0.,7.]}
        image=QImage(800,600,QImage.Format.Format_ARGB32);painter=QPainter(image)
        try:
            rect,x,y=chart._axes(painter,QRectF(0,0,800,600),(-1.,1.),(-5.,5.),'X','Y',nice_ticks=True,frequency=True)
            self.assertAlmostEqual(x(-.025),rect.left());self.assertAlmostEqual(x(.035),rect.right())
            self.assertAlmostEqual(y(0.),rect.bottom());self.assertAlmostEqual(y(7.),rect.top())
        finally:painter.end();chart.deleteLater()
