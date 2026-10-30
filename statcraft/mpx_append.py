"""Original bounded numeric-column encoding for the observed MPX schema.

Native application reopening is unverified. No existing object IDs are changed.
Evidence and limits: outputs/statcraft-mpx-append-column-evidence.md.
"""
from uuid import uuid4
from . import io
from .model import finite_number


def validate_plain(document):
    """Reject structural changes with unimplemented native worksheet state."""
    data=document['Data']
    for key in ('DDE','Unknown_DEP','RegressionModel','ResponseSurfaceModel','FactorialModel','BinaryLogisticModel',
                'PoissonRegressionModel','GeneralLinearModel','StabilityStudyModel','DefinitiveScreeningModel','REMLModel'):
        if key in data and data[key]!=[]:
            raise io.UnsupportedFormatError('Structural edits to worksheets with native '+key+' content are unverified.')
    if data.get('HasDOE',False) is not False:
        raise io.UnsupportedFormatError('Structural edits to worksheets with native DOE metadata are unverified.')
    managers={'FormulaManager':{'ClassId':0,'UpdateAutomatically':True,'RecalcNeeded':False,'StatusUpdateNeeded':False,'SetNodes':[],'Class_Version':[1,1]},
              'ConditionalFormatManager':{'ClassId':0,'Formats':[],'Class_Version':[1,1]},
              'CellPropertiesManager':{'ClassId':0,'CellStyles':[],'UserDefinedCellStyle':[],'CellComments':[],'Class_Version':[1,1]}}
    for key,empty in managers.items():
        if key in data and data[key]!=empty:
            raise io.UnsupportedFormatError('Structural edits with nonempty or unknown native '+key+' state are unverified.')


def append_numeric(document,columns,original_count,row_extent,identity_cache,worksheet_uri):
    """Append independent numeric columns inside the supported row extent."""
    validate_plain(document)
    data=document['Data']
    existing=data['Columns']; used=set(); ids=set()
    for entry in existing:
        if isinstance(entry.get('Id'),str):ids.add(entry['Id'])
        var=entry.get('VarId')
        if var is not None:
            value=var.get('VarId') if isinstance(var,dict) else None
            if type(value) is not int or value<1 or value in used:
                raise io.UnsupportedFormatError('Native variable identities are outside the verified append schema.')
            used.add(value)
    next_id=max(used|{original_count})+1
    for offset,column in enumerate(columns):
        if column.kind!='number' or column.metadata:
            raise io.UnsupportedFormatError('Only independent numeric columns can currently be appended to an MPX copy.')
        if len(column.values)>row_extent:
            raise io.UnsupportedFormatError('Appended MPX columns must stay within the original worksheet row extent.')
        values=[]
        for value in column.values:
            if value is not None and finite_number(value)==io.MISSING_SENTINEL:
                raise io.UnsupportedFormatError('This numeric value is reserved for native missing cells.')
            values.append(io.MISSING_SENTINEL if value is None else finite_number(value))
        observed=[v for v in values if v!=io.MISSING_SENTINEL]
        cache_key=worksheet_uri+':'+str(original_count+offset)
        identifier=identity_cache.get(cache_key,str(uuid4()))
        while identifier in ids:identifier=str(uuid4())
        identity_cache[cache_key]=identifier
        ids.add(identifier)
        existing.append({'ClassId':434,'DefaultBody':False,
            'VarId':{'ClassId':440,'Variable':3,'Copy':False,'Attached':True,'VarId':next_id},
            'WorksheetVarBody':{'ClassId':437,'Name':column.name,'Desc':'',
                'Format':{'Key':1,'Value':{'ClassId':17,'AutoFormat':True,'MissingValueLabel':'*',
                    'PrevMissingValueLabel':'*','StrToStr':[],'DataToStr':[],'Numeric':0,
                    'NumDecPlaces':6,'PlacesToLeft':1,'MinValue':min(observed,default=0.),
                    'MaxValue':max(observed,default=0.),'Subtype':0,'ShowFullPrecision':False,'Class_Version':[3,1]}},
                'VarData':{'ClassId':439,'VariableType':3,'Data':1,'VarDataBody':{
                    'ClassId':447,'CellCt':len(values),'ColCt':1,'CharCt':0,
                    'HasNumericData':True,'NumericData':values,'HasTextData':False},'Locked':False,'Class_Version':[2]},
                'Ordering':{'ClassId':0,'DefinedSortOrder':0,'NumericOrder':[],'TextOrder':[]},
                'FormatType':3,'GeneralVarFmt':{'ClassId':0,'Hidden':False,'AutoWidening':True,
                    'FormatSet':False,'DisplayedWidthDouble':8.,'DisplayedWidthInt':8,'WidthSetIndividually':False},
                'Available':True,'Compressed':False,'HasChanged':False,'FormatDirty':False,'Class_Version':[2]},
            'WorksheetVar':None,'Id':identifier,'ReadOnly':False,'OriginalVarId':'','Imported':False,'Class_Version':[1,5]})
        next_id+=1
    if 'MaxColumns_DEP' in document:
        value=io._count(document['MaxColumns_DEP'],'MaxColumns_DEP')
        document['MaxColumns_DEP']=max(value,len(existing))
