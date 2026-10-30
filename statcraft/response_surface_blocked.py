"""Coded response-surface OLS with an explicit fixed block factor."""
import itertools
import math
import numpy as np
from scipy import stats
from .model import finite_number
from .doe import _coding
from .glm import settings
from .regression import multiple_regression
from .value_order import ordered_values


def fit(worksheet,response_index,factor_indices,coding=None,terms=None,options=None,block_index=None):
    from .response_surface import full_terms,validate_terms,default_coding
    o=settings(options);indices=list(factor_indices);k=len(indices)
    selected=[response_index,block_index]+indices
    if not 2<=k<=10 or any(type(i) is not int or not 0<=i<len(worksheet.columns) for i in selected) or len(set(selected))!=len(selected):
        raise ValueError('Choose separate response, block and 2–10 continuous factor columns.')
    cols=[worksheet.columns[i] for i in indices];response=worksheet.columns[response_index];block=worksheet.columns[block_index]
    if response.kind!='number' or any(c.kind!='number' for c in cols) or block.kind not in ('number','text'):
        raise ValueError('Use numeric response and continuous factors, with a numeric or text block column.')
    coding=default_coding(worksheet,indices) if coding is None else coding
    if not isinstance(coding,list) or len(coding)!=k or any(not isinstance(c,dict) or set(c)!={'low','high'} for c in coding):raise ValueError('Enter low/high coding for each continuous factor.')
    codes=[_coding(c.name,v['low'],v['high']) for c,v in zip(cols,coding)]
    terms=validate_terms(full_terms(k) if terms is None else terms,k)
    length=max(len(c.values) for c in cols+[response,block])
    if length>20000:raise ValueError('Response surface fitting supports at most 20,000 input rows.')
    rows=[r for r in range(length) if all(r<len(c.values) and c.values[r] is not None for c in cols+[response,block])]
    if not rows:raise ValueError('No complete response/factor/block rows remain.')
    levels=ordered_values(block,[block.values[r] for r in rows])
    if not 2<=len(levels)<=32:raise ValueError('The block column needs 2–32 observed levels after complete-row omission.')
    reference=levels[-1];groups=[];x=[];names=[]
    for level in levels[:-1]:
        x.append([1. if block.values[r]==level else -1. if o['coding']=='effect' and block.values[r]==reference else 0. for r in rows])
        names.append(block.name+'['+str(level)+']')
    groups.append((block.name,list(range(len(x)))))
    encoded=[[(c.values[r]-code['center'])/code['half_range'] for r in rows] for c,code in zip(cols,codes)]
    with np.errstate(over='raise',invalid='raise'):
        try:
            for term in terms:
                v=np.ones(len(rows))
                for i in term:v*=encoded[i]
                label='*'.join(cols[i].name for i in term)
                groups.append((label,[len(x)]));x.append(v.tolist());names.append(label)
        except FloatingPointError as exc:raise ValueError('Polynomial terms exceed finite numeric range.') from exc
    if len(rows)*(len(x)+1)>2000000:raise ValueError('The blocked model exceeds two million design cells.')
    y=[response.values[r] for r in rows];result=multiple_regression(x,y,o['confidence'],names)
    design=np.asarray(x).T;n=len(rows);means=np.asarray([math.fsum(design[:,i]/n) for i in range(len(x))])
    centered=design-means;scales=np.max(np.abs(centered),axis=0);z=np.column_stack([np.ones(n),centered/scales])
    u,_,_=np.linalg.svd(z,full_matrices=False);leverage=np.minimum(1.,np.maximum(0.,np.sum(u*u,axis=1)))
    dy=np.asarray(y)-math.fsum(np.asarray(y)/n);unit=float(max(abs(dy)));target=dy/unit
    def sse(keep):
        a=z[:,[0]+[i+1 for i in keep]];res=target-a@np.linalg.lstsq(a,target,rcond=None)[0]
        return float(res@res)*unit*unit
    allcols=list(range(len(x)));prefix=[];before=result['ss_total'];anova=[]
    for label,group in groups:
        adj=max(0.,sse([i for i in allcols if i not in group])-result['ss_error'])
        prefix+=group;after=sse(prefix);seq=max(0.,before-after);before=after
        df=len(group);ss=adj if o['ss_type']=='adjusted' else seq;ms=ss/df
        f=ms/result['ms_error'] if result['status']!='exact_fit' else None
        anova.append(dict(source=label,df=df,seq_ss=seq,adj_ss=adj,ms=ms,f=f,p_value=None if f is None else float(stats.f.sf(f,df,result['df_error']))))
    repeats={}
    for i,r in enumerate(rows):repeats.setdefault((block.values[r],)+tuple(c.values[r] for c in cols),[]).append(y[i])
    pure=math.fsum(math.fsum((v-math.fsum(g)/len(g))**2 for v in g) for g in repeats.values())
    df_pure=n-len(repeats);df_lof=len(repeats)-len(x)-1;lof=max(0.,result['ss_error']-pure)
    f_lof=(lof/df_lof)/(pure/df_pure) if df_lof>0 and df_pure>0 and pure>0 and result['status']!='exact_fit' else None
    diagnostics=[]
    for i,r in enumerate(rows):
        h=float(leverage[i]);denom=1-h;se=result['residual_stdev']*math.sqrt(max(0.,denom));residual=result['residuals'][i];std=residual/se if se>0 and denom>1e-14 else None
        diagnostics.append(dict(row=r+1,response=y[i],fit=result['fitted'][i],residual=residual,standardized_residual=std,leverage=h,cooks_distance=std**2*h/((len(x)+1)*denom) if std is not None else None,flag=('R' if std is not None and abs(std)>2 else '')+('X' if h>3*(len(x)+1)/n else '')))
    result.update(analysis='response_surface',method='Response Surface Regression — coded OLS with fixed blocks',response_name=response.name,options=o,coding=o['coding'],plot_residuals=o['graphs']!='none',row_indices=rows,missing=length-n,
        coding_information=[dict(name=block.name,kind='factor',levels=levels,shift=0.,scale=1.)]+codes,
        surface_coding_information=codes,surface_terms=[list(t) for t in terms],block_index=block_index,block_levels=levels,
        factor_information=[dict(factor=block.name,type='Fixed block',levels=len(levels),values=', '.join(map(str,levels)),reference=str(reference))],
        terms=[[0]]+[[i+1 for i in t] for t in terms],anova_terms=anova,diagnostics=diagnostics,
        lack_of_fit=dict(df=df_lof,ss=lof,ms=lof/df_lof if df_lof>0 else None,f=f_lof,p_value=None if f_lof is None else float(stats.f.sf(f_lof,df_lof,df_pure))),
        pure_error=dict(df=df_pure,ss=pure,ms=pure/df_pure if df_pure>0 else None),
        assumptions='Continuous factors use (setting − midpoint) / half range. Blocks are an explicit fixed categorical main effect. Complete response/factor/block rows are omitted together. Pure error groups identical settings within each block; blocks are never silently pooled. Independent normal, constant-variance errors are assumed for inference.')
    return result
