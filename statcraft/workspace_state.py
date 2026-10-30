"""Bounded inert StatCraft output workspace, separate from native MPX objects."""
import copy
import json
from . import io

MEMBER='/statcraft/workspace.json'
REPORT='__report_pad__'
VIEWS=('Graph','Report','Text export','ReportPad')


def empty():
    return dict(open_ids=[],active=None,closed_ids=[],views={},report_pad='')


def validate(state):
    if not isinstance(state,dict) or set(state)!=set(empty()):raise io.FormatError('Invalid output workspace fields.')
    for field in ('open_ids','closed_ids'):
        items=state[field]
        if not isinstance(items,list) or len(items)>101 or any(not isinstance(x,str) or not 1<=len(x)<=160 for x in items) or len(set(items))!=len(items):raise io.FormatError('Invalid output tab identities.')
    if state['active'] is not None and state['active'] not in state['open_ids']:raise io.FormatError('The active output tab must be open.')
    if not isinstance(state['report_pad'],str) or len(state['report_pad'])>1000000:raise io.FormatError('ReportPad supports up to 1,000,000 characters.')
    if not isinstance(state['views'],dict) or len(state['views'])>101:raise io.FormatError('Invalid output view state.')
    for key,value in state['views'].items():
        if not isinstance(key,str) or len(key)>160 or not isinstance(value,dict) or set(value)!={'view','zoom','scroll','editor'}:raise io.FormatError('Invalid output view properties.')
        if value['view'] not in VIEWS or type(value['editor']) is not bool:raise io.FormatError('Invalid selected output view.')
        for field in ('zoom','scroll'):
            values=value[field]
            if not isinstance(values,dict) or set(values)-set(VIEWS):raise io.FormatError('Invalid output viewport state.')
            for item in values.values():
                if field=='zoom':
                    if type(item) is not int or not 10<=item<=500:raise io.FormatError('Output zoom must be 10 to 500 percent.')
                elif not isinstance(item,list) or len(item)!=2 or any(type(v) is not int or not 0<=v<=10000000 for v in item):raise io.FormatError('Invalid output scroll position.')
    raw=json.dumps(state,ensure_ascii=False,allow_nan=False)
    if len(raw.encode('utf-8'))>2*1024*1024:raise io.FormatError('Output workspace exceeds 2 MiB.')
    return copy.deepcopy(state)


def encode(state):
    return json.dumps({'schema':'statcraft-output-workspace','version':1,'workspace':validate(state)},ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')


def decode(raw):
    if len(raw)>2*1024*1024:raise io.FormatError('Output workspace exceeds 2 MiB.')
    doc=io._json(raw)
    if not isinstance(doc,dict) or set(doc)!={'schema','version','workspace'} or doc['schema']!='statcraft-output-workspace' or type(doc['version']) is not int or doc['version']!=1:raise io.FormatError('Unsupported output workspace.')
    return validate(doc['workspace'])


def prune(state,known,strict=True):
    state=validate(state) if strict else copy.deepcopy(state);known=set(known)|{REPORT}
    for field in ('open_ids','closed_ids'):state[field]=[key for key in state[field] if key in known]
    state['views']={key:value for key,value in state['views'].items() if key in known}
    if state['active'] not in state['open_ids']:state['active']=state['open_ids'][-1] if state['open_ids'] else None
    return state
