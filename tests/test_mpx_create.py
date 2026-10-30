"""Original data only; canonical acceptance is not native interoperability."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import unittest
import zipfile
from statcraft import io
from statcraft.model import Column, Worksheet
from statcraft.mpx import load_mpx, save_mpx
from statcraft.mpx_create import create_project, save_owned, restore_owned, MEMBER, MODEL_TYPES
from test_mpx import fixture, scratch


def worksheet(name='Original data'):
    return Worksheet(name, [Column('Response', values=[1, None, 4.5], metadata={'auto_type': True}),
                            Column('', values=[2])], metadata={'doe': {'original': True}})


def rewrite(path, mutate):
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    mutate(members)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


class MpxCreateTests(unittest.TestCase):
    def test_original_envelope_two_sheets_identity_and_no_vendor_provenance(self):
        source = worksheet()
        project = create_project([source, worksheet('Other')], 1)
        self.assertEqual(project.active_index, 1)
        self.assertEqual(project.history, [])
        self.assertNotEqual(project.worksheet_ids[0], project.worksheet_ids[1])
        self.assertNotEqual(project.worksheet_ids[0], create_project([source]).worksheet_ids[0])
        source.columns[0].values[0] = 999
        self.assertEqual(project.worksheets[0].columns[0].values[0], 1)
        with scratch() as folder:
            path = Path(folder) / 'new.mpx'
            save_owned(project, path)
            with zipfile.ZipFile(path) as archive:
                meta = json.loads(archive.read('/project_metadata_20.json'))
                self.assertEqual(meta['Creator'], 'StatCraft')
                self.assertEqual(meta['ExtraInformation'], {'version_history': []})
                self.assertEqual(meta['NextSheet'], 2)
                self.assertEqual([m['Type'] for m in meta['Models']['Items']], MODEL_TYPES)
                self.assertEqual(len(meta['Models']['Items']), 21)
                self.assertEqual(meta['Commands']['Items'], [])
                for index, identifier in enumerate(project.worksheet_ids):
                    sheet = json.loads(archive.read('/sheets/' + str(index) + '/sheet.json'))
                    self.assertEqual(sheet['Data']['WorksheetId_DEP'], identifier)
                    self.assertEqual(sheet['Data']['Columns'][0]['WorksheetVarBody']['VarData']['Class_Version'], [2])
                    self.assertEqual(sheet['CreatedDate'], 0)
                    self.assertEqual(sheet['SavedDate'], 0)
            restored = load_mpx(path)
            self.assertTrue(restored.statcraft_owned)
            self.assertEqual(restored.active_index, 1)
            self.assertEqual(restored.worksheets, project.worksheets)

    def test_blank_and_zero_column_profiles_reload_experimentally(self):
        for sheet in (Worksheet('Empty'), Worksheet('Blank', [Column('') for _ in range(8)])):
            with self.subTest(columns=len(sheet.columns)), scratch() as folder:
                path = Path(folder) / 'blank.mpx'
                save_owned(create_project([sheet]), path)
                restored = load_mpx(path)
                self.assertTrue(restored.statcraft_owned)
                self.assertEqual(restored.active_worksheet, sheet)

    def test_stable_column_ids_across_edit_append_and_overwrite(self):
        with scratch() as folder:
            path = Path(folder) / 'original.mpx'
            project = create_project([worksheet()])
            original_ids = copy.deepcopy(project._appended_ids)
            save_owned(project, path)
            project = load_mpx(path)
            project.active_worksheet.columns[0].values.extend([5, None])
            project.active_worksheet.columns.append(Column('New response', values=[4, 5, 6]))
            save_mpx(project, path)
            restored = load_mpx(path)
            self.assertTrue(restored.statcraft_owned)
            for key, identifier in original_ids.items():
                self.assertEqual(restored._appended_ids[key], identifier)
            self.assertEqual(restored.active_worksheet.columns[0].values, [1, None, 4.5, 5, None])
            self.assertEqual(restored.active_worksheet.columns[2].values, [4, 5, 6])
            self.assertEqual(len(set(restored._appended_ids.values())), 3)

    def test_structural_reorder_rename_and_new_sheet_roundtrip(self):
        project = create_project([worksheet('First'), worksheet('Second')])
        original_ids = list(project.worksheet_ids)
        project.worksheets.reverse()
        project.worksheet_ids.reverse()
        project.worksheet_uris.reverse()
        project.worksheets[0].name = 'Renamed'
        project.active_index = 1
        with scratch() as folder:
            path = Path(folder) / 'order.mpx'
            save_owned(project, path)
            restored = load_mpx(path)
            self.assertEqual(restored.worksheet_ids, original_ids[::-1])
            self.assertEqual([s.name for s in restored.worksheets], ['Renamed', 'First'])
            self.assertTrue(restored.statcraft_owned)

    def test_sessions_bind_to_original_sheet_ids_and_remain_inert(self):
        project = create_project([worksheet()])
        entry = {'origin': 'statcraft', 'title': 'Summary', 'time': 'original fixture',
                 'result': {'count': 2}, 'worksheet_id': project.worksheet_ids[0],
                 'worksheet_name': 'Original data'}
        with scratch() as folder:
            path = Path(folder) / 'results.mpx'
            save_owned(project, path, [entry])
            restored = load_mpx(path)
            self.assertTrue(restored.statcraft_owned)
            self.assertEqual(restored.session_records, [entry])
            entry['worksheet_id'] = 'wrong'
            before = path.read_bytes()
            with self.assertRaises(io.FormatError):
                save_owned(project, path, [entry])
            self.assertEqual(path.read_bytes(), before)

    def test_unknown_member_or_native_default_change_never_grants_ownership(self):
        mutations = (
            lambda m: m.update({'/unknown.json': b'{}'}),
            lambda m: m.update({'/project_metadata_20.json': m['/project_metadata_20.json'].replace(b'"Creator":"StatCraft"', b'"Creator":"Other"')}),
            lambda m: m.update({'/sheets/0/sheet.json': m['/sheets/0/sheet.json'].replace(b'"PrintGrid":true', b'"PrintGrid":false')}),
            lambda m: m.update({MEMBER: m[MEMBER] + b' '}),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), scratch() as folder:
                path = Path(folder) / 'altered.mpx'
                save_owned(create_project([worksheet()]), path)
                rewrite(path, mutation)
                restored = load_mpx(path)
                self.assertFalse(getattr(restored, 'statcraft_owned', False))
                self.assertIn('import', restored.active_worksheet.metadata)
                with self.assertRaises(io.UnsupportedFormatError):
                    save_owned(restored, path)

    def test_original_native_project_and_fake_marker_do_not_grant_ownership(self):
        with scratch() as folder:
            path = Path(folder) / 'native.mpx'
            fixture(path)
            rewrite(path, lambda m: m.update({MEMBER: b'{"schema":"statcraft-owned-mpx-v1","sheets":[],"column_ids":{}}'}))
            project = load_mpx(path)
            before = copy.deepcopy(project.worksheets)
            self.assertFalse(restore_owned(project))
            self.assertEqual(project.worksheets, before)
            with self.assertRaises(io.UnsupportedFormatError):
                save_owned(project, path)

    def test_numeric_only_validation_reserved_missing_and_invalid_identities(self):
        for sheet in (Worksheet('Date', [Column('T', 'date', [-1])]),
                      Worksheet('Constant', constants=[Column('K', 'text', ['unsupported'])]),
                      Worksheet('Sentinel', [Column('X', values=[io.MISSING_SENTINEL])])):
            with self.subTest(sheet=sheet.name), self.assertRaises((ValueError, io.UnsupportedFormatError)):
                create_project([sheet])
        with self.assertRaises(io.FormatError):
            create_project([])
        with self.assertRaises(ValueError):
            create_project([worksheet()], True)
        project = create_project([worksheet()])
        project.worksheet_ids[0] = 'bad'
        with scratch() as folder, self.assertRaises(ValueError):
            save_owned(project, Path(folder) / 'ids.mpx')

    def test_member_cell_and_metadata_limits_before_file_replacement(self):
        project = create_project([worksheet()])
        with scratch() as folder:
            path = Path(folder) / 'valid.mpx'
            save_owned(project, path)
            before = path.read_bytes()
            with patch.object(io, 'MAX_CELLS', 1), self.assertRaises(io.FormatError):
                save_owned(project, path)
            with patch.object(io, 'MAX_MEMBER_BYTES', 20), self.assertRaises(io.FormatError):
                save_owned(project, path)
            project.active_worksheet.metadata['bad'] = float('nan')
            with self.assertRaises(io.FormatError):
                save_owned(project, path)
            self.assertEqual(path.read_bytes(), before)

    def test_retained_payload_and_native_metadata_edits_rejected(self):
        with scratch() as folder:
            path = Path(folder) / 'owned.mpx'
            save_owned(create_project([worksheet()]), path)
            project = load_mpx(path)
            project.retained_members['/extra'] = b''
            with self.assertRaises(io.UnsupportedFormatError):
                save_owned(project, path)
            project = load_mpx(path)
            project.metadata['Worksheets']['Items'][0]['Unknown'] = 'retain me'
            with self.assertRaises(io.UnsupportedFormatError):
                save_owned(project, path)
            project = load_mpx(path)
            project.metadata['Unknown'] = True
            with self.assertRaises(io.UnsupportedFormatError):
                save_owned(project, path)

    def test_unknown_zip_member_comment_never_grants_structural_ownership(self):
        with scratch() as folder:
            path = Path(folder) / 'zip-comments.mpx'
            save_owned(create_project([worksheet()]), path)
            with zipfile.ZipFile(path) as archive:
                entries = [(info, archive.read(info)) for info in archive.infolist()]
            with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for info, payload in entries:
                    if info.filename == '/project_metadata_20.json':
                        info.comment = b'unknown information'
                    archive.writestr(info, payload)
            project = load_mpx(path)
            self.assertFalse(getattr(project, 'statcraft_owned', False))
            self.assertIn('import', project.active_worksheet.metadata)


if __name__ == '__main__':
    unittest.main()
