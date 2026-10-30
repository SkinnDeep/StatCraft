"""Data readouts for painted graph elements; no model or worksheet mutation."""
import math


def number(value):
    return format(value, '.8g') if isinstance(value,(int,float)) and not isinstance(value,bool) else str(value)


def point_info(x,y,xlabel='X',ylabel='Y',series='',row=None,z=None,zlabel='Z'):
    pairs=[]
    if series:pairs.append(('Series',series))
    if type(row) is int and row>0:pairs.append(('Row',row))
    pairs.extend(((xlabel or 'X',x),(ylabel or 'Y',y)))
    if z is not None:pairs.append((zlabel or 'Z',z))
    return {'kind':'point','x':x,'y':y,'z':z,'row':row,'series':series,
            'text':'\n'.join(str(k)+': '+number(v) for k,v in pairs)}


def histogram_info(left,right,value,measure='Frequency',series='',source=None,rows=None,last=False):
    pairs=[]
    if series:pairs.append(('Series',series))
    pairs.extend((('Lower boundary',left),('Upper boundary',right),(measure or 'Frequency',value)))
    info={'kind':'histogram','interval':(left,right),'value':value,'measure':measure or 'Frequency','series':series}
    if isinstance(source,(list,tuple)):
        included=[i for i,v in enumerate(source) if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and left<=v and (v<=right if last else v<right)]
        info['count']=len(included);info['n']=len(source)
        if (measure or '').casefold()!='frequency':pairs.append(('Frequency',len(included)))
        pairs.append(('N',len(source)))
        if rows and len(rows)==len(source):
            ids=[rows[i] for i in included if type(rows[i]) is int and rows[i]>0]
            info['rows']=ids
            if ids:pairs.append(('Rows',', '.join(map(str,ids[:12]))+(' …' if len(ids)>12 else '')))
    info['text']='\n'.join(str(k)+': '+number(v) for k,v in pairs)
    return info


def summary_info(kind,pairs,**fields):
    return dict(fields,kind=kind,text='\n'.join(str(k)+': '+number(v) for k,v in pairs))


def surface_cell_info(vertices,labels=('X','Y','Z')):
    ranges=[(min(v[i] for v in vertices),max(v[i] for v in vertices)) for i in range(3)]
    pairs=[('Surface','Saved mesh cell')]+[(label,number(lo)+' to '+number(hi)) for label,(lo,hi) in zip(labels,ranges)]
    return summary_info('surface',pairs,ranges=ranges)
