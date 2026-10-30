"""Original typed-column and numeric-collection MPX writer. Native reopening is unverified.

Only this writer's byte-canonical data-only profile permits structural editing.
The sidecar marker alone never grants ownership to an imported native project.
Zero timestamps, empty history/version_history and blank sheets are deliberate
StatCraft choices; the neutral envelope follows the audited 20200604 corpus.
"""
import copy
import io as memory_io
import json
from pathlib import Path
import re
from uuid import UUID, uuid4
import zipfile
from . import io, session
from .model import Worksheet, Column, serial_to_datetime
from .mpx_append import append_numeric

MEMBER = '/statcraft/workbook.json'
SCHEMA = 'statcraft-owned-mpx-v1'
TEXT_SCHEMA = 'statcraft-owned-mpx-v2'
DATE_SCHEMA = 'statcraft-owned-mpx-v3'
COLLECTION_SCHEMA = 'statcraft-owned-mpx-v4'
MODEL_TYPES = ('ClassificationTree RegressionTree ClassificationTreeNet RegressionTreeNet '
               'ClassificationRandomForest RegressionRandomForest ClassificationMultiModel RegressionMultiModel '
               'BinaryLogisticRegression MultipleRegression PoissonRegression VariabilityFactorial '
               'BinaryFractionalFactorial FractionalFactorial SplitPlotFactorial GeneralFactorial '
               'BinaryGeneralFactorial ResponseSurfaceRegression BinaryResponseSurfaceRegression '
               'ForecastWithBestArima MarsRegression').split()
NOTICE = 'Original StatCraft data-only MPX profile; reopening in native StatCraft is unverified.'


def _json(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         separators=(',', ':')).encode('utf-8')
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        raise io.FormatError('Project metadata must contain finite JSON data.') from exc
    if len(raw) > io.MAX_MEMBER_BYTES:
        raise io.FormatError('Project member exceeds the size limit.')
    return raw


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise io.FormatError('Invalid original project identity.')
    return value


def _validate(project):
    if not getattr(project, 'statcraft_owned', False):
        raise io.UnsupportedFormatError('Structural writing requires a StatCraft-created project.')
    if not project.worksheets or len(project.worksheets) > (io.MAX_MEMBERS - 5) // 2:
        raise io.FormatError('Invalid worksheet count.')
    project.active_worksheet
    if len(project.worksheet_ids) != len(project.worksheets) or len(project.worksheet_uris) != len(project.worksheets):
        raise io.FormatError('Worksheet identity counts do not match.')
    if len(set(project.worksheet_ids)) != len(project.worksheets) or len(set(project.worksheet_uris)) != len(project.worksheets):
        raise io.FormatError('Duplicate worksheet identities.')
    _uuid(project.metadata['Id'])
    cells = 0
    for sheet, identifier, uri in zip(project.worksheets, project.worksheet_ids, project.worksheet_uris):
        _uuid(identifier)
        if not isinstance(uri, str) or not re.fullmatch(r'/sheets/\d+/sheet', uri):
            raise io.FormatError('Invalid worksheet URI.')
        if not isinstance(sheet, Worksheet):
            raise io.FormatError('Invalid worksheet.')
        sheet.validate()
        for constant in sheet.constants:
            if constant.kind != 'number':
                raise io.UnsupportedFormatError('Only numeric scalar constants are supported in new MPX projects.')
        for matrix in sheet.matrices:
            if matrix.rows < 1:
                raise io.UnsupportedFormatError('New MPX matrices require positive dimensions.')
        for collection in sheet.constants + sheet.matrices:
            if any(value is not None and value == io.MISSING_SENTINEL for value in collection.values):
                raise io.UnsupportedFormatError('This numeric value is reserved for native missing cells.')
        for column in sheet.columns:
            if column.kind=='date':
                for value in column.values:
                    if value is not None:serial_to_datetime(value)
        cells += sum(len(c.values) for c in sheet.columns + sheet.constants) + sum(len(m.values) for m in sheet.matrices)
        if cells > io.MAX_CELLS or len(sheet.columns) > io.MAX_CELLS:
            raise io.FormatError('Project exceeds the cell limit.')
    if project.history:
        raise io.UnsupportedFormatError('Original native command history cannot be written.')


def _collection(value, index, prefix, uri, identities):
    """Original bounded scalar/matrix profile; zero placeholders use our sidecar."""
    temporary = {'Data': {'Columns': []}}
    plain = Column(value.name, 'number', [0 if v is None else v for v in value.values])
    append_numeric(temporary, [plain], index, len(plain.values), identities, uri + ':' + prefix)
    encoded = temporary['Data']['Columns'][0]
    # Reuse our neutral numeric formatting policy (six decimal places), not the
    # sample-specific native format's precision and extrema. Namespaces have
    # separate K/M slots but globally distinct persistent object UUIDs.
    encoded['ClassId'] = 435 if prefix == 'K' else 436
    variable = 2 if prefix == 'K' else 4
    encoded['VarId']['Variable'] = variable
    wrapper = encoded['WorksheetVarBody']
    wrapper['VarData']['VariableType'] = variable
    wrapper['VarData']['VarDataBody']['ColCt'] = 1 if prefix == 'K' else value.columns
    wrapper['FormatType'] = 0
    wrapper['GeneralVarFmt'] = {'ClassId': 0, 'Hidden': False}
    return encoded


def _sheet(sheet, identifier, uri, identities):
    data = {'ClassId': 1, 'Type_DEP': 1263685463, 'IOtype_DEP': 1,
            'Name': sheet.name, 'PrivateTitle': sheet.name,
            'HTMLOptions': {'ClassId': 0, 'Title': ''},
            'WorksheetViewData': {'ClassId': 0, 'PrintGrid': True, 'PrintColNames': True,
                'PrintColLabels': True, 'PrintRowLabels': True, 'UseAllColumns': True,
                'DirectionIsHorizontal': True, 'ActiveRow': 1, 'ActiveCol': 1,
                'TopVisibleRow': 1, 'LeftmostVisibleCol': 1, 'StandardColumnWidthInt': 8,
                'PrintJustification': 2, 'DataStyle': 0, 'LabelStyle': 2,
                'DataPointSize': 10, 'LabelPointSize': 10, 'StandardColumnWidthDouble': 8,
                'DataFaceName': 'Arial', 'LabelFaceName': 'Arial', 'MissingValue': '*'},
            'UseHiddenColumns': True, 'Columns': [], 'Constants': [], 'Matrices': [],
            'HasDOE': False, 'DDE': [], 'Unknown_DEP': [],
            'FormulaManager': {'ClassId': 0, 'UpdateAutomatically': True, 'RecalcNeeded': False,
                'StatusUpdateNeeded': False, 'SetNodes': [], 'Class_Version': [1, 1]}}
    for key in ('RegressionModel', 'ResponseSurfaceModel', 'FactorialModel', 'BinaryLogisticModel',
                'PoissonRegressionModel', 'GeneralLinearModel', 'StabilityStudyModel'):
        data[key] = []
    data['ConditionalFormatManager'] = {'ClassId': 0, 'Formats': [], 'Class_Version': [1, 1]}
    data['CellPropertiesManager'] = {'ClassId': 0, 'CellStyles': [], 'UserDefinedCellStyle': [],
                                     'CellComments': [], 'Class_Version': [1, 1]}
    data.update(DefinitiveScreeningModel=[], REMLModel=[], WorksheetId_DEP=identifier, Class_Version=[1, 7])
    document = {'Data': data, 'Word_DEP': {}, 'MaxRows_DEP': sheet.row_count,
                'MaxColumns_DEP': len(sheet.columns), 'MaxConstants_DEP': len(sheet.constants), 'MaxMatrices_DEP': len(sheet.matrices),
                'CreationDate': 0, 'LastSavedDate': 0, 'Version': 20200604, 'SaveAsVersion': 20200604,
                'Creator': 'StatCraft', 'Date': '', 'Comment': '', 'OSVersion_DEP': 0,
                'CodePage_DEP': 0, 'CreatedDate': 0, 'SavedDate': 0, 'Class_Version': [2]}
    plain = [Column(c.name, 'number', [0 if v is None else v for v in c.values] if c.kind=='date' else list(c.values) if c.kind=='number' else [None]*len(c.values)) for c in sheet.columns]
    append_numeric(document, plain, 0, sheet.row_count, identities, uri)
    for column,encoded in zip(sheet.columns,data['Columns']):
        if column.kind=='date':
            encoded['WorksheetVarBody']['Format']={'Key':2,'Value':{
                'ClassId':19,'AutoFormat':False,'MissingValueLabel':'*','PrevMissingValueLabel':'*',
                'StrToStr':[],'DataToStr':[],'TimeFmt14_DEP':[0,0,0],
                'TimeFmt17_DEP':[68260171,0,3801135,0],
                'TimeFmt':[1091113027,1025,0,0,3801135],'Class_Version':[2,1]}}
        if column.kind!='text':continue
        strings=['' if value is None else value for value in column.values]
        try:width=max([1]+[len(value.encode('utf-16-le'))//2 for value in strings])
        except UnicodeError as exc:raise io.FormatError('Text cells must contain valid Unicode.') from exc
        wrapper=encoded['WorksheetVarBody']
        wrapper['Format']={'Key':3,'Value':{'ClassId':18,'AutoFormat':True,
            'MissingValueLabel':'','PrevMissingValueLabel':'','StrToStr':[],'DataToStr':[],
            'CharCt':width,'Class_Version':[1,1]}}
        wrapper['VarData']['Data']=2
        wrapper['VarData']['VarDataBody']={'ClassId':447,'CellCt':len(strings),'ColCt':1,'CharCt':width,
            'HasNumericData':False,'HasTextData':True,'TextData':strings}
    data['Constants'] = [_collection(value, i, 'K', uri, identities) for i, value in enumerate(sheet.constants)]
    data['Matrices'] = [_collection(value, i, 'M', uri, identities) for i, value in enumerate(sheet.matrices)]
    return document


def _members(project, records, identities):
    _validate(project)
    items = [{'Id': identifier, 'Name': sheet.name, 'Uri': uri, 'Comments': '',
              'Creator': 'StatCraft', 'Date': '',
              'ExtraInformation': {'column_widths': {'default': 8}, 'hidden_columns': []}}
             for sheet, identifier, uri in zip(project.worksheets, project.worksheet_ids, project.worksheet_uris)]
    metadata = {'Version': 20200604, 'Worksheets': {'Items': items, 'ExtraInformation': {
        'current_worksheet': project.worksheet_ids[project.active_index],
        'worksheet_ordering': list(project.worksheet_ids)}},
        'Commands': {'Items': [], 'ExtraInformation': {'layout': {'groups': [], 'active': 0}},
                     'PendingUpdates': [], 'Class_Version': [2]},
        'History': [], 'Creator': 'StatCraft', 'Date': '', 'Comments': '',
        'Id': project.metadata['Id'],
        'NextSheet': max(int(uri.split('/')[2]) for uri in project.worksheet_uris) + 1,
        'ExtraInformation': {'version_history': []},
        'Models': {'Items': [{'Type': kind, 'Uri': '', 'NextTreeId': 1, 'Items': [],
                             'Class_Version': [2]} for kind in MODEL_TYPES]},
        'Reports': {'Items': []}, 'Class_Version': [3]}
    members = {'/': b'', '/project_metadata_20.json': _json(metadata), '/sheets/': b''}
    previous=getattr(project,'_owned_schema',None)
    kinds={c.kind for sheet in project.worksheets for c in sheet.columns}
    schema=COLLECTION_SCHEMA if previous==COLLECTION_SCHEMA or any(s.constants or s.matrices for s in project.worksheets) else DATE_SCHEMA if previous==DATE_SCHEMA or 'date' in kinds else TEXT_SCHEMA if previous==TEXT_SCHEMA or 'text' in kinds else SCHEMA
    sheets = []
    for sheet, identifier, uri in zip(project.worksheets, project.worksheet_ids, project.worksheet_uris):
        members[uri.rsplit('/', 1)[0] + '/'] = b''
        members[uri + '.json'] = _json(_sheet(sheet, identifier, uri, identities))
        sidecar={'id': identifier, 'metadata': sheet.metadata,'columns': [c.metadata for c in sheet.columns]}
        if schema in (TEXT_SCHEMA,DATE_SCHEMA,COLLECTION_SCHEMA):
            sidecar['missing_text']={str(i):[row for row,value in enumerate(c.values) if value is None]
                for i,c in enumerate(sheet.columns) if c.kind=='text' and any(v is None for v in c.values)}
        if schema in (DATE_SCHEMA,COLLECTION_SCHEMA):
            sidecar['missing_dates']={str(i):[row for row,value in enumerate(c.values) if value is None]
                for i,c in enumerate(sheet.columns) if c.kind=='date' and any(v is None for v in c.values)}
        if schema==COLLECTION_SCHEMA:
            for key, values in (('constants',sheet.constants),('matrices',sheet.matrices)):
                sidecar[key]=[value.metadata for value in values]
                sidecar['missing_'+key]={str(i):[row for row,value in enumerate(entry.values) if value is None]
                    for i,entry in enumerate(values) if any(value is None for value in entry.values)}
        sheets.append(sidecar)
    # Keep only current C/K/M identities. Deleted variables are not latent members.
    keys = {uri + ':' + str(i) for sheet, uri in zip(project.worksheets, project.worksheet_uris)
            for i in range(len(sheet.columns))}
    keys.update(uri+':'+prefix+':'+str(i) for sheet,uri in zip(project.worksheets,project.worksheet_uris)
        for prefix,values in (('K',sheet.constants),('M',sheet.matrices)) for i in range(len(values)))
    identities = {key: value for key, value in identities.items() if key in keys}
    if getattr(project,'workspace',None) is not None:
        from . import workspace_state
        members[workspace_state.MEMBER]=workspace_state.encode(project.workspace)
    if getattr(project,'native_views',None):
        from . import native_output_state
        members[native_output_state.MEMBER]=native_output_state.encode(project.native_views)
    members[MEMBER] = _json({'schema': schema, 'sheets': sheets, 'column_ids': identities})
    members[session.MEMBER] = session.validate(records, project.worksheet_ids)
    if len(members) > io.MAX_MEMBERS or sum(map(len, members.values())) > io.MAX_TOTAL_BYTES:
        raise io.FormatError('Project archive exceeds its limits.')
    return members, metadata, identities


def create_project(worksheets, active_index=0):
    """Construct fresh native identities; caller data and metadata are copied."""
    from .mpx import Project
    worksheets = list(worksheets)
    project = Project('Untitled', copy.deepcopy(worksheets), active_index,
                      metadata={'Id': str(uuid4())},
                      worksheet_ids=[str(uuid4()) for _ in worksheets],
                      worksheet_uris=['/sheets/' + str(i) + '/sheet' for i in range(len(worksheets))])
    project.statcraft_owned = True
    members, metadata, identities = _members(project, [], {})
    project.metadata = metadata
    project._owned_metadata = copy.deepcopy(metadata)
    project._appended_ids = identities
    project.warnings = [NOTICE]
    return project


def save_owned(project, path, session_records=None):
    """Atomically save only an original, data-only StatCraft project profile."""
    from .mpx import _atomic_bytes
    path = Path(path)
    if path.suffix.lower() != '.mpx':
        raise io.FormatError('MPX projects require the .mpx extension.')
    _validate(project)
    if project.metadata != getattr(project, '_owned_metadata', None):
        raise io.UnsupportedFormatError('Direct native project metadata edits cannot be rewritten.')
    if project._original_members and project.retained_members != project._original_members:
        raise io.UnsupportedFormatError('Retained project members were modified outside the worksheet editor.')
    if project.archive_comment:
        raise io.UnsupportedFormatError('Unknown project archive comments cannot be rewritten.')
    if any(info.extra or info.comment for info in project.retained_zip_infos):
        raise io.UnsupportedFormatError('Unknown ZIP member metadata cannot be rewritten.')
    records = project.session_records if session_records is None else session_records
    members, metadata, identities = _members(project, records, copy.deepcopy(project._appended_ids))
    if set(project.metadata) != set(metadata) or any(project.metadata[key] != metadata[key]
            for key in metadata if key not in ('Worksheets', 'NextSheet')):
        raise io.UnsupportedFormatError('Unknown or edited native project metadata cannot be rewritten.')
    stream = memory_io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    if len(stream.getvalue()) > io.MAX_TOTAL_BYTES:
        raise io.FormatError('Project archive exceeds the size limit.')
    _atomic_bytes(path, stream.getvalue())
    project.metadata = metadata
    project._owned_metadata = copy.deepcopy(metadata)
    project._appended_ids = identities
    project.session_records = copy.deepcopy(records)
    project._owned_schema=io._json(members[MEMBER])['schema']
    return [NOTICE]


def restore_owned(project):
    """Restore original metadata only after every decoded payload matches."""
    if (MEMBER not in project.retained_members or project.archive_comment or
            any(info.extra or info.comment for info in project.retained_zip_infos)):
        return False
    try:
        document = io._json(project.retained_members[MEMBER])
        if not isinstance(document, dict) or set(document) != {'schema', 'sheets', 'column_ids'} or document['schema'] not in (SCHEMA,TEXT_SCHEMA,DATE_SCHEMA,COLLECTION_SCHEMA):
            return False
        sheets = document['sheets']
        if not isinstance(sheets, list) or len(sheets) != len(project.worksheets):
            return False
        identities = document['column_ids']
        if not isinstance(identities, dict):
            return False
        for key, value in identities.items():
            if not isinstance(key, str):
                return False
            _uuid(value)
        if len(set(identities.values())) != len(identities):
            return False
        candidate = copy.deepcopy(project)
        candidate.statcraft_owned = True
        candidate._owned_schema=document['schema']
        for sheet, identifier, sidecar in zip(candidate.worksheets, candidate.worksheet_ids, sheets):
            keys={'id','metadata','columns'}|({'missing_text'} if document['schema'] in (TEXT_SCHEMA,DATE_SCHEMA,COLLECTION_SCHEMA) else set())|({'missing_dates'} if document['schema'] in (DATE_SCHEMA,COLLECTION_SCHEMA) else set())
            if document['schema']==COLLECTION_SCHEMA:keys|={'constants','matrices','missing_constants','missing_matrices'}
            if not isinstance(sidecar, dict) or set(sidecar) != keys or sidecar['id'] != identifier:
                return False
            if not isinstance(sidecar['metadata'], dict) or not isinstance(sidecar['columns'], list) or len(sidecar['columns']) != len(sheet.columns):
                return False
            sheet.metadata = copy.deepcopy(sidecar['metadata'])
            uri = candidate.worksheet_uris[candidate.worksheet_ids.index(identifier)]
            originals = candidate._original_sheets[uri + '.json']['Data']['Columns']
            for column, metadata, original in zip(sheet.columns, sidecar['columns'], originals):
                if not isinstance(metadata, dict):
                    return False
                column.metadata = copy.deepcopy(metadata)
                column.name = original['WorksheetVarBody']['Name']
            maps=[('missing_text','text','',sheet.columns)] if document['schema'] in (TEXT_SCHEMA,DATE_SCHEMA,COLLECTION_SCHEMA) else []
            if document['schema'] in (DATE_SCHEMA,COLLECTION_SCHEMA):maps.append(('missing_dates','date',0,sheet.columns))
            if document['schema']==COLLECTION_SCHEMA:
                for key,native,values in (('constants','Constants',sheet.constants),('matrices','Matrices',sheet.matrices)):
                    metadata=sidecar[key]
                    originals=candidate._original_sheets[uri+'.json']['Data'][native]
                    if not isinstance(metadata,list) or len(metadata)!=len(values):return False
                    for entry,meta,original in zip(values,metadata,originals):
                        if not isinstance(meta,dict):return False
                        entry.metadata=copy.deepcopy(meta)
                        entry.name=original['WorksheetVarBody']['Name']
                    maps.append(('missing_'+key,'number',0,values))
            for key,kind,placeholder,values in maps:
                missing=sidecar[key]
                if not isinstance(missing,dict):return False
                for position,rows in missing.items():
                    if not isinstance(position,str) or not position.isascii() or not position.isdigit() or str(int(position))!=position:return False
                    index=int(position)
                    if index>=len(values) or getattr(values[index],'kind','number')!=kind or not isinstance(rows,list):return False
                    if any(type(row) is not int or row<0 or row>=len(values[index].values) for row in rows) or len(set(rows))!=len(rows):return False
                    for row in rows:
                        if values[index].values[row]!=placeholder:return False
                        values[index].values[row]=None
        expected, metadata, cache = _members(candidate, candidate.session_records, copy.deepcopy(identities))
        if expected != project.retained_members:
            return False
        project.worksheets = candidate.worksheets
        project.statcraft_owned = True
        project._owned_metadata = copy.deepcopy(metadata)
        project._appended_ids = cache
        project._owned_schema=document['schema']
        project.warnings = [NOTICE]
        return True
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        return False
