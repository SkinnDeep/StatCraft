"""Original bounded collection writing; native reopening remains unverified."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from statcraft import io
from statcraft.model import Column, Matrix, Worksheet
from statcraft.mpx import load_mpx, save_mpx
from statcraft.mpx_create import create_project, save_owned, MEMBER, COLLECTION_SCHEMA
from test_mpx import scratch
from test_mpx_create import rewrite


def sample():
    return Worksheet('Collections', [Column('C',values=[1,2])],
        constants=[Column('Scalar',values=[3.141592653589793],metadata={'units':'rad'}),Column('',values=[None])],
        matrices=[Matrix('Matrix',2,3,[1,2,3,4,5,6],{'original':True}),Matrix('',1,3,[0,None,2])])


class CollectionsCreateTests(unittest.TestCase):
    def test_native_envelope_column_major_counts_and_metadata_roundtrip(self):
        sheet=sample()
        with scratch() as folder:
            path=Path(folder)/'collections.mpx';p=create_project([sheet]);save_owned(p,path);q=load_mpx(path)
            self.assertTrue(q.statcraft_owned);self.assertEqual(q.active_worksheet,sheet)
            self.assertEqual(q.active_worksheet.matrices[0].as_rows(),[[1,3,5],[2,4,6]])
            self.assertEqual(len(set(q._appended_ids.values())),5)
            with ZipFile(path) as archive:
                own=json.loads(archive.read(MEMBER));self.assertEqual(own['schema'],COLLECTION_SCHEMA)
                self.assertEqual(own['sheets'][0]['missing_constants'],{'1':[0]})
                self.assertEqual(own['sheets'][0]['missing_matrices'],{'1':[1]})
                native=json.loads(archive.read('/sheets/0/sheet.json'))
                self.assertEqual([native[k] for k in ('MaxRows_DEP','MaxColumns_DEP','MaxConstants_DEP','MaxMatrices_DEP')],[2,1,2,2])
                for key,cls,var,width in [('Constants',435,2,1),('Matrices',436,4,3)]:
                    entry=native['Data'][key][0];wrapper=entry['WorksheetVarBody']
                    self.assertEqual(entry['ClassId'],cls);self.assertEqual(entry['VarId']['Variable'],var)
                    self.assertEqual(entry['VarId']['VarId'],1);self.assertEqual(wrapper['FormatType'],0)
                    self.assertEqual(wrapper['GeneralVarFmt'],{'ClassId':0,'Hidden':False})
                    self.assertEqual(wrapper['VarData']['VariableType'],var)
                    self.assertEqual(wrapper['VarData']['VarDataBody']['ColCt'],width)
                    self.assertEqual(wrapper['Format']['Value']['MinValue'],min(sheet.constants[0].values if key=='Constants' else sheet.matrices[0].values))
                self.assertEqual(native['Data']['Matrices'][0]['WorksheetVarBody']['VarData']['VarDataBody']['NumericData'],[1,2,3,4,5,6])

    def test_overwrite_growth_append_stable_namespaced_ids(self):
        with scratch() as folder:
            path=Path(folder)/'collections.mpx';p=create_project([sample()]);save_owned(p,path);p=load_mpx(path)
            old=copy.deepcopy(p._appended_ids)
            p.active_worksheet.constants[0].name='Renamed';p.active_worksheet.constants[0].values=[5]
            p.active_worksheet.constants.append(Column('Third',values=[0]))
            p.active_worksheet.matrices[0]=Matrix('Bigger',3,2,[1,None,3,4,5,6])
            save_mpx(p,path);q=load_mpx(path)
            self.assertTrue(q.statcraft_owned);self.assertEqual(q.active_worksheet,p.active_worksheet)
            self.assertTrue(all(q._appended_ids[k]==v for k,v in old.items()))
            self.assertEqual(len(q._appended_ids),6)
            with ZipFile(path) as archive:
                native=json.loads(archive.read('/sheets/0/sheet.json'))
                self.assertEqual(native['MaxRows_DEP'],2)  # Original writer choice: collection extents are separate.
                self.assertEqual(native['MaxConstants_DEP'],3)

    def test_collection_only_and_multiple_mixed_sheets_keep_separate_identities(self):
        only=Worksheet('Only',constants=[Column('',values=[None])],matrices=[Matrix('',1,1,[None])])
        mixed=sample();mixed.columns.extend([Column('Date','date',[0,None]),Column('Group','text',['',None])])
        with scratch() as folder:
            path=Path(folder)/'mixed.mpx';save_owned(create_project([only,mixed],1),path);q=load_mpx(path)
            self.assertTrue(q.statcraft_owned);self.assertEqual(q.worksheets,[only,mixed]);self.assertEqual(q.active_index,1)
            self.assertEqual(len(q._appended_ids),len(set(q._appended_ids.values())))
            with ZipFile(path) as archive:
                native=json.loads(archive.read('/sheets/0/sheet.json'))
                self.assertEqual([native[k] for k in ('MaxRows_DEP','MaxColumns_DEP','MaxConstants_DEP','MaxMatrices_DEP')],[0,0,1,1])

    def test_previous_profiles_remain_byte_identical_and_upgrade_to_v4(self):
        for name in ('statcraft-profile-v1.mpx','statcraft-profile-v2.mpx','statcraft-profile-v3.mpx'):
            fixture=Path(__file__).parent/'fixtures'/name
            with self.subTest(profile=name),scratch() as folder:
                p=load_mpx(fixture);self.assertTrue(p.statcraft_owned)
                path=Path(folder)/'copy.mpx';save_owned(p,path)
                with ZipFile(fixture) as a,ZipFile(path) as b:
                    self.assertEqual({n:a.read(n) for n in a.namelist()},{n:b.read(n) for n in b.namelist()})
                before=copy.deepcopy(p.active_worksheet.columns)
                p.active_worksheet.constants.append(Column('K',values=[None]))
                save_mpx(p,path);q=load_mpx(path)
                self.assertTrue(q.statcraft_owned);self.assertEqual(q._owned_schema,COLLECTION_SCHEMA)
                self.assertEqual(q.active_worksheet.columns,before)
                self.assertEqual(q.active_worksheet.constants,[Column('K',values=[None])])

    def test_missing_maps_cannot_hide_nonzero_or_invalid_positions(self):
        cases=({'0':[0]},{'1':[0,0]},{'1':[-1]},{'1':[True]},{'01':[0]},{'2':[0]},{'1':'0'})
        for missing in cases:
            with self.subTest(missing=missing),scratch() as folder:
                path=Path(folder)/'tampered.mpx';save_owned(create_project([sample()]),path)
                def mutate(members):
                    own=json.loads(members[MEMBER]);own['sheets'][0]['missing_constants']=missing
                    members[MEMBER]=json.dumps(own,separators=(',',':')).encode()
                rewrite(path,mutate);q=load_mpx(path)
                self.assertFalse(getattr(q,'statcraft_owned',False))
                self.assertEqual(q.active_worksheet.constants[0].values,[3.141592653589793])
                self.assertEqual(q.active_worksheet.constants[1].values,[0])

    def test_missing_matrix_map_nonzero_and_unknown_metadata_fall_back(self):
        for kind in ('nonzero','unknown_metadata','duplicate_identity'):
            with self.subTest(kind=kind),scratch() as folder:
                path=Path(folder)/'tampered.mpx';save_owned(create_project([sample()]),path)
                def mutate(members):
                    if kind=='unknown_metadata':
                        native=json.loads(members['/sheets/0/sheet.json']);native['Data']['Matrices'][0]['Unknown']=1
                        members['/sheets/0/sheet.json']=json.dumps(native,separators=(',',':')).encode()
                    else:
                        own=json.loads(members[MEMBER])
                        if kind=='nonzero':own['sheets'][0]['missing_matrices']={'0':[0]}
                        else:
                            keys=list(own['column_ids']);own['column_ids'][keys[1]]=own['column_ids'][keys[0]]
                        members[MEMBER]=json.dumps(own,separators=(',',':')).encode()
                rewrite(path,mutate);q=load_mpx(path)
                self.assertFalse(getattr(q,'statcraft_owned',False));self.assertEqual(q.active_worksheet.matrices[0].values,[1,2,3,4,5,6])

    def test_collections_count_toward_limits_before_atomic_publication(self):
        p=create_project([sample()])
        with scratch() as folder:
            path=Path(folder)/'keep.mpx';save_owned(p,path);before=path.read_bytes()
            with patch.object(io,'MAX_CELLS',12),self.assertRaises(io.FormatError):save_owned(p,path)
            self.assertEqual(path.read_bytes(),before)
            for values in ([float('nan')],[io.MISSING_SENTINEL]):
                p.active_worksheet.constants[0].values=values
                with self.assertRaises((ValueError,io.UnsupportedFormatError)):save_owned(p,path)
                self.assertEqual(path.read_bytes(),before)

    def test_unsupported_scalar_types_empty_dimensions_and_missing_sidecar(self):
        for sheet in (Worksheet(constants=[Column('K','text',['x'])]),Worksheet(constants=[Column('K','date',[0])]),
                      Worksheet(matrices=[Matrix('M',0,2,[])]),Worksheet(matrices=[Matrix('M',1,1,[io.MISSING_SENTINEL])])):
            with self.subTest(sheet=sheet),self.assertRaises(io.UnsupportedFormatError):create_project([sheet])
        with scratch() as folder:
            path=Path(folder)/'foreign.mpx';save_owned(create_project([sample()]),path)
            rewrite(path,lambda members:members.pop(MEMBER));q=load_mpx(path)
            self.assertFalse(getattr(q,'statcraft_owned',False))
            self.assertEqual(q.active_worksheet.constants[1].values,[0])
            self.assertEqual(q.active_worksheet.matrices[1].values,[0,0,2])


if __name__=='__main__':unittest.main()
