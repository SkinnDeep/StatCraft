"""Original bounded numeric resize checks for observed MPX worksheet storage."""
from . import io
import re


def prepare_numeric_resize(document,wrapper,count):
    from .mpx_append import validate_plain
    validate_plain(document)
    var=wrapper['VarData'];body=var['VarDataBody'];fmt=wrapper['Format']
    if var.get('Locked',False) is not False:
        raise io.UnsupportedFormatError('Resizing locked native variables is unsupported.')
    if fmt.get('Key')!=1 or var.get('Data')!=1 or body.get('ColCt')!=1 or body.get('HasNumericData') is not True or body.get('HasTextData') is not False:
        raise io.UnsupportedFormatError('Only typed numeric columns support MPX length changes.')
    order=wrapper.get('Ordering')
    if order is not None and order!={'ClassId':0,'DefinedSortOrder':0,'NumericOrder':[],'TextOrder':[]}:
        raise io.UnsupportedFormatError('Resizing columns with native ordering metadata is unverified.')
    value=fmt.get('Value',{})
    if not isinstance(value,dict) or value.get('DataToStr',[])!=[] or value.get('StrToStr',[])!=[]:
        raise io.UnsupportedFormatError('Resizing columns with native value-label conversions is unverified.')
    if count>io.MAX_CELLS:
        raise io.FormatError('Numeric column exceeds the cell limit.')
    body['CellCt']=count


def update_numeric_bounds(wrapper,values):
    """Expand observed display-range fields; do not assume exact extrema caches."""
    settings=wrapper['Format'].get('Value')
    if isinstance(settings,dict):
        observed=[value for value in values if value!=io.MISSING_SENTINEL]
        if observed:
            from .model import finite_number
            if 'MinValue' in settings:settings['MinValue']=min(finite_number(settings['MinValue']),min(observed))
            if 'MaxValue' in settings:settings['MaxValue']=max(finite_number(settings['MaxValue']),max(observed))


def numeric_blob_uses(members,member):
    """Count canonical member references across retained JSON, including outputs."""
    count=0
    reference=re.compile(re.escape(member)+r'(?=$|[^A-Za-z0-9_/.-])')
    for name,raw in members.items():
        if not name.endswith('.json'):continue
        try:document=io._json(raw)
        except io.FormatError as exc:
            raise io.UnsupportedFormatError('Numeric blob references in unknown JSON content cannot be verified.') from exc
        pending=[document]
        while pending:
            value=pending.pop()
            if isinstance(value,dict):pending.extend(value.values());pending.extend(value.keys())
            elif isinstance(value,list):pending.extend(value)
            elif isinstance(value,str):
                count+=len(reference.findall(value))
    return count
