"""Independent fixed-factor general linear models with effect or reference coding.

Adjusted tests compare the full model against each term-deleted model; sequential
tests add whole terms in order. Uses NumPy SVD and SciPy distributions.
"""
import itertools
import math
import numpy as np
from scipy import stats
from .value_order import ordered_values
from .regression import multiple_regression

DEFAULTS=dict(confidence=.95,ss_type='adjusted',coding='effect',standardize='none',
    graphs='none',method=True,factor_information=True,anova=True,model_summary=True,
    coefficients=True,diagnostics='unusual')


def settings(options=None):
    if options is None:return dict(DEFAULTS)
    if not isinstance(options,dict) or set(options)!=set(DEFAULTS):raise ValueError('Unsupported general linear model options.')
    o=dict(options)
    if type(o['confidence']) not in (int,float) or not math.isfinite(o['confidence']) or not 0<o['confidence']<1:raise ValueError('Confidence level must be between 0 and 100 percent.')
    for k,choices in dict(ss_type=('adjusted','sequential'),coding=('effect','reference'),standardize=('none','center','scale','standardize'),graphs=('none','four','fitted','order','normal','histogram'),diagnostics=('none','unusual','all')).items():
        if o[k] not in choices:raise ValueError('Unsupported model option: '+k)
    for k in ('method','factor_information','anova','model_summary','coefficients'):
        if type(o[k]) is not bool:raise ValueError('Invalid result display setting.')
    return o


def validate_terms(terms, count):
    if not isinstance(terms,list) or not 1<=len(terms)<=64:raise ValueError('Select 1–64 model terms.')
    seen=set()
    for term in terms:
        if not isinstance(term,list) or not 1<=len(term)<=3 or any(type(i) is not int or not 0<=i<count for i in term) or term!=sorted(set(term)):
            raise ValueError('Model terms must contain distinct predictors in order, up to three-way interactions.')
        key=tuple(term)
        if key in seen:raise ValueError('A model term was selected more than once.')
        seen.add(key)
    for term in seen:
        for size in range(1,len(term)):
            if any(sub not in seen for sub in itertools.combinations(term,size)):raise ValueError('Keep all lower-order terms for a hierarchical model.')
    return terms


def fit(worksheet,response_index,factor_indices,covariate_indices,terms=None,options=None):
    o=settings(options);factors=list(factor_indices);covariates=list(covariate_indices);indices=factors+covariates
    if not 1<=len(indices)<=8 or len(set(indices+[response_index]))!=len(indices)+1 or any(type(i) is not int or not 0<=i<len(worksheet.columns) for i in indices+[response_index]):
        raise ValueError('Choose a separate numeric response and 1–8 distinct predictors.')
    response=worksheet.columns[response_index];columns=[worksheet.columns[i] for i in indices]
    if response.kind!='number' or any(worksheet.columns[i].kind!='number' for i in covariates) or any(worksheet.columns[i].kind not in ('number','text') for i in factors):
        raise ValueError('Use numeric response/covariates and numeric or text factors.')
    terms=validate_terms(terms if terms is not None else [[i] for i in range(len(indices))],len(indices))
    active=sorted({i for term in terms for i in term})
    if active!=list(range(len(indices))):raise ValueError('Include each selected predictor in the model, or remove it from the predictor selection.')
    length=max(len(c.values) for c in columns+[response])
    if length>20000:raise ValueError('This model supports at most 20,000 input rows.')
    rows=[r for r in range(length) if all(r<len(c.values) and c.values[r] is not None for c in columns+[response])]
    if not rows:raise ValueError('No complete model observations remain.')
    basis=[];blocks=[];test_blocks=[];factor_info=[];coding_info=[]
    for position,c in enumerate(columns):
        values=[c.values[r] for r in rows]
        if position<len(factors):
            levels=ordered_values(c,values)
            if not 2<=len(levels)<=32:raise ValueError('Each factor needs 2–32 observed levels after missing-row omission: '+c.name)
            reference=levels[-1];block=[]
            for level in levels[:-1]:block.append(np.asarray([1. if v==level else (-1. if o['coding']=='effect' and v==reference else 0.) for v in values]))
            blocks.append(block);test_blocks.append([np.asarray([1. if v==level else -1. if v==reference else 0. for v in values]) for level in levels[:-1]]);basis.append([c.name+'['+str(level)+']' for level in levels[:-1]])
            factor_info.append(dict(factor=c.name,type='Fixed',levels=len(levels),values=', '.join(map(str,levels)),reference=str(reference)))
            coding_info.append(dict(name=c.name,kind='factor',levels=levels,shift=0.,scale=1.))
        else:
            v=np.asarray(values,dtype=float);mean=math.fsum(v/len(v));sd=float(np.std(v,ddof=1)) if len(v)>1 else 0.
            shift=mean if o['standardize'] in ('center','standardize') else 0.;scale=sd if o['standardize'] in ('scale','standardize') else 1.
            if scale<=0 or not math.isfinite(scale):raise ValueError('A covariate has no supported variation: '+c.name)
            transformed=(v-shift)/scale
            if not np.all(np.isfinite(transformed)):raise ValueError('Covariate arithmetic exceeds the supported range.')
            blocks.append([transformed]);test_blocks.append([transformed]);basis.append([c.name]);coding_info.append(dict(name=c.name,kind='covariate',shift=shift,scale=scale))
    widths=[math.prod(len(blocks[i]) for i in term) for term in terms];width=sum(widths)
    if width>120 or len(rows)*(width+1)>2000000:raise ValueError('Model expansion exceeds 120 coefficients or two million design cells.')
    encoded=[];test_encoded=[];labels=[];groups=[];offset=0
    with np.errstate(over='raise',invalid='raise'):
        try:
            for term,size in zip(terms,widths):
                group=list(range(offset,offset+size));groups.append(group);offset+=size
                for combination in itertools.product(*(range(len(blocks[i])) for i in term)):
                    product=np.ones(len(rows));test_product=np.ones(len(rows));names=[]
                    for i,j in zip(term,combination):product*=blocks[i][j];test_product*=test_blocks[i][j];names.append(basis[i][j])
                    encoded.append(product.tolist());test_encoded.append(test_product);labels.append('*'.join(names))
        except FloatingPointError as exc:raise ValueError('Interaction arithmetic exceeds the supported range.') from exc
    y=[response.values[r] for r in rows];result=multiple_regression(encoded,y,o['confidence'],labels)
    design=np.asarray(test_encoded).T;centers=np.asarray([math.fsum(design[:,j]/len(rows)) for j in range(width)])
    centered_design=design-centers;scales=np.max(np.abs(centered_design),axis=0)
    z=np.column_stack([np.ones(len(rows)),centered_design/scales])
    u,s,vh=np.linalg.svd(z,full_matrices=False);h=np.minimum(1.,np.maximum(0.,np.sum(u*u,axis=1)))
    centered=np.asarray(y)-math.fsum(np.asarray(y)/len(y));unit=float(max(abs(centered)));target=centered/unit
    def sse(keep):
        a=z[:,[0]+[i+1 for i in keep]];b=np.linalg.lstsq(a,target,rcond=None)[0];residual=target-a@b
        return float(residual@residual)*unit*unit
    anova=[];allcols=list(range(width));before=result['ss_total'];prefix=[]
    for term,group in zip(terms,groups):
        reduced=sse([i for i in allcols if i not in group]);adj=max(0.,reduced-result['ss_error'])
        prefix+=group;after=sse(prefix);seq=max(0.,before-after);before=after
        ss=adj if o['ss_type']=='adjusted' else seq;ms=ss/len(group)
        f=None if result['status']=='exact_fit' else ms/result['ms_error']
        anova.append(dict(source='*'.join(columns[i].name for i in term),df=len(group),seq_ss=seq,adj_ss=adj,ms=ms,f=f,p_value=None if f is None else float(stats.f.sf(f,len(group),result['df_error']))))
    diagnostics=[]
    for i,row in enumerate(rows):
        residual=result['residuals'][i];denom=1-float(h[i]);se=result['residual_stdev']*math.sqrt(max(0.,denom))
        standardized=residual/se if se>0 and denom>1e-14 else None
        cook=(standardized**2*float(h[i])/((width+1)*denom)) if standardized is not None and denom>1e-14 else None
        flags=('R' if standardized is not None and abs(standardized)>2 else '')+('X' if h[i]>3*(width+1)/len(rows) else '')
        diagnostics.append(dict(row=row+1,response=y[i],fit=result['fitted'][i],residual=residual,standardized_residual=standardized,leverage=float(h[i]),cooks_distance=cook,flag=flags))
    result.update(analysis='general_linear_model',method='General Linear Model — fixed factors, ordinary least squares',response_name=response.name,
        row_indices=rows,missing=length-len(rows),factor_information=factor_info,coding_information=coding_info,terms=[list(t) for t in terms],term_names=[a['source'] for a in anova],anova_terms=anova,diagnostics=diagnostics,
        options=o,plot_residuals=o['graphs']!='none',ss_type=o['ss_type'],coding=o['coding'],standardize=o['standardize'],
        assumptions='Independent errors with constant variance and normal error distribution for tests and intervals. Complete-case omission preserves source row identities. Adjusted tests use sum-to-zero factor contrasts, with covariates at the selected coded origin; coefficient coding may differ. Fixed factors only; rank-deficient and saturated models are rejected.')
    return result


def residual_panels(result):
    mode=result['options']['graphs'];residuals=result['residuals'];rows=[r+1 for r in result['row_indices']]
    scatter=lambda title,x,y,xlabel,ylabel,**extra:dict(kind='scatter',title=title,x=x,y=y,xlabel=xlabel,ylabel=ylabel,**extra)
    ordered=sorted(residuals);scores=stats.norm.ppf((np.arange(len(ordered))+.625)/(len(ordered)+.25)).tolist()
    counts,edges=np.histogram(residuals,bins=min(10,max(3,math.ceil(math.sqrt(len(residuals))))))
    normal=scatter('Normal Probability Plot',ordered,scores,'Residual','Percent')
    normal['kind']='normal_probability';normal['reference_x']=[ordered[0],ordered[-1]]
    spread=float(np.std(residuals,ddof=1));normal['reference_y']=[v/spread for v in normal['reference_x']] if spread>0 else [-1.,1.]
    panels=dict(normal=normal,
        fitted=scatter('Versus Fits',result['fitted'],residuals,'Fitted Value','Residual',zero=True,row_indices=rows),
        order=scatter('Versus Order',rows,residuals,'Observation Order','Residual',zero=True,row_indices=rows),
        histogram=dict(kind='histogram',title='Histogram',edges=edges.tolist(),counts=counts.tolist(),curves=[],specs=[],xlabel='Residual',ylabel='Frequency'))
    panels['order']['kind']='line';panels['order']['lines']=[]
    return [panels[k] for k in ('normal','fitted','histogram','order')] if mode=='four' else ([panels[mode]] if mode!='none' else [])
