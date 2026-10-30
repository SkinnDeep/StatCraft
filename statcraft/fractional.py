"""Original bounded regular fractions and exact signed defining-group algebra.

NIST primary construction/alias references:
https://www.itl.nist.gov/div898/handbook/pri/section3/pri3342.htm
https://www.itl.nist.gov/div898/handbook/pri/section3/pri3343.htm
Factor letters A..H denote positions, independently of actual display names.
No native metadata/parity, blocks, optimality search or nonregular designs.
"""
import itertools
import random
import re
from .doe import _integer, _coding
from .model import Column, Worksheet


def _term(mask,factor_count):
    return ''.join(chr(65+i) for i in range(factor_count) if mask&(1<<i)) or 'I'


def _record(mask,sign,k):
    return dict(term=_term(mask,k),sign=sign,order=mask.bit_count(),mask=mask)


def _parse(generators,factor_count):
    _integer(factor_count,2,8,'Factor count')
    if not isinstance(generators,dict) or not generators:
        raise ValueError('A regular fraction requires at least one generated factor.')
    labels=[chr(65+i) for i in range(factor_count)]
    if any(not isinstance(k,str) or len(k)!=1 or k not in labels for k in generators):
        raise ValueError('Generated-factor keys must be uppercase positional letters A..H within the factor count.')
    bases=[letter for letter in labels if letter not in generators]
    if len(bases)<2:raise ValueError('At least two independent base factors are required.')
    occupied={1<<labels.index(letter) for letter in bases}
    parsed=[];normalized={}
    for letter in sorted(generators):
        expression=generators[letter]
        if not isinstance(expression,str):raise ValueError('Generator products must be signed base-factor strings.')
        expression=expression.strip().upper()
        if not re.fullmatch(r'[+-]?[A-H](?:\*?[A-H])*',expression):
            raise ValueError('Use a signed product of base-factor letters, for example ABC or -A*B*C.')
        sign=-1 if expression.startswith('-') else 1
        product=expression.lstrip('+-').replace('*','')
        if len(set(product))!=len(product):raise ValueError('Generator products may not repeat a factor letter.')
        if any(l not in bases for l in product):raise ValueError('Generators may reference only independent base factors.')
        mask=sum(1<<labels.index(l) for l in product)
        if mask in occupied:raise ValueError('Generated columns cannot duplicate or negate a base or another generated column.')
        occupied.add(mask)
        product=''.join(sorted(product));normalized[letter]=('-' if sign<0 else '')+product
        parsed.append((letter,mask,sign))
    return labels,bases,parsed,normalized


def alias_structure(generators,factor_count,max_order=3):
    """Return JSON-safe exact signed defining relation and alias rows.

    Each row satisfies row.term = alias.sign * alias.term on fraction corners.
    max_order restricts row seeds, never truncates their complete alias orbit.
    Identity I has mask0/sign1. Center runs do not satisfy corner alias identities.
    """
    _integer(max_order,1,3,'Maximum alias seed order')
    labels,bases,parsed,normalized=_parse(generators,factor_count)
    group={0:1}
    for letter,base_mask,sign in parsed:
        word=base_mask^(1<<labels.index(letter))
        for mask,prior_sign in list(group.items()):
            new_mask=mask^word;new_sign=prior_sign*sign
            if new_mask in group and group[new_mask]!=new_sign:
                raise ValueError('Generator signs create an inconsistent defining relation.')
            group[new_mask]=new_sign
    if any(mask.bit_count() in (1,2) for mask in group if mask):
        raise ValueError('The defining group aliases an identity/main effect or duplicate factor columns.')
    defining=[_record(mask,group[mask],factor_count) for mask in sorted(group,key=lambda m:(m.bit_count(),_term(m,factor_count)))]
    resolution=min(mask.bit_count() for mask in group if mask)
    seeds=[0]+[sum(1<<i for i in term) for order in range(1,min(max_order,factor_count)+1) for term in itertools.combinations(range(factor_count),order)]
    rows=[]
    for seed in seeds:
        aliases=[_record(seed^mask,sign,factor_count) for mask,sign in group.items()]
        aliases.sort(key=lambda a:(a['order'],a['term']))
        other=[a for a in aliases if a['mask']!=seed]
        expression=_term(seed,factor_count)+''.join(' = '+('-' if a['sign']<0 else '')+a['term'] for a in other)
        rows.append(dict(term=_term(seed,factor_count),mask=seed,aliases=aliases,expression=expression))
    return dict(factor_count=factor_count,base_factors=bases,generators=normalized,
                defining_relation=defining,resolution=resolution,max_order=min(max_order,factor_count),rows=rows,
                convention='Each seed term equals signed aliases on fraction corner runs; centers excluded.',native_parity=False)


def create_fractional(factors,generators,replicates=1,centers=0,randomize=True,seed=1,blocks=1):
    """Create one regular fraction, single or multiple blocks, first base factor fastest.

    Standard/run order and point types follow StatCraft full-factorial creation.
    All center settings are actual midpoints, not generator products of zeros.
    """
    factors=list(factors);k=len(factors)
    labels,bases,parsed,normalized=_parse(generators,k)
    _integer(replicates,1,20,'Replicates');_integer(centers,0,20,'Center runs')
    _integer(blocks,1,64,'Blocks')
    _integer(seed,-(2**63),2**63-1,'Randomization seed')
    if type(randomize) is not bool:raise ValueError('Randomize must be true or false.')
    total_corners=2**len(bases)*replicates
    if total_corners%blocks!=0:
        raise ValueError('Total corner runs must be evenly divisible by the number of blocks.')
    count=total_corners+(centers*blocks)
    if count>4096:raise ValueError('The fraction exceeds the 4096-run limit.')
    names={s.casefold() for s in ('StdOrder','RunOrder','PtType','Blocks')};coding=[]
    for i,factor in enumerate(factors):
        if not isinstance(factor,dict):raise ValueError('Factors require name, low and high fields.')
        name=factor.get('name')
        if not isinstance(name,str) or not name.strip() or name.casefold() in names:
            raise ValueError('Factor names must be nonempty, unique and different from design-column names.')
        names.add(name.casefold())
        if 'low' not in factor or 'high' not in factor:raise ValueError('Each factor requires low and high settings.')
        code=_coding(name,factor['low'],factor['high']);code.update(letter=labels[i],column_index=4+i);coding.append(code)
    alias=alias_structure(normalized,k)
    corners_per_rep=2**len(bases); corners_per_block=total_corners//blocks
    corner_runs=[]
    for rep in range(replicates):
        for corner in range(corners_per_rep):
            codes={letter:1 if corner&(1<<j) else -1 for j,letter in enumerate(bases)}
            for letter,mask,sign in parsed:
                value=sign
                for base in bases:
                    if mask&(1<<labels.index(base)):value*=codes[base]
                codes[letter]=value
            settings=[f['high'] if codes[f['letter']]>0 else f['low'] for f in coding]
            if blocks==replicates: b=rep+1
            elif blocks==1: b=1
            elif blocks%replicates==0:
                sub_blocks=blocks//replicates
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
    return Worksheet('Regular fractional factorial design',columns,metadata={'doe':dict(
        schema='statcraft-regular-fractional-v1',origin='Original StatCraft design',
        design='regular two-level fractional factorial',factors=coding,base_factors=bases,
        generators=normalized,defining_relation=alias['defining_relation'],resolution=alias['resolution'],
        alias_structure=alias,replicates=replicates,centers=centers,randomize=randomize,seed=seed,blocks=blocks,
        standard_order='Runs grouped by block; first base factor fastest within block; centers per block.',
        point_types={'factorial':1,'center':0},native_parity=False)})
