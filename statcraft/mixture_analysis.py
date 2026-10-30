"""Original Scheffe mixture-response models with a fixed-total constraint.

Coordinates are raw component proportions, not lower-bound pseudocomponents.
The component sum supplies the constant-response direction, so no independent
intercept is added. Corrected ANOVA tests improvement over a constant response.
"""
from copy import deepcopy
from itertools import combinations
import json
import math
import numbers
import numpy as np
from scipy import stats

from .model import Worksheet

MODELS=('linear','quadratic','special_cubic')
DEFAULT_OPTIONS={'confidence':.95,'show_graphs':True,'title':'','bounds':None}


def _number(value,label,positive=False):
    if isinstance(value,(bool,np.bool_)) or not isinstance(value,numbers.Real) or not math.isfinite(value):
        raise ValueError(f'{label} must be finite and numeric.')
    value=float(value)
    if positive and value<=0:raise ValueError(f'{label} must be positive.')
    return value


def _confidence(value):
    value=_number(value,'Confidence level')
    if not 0<value<1:raise ValueError('Confidence level must be strictly between 0 and 1.')
    return value


def _terms(names,model):
    terms=[{'name':name,'components':[i]} for i,name in enumerate(names)]
    if model!='linear':
        terms += [{'name':'*'.join(names[i] for i in indices),'components':list(indices)} for indices in combinations(range(len(names)),2)]
    if model=='special_cubic':
        terms += [{'name':'*'.join(names[i] for i in indices),'components':list(indices)} for indices in combinations(range(len(names)),3)]
    return terms


def _basis(points,terms):
    return np.asarray([[math.prod(point[index] for index in term['components']) for term in terms] for point in points],dtype=float)


def _bounds(worksheet,indices,total,explicit):
    source='simplex'
    warnings=[]
    bounds=explicit
    if bounds is None:
        design=worksheet.metadata.get('doe',{})
        if isinstance(design,dict) and design.get('schema')=='statcraft-special-design-v1' and design.get('kind') in ('simplex_centroid','simplex_lattice','extreme_vertices'):
            factors=design.get('factors',[])
            try:
                declared_total=_number(design.get('options',{}).get('total',1.),'Design total',True)
                matches=[]
                for index in indices:
                    match=[factor for factor in factors if isinstance(factor,dict) and factor.get('column_index')==index and factor.get('name')==worksheet.columns[index].name and factor.get('kind')=='number']
                    if len(match)!=1:raise ValueError('Unmatched component.')
                    matches.append({'low':match[0]['low'],'high':match[0]['high']})
                if not math.isclose(total,declared_total,rel_tol=1e-10,abs_tol=0):raise ValueError('Changed design total.')
                bounds=matches;source='worksheet_design'
            except (ValueError,TypeError,KeyError,AttributeError):
                warnings.append('Worksheet design bounds could not be matched by component index, name and total; the standard simplex region is used.')
    else:source='explicit_options'
    if bounds is None:bounds=[{'low':0.,'high':total} for _ in indices]
    if not isinstance(bounds,(list,tuple)) or len(bounds)!=len(indices):
        raise ValueError('Provide one lower/upper bounds object for each component.')
    normalized=[]
    for item in bounds:
        if not isinstance(item,dict) or set(item)!={'low','high'}:
            raise ValueError('Each component bounds object must specify low and high.')
        low=_number(item['low'],'Component lower bound');high=_number(item['high'],'Component upper bound')
        if low<0 or high>total or low>=high:
            raise ValueError('Component bounds must satisfy 0 <= low < high <= total.')
        normalized.append({'low':low,'high':high})
    if math.fsum(item['low']/total for item in normalized)>1+1e-12 or math.fsum(item['high']/total for item in normalized)<1-1e-12:
        raise ValueError('Component bounds do not contain a feasible fixed-total mixture.')
    return normalized,source,warnings


def _point(values,total,bounds,label):
    if len(values)!=len(bounds):raise ValueError(f'{label}: provide one amount per component.')
    point=[_number(value,f'{label} component') for value in values]
    if any(value<0 for value in point):raise ValueError(f'{label}: component amounts must be nonnegative.')
    ratios=[value/total for value in point]
    if not all(math.isfinite(value) for value in ratios):raise ValueError(f'{label}: component scaling exceeds the supported range.')
    sum_ratio=math.fsum(ratios)
    if not math.isclose(sum_ratio,1.,rel_tol=1e-9,abs_tol=1e-12):
        raise ValueError(f'{label}: component amounts must sum to the fixed total {total:g}.')
    for value,bound in zip(ratios,bounds):
        if value<bound['low']/total-1e-10 or value>bound['high']/total+1e-10:
            raise ValueError(f'{label}: component amount lies outside its declared bounds.')
    # Remove only accepted arithmetic closure error; preserve nonnegative amounts.
    return [value/sum_ratio for value in ratios]


def _finite_or_none(value):
    value=float(value)
    return value if math.isfinite(value) else None


def fit(worksheet,response_index,component_indices,model='quadratic',total=1.0,options=None):
    """Fit a full-rank Scheffe model with positive residual degrees of freedom.

    Bounds may be supplied explicitly or matched to an active StatCraft mixture
    design. Complete-case rows retain their one-based worksheet numbers. Native
    coefficient/ANOVA layout and numerical equivalence remain unverified.
    """
    if not isinstance(worksheet,Worksheet):raise ValueError('A typed Worksheet is required.')
    if type(response_index) is not int or not 0<=response_index<len(worksheet.columns):raise ValueError('Select a valid response column.')
    if not isinstance(component_indices,(list,tuple)) or not 2<=len(component_indices)<=8:
        raise ValueError('Select 2 to 8 numeric component columns.')
    indices=list(component_indices)
    if any(type(index) is not int or not 0<=index<len(worksheet.columns) for index in indices) or len(set(indices))!=len(indices) or response_index in indices:
        raise ValueError('Select distinct component columns and a separate response column.')
    if model not in MODELS:raise ValueError('Choose linear, quadratic or special_cubic.')
    if model=='special_cubic' and len(indices)<3:raise ValueError('Special cubic requires at least 3 components.')
    total=_number(total,'Mixture total',True)
    if options is not None and not isinstance(options,dict):raise ValueError('Mixture model options must be an object.')
    opts=deepcopy(DEFAULT_OPTIONS)
    if options:
        if set(options)-set(opts):raise ValueError('Unknown mixture model option.')
        opts.update(deepcopy(options))
    confidence=_confidence(opts['confidence'])
    if type(opts['show_graphs']) is not bool or not isinstance(opts['title'],str):raise ValueError('show_graphs must be Boolean and title must be text.')
    columns=[worksheet.columns[index] for index in indices]
    response=worksheet.columns[response_index]
    if any(column.kind!='number' for column in columns+[response]):raise ValueError('Response and components must be numeric columns.')
    for column in columns+[response]:column.validate()
    names=[column.name or f'C{index+1}' for column,index in zip(columns,indices)]
    if len(set(names))!=len(names):raise ValueError('Component names must be distinct.')
    bounds,bounds_source,warnings=_bounds(worksheet,indices,total,opts['bounds'])
    extent=max(len(column.values) for column in columns+[response])
    if extent>4096:raise ValueError('Mixture fitting is limited to 4096 worksheet rows.')
    points=[];raw_points=[];outcomes=[];used=[];missing=[]
    for row in range(extent):
        values=[column.values[row] if row<len(column.values) else None for column in columns]
        y=response.values[row] if row<len(response.values) else None
        if y is None or any(value is None for value in values):missing.append(row+1);continue
        points.append(_point(values,total,bounds,f'Row {row+1}'))
        raw_points.append(tuple(float(value) for value in values))
        outcomes.append(float(y));used.append(row+1)
    terms=_terms(names,model);p=len(terms);n=len(points)
    if n<=p:raise ValueError(f'The {model} model has {p} terms; provide more than {p} complete observations for residual degrees of freedom.')
    try:
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            matrix=_basis(points,terms)
            scales=np.max(np.abs(matrix),axis=0)
            if np.any(scales==0):raise ValueError('Mixture design is rank deficient: a model term has no variation in the selected region.')
            scaled=matrix/scales
            u,singular,vh=np.linalg.svd(scaled,full_matrices=False)
            tolerance=np.finfo(float).eps*max(n,p)*singular[0]
            if singular[-1]<=tolerance:raise ValueError('Mixture design is rank deficient for the selected model.')
            condition=float(singular[0]/singular[-1])
            if condition>1e12:raise ValueError('Mixture design is too poorly conditioned for a reliable fit.')
            mean_y=math.fsum(value/n for value in outcomes)
            y=np.asarray(outcomes)
            centered=y-mean_y
            scale_y=float(np.max(np.abs(centered))) or 1.
            target=centered/scale_y
            gamma=vh.T@((u.T@target)/singular)
            centered_coefficients=(gamma*scale_y)/scales
            estimates=centered_coefficients.copy();estimates[:len(indices)]+=mean_y
            fitted=mean_y+scale_y*(scaled@gamma)
            residual_unit=target-scaled@gamma
            resolution=32*np.finfo(float).eps*max(n,p)*max(1.,float(np.linalg.norm(target)))
            exact=bool(np.linalg.norm(residual_unit)<=resolution)
            if exact:residual_unit=np.zeros(n)
            residuals=scale_y*residual_unit
            ss_error=scale_y*(scale_y*float(residual_unit@residual_unit))
            ss_total=scale_y*(scale_y*float(target@target))
            ss_model=max(0.,ss_total-ss_error)
            df_error=n-p;df_model=p-1
            mse=ss_error/df_error;ms_model=ss_model/df_model
            if not exact and mse<=0:raise ValueError('Residual variance is below supported numeric precision.')
            inverse=((vh.T/singular**2)@vh)/scales[:,None]/scales[None,:]
            covariance=None if exact else mse*inverse
            errors=np.zeros(p) if exact else np.sqrt(np.maximum(0.,np.diag(covariance)))
            critical=float(stats.t.isf((1-confidence)/2,df_error))
            leverage=np.sum(u*u,axis=1)
            r_squared=None if ss_total==0 else min(1.,max(0.,1-ss_error/ss_total))
            adjusted=None if r_squared is None else 1-(1-r_squared)*(n-1)/df_error
            f=None if exact else ms_model/mse
            model_p=None if f is None else float(stats.f.sf(f,df_model,df_error))
    except (FloatingPointError,OverflowError,np.linalg.LinAlgError) as exc:
        raise ValueError('Mixture model arithmetic exceeds the supported range or the numerical solve failed.') from exc
    coefficients=[]
    for term,estimate,se in zip(terms,estimates,errors):
        estimate=float(estimate);se=float(se)
        if exact:
            t,p_value,low,high=None,None,None,None
        else:
            if se<=0:raise ValueError('Coefficient uncertainty is below supported numeric precision.')
            t=float(estimate/se)
            p_value=float(2*stats.t.sf(abs(t),df_error))
            low=estimate-critical*se;high=estimate+critical*se
        coefficients.append({'name':term['name'],'components':term['components'],'estimate':estimate,
            'standard_error':se,'t':t,'p_value':p_value,'ci_low':low,'ci_high':high})
    # Exact original component amounts define replicate groups; nearby blends
    # are never rounded together to manufacture pure-error degrees of freedom.
    groups={}
    for point,value in zip(raw_points,outcomes):groups.setdefault(point,[]).append(value)
    pure_error=math.fsum(math.fsum((value-math.fsum(item/len(group) for item in group))**2 for value in group) for group in groups.values())
    if exact and pure_error<=resolution**2*scale_y**2:pure_error=0.
    pure_df=n-len(groups);lack_df=len(groups)-p
    lack_ss=max(0.,ss_error-pure_error)
    pure_ms=pure_error/pure_df if pure_df>0 else None
    lack_ms=lack_ss/lack_df if lack_df>0 else None
    lack_f=lack_ms/pure_ms if lack_ms is not None and pure_ms is not None and pure_ms>0 else None
    lack_p=float(stats.f.sf(lack_f,lack_df,pure_df)) if lack_f is not None else None
    anova=[{'source':'Model (corrected for mean)','df':df_model,'ss':ss_model,'ms':ms_model,'f':f,'p_value':model_p},
           {'source':'Error','df':df_error,'ss':ss_error,'ms':mse,'f':None,'p_value':None}]
    if pure_df>0:
        anova.extend([{'source':'Lack-of-fit','df':lack_df,'ss':lack_ss,'ms':lack_ms,'f':lack_f,'p_value':lack_p},
                      {'source':'Pure error','df':pure_df,'ss':pure_error,'ms':pure_ms,'f':None,'p_value':None}])
    anova.append({'source':'Total (corrected)','df':n-1,'ss':ss_total,'ms':None,'f':None,'p_value':None})
    if exact:warnings.append('Exact fit at floating-point resolution: coefficient tests, confidence intervals and model F test are unavailable.')
    if pure_df>0 and pure_ms==0 and lack_df>0:warnings.append('Pure-error variance is zero; the lack-of-fit F test is unavailable.')
    if condition>1e8:warnings.append('The model is poorly conditioned; coefficient estimates may be sensitive to rounding.')
    if missing:warnings.append(f'{len(missing)} incomplete rows were omitted jointly.')
    warnings.append('The model contains mixture-component terms only; block, process-variable and covariate effects are not fitted.')
    warnings.append('Coordinates use normalized raw amounts, with only arithmetic closure error removed; lower-bound pseudocomponents are not used.')
    warnings.append('Original SVD estimation and inference; full native model equivalence is unverified.')
    summary={'count':n,'term_count':p,'residual_stdev':math.sqrt(mse),'r_squared':r_squared,
             'adjusted_r_squared':adjusted,'df_error':df_error,'status':'exact_fit' if exact else 'estimated'}
    result={'analysis':'mixture_model','method':'Scheffe mixture OLS (no independent intercept)',
        'title':opts['title'].strip() or f'Mixture Model: {response.name or "Response"}',
        'model':model,'total':total,'response_index':response_index,'response_name':response.name or f'C{response_index+1}',
        'component_indices':indices,'component_names':names,'predictor_names':names,
        'component_bounds':bounds,'bounds_source':bounds_source,'options':opts,
        'show_graphs':opts['show_graphs'],'plot_residuals':opts['show_graphs'],
        'confidence':confidence,'coefficients':coefficients,'anova':anova,'model_summary':summary,
        'count':n,'missing':len(missing),'used_rows':used,'missing_rows':missing,'row_indices':[row-1 for row in used],
        'fitted':fitted.tolist(),'residuals':residuals.tolist(),'observations':outcomes,'leverage':leverage.tolist(),
        'r_squared':r_squared,'adjusted_r_squared':adjusted,'residual_stdev':math.sqrt(mse),
        'df_regression':df_model,'df_error':df_error,'df_total':n-1,
        'ss_regression':ss_model,'ss_error':ss_error,'ss_total':ss_total,'ms_error':mse,
        'f':f,'p_value':model_p,'status':summary['status'],'warnings':warnings,
        'mixture_fit':{'schema':'statcraft-mixture-fit-v1','terms':terms,'total':total,'component_bounds':bounds,
            'component_names':names,'coefficient_values':estimates.tolist(),
            'centered_coefficient_values':centered_coefficients.tolist(),'response_offset':mean_y,
            'covariance':None if covariance is None else covariance.tolist(),'mse':mse,'df_error':df_error}}
    try:json.dumps(result,allow_nan=False)
    except (ValueError,OverflowError) as exc:raise ValueError('Mixture fit statistics exceed the supported finite numeric range.') from exc
    return result


def predict(result,component_rows,confidence=None):
    """Predict feasible raw-amount mixtures with t-based mean and individual CIs."""
    result=result.get('result',result)
    saved=result.get('mixture_fit',{})
    if saved.get('schema')!='statcraft-mixture-fit-v1':raise ValueError('A saved StatCraft mixture fit is required.')
    confidence=_confidence(result['confidence'] if confidence is None else confidence)
    if not isinstance(component_rows,(list,tuple)) or not 1<=len(component_rows)<=4096:
        raise ValueError('Provide 1 to 4096 mixture component rows.')
    total=_number(saved['total'],'Saved mixture total',True)
    bounds=saved['component_bounds'];terms=saved['terms']
    points=[]
    for i,row in enumerate(component_rows,1):
        if not isinstance(row,(list,tuple)):raise ValueError('Each prediction row must contain component amounts.')
        points.append(_point(row,total,bounds,f'Prediction row {i}'))
    matrix=_basis(points,terms)
    centered=np.asarray(saved['centered_coefficient_values'],dtype=float)
    predictions=float(saved['response_offset'])+matrix@centered
    covariance=None if saved['covariance'] is None else np.asarray(saved['covariance'],dtype=float)
    critical=float(stats.t.isf((1-confidence)/2,saved['df_error']))
    rows=[]
    for amounts,vector,estimate in zip(component_rows,matrix,predictions):
        se=None;mean_low=None;mean_high=None;prediction_low=None;prediction_high=None
        if covariance is not None:
            variance=max(0.,float(vector@covariance@vector))
            se=math.sqrt(variance)
            mean_low=float(estimate)-critical*se;mean_high=float(estimate)+critical*se
            individual=math.sqrt(variance+saved['mse'])
            prediction_low=float(estimate)-critical*individual;prediction_high=float(estimate)+critical*individual
        rows.append({'components':[float(value) for value in amounts],'fit':float(estimate),'standard_error':se,
            'ci_low':mean_low,'ci_high':mean_high,'prediction_low':prediction_low,'prediction_high':prediction_high})
    output={'analysis':'mixture_prediction','confidence':confidence,'rows':rows,
            'warnings':['Exact-fit uncertainty is unavailable.'] if covariance is None else []}
    try:json.dumps(output,allow_nan=False)
    except (ValueError,OverflowError) as exc:raise ValueError('Mixture prediction exceeds the supported finite numeric range.') from exc
    return output
