import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from statcraft.model import Worksheet,Column
from statcraft.attribute_capability import analyze
from statcraft.attribute_capability_dialogs import AttributeCapabilityDialog
from statcraft.attribute_capability_report import generate_attribute_capability_report
from statcraft.attribute_capability_chart import AttributeCapabilityChartWidget


class AttributeCapabilityUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        from statcraft.verification_fonts import load_verification_fonts
        load_verification_fonts(cls.app)

    def setUp(self):
        self.sheet=Worksheet('Calls',columns=[Column('Unanswered Calls',values=[4,1,3,5]),Column('Total Calls',values=[47,39,55,67]),Column('Notes','text',['A'])])

    def dialog(self,method='binomial'):
        dialog=AttributeCapabilityDialog(None,self.sheet,method)
        self.addCleanup(dialog.close)
        dialog.controls['count_index'].setText('C1')
        return dialog

    def test_named_numeric_columns(self):
        dialog=self.dialog()
        self.assertEqual(dialog.available.count(),2)
        self.assertIn('Unanswered Calls',dialog.available.item(0).text())
        dialog.available.setCurrentRow(0);dialog.transfer()
        self.assertIn('Unanswered Calls',dialog.controls['count_index'].text())
        self.assertEqual(dialog.values()['count_index'],0)

    def test_constant_ignores_disabled_size_column(self):
        dialog=self.dialog();dialog.controls['sample_size'].setText('50')
        dialog.controls['size_index'].setText('garbage')
        self.assertIsNone(dialog.values()['size_index'])
        self.assertEqual(dialog.values()['sample_size'],50)

    def test_column_size_and_target_units(self):
        dialog=self.dialog();dialog.controls['size_mode'].setCurrentIndex(1)
        dialog.controls['size_index'].setText('C2')
        dialog.controls['historical'].setText('0.023');dialog.controls['target'].setText('1')
        config=dialog.get_configuration()
        self.assertEqual(config['size_index'],1)
        self.assertEqual(config['options']['historical'],.023)
        self.assertEqual(config['options']['target'],.01)
        result=analyze(self.sheet,**config)
        self.assertAlmostEqual(result['observed_rate'],13/208)

    def test_fractional_poisson_exposure(self):
        dialog=self.dialog('poisson');dialog.controls['sample_size'].setText('.5')
        dialog.controls['target'].setText('2.5')
        self.assertEqual(dialog.values()['sample_size'],.5)
        self.assertEqual(dialog.values()['options']['target'],2.5)

    def test_invalid_options_rejected(self):
        for key,value in [('sample_size','0'),('sample_size','1.5'),('sample_size','nan'),('historical','2'),('target','101'),('confidence','100'),('confidence','inf')]:
            with self.subTest(key=key,value=value):
                dialog=self.dialog();dialog.controls[key].setText(value)
                with self.assertRaises(ValueError):dialog.values()

    def test_role_overlap_rejected(self):
        dialog=self.dialog();dialog.controls['size_mode'].setCurrentIndex(1)
        dialog.controls['size_index'].setText('C1')
        with self.assertRaisesRegex(ValueError,'separate'):dialog.values()

    def test_report_has_statistics_without_array_dumps(self):
        for method in ('binomial','poisson'):
            with self.subTest(method=method):
                result=analyze(self.sheet,method,0,size_index=1,options={'historical':.1})
                report=generate_attribute_capability_report(result)
                self.assertIn('Unanswered Calls',report)
                self.assertIn('95% CI',report)
                self.assertIn('historical rate',report)
                self.assertNotIn('cumulative_rates',report)
                self.assertNotIn('[47',report)
                self.assertIn('% Defective' if method=='binomial' else 'Mean DPU',report)

    def test_editable_styles_are_valid_persisted_targets(self):
        from statcraft.graph_styles import validate_styles
        result=analyze(self.sheet,'binomial',0,size_index=1)
        widget=AttributeCapabilityChartWidget({'result':result})
        styles={item['target']:item['defaults'] for item in widget.editable_objects()}
        validated=validate_styles(styles)
        self.assertIn('p0:ref2',validated)
        widget.close()
        styled=AttributeCapabilityChartWidget({'result':result,'graph_styles':validated})
        styled.resize(980,680);styled.show();self.app.processEvents()
        self.assertFalse(styled.grab().isNull())
        styled.close()

    def test_zero_defects_report_and_chart(self):
        sheet=Worksheet('Zero',columns=[Column('Defects',values=[0,0,0])])
        for method in ('binomial','poisson'):
            with self.subTest(method=method):
                result=analyze(sheet,method,0,sample_size=50)
                report=generate_attribute_capability_report(result)
                if method=='binomial':self.assertIn('+Infinity',report)
                widget=AttributeCapabilityChartWidget({'result':result})
                widget.resize(980,680);widget.show();self.app.processEvents()
                image=QImage(widget.size(),QImage.Format.Format_ARGB32);image.fill(0)
                widget.render(image)
                self.assertFalse(image.isNull())
                self.assertGreater(len(widget.hit_regions),10)
                objects=widget.editable_objects()
                self.assertTrue(any(item['target']=='p0:s0' for item in objects))
                widget.close()


if __name__=='__main__':unittest.main()
