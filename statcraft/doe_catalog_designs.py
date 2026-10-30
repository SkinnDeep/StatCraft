"""Original bounded factorial, Hadamard screening and orthogonal-array designs.

PB matrices use Sylvester or prime-order Paley constructions. Taguchi arrays use
finite-field linear contrasts (or the verified Hadamard L12). Array equivalence
and orthogonality do not establish native column assignments or row ordering.
"""
from copy import deepcopy
from itertools import product
import math
import random

from .model import Column, Worksheet, finite_number

PB_RUNS = (4,8,12,16,20,24,32,48,64)
TAGUCHI_ARRAYS = {
    'L4': {'runs':4,'levels':2,'capacity':3},
    'L8': {'runs':8,'levels':2,'capacity':7},
    'L9': {'runs':9,'levels':3,'capacity':4},
    'L12': {'runs':12,'levels':2,'capacity':11},
    'L16': {'runs':16,'levels':2,'capacity':15},
    'L16_4': {'runs':16,'levels':4,'capacity':5},
    'L25': {'runs':25,'levels':5,'capacity':6},
    'L27': {'runs':27,'levels':3,'capacity':13},
    'L32': {'runs':32,'levels':2,'capacity':31},
    'L8_MIXED': {'runs':8,'levels':'one 4-level and up to four 2-level factors','capacity':5},
}
MAX_RUNS = 4096


def _integer(value,minimum,maximum,label):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ValueError(f'{label} must be an integer from {minimum} to {maximum}.')
    return value


def _factors(factors):
    if not isinstance(factors,(list,tuple)) or not 2<=len(factors)<=63:
        raise ValueError('Specify 2 to 63 factors.')
    names={name.casefold() for name in ('StdOrder','RunOrder','PtType','Blocks')}
    result=[]
    for factor in factors:
        if not isinstance(factor,dict) or set(factor)-{'name','kind','levels'}:
            raise ValueError('Each factor must specify name, kind and explicit levels only.')
        name=factor.get('name')
        if not isinstance(name,str) or not name.strip() or len(name)>256:
            raise ValueError('Each factor requires a nonblank name of at most 256 characters.')
        name=name.strip()
        if name.casefold() in names:
            raise ValueError('Factor names must be unique and different from design columns.')
        names.add(name.casefold())
        kind=factor.get('kind')
        if kind not in ('number','text'):
            raise ValueError('Factor kind must be number or text.')
        values=factor.get('levels')
        if not isinstance(values,(list,tuple)) or not 2<=len(values)<=100:
            raise ValueError('Each factor requires 2 to 100 explicit levels.')
        if kind=='number':
            levels=[finite_number(value) for value in values]
        else:
            if any(not isinstance(value,str) or not value.strip() or len(value)>10000 for value in values):
                raise ValueError('Text levels must be nonblank strings of at most 10000 characters.')
            levels=list(values)
        if len(levels)!=len(set(levels)):
            raise ValueError('Factor levels must be distinct within each factor.')
        result.append({'name':name,'kind':kind,'levels':levels,'column_index':4+len(result)})
    return result


def _hadamard(order):
    """Normalized +/-1 matrix with orthogonal columns for supported orders."""
    if order not in PB_RUNS:
        raise ValueError('Unsupported screening run count. Choose '+', '.join(map(str,PB_RUNS))+'.')
    if order & (order-1)==0:
        matrix=[[1 if (row&column).bit_count()%2==0 else -1 for column in range(order)] for row in range(order)]
        construction='Sylvester Hadamard'
    else:
        q=order-1
        # Supported non-powers are q=11,19,23,47: prime, q=3 (mod 4).
        residues={(value*value)%q for value in range(1,q)}
        matrix=[[1]*order]
        for row in range(q):
            matrix.append([1]+[-1 if row==column else 1 if (row-column)%q in residues else -1 for column in range(q)])
        construction=f'Paley Hadamard over prime field GF({q})'
    # This is a construction invariant, not a substitute for the external tests.
    if any(sum(matrix[row][a]*matrix[row][b] for row in range(order))!=(order if a==b else 0)
           for a in range(order) for b in range(a,order)):
        raise ValueError('Hadamard construction failed its orthogonality invariant.')
    return matrix,construction


def _field_multiply(left,right,q):
    if q!=4:
        return left*right%q
    # GF(4)=GF(2)[x]/(x^2+x+1); coefficients encoded as two bits.
    result=0
    while right:
        if right&1:result^=left
        right>>=1
        left<<=1
        if left&4:left^=7
    return result


def _field_add(left,right,q):
    return left^right if q==4 else (left+right)%q


def _linear_array(q,dimension):
    """Strength-two OA from one representative per finite-field 1D subspace."""
    vectors=[]
    for vector in product(range(q),repeat=dimension):
        nonzero=next((value for value in vector if value),None)
        if nonzero==1:vectors.append(vector)
    rows=[]
    for point in product(range(q),repeat=dimension):
        values=[]
        for vector in vectors:
            total=0
            for left,right in zip(point,vector):
                total=_field_add(total,_field_multiply(left,right,q),q)
            values.append(total)
        rows.append(values)
    return rows


def _taguchi(factors,array):
    level_counts=[len(factor['levels']) for factor in factors]
    homogeneous=len(set(level_counts))==1
    mixed=level_counts.count(4)==1 and all(count in (2,4) for count in level_counts) and 1<=level_counts.count(2)<=4
    if array is not None:
        if not isinstance(array,str):raise ValueError('Taguchi array must be a catalogue name.')
        key=array.strip().upper()
        if key in ('','AUTO'):array=None
        else:array=key
    if array=='L16' and homogeneous and level_counts[0]==4:array='L16_4'
    if array=='L8' and mixed:array='L8_MIXED'
    if array is None:
        if mixed:array='L8_MIXED'
        elif homogeneous:
            available=[key for key,item in TAGUCHI_ARRAYS.items() if item['levels']==level_counts[0] and item['capacity']>=len(factors)]
            if not available:raise ValueError('No supported orthogonal array accommodates these levels and factor count.')
            array=min(available,key=lambda key:TAGUCHI_ARRAYS[key]['runs'])
        else:
            raise ValueError('Supported mixed array: one 4-level factor with up to four 2-level factors in L8.')
    if array not in TAGUCHI_ARRAYS:raise ValueError('Unsupported Taguchi array.')
    spec=TAGUCHI_ARRAYS[array]
    if array=='L8_MIXED':
        if not mixed:raise ValueError('Mixed L8 requires one 4-level factor and one to four 2-level factors.')
        rows=[]
        for a,b,c in product(range(2),repeat=3):
            twos=[c,c^a,c^b,c^a^b]
            which=0;row=[]
            for count in level_counts:
                if count==4:row.append(a*2+b)
                else:row.append(twos[which]);which+=1
            rows.append(row)
        return rows,'L8 (4^1 2^4)', 'GF(2) contrast-column collapse with pairwise orthogonality',array
    if not homogeneous or level_counts[0]!=spec['levels'] or len(factors)>spec['capacity']:
        raise ValueError('Factor levels or count do not fit the selected Taguchi array.')
    if array=='L12':
        h,_=_hadamard(12)
        rows=[[0 if value==1 else 1 for value in row[1:]] for row in h]
    else:
        q=spec['levels'];dimension=0;count=spec['runs']
        while count>1:
            count//=q;dimension+=1
        rows=_linear_array(q,dimension)
    rows=[row[:len(factors)] for row in rows]
    label=f"L{spec['runs']} ({spec['levels']}^{spec['capacity']})"
    return rows,label,f"Projective finite-field contrasts over GF({spec['levels']})" if array!='L12' else 'Paley Hadamard strength-two orthogonal array',array


def create_design(kind,factors,replicates=1,centers=0,randomize=True,seed=1,blocks=1,options=None,name='DOE plan'):
    """Create an original worksheet plan with <=4096 physical runs.

    Blocks may be one or complete replicate blocks. Centers are counted per
    block, and require exclusively numeric two-level factors. Taguchi centers,
    arbitrary block confounding, noise/signal arrays and other catalogue designs
    are unavailable and rejected explicitly.
    """
    if kind not in ('general_factorial','plackett_burman','taguchi'):
        raise ValueError('Choose general_factorial, plackett_burman or taguchi.')
    coding=_factors(factors)
    _integer(replicates,1,20,'Replicates');_integer(centers,0,100,'Center runs')
    _integer(blocks,1,20,'Blocks');_integer(seed,-(2**63),2**63-1,'Randomization seed')
    if type(randomize) is not bool:raise ValueError('Randomize must be Boolean.')
    if not isinstance(name,str) or not name.strip() or len(name)>256:
        raise ValueError('Worksheet name must be nonblank text of at most 256 characters.')
    if blocks not in (1,replicates):
        raise ValueError('Blocks must be 1 or the replicate count (one complete replicate per block).')
    if options is not None and not isinstance(options,dict):raise ValueError('Design options must be an object.')
    opts=deepcopy(options or {})
    allowed={'runs'} if kind=='plackett_burman' else {'array'} if kind=='taguchi' else set()
    if set(opts)-allowed:raise ValueError('Unsupported options for this design family.')
    array=None;array_key=None;warnings=[]
    if kind=='general_factorial':
        base_runs=math.prod(len(factor['levels']) for factor in coding)
        if base_runs*replicates+centers*blocks>MAX_RUNS:
            raise ValueError('The design exceeds the 4096-run limit.')
        # Reversing product order makes the first factor change fastest.
        codes=[list(reversed(row)) for row in product(*(range(len(factor['levels'])) for factor in reversed(coding)))]
        construction='Cartesian product of explicitly declared factor levels'
    elif kind=='plackett_burman':
        if any(len(factor['levels'])!=2 for factor in coding):raise ValueError('Plackett-Burman factors require exactly two levels.')
        order=opts.get('runs')
        if order is None:
            order=next((value for value in PB_RUNS if value>len(coding)),None)
        if type(order) is not int or order not in PB_RUNS or len(coding)>=order:
            raise ValueError('Choose a supported run count greater than the number of factors.')
        matrix,construction=_hadamard(order)
        codes=[[0 if value==-1 else 1 for value in row[1:len(coding)+1]] for row in matrix]
        warnings.append('Screening main effects can be confounded with interactions; this plan does not estimate a full interaction model.')
    else:
        if centers:raise ValueError('Center points are unavailable for Taguchi orthogonal arrays.')
        codes,array,construction,array_key=_taguchi(coding,opts.get('array'))
        warnings.append('Array strength-two balance is verified; native row order, interaction assignments and robust-parameter noise arrays are unverified.')
    base_runs=len(codes)
    total=base_runs*replicates+centers*blocks
    if total>MAX_RUNS:raise ValueError('The design exceeds the 4096-run limit.')
    center_values=None
    if centers:
        if any(factor['kind']!='number' or len(factor['levels'])!=2 for factor in coding):
            raise ValueError('Center points require exclusively numeric two-level factors.')
        center_values=[]
        for factor in coding:
            left,right=factor['levels']
            midpoint=math.fsum((left/2,right/2))
            if not math.isfinite(midpoint) or not min(left,right)<midpoint<max(left,right):
                raise ValueError('A center setting cannot be represented strictly between the declared levels.')
            center_values.append(midpoint)
    groups={block:[] for block in range(1,blocks+1)}
    for replicate in range(replicates):
        block=replicate+1 if blocks==replicates else 1
        for row in codes:
            groups[block].append({'settings':[factor['levels'][level] for factor,level in zip(coding,row)],'point':1,'block':block,'replicate':replicate+1})
    for block in groups:
        groups[block].extend({'settings':list(center_values),'point':0,'block':block,'replicate':None} for _ in range(centers))
    standard=[]
    for rows in groups.values():standard.extend(rows)
    for ordinal,row in enumerate(standard,1):row['standard_order']=ordinal
    plan=[];rng=random.Random(seed)
    for rows in groups.values():
        physical=list(rows)
        if randomize:rng.shuffle(physical)
        plan.extend(physical)
    columns=[Column('StdOrder',values=[row['standard_order'] for row in plan]),
             Column('RunOrder',values=list(range(1,total+1))),
             Column('PtType',values=[row['point'] for row in plan]),
             Column('Blocks',values=[row['block'] for row in plan])]
    columns.extend(Column(factor['name'],factor['kind'],[row['settings'][at] for row in plan]) for at,factor in enumerate(coding))
    metadata={'schema':'statcraft-catalog-design-v1','origin':'Original StatCraft design construction',
              'design':kind,'factors':coding,'replicates':replicates,'centers':centers,'blocks':blocks,
              'randomize':randomize,'seed':seed,'base_runs':base_runs,'run_count':total,
              'construction':construction,'array':array,'array_key':array_key,
              'standard_order':'Grouped by complete-replicate block; first general-factorial factor changes fastest; centers last within each block.',
              'point_types':{'design':1,'center':0},'warnings':warnings,'native_parity':False}
    return Worksheet(name.strip(),columns,metadata={'doe':metadata})
