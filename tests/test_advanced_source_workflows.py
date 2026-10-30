import json,tempfile,unittest
from pathlib import Path
from statcraft.app import Presenter,format_entry
from statcraft.model import Worksheet,Column
from statcraft.msa_linearity_engine import analyze_gage_linearity_and_bias
from test_preview77_real_outputs import make_presenter,make_entries


def numbers(value):
    if isinstance(value,dict):return {k:numbers(v) for k,v in value.items() if isinstance(v,(dict,list,int,float)) and not isinstance(v,bool)}
    if isinstance(value,list):return [numbers(v) for v in value if isinstance(v,(dict,list,int,float)) and not isinstance(v,bool)]
    return value


class AdvancedSourceWorkflowTests(unittest.TestCase):
    def test_three_msa_sources_survive_duplicate_names_moves_and_roundtrip(self):
        p=make_presenter();entries=[entry for entry,_ in make_entries(p)[:3]]
        original=[numbers(entry['result']) for entry in entries]
        p.move_columns([2],'before_c1');p.rename_column(0,'Reference')
        for entry,expected in zip(entries,original):self.assertEqual(numbers(p.rerun_result(entry)['result']),expected)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'msa.mpx';p.save(path);q=Presenter();q.load(path)
            for entry in list(q.history)[:3]:q.rerun_result(entry)
            q.delete_columns([0])
            with self.assertRaisesRegex(ValueError,'deleted'):q.rerun_result(q.history[0])
            q.undo();q.rerun_result(q.history[0])

    def test_nested_options_not_discarded_during_rerun(self):
        p=make_presenter();entry=p.nested_gage_rr(part_col=0,operator_col=1,measurement_col=2,options={'study_multiplier':5.15,'tolerance':10})
        p.rename_column(2,'Renamed')
        result=p.rerun_result(entry)['result']
        self.assertEqual(result['study_multiplier'],5.15)
        self.assertEqual(result['tolerance'],10)
        with self.assertRaises(ValueError):p.nested_gage_rr(part_col=0,operator_col=1,measurement_col=2,options={'study_multiplier':0})

    def test_lifetime_missing_rows_preserve_censor_identity_and_metadata(self):
        p=Presenter();p.worksheet=Worksheet('Life',[Column('Time',values=[1,None,4,8,9]),Column('Event',values=[1,0,1,0,1])])
        entry=p.reliability_distribution(settings={'column_index':0,'censor_index':1,'dist_name':'exponential'})
        result=entry['result'];self.assertEqual(result['n_events'],3);self.assertEqual(result['n_censored'],1)
        self.assertEqual(result['row_indices'],[0,2,3,4]);self.assertEqual(result['omitted_rows'],[1])
        p.move_columns([1],'before_c1');p.rename_column(0,'Status renamed')
        self.assertEqual(p.rerun_result(entry)['result']['parameters'],result['parameters'])
        self.assertIsNone(result['ad_stat']);self.assertNotIn('95.0% Normal CI',format_entry(entry))

    def test_exact_linearity_does_not_claim_no_significant_bias(self):
        result=analyze_gage_linearity_and_bias([1,1,2,2,3,3],[2,2,4,4,6,6])
        self.assertEqual(result['regression']['slope'],1)
        self.assertIsNone(result['regression']['slope_t']);self.assertIsNone(result['regression']['slope_p'])
        self.assertIsNone(result['overall_bias']['p_value'])
        json.dumps(result,allow_nan=False)
        from statcraft.msa_reports import format_gage_linearity_report
        self.assertIn('*',format_gage_linearity_report(result))
