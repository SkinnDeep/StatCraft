import copy
import os
import unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.logistic_chart import prepare
from statcraft.modern_charts import ChartWidget
from statcraft.verification_fonts import load_verification_fonts


def fixture():
    return dict(analysis='binary_logistic',event='Pass',options={'graphs':'four'},
        probabilities=[.1,.3,.65,.8],residuals=[-.3,1.2,-1.3,.5],pearson_residuals=[-.4,1.4,-1.5,.6],
        row_indices=[0,2,4,5],auc=.75,roc_curve=[
            dict(false_positive_rate=0.,sensitivity=0.),dict(false_positive_rate=0.,sensitivity=.5),
            dict(false_positive_rate=.5,sensitivity=.5),dict(false_positive_rate=.5,sensitivity=1.),dict(false_positive_rate=1.,sensitivity=1.)])


class LogisticChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False);load_verification_fonts(cls.app)

    def tearDown(self):
        for widget in self.app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def chart(self,r):
        chart=ChartWidget({'title':'Binary Logistic Regression','result':{}});prepare(chart,r);return chart

    def test_four_panels_have_correct_semantics(self):
        c=self.chart(fixture());self.assertEqual(len(c.panels),4);self.assertEqual(c.panel_columns,2)
        self.assertIn('ROC Curve',c.panels[0]['title']);self.assertEqual(c.panels[0]['lines'][0][1],c.panels[0]['x'])
        self.assertEqual(c.panels[1]['ylabel'],'Event Probability');self.assertEqual(c.panels[2]['ylabel'],'Deviance Residual');self.assertEqual(c.panels[3]['ylabel'],'Pearson Residual')

    def test_source_links_keep_missing_row_gaps_and_roc_has_none(self):
        c=self.chart(fixture());self.assertNotIn('row_indices',c.panels[0])
        for panel in c.panels[1:]:self.assertEqual(panel['row_indices'],[1,3,5,6])
        self.assertEqual(c.panels[1]['x'],[1,3,5,6])

    def test_four_plots_paint_at_two_sizes(self):
        c=self.chart(fixture())
        for width,height in [(960,900),(1440,1000)]:
            c.resize(width,height);image=c.grab().toImage();self.assertFalse(image.isNull());self.assertGreater(len(c.hit_regions),0);self.assertGreater(len(c.brush_regions),0)
            colors={image.pixelColor(x,y).name() for x in range(0,width,13) for y in range(0,height,13)};self.assertGreater(len(colors),10)

    def test_no_graph_choice_hides_panels(self):
        r=fixture();r['options']['graphs']='none';c=self.chart(r);self.assertEqual(c.panels,[]);self.assertEqual(c.note,'')

    def test_no_input_mutation(self):
        r=fixture();before=copy.deepcopy(r);self.chart(r).grab();self.assertEqual(r,before)

    def test_alignment_and_nonfinite_rejected_before_paint(self):
        for key,value in [('residuals',[1]),('probabilities',[.1,.2,float('nan'),.5]),('pearson_residuals',[.1,.2,float('inf'),.5])]:
            r=fixture();r[key]=value
            with self.assertRaises(ValueError):self.chart(r)

    def test_probability_validation(self):
        for key in ('probabilities','auc'):
            r=fixture();r[key]=[.1,.2,1.1,.4] if key=='probabilities' else 1.1
            with self.assertRaises(ValueError):self.chart(r)

    def test_roc_validation(self):
        for change in ('empty','nonfinite','nonmonotone','too_long'):
            r=fixture()
            if change=='empty':r['roc_curve']=[]
            elif change=='nonfinite':r['roc_curve'][1]['sensitivity']=float('inf')
            elif change=='nonmonotone':r['roc_curve'][2]['sensitivity']=.1
            else:r['roc_curve']*=2
            with self.assertRaises(ValueError):self.chart(r)

    def test_row_validation(self):
        for rows in ([0,0,2,3],[-1,1,2,3],[0,2,1,3],[0.,1,2,3]):
            r=fixture();r['row_indices']=rows
            with self.assertRaises(ValueError):self.chart(r)

    def test_extreme_finite_range_rejected_before_paint(self):
        r=fixture();r['residuals']=[-1e308,1e308,1.,2.]
        with self.assertRaisesRegex(ValueError,'precision'):self.chart(r)

    def test_display_limit_preserves_report_payload(self):
        r=fixture();n=20001;r.update(probabilities=[.5]*n,residuals=[0.]*n,pearson_residuals=[0.]*n,row_indices=list(range(n)));before=copy.deepcopy(r)
        with self.assertRaisesRegex(ValueError,'20,000'):self.chart(r)
        self.assertEqual(r,before)

    def test_actual_fit_uses_public_chart_path_and_row_links(self):
        from statcraft.model import Worksheet,Column
        from statcraft.logistic import fit,settings
        from statcraft.modern_charts import supported
        sheet=Worksheet('Dose study',[Column('Events',values=[1,2,4,5,7,8]),Column('Trials',values=[10]*6),Column('Dose',values=[1.,2.,3.,4.,5.,6.])])
        options=settings();options['graphs']='four'
        result=fit(sheet,0,[2],[],trials_index=1,options=options)
        entry={'title':'Binary Logistic Regression','result':result}
        self.assertTrue(supported(entry));chart=ChartWidget(entry);self.assertIsNone(chart.error);self.assertEqual(len(chart.panels),4)
        chart.resize(1200,1000);self.assertFalse(chart.grab().isNull());self.assertGreater(len(chart.brush_regions),0)
        self.assertEqual(chart.panels[1]['row_indices'],[1,2,3,4,5,6])
        result['options']['graphs']='none';self.assertFalse(supported(entry));hidden=ChartWidget(entry);self.assertEqual(hidden.panels,[])
