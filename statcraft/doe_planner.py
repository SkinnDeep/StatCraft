"""A unified, side-effect-free DOE planner over original bounded generators."""
import copy
import math
from .model import Worksheet

KINDS=('full_factorial','fractional_factorial','general_factorial','plackett_burman',
       'central_composite','box_behnken','taguchi','simplex_centroid','simplex_lattice',
       'extreme_vertices','custom_optimal')


def build_plan(kind,factors,replicates=1,centers=0,randomize=True,seed=1,blocks=1,options=None,name='DOE plan'):
    if kind not in KINDS:raise ValueError('Choose a supported design family.')
    if not isinstance(name,str) or not name.strip() or name!=name.strip() or len(name)>128:
        raise ValueError('Use a worksheet name of 1–128 characters without surrounding blanks.')
    if type(blocks) is not int or blocks<1 or type(replicates) is not int or replicates<1 or replicates%blocks:
        raise ValueError('Complete-replicate blocks must divide the number of replicates.')
    if options is not None and not isinstance(options,dict):raise ValueError('Design options must be an object.')
    options=copy.deepcopy(options or {})
    configuration=dict(kind=kind,factors=copy.deepcopy(factors),replicates=replicates,centers=centers,
                       randomize=randomize,seed=seed,blocks=blocks,options=options,name=name)
    if kind in ('full_factorial','fractional_factorial'):
        allowed={'generators'} if kind=='fractional_factorial' else set()
        if set(options)-allowed:raise ValueError('Unknown factorial design options.')
        if kind=='fractional_factorial':
            from .fractional import create_fractional
            if not options.get('generators'):raise ValueError('Specify the fractional design generators.')
            sheet=create_fractional(factors,options['generators'],replicates,centers,randomize,seed,blocks=blocks)
        else:
            from .doe import create_factorial
            sheet=create_factorial(factors,replicates,centers,randomize,seed,blocks=blocks)
        sheet.name=name
    elif kind in ('central_composite','box_behnken'):
        if blocks!=1:raise ValueError('Response surface designs currently support one block in the planner.')
        if set(options)-{'alpha'}:raise ValueError('Unknown response surface design options.')
        alpha=options.get('alpha','rotatable')
        if isinstance(alpha,str):
            if alpha not in ('rotatable','face_centered'):raise ValueError('Choose rotatable, face-centered or a numeric alpha.')
            mode='face' if alpha=='face_centered' else 'rotatable';value=1.0
        elif isinstance(alpha,(int,float)) and not isinstance(alpha,bool) and math.isfinite(alpha):mode='custom';value=float(alpha)
        else:raise ValueError('Choose a finite numeric alpha.')
        from .response_surface import create
        sheet=create(factors,kind,centers,replicates,mode,value,'cube',randomize,seed,name)
    elif kind in ('general_factorial','plackett_burman','taguchi'):
        from .doe_catalog_designs import create_design
        sheet=create_design(kind,factors,replicates,centers,randomize,seed,blocks,options,name)
    else:
        from .doe_special_designs import create_design
        sheet=create_design(kind,factors,replicates,centers,randomize,seed,blocks,options,name)
    sheet.validate();sheet.metadata['doe']['planner_configuration']=configuration
    return sheet


def summarize(sheet):
    metadata=sheet.metadata['doe'];config=metadata['planner_configuration']
    return {'analysis':'doe_plan','design':config['kind'].replace('_',' ').title(),
            'runs':sheet.row_count,'factor_count':len(config['factors']),
            'replicates':config['replicates'],'blocks':config['blocks'],
            'center_runs':sum(value==0 for value in sheet.columns[2].values),'randomized':config['randomize'],
            'seed':config['seed'],'factors':copy.deepcopy(config['factors']),
            'diagnostics':copy.deepcopy(metadata.get('diagnostics',{})),
            'notes':[note for note in metadata.get('notes',[]) if 'native' not in note.lower() and 'original' not in note.lower()],
            'instructions':'Enter measured responses in new worksheet columns. Use Factorial analysis for two-level designs, General Linear Model for categorical designs, or Response Surface analysis for CCD/Box–Behnken. Mixture-specific response fitting and Taguchi signal-to-noise analysis are not included in this planner.'}


def format_plan(result):
    lines=[result['design'],f"Runs: {result['runs']}    Factors: {result['factor_count']}    Blocks: {result['blocks']}",
           f"Replicates: {result['replicates']}    Added center runs: {result['center_runs']}",
           'Run order: '+('Randomized' if result['randomized'] else 'Standard')+f"    Seed: {result['seed']}", '', 'Factors']
    for f in result['factors']:
        values=f.get('levels')
        lines.append(f['name']+': '+(', '.join(map(str,values)) if values is not None else str(f.get('low'))+' to '+str(f.get('high'))))
    if result['diagnostics']:
        lines.extend(['','Design diagnostics'])
        for key,value in result['diagnostics'].items():
            if not isinstance(value,(dict,list)):lines.append(key.replace('_',' ').title()+': '+str(value))
    lines.extend(['',result['instructions'],*result['notes']])
    return '\n'.join(lines)
