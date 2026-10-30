"""Original bounded Scheffe mixture slices and single-response optimization.

Only component-only saved fits are supported. Ternary coordinates are fractions
of the displayed three-component subtotal; model evaluation uses full-total raw
proportions. Nonlinear multi-start solutions are numerical candidates, not a
certificate of a global optimum or native optimizer equivalence.
"""
import copy
import itertools
import json
import math
import numpy as np
from scipy.optimize import minimize,linprog
from scipy.spatial import ConvexHull,Delaunay,QhullError
from .mixture_analysis import _number,_basis,_confidence,predict

SOURCES=[
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/contour-plot/perform-the-analysis/specify-settings/',
 'https://support.statcraft.com/en-us/statcraft/help-and-how-to/statistical-modeling/using-fitted-models/how-to/response-optimizer/perform-the-analysis/options-for-mixture-designs/',
]
CONTOUR_DEFAULTS={'resolution':32,'levels':8,'title':''}
OPTIMIZER_DEFAULTS={'starts':16,'max_iterations':300,'confidence':.95,'start_values':None,'title':''}


def _integer(value,low,high,label):
    if type(value) is not int or not low<=value<=high:raise ValueError(f'{label} must be an integer from {low} to {high}.')
    return value


def _options(values,defaults):
    if values is not None and (not isinstance(values,dict) or set(values)-set(defaults)):raise ValueError('Unsupported mixture exploration options.')
    result=copy.deepcopy(defaults)
    result.update(copy.deepcopy(values or {}))
    if not isinstance(result['title'],str):raise ValueError('Title must be text.')
    return result


def _saved(value):
    if not isinstance(value,dict):raise ValueError('Select a fitted StatCraft mixture model.')
    result=value.get('result',value)
    if not isinstance(result,dict):raise ValueError('Select a fitted StatCraft mixture model.')
    saved=result.get('mixture_fit',{})
    if not isinstance(saved,dict) or saved.get('schema')!='statcraft-mixture-fit-v1':raise ValueError('A saved StatCraft mixture model is required.')
    total=_number(saved.get('total'),'Saved total',True)
    names=saved.get('component_names')
    if not isinstance(names,list) or not 2<=len(names)<=8 or any(not isinstance(name,str) or not name for name in names):raise ValueError('Saved component names are invalid.')
    n=len(names)
    bounds=saved.get('component_bounds')
    if not isinstance(bounds,list) or len(bounds)!=n:raise ValueError('Saved component bounds are invalid.')
    normalized=[]
    for item in bounds:
        if not isinstance(item,dict) or set(item)!={'low','high'}:raise ValueError('Saved component bounds are invalid.')
        low=_number(item['low'],'Saved lower bound')/total;high=_number(item['high'],'Saved upper bound')/total
        if not 0<=low<high<=1:raise ValueError('Saved component bounds are invalid.')
        normalized.append((low,high))
    terms=saved.get('terms');coeff=saved.get('centered_coefficient_values')
    if not isinstance(terms,list) or not terms or not isinstance(coeff,list) or len(terms)!=len(coeff):raise ValueError('Saved mixture coefficients are invalid.')
    patterns=[]
    for term in terms:
        if not isinstance(term,dict):raise ValueError('Saved model terms are invalid.')
        positions=term.get('components')
        if not isinstance(positions,list) or not 1<=len(positions)<=3 or any(type(i) is not int or not 0<=i<n for i in positions) or len(set(positions))!=len(positions):raise ValueError('Saved model terms are invalid.')
        patterns.append(tuple(positions))
    if len(set(patterns))!=len(patterns) or {p[0] for p in patterns if len(p)==1}!=set(range(n)):raise ValueError('Saved model does not contain distinct component terms.')
    coefficients=np.asarray([_number(c,'Saved coefficient') for c in coeff])
    offset=_number(saved.get('response_offset'),'Saved response offset')
    if math.fsum(low for low,high in normalized)>1+1e-12 or math.fsum(high for low,high in normalized)<1-1e-12:raise ValueError('Saved bounds do not contain a fixed-total mixture.')
    return result,saved,total,list(names),normalized,terms,coefficients,offset


def _vertices(bounds,subtotal=1.):
    """Every vertex of a box intersected by one fixed-sum plane, <=1024."""
    count=len(bounds);found={}
    for free in range(count):
        other=[i for i in range(count) if i!=free]
        for bits in itertools.product((0,1),repeat=count-1):
            point=[0.]*count
            for index,bit in zip(other,bits):point[index]=bounds[index][bit]
            point[free]=subtotal-math.fsum(point[index] for index in other)
            if all(low-2e-12<=value<=high+2e-12 for value,(low,high) in zip(point,bounds)):
                point=[min(high,max(low,value)) for value,(low,high) in zip(point,bounds)]
                # A final closure adjustment cannot move outside the accepted region.
                delta=subtotal-math.fsum(point)
                if delta:
                    at=max(range(count),key=lambda i:bounds[i][1]-point[i] if delta>0 else point[i]-bounds[i][0])
                    point[at]+=delta
                found[tuple(round(value,14) for value in point)]=point
    return list(found.values())


def _evaluate(points,terms,coefficients,offset):
    try:
        with np.errstate(over='raise',invalid='raise'):
            values=offset+_basis(points,terms)@coefficients
    except (FloatingPointError,OverflowError) as error:raise ValueError('Mixture predictions exceed the supported finite range.') from error
    if not np.all(np.isfinite(values)):raise ValueError('Mixture predictions exceed the supported finite range.')
    return values


def _xy(point,subtotal):
    return [float(point[1]/subtotal+.5*point[2]/subtotal),float(math.sqrt(3)/2*point[2]/subtotal)]


def contour(fitted_result,component_positions=None,hold_values=None,options=None):
    """Return a clipped triangular response mesh and piecewise-linear isolines."""
    result,saved,total,names,bounds,terms,coefficients,offset=_saved(fitted_result)
    n=len(names)
    if n<3:raise ValueError('A triangular contour plot requires at least three components.')
    positions=[0,1,2] if component_positions is None else component_positions
    if not isinstance(positions,(list,tuple)) or len(positions)!=3 or any(type(i) is not int or not 0<=i<n for i in positions) or len(set(positions))!=3:raise ValueError('Select three distinct model component positions.')
    positions=list(positions);others=[i for i in range(n) if i not in positions]
    if hold_values is None:holds={i:bounds[i][0] for i in others}
    else:
        if not isinstance(hold_values,(list,tuple)) or len(hold_values)!=len(others):raise ValueError('Provide one holding value for each component not displayed.')
        holds={}
        for item in hold_values:
            if not isinstance(item,dict) or set(item)!={'position','value'}:raise ValueError('Holding values require position and value.')
            index=item['position']
            if type(index) is not int or index not in others or index in holds:raise ValueError('Hold only distinct components outside the plot.')
            value=_number(item['value'],'Holding amount')/total
            if not bounds[index][0]-1e-12<=value<=bounds[index][1]+1e-12:raise ValueError('A holding amount is outside its saved component bounds.')
            holds[index]=min(bounds[index][1],max(bounds[index][0],value))
    subtotal=1.-math.fsum(holds.values())
    if subtotal<=1e-14:raise ValueError('Holding amounts leave no positive three-component subtotal.')
    selected_bounds=[bounds[i] for i in positions]
    if math.fsum(low for low,high in selected_bounds)>subtotal+1e-12 or math.fsum(high for low,high in selected_bounds)<subtotal-1e-12:raise ValueError('Holding amounts leave no feasible contour region within component bounds.')
    vertices=_vertices(selected_bounds,subtotal)
    if len(vertices)<3:raise ValueError('The selected slice has no two-dimensional feasible contour region.')
    xy=np.asarray([_xy(point,subtotal) for point in vertices])
    try:
        hull=ConvexHull(xy)
    except QhullError as error:raise ValueError('The selected slice has no two-dimensional feasible contour region.') from error
    if hull.volume<=1e-14:raise ValueError('The selected slice is too narrow to resolve a contour region.')
    vertices=[vertices[int(index)] for index in hull.vertices]
    polygon=[_xy(point,subtotal) for point in vertices]
    opts=_options(options,CONTOUR_DEFAULTS)
    resolution=_integer(opts['resolution'],8,80,'Contour resolution');level_count=_integer(opts['levels'],2,20,'Contour levels')
    pool={}
    def add(point):
        pool[tuple(round(value/subtotal,14) for value in point)]=list(point)
    for a in range(resolution+1):
        for b in range(resolution+1-a):
            point=[subtotal*a/resolution,subtotal*b/resolution,subtotal*(resolution-a-b)/resolution]
            if all(low-1e-12<=value<=high+1e-12 for value,(low,high) in zip(point,selected_bounds)):add(point)
    # Include exact boundary vertices and subdivision so narrow clipped regions
    # still have a useful surface rather than disappearing between grid nodes.
    for k,left in enumerate(vertices):
        right=vertices[(k+1)%len(vertices)]
        for step in range(resolution+1):
            fraction=step/resolution;add([a+(b-a)*fraction for a,b in zip(left,right)])
    add([math.fsum(point[i]/len(vertices) for point in vertices) for i in range(3)])
    selected_points=list(pool.values())
    coords=np.asarray([_xy(point,subtotal) for point in selected_points])
    try:triangulation=Delaunay(coords)
    except QhullError as error:raise ValueError('The contour mesh could not be triangulated reliably.') from error
    full=[]
    for point in selected_points:
        row=[holds.get(i,0.) for i in range(n)]
        for index,value in zip(positions,point):row[index]=value
        full.append(row)
    values=_evaluate(full,terms,coefficients,offset)
    triangles=[]
    for candidate in triangulation.simplices:
        a,b,c=coords[candidate]
        area=abs(float(np.linalg.det(np.stack((b-a,c-a)))))
        if area>1e-15:triangles.append([int(i) for i in candidate])
    if not triangles:raise ValueError('The contour mesh has no usable surface triangles.')
    low=float(np.min(values));high=float(np.max(values))
    if not math.isfinite(high-low):raise ValueError('The contour response span exceeds the supported finite range.')
    levels=[] if math.isclose(low,high,rel_tol=0,abs_tol=32*math.ulp(max(abs(low),abs(high)))) else [low+(high-low)*i/(level_count+1) for i in range(1,level_count+1)]
    lines=[]
    for level in levels:
        segments=[]
        for triangle in triangles:
            intersections=[]
            for a,b in zip(triangle,(triangle[1],triangle[2],triangle[0])):
                va=float(values[a]);vb=float(values[b])
                if (va<level<=vb) or (vb<level<=va):
                    fraction=(level-va)/(vb-va);point=coords[a]+fraction*(coords[b]-coords[a]);intersections.append([float(point[0]),float(point[1])])
            if len(intersections)==2 and intersections[0]!=intersections[1]:segments.append(intersections[0]+intersections[1])
        lines.append({'level':level,'segments':segments})
    points=[dict(components=[float(value*total) for value in row],x=float(coord[0]),y=float(coord[1]),fit=float(value)) for row,coord,value in zip(full,coords,values)]
    output=dict(analysis='mixture_contour',title=opts['title'].strip() or 'Contour Plot of '+result.get('response_name','Response'),
        response_name=result.get('response_name','Response'),component_names=names,component_positions=positions,
        selected_names=[names[i] for i in positions],hold_values=[{'position':i,'name':names[i],'value':holds[i]*total} for i in others],
        total=total,display_total=subtotal*total,component_bounds=copy.deepcopy(saved['component_bounds']),
        points=points,triangles=triangles,polygon=polygon,vertices=polygon,contour_lines=lines,levels=levels,
        value_range=[low,high],options=opts,show_graphs=True,
        warnings=['Model evaluated in full-total raw proportions; ternary coordinates show the selected component subtotal.',
          'Contour bands/lines use a finite piecewise-linear mesh; extrema and isolines are approximations.',
          'Saved component bounds and explicit holding amounts define this slice. Native numerical/UI equivalence is unverified.'],sources=SOURCES)
    json.dumps(output,allow_nan=False)
    return output


def _project(seed,bounds):
    values=np.asarray(seed,dtype=float);low=np.asarray([item[0] for item in bounds]);high=np.asarray([item[1] for item in bounds])
    a=float(np.min(values-high))-1.;b=float(np.max(values-low))+1.
    for _ in range(90):
        mid=(a+b)/2;point=np.clip(values-mid,low,high)
        if float(point.sum())>1:a=mid
        else:b=mid
    point=np.clip(values-(a+b)/2,low,high)
    residual=1.-math.fsum(float(value) for value in point)
    if residual:
        index=int(np.argmax(high-point if residual>0 else point-low));point[index]+=residual
    return point


def optimize(fitted_result,goal='maximize',target=None,bounds=None,options=None):
    """Search one response under saved/tighter box and fixed-total constraints."""
    result,saved,total,names,original,terms,coefficients,offset=_saved(fitted_result)
    if goal not in ('maximize','minimize','target'):raise ValueError('Choose maximize, minimize or target.')
    if goal=='target':target=_number(target,'Response target')
    elif target is not None:raise ValueError('A target is used only with the target goal.')
    opts=_options(options,OPTIMIZER_DEFAULTS)
    starts=_integer(opts['starts'],1,64,'Search starts');iterations=_integer(opts['max_iterations'],10,2000,'Maximum iterations')
    confidence=_confidence(opts['confidence']);n=len(names)
    region=original
    if bounds is not None:
        if not isinstance(bounds,(list,tuple)) or len(bounds)!=n:raise ValueError('Provide bounds for every component.')
        region=[]
        for item,(saved_low,saved_high) in zip(bounds,original):
            if not isinstance(item,dict) or set(item)!={'low','high'}:raise ValueError('Each constraint requires low and high amounts.')
            low=_number(item['low'],'Lower amount')/total;high=_number(item['high'],'Upper amount')/total
            if low>high or low<saved_low-1e-12 or high>saved_high+1e-12:raise ValueError('Optimizer bounds must tighten the saved model bounds.')
            region.append((max(saved_low,low),min(saved_high,high)))
    if math.fsum(a for a,b in region)>1+1e-12 or math.fsum(b for a,b in region)<1-1e-12:raise ValueError('Optimizer constraints contain no fixed-total mixture.')
    vertices=_vertices(region)
    if not vertices:raise ValueError('Optimizer constraints contain no fixed-total mixture.')
    center=np.mean(np.asarray(vertices),axis=0)
    initial=None
    if opts['start_values'] is not None:
        raw=opts['start_values']
        if not isinstance(raw,(list,tuple)) or len(raw)!=n:raise ValueError('Enter one starting amount per component.')
        initial=np.asarray([_number(value,'Starting amount')/total for value in raw])
        if abs(math.fsum(initial)-1)>1e-10 or any(not low-1e-12<=value<=high+1e-12 for value,(low,high) in zip(initial,region)):raise ValueError('Starting amounts must satisfy the total and optimizer bounds.')
    delta=0. if target is None else target-offset
    if not math.isfinite(delta):raise ValueError('Response target difference exceeds the supported finite range.')
    scale=max(float(np.max(np.abs(coefficients))),abs(delta)) or 1.
    scaled=coefficients/scale;target_scaled=delta/scale
    def value_and_gradient(point):
        basis=_basis([point],terms)[0];value=float(basis@scaled);gradient=np.zeros(n)
        for coefficient,term in zip(scaled,terms):
            positions=term['components']
            for index in positions:gradient[index]+=coefficient*math.prod(point[i] for i in positions if i!=index)
        if goal=='target':return (value-target_scaled)**2,2*(value-target_scaled)*gradient
        return (-value,-gradient) if goal=='maximize' else (value,gradient)
    def objective(point):return value_and_gradient(point)[0]
    def feasible(point):return len(point)==n and np.all(np.isfinite(point)) and abs(math.fsum(float(v) for v in point)-1)<1e-8 and all(low-1e-8<=v<=high+1e-8 for v,(low,high) in zip(point,region))
    candidates=[];local=[];successes=0
    linear=all(len(term['components'])==1 for term in terms)
    unique_region=(math.fsum(low for low,high in region)==1. or math.fsum(high for low,high in region)==1.)
    if len(vertices)==1 and unique_region:
        candidates=[(np.asarray(vertices[0]),'Unique feasible mixture')];successes=1;method='Unique feasible mixture';global_proven=True
    elif linear and goal!='target':
        cost=value_and_gradient(center)[1]
        solution=linprog(cost,A_eq=np.ones((1,n)),b_eq=[1.],bounds=region,method='highs')
        if not solution.success or not feasible(solution.x):raise ValueError('The constrained linear mixture optimization did not converge.')
        candidates=[(_project(solution.x,region),'Linear programming')];successes=1;method='Linear programming';global_proven=True
    else:
        ranked=sorted(vertices,key=objective)
        seeds=[initial] if initial is not None else []
        seeds.append(center)
        # Mix promising boundary starts and reproducible interior starts.
        seeds.extend(np.asarray(point) for point in ranked[:max(1,(starts-len(seeds))//2)])
        generator=np.random.default_rng(8301)
        while len(seeds)<starts:seeds.append(_project(generator.random(n),region))
        unique=[]
        for seed in seeds[:starts]:
            if not any(np.linalg.norm(seed-other)<1e-10 for other in unique):unique.append(seed)
        for seed in unique:
            solution=minimize(lambda point:value_and_gradient(point)[0],seed,jac=lambda point:value_and_gradient(point)[1],method='SLSQP',bounds=region,
                constraints=[{'type':'eq','fun':lambda point:float(np.sum(point)-1.),'jac':lambda point:np.ones(n)}],options={'maxiter':iterations,'ftol':1e-12})
            if solution.success and feasible(solution.x):
                point=_project(solution.x,region);candidates.append((point,'Converged local search'));successes+=1
                local.append({'components':[float(v*total) for v in point],'objective':float(objective(point)),'iterations':int(solution.nit)})
        if not successes:raise ValueError('The constrained mixture search did not converge from any start. Try different starting amounts or constraints.')
        # Evaluate vertices too; curved surfaces can have boundary optima missed
        # by a local termination point. These remain feasible candidates.
        candidates.extend((seed.copy(),'Starting setting candidate') for seed in unique)
        candidates.extend((np.asarray(point),'Boundary candidate') for point in vertices)
        method='Deterministic multi-start constrained SLSQP with boundary candidates';global_proven=False
    best,origin=min(candidates,key=lambda item:objective(item[0]))
    best=_project(best,region);amounts=[float(value*total) for value in best]
    prediction=predict(result,[amounts],confidence)['rows'][0]
    output=dict(analysis='mixture_optimization',title=opts['title'].strip() or 'Response Optimization: '+result.get('response_name','Response'),
        response_name=result.get('response_name','Response'),component_names=names,total=total,goal=goal,target=target,
        components=amounts,prediction=prediction,predicted_response=prediction['fit'],confidence=confidence,
        component_bounds=[{'low':float(low*total),'high':float(high*total)} for low,high in region],
        method=method,converged=True,converged_starts=successes,global_optimum_proven=global_proven,
        selected_origin=origin,local_solutions=local,objective=float(objective(best)),options=opts,
        target_error=None if target is None else abs(prediction['fit']-target),show_graphs=True,
        warnings=['One fitted response is optimized; multi-response composite desirability and process/block effects are not implemented.',
          'Nonlinear search is bounded and numerical; a global optimum is not certified.' if not global_proven else 'The fixed feasible mixture or linear objective permits a global optimum certificate within the stated constraints.',
          'Saved-model uncertainty is conditional on this selected setting; it does not account for optimization/selection uncertainty.',
          'Original numerical search; native optimizer and interactive desirability equivalence are unverified.'],sources=SOURCES)
    json.dumps(output,allow_nan=False)
    return output
