import json
from pathlib import Path
import unittest
from zipfile import ZipFile
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column,serial_to_datetime,display_date
from statcraft.mpx import load_mpx
from statcraft.mpx_create import create_project,save_owned,MEMBER,DATE_SCHEMA
from test_mpx import scratch
from test_mpx_create import rewrite


class DateWorkbookTests(unittest.TestCase):
    def test_date_envelope_missing_epoch_and_mixed_roundtrip(self):
        values=[0,None,43831,43832.520833333336,45000.123456789]
        sheet=Worksheet('Dated',[Column('When','date',values),Column('Value',values=[1,2,3]),
            Column('Group','text',['A',None,''])])
        with scratch() as folder:
            path=Path(folder)/'dated.mpx';save_owned(create_project([sheet]),path);q=load_mpx(path)
            self.assertTrue(q.statcraft_owned);self.assertEqual(q.active_worksheet.columns[0].values,values)
            self.assertEqual(q.active_worksheet.columns[2].values,['A',None,''])
            with ZipFile(path) as archive:
                own=json.loads(archive.read(MEMBER));self.assertEqual(own['schema'],DATE_SCHEMA)
                self.assertEqual(own['sheets'][0]['missing_dates'],{'0':[1]})
                self.assertEqual(own['sheets'][0]['missing_text'],{'2':[1]})
                col=json.loads(archive.read('/sheets/0/sheet.json'))['Data']['Columns'][0]['WorksheetVarBody']
                self.assertEqual(col['Format']['Key'],2);self.assertEqual(col['Format']['Value']['ClassId'],19)
                self.assertEqual(col['Format']['Value']['TimeFmt'],[1091113027,1025,0,0,3801135])
                self.assertEqual(col['VarData']['VarDataBody']['NumericData'],[0,0]+values[2:])
                self.assertEqual(col['VarData']['Data'],1)

    def test_blank_date_growth_and_overwrite(self):
        p=Presenter();p.worksheet=Worksheet('Dates',[Column('When','date',[])])
        with scratch() as folder:
            path=Path(folder)/'dates.mpx';p.save(path);p.add_rows(3)
            p.set_cell(1,0,'2020-01-02 12:30:00');p.save(path);q=Presenter();q.load(path)
            self.assertEqual(q.worksheet.columns[0].values,[None,43832.520833333336,None])
            q.set_cell(0,0,'1899-12-30');q.save(path);r=load_mpx(path)
            self.assertTrue(r.statcraft_owned);self.assertEqual(r.active_worksheet.columns[0].values[0],0)

    def test_previous_v2_profile_upgrades_without_losing_text(self):
        p=Presenter();p.load(Path(__file__).parent/'fixtures/statcraft-profile-v2.mpx')
        self.assertTrue(p.native_project.statcraft_owned);original=list(p.worksheet.columns[2].values)
        p.add_column('When','date');p.set_cell(0,3,'2026-10-15')
        with scratch() as folder:
            path=Path(folder)/'upgrade.mpx';p.save(path);q=Presenter();q.load(path)
            self.assertTrue(q.native_project.statcraft_owned);self.assertEqual(q.native_project._owned_schema,DATE_SCHEMA)
            self.assertEqual(q.worksheet.columns[2].values,original)
            self.assertEqual(q.worksheet.columns[3].values[1:],[None]*5)

    def test_invalid_calendar_values_do_not_replace_file(self):
        for value in (-1,1e10,1.23456e30):
            with self.subTest(value=value),scratch() as folder:
                path=Path(folder)/'keep.mpx';path.write_bytes(b'keep')
                p=Presenter();p.worksheet=Worksheet('D',[Column('D','date',[value])])
                with self.assertRaises(ValueError):p.save(path)
                self.assertEqual(path.read_bytes(),b'keep');self.assertIsNone(p.native_project)

    def test_missing_map_cannot_hide_nonzero_date_or_other_kind(self):
        for missing in ({'0':[1]},{'1':[0]},{'00':[0]},{'0':[True]},{'0':[0,0]},{'0':[-1]}):
            with scratch() as folder:
                path=Path(folder)/'changed.mpx'
                save_owned(create_project([Worksheet('D',[Column('D','date',[None,43831]),Column('X',values=[0])])]),path)
                def mutate(members):
                    own=json.loads(members[MEMBER]);own['sheets'][0]['missing_dates']=missing;members[MEMBER]=json.dumps(own).encode()
                rewrite(path,mutate);q=load_mpx(path)
                self.assertFalse(getattr(q,'statcraft_owned',False));self.assertEqual(q.active_worksheet.columns[0].values,[0,43831])

    def test_no_sidecar_preserves_native_placeholder_as_epoch(self):
        with scratch() as folder:
            path=Path(folder)/'foreign.mpx';save_owned(create_project([Worksheet('D',[Column('D','date',[None])])]),path)
            rewrite(path,lambda members:members.pop(MEMBER));q=load_mpx(path)
            self.assertFalse(getattr(q,'statcraft_owned',False));self.assertEqual(q.active_worksheet.columns[0].values,[0])

    def test_date_input_clipboard_and_undo(self):
        p=Presenter();p.worksheet=Worksheet('D',[Column('D','date',[None])])
        p.set_cell(0,0,'2020-01-02T12:30:00');self.assertEqual(p.copy_block(0,0,0,0),'2020-01-02 12:30:00\n')
        p.paste(1,0,'2020-01-03\n*');self.assertEqual(p.worksheet.columns[0].values,[43832.520833333336,43833,None])
        p.undo();self.assertEqual(p.worksheet.columns[0].values,[43832.520833333336])
        for raw in ('-1','1e10','NaN','2020-02-30','2020-01-01T00:00:00+00:00'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):p.set_cell(0,0,raw)
        self.assertEqual(p.worksheet.columns[0].values,[43832.520833333336])

    def test_display_is_readable_with_imported_serial_fallback(self):
        self.assertEqual(display_date(0),'1899-12-30');self.assertEqual(display_date(43831),'2020-01-01')
        self.assertEqual(display_date(43832.520833333336),'2020-01-02 12:30:00')
        self.assertEqual(display_date(-.25),'-0.25')
        self.assertEqual(display_date(1e10),'10000000000.0')
        with self.assertRaises(ValueError):serial_to_datetime(1e10)
