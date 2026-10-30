"""Joint constrained optimization of mixture amounts and continuous processes.

All predictions and uncertainty use the complete saved mixture/process model.
Nonlinear multi-start search returns the best evaluated feasible setting; it is
not a certificate of global optimality or native optimizer equivalence.
"""
import copy
import itertools
import json
import math
import numpy as np
from scipy.optimize import minimize
from .mixture_analysis import _number,_confidence
from .mixture_condition import _validated,_values
from .mixture_process_model import _code,_matrix,predict
from .mixture_exploration import _vertices,_project,_integer,_options

DEFAULTS={'starts':20,'max_iterations':300,'confidence':.95,'start_components':None,'start_processes':None,'profile_points':31,'title':''}


def _region(raw,saved,total,label):
    if raw is None:return [(v['low']/total,v['high']/total) for v in saved]
    if not isinstance(raw,(list,tuple)) or len(raw)!=len(saved):raise ValueError('Enter one lower/upper bound for every '+label+'.')
    out=[]
    for pair,original in zip(raw,saved):
        if not isinstance(pair,dict) or set(pair)!={'low','high'}:raise ValueError('Bounds require low and high values.')
        low=_number(pair['low'],label+' lower bound');high=_number(pair['high'],label+' upper bound')
        tol=1e-10*max(1.,abs(original['low']),abs(original['high']))
        if low>high or low<original['low']-tol or high>original['high']+tol:raise ValueError(label.title()+' bounds must tighten the saved/observed bounds.')
        out.append((max(low,original['low'])/total,min(high,original['high'])/total))
    return out


def optimize(fitted_result,goal='maximize',target=None,component_bounds=None,process_bounds=None,covariate_values=None,block_value=None,options=None):
    r,saved,total,cn,pn,vn,cb,pc,vc,pr,vr,levels,terms,coeff,offset,cov,mse,df,unused=_validated(fitted_result)
    if not pn:raise ValueError('Select a mixture model with at least one continuous process variable for joint optimization.')
    if goal not in ('maximize','minimize','target'):raise ValueError('Choose maximize, minimize or target.')
    if goal=='target':target=_number(target,'Response target')
    elif target is not None:raise ValueError('A target is used only with a target goal.')
    opts=_options(options,DEFAULTS);starts=_integer(opts['starts'],1,64,'Search starts');iterations=_integer(opts['max_iterations'],10,2000,'Maximum iterations');count=_integer(opts['profile_points'],2,101,'Profile points');confidence=_confidence(opts['confidence'])
    component_region=_region(component_bounds,cb,total,'component')
    raw_process_region=_region(process_bounds,pr,1.,'process')
    process_region=[(_code(low,code,name),_code(high,code,name)) for (low,high),code,name in zip(raw_process_region,pc,pn)]
    covariates,c=_values(covariate_values,vn,vc,'covariate')
    if levels:
        if type(block_value) is bool or block_value not in levels:raise ValueError('Choose an observed block level explicitly.')
        block=copy.deepcopy(next(v for v in levels if v==block_value))
    else:
        if block_value is not None:raise ValueError('This model has no block holding value.')
        block=None
    n=len(cn);m=len(pn);vertices=_vertices(component_region)
    if not vertices:raise ValueError('The component bounds contain no fixed-total mixture.')
    unique_components=(math.fsum(v[0] for v in component_region)==1. or math.fsum(v[1] for v in component_region)==1.)
    if unique_components:component_region=[(v,v) for v in vertices[0]]
    bounds=component_region+process_region
    center=np.asarray(list(np.mean(np.asarray(vertices),axis=0))+[(a+b)/2 for a,b in process_region])
    initial=center.copy()
    if opts['start_components'] is not None:
        raw=opts['start_components']
        if not isinstance(raw,(list,tuple)) or len(raw)!=n:raise ValueError('Enter one starting amount per component.')
        initial[:n]=[_number(v,'Starting component amount')/total for v in raw]
    if opts['start_processes'] is not None:
        raw=opts['start_processes']
        if not isinstance(raw,(list,tuple)) or len(raw)!=m:raise ValueError('Enter one starting value per process.')
        initial[n:]=[_code(_number(v,'Starting process value'),code,name) for v,code,name in zip(raw,pc,pn)]
    def feasible(point):
        return len(point)==n+m and np.all(np.isfinite(point)) and abs(math.fsum(float(v) for v in point[:n])-1)<1e-8 and all(a-1e-9<=v<=b+1e-9 for v,(a,b) in zip(point,bounds))
    if not feasible(initial):raise ValueError('Starting settings must satisfy component total and all optimizer bounds.')
    delta=0. if target is None else target-offset
    if not math.isfinite(delta):raise ValueError('Response target difference exceeds finite numeric range.')
    scale=max(float(np.max(np.abs(coeff))),abs(delta)) or 1.;scaled=coeff/scale;target_scaled=delta/scale
    def value_gradient(point):
        value=0.;gradient=np.zeros(n+m)
        for coefficient,term in zip(scaled,terms):
            if 'covariate_position' in term:value+=coefficient*c[term['covariate_position']];continue
            if 'block_level' in term:value+=coefficient*float(block==term['block_level']);continue
            positions=list(term['components'])+[n+j for j in term['process_positions']]
            value+=coefficient*math.prod(point[i] for i in positions)
            for at,index in enumerate(positions):gradient[index]+=coefficient*math.prod(point[j] for ordinal,j in enumerate(positions) if ordinal!=at)
        if not math.isfinite(value) or not np.all(np.isfinite(gradient)):raise ValueError('Joint optimization exceeds finite model arithmetic.')
        if goal=='target':return (value-target_scaled)**2,2*(value-target_scaled)*gradient
        return (-value,-gradient) if goal=='maximize' else (value,gradient)
    def objective(point):return value_gradient(point)[0]
    def normalized(point):
        return np.concatenate((_project(point[:n],component_region),np.asarray([min(b,max(a,float(v))) for v,(a,b) in zip(point[n:],process_region)])))
    process_corners=list(itertools.product(*[(a,) if a==b else (a,b) for a,b in process_region]))
    boundary=[np.asarray(list(v)+list(p)) for v in vertices for p in process_corners]
    ranked=sorted(boundary,key=objective)
    unique_setting=unique_components and all(a==b for a,b in process_region)
    local=[];candidates=[];successes=0
    if unique_setting:candidates=[(initial,'Unique feasible setting')];successes=1
    else:
        seeds=[initial,center];seeds+=ranked[:max(1,(starts-len(seeds))//2)]
        rng=np.random.default_rng(8903)
        while len(seeds)<starts:seeds.append(np.concatenate((_project(rng.random(n),component_region),[rng.uniform(a,b) if a<b else a for a,b in process_region])))
        unique=[]
        for seed in seeds[:starts]:
            if not any(np.linalg.norm(seed-v)<1e-10 for v in unique):unique.append(seed)
        constraints=[] if unique_components else [{'type':'eq','fun':lambda x:float(np.sum(x[:n])-1.),'jac':lambda x:np.concatenate((np.ones(n),np.zeros(m)))}]
        for seed in unique:
            solution=minimize(lambda x:value_gradient(x)[0],seed,jac=lambda x:value_gradient(x)[1],method='SLSQP',bounds=bounds,constraints=constraints,options={'maxiter':iterations,'ftol':1e-12})
            if solution.success and feasible(solution.x):
                point=normalized(solution.x);successes+=1;candidates.append((point,'Converged local search'))
                local.append({'objective':float(objective(point)),'iterations':int(solution.nit)})
        if not successes:raise ValueError('The joint mixture/process search did not converge. Try different starting values or bounds.')
        candidates.extend((v.copy(),'Starting setting candidate') for v in unique)
        candidates.extend((v,'Boundary setting candidate') for v in boundary)
    best,origin=min(candidates,key=lambda item:objective(item[0]));best=normalized(best)
    def actual(point):
        amounts=[float(v*total) for v in point[:n]]
        processes=[float(code['low']/2+code['high']/2+(code['high']/2-code['low']/2)*v) for v,code in zip(point[n:],pc)]
        return amounts,processes
    amounts,processes=actual(best)
    prediction=predict(r,[amounts],[processes],[covariates] if vn else None,[block] if levels else None,confidence)['rows'][0]
    profiles=[]
    # Mixture profiles transfer amount against another movable component to
    # preserve closure exactly. Process profiles leave the composition fixed.
    for index,name in enumerate(cn):
        others=[j for j in range(n) if j!=index and component_region[j][1]>component_region[j][0]]
        if not others:continue
        balance=max(others,key=lambda j:component_region[j][1]-component_region[j][0]);pair=float(best[index]+best[balance])
        low=max(component_region[index][0],pair-component_region[balance][1]);high=min(component_region[index][1],pair-component_region[balance][0])
        xs=[float(best[index])] if high-low<1e-12 else np.linspace(low,high,count).tolist();points=[]
        for value in xs:
            point=best.copy();point[index]=value;point[balance]=pair-value;points.append(point)
        profiles.append(_profile(r,points,actual,covariates,block,levels,confidence,role='component',position=index,name=name+' ↔ '+cn[balance],low=low*total,high=high*total,current=amounts[index],x=[v*total for v in xs],balance_position=balance))
    for index,name in enumerate(pn):
        low,high=process_region[index];xs=[float(best[n+index])] if low==high else np.linspace(low,high,count).tolist();points=[]
        for value in xs:point=best.copy();point[n+index]=value;points.append(point)
        rawxs=[actual(point)[1][index] for point in points]
        profiles.append(_profile(r,points,actual,covariates,block,levels,confidence,role='process',position=index,name=name,low=raw_process_region[index][0],high=raw_process_region[index][1],current=processes[index],x=rawxs))
    warnings=['Joint composition/process optimization uses an independent bounded nonlinear search; global optimality and native equivalence are unverified.','Prediction intervals are conditional on the selected setting and do not include optimization-selection uncertainty.']
    if any(v<pair['low'] or v>pair['high'] for v,pair in zip(covariates,vr)):warnings.append('Held covariates extrapolate beyond their observed complete-row ranges.')
    if cov is None:warnings.append('Exact-fit uncertainty is unavailable.')
    output=dict(analysis='mixture_joint_optimization',title=opts['title'].strip() or 'Joint Mixture and Process Optimization: '+r['response_name'],response_name=r['response_name'],component_names=cn,process_names=pn,covariate_names=vn,block_name=saved['block_name'],total=total,goal=goal,target=target,components=amounts,processes=processes,covariate_values=covariates,block_value=block,prediction=prediction,predicted_response=prediction['fit'],confidence=confidence,component_bounds=[{'low':float(a*total),'high':float(b*total)} for a,b in component_region],process_bounds=[{'low':float(a),'high':float(b)} for a,b in raw_process_region],profiles=profiles,method='Unique feasible setting' if unique_setting else 'Deterministic constrained multi-start SLSQP with starting and boundary candidates',converged=True,converged_starts=successes,selected_origin=origin,local_solutions=local,objective=float(objective(best)),target_error=None if target is None else abs(prediction['fit']-target),global_optimum_proven=unique_setting,options=opts,show_graphs=True,warnings=warnings,native_full_parity=False)
    json.dumps(output,allow_nan=False)
    return output


def _profile(result,points,actual,covariates,block,levels,confidence,**fields):
    settings=[actual(p) for p in points]
    predictions=predict(result,[v[0] for v in settings],[v[1] for v in settings],[covariates for p in points] if covariates else None,[block for p in points] if levels else None,confidence)['rows']
    return dict(fields,fits=[row['fit'] for row in predictions],ci_low=[row['ci_low'] for row in predictions],ci_high=[row['ci_high'] for row in predictions])
