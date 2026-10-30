"""Original graph appearance overlays stored separately from retained native MPX objects."""
import copy
import json
from . import io

MEMBER='/statcraft/native-output-views.json'
SCHEMA='statcraft-native-output-views-v1'


def validate(state,entries=None):
    from .native_graph_view import validate_views
    if not isinstance(state,dict) or len(state)>100:raise io.FormatError('Native graph appearance supports at most 100 output groups.')
    known={e.get('entry_id'):e for e in entries} if entries is not None else None
    result={}
    for key,item in state.items():
        if not isinstance(key,str) or not 1<=len(key)<=160 or not isinstance(item,dict) or set(item)!={'views','graph_index'}:
            raise io.FormatError('Invalid native graph appearance entry.')
        count=None
        if known is not None:
            entry=known.get(key)
            if entry is None or entry.get('result',{}).get('analysis')!='native_saved_output':raise io.FormatError('Native graph appearance references an unavailable saved output.')
            count=len(entry['result'].get('graphs',[]))
        index=item['graph_index']
        if type(index) is not int or not 0<=index<100 or count is not None and index>=count:raise io.FormatError('Invalid selected native graph.')
        try:views=validate_views(item['views'],count)
        except (ValueError,TypeError,KeyError) as exc:raise io.FormatError('Invalid native graph appearance: '+str(exc)) from exc
        result[key]={'views':views,'graph_index':index}
    return result


def encode(state):
    raw=json.dumps({'schema':SCHEMA,'entries':validate(state)},ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
    if len(raw)>2*1024*1024:raise io.FormatError('Native graph appearance exceeds 2 MiB.')
    return raw


def decode(raw):
    if len(raw)>2*1024*1024:raise io.FormatError('Native graph appearance exceeds 2 MiB.')
    doc=io._json(raw)
    if not isinstance(doc,dict) or set(doc)!={'schema','entries'} or doc['schema']!=SCHEMA:raise io.FormatError('Unsupported native graph appearance schema.')
    return validate(doc['entries'])


def capture(entries):
    state={}
    for entry in entries:
        if entry.get('result',{}).get('analysis')!='native_saved_output' or not entry.get('result',{}).get('graphs'):continue
        views=entry.get('native_graph_views',{});index=entry.get('_native_graph_index',0)
        if views or index:state[entry['entry_id']]={'views':copy.deepcopy(views),'graph_index':index}
    return validate(state,entries)


def apply(entries,state):
    state=validate(state,entries)
    for entry in entries:
        item=state.get(entry.get('entry_id'))
        if item is not None:
            entry['native_graph_views']=copy.deepcopy(item['views']);entry['_native_graph_index']=item['graph_index']
