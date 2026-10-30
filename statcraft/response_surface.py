"""Independent full/fractional blocked response-surface designs and quadratic OLS."""
import itertools,math,random
import numpy as np
from scipy import stats
from .model import Column,Worksheet,finite_number
from .doe import _coding,_integer
from .regression import multiple_regression
from .glm import settings


def create(factors,kind='central_composite',centers=6,replicates=1,alpha_mode='rotatable',alpha=1.4142135623730951,levels_define='cube',randomize=True,seed=1,name='Response surface design',fraction=1,blocks=1,center_cube=None,center_axial=None,block_replicates=False):
    from .response_surface_catalog import preset,cube_plan,box_plan
    if kind not in ('central_composite','box_behnken'):raise ValueError('Choose central composite or Box-Behnken.')
    if not isinstance(factors,list):raise ValueError('Enter a list of continuous factors.')
    k=len(factors);_integer(k,2 if kind=='central_composite' else 3,10,'Factor count')
    _integer(fraction,1,8,'Cube fraction');_integer(blocks,1,10,'Base blocks')
    spec=preset(kind,k,fraction,blocks)
    _integer(centers,1,1000,'Center points per replicate');_integer(replicates,1,100,'Replicates');_integer(seed,-(2**63),2**63-1,'Seed')
    if type(randomize) is not bool or type(block_replicates) is not bool:raise ValueError('Choose valid randomization and block-replicate settings.')
    if alpha_mode not in ('default','rotatable','face','custom') or levels_define not in ('cube','axial'):raise ValueError('Choose valid alpha and level settings.')
    if center_cube is None and center_axial is None:
        if blocks==1:cc,ca=centers,0
        else:
            ratio=spec['center_cube']/spec['centers'];cc=round(centers*ratio);ca=centers-cc
    else:
        cc=0 if center_cube is None else center_cube;ca=0 if center_axial is None else center_axial
        _integer(cc,0,1000,'Cube center points');_integer(ca,0,1000,'Axial center points')
    if kind=='box_behnken' and ca:raise ValueError('Box-Behnken designs have no axial block.')
    if blocks==1 and ca:raise ValueError('An unblocked design has one common center-point pool.')
    n_cube=2**k//fraction
    if kind=='box_behnken':a=1.
    elif alpha_mode=='face':a=1.
    elif alpha_mode=='custom':a=finite_number(alpha)
    elif alpha_mode=='default' and blocks>1:a=math.sqrt(n_cube*(2*k+ca)/(2*(n_cube+cc)))
    else:a=n_cube**.25
    if not 0<a<=5:raise ValueError('Alpha must lie above zero and at most 5.')
    if alpha_mode=='custom' and a<1:raise ValueError('Custom alpha must lie between 1 and 5.')
    names={'stdorder','runorder','pttype','blocks'};coding=[]
    for i,f in enumerate(factors):
        if not isinstance(f,dict) or set(f)!={'name','low','high'}:raise ValueError('Each factor requires name, low and high.')
        label=f['name']
        if not isinstance(label,str) or not label.strip() or label!=label.strip() or len(label)>128 or label.casefold() in names:raise ValueError('Use unique factor names, distinct from design columns, up to 128 characters.')
        names.add(label.casefold());c=_coding(label,f['low'],f['high'])
        if kind=='central_composite' and levels_define=='axial':c['half_range']/=a;c['low']=c['center']-c['half_range'];c['high']=c['center']+c['half_range']
        if not c['low']<c['center']<c['high']:raise ValueError('Axial-defined cube levels exceed supported numeric precision.')
        c['column_index']=4+i;coding.append(c)
    plan=[]
    if kind=='central_composite':
        cube_blocks=max(1,blocks-1);plan=cube_plan(k,fraction,cube_blocks)
        for b in range(1,cube_blocks+1):plan.extend((0,[0.]*k,b) for _ in range(cc//cube_blocks+(b<=cc%cube_blocks)))
        axial_block=blocks if blocks>1 else 1
        for i in range(k):
            for sign in (-1,1):row=[0.]*k;row[i]=sign*a;plan.append((-1,row,axial_block))
        plan.extend((0,[0.]*k,axial_block) for _ in range(ca))
    else:
        plan=box_plan(k,blocks)
        for b in range(1,blocks+1):plan.extend((0,[0.]*k,b) for _ in range(cc//blocks+(b<=cc%blocks)))
    # Legacy unblocked order places centers after the axial points.
    if kind=='central_composite' and blocks==1:
        plan=[r for r in plan if r[0]!=0]+[r for r in plan if r[0]==0]
    if len(plan)*replicates>4096:raise ValueError('The design exceeds 4096 runs.')
    coords=np.asarray([r[1] for r in plan]);x=np.column_stack([np.ones(len(plan))]+[coords[:,i] for i in range(k)]+[coords[:,i]**2 for i in range(k)]+[coords[:,i]*coords[:,j] for i,j in itertools.combinations(range(k),2)])
    bvec=np.asarray([r[2] for r in plan]);indicators=[(bvec==b).astype(float) for b in range(2,blocks+1)]
    augmented=np.column_stack([x]+indicators) if indicators else x
    if np.linalg.matrix_rank(augmented)<augmented.shape[1]:raise ValueError('The requested design aliases quadratic terms or block effects. Add center points or choose another design.')
    means=[np.mean(x[bvec==b,1:],axis=0) for b in range(1,blocks+1)]
    orthogonal=all(np.allclose(means[0],v,atol=1e-10,rtol=1e-10) for v in means[1:])
    rows=[]
    for replicate in range(replicates):
        for point,coords0,b in plan:
            values=[c['center']+c['half_range']*v for c,v in zip(coding,coords0)]
            if any(not math.isfinite(v) for v in values):raise ValueError('Axial factor settings exceed finite numeric range.')
            rows.append([len(rows)+1,point,b+replicate*blocks if block_replicates else b]+values)
    if randomize:
        rng=random.Random(seed)
        if blocks>1 or block_replicates:
            grouped=[]
            for b in sorted({r[2] for r in rows}):
                group=[r for r in rows if r[2]==b];rng.shuffle(group);grouped.extend(group)
            rows=grouped
        else:rng.shuffle(rows)
    columns=[Column('StdOrder',values=[r[0] for r in rows]),Column('RunOrder',values=list(range(1,len(rows)+1))),Column('PtType',values=[r[1] for r in rows]),Column('Blocks',values=[r[2] for r in rows])]
    columns += [Column(c['name'],values=[r[3+i] for r in rows],metadata={'rsm_coding':{'low':c['low'],'high':c['high']}}) for i,c in enumerate(coding)]
    if not isinstance(name,str) or not name.strip() or name!=name.strip() or len(name)>128:raise ValueError('Enter a worksheet name up to 128 characters.')
    return Worksheet(name,columns,metadata={'doe':dict(schema='statcraft-response-surface-v1',design=kind,factors=coding,alpha=a,levels_define=levels_define,centers=cc+ca,replicates=replicates,randomize=randomize,seed=seed,blocks=blocks*replicates if block_replicates else blocks,base_blocks=blocks,fraction=fraction,center_cube=cc,center_axial=ca,block_replicates=block_replicates,orthogonal_blocks=orthogonal,quadratic_rank=int(np.linalg.matrix_rank(x)),native_parity=False,warnings=[] if orthogonal else ['Custom settings do not provide orthogonal blocks. Block and model estimates may be correlated.'])})


def full_terms(count):return [[i] for i in range(count)]+[[i,i] for i in range(count)]+[list(t) for t in itertools.combinations(range(count),2)]


def validate_terms(terms,count):
    allowed=full_terms(count)
    if not isinstance(terms,list) or not terms or len(terms)>65 or any(not isinstance(t,list) or any(type(i) is not int for i in t) or t not in allowed for t in terms):raise ValueError('Choose supported linear, square and two-factor interaction terms.')
    if len({tuple(t) for t in terms})!=len(terms):raise ValueError('Model terms must be unique.')
    for t in terms:
        if any([i] not in terms for i in t):raise ValueError('Keep each main effect required by a square or interaction.')
    if any([i] not in terms for i in range(count)):raise ValueError('Include each selected factor main effect, or remove that factor.')
    return terms


def default_coding(worksheet,indices):
    result=[]
    for i in indices:
        c=worksheet.columns[i];stored=c.metadata.get('rsm_coding')
        if isinstance(stored,dict) and set(stored)=={'low','high'}:result.append(dict(stored))
        else:
            values=c.numeric_values()
            if not values or min(values)==max(values):raise ValueError('A factor needs varying numeric settings: '+c.name)
            result.append(dict(low=min(values),high=max(values)))
    return result


def fit(worksheet,response_index,factor_indices,coding=None,terms=None,options=None,block_index=None):
    if block_index is not None:
        from .response_surface_blocked import fit as fit_blocked
        return fit_blocked(worksheet,response_index,factor_indices,coding,terms,options,block_index)
    o=settings(options);indices=list(factor_indices);k=len(indices)
    if not 2<=k<=10 or len(set(indices+[response_index]))!=k+1 or any(type(i) is not int or not 0<=i<len(worksheet.columns) for i in indices+[response_index]):raise ValueError('Choose a separate response and 2–10 distinct numeric factors.')
    cols=[worksheet.columns[i] for i in indices];response=worksheet.columns[response_index]
    if any(c.kind!='number' for c in cols+[response]):raise ValueError('Response surface models require numeric factors and response.')
    coding=default_coding(worksheet,indices) if coding is None else coding
    if not isinstance(coding,list) or len(coding)!=k or any(not isinstance(c,dict) or set(c)!={'low','high'} for c in coding):raise ValueError('Enter low/high coding settings for each factor.')
    codes=[_coding(c.name,v['low'],v['high']) for c,v in zip(cols,coding)]
    terms=validate_terms(full_terms(k) if terms is None else terms,k)
    length=max(len(c.values) for c in cols+[response])
    if length>20000:raise ValueError('Response surface fitting supports at most 20,000 input rows.')
    rows=[r for r in range(length) if all(r<len(c.values) and c.values[r] is not None for c in cols+[response])]
    if not rows:raise ValueError('No complete response/factor rows remain.')
    encoded=[[(c.values[r]-code['center'])/code['half_range'] for r in rows] for c,code in zip(cols,codes)]
    x=[];names=[]
    for term in terms:
        v=np.ones(len(rows))
        with np.errstate(over='raise',invalid='raise'):
            try:
                for i in term:v*=encoded[i]
            except FloatingPointError as exc:raise ValueError('Polynomial terms exceed finite numeric range.') from exc
        x.append(v.tolist());names.append('*'.join(cols[i].name for i in term))
    y=[response.values[r] for r in rows];result=multiple_regression(x,y,o['confidence'],names)
    design=np.asarray(x).T;means=np.asarray([math.fsum(design[:,i]/len(rows)) for i in range(len(x))]);z=design-means;z/=np.max(np.abs(z),axis=0);z=np.column_stack([np.ones(len(rows)),z])
    u,_,_=np.linalg.svd(z,full_matrices=False);leverage=np.minimum(1.,np.maximum(0.,np.sum(u*u,axis=1)))
    centered=np.asarray(y)-math.fsum(np.asarray(y)/len(y));scale=float(max(abs(centered)));target=centered/scale
    before=result['ss_total'];anova=[]
    for i,(term,label,coef) in enumerate(zip(terms,names,result['coefficients'][1:])):
        a=z[:,:i+2];res=target-a@np.linalg.lstsq(a,target,rcond=None)[0];after=float(res@res)*scale*scale
        seq=max(0.,before-after);before=after
        # One degree of freedom per scalar polynomial term; Wald t^2 equals partial F.
        adj=0. if result['status']=='exact_fit' else coef['t']**2*result['ms_error']
        if result['status']=='exact_fit':
            keep=[j for j in range(z.shape[1]) if j!=i+1];a=z[:,keep];res=target-a@np.linalg.lstsq(a,target,rcond=None)[0];adj=max(0.,float(res@res)*scale*scale)
        ss=adj if o['ss_type']=='adjusted' else seq;f=ss/result['ms_error'] if result['status']!='exact_fit' else None
        anova.append(dict(source=label,df=1,seq_ss=seq,adj_ss=adj,ms=ss,f=f,p_value=None if f is None else float(stats.f.sf(f,1,result['df_error']))))
    groups={}
    for position,r in enumerate(rows):groups.setdefault(tuple(c.values[r] for c in cols),[]).append(y[position])
    pure=sum(sum((v-math.fsum(g)/len(g))**2 for v in g) for g in groups.values());df_pure=len(rows)-len(groups);df_lof=len(groups)-len(x)-1;lof=max(0.,result['ss_error']-pure)
    f_lof=(lof/df_lof)/(pure/df_pure) if df_lof>0 and df_pure>0 and pure>0 and result['status']!='exact_fit' else None
    diagnostics=[]
    for i,r in enumerate(rows):
        h=float(leverage[i]);denom=1-h;se=result['residual_stdev']*math.sqrt(max(0.,denom));residual=result['residuals'][i];std=residual/se if se>0 and denom>1e-14 else None
        diagnostics.append(dict(row=r+1,response=y[i],fit=result['fitted'][i],residual=residual,standardized_residual=std,leverage=h,cooks_distance=std**2*h/((len(x)+1)*denom) if std is not None else None,flag=('R' if std is not None and abs(std)>2 else '')+('X' if h>3*(len(x)+1)/len(rows) else '')))
    result.update(analysis='response_surface',method='Response Surface Regression — coded ordinary least squares',response_name=response.name,options=o,plot_residuals=o['graphs']!='none',row_indices=rows,missing=length-len(rows),coding_information=codes,factor_information=[],terms=[list(t) for t in terms],anova_terms=anova,diagnostics=diagnostics,
        lack_of_fit=dict(df=df_lof,ss=lof,ms=lof/df_lof if df_lof>0 else None,f=f_lof,p_value=float(stats.f.sf(f_lof,df_lof,df_pure)) if f_lof is not None else None),pure_error=dict(df=df_pure,ss=pure,ms=pure/df_pure if df_pure>0 else None),
        assumptions='One-block numeric-factor polynomial model with an intercept and independent normal errors of constant variance for inference. Factors use (setting − midpoint) / half range. Complete model rows are omitted together. Lack-of-fit separates exact repeated factor settings; it requires both lack-of-fit and pure-error degrees of freedom and positive pure error.')
    return result


def design_summary(sheet,display='summary'):
    if display not in ('none','summary','full'):raise ValueError('Choose a valid design result display.')
    d=sheet.metadata['doe'];r=dict(analysis='response_surface_design',design='Central composite' if d['design']=='central_composite' else 'Box-Behnken',runs=sheet.row_count,factors=len(d['factors']),blocks=d.get('blocks',1),alpha=d['alpha'],center_points_per_replicate=d['centers'],replicates=d['replicates'],randomized=d['randomize'],seed=d['seed'],factor_coding=d['factors'],fraction=d.get('fraction',1),cube_center_points=d.get('center_cube',d['centers']),axial_center_points=d.get('center_axial',0),orthogonal_blocks=d.get('orthogonal_blocks',True),warnings=d.get('warnings',[]),convention='Standard order identifies the original plan; run order identifies collection order. Blocks label distinct experimental conditions; replicated blocks are kept separate when requested. Add a numeric response after collecting measurements.')
    if display=='full':r['design_table']=[dict(zip(sheet.headers,sheet.row(i))) for i in range(sheet.row_count)]
    return r
