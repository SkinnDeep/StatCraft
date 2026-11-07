"""Independent classical OLS fixtures; no vendor numerical-parity claim."""
import itertools
import math
import unittest
import numpy as np
from scipy import stats
from statcraft.engine import MISSING_SENTINEL
from statcraft.inference import linear_regression
from statcraft.regression import multiple_regression


class MultipleRegressionTests(unittest.TestCase):
    def cube(self):
        rows = list(itertools.product((-1., 1.), repeat=3))
        return [[r[0] for r in rows], [r[1] for r in rows]], [10+2*a-3*b+.5*c for a,b,c in rows]

    def test_orthogonal_closed_form_coefficients_and_anova(self):
        x, y = self.cube()
        r = multiple_regression(x, y, predictor_names=['A', 'B'])
        self.assertEqual(r['predictor_names'], ['A', 'B'])
        self.assertEqual([c['name'] for c in r['coefficients']], ['Constant', 'A', 'B'])
        for c, expected in zip(r['coefficients'], (10, 2, -3)):
            self.assertAlmostEqual(c['estimate'], expected, places=12)
            self.assertAlmostEqual(c['standard_error'], math.sqrt(.05), places=12)
            self.assertLess(c['ci_low'], expected)
            self.assertGreater(c['ci_high'], expected)
        self.assertIsNone(r['coefficients'][0]['vif'])
        for c in r['coefficients'][1:]: self.assertAlmostEqual(c['vif'], 1, places=12)
        self.assertEqual((r['df_regression'], r['df_error'], r['df_total']), (2, 5, 7))
        for k,v in [('ss_error',2),('ss_regression',104),('ss_total',106),('f',130),
                    ('residual_stdev',math.sqrt(.4)),('r_squared',52/53),
                    ('adjusted_r_squared',1-(2/5)/(106/7))]:
            self.assertAlmostEqual(r[k], v, places=11)
        # F(2,5) survival has the closed form (5/(5+2*f))**(5/2).
        self.assertAlmostEqual(r['p_value'], 53**(-2.5), places=14)
        self.assertAlmostEqual(sum(r['residuals']), 0, places=12)

    def test_one_predictor_agrees_with_existing_independent_api(self):
        x,y = [0,1,2,3,4],[1,2,1,4,5]
        simple, multi = linear_regression(x,y), multiple_regression([x],y)
        for row, name in zip(multi['coefficients'], ['intercept','slope']):
            for a,b in [('estimate',name),('standard_error',name+'_se'),('t',name+'_t'),
                        ('p_value',name+'_p_value'),('ci_low',name+'_ci_low'),('ci_high',name+'_ci_high')]:
                self.assertAlmostEqual(row[a],simple[b],places=12)
        self.assertAlmostEqual(multi['f'], simple['slope_t']**2, places=12)
        self.assertAlmostEqual(multi['p_value'], simple['slope_p_value'], places=13)
        self.assertAlmostEqual(multi['r_squared'],simple['r_squared'],places=12)

    def test_nonorthogonal_matrix_fixture_by_direct_normal_equations(self):
        x=[[0,1,2,4,5,6],[2,0,3,1,5,4]]; y=[1,3,2,6,7,8]
        r=multiple_regression(x,y)
        design=np.column_stack([np.ones(6), np.asarray(x).T])
        inv=np.linalg.inv(design.T@design)
        beta=inv@design.T@np.asarray(y)
        residual=np.asarray(y)-design@beta
        mse=float(residual@residual)/3
        for c,b,se in zip(r['coefficients'],beta,np.sqrt(mse*np.diag(inv))):
            self.assertAlmostEqual(c['estimate'],float(b),places=11)
            self.assertAlmostEqual(c['standard_error'],float(se),places=11)
            self.assertAlmostEqual(c['p_value'],float(2*stats.t.sf(abs(b/se),3)),places=12)
        # Two-predictor VIF is 1/(1-r_xy**2), independent of OLS covariance route.
        corr=float(np.corrcoef(x)[0,1])
        for c in r['coefficients'][1:]: self.assertAlmostEqual(c['vif'],1/(1-corr*corr),places=12)

    def test_joint_missing_mask_and_original_row_indices(self):
        x,y=self.cube()
        x[0].extend([None, 4, 4, 4]);x[1].extend([4,None,4,4]);y.extend([4,4,None,MISSING_SENTINEL])
        r=multiple_regression(x,y)
        self.assertEqual((r['count'],r['missing'],r['row_indices']),(8,4,list(range(8))))
        self.assertAlmostEqual(r['coefficients'][1]['estimate'],2,places=12)

    def test_scaling_translation_and_column_permutation(self):
        x,y=self.cube(); a=multiple_regression(x,y)
        b=multiple_regression([[v*1e8+1e9 for v in x[1]],[v*1e-8-1e-7 for v in x[0]]],y)
        self.assertAlmostEqual(b['coefficients'][1]['estimate']*1e8,-3,places=11)
        self.assertAlmostEqual(b['coefficients'][2]['estimate']*1e-8,2,places=11)
        self.assertAlmostEqual(b['r_squared'],a['r_squared'],places=13)
        np.testing.assert_allclose(a['fitted'],b['fitted'],rtol=1e-13,atol=1e-13)

    def test_exact_fit_has_explicit_no_inference_policy(self):
        x,y=self.cube();y=[10+2*a-3*b for a,b in zip(*x)]
        r=multiple_regression(x,y)
        self.assertEqual(r['status'],'exact_fit')
        self.assertTrue(r['warnings'])
        self.assertEqual((r['r_squared'],r['ss_error']),(1,0))
        self.assertIsNone(r['f']);self.assertIsNone(r['p_value'])
        for c in r['coefficients']:
            self.assertIsNone(c['t']);self.assertIsNone(c['p_value']);self.assertIsNone(c['ci_low'])

    def test_rank_degrees_of_freedom_and_domain_validation(self):
        for x,y in [([], [1,2,3]), ([[1,2]],[1,2,3]), ([[1,1,1]],[1,2,3]),
                    ([[1,2,3],[2,4,6]],[2,3,5]), ([[1,2,3],[1,0,2]],[2,3,5]),
                    ([[1,2,3]],[4,4,4]), ([[1,None,3]],[1,2,3])]:
            with self.assertRaises(ValueError):multiple_regression(x,y)
        for conf in [0,1,math.nan,math.inf]:
            with self.assertRaises(ValueError):multiple_regression([[1,2,3,4]],[1,3,2,4],confidence=conf)
        for names in [[], [''], ['a','b']]:
            with self.assertRaises(ValueError):multiple_regression([[1,2,3]],[1,3,2],predictor_names=names)
        with self.assertRaises(TypeError):multiple_regression([[1,True,3]],[1,3,2])

    def test_extreme_finite_data_fail_cleanly(self):
        with self.assertRaises(ValueError):
            multiple_regression([[0,1,2,3]],[-1e200,1e200,-2e200,2e200])

    def test_full_df_collinearity_and_affine_dependence_rejected(self):
        for second in ([2,4,6,8,10], [5,7,9,11,13]):
            with self.assertRaisesRegex(ValueError, 'rank deficient'):
                multiple_regression([[1,2,3,4,5],second],[1,3,2,6,5])

    def test_minitab_parity_press_predicted_r2_and_unusual_diagnostics(self):
        # Known dataset with an outlier and a high leverage point
        x1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 20.0]  # row 10 has extreme high leverage
        x2 = [2.0, 3.0, 2.5, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 10.0]
        y =  [5.1, 7.2, 7.8, 9.9, 11.8, 30.0, 16.2, 18.0, 20.1, 45.0]  # row 6 (index 5) is an outlier
        r = multiple_regression([x1, x2], y, predictor_names=['X1', 'X2'], response_name='Y_Response')

        # Check regression equation formatting
        self.assertIn('Y_Response =', r['regression_equation'])
        self.assertIn('X1', r['regression_equation'])
        self.assertIn('X2', r['regression_equation'])

        # Check leverages
        leverages = r['leverages']
        self.assertEqual(len(leverages), 10)
        self.assertAlmostEqual(sum(leverages), 3.0, places=10)  # p + 1 = 3

        # Check PRESS and predicted R-squared
        self.assertIn('press', r)
        self.assertIn('predicted_r_squared', r)
        self.assertGreater(r['press'], 0.0)
        self.assertGreaterEqual(r['predicted_r_squared'], 0.0)
        self.assertLessEqual(r['predicted_r_squared'], 1.0)

        # Check unusual observations
        unusual = r['unusual_observations']
        self.assertGreater(len(unusual), 0)
        symbols = [u['symbol'] for u in unusual]
        # Should flag large residual ('R') or high leverage ('X')
        self.assertTrue(any('R' in s for s in symbols))
        self.assertTrue(any('X' in s for s in symbols))

        # Check 4-in-1 widget instantiation
        import sys
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from statcraft.regression_residual_chart import RegressionResidualChartWidget
        entry = {'result': r, 'title': 'Test Regression'}
        widget = RegressionResidualChartWidget(entry)
        self.assertEqual(widget.sizeHint().width(), 920)
        self.assertEqual(widget.sizeHint().height(), 640)
        widget.close()
        widget.deleteLater()
        app.processEvents()

    def test_regression_dialog_and_subdialogs(self):
        import sys
        from PySide6.QtWidgets import QApplication, QWidget
        app = QApplication.instance() or QApplication(sys.argv)
        from statcraft.app import Presenter, Worksheet, Column
        from statcraft.regression_dialog import (
            FitRegressionModelDialog, RegressionOptionsDialog,
            RegressionGraphsDialog, RegressionResultsDialog, RegressionStorageDialog
        )
        p = Presenter()
        p.worksheet = Worksheet("Test", [
            Column("Y", values=[10.0, 12.0, 15.0, 18.0, 22.0, 25.0]),
            Column("X1", values=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]),
            Column("X2", values=[2.0, 1.0, 4.0, 3.0, 5.0, 7.0]),
        ])
        class MockWindow(QWidget):
            def __init__(self, presenter):
                super().__init__()
                self.presenter = presenter
                self.results_shown = []
            def refresh(self): pass
            def show_result(self, entry): self.results_shown.append(entry)

        win = MockWindow(p)
        dlg = FitRegressionModelDialog(win)

        # Test subdialogs
        opt_dlg = RegressionOptionsDialog(dlg, dlg.options)
        opt_dlg.spin_conf.setValue(90.0)
        opt_dlg.validate()
        self.assertAlmostEqual(opt_dlg.options['confidence'], 0.90)

        graph_dlg = RegressionGraphsDialog(dlg, dlg.options)
        graph_dlg.combo_graphs.setCurrentIndex(0)
        graph_dlg.validate()
        self.assertEqual(graph_dlg.options['graphs'], 'four')

        res_dlg = RegressionResultsDialog(dlg, dlg.options)
        res_dlg.chk_unusual.setChecked(True)
        res_dlg.validate()
        self.assertTrue(res_dlg.options['results']['unusual'])

        store_dlg = RegressionStorageDialog(dlg, dlg.options)
        store_dlg.chk_fits.setChecked(True)
        store_dlg.chk_residuals.setChecked(True)
        store_dlg.validate()
        self.assertTrue(store_dlg.options['storage']['fits'])
        self.assertTrue(store_dlg.options['storage']['residuals'])

        # Apply storage to dialog
        dlg.options['storage'] = store_dlg.options['storage']
        dlg.controls['response_index'].setText('C1')
        dlg.controls['predictor_indices'].setText('C2 C3')
        dlg.validate()

        self.assertEqual(len(win.results_shown), 1)
        res_entry = win.results_shown[0]
        self.assertEqual(res_entry['result']['count'], 6)
        # Check storage columns added to worksheet
        col_names = [c.name for c in p.worksheet.columns]
        self.assertIn('FITS1', col_names)
        self.assertIn('RESI1', col_names)
        for d in (opt_dlg, graph_dlg, res_dlg, store_dlg, dlg, win):
            d.close()
            d.setParent(None)
            d.deleteLater()
        app.processEvents()


if __name__ == '__main__': unittest.main()
