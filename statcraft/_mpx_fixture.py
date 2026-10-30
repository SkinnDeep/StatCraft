"""Original synthetic fixture for packaged MPX verification; no vendor dataset."""
import json
import copy
import zipfile
import struct


def write_fixture(path):
    ids = ['11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222']
    metadata = {'Version': 20200604, 'Worksheets': {
        'Items': [{'Id': ids[i], 'Name': name, 'Uri': f'/sheets/{i}/sheet'} for i, name in enumerate(['First', 'Second'])],
        'ExtraInformation': {'current_worksheet': ids[0], 'worksheet_ordering': ids[::-1]}},
        'History': ['DESCRIBE C1.'], 'Commands': {'Items': []}}
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('/', b'')
        archive.writestr('/project_metadata_20.json', json.dumps(metadata))
        for i in range(2):
            variable = {'ClassId': 434, 'WorksheetVar': None, 'Compressed': False,
                'WorksheetVarBody': {'ClassId': 437, 'Name': 'Measurements',
                'Format': {'Key': 1}, 'VarData': {'ClassId': 439, 'VariableType': 3, 'Data': 1,
                'VarDataBody': {'ClassId': 447, 'CellCt': 3, 'ColCt': 1, 'CharCt': 0,
                    'HasNumericData': True, 'HasTextData': False, 'NumericData': [1+i, 2+i, 3+i]}}}}
            sheet = {'Version': 20200604, 'Data': {'Columns': [variable], 'Constants': [], 'Matrices': []}}
            archive.writestr(f'/sheets/{i}/sheet.json', json.dumps(sheet))
        archive.writestr('/unknown/retained.bin', b'Original synthetic opaque payload\x00\xff')


def write_subgroup_fixture(path):
    """Original synthetic subgroup container; never a supported product writer."""
    write_fixture(path)
    with zipfile.ZipFile(path) as archive:
        members = [(info, archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(path, 'w') as archive:
        for info, raw in members:
            if info.filename == '/sheets/0/sheet.json':
                sheet = json.loads(raw)
                column = sheet['Data']['Columns'][0]
                body = column['WorksheetVarBody']['VarData']['VarDataBody']
                body.update(CellCt=6, NumericData=[1,3,4,6,7,9])
                identifier = copy.deepcopy(column)
                identifier['WorksheetVarBody']['Name'] = 'Subgroup'
                identifier['WorksheetVarBody']['VarData']['VarDataBody']['NumericData'] = [1,1,2,2,3,3]
                sheet['Data']['Columns'].append(identifier)
                raw = json.dumps(sheet).encode('utf8')
            archive.writestr(info, raw)


def write_blob_fixture(path, values=None):
    """Synthetic little-endian double member with an internal numeric URI."""
    write_fixture(path)
    values=[1,2,3] if values is None else list(values)
    with zipfile.ZipFile(path) as archive:
        members=[(info,archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(path,'w') as archive:
        for info,raw in members:
            if info.filename=='/sheets/0/sheet.json':
                sheet=json.loads(raw)
                body=sheet['Data']['Columns'][0]['WorksheetVarBody']['VarData']['VarDataBody']
                body['CellCt']=len(values); body['NumericData']='/blobs/blob1?size='+str(len(values))
                raw=json.dumps(sheet).encode('utf-8')
            archive.writestr(info,raw)
        archive.writestr('/blobs/blob1',struct.pack('<'+str(len(values))+'d',*values))


def write_scatter_fixture(path):
    """Synthetic response, grouping ID and predictor for saved scatter checks."""
    write_subgroup_fixture(path)
    with zipfile.ZipFile(path) as archive: members=[(info,archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(path,'w') as archive:
        for info,raw in members:
            if info.filename=='/sheets/0/sheet.json':
                sheet=json.loads(raw); column=copy.deepcopy(sheet['Data']['Columns'][0])
                column['WorksheetVarBody']['Name']='Predictor'
                column['WorksheetVarBody']['VarData']['VarDataBody']['NumericData']=[1,2,1,2,1,2]
                sheet['Data']['Columns'].append(column); raw=json.dumps(sheet).encode('utf-8')
            archive.writestr(info,raw)


def write_factorial_fixture(path):
    """Original replicated two-factor data for conservative MPX analysis tests."""
    write_fixture(path)
    a=[-1,1,-1,1]*2; b=[-1,-1,1,1]*2
    y=[10+2*x-3*z+1.5*x*z+(1 if i<4 else -1) for i,(x,z) in enumerate(zip(a,b))]
    with zipfile.ZipFile(path) as archive: members=[(info,archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(path,'w') as archive:
        for info,raw in members:
            if info.filename=='/sheets/0/sheet.json':
                sheet=json.loads(raw); template=sheet['Data']['Columns'][0]; columns=[]
                for name,values in [('A',a),('B',b),('Response',y)]:
                    column=copy.deepcopy(template); column['WorksheetVarBody']['Name']=name
                    column['WorksheetVarBody']['VarData']['VarDataBody'].update(CellCt=8,NumericData=values)
                    columns.append(column)
                sheet['Data']['Columns']=columns; raw=json.dumps(sheet).encode('utf-8')
            archive.writestr(info,raw)


def write_fractional_fixture(path):
    """Synthetic 16-run response and four fractional factor columns."""
    write_fixture(path)
    a=[-1,1]*8; b=[-1,-1,1,1]*4; c=[-1]*4+[1]*4
    c=c*2; d=[x*y*z for x,y,z in zip(a,b,c)]
    response=[10+2*x-3*y+1.5*z+.5*t+(1 if i<8 else -1) for i,(x,y,z,t) in enumerate(zip(a,b,c,d))]
    with zipfile.ZipFile(path) as archive:members=[(info,archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(path,'w') as archive:
        for info,raw in members:
            if info.filename=='/sheets/0/sheet.json':
                sheet=json.loads(raw); template=sheet['Data']['Columns'][0]; columns=[]
                for name,values in zip(['A','B','C','D','Response'],[a,b,c,d,response]):
                    column=copy.deepcopy(template); column['WorksheetVarBody']['Name']=name
                    column['WorksheetVarBody']['VarData']['VarDataBody'].update(CellCt=16,NumericData=values); columns.append(column)
                sheet['Data']['Columns']=columns; raw=json.dumps(sheet).encode('utf-8')
            archive.writestr(info,raw)
