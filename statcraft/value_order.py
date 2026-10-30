"""Independent categorical ordering for supported tables and graph snapshots."""
from .model import finite_number


def validate_order(mode,values=()):
    if mode not in ('alphabetical','occurrence','custom'):
        raise ValueError('Choose alphabetical, worksheet occurrence or custom value order.')
    if not isinstance(values,(list,tuple)) or len(values)>10000 or any(not isinstance(v,str) for v in values):
        raise ValueError('Enter text categories, one per line (at most 10000).')
    unique=list(dict.fromkeys(v for v in values if v.strip()))
    if mode=='custom' and not unique:raise ValueError('Enter at least one category for a custom order.')
    return {'mode':mode,'values':unique if mode=='custom' else []}


def ordered_values(column,values):
    """Order observed values only; unlisted custom levels follow alphabetically.

    Alphabetical uses deterministic Unicode casefold ordering, not native locale
    collation. Occurrence uses the entire source column, before case omission.
    Numeric levels sort by numeric magnitude and ignore legacy text-order metadata.
    """
    observed=list(dict.fromkeys(values))
    if column.kind!='text':return sorted(observed,key=lambda v:finite_number(float(v)))
    settings=column.metadata.get('value_order',{'mode':'alphabetical','values':[]})
    if not isinstance(settings,dict):raise ValueError('Invalid column value-order settings.')
    settings=validate_order(settings.get('mode'),settings.get('values',[]))
    alphabetical=lambda v:(v.casefold(),v)
    mode=settings['mode']
    if mode=='alphabetical':return sorted(observed,key=alphabetical)
    sequence=column.values if mode=='occurrence' else settings['values']
    rank={}
    for value in sequence:
        if value is not None and value not in rank:rank[value]=len(rank)
    return sorted(observed,key=lambda v:(0,rank[v]) if v in rank else (1,alphabetical(v)))
