"""Exact conditional mixture slices of fitted mixture/process models.

External process, covariate and block settings are fixed explicitly. A linear
basis map preserves fitted means and the complete coefficient covariance;
this is not a refit or a search over the external settings.
"""
import copy
import json
import math
import numpy as np
from .mixture_analysis import _number,_confidence,_terms
from .mixture_process_model import _code,_model_terms

SOURCES=[
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/contour-plot/perform-the-analysis/specify-settings/',
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/perform-the-analysis/options-for-mixture-designs/',
]


def _names(values,minimum,maximum,label):
    if not isinstance(values,list) or not minimum<=len(values)<=maximum or any(not isinstance(name,str) or not name.strip() for name in values) or len(set(values))!=len(values):
        raise ValueError('Saved '+label+' names are invalid.')
    return list(values)


def _ranges(values,n,label,strict=True):
    if not isinstance(values,list) or len(values)!=n:raise ValueError('Saved '+label+' ranges are invalid.')
    result=[]
    for pair in values:
        if not isinstance(pair,dict) or set(pair)!={'low','high'}:raise ValueError('Saved '+label+' ranges require low and high.')
        low=_number(pair['low'],'Saved '+label+' low');high=_number(pair['high'],'Saved '+label+' high')
        if low>high or strict and low==high:raise ValueError('Saved '+label+' ranges are invalid.')
        if strict:_code(low,{'low':low,'high':high},label);_code(high,{'low':low,'high':high},label)
        result.append({'low':low,'high':high})
    return result


def _validated(value):
    if not isinstance(value,dict):raise ValueError('Select a fitted mixture/process model.')
    result=value.get('result',value)
    if not isinstance(result,dict):raise ValueError('Select a fitted mixture/process model.')
    saved=result.get('mixture_process_fit')
    if not isinstance(saved,dict) or saved.get('schema')!='statcraft-mixture-process-fit-v1':raise ValueError('Select a fitted mixture/process model with all saved roles.')
    required={'total','component_names','component_bounds','process_names','process_coding','process_observed_ranges','covariate_names','covariate_coding','covariate_observed_ranges','block_name','block_levels','block_reference','terms','coefficient_values','centered_coefficient_values','response_offset','covariance','mse','df_error'}
    if required-set(saved):raise ValueError('Saved mixture/process model state is incomplete.')
    _names([result.get('response_name')],1,1,'response')
    total=_number(saved['total'],'Saved mixture total',True)
    cn=_names(saved['component_names'],2,8,'component');pn=_names(saved['process_names'],0,3,'process');vn=_names(saved['covariate_names'],0,4,'covariate')
    if len(set(cn+pn+vn))!=len(cn+pn+vn):raise ValueError('Saved model role names must be distinct.')
    bounds=_ranges(saved['component_bounds'],len(cn),'component')
    if any(pair['low']<0 or pair['high']>total for pair in bounds) or math.fsum(pair['low']/total for pair in bounds)>1+1e-12 or math.fsum(pair['high']/total for pair in bounds)<1-1e-12:raise ValueError('Saved component bounds do not contain a fixed-total mixture.')
    pc=_ranges(saved['process_coding'],len(pn),'process coding');vc=_ranges(saved['covariate_coding'],len(vn),'covariate coding')
    pr=_ranges(saved['process_observed_ranges'],len(pn),'observed process',False);vr=_ranges(saved['covariate_observed_ranges'],len(vn),'observed covariate',False)
    levels=saved['block_levels'];block_name=saved['block_name']
    if not isinstance(levels,list):raise ValueError('Saved block levels are invalid.')
    if block_name is None:
        if levels or saved['block_reference'] is not None:raise ValueError('Saved block metadata is inconsistent.')
    else:
        if not isinstance(block_name,str) or not block_name.strip() or not 2<=len(levels)<=16:raise ValueError('Saved fixed-block metadata is invalid.')
        numeric=all(type(level) in (int,float) and math.isfinite(level) for level in levels)
        textual=all(isinstance(level,str) and bool(level.strip()) for level in levels)
        if not (numeric or textual) or any(level in levels[:i] for i,level in enumerate(levels)) or saved['block_reference']!=levels[-1]:raise ValueError('Saved fixed-block levels/reference are invalid.')
    if not pn and not vn and not levels:raise ValueError('This saved model has no process, covariate or block roles.')
    model=result.get('model');options=result.get('options')
    if model not in ('linear','quadratic','special_cubic') or model=='special_cubic' and len(cn)<3 or not isinstance(options,dict) or type(options.get('process_order')) is not int or options['process_order'] not in (1,2):raise ValueError('Saved model orders are invalid.')
    expected=_model_terms(cn,model,pn,options['process_order'],vn,levels)
    terms=saved['terms']
    if not isinstance(terms,list) or len(terms)!=len(expected):raise ValueError('Saved model terms are incomplete.')
    # Exact authored tensor descriptors prevent a corrupted partial model from
    # being silently interpreted as a different conditional polynomial.
    for term,wanted in zip(terms,expected):
        if not isinstance(term,dict) or set(term)!=set(wanted) or any(term[key]!=wanted[key] for key in wanted):raise ValueError('Saved model term descriptors are invalid or inconsistent.')
    for term in terms:
        for key in ('components','process_positions'):
            if key in term and (not isinstance(term[key],list) or any(type(i) is not int for i in term[key])):raise ValueError('Saved term positions must be integer ordinals.')
        if 'covariate_position' in term and type(term['covariate_position']) is not int:raise ValueError('Saved covariate position is invalid.')
    p=len(terms)
    def vector(raw,label):
        if not isinstance(raw,list) or len(raw)!=p:raise ValueError('Saved '+label+' dimensions are invalid.')
        return np.asarray([_number(item,'Saved '+label) for item in raw],dtype=float)
    centered=vector(saved['centered_coefficient_values'],'centered coefficients');vector(saved['coefficient_values'],'coefficients')
    offset=_number(saved['response_offset'],'Saved response offset');mse=_number(saved['mse'],'Saved residual variance')
    df=saved['df_error']
    if mse<0 or type(df) is not int or df<=0:raise ValueError('Saved residual variance/degrees of freedom are invalid.')
    covariance=saved['covariance']
    if covariance is not None:
        if not isinstance(covariance,list) or len(covariance)!=p or any(not isinstance(row,list) or len(row)!=p for row in covariance):raise ValueError('Saved covariance dimensions are invalid.')
        covariance=np.asarray([[_number(item,'Saved covariance') for item in row] for row in covariance],dtype=float)
        scale=float(np.max(np.abs(covariance)))
        normalized=covariance/scale if scale else covariance
        if not np.allclose(normalized,normalized.T,rtol=1e-9,atol=1e-12):raise ValueError('Saved covariance must be symmetric.')
        try:minimum=float(np.linalg.eigvalsh((normalized+normalized.T)/2)[0])
        except np.linalg.LinAlgError as error:raise ValueError('Saved covariance cannot be validated.') from error
        if minimum < -1e-9:raise ValueError('Saved covariance must be positive semidefinite.')
        covariance=(covariance/2+covariance.T/2)
    elif mse!=0:raise ValueError('Saved covariance is unavailable despite nonzero residual variance.')
    confidence=_confidence(result.get('confidence'))
    return result,saved,total,cn,pn,vn,bounds,pc,vc,pr,vr,levels,terms,centered,offset,covariance,mse,df,confidence


def _values(raw,names,coding,label):
    if not names:
        if raw is not None and not (isinstance(raw,(list,tuple)) and not raw):raise ValueError('This model has no '+label+' values to hold.')
        return [],[]
    if not isinstance(raw,(list,tuple)) or len(raw)!=len(names):raise ValueError('Specify every '+label+' holding value explicitly.')
    values=[_number(value,label+' holding value') for value in raw]
    return values,[_code(value,pair,name) for value,pair,name in zip(values,coding,names)]


def condition(result,process_values=None,covariate_values=None,block_value=None):
    """Reduce a full fit at explicit physical-unit external settings exactly."""
    r,saved,total,cn,pn,vn,bounds,pc,vc,pr,vr,levels,terms,centered,offset,covariance,mse,df,confidence=_validated(result)
    processes,z=_values(process_values,pn,pc,'process');covariates,c=_values(covariate_values,vn,vc,'covariate')
    if levels:
        if type(block_value) is bool or block_value not in levels:raise ValueError('Choose an observed block level explicitly.')
        block=copy.deepcopy(next(level for level in levels if level==block_value))
    else:
        if block_value is not None:raise ValueError('This model has no block holding value.')
        block=None
    mixture=_terms(cn,r['model']);positions={tuple(term['components']):i for i,term in enumerate(mixture)}
    transform=np.zeros((len(terms),len(mixture)))
    try:
        with np.errstate(over='raise',invalid='raise'):
            for row,term in enumerate(terms):
                if 'covariate_position' in term:transform[row,:len(cn)]=c[term['covariate_position']]
                elif 'block_level' in term:transform[row,:len(cn)]=float(block==term['block_level'])
                else:transform[row,positions[tuple(term['components'])]]=math.prod(z[i] for i in term['process_positions'])
            coefficients=transform.T@centered
            cov=None if covariance is None else transform.T@covariance@transform
            estimates=coefficients.copy();estimates[:len(cn)]+=offset
    except (FloatingPointError,OverflowError) as error:raise ValueError('Conditioned model arithmetic exceeds supported finite range.') from error
    if not np.all(np.isfinite(coefficients)) or not np.all(np.isfinite(estimates)) or cov is not None and not np.all(np.isfinite(cov)):raise ValueError('Conditioned model arithmetic exceeds supported finite range.')
    warnings=[]
    if any(value<pair['low'] or value>pair['high'] for value,pair in zip(processes,pr)) or any(value<pair['low'] or value>pair['high'] for value,pair in zip(covariates,vr)):
        warnings.append('Fixed process/covariate settings extrapolate beyond the observed complete-row ranges.')
    labels=['Process '+name+' = '+format(value,'.7g')+' (coded '+format(code,'.7g')+')' for name,value,code in zip(pn,processes,z)]
    labels += ['Covariate '+name+' = '+format(value,'.7g') for name,value in zip(vn,covariates)]
    if levels:labels.append('Block '+saved['block_name']+' = '+str(block))
    context=dict(process_names=pn,process_values=processes,process_coded_values=z,covariate_names=vn,covariate_values=covariates,covariate_coded_values=c,
                 block_name=saved['block_name'],block_value=block,summary='; '.join(labels),warnings=list(warnings))
    warnings.append('Process, covariate and block settings are fixed explicitly; contouring and optimization vary component amounts only.')
    if cov is None:warnings.append('Exact-fit uncertainty is unavailable.')
    output=dict(analysis='mixture_condition',title='Conditional Mixture Model: '+r['response_name'],response_name=r['response_name'],model=r['model'],
        component_names=cn,component_indices=copy.deepcopy(r.get('component_indices',[])),component_bounds=copy.deepcopy(bounds),total=total,confidence=confidence,
        conditioning=context,warnings=warnings,sources=list(SOURCES),
        mixture_fit=dict(schema='statcraft-mixture-fit-v1',terms=mixture,total=total,component_names=cn,component_bounds=copy.deepcopy(bounds),
             coefficient_values=estimates.tolist(),centered_coefficient_values=coefficients.tolist(),response_offset=offset,
             covariance=None if cov is None else cov.tolist(),mse=mse,df_error=df))
    json.dumps(output,allow_nan=False)
    return output


def _attach(output,conditioned):
    output['conditioning']=copy.deepcopy(conditioned['conditioning'])
    output['warnings']=[warning for warning in output.get('warnings',[]) if warning!='One fitted response is optimized; multi-response composite desirability and process/block effects are not implemented.']
    output['warnings']+=list(conditioned['warnings'])
    output['sources']=list(dict.fromkeys(output.get('sources',[])+SOURCES))
    json.dumps(output,allow_nan=False)
    return output


def contour(result,process_values=None,covariate_values=None,block_value=None,component_positions=None,hold_values=None,options=None):
    from .mixture_exploration import contour as explore
    conditioned=condition(result,process_values,covariate_values,block_value)
    return _attach(explore(conditioned,component_positions,hold_values,options),conditioned)


def optimize(result,process_values=None,covariate_values=None,block_value=None,goal='maximize',target=None,bounds=None,options=None):
    from .mixture_exploration import optimize as explore
    conditioned=condition(result,process_values,covariate_values,block_value)
    return _attach(explore(conditioned,goal,target,bounds,options),conditioned)
