"""Regression for user-visible one-sided confidence and benchmark-Z plot options."""
import math
import unittest
from PySide6.QtWidgets import QApplication
from statcraft.capability_engine import run_normal_capability
from statcraft.capability_chart import CapabilityPlotWidget,performance_table

class CapabilityChartOptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_all_confidence_modes_paint_actual_chart_including_one_sided_and_one_spec(self):
        data=[10+math.sin(i*.7)+i*.01 for i in range(50)]
        for ci_type in ('two_sided','lower','upper'):
            for lsl in (None,7):
                with self.subTest(ci_type=ci_type,lsl=lsl):
                    result=run_normal_capability(data,lsl=lsl,usl=14,include_ci=True,ci_type=ci_type)
                    chart=CapabilityPlotWidget({'result':result});chart.resize(900,600)
                    self.assertFalse(chart.grab().isNull())
                    chart.deleteLater()

    def test_benchmark_chart_uses_standardized_z_not_ppm_and_preserves_missing_values(self):
        result=run_normal_capability([9,10,11,10,12,11],lsl=5,usl=17)
        headers,rows=performance_table(result,'zbench')
        self.assertEqual(headers,['Within','Overall'])
        self.assertEqual([r[0] for r in rows],['Z.LSL','Z.USL','Z.Bench'])
        self.assertEqual(rows[0][1],[result['within_perf']['z_lsl'],result['overall_perf']['z_lsl']])
        self.assertEqual(rows[-1][1],[result['within_perf']['z_bench'],result['overall_perf']['z_bench']])
        result['within_perf']['z_bench']=None
        self.assertIsNone(performance_table(result,'zbench')[1][-1][1][0])

    def test_percent_and_ppm_graph_values_follow_selected_units(self):
        data=[9,10,11,10,12,11]
        for unit in ('ppm','percent'):
            r=run_normal_capability(data,lsl=9.5,usl=11.5,display_unit=unit)
            headers,rows=performance_table(r,unit='%' if unit=='percent' else 'PPM')
            self.assertEqual(headers[0],'Observed')
            self.assertAlmostEqual(rows[-1][1][0],r['observed_perf']['total'])
            self.assertEqual(rows[-1][0],('%' if unit=='percent' else 'PPM')+' Total')
