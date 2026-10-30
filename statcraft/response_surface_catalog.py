"""Original response-surface presets and balanced design construction.

Catalog sizes/center allocation follow the documented native design summaries.
Coordinates use independent GF(2) factorial contrasts and balanced edge groups;
native row ordering and numerical equivalence are not asserted.
"""
import itertools, math
from functools import lru_cache

CCD = [
 (2,1,5,3,3,(2,)), (3,1,6,4,2,(2,3)), (4,1,7,4,2,(2,3)),
 (5,1,10,8,4,(2,3)), (5,2,6,6,1,(2,)),
 (6,1,14,8,6,(2,3,5)), (6,2,9,8,2,(2,3)),
 (7,1,10,8,10,(2,3,5)), (7,2,10,8,4,(2,3,5)),
 (8,2,10,8,8,(2,3,5)), (8,4,10,8,2,(2,3,5)),
 (9,4,10,8,6,(2,3,5)), (10,8,10,8,4,(2,3,5))]
BB_CENTERS={3:3,4:3,5:6,6:6,7:6,9:10,10:10}
BB_BLOCKS={3:(),4:(3,),5:(2,),6:(2,),7:(2,),9:(5,10),10:(2,)}


def catalog():
    out=[]
    for k,f,c,cc,ca,choices in CCD:
        n=2**k//f
        for b in (1,)+choices:
            cube,axial=(c,0) if b==1 else (cc,ca)
            a=n**.25 if b==1 else math.sqrt(n*(2*k+axial)/(2*(n+cube)))
            out.append(dict(kind='central_composite',factors=k,fraction=f,blocks=b,
                            runs=n+2*k+cube+axial,centers=cube+axial,
                            center_cube=cube,center_axial=axial,alpha=a))
    for k,c in BB_CENTERS.items():
        n=4*math.comb(k,2) if k<=5 else {6:48,7:56,9:120,10:160}[k]
        for b in (1,)+BB_BLOCKS[k]:
            out.append(dict(kind='box_behnken',factors=k,fraction=1,blocks=b,
                            runs=n+c,centers=c,center_cube=c,center_axial=0,alpha=1.))
    return out


def preset(kind,k,fraction=1,blocks=1):
    for spec in catalog():
        if (spec['kind'],spec['factors'],spec['fraction'],spec['blocks'])==(kind,k,fraction,blocks):return spec
    raise ValueError('Choose an available response-surface design, fraction, factor count and block count.')


@lru_cache(maxsize=32)
def column_masks(k,fraction):
    p={1:0,2:1,4:2,8:3}.get(fraction)
    if p is None or k-p<2:raise ValueError('Choose full, half, quarter or eighth cube fraction.')
    m=k-p;columns=[1<<i for i in range(m)]
    # A regular fraction with all distinct main and two-factor contrast masks
    # has resolution at least V, so every quadratic-model interaction is clear.
    candidates=sorted((v for v in range(1,2**m) if v.bit_count()>=4),key=lambda x:(x.bit_count(),x))
    def extend(current,start):
        if len(current)==k:return current
        forbidden={0}
        for degree in (1,2,3):
            for group in itertools.combinations(current,degree):
                mask=0
                for value in group:mask^=value
                forbidden.add(mask)
        for index in range(start,len(candidates)):
            candidate=candidates[index]
            if candidate in forbidden:continue
            result=extend(current+[candidate],index+1)
            if result is not None:return result
        return None
    columns=extend(columns,0)
    if columns is None:raise ValueError('No supported resolution-V cube fraction exists for this choice.')
    return tuple(columns)


@lru_cache(maxsize=64)
def block_masks(k,fraction,cube_blocks):
    if cube_blocks==1:return ()
    columns=column_masks(k,fraction);m=k-{1:0,2:1,4:2,8:3}[fraction]
    forbidden=set(columns)|{a^b for a,b in itertools.combinations(columns,2)}|{0}
    choices=[v for v in range(1,2**m) if v not in forbidden]
    needed={2:1,4:2}.get(cube_blocks)
    if needed is None:raise ValueError('Use one, two or four cube blocks.')
    for group in itertools.combinations(choices,needed):
        span={0}
        for value in group:span|={v^value for v in tuple(span)}
        if len(span)==cube_blocks and not (span-{0})&forbidden:return group
    raise ValueError('These cube blocks alias a main effect or two-factor interaction.')


def cube_plan(k,fraction=1,cube_blocks=1):
    columns=column_masks(k,fraction);blocking=block_masks(k,fraction,cube_blocks)
    m=k-{1:0,2:1,4:2,8:3}[fraction]
    rows=[]
    for corner in range(2**m):
        coords=[]
        for mask in columns:
            value=1.
            for bit in range(m):
                if mask&(1<<bit):value*=1. if corner&(1<<bit) else -1.
            coords.append(value)
        block=1+sum(((corner&mask).bit_count()%2)<<i for i,mask in enumerate(blocking))
        rows.append((1,coords,block))
    return rows


def _bb_groups(k):
    if k<=5:return list(itertools.combinations(range(k),2))
    if k==6:return [tuple(sorted({i,(i+1)%6,(i+3)%6})) for i in range(6)]
    if k==7:
        # Lines of the Fano plane: each factor appears in three triples and
        # every pair occurs together once.
        return [tuple(i-1 for i in t) for t in ((4,5,6),(1,6,7),(2,5,7),(1,2,4),(3,4,7),(1,3,5),(2,3,6))]
    if k==9:
        # Four parallel classes of affine lines over GF(3), plus a fifth
        # balanced partition. Every factor occurs five times and all pairs
        # are represented; each parallel class supplies an orthogonal block.
        groups=[]
        for slope in (None,0,1,2):
            for intercept in range(3):
                groups.append(tuple((3*intercept+y if slope is None else 3*x+(slope*x+intercept)%3)
                                    for x,y in ((j,j) for j in range(3))))
        groups.extend(((0,1,3),(2,5,6),(4,7,8)))
        return groups
    if k==10:return [tuple(sorted({i,(i+1)%10,(i+3)%10,(i+5)%10})) for i in range(10)]
    raise ValueError('Box-Behnken designs support 3, 4, 5, 6, 7, 9 or 10 factors.')


def box_plan(k,blocks=1):
    groups=_bb_groups(k);rows=[]
    # Whole edge groups permit orthogonal blocking for 4/5-factor designs;
    # higher-dimensional groups can be split by a high-order sign contrast.
    pairs5=set(tuple(sorted((i,(i+1)%5))) for i in range(5))
    match4={tuple(sorted(pair)):b+1 for b,matching in enumerate((((0,1),(2,3)),((0,2),(1,3)),((0,3),(1,2)))) for pair in matching}
    for index,group in enumerate(groups):
        for signs in itertools.product((-1.,1.),repeat=len(group)):
            coords=[0.]*k
            for i,value in zip(group,signs):coords[i]=value
            b=1
            if blocks>1:
                if k==4:b=match4[group]
                elif k==5:b=1 if group in pairs5 else 2
                elif k==9:
                    b=index//3+1
                    if blocks==10:b=2*(b-1)+(1 if math.prod(signs)<0 else 2)
                else:b=1 if math.prod(signs)<0 else 2
            rows.append((2,coords,b))
    return rows
