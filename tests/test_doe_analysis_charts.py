"""Live renderer and prediction-dialog contracts for new DOE analyses."""
import math
import unittest
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from statcraft.model import Worksheet,Column
from statcraft.taguchi_analysis import analyze
from statcraft.doe_analysis_charts import TaguchiEffectsWidget
from statcraft.mixture_prediction_dialog import MixturePredictionDialog
from test_mixture_taguchi_workflows import mixture
from statcraft.graph_frame import GraphFrame
from statcraft.verification_fonts import load_verification_fonts

class DOEAnalysisChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)

    def test_real_level_labels_means_and_editable_series_paint(self):
        s=Worksheet('Taguchi',[Column('Material','text',['Brass','Steel','Brass','Steel']*2),Column('Speed',values=[1,1,2,2]*2),
            Column('First',values=[10+i*.4 for i in range(8)]),Column('Second',values=[10.2+i*.5 for i in range(8)])])
        result=analyze(s,[2,3],[0,1]);entry={'title':'Main effects','result':result}
        chart=TaguchiEffectsWidget(entry);frame=GraphFrame(chart,entry);frame.resize(1100,1050);frame.show();self.app.processEvents()
        try:
            self.assertEqual(len(chart.panels),6)
            self.assertEqual(chart.panels[0]['x_labels'],['Brass','Steel'])
            self.assertTrue(chart.editable_objects())
            self.assertFalse(frame.capture().isNull());self.assertIsNone(chart.error)
        finally:frame.close();frame.deleteLater()

    def test_unavailable_nominal_levels_have_gaps_without_chart_error(self):
        s=Worksheet('Static',[Column('Factor','text',['A','B','A','B']),Column('One',values=[10,12,11,14]),Column('Two',values=[10,13,11,16])])
        result=analyze(s,[1,2],[0],{'sn_type':'nominal','fit_models':False})
        chart=TaguchiEffectsWidget({'title':'Nominal','result':result});chart.resize(800,1050)
        self.assertFalse(chart.grab().isNull());self.assertIsNone(chart.error)
        panel=next(panel for panel in chart.panels if panel['metric']=='sn')
        self.assertIsNone(panel['y'][0]);chart.deleteLater()

    def test_prediction_rejects_wrong_total_then_accepts_valid_composition(self):
        p=mixture();entry=p.analyze_mixture(7,[4,5,6],model='linear');dialog=MixturePredictionDialog(p.worksheet,[entry])
        for i,value in enumerate((.1,.1,.1)):dialog.table.setItem(0,i,QTableWidgetItem(str(value)))
        dialog.validate();self.assertIsNone(dialog.parameters);self.assertIn('sum',dialog.error.text())
        for i,value in enumerate((.2,.3,.5)):dialog.table.item(0,i).setText(str(value))
        dialog.validate();self.assertEqual(dialog.result(),1)
        self.assertEqual(dialog.parameters['component_rows'],[[.2,.3,.5]]);dialog.deleteLater()

    def test_no_model_prediction_has_clear_inline_error(self):
        p=mixture();dialog=MixturePredictionDialog(p.worksheet,[]);dialog.validate()
        self.assertIsNone(dialog.parameters);self.assertIn('Analyze a mixture',dialog.error.text());dialog.deleteLater()
