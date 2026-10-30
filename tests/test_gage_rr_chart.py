import copy,os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.model import Worksheet,Column
from statcraft.gage_rr import analyze
from statcraft.gage_rr_report import sections,text_report
from statcraft.modern_charts import ChartWidget,supported
from statcraft.verification_fonts import load_verification_fonts


def study(repeats=2,constant=False):
    rows=[(10. if constant else 20+p*3+o+.1*r,'P'+str(p+1),'Op'+str(o+1)) for p in range(3) for o in range(2) for r in range(repeats)]
    sheet=Worksheet('Measurement',[Column('Diameter',values=[a[0] for a in rows]),Column('Part','text',[a[1] for a in rows]),Column('Operator','text',[a[2] for a in rows])])
    return analyze(sheet,0,1,2)


class GageRRChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False);load_verification_fonts(cls.app)

    def tearDown(self):
        for widget in self.app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def chart(self,result):
        entry={'title':'Gage R&R Study for Diameter','result':result};self.assertTrue(supported(entry));return ChartWidget(entry)

    def test_six_panels_render_at_two_sizes_with_real_hit_regions(self):
        c=self.chart(study());self.assertIsNone(c.error);self.assertEqual(len(c.panels),6);self.assertEqual(c.panel_columns,2)
        for width,height in [(960,1040),(1440,1200)]:
            c.resize(width,height);image=c.grab().toImage();self.assertFalse(image.isNull());self.assertGreater(len(c.hit_regions),0);self.assertGreater(len(c.brush_regions),0)
            # A real rendered graph contains substantially more than a white canvas.
            colors={image.pixelColor(x,y).name() for x in range(0,width,9) for y in range(0,height,9)}
            self.assertGreater(len(colors),10)

    def test_measurement_and_factor_names_and_source_rows(self):
        r=study();c=self.chart(r);p=c.panels
        self.assertEqual(p[1]['categories'],['P1','P2','P3']);self.assertEqual(p[3]['categories'],['Op1','Op2']);self.assertEqual(p[1]['ylabel'],'Diameter')
        self.assertEqual(p[5]['legend'],'Operator');self.assertEqual(p[5]['series'][0]['x'],[1,2,3])
        self.assertEqual(sorted(a for s in p[1]['series'] for a in s['row_indices']),[a+1 for a in r['row_indices']])
        self.assertEqual(sorted(a for s in p[3]['series'] for a in s['row_indices']),list(range(1,r['n']+1)))

    def test_control_limits_match_standard_range_constants_and_do_not_join_operators(self):
        c=self.chart(study());ranges=c.panels[2];means=c.panels[4];rbar=.1
        limits=dict(ranges['limits']);self.assertAlmostEqual(limits['Center'],rbar);self.assertAlmostEqual(limits['UCL'],3.267*rbar);self.assertEqual(limits['LCL'],0)
        grand=sum(a['value'] for a in c.result['plot_data']['rows'])/c.result['n'];limits=dict(means['limits'])
        self.assertAlmostEqual(limits['UCL'],grand+1.880*rbar);self.assertAlmostEqual(limits['LCL'],grand-1.880*rbar)
        self.assertEqual(len(ranges['series']),2);self.assertEqual(ranges['series'][0]['x'],[1,2,3]);self.assertEqual(ranges['series'][1]['x'],[4,5,6])

    def test_unsupported_replicate_constants_are_not_fabricated(self):
        c=self.chart(study(11));self.assertEqual(c.panels[2]['limits'],[]);self.assertEqual(c.panels[4]['limits'],[]);self.assertIn('unavailable',c.note);self.assertFalse(c.grab().isNull())

    def test_constant_study_renders_without_undefined_percentage_crash(self):
        c=self.chart(study(constant=True));self.assertIsNone(c.error);self.assertFalse(c.grab().isNull());self.assertEqual(dict(c.panels[2]['limits'])['UCL'],0)
        self.assertTrue(c.panels[0]['undefined']);self.assertTrue(all(v is None for a in c.panels[0]['series'] for v in a['y']))
        report=text_report(c.result);self.assertIn('Number of Distinct Categories',report);self.assertNotIn('nan',report.lower());self.assertNotIn('plot_data',report)

    def test_report_lists_final_and_full_anova_without_internal_payload(self):
        r=study();text=text_report(r);tables=sections(r)
        self.assertIn('Two-Way ANOVA with Interaction',text);self.assertIn('Final Model',text);self.assertIn('Variance Components',text);self.assertIn('Diameter',text);self.assertIn('Pooled into repeatability',text)
        self.assertNotIn('%Tolerance',next(a[1] for a in tables if a[0]=='Gage Evaluation'));self.assertNotIn('row_indices',text);self.assertNotIn('plot_data',text)
        for title,headers,rows in tables:
            self.assertTrue(all(len(row)==len(headers) for row in rows),title)

    def test_tolerance_process_and_retained_interaction_are_reported(self):
        r=study();r['options'].update(tolerance=10.,process_stdev=2.);r['interaction']['pooled']=False
        tables=sections(r);headers=next(a[1] for a in tables if a[0]=='Gage Evaluation');self.assertIn('%Tolerance',headers);self.assertIn('%Process',headers);self.assertIn('Retained',text_report(r));self.assertIn('only as the %Process denominator',text_report(r))
        c=self.chart(r);before=copy.deepcopy(r);c.grab();self.assertEqual(r,before)

    def test_invalid_nonfinite_data_is_rejected_before_paint(self):
        r=study();r['plot_data']['rows'][0]['value']=float('nan');c=self.chart(r);self.assertEqual(c.panels,[]);self.assertIn('finite',c.error)

    def test_large_finite_constant_uses_safe_center_instead_of_overflow(self):
        rows=[(1e308,p,o) for p in (1,2,3) for o in (1,2) for _ in range(2)]
        sheet=Worksheet('Huge constant',[Column('Y',values=[v for v,p,o in rows]),Column('Part',values=[p for v,p,o in rows]),Column('Operator',values=[o for v,p,o in rows])])
        c=self.chart(analyze(sheet,0,1,2));self.assertIsNone(c.error);self.assertEqual(dict(c.panels[4]['limits'])['Center'],1e308);self.assertFalse(c.grab().isNull())

    def test_equivalent_integer_float_factor_levels_retain_every_observation(self):
        rows=[(10+p+o+.1*rep,float(p) if rep else p,float(o) if rep else o) for p in (1,2,3) for o in (1,2) for rep in range(2)]
        sheet=Worksheet('Numeric factors',[Column('Y',values=[v for v,p,o in rows]),Column('Part',values=[p for v,p,o in rows]),Column('Operator',values=[o for v,p,o in rows])])
        r=analyze(sheet,0,1,2);c=self.chart(r);self.assertIsNone(c.error)
        self.assertEqual(sum(len(a['y']) for a in c.panels[1]['series']),len(rows));self.assertEqual(sum(len(a['y']) for a in c.panels[3]['series']),len(rows));self.assertEqual(len(c.panels[5]['series']),2);self.assertFalse(c.grab().isNull())

    def test_display_limits_preserve_valid_study_reports(self):
        for part_count,operator_count,repeats in [(101,2,2),(3,21,2),(2,2,5001)]:
            rows=[(10.+p+o+.001*rep,p,o) for p in range(part_count) for o in range(operator_count) for rep in range(repeats)]
            sheet=Worksheet('Large study',[Column('Y',values=[v for v,p,o in rows]),Column('Part',values=[p for v,p,o in rows]),Column('Operator',values=[o for v,p,o in rows])])
            r=analyze(sheet,0,1,2);c=self.chart(r);self.assertIn('graph display supports at most',c.error);self.assertEqual(c.panels,[]);self.assertIn('complete numerical report',c.error);self.assertIn('Gage Evaluation',text_report(r));self.assertFalse(c.grab().isNull())

    def test_grouping_scans_raw_and_cells_a_bounded_number_of_times(self):
        class CountedList(list):
            def __init__(self,values):super().__init__(values);self.iterations=0
            def __iter__(self):self.iterations+=1;return super().__iter__()
        r=study();raw=CountedList(r['plot_data']['rows']);cells=CountedList(r['plot_data']['cells']);r['plot_data'].update(rows=raw,cells=cells)
        c=self.chart(r);self.assertIsNone(c.error);self.assertLessEqual(raw.iterations,3);self.assertEqual(cells.iterations,1)

    def test_control_axes_show_operator_once_per_block_without_overlap(self):
        from statcraft.gage_rr_smoke import fixture
        c=self.chart(analyze(fixture(),2,0,1));c.resize(1180,1100);records=[];original=c._text
        def capture(p,rect,text,*args,**kwargs):records.append((QRectF(rect),str(text)));return original(p,rect,text,*args,**kwargs)
        from PySide6.QtCore import QRectF
        c._text=capture;c.grab()
        for index in (2,4):
            area=c.panel_areas()[index]
            labels=[(rect,text) for rect,text in records if text in ('Alex','Blair','Casey') and area.top()<rect.top()<area.bottom() and rect.left()>=area.left() and rect.right()<=area.right()]
            self.assertEqual([text for rect,text in labels],['Alex','Blair','Casey'])
            self.assertTrue(all(left.right()<=right.left()+.01 for (left,_),(right,_) in zip(labels,labels[1:])))
            ticks=[(rect,text) for rect,text in records if text.isdigit() and area.top()<rect.top()<area.bottom() and rect.left()>=area.left() and rect.right()<=area.right()]
            self.assertLess(len(ticks),30)
