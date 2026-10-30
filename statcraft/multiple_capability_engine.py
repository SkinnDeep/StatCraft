"""Original multiple-variable capability orchestration over typed worksheet data.

Each column or By group is analyzed independently. This module retains source
rows and subgroup boundaries, validates broadcast specifications, and reuses the
existing single-series estimators. Full native numerical parity is unverified.
"""
from copy import deepcopy
import json
import math
import numbers

from .model import display_date
from .value_order import ordered_values

MAX_SERIES = 256

DEFAULT_OPTIONS = {
    'title':'', 'show_graphs':True, 'columns':2, 'confidence_level':95.0,
    'include_ci':False, 'ci_type':'two_sided', 'estimate_method_gt1':'pooled',
    'estimate_method_eq1':'amr', 'unbiased_within':True, 'unbiased_overall':False,
    'analysis_mode':'normal', 'display_unit':'ppm', 'stats_type':'capability',
    'naming_convention':'classical', 'tolerance_k':6.0, 'moving_range_len':2,
}


def _selectors(value, name, *, optional=False, allow_none=False, repeated=False):
    if value is None and optional:
        return []
    if not isinstance(value,(list,tuple)) or (not value and not optional):
        raise ValueError(f'{name} must be a list of column indices.')
    result=list(value)
    if any((entry is None and not allow_none) or (entry is not None and (type(entry) is not int or entry<0)) for entry in result):
        raise ValueError(f'{name} must contain nonnegative integer column indices.')
    selected=[entry for entry in result if entry is not None]
    if not repeated and len(selected)!=len(set(selected)):
        raise ValueError(f'{name} must not contain duplicate columns.')
    return result


def recipe_sources(parameters):
    """Validate source selectors without evaluating a worksheet or fitting data."""
    if not isinstance(parameters,dict):
        raise ValueError('Multiple capability parameters must be an object.')
    variables=_selectors(parameters.get('variable_indices'),'Variables')
    by=_selectors(parameters.get('by_indices'),'By variables',optional=True)
    subgroups=_selectors(parameters.get('subgroup_indices'),'Subgroup columns',optional=True,allow_none=True,repeated=True)
    if by and len(variables)!=1:
        raise ValueError('By variables require exactly one response column.')
    if set(variables)&set(by) or set(variables)&set(subgroups) or set(by)&set(subgroups):
        raise ValueError('Response, By and subgroup columns must use different columns.')
    return sorted(set(variables+by+[entry for entry in subgroups if entry is not None]))


def _broadcast(value, count, name, default=None):
    if value is None:
        return [default]*count
    if isinstance(value,(list,tuple)):
        if len(value)==1:
            return list(value)*count
        if len(value)!=count:
            raise ValueError(f'{name} must contain one value or exactly {count} values in series order.')
        return list(value)
    return [value]*count


def _finite(value, name, *, optional=False, positive=False):
    if value is None and optional:
        return None
    if isinstance(value,bool) or not isinstance(value,numbers.Real) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite and numeric.')
    if positive and value<=0:
        raise ValueError(f'{name} must be positive.')
    return float(value)


def _options(options,method):
    if options is not None and not isinstance(options,dict):
        raise ValueError('Options must be an object.')
    opts=deepcopy(DEFAULT_OPTIONS)
    if options:
        if set(options)-set(opts):
            raise ValueError('Unknown multiple capability options: '+', '.join(map(str,set(options)-set(opts))))
        opts.update(deepcopy(options))
    if not isinstance(opts['title'],str):
        raise ValueError('Title must be text.')
    for key in ('show_graphs','include_ci','unbiased_within','unbiased_overall'):
        if type(opts[key]) is not bool:
            raise ValueError(f'{key} must be Boolean.')
    if type(opts['columns']) is not int or not 1<=opts['columns']<=4:
        raise ValueError('Graph layout columns must be an integer from 1 to 4.')
    confidence=_finite(opts['confidence_level'],'Confidence level')
    if not 0<confidence<100:
        raise ValueError('Confidence level must be strictly between 0 and 100.')
    if opts['ci_type'] not in ('two_sided','lower','upper'):
        raise ValueError('Invalid confidence interval type.')
    for key,choices in [('estimate_method_gt1',('pooled','rbar','sbar')),('estimate_method_eq1',('amr','mmr','srmssd')),
                        ('analysis_mode',('normal','between_within')),('display_unit',('ppm','percent')),
                        ('stats_type',('capability','zbench')),('naming_convention',('classical','aiag_vda'))]:
        if opts[key] not in choices:
            raise ValueError(f'Invalid {key}.')
    if _finite(opts['tolerance_k'],'Tolerance multiplier')!=6:
        raise ValueError('Multiple-variable capability currently supports the six-sigma tolerance multiplier only.')
    if type(opts['moving_range_len']) is not int or opts['moving_range_len']!=2:
        raise ValueError('Multiple-variable capability currently supports moving ranges of length 2 only.')
    if method=='nonnormal':
        unsupported=('include_ci','analysis_mode','display_unit','stats_type','estimate_method_gt1',
                     'estimate_method_eq1','unbiased_within','unbiased_overall','ci_type')
        if any(opts[key]!=DEFAULT_OPTIONS[key] for key in unsupported):
            raise ValueError('The selected normal-only estimation or confidence option is unavailable for nonnormal multiple capability.')
    return opts


def _cell(column,row):
    return column.values[row] if row<len(column.values) else None


def _label(column,value):
    return display_date(value) if column.kind=='date' else str(value)


def _group_rows(worksheet, variable_indices,by_indices):
    if not by_indices:
        return [(index,[],list(range(len(worksheet.columns[index].values)))) for index in variable_indices],[]
    columns=[worksheet.columns[index] for index in by_indices]
    response=worksheet.columns[variable_indices[0]]
    extent=max([len(response.values)]+[len(column.values) for column in columns])
    groups={}; omitted=[]
    for row in range(extent):
        values=tuple(_cell(column,row) for column in columns)
        if any(value is None for value in values):
            omitted.append(row+1)
            continue
        groups.setdefault(values,[]).append(row)
    if not groups:
        raise ValueError('No nonmissing By-variable groups are available.')
    ranks=[]
    for position,column in enumerate(columns):
        levels=ordered_values(column,[key[position] for key in groups])
        ranks.append({value:rank for rank,value in enumerate(levels)})
    keys=sorted(groups,key=lambda key:tuple(ranks[pos][value] for pos,value in enumerate(key)))
    return [(variable_indices[0],list(key),groups[key]) for key in keys],omitted


def analyze_multiple_capability(worksheet,method='normal',variable_indices=None,by_indices=None,
                                subgroup_sizes=1,subgroup_indices=None,lower_specs=None,
                                upper_specs=None,targets=None,distribution='weibull',options=None):
    """Compare independent columns or one response split by ordered By groups.

    Specification sequences correspond to variable order or ordered group order.
    Text groups honor worksheet value order; numeric groups sort numerically;
    combinations use lexicographic order of those ranks. Constant subgroup slots
    retain missing-cell positions. ID subgroups use consecutive runs within each
    series. Nonnormal capability has no within-subgroup estimator.
    """
    if method not in ('normal','nonnormal'):
        raise ValueError('Method must be normal or nonnormal.')
    params={'variable_indices':variable_indices,'by_indices':by_indices,'subgroup_indices':subgroup_indices}
    sources=recipe_sources(params)
    worksheet.validate()
    if any(index>=len(worksheet.columns) for index in sources):
        raise ValueError('A selected source column no longer exists.')
    variables=list(variable_indices); by=list(by_indices or [])
    if any(worksheet.columns[index].kind!='number' for index in variables):
        raise ValueError('Response variables must be numeric columns.')
    opts=_options(options,method)
    if method=='nonnormal' and distribution not in ('weibull','lognormal','exponential','gamma'):
        raise ValueError('Choose Weibull, lognormal, exponential or gamma for nonnormal multiple capability.')
    items,omitted_by=_group_rows(worksheet,variables,by)
    count=len(items)
    if not count:
        raise ValueError('At least one series is required.')
    if count>MAX_SERIES:
        raise ValueError(f'Compare at most {MAX_SERIES} series in one analysis.')
    lows=_broadcast(lower_specs,count,'Lower specs')
    highs=_broadcast(upper_specs,count,'Upper specs')
    centers=_broadcast(targets,count,'Targets')
    if by and isinstance(subgroup_sizes,(list,tuple)) and len(subgroup_sizes)>1:
        raise ValueError('By groups require a shared constant subgroup size or subgroup ID column.')
    if by and subgroup_indices is not None and len(subgroup_indices)>1:
        raise ValueError('By groups require a shared subgroup ID column.')
    sizes=_broadcast(subgroup_sizes,count,'Subgroup sizes',1)
    subindices=_broadcast(subgroup_indices,count,'Subgroup columns',None)
    if method=='nonnormal' and (any(index is not None for index in subindices) or any(size not in (None,1) or isinstance(size,bool) for size in sizes)):
        raise ValueError('Subgroup selectors apply only to normal multiple capability.')
    series=[]; summary=[]
    for position,(variable_index,group_values,source_rows) in enumerate(items):
        column=worksheet.columns[variable_index]
        name=column.name or f'C{variable_index+1}'
        group_label=', '.join(f'{worksheet.columns[index].name or "C"+str(index+1)}={_label(worksheet.columns[index],value)}' for index,value in zip(by,group_values))
        label=name+(' | '+group_label if group_label else '')
        lsl=_finite(lows[position],f'Lower spec for {label}',optional=True)
        usl=_finite(highs[position],f'Upper spec for {label}',optional=True)
        target=_finite(centers[position],f'Target for {label}',optional=True)
        if lsl is None and usl is None:
            raise ValueError(f'{label}: enter at least one specification limit.')
        if lsl is not None and usl is not None and lsl>=usl:
            raise ValueError(f'{label}: lower spec must be less than upper spec.')
        index=subindices[position]
        raw=[_cell(column,row) for row in source_rows]
        ids=[_cell(worksheet.columns[index],row) for row in source_rows] if index is not None else None
        used=[row+1 for at,row in enumerate(source_rows) if raw[at] is not None and (ids is None or ids[at] is not None)]
        missing=[row+1 for at,row in enumerate(source_rows) if raw[at] is None or (ids is not None and ids[at] is None)]
        values=[float(value) for at,value in enumerate(raw) if value is not None and (ids is None or ids[at] is not None)]
        if len(values)<(2 if method=='normal' else 3):
            raise ValueError(f'{label}: insufficient nonmissing observations.')
        if max(values)==min(values):
            raise ValueError(f'{label}: capability requires variation in the observations.')
        if method=='normal':
            from .capability_engine import run_normal_capability
            if ids is not None:
                groups=[]; current=[]; previous=object()
                for value,identifier in zip(raw,ids):
                    if identifier is None:
                        if current:groups.append(current)
                        current=[]; previous=object()
                        continue
                    if identifier!=previous:
                        if current:groups.append(current)
                        current=[]; previous=identifier
                    if value is not None:current.append(float(value))
                if current:groups.append(current)
            else:
                size=sizes[position] if sizes[position] is not None else 1
                if isinstance(size,bool) or not isinstance(size,numbers.Real) or not math.isfinite(size) or int(size)!=size or size<1:
                    raise ValueError(f'{label}: subgroup size must be a positive whole number.')
                size=int(size)
                groups=[[float(value) for value in raw[start:start+size] if value is not None] for start in range(0,len(raw),size)]
                groups=[group for group in groups if group]
            if max(map(len,groups))>1 and not any(max(group)>min(group) for group in groups):
                raise ValueError(f'{label}: within-subgroup variation is zero and capability indices are not estimable.')
            if max(map(len,groups))==1 and opts['estimate_method_eq1']=='mmr':
                ranges=sorted(abs(values[at]-values[at-1]) for at in range(1,len(values)))
                middle=len(ranges)//2
                median=ranges[middle] if len(ranges)%2 else (ranges[middle-1]+ranges[middle])/2
                if median==0:
                    raise ValueError(f'{label}: median moving range is zero and within capability is not estimable.')
            call={key:opts[key] for key in DEFAULT_OPTIONS if key not in ('title','show_graphs','columns')}
            child=run_normal_capability(groups,lsl=lsl,usl=usl,target=target,variable_name=label,**call)
            child.update(analysis='capability',graph='capability')
            normal=True
        else:
            from .capability_nonnormal_engine import run_nonnormal_capability
            child=run_nonnormal_capability(values,dist_or_transform=distribution,lsl=lsl,usl=usl,target=target,
                confidence_level=opts['confidence_level']/100,tolerance_k=opts['tolerance_k'],naming_convention=opts['naming_convention'])
            child.update(variable_name=label,variable=label,graph='capability_nonnormal')
            normal=False
        try:
            json.dumps(child,allow_nan=False)
        except (ValueError,OverflowError) as exc:
            raise ValueError(f'{label}: the selected estimator produced an undefined or nonfinite result.') from exc
        item={'label':label,'variable_index':variable_index,'variable_name':name,'group_values':group_values,
              'group_label':group_label,'rows':used,'missing_rows':missing,'result':child,
              'subgroup_index':index,'subgroup_size':sizes[position] if index is None else None}
        series.append(item)
        indices=child if normal else child['indices']
        observed=child['observed_perf']['total']*(10000 if opts['display_unit']=='percent' else 1) if normal else child['observed_ppm']['total']
        expected=child['overall_perf']['expected_total']*(10000 if opts['display_unit']=='percent' else 1) if normal else child['expected_ppm']['total']
        summary.append({'label':label,'variable_name':name,'group_label':group_label,'n':len(values),
            'lsl':lsl,'usl':usl,'target':target,'cp':indices.get('cp') if normal else None,
            'cpk':indices.get('cpk') if normal else None,'pp':indices.get('pp'),'ppk':indices.get('ppk'),
            'observed_ppm':observed,'expected_ppm':expected})
    warnings=['Each series uses the existing single-series estimator; full native numerical equivalence is unverified.',
              'Specification arrays follow the displayed series order. Text By groups honor worksheet value order; numeric groups sort numerically.']
    if omitted_by:warnings.append(f'{len(omitted_by)} rows with missing By values were omitted.')
    if any(item['missing_rows'] for item in series):warnings.append('Missing observations are omitted independently for each series; constant subgroup slots retain their original positions.')
    return {'analysis':'multiple_capability','graph':'multiple_capability' if opts['show_graphs'] else None,
            'method':method,'title':opts['title'].strip() or f'Multiple Variables Capability Analysis ({method.title()})',
            'options':opts,'series':series,'summary':summary,'group_labels':[item['group_label'] for item in series],
            'variable_indices':variables,'by_indices':by,'omitted_by_rows':omitted_by,'warnings':warnings}
