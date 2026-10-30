"""Original multi-response desirability search over a common fixed-total mixture.

Goals use Derringer-Suich individual transfer functions and an importance-
weighted geometric mean. Nonlinear searches and pairwise-transfer profiles do
not establish native optimizer equivalence or a general global certificate.
"""
import copy
import json
import math
import numpy as np
from scipy.optimize import minimize
from .mixture_analysis import _number,_confidence,_basis,predict
from .mixture_exploration import _saved,_vertices,_project,_integer,_options

SOURCES=[
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/methods-and-formulas/individual-desirabilities/',
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/methods-and-formulas/composite-desirability/',
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/supporting-topics/response-optimization/what-is-importance-in-response-optimization/',
]
DEFAULTS={'starts':16,'max_iterations':300,'confidence':.95,'start_values':None,'title':''}
_SPEC={'goal','lower','target','upper','weight','importance'}


def normalize_responses(responses):
    if not isinstance(responses,(list,tuple)) or not 2<=len(responses)<=8:
        raise ValueError('Select 2 to 8 fitted responses and desirability goals.')
    normalized=[]
    for item in responses:
        if not isinstance(item,dict) or set(item)!=_SPEC:raise ValueError('Each response requires goal, lower, target, upper, weight and importance.')
        goal=item['goal']
        if goal not in ('maximize','minimize','target'):raise ValueError('Choose maximize, minimize or target for every response.')
        spec={'goal':goal}
        for name in ('lower','target','upper'):
            value=item[name]
            unused=(name=='lower' and goal=='minimize') or (name=='upper' and goal=='maximize')
            if unused:
                if value is not None:raise ValueError('Unused desirability boundary must be blank (None).')
                spec[name]=None
            else:spec[name]=_number(value,'Response '+name)
        if goal=='maximize' and not spec['lower']<spec['target']:raise ValueError('Maximize requires lower < target.')
        if goal=='minimize' and not spec['target']<spec['upper']:raise ValueError('Minimize requires target < upper.')
        if goal=='target' and not spec['lower']<spec['target']<spec['upper']:raise ValueError('Target requires lower < target < upper.')
        for name in ('weight','importance'):
            value=_number(item[name],'Response '+name)
            if not .1<=value<=10:raise ValueError('Response '+name+' must be between 0.1 and 10.')
            spec[name]=value
        normalized.append(spec)
    return normalized


def settings(options=None):
    result=_options(options,DEFAULTS)
    result['starts']=_integer(result['starts'],1,64,'Search starts')
    result['max_iterations']=_integer(result['max_iterations'],10,2000,'Maximum iterations')
    result['confidence']=_confidence(result['confidence'])
    return result


def _prepare(models,responses,bounds=None):
    specs=normalize_responses(responses)
    if not isinstance(models,(list,tuple)) or len(models)!=len(specs):raise ValueError('Match one fitted mixture model to each response goal.')
    bundles=[_saved(model) for model in models]
    total=bundles[0][2];names=bundles[0][3];n=len(names)
    physical=bundles[0][0].get('component_indices')
    for result,saved,other_total,other_names,region,terms,coefficients,offset in bundles:
        if other_total!=total or other_names!=names:raise ValueError('Response models must use the same component order, names and mixture total.')
        if physical is not None and result.get('component_indices') is not None and result['component_indices']!=physical:
            raise ValueError('Response models must use the same physical component columns in the same order.')
    region=[(max(bundle[4][i][0] for bundle in bundles),min(bundle[4][i][1] for bundle in bundles)) for i in range(n)]
    if any(low>high for low,high in region):raise ValueError('The fitted response regions have no common component bounds.')
    if bounds is not None:
        if not isinstance(bounds,(list,tuple)) or len(bounds)!=n:raise ValueError('Provide bounds for every mixture component.')
        tightened=[]
        for item,(saved_low,saved_high) in zip(bounds,region):
            if not isinstance(item,dict) or set(item)!={'low','high'}:raise ValueError('Each component bound requires low and high amounts.')
            low=_number(item['low'],'Component lower bound')/total;high=_number(item['high'],'Component upper bound')/total
            if low>high or low<saved_low-1e-12 or high>saved_high+1e-12:raise ValueError('Component limits must tighten the common fitted region.')
            tightened.append((max(low,saved_low),min(high,saved_high)))
        region=tightened
    if any(low>high for low,high in region) or math.fsum(low for low,high in region)>1+1e-12 or math.fsum(high for low,high in region)<1-1e-12:
        raise ValueError('The common component limits contain no fixed-total mixture.')
    vertices=_vertices(region)
    if not vertices:raise ValueError('The common component limits contain no fixed-total mixture.')
    scaled=[]
    for bundle,spec in zip(bundles,specs):
        coeff=bundle[6];offset=bundle[7]
        scale=max([abs(offset),float(np.max(np.abs(coeff)))]+[abs(spec[k]) for k in ('lower','target','upper') if spec[k] is not None]) or 1.
        thresholds={key:None if spec[key] is None else spec[key]/scale for key in ('lower','target','upper')}
        for left,right in (('lower','target'),('target','upper')):
            if thresholds[left] is not None and thresholds[right] is not None and thresholds[left]>=thresholds[right]:
                raise ValueError('Response goal differences are below precision relative to the fitted model scale.')
        scaled.append((bundle[5],coeff/scale,offset/scale,thresholds))
    return {'bundles':bundles,'specs':specs,'total':total,'names':names,'region':region,'vertices':vertices,'scaled':scaled}


def normalize(models,responses,bounds=None):
    ctx=_prepare(models,responses,bounds)
    return {'component_names':list(ctx['names']),'total':ctx['total'],
            'component_bounds':[{'low':low*ctx['total'],'high':high*ctx['total']} for low,high in ctx['region']],
            'responses':copy.deepcopy(ctx['specs'])}


def _point(ctx,components):
    if not isinstance(components,(list,tuple)) or len(components)!=len(ctx['names']):raise ValueError('Enter one amount for each mixture component.')
    point=[_number(value,'Component amount')/ctx['total'] for value in components]
    if any(not math.isfinite(v) for v in point) or abs(math.fsum(point)-1.)>1e-9 or any(v<low-1e-10 or v>high+1e-10 for v,(low,high) in zip(point,ctx['region'])):
        raise ValueError('Component amounts must satisfy the fixed total and common component limits.')
    # Preserve already exact feasible amounts; projection can perturb a target
    # boundary by one ULP and spuriously lower a saturated desirability.
    if math.fsum(point)==1. and all(low<=v<=high for v,(low,high) in zip(point,ctx['region'])):return np.asarray(point)
    return np.asarray(_project(point,ctx['region']))


def _q(value,thresholds):
    lower,target,upper=(thresholds[k] for k in ('lower','target','upper'))
    if lower is None:
        if value<=target:return 1.,0.
        denominator=upper-target
        return (upper-value)/denominator,-1./denominator
    if upper is None:
        if value>=target:return 1.,0.
        denominator=target-lower
        return (value-lower)/denominator,1./denominator
    if value<=target:
        denominator=target-lower
        return (value-lower)/denominator,1./denominator
    denominator=upper-target
    return (upper-value)/denominator,-1./denominator


def _characteristics(ctx,point,gradient=False):
    qs=[];gradients=[]
    for terms,coeff,offset,thresholds in ctx['scaled']:
        basis=_basis([point],terms)[0]
        value=float(offset+basis@coeff)
        q,slope=_q(value,thresholds)
        if not math.isfinite(q) or not math.isfinite(slope):raise ValueError('Desirability arithmetic exceeds supported finite precision.')
        qs.append(min(1.,q))
        if gradient:
            grad=np.zeros(len(point))
            for coefficient,term in zip(coeff,terms):
                for index in term['components']:
                    grad[index]+=coefficient*math.prod(point[j] for j in term['components'] if j!=index)
            gradients.append(slope*grad)
    return qs,gradients


def _scores(ctx,point):
    qs,_=_characteristics(ctx,point)
    logs=[spec['weight']*math.log(q) if q>0 else None for q,spec in zip(qs,ctx['specs'])]
    ds=[math.exp(value) if value is not None else 0. for value in logs]
    importance=math.fsum(spec['importance'] for spec in ctx['specs'])
    log_composite=None if any(value is None for value in logs) else math.fsum(spec['importance']/importance*value for value,spec in zip(logs,ctx['specs']))
    composite=0. if log_composite is None else min(1.,math.exp(log_composite))
    deficit=math.fsum(max(0.,-q) for q in qs)
    return ds,logs,composite,log_composite,deficit


def _evaluate(ctx,point,confidence):
    amounts=[float(value*ctx['total']) for value in point]
    ds,logs,composite,log_composite,deficit=_scores(ctx,point)
    rows=[]
    for index,(bundle,spec,d,log_d) in enumerate(zip(ctx['bundles'],ctx['specs'],ds,logs)):
        prediction=predict(bundle[0],[amounts],confidence)['rows'][0]
        rows.append(dict(copy.deepcopy(spec),model_index=index,response_name=bundle[0].get('response_name','Response '+str(index+1)),
                         prediction=prediction,fit=prediction['fit'],desirability=d,log_desirability=log_d))
    warnings=['One common fixed-total mixture is evaluated for component-only fitted models; process/block effects and additional linear constraints are not implemented.',
              'Prediction intervals are conditional on this selected setting and do not include optimization/selection uncertainty.',
              'Original desirability implementation; native numerical/UI equivalence is unverified.']
    if log_composite is None:warnings.append('At least one predicted response is at or outside an unacceptable goal boundary; composite desirability is zero.')
    elif composite==0:warnings.append('Positive composite desirability is below finite display precision; its finite log value is retained.')
    if any(value==0 and log_value is not None for value,log_value in zip(ds,logs)):
        warnings.append('Some positive individual desirabilities are below finite display precision; their finite logs are retained in the composite calculation.')
    return dict(analysis='mixture_multi_evaluation',title='Mixture Response Evaluation',component_names=list(ctx['names']),total=ctx['total'],
        component_bounds=[{'low':low*ctx['total'],'high':high*ctx['total']} for low,high in ctx['region']],components=amounts,
        responses=rows,composite_desirability=composite,log_composite_desirability=log_composite,
        positive_desirability=log_composite is not None,confidence=confidence,goal_deficit=deficit,
        status='positive_desirability' if log_composite is not None else 'zero_desirability',warnings=warnings,sources=SOURCES)


def evaluate(models,responses,components,bounds=None,confidence=.95):
    ctx=_prepare(models,responses,bounds);confidence=_confidence(confidence)
    result=_evaluate(ctx,_point(ctx,components),confidence)
    json.dumps(result,allow_nan=False)
    return result


def optimize(models,responses,bounds=None,options=None):
    ctx=_prepare(models,responses,bounds);opts=settings(options);region=ctx['region'];vertices=ctx['vertices'];n=len(region)
    initial=None if opts['start_values'] is None else _point(ctx,opts['start_values'])
    center=_project(np.mean(np.asarray(vertices),axis=0),region)
    importance=math.fsum(spec['importance'] for spec in ctx['specs'])
    weights=[spec['weight']*spec['importance']/importance for spec in ctx['specs']]
    def objective_gradient(point,epsilon):
        qs,gradients=_characteristics(ctx,point,True)
        values=[];grad=np.zeros(n)
        for q,g,weight in zip(qs,gradients,weights):
            if q>=1:values.append(0.)
            elif q>=epsilon:values.append(-weight*math.log(q));grad-=weight*g/q
            else:values.append(-weight*(math.log(epsilon)+(q-epsilon)/epsilon));grad-=weight*g/epsilon
        value=math.fsum(values)
        if not math.isfinite(value) or not np.all(np.isfinite(grad)):raise ValueError('Optimization goal arithmetic exceeds supported finite precision.')
        return value,grad
    def feasible(point):
        return len(point)==n and np.all(np.isfinite(point)) and abs(math.fsum(float(v) for v in point)-1.)<1e-8 and all(low-1e-8<=v<=high+1e-8 for v,(low,high) in zip(point,region))
    def rank(point):
        ds,logs,d,logd,deficit=_scores(ctx,point)
        return (logd is not None,logd if logd is not None else -deficit,-deficit)
    unique_region=(math.fsum(low for low,high in region)==1. or math.fsum(high for low,high in region)==1.)
    candidates=[];local=[];successes=0
    if len(vertices)==1 and unique_region:
        candidates=[(np.asarray(vertices[0]),'Unique feasible mixture')];successes=1;method='Unique feasible mixture'
    else:
        ordered=sorted((np.asarray(point) for point in vertices),key=lambda point:objective_gradient(point,.1)[0])
        seeds=[initial] if initial is not None else []
        seeds.append(center);seeds.extend(ordered[:max(1,(opts['starts']-len(seeds))//2)])
        generator=np.random.default_rng(8401)
        while len(seeds)<opts['starts']:seeds.append(_project(generator.random(n),region))
        unique=[]
        for seed in seeds[:opts['starts']]:
            if not any(np.linalg.norm(seed-other)<1e-10 for other in unique):unique.append(seed)
        for seed in unique:
            point=seed
            final=None
            for epsilon in (.1,.01,1e-4,1e-8):
                solution=minimize(lambda x:objective_gradient(x,epsilon)[0],point,
                    jac=lambda x:objective_gradient(x,epsilon)[1],method='SLSQP',bounds=region,
                    constraints=[{'type':'eq','fun':lambda x:float(np.sum(x)-1.),'jac':lambda x:np.ones(n)}],
                    options={'maxiter':opts['max_iterations'],'ftol':1e-11})
                if solution.success and feasible(solution.x):point=_project(solution.x,region)
                if epsilon==1e-8:final=solution
            if final is not None and final.success and feasible(final.x):
                point=_project(final.x,region);candidates.append((point,'Converged local search'));successes+=1
                score=_scores(ctx,point)
                local.append({'components':[float(v*ctx['total']) for v in point],
                              'composite_desirability':score[2],'log_composite_desirability':score[3],
                              'iterations':int(final.nit)})
        if not successes:raise ValueError('The multi-response mixture search did not converge from any start. Try different starts or constraints.')
        candidates.extend((np.asarray(point),'Boundary candidate') for point in vertices)
        candidates.append((center,'Feasible center candidate'))
        # Retain every evaluated starting setting; a converged local search
        # must not discard a better feasible point supplied by the user.
        candidates.extend((seed.copy(),'Starting setting candidate') for seed in unique)
        method='Deterministic multi-start constrained SLSQP with continued log-desirability and boundary candidates'
    best,origin=max(candidates,key=lambda item:rank(item[0]));best=_project(best,region)
    output=_evaluate(ctx,best,opts['confidence'])
    globally_proven=(len(vertices)==1 and unique_region) or output['composite_desirability']==1.
    output.update(analysis='mixture_multi_optimization',title=opts['title'].strip() or 'Mixture Multiple Response Optimization',
        method=method,converged=True,converged_starts=successes,global_optimum_proven=globally_proven,
        selected_origin=origin,local_solutions=local,options=opts,
        status='positive_solution_found' if output['positive_desirability'] else 'no_positive_solution_found')
    if not output['positive_desirability']:
        output['warnings'].append('No positive composite desirability was found in this bounded numerical search; this does not prove that the requested goals are infeasible.')
    if globally_proven:output['warnings'].append('The only feasible setting or the attained upper desirability bound permits a global certificate within finite numerical precision.')
    else:output['warnings'].append('Nonlinear global optimality is not certified. The best evaluated candidate is returned.')
    json.dumps(output,allow_nan=False)
    return output


def profiles(models,responses,components,bounds=None,options=None):
    ctx=_prepare(models,responses,bounds);point=_point(ctx,components)
    opts=_options(options,{'points':31,'balance_position':None,'title':''})
    count=_integer(opts['points'],2,101,'Profile points');balance=opts['balance_position']
    if balance is None:balance=len(point)-1
    if type(balance) is not int or not 0<=balance<len(point):raise ValueError('Select an existing balance component position.')
    result=[];total=ctx['total']
    for index,name in enumerate(ctx['names']):
        if index==balance:continue
        pair=float(point[index]+point[balance]);low=max(ctx['region'][index][0],pair-ctx['region'][balance][1]);high=min(ctx['region'][index][1],pair-ctx['region'][balance][0])
        if high<low-1e-12:raise ValueError('The profile has no feasible component-transfer range.')
        if ctx['region'][index][0]==ctx['region'][index][1] or ctx['region'][balance][0]==ctx['region'][balance][1] or high<low:
            low=high=float(point[index])
        values=[float(point[index])] if low==high else np.linspace(low,high,count).tolist()
        series=[{'fits':[],'desirabilities':[]} for unused in ctx['specs']];composite=[]
        for value in values:
            current=point.copy();current[index]=value;current[balance]=pair-value
            ds,logs,d,logd,deficit=_scores(ctx,current);composite.append(d)
            for j,bundle in enumerate(ctx['bundles']):
                fit=float(bundle[7]+_basis([current],bundle[5])[0]@bundle[6])
                if not math.isfinite(fit):raise ValueError('Profile predictions exceed supported finite range.')
                series[j]['fits'].append(fit);series[j]['desirabilities'].append(ds[j])
        result.append({'position':index,'name':name,'balance_position':balance,'balance_name':ctx['names'][balance],
            'low':float(low*total),'high':float(high*total),'current':float(point[index]*total),
            'x':[float(v*total) for v in values],'composite_desirability':composite,'responses':series})
    json.dumps(result,allow_nan=False)
    return result
