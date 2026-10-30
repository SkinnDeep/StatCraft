"""Original Scheffe-by-process OLS with additive covariates and fixed blocks.

Components use raw proportions. Process polynomial terms are fully crossed
with every selected mixture term. The component sum supplies a constant
response direction, so no separate intercept is added.
"""
import copy,json,math
from itertools import combinations
import numpy as np
from scipy import stats
from .model import Worksheet
from .value_order import ordered_values
from .mixture_analysis import _number,_confidence,_bounds,_point,_terms

SOURCES=[
 'https://www.itl.nist.gov/div898/handbook/pri/section5/pri545.htm',
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/how-to/mixtures/analyze-mixture-design/perform-the-analysis/specify-the-model-terms/',
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/doe/how-to/factorial/analyze-factorial-design/methods-and-formulas/model-information/',
]
DEFAULT_OPTIONS={'confidence':.95,'show_graphs':True,'title':'','bounds':None,'process_order':1,'process_coding':None,'covariate_coding':None}


def _selectors(ws,indices,minimum,maximum,label,kinds=('number',)):
    if not isinstance(indices,(list,tuple)) or not minimum<=len(indices)<=maximum:raise ValueError(f'Select {minimum} to {maximum} {label} columns.')
    if any(type(i) is not int or not 0<=i<len(ws.columns) for i in indices) or len(set(indices))!=len(indices):raise ValueError('Choose distinct existing '+label+' columns.')
    if any(ws.columns[i].kind not in kinds for i in indices):raise ValueError('Unsupported data type in '+label+' columns.')
    return list(indices)


def settings(options=None):
    if options is not None and (not isinstance(options,dict) or set(options)-set(DEFAULT_OPTIONS)):raise ValueError('Unsupported mixture-process model options.')
    o=copy.deepcopy(DEFAULT_OPTIONS);o.update(copy.deepcopy(options or {}));o['confidence']=_confidence(o['confidence'])
    if type(o['show_graphs']) is not bool or not isinstance(o['title'],str):raise ValueError('Choose a valid title and graph display option.')
    if type(o['process_order']) is not int or o['process_order'] not in (1,2):raise ValueError('Process order must be 1 or 2.')
    return o


def _code(value,item,label):
    center=item['low']/2+item['high']/2;scale=item['high']/2-item['low']/2
    if not math.isfinite(scale) or scale<=0:raise ValueError(label+' coding range is below supported precision.')
    difference=value-center
    result=difference/scale if math.isfinite(difference) else value/scale-center/scale
    if not math.isfinite(result):raise ValueError(label+' exceeds supported coded range.')
    return result


def _coding(raw,values,names,label):
    if raw is not None and (not isinstance(raw,(list,tuple)) or len(raw)!=len(names)):raise ValueError('Specify one low/high coding pair per '+label+'.')
    result=[]
    for index,name in enumerate(names):
        item={'low':min(row[index] for row in values),'high':max(row[index] for row in values)} if raw is None else raw[index]
        if not isinstance(item,dict) or set(item)!={'low','high'}:raise ValueError('Coding pairs require low and high.')
        low=_number(item['low'],name+' low');high=_number(item['high'],name+' high')
        if low>=high:raise ValueError(name+' must have a nonzero coding range; constant '+label+' cannot be estimated.')
        pair={'low':low,'high':high};_code(low,pair,name);_code(high,pair,name);result.append(pair)
    return result


def _model_terms(component_names,model,process_names,order,covariate_names,levels):
    mixture=_terms(component_names,model);powers=[[]]+[[i] for i in range(len(process_names))]
    if order==2:powers += [[i,i] for i in range(len(process_names))]+[list(pair) for pair in combinations(range(len(process_names)),2)]
    terms=[]
    for power in powers:
        suffix='*'.join(process_names[i] for i in power)
        for term in mixture:terms.append({'name':term['name']+('*'+suffix if suffix else ''),'components':term['components'],'process_positions':power})
    terms += [{'name':'Covariate: '+name,'covariate_position':i} for i,name in enumerate(covariate_names)]
    terms += [{'name':'Block: '+str(level),'block_level':level} for level in levels[:-1]]
    if len(terms)>128:raise ValueError('This tensor model exceeds 128 terms. Reduce mixture/process order or selected variables.')
    return terms


def _matrix(points,processes,covariates,blocks,terms):
    rows=[]
    for point,z,c,block in zip(points,processes,covariates,blocks):
        row=[]
        for term in terms:
            if 'covariate_position' in term:value=c[term['covariate_position']]
            elif 'block_level' in term:value=float(block==term['block_level'])
            else:value=math.prod(point[i] for i in term['components'])*math.prod(z[i] for i in term['process_positions'])
            row.append(value)
        rows.append(row)
    matrix=np.asarray(rows,dtype=float)
    if not np.all(np.isfinite(matrix)):raise ValueError('Model basis exceeds supported finite range.')
    return matrix


def fit(worksheet,response_index,component_indices,process_indices=None,block_index=None,covariate_indices=None,model='quadratic',total=1.,options=None):
    if not isinstance(worksheet,Worksheet):raise ValueError('Select a worksheet for mixture-process analysis.')
    components=_selectors(worksheet,component_indices,2,8,'component');processes=_selectors(worksheet,[] if process_indices is None else process_indices,0,3,'process')
    covariates=_selectors(worksheet,[] if covariate_indices is None else covariate_indices,0,4,'covariate')
    response=_selectors(worksheet,[response_index],1,1,'response')[0]
    block=[] if block_index is None else _selectors(worksheet,[block_index],1,1,'block',('number','text'))
    indices=components+processes+covariates+block+[response]
    if len(set(indices))!=len(indices):raise ValueError('Response, components, process variables, covariates and block must use separate columns.')
    if not processes and not covariates and not block:raise ValueError('Select a process variable, covariate or block, or use Analyze Mixture Design.')
    if model not in ('linear','quadratic','special_cubic') or (model=='special_cubic' and len(components)<3):raise ValueError('Choose a valid mixture model order for the selected components.')
    for i in indices:worksheet.columns[i].validate()
    total=_number(total,'Mixture total',True);opts=settings(options)
    names=lambda refs:[worksheet.columns[i].name or 'C'+str(i+1) for i in refs]
    cn=names(components);pn=names(processes);vn=names(covariates)
    if len(set(cn+pn+vn))!=len(cn+pn+vn):raise ValueError('Component, process and covariate names must be distinct.')
    bounds,bounds_source,warnings=_bounds(worksheet,components,total,opts['bounds'])
    extent=max(len(worksheet.columns[i].values) for i in indices)
    if extent>4096:raise ValueError('Mixture-process fitting supports at most 4096 worksheet rows.')
    points=[];raw_points=[];raw_process=[];raw_cov=[];blocks=[];ys=[];used=[];missing=[]
    for row in range(extent):
        if any(row>=len(worksheet.columns[i].values) or worksheet.columns[i].values[row] is None or (isinstance(worksheet.columns[i].values[row],str) and not worksheet.columns[i].values[row].strip()) for i in indices):missing.append(row+1);continue
        amounts=[_number(worksheet.columns[i].values[row],'Component') for i in components]
        points.append(_point(amounts,total,bounds,'Worksheet row '+str(row+1)));raw_points.append(amounts)
        raw_process.append([_number(worksheet.columns[i].values[row],'Process value') for i in processes]);raw_cov.append([_number(worksheet.columns[i].values[row],'Covariate') for i in covariates])
        blocks.append(worksheet.columns[block[0]].values[row] if block else None);ys.append(_number(worksheet.columns[response].values[row],'Response'));used.append(row+1)
    if not used:raise ValueError('No complete selected model rows remain.')
    levels=ordered_values(worksheet.columns[block[0]],blocks) if block else []
    if block and not 2<=len(levels)<=16:raise ValueError('A fixed block needs 2 to 16 observed levels after missing-row omission.')
    pc=_coding(opts['process_coding'],raw_process,pn,'process variable');vc=_coding(opts['covariate_coding'],raw_cov,vn,'covariate')
    opts['process_coding']=copy.deepcopy(pc);opts['covariate_coding']=copy.deepcopy(vc);opts['bounds']=copy.deepcopy(bounds)
    z=[[_code(value,code,name) for value,code,name in zip(row,pc,pn)] for row in raw_process]
    c=[[_code(value,code,name) for value,code,name in zip(row,vc,vn)] for row in raw_cov]
    terms=_model_terms(cn,model,pn,opts['process_order'],vn,levels);n=len(ys);p=len(terms)
    if n<=p:raise ValueError(f'This model has {p} terms; provide more than {p} complete observations for residual degrees of freedom.')
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            matrix=_matrix(points,z,c,blocks,terms);scales=np.max(np.abs(matrix),axis=0)
            if np.any(scales==0):raise ValueError('The model is rank deficient: a selected term has no observed variation.')
            scaled=matrix/scales;u,s,vh=np.linalg.svd(scaled,full_matrices=False);tolerance=np.finfo(float).eps*max(n,p)*s[0]
            if s[-1]<=tolerance:raise ValueError('The selected mixture/process/covariate/block model is rank deficient or confounded; no terms were silently removed.')
            condition=float(s[0]/s[-1])
            if condition>1e12:raise ValueError('The model is too poorly conditioned for reliable estimation.')
            offset=math.fsum(value/n for value in ys);y=np.asarray(ys);centered=y-offset;scale_y=float(np.max(np.abs(centered))) or 1.;target=centered/scale_y
            gamma=vh.T@((u.T@target)/s);centered_coefs=gamma*scale_y/scales;estimates=centered_coefs.copy();estimates[:len(components)]+=offset
            fitted=offset+scale_y*(scaled@gamma);residual_unit=target-scaled@gamma
            resolution=32*np.finfo(float).eps*max(n,p)*max(1.,float(np.linalg.norm(target)))
            exact=bool(np.linalg.norm(residual_unit)<=resolution)
            if exact:residual_unit=np.zeros(n)
            residuals=scale_y*residual_unit;ss_error=scale_y*(scale_y*float(residual_unit@residual_unit));ss_total=scale_y*(scale_y*float(target@target));ss_model=max(0.,ss_total-ss_error)
            df_error=n-p;df_model=p-1;mse=ss_error/df_error
            if not exact and mse<=0:raise ValueError('Residual variance is below supported numerical precision.')
            inverse=((vh.T/s**2)@vh)/scales[:,None]/scales[None,:];covariance=None if exact else mse*inverse
            errors=np.zeros(p) if exact else np.sqrt(np.maximum(0.,np.diag(covariance)));critical=float(stats.t.isf((1-opts['confidence'])/2,df_error))
            leverage=np.sum(u*u,axis=1);r2=None if ss_total==0 else min(1.,max(0.,1-ss_error/ss_total));adjusted=None if r2 is None else 1-(1-r2)*(n-1)/df_error
            f=None if exact else (ss_model/df_model)/mse;model_p=None if f is None else float(stats.f.sf(f,df_model,df_error))
    except (FloatingPointError,OverflowError,np.linalg.LinAlgError) as error:raise ValueError('Mixture-process model arithmetic exceeds the supported finite range.') from error
    if not all(math.isfinite(value) for value in (ss_error,ss_total,ss_model,mse)):
        raise ValueError('Mixture-process sums of squares exceed supported finite range.')
    coefficients=[]
    for term,estimate,se in zip(terms,estimates,errors):
        estimate=float(estimate);se=float(se)
        if exact:t=prob=low=high=None
        else:
            if se<=0:raise ValueError('Coefficient uncertainty is below supported numerical precision.')
            t=estimate/se;prob=float(2*stats.t.sf(abs(t),df_error));low=estimate-critical*se;high=estimate+critical*se
        coefficients.append(dict(copy.deepcopy(term),estimate=estimate,standard_error=se,t=t,p_value=prob,ci_low=low,ci_high=high))
    groups={}
    for amounts,process,cov,level,value in zip(raw_points,raw_process,raw_cov,blocks,ys):groups.setdefault(tuple(amounts+process+cov+[level]),[]).append(value)
    pure_error=math.fsum(math.fsum((value-math.fsum(item/len(group) for item in group))**2 for value in group) for group in groups.values())
    if exact and pure_error<=resolution**2*scale_y**2:pure_error=0.
    pure_df=n-len(groups);lack_df=len(groups)-p;lack_ss=max(0.,ss_error-pure_error);pure_ms=pure_error/pure_df if pure_df else None;lack_ms=lack_ss/lack_df if lack_df>0 else None
    lack_f=lack_ms/pure_ms if lack_ms is not None and pure_ms is not None and pure_ms>0 else None
    anova=[dict(source='Model (corrected for mean)',df=df_model,ss=ss_model,ms=ss_model/df_model,f=f,p_value=model_p),dict(source='Error',df=df_error,ss=ss_error,ms=mse,f=None,p_value=None)]
    if pure_df>0:anova += [dict(source='Lack-of-fit',df=lack_df,ss=lack_ss,ms=lack_ms,f=lack_f,p_value=float(stats.f.sf(lack_f,lack_df,pure_df)) if lack_f is not None else None),dict(source='Pure error',df=pure_df,ss=pure_error,ms=pure_ms,f=None,p_value=None)]
    anova.append(dict(source='Total (corrected)',df=n-1,ss=ss_total,ms=None,f=None,p_value=None))
    if exact:warnings.append('Exact fit at floating-point resolution: coefficient tests, confidence intervals and model F test are unavailable.')
    if missing:warnings.append(str(len(missing))+' incomplete rows were omitted jointly across all selected roles.')
    if condition>1e8:warnings.append('The model is poorly conditioned; estimates may be sensitive to rounding.')
    warnings += ['Process terms are fully crossed with the chosen mixture basis. Covariates are additive coded numeric terms; block effects are fixed, additive and reference-coded.',
        'Component coordinates are normalized raw amounts. Inverse/pseudocomponent terms, variable mixture amounts, random blocks, stepwise selection and block interactions are not fitted.']
    saved=dict(schema='statcraft-mixture-process-fit-v1',terms=terms,total=total,component_names=cn,component_bounds=bounds,process_names=pn,process_coding=pc,covariate_names=vn,covariate_coding=vc,
        process_observed_ranges=[{'low':min(row[i] for row in raw_process),'high':max(row[i] for row in raw_process)} for i in range(len(pn))],covariate_observed_ranges=[{'low':min(row[i] for row in raw_cov),'high':max(row[i] for row in raw_cov)} for i in range(len(vn))],
        block_name=names(block)[0] if block else None,block_levels=levels,block_reference=levels[-1] if levels else None,
        coefficient_values=estimates.tolist(),centered_coefficient_values=centered_coefs.tolist(),response_offset=offset,covariance=None if covariance is None else covariance.tolist(),mse=mse,df_error=df_error)
    result=dict(analysis='mixture_process_model',method='Scheffe mixture × coded process polynomial OLS; additive covariates/fixed blocks',title=opts['title'].strip() or 'Mixture-Process Model: '+names([response])[0],
        response_index=response,response_name=names([response])[0],component_indices=components,component_names=cn,component_bounds=bounds,bounds_source=bounds_source,total=total,model=model,
        process_indices=processes,process_names=pn,process_coding=pc,covariate_indices=covariates,covariate_names=vn,covariate_coding=vc,block_index=block_index,block_name=saved['block_name'],block_levels=levels,block_reference=saved['block_reference'],
        options=opts,show_graphs=opts['show_graphs'],plot_residuals=opts['show_graphs'],confidence=opts['confidence'],coefficients=coefficients,anova=anova,
        count=n,missing=len(missing),used_rows=used,row_indices=[row-1 for row in used],missing_rows=missing,fitted=fitted.tolist(),residuals=residuals.tolist(),observations=ys,leverage=leverage.tolist(),
        r_squared=r2,adjusted_r_squared=adjusted,residual_stdev=math.sqrt(mse),df_regression=df_model,df_error=df_error,df_total=n-1,ss_regression=ss_model,ss_error=ss_error,ss_total=ss_total,ms_error=mse,f=f,p_value=model_p,
        status='exact_fit' if exact else 'estimated',model_summary=dict(count=n,term_count=p,residual_stdev=math.sqrt(mse),r_squared=r2,adjusted_r_squared=adjusted,df_error=df_error),mixture_process_fit=saved,warnings=warnings,sources=SOURCES,native_full_parity=False)
    try:json.dumps(result,allow_nan=False)
    except (ValueError,OverflowError) as error:raise ValueError('Mixture-process fit statistics exceed supported finite range.') from error
    return result


def predict(result,component_rows,process_rows=None,covariate_rows=None,block_values=None,confidence=None):
    result=result.get('result',result);saved=result.get('mixture_process_fit',{})
    if saved.get('schema')!='statcraft-mixture-process-fit-v1':raise ValueError('Select a fitted StatCraft mixture-process model.')
    confidence=_confidence(result['confidence'] if confidence is None else confidence)
    if not isinstance(component_rows,(list,tuple)) or not 1<=len(component_rows)<=4096:raise ValueError('Enter 1 to 4096 component prediction rows.')
    n=len(component_rows);total=_number(saved['total'],'Saved mixture total',True)
    points=[]
    for i,row in enumerate(component_rows):
        if not isinstance(row,(list,tuple)):raise ValueError('Enter one component amount per selected component.')
        points.append(_point(row,total,saved['component_bounds'],'Prediction row '+str(i+1)))
    warnings=[]
    def role_rows(raw,names,coding,ranges,label):
        if not names:
            if raw is not None and raw!=[] and raw!=[[] for unused in range(n)]:raise ValueError('This model has no '+label+' inputs.')
            return [[] for unused in range(n)],[[] for unused in range(n)]
        if not isinstance(raw,(list,tuple)) or len(raw)!=n:raise ValueError('Enter one '+label+' row per prediction.')
        original=[];coded=[]
        for row in raw:
            if not isinstance(row,(list,tuple)) or len(row)!=len(names):raise ValueError('Enter every selected '+label+' value in each prediction row.')
            values=[_number(value,label+' value') for value in row];original.append(values);coded.append([_code(value,code,name) for value,code,name in zip(values,coding,names)])
            if any(value<bound['low'] or value>bound['high'] for value,bound in zip(values,ranges)) and 'extrapolation' not in ' '.join(warnings).lower():warnings.append('Process/covariate extrapolation beyond observed complete-row ranges was requested; interpret predictions with care.')
        return original,coded
    raw_z,z=role_rows(process_rows,saved['process_names'],saved['process_coding'],saved['process_observed_ranges'],'process')
    raw_c,c=role_rows(covariate_rows,saved['covariate_names'],saved['covariate_coding'],saved['covariate_observed_ranges'],'covariate')
    if saved['block_levels']:
        if not isinstance(block_values,(list,tuple)) or len(block_values)!=n:raise ValueError('Enter a known block level for each prediction.')
        if any(type(value) is bool or value not in saved['block_levels'] for value in block_values):raise ValueError('Prediction block levels must occur in the fitted model.')
        blocks=list(block_values)
    else:
        if block_values is not None and block_values!=[] and block_values!=[None for unused in range(n)]:raise ValueError('This model has no block input.')
        blocks=[None]*n
    try:
        with np.errstate(over='raise',invalid='raise'):
            matrix=_matrix(points,z,c,blocks,saved['terms']);estimates=saved['response_offset']+matrix@np.asarray(saved['centered_coefficient_values'])
            covariance=None if saved['covariance'] is None else np.asarray(saved['covariance']);critical=float(stats.t.isf((1-confidence)/2,saved['df_error']));rows=[]
            for amounts,process,cov,block,vector,value in zip(component_rows,raw_z,raw_c,blocks,matrix,estimates):
                se=lo=hi=pi_lo=pi_hi=None
                if covariance is not None:
                    variance=max(0.,float(vector@covariance@vector));se=math.sqrt(variance);lo=float(value)-critical*se;hi=float(value)+critical*se;individual=math.sqrt(variance+saved['mse']);pi_lo=float(value)-critical*individual;pi_hi=float(value)+critical*individual
                rows.append(dict(components=[float(v) for v in amounts],processes=process,covariates=cov,block=block,fit=float(value),standard_error=se,ci_low=lo,ci_high=hi,prediction_low=pi_lo,prediction_high=pi_hi))
    except (FloatingPointError,OverflowError,ValueError) as error:raise ValueError('Mixture-process prediction exceeds supported finite arithmetic: '+str(error)) from error
    if covariance is None:warnings.append('Exact-fit uncertainty is unavailable.')
    output=dict(analysis='mixture_process_prediction',title='Mixture-Process Predictions',response_name=result['response_name'],component_names=saved['component_names'],process_names=saved['process_names'],covariate_names=saved['covariate_names'],block_name=saved['block_name'],total=total,confidence=confidence,rows=rows,warnings=warnings,native_full_parity=False)
    try:json.dumps(output,allow_nan=False)
    except (ValueError,OverflowError) as error:raise ValueError('Mixture-process prediction exceeds supported finite range.') from error
    return output
