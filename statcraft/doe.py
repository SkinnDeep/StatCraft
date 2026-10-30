"""Original bounded full two-level factorial creation and coded OLS analysis.

NIST standard order/model matrix reference:
https://www.itl.nist.gov/div898/handbook/pri/section3/pri3331.htm
No native DOE metadata, response-surface/Taguchi designs,
multiple blocks, curvature test or native parity is implemented.
"""
import itertools
import math
import random
from .model import Column, Worksheet
from .engine import normalize_numeric
from .regression import multiple_regression


def _integer(value, low, high, name):
    if type(value) is not int or not low<=value<=high:
        raise ValueError(f'{name} must be an integer from {low} to {high}.')
    return value


def _level(value):
    value=normalize_numeric(value)
    if value is None:raise ValueError('Factor levels must be finite and nonmissing.')
    return value


def _coding(name,low,high):
    low,high=_level(low),_level(high)
    if low>=high:raise ValueError('Each factor low setting must be below its high setting.')
    span=high-low;center=math.fsum((low/2,high/2));half=span/2
    if not math.isfinite(span) or half<=0 or not low<center<high:
        raise ValueError('Factor range/midpoint exceeds supported numeric precision.')
    return dict(name=name,low=low,high=high,center=center,half_range=half)


def create_factorial(factors,replicates=1,centers=0,randomize=True,seed=1,blocks=1):
    """Create 2..8 numeric factors, first factor fastest, single or multiple blocks, <=4096 runs.

    Centers is the center-run count per block. PtType=1 corners, 0 centers.
    StdOrder is grouped by block (corners then centers); RunOrder is physical row order.
    """
    factors=list(factors);k=len(factors)
    _integer(k,2,8,'Factor count');_integer(replicates,1,20,'Replicates')
    _integer(centers,0,20,'Center runs')
    _integer(blocks,1,64,'Blocks')
    if type(randomize) is not bool:raise ValueError('Randomize must be true or false.')
    _integer(seed,-(2**63),2**63-1,'Randomization seed')
    total_corners=(2**k)*replicates
    if total_corners%blocks!=0:
        raise ValueError('Total corner runs must be evenly divisible by the number of blocks.')
    count=total_corners+(centers*blocks)
    if count>4096:raise ValueError('The factorial plan exceeds the 4096-run limit.')
    coding=[];names=set(n.casefold() for n in ['StdOrder','RunOrder','PtType','Blocks'])
    for i,factor in enumerate(factors):
        if not isinstance(factor,dict):raise ValueError('Factors must be objects with name, low and high.')
        name=factor.get('name')
        if not isinstance(name,str) or not name.strip() or name.casefold() in names:
            raise ValueError('Factor names must be nonempty, unique and different from design-column names.')
        names.add(name.casefold())
        if 'low' not in factor or 'high' not in factor:raise ValueError('Each factor needs low and high settings.')
        code=_coding(name,factor['low'],factor['high']);code['column_index']=4+i;coding.append(code)
    corners_per_rep=2**k; corners_per_block=total_corners//blocks
    corner_runs=[]
    for rep in range(replicates):
        for corner in range(corners_per_rep):
            settings=[f['high'] if corner&(1<<i) else f['low'] for i,f in enumerate(coding)]
            if blocks==replicates: b=rep+1
            elif blocks==1: b=1
            elif blocks%replicates==0:
                sub_blocks=blocks//replicates
                if sub_blocks==2:
                    prod=math.prod(1 if corner&(1<<i) else -1 for i in range(k))
                    sub=0 if prod<0 else 1
                elif sub_blocks==4 and k>=3:
                    p1=math.prod(1 if corner&(1<<i) else -1 for i in range(k-1))
                    p2=math.prod(1 if corner&(1<<i) else -1 for i in range(1,k))
                    sub=(0 if p1<0 else 1)+2*(0 if p2<0 else 1)
                else:
                    sub=corner//(corners_per_rep//sub_blocks)
                b=rep*sub_blocks+sub+1
            else:
                flat_idx=rep*corners_per_rep+corner
                b=flat_idx//corners_per_block+1
            corner_runs.append(dict(pt_type=1,block=b,settings=settings))
    center_runs=[]
    for b in range(1,blocks+1):
        for _ in range(centers):
            center_runs.append(dict(pt_type=0,block=b,settings=[f['center'] for f in coding]))
    block_groups={b:[] for b in range(1,blocks+1)}
    for r in corner_runs: block_groups[r['block']].append(r)
    for r in center_runs: block_groups[r['block']].append(r)
    unrandomized=[]
    for b in range(1,blocks+1): unrandomized.extend(block_groups[b])
    for i,r in enumerate(unrandomized,1): r['std_order']=i
    if randomize:
        rng=random.Random(seed)
        plan=[]
        for b in range(1,blocks+1):
            b_runs=list(block_groups[b]); rng.shuffle(b_runs); plan.extend(b_runs)
    else: plan=unrandomized
    columns=[Column('StdOrder',values=[r['std_order'] for r in plan]),
             Column('RunOrder',values=list(range(1,count+1))),
             Column('PtType',values=[r['pt_type'] for r in plan]),
             Column('Blocks',values=[r['block'] for r in plan])]
    columns.extend(Column(f['name'],values=[r['settings'][i] for r in plan]) for i,f in enumerate(coding))
    return Worksheet('Full factorial design',columns,metadata={'doe':dict(
        schema='statcraft-full-factorial-v1',origin='Original StatCraft design',
        design='full two-level factorial',factors=coding,replicates=replicates,
        centers=centers,randomize=randomize,seed=seed,blocks=blocks,
        standard_order='Runs grouped by block; first factor fastest within block; centers per block.',
        point_types={'factorial':1,'center':0},native_parity=False)})


def analyze_factorial(worksheet,response_index,factor_indices,max_order=2,confidence=.95,selected_terms=None,include_blocks=None):
    """Fit all hierarchical coded terms through order1..3, intercept included.

    Main/interaction effects are twice coded coefficients. Centers inform the
    linear/interactions model; no center indicator or curvature test is fitted.
    Blocks are fitted when multiple blocks are present and include_blocks is not False.
    Missing responses/factors omit a row jointly. Rank/saturated models error.
    """
    if not isinstance(worksheet,Worksheet):raise ValueError('A Worksheet is required.')
    factors=list(factor_indices);k=len(factors)
    _integer(k,2,8,'Factor count');_integer(max_order,1,3,'Maximum interaction order')
    _integer(response_index,0,len(worksheet.columns)-1,'Response index')
    for index in factors:_integer(index,0,len(worksheet.columns)-1,'Factor index')
    if len(set(factors))!=k or response_index in factors:raise ValueError('Select distinct factor columns and a separate response.')
    selected=[worksheet.columns[i] for i in factors]
    response=worksheet.columns[response_index]
    if any(c.kind!='number' for c in selected+[response]):raise ValueError('DOE requires numeric factor and response columns.')
    names=[c.name for c in selected]
    if len(set(names))!=k:raise ValueError('Selected factors need distinct names.')
    n=worksheet.row_count
    if n>4096:raise ValueError('DOE analysis is limited to 4096 worksheet rows.')
    values=[[_level_or_missing(c.values[i]) if i<len(c.values) else None for i in range(n)] for c in selected]
    metadata=worksheet.metadata.get('doe',{})
    trusted=metadata.get('schema') in ('statcraft-full-factorial-v1','statcraft-regular-fractional-v1')
    coding=[]
    for column,index,observed in zip(selected,factors,values):
        declared=next((f for f in metadata.get('factors',[]) if f.get('column_index')==index and f.get('name')==column.name),None) if trusted else None
        if declared is not None:
            code=_coding(column.name,declared['low'],declared['high']);code['source']='StatCraft design metadata'
        else:
            levels=sorted(set(v for v in observed if v is not None))
            if len(levels) not in (2,3):raise ValueError('Each factor needs two observed levels, optionally their common center setting.')
            code=_coding(column.name,levels[0],levels[-1]);code['source']='Observed levels'
        code['column_index']=index;code['letter']=chr(65+len(coding));coding.append(code)
    used=[];coded_rows=[];ys=[]
    for row in range(n):
        y=_level_or_missing(response.values[row]) if row<len(response.values) else None
        raw=[v[row] for v in values]
        if y is None or any(v is None for v in raw):continue
        codes=[]
        for v,code in zip(raw,coding):
            z=(v-code['center'])/code['half_range']
            if not math.isfinite(z):raise ValueError('Factor coding exceeds supported numeric range.')
            nearest=min((-1.,0.,1.),key=lambda t:abs(z-t))
            if abs(z-nearest)>1e-10:raise ValueError('Factor data contain settings outside the two levels and their midpoint.')
            codes.append(nearest)
        if any(v==0 for v in codes) and not all(v==0 for v in codes):
            raise ValueError('A center run must place every selected factor at its midpoint.')
        used.append(row);coded_rows.append(codes);ys.append(y)
    block_col=next((c for c in worksheet.columns if c.name.casefold()=='blocks'),None)
    raw_blocks=[block_col.values[r] if r<len(block_col.values) else None for r in used] if block_col is not None else [1]*len(used)
    observed_blocks=[normalize_numeric(b) for b in raw_blocks]
    unique_blocks=sorted(set(b for b in observed_blocks if b is not None))
    has_multiple_blocks=len(unique_blocks)>1
    if include_blocks is None:
        include_blocks=has_multiple_blocks
    elif type(include_blocks) is not bool:
        raise ValueError('Include blocks must be true or false.')
    elif include_blocks and not has_multiple_blocks:
        include_blocks=False
    block_predictors=[]
    block_names=[]
    if include_blocks:
        if len(unique_blocks)==2:
            b0,b1=unique_blocks[0],unique_blocks[1]
            block_predictors.append([1. if b==b1 else -1. for b in observed_blocks])
            block_names.append('Blocks')
        elif len(unique_blocks)>2:
            ref_block=unique_blocks[-1]
            for b_lvl in unique_blocks[:-1]:
                block_predictors.append([1. if b==b_lvl else (-1. if b==ref_block else 0.) for b in observed_blocks])
                block_names.append(f'Blocks {b_lvl}')
    terms=[indices for order in range(1,min(max_order,k)+1) for indices in itertools.combinations(range(k),order)]
    if selected_terms is not None:
        if not isinstance(selected_terms,list) or not selected_terms:raise ValueError('Select at least one model term.')
        terms=[]
        for term in selected_terms:
            if not isinstance(term,list) or not 1<=len(term)<=3 or any(type(i) is not int or not 0<=i<k for i in term):
                raise ValueError('Model terms must contain one to three valid factor positions.')
            if len(set(term))!=len(term):raise ValueError('A factor cannot repeat within a term.')
            value=tuple(sorted(term))
            if value in terms:raise ValueError('Model terms must be distinct.')
            terms.append(value)
        terms.sort(key=lambda value:(len(value),value))
        for term in terms:
            for order in range(1,len(term)):
                if any(subset not in terms for subset in itertools.combinations(term,order)):
                    raise ValueError('Include all lower-order terms for a hierarchical model.')
    term_names=['*'.join(names[i] for i in term) for term in terms]
    if len(set(term_names))!=len(term_names):raise ValueError('Factor names produce ambiguous interaction labels.')
    predictors=[[math.prod(row[i] for i in term) for row in coded_rows] for term in terms]
    all_predictors=block_predictors+predictors
    all_term_names=block_names+term_names
    aliases=[]
    for i,values in enumerate(all_predictors):
        for j in range(i):
            if values==all_predictors[j] or values==[-v for v in all_predictors[j]]:
                aliases.append(all_term_names[j]+' = '+('−' if values!=all_predictors[j] else '')+all_term_names[i])
    if aliases:raise ValueError('Selected model is rank deficient; terms are confounded on the retained rows: '+ '; '.join(aliases[:8])+'. Select one representative in Terms.')
    result=multiple_regression(all_predictors,ys,confidence,predictor_names=all_term_names)
    n_blocks=len(block_names)
    for i,coefficient in enumerate(result['coefficients']):
        if i==0:
            coefficient['term_factors']=[]
            coefficient['effect']=None
            coefficient['effect_se']=None
        elif i<=n_blocks:
            coefficient['term_factors']=['Blocks']
            coefficient['effect']=2*coefficient['estimate'] if len(unique_blocks)==2 else None
            coefficient['effect_se']=2*coefficient['standard_error'] if len(unique_blocks)==2 else None
        else:
            factor_idx=i-n_blocks-1
            coefficient['term_factors']=[names[j] for j in terms[factor_idx]]
            coefficient['effect']=2*coefficient['estimate']
            coefficient['effect_se']=2*coefficient['standard_error']
        for suffix in ('low','high'):
            ci=coefficient['ci_'+suffix]
            coefficient['effect_ci_'+suffix]=None if coefficient['effect'] is None or ci is None else 2*ci
        for key in ('effect','effect_se','effect_ci_low','effect_ci_high'):
            if coefficient[key] is not None and not math.isfinite(coefficient[key]):raise ValueError('Factor effect exceeds supported numeric range.')
    result.update(method='Two-level factorial coded OLS; hierarchical selected terms',
        response_name=response.name,factor_coding=coding,terms=all_term_names,
        factor_terms=term_names,block_terms=block_names,include_blocks=include_blocks,
        blocks=len(unique_blocks) if has_multiple_blocks else 1,
        max_order=max(map(len,terms)),selected_terms=[list(term) for term in terms],row_indices=used,used_rows=used,missing=n-len(used),
        coded_factors=coded_rows,native_parity=False,
        assumptions='Independent errors with common variance and normality for t/F inference. Selected hierarchical terms are fitted in coded units; effects equal twice coefficients. Omitted effects are assumed negligible.')
    if not include_blocks:
        result['warnings'].append('Limited coded analysis: no multiple blocks, response-surface/Taguchi models, curvature test or native parity. Omitted effects are assumed negligible.')
    if metadata.get('schema')=='statcraft-regular-fractional-v1':
        matching=len(factors)==len(metadata.get('factors',[])) and all(
            f.get('column_index')==index and f.get('name')==column.name for f,index,column in zip(metadata['factors'],factors,selected))
        if matching:
            from .fractional import alias_structure
            structure=alias_structure(metadata.get('generators'),k)
            for row in coded_rows:
                if all(value==0 for value in row):continue
                for word in structure['defining_relation']:
                    product=math.prod(row[i] for i in range(k) if word['mask']&(1<<i))
                    if product!=word['sign']:raise ValueError('Factor settings no longer match the saved fractional generators.')
            result['design_resolution']=structure['resolution']
            result['alias_structure']=[{'term':row['term'],'aliases':row['expression']} for row in structure['rows']]
            result['warnings'].append('Fractional estimates combine aliased effects; aliases are not separately estimable.')
            result['warnings'].append('Alias table describes the nominal corner fraction, excluding center rows. Letters follow the factor coding table.')
    corners={tuple(row) for row in coded_rows if all(v!=0 for v in row)}
    if len(corners)<2**k:result['warnings'].append('Not every full-factorial corner is present; estimates rely on the chosen model and retained full-rank rows.')
    if any(all(v==0 for v in row) for row in coded_rows):result['warnings'].append('Center runs included without a separate curvature term; lack-of-fit and pure error are not separated.')
    return result


def _level_or_missing(value):
    return normalize_numeric(value)
