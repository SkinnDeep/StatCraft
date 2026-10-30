"""Validated per-gallery appearance overlays, separate from native MPX objects."""
import copy
import math
import re
from .graph_presentation import DEFAULTS, validate_presentation
from .graph_styles import validate_styles
from .spatial_view import DEFAULT_VIEW, view_state

_COLOR=re.compile(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\Z')


def validate_view(value):
    if not isinstance(value,dict) or set(value)-{'presentation','styles','palette','camera'}:
        raise ValueError('Unsupported saved-native graph appearance fields.')
    result={}
    if 'presentation' in value:result['presentation']=validate_presentation(value['presentation'])
    if 'styles' in value:result['styles']=validate_styles(value['styles'])
    if 'palette' in value:
        colors=value['palette']
        if colors is not None:
            if not isinstance(colors,list) or not 2<=len(colors)<=32 or any(not isinstance(c,str) or not _COLOR.fullmatch(c) for c in colors):
                raise ValueError('A graph palette requires 2–32 #RRGGBB or #RRGGBBAA colors.')
            colors=[c.lower() for c in colors]
        result['palette']=colors
    if 'camera' in value:
        camera=value['camera']
        if not isinstance(camera, dict):
            raise ValueError('A saved surface camera requires azimuth, elevation and zoom.')
        for k in ('azimuth', 'elevation', 'zoom'):
            if k not in camera:
                raise ValueError('A saved surface camera requires azimuth, elevation and zoom.')
        for k in camera:
            if k not in ('azimuth', 'elevation', 'zoom', 'pan_x', 'pan_y'):
                raise ValueError('A saved surface camera requires azimuth, elevation and zoom.')
        for k,(lo,hi) in {'azimuth':(-180,180),'elevation':(-89,89),'zoom':(.4,2.5)}.items():
            v=camera[k]
            if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Saved surface '+k+' is outside the supported range.')
        clean = {'azimuth': camera['azimuth'], 'elevation': camera['elevation'], 'zoom': camera['zoom']}
        if 'pan_x' in camera and type(camera['pan_x']) in (int, float) and math.isfinite(camera['pan_x']):
            clean['pan_x'] = float(camera['pan_x'])
        if 'pan_y' in camera and type(camera['pan_y']) in (int, float) and math.isfinite(camera['pan_y']):
            clean['pan_y'] = float(camera['pan_y'])
        result['camera']=view_state(**clean)
    return result


def validate_views(values,graph_count=None):
    if not isinstance(values,dict) or len(values)>100:raise ValueError('Saved-native graph appearance must be a map of at most 100 views.')
    result={}
    for key,value in values.items():
        if not isinstance(key,str) or not key.isascii() or not key.isdigit() or str(int(key))!=key or not 0<=int(key)<100 or graph_count is not None and int(key)>=graph_count:
            raise ValueError('Saved-native graph appearance references an unavailable graph.')
        result[key]=validate_view(value)
    return result


def graph_index(entry,index=None):
    graphs=entry.get('result',{}).get('graphs',[])
    chosen=entry.get('_native_graph_index',0) if index is None else index
    if type(chosen) is not int or not 0<=chosen<len(graphs):return 0
    return chosen


def presentation(entry,index=None):
    graphs=entry.get('result',{}).get('graphs',[]);index=graph_index(entry,index)
    graph=graphs[index] if graphs else {};panels=graph.get('panels',[]);first=panels[0] if panels else {}
    text=lambda x:str(x or '')[:145]
    defaults=dict(DEFAULTS,title=text(graph.get('title',entry.get('title','Saved graph'))),subtitle=text(graph.get('subtitle','')),footnote=text(graph.get('footnote','')),
        x_label=text(first.get('y_label' if first.get('horizontal') else 'x_label','')),
        y_label=text(first.get('x_label' if first.get('horizontal') else 'y_label','')))
    for k in ('title','subtitle','footnote'):defaults[k+'_enabled']=bool(defaults[k])
    views=validate_views(entry.get('native_graph_views',{}),len(graphs));saved=views.get(str(index),{}).get('presentation',{})
    defaults.update(saved)
    return validate_presentation(defaults)


def resolve_view(entry,index=None):
    graphs=entry.get('result',{}).get('graphs',[]);index=graph_index(entry,index)
    views=validate_views(entry.get('native_graph_views',{}),len(graphs));view=views.get(str(index),{})
    return {'presentation':presentation(entry,index),'styles':copy.deepcopy(view.get('styles',{})),
            'palette':copy.deepcopy(view.get('palette')),'camera':copy.deepcopy(view.get('camera',DEFAULT_VIEW))}


def cartesian(entry,index=None):
    graphs=entry.get('result',{}).get('graphs',[]);index=graph_index(entry,index)
    panels=graphs[index].get('panels',[]) if graphs else []
    return bool(panels) and all(p.get('kind') not in ('surface','probability') for p in panels)
