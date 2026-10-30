"""Recover explicit refit setups from observed native MPX model state.

Only declarative, unweighted, untransformed continuous response-surface models
are accepted. Native command/history text is never interpreted or executed.
Saved reports remain separate immutable snapshots. All column joins use native
UUIDs and saved internal variable IDs, never names or current C positions.
"""
import copy
import math
from .native_mpx_outputs import _Reader
from .glm import settings
from .response_surface import validate_terms

MAX_MODELS=100


def _number(value):
    return type(value) in (int,float) and math.isfinite(value) and abs(value)<1e29


def _integer(value,label):
    if not _number(value) or int(value)!=value:raise ValueError('Invalid saved '+label+'.')
    return int(value)


def _dict(value,label):
    if not isinstance(value,dict):raise ValueError('Missing or malformed saved '+label+'.')
    return value


def _items(value,label,maximum):
    if not isinstance(value,list) or len(value)>maximum:raise ValueError('Missing or malformed saved '+label+'.')
    return value


def _source_columns(sheet):
    found={}
    for index,column in enumerate(sheet.columns):
        raw=column.metadata.get('imported_variable_metadata',{})
        identity=raw.get('Id') if isinstance(raw,dict) else None
        if isinstance(identity,str) and identity:
            if identity in found:raise ValueError('Ambiguous duplicate native column identity in the worksheet.')
            found[identity]=index
    return found


def _decode(project,model,uri,declared_id,commands):
    model=_dict(model,'model');metadata=_dict(model.get('metadata'),'model metadata')
    cid=metadata.get('command_id');wid=metadata.get('worksheet_id')
    if not isinstance(cid,str) or not cid or wid not in project.worksheet_ids:raise ValueError('The saved model has no available source worksheet or command identity.')
    command=commands.get(cid)
    if command is None:raise ValueError('The saved model command is absent or ambiguous.')
    if command.get('InputWorksheet')!=wid and command.get('OutputWorksheet')!=wid:raise ValueError('The saved model and command refer to different worksheets.')
    if metadata.get('model_type')!='response_surface_regression':raise ValueError('Unsupported native model type.')
    model_id=_integer(metadata.get('model_id'),'model identity')
    if declared_id is not None and _integer(declared_id,'declared model identity')!=model_id:raise ValueError('Native model identities disagree.')
    sheet=project.worksheets[project.worksheet_ids.index(wid)];sources=_source_columns(sheet)
    variables=_dict(model.get('variables'),'model variables');target=_dict(variables.get('target'),'response variable')
    predictors=_items(variables.get('predictors'),'continuous predictors',10)
    if not 2<=len(predictors)<=10:raise ValueError('Refitting supports 2–10 continuous factors.')
    block=variables.get('block');roles=[target]+predictors+([] if block is None else [_dict(block,'block variable')])
    if set(variables)-{'target','predictors','block'}:raise ValueError('The native model uses additional unsupported variable roles.')
    ids=[];internal={};indices=[]
    for position,variable in enumerate(roles):
        variable=_dict(variable,'variable reference');identity=variable.get('id')
        if not isinstance(identity,str) or identity not in sources:raise ValueError('A saved model column identity is unavailable in its worksheet.')
        if identity in ids:raise ValueError('Saved response, factors and blocks must have distinct identities.')
        ids.append(identity);internal_id=_integer(variable.get('variable_id'),'variable identity')
        if internal_id in internal:raise ValueError('Ambiguous saved internal variable identity.')
        internal[internal_id]=identity;index=sources[identity];indices.append(index)
        expected='categorical' if block is not None and position==len(roles)-1 else 'continuous'
        if variable.get('type')!=expected:raise ValueError('The native model contains an unsupported predictor type.')
        if variable.get('data_type')!=('text' if sheet.columns[index].kind=='text' else 'numeric'):raise ValueError('The source data type conflicts with its saved native variable type.')
        if (expected=='continuous' and sheet.columns[index].kind!='number') or (expected=='categorical' and sheet.columns[index].kind not in ('number','text')):raise ValueError('The source column type no longer matches its saved model role.')
    response=indices[0];factors=indices[1:1+len(predictors)];block_index=indices[-1] if block is not None else None
    state=_dict(_dict(model.get('model_information'),'model information').get('input_state'),'input state')
    obj=_dict(_dict(model.get('post_analysis_data'),'post-analysis data').get('model_object'),'model object')
    if obj.get('model_object_type')!='response_surface' or obj.get('model_analysis_type')!='response_surface':raise ValueError('Unsupported native post-analysis model.')
    if state.get('include_constant_term') is not True:raise ValueError('Native no-intercept models cannot be reconstructed by this response-surface fitter.')
    if state.get('coding') not in ('effects','effect'):raise ValueError('Only the observed native effects coding is supported for refitting.')
    if state.get('standardized') is not False:raise ValueError('Native standardized predictor models are not yet supported.')
    if state.get('link_function_type')!='none' or obj.get('link_function_type')!='none':raise ValueError('Native linked/generalized response models are not supported here.')
    if state.get('confidence_interval')!='two_sided':raise ValueError('Native one-sided model inference is not supported here.')
    if state.get('selection_method')!='none' or state.get('validation_type')!='none':raise ValueError('Native model selection or validation procedures cannot be replayed by a fixed-model refit.')
    continuous=_dict(state.get('continuous_response_model_data'),'continuous-response settings')
    if continuous.get('box_cox') is not False or obj.get('lambda')!=1:raise ValueError('Native transformed responses are not supported for this refit.')
    if obj.get('has_weights') is not False or obj.get('weights_column_id') not in (0,0.0):raise ValueError('Native weighted models are not supported for this refit.')
    if obj.get('is_categorical_response') is not False or obj.get('is_event_trial') is not False or obj.get('is_mle') is not False:raise ValueError('Native non-OLS response models are not supported here.')
    rows=_dict(_dict(obj.get('rows_to_use'),'row selection').get('rows'),'row selection')
    if rows.get('use_all_rows') is not True:raise ValueError('Native row-subset models need a supported row-selection workflow before refitting.')
    confidence=state.get('confidence')
    if not _number(confidence) or not 0<confidence<1 or confidence!=obj.get('confidence'):raise ValueError('Native confidence settings are invalid or inconsistent.')
    termlist=_dict(obj.get('model_term_list'),'post-analysis term list')
    post_predictors=_items(termlist.get('model_predictors'),'post-analysis predictors',12)
    positions={identity:i for i,identity in enumerate(ids[1:1+len(predictors)])}
    post_ids={};coding=[None]*len(predictors);block_levels=[];constants=0
    for pred in post_predictors:
        pred=_dict(pred,'post-analysis predictor');pid=_integer(pred.get('predictor_id'),'predictor identity')
        if pid in post_ids:raise ValueError('Duplicate native predictor identity.')
        typ=pred.get('predictor_type')
        if typ=='constant':
            if pid!=-1 or pred.get('column_id')!=0:raise ValueError('Invalid native intercept identity.')
            post_ids[pid]='constant';constants+=1;continue
        column_id=_integer(pred.get('column_id'),'post-analysis column identity');identity=internal.get(column_id)
        if identity not in ids[1:]:raise ValueError('Post-analysis predictor does not match a declared source variable.')
        if pred.get('was_predictor_fit') is not True or pred.get('is_random') is not False or pred.get('is_hard_to_change') is not False or pred.get('nesting_predictor_ids'):
            raise ValueError('Native random, nested, excluded or hard-to-change predictors are not supported here.')
        if identity in positions:
            if typ!='continuous':raise ValueError('Native factor types disagree across model state.')
            levels=_items(pred.get('numeric_levels'),'factor coding levels',2)
            if len(levels)!=2 or not all(_number(v) for v in levels) or not levels[0]<levels[1]:raise ValueError('The saved factor has no valid low/high coding levels.')
            coding[positions[identity]]={'low':levels[0],'high':levels[1]}
        else:
            if block is None or identity!=ids[-1] or typ!='block':raise ValueError('Unexpected categorical predictor in native response-surface model.')
            block_levels=pred.get('text_levels') if sheet.columns[block_index].kind=='text' else pred.get('numeric_levels')
            block_levels=_items(block_levels,'block levels',32)
            if len(block_levels)<2 or len(set(block_levels))!=len(block_levels):raise ValueError('Invalid native fixed-block levels.')
            if block.get('classes')!=block_levels:raise ValueError('Native fixed-block levels disagree across model state.')
        post_ids[pid]=identity
    if constants!=1 or len(post_ids)!=1+len(predictors)+(block is not None) or any(c is None for c in coding):raise ValueError('The saved model has an incomplete predictor/coding map.')
    inputs=_dict(state.get('termlist'),'input term list');input_terms=[];block_terms=0
    fixed=_items(inputs.get('fixed_factor_columns'),'fixed factor identities',11)
    fixed_ids=[_dict(v,'fixed factor').get('id') for v in fixed]
    if len(fixed_ids)!=len(ids)-1 or set(fixed_ids)!=set(ids[1:]):raise ValueError('Native input factors disagree with the declared model variables.')
    for term in _items(inputs.get('model_terms'),'input model terms',66):
        columns=_items(_dict(term,'input term').get('term_columns'),'input term columns',2)
        identities=[_dict(v,'term variable').get('id') for v in columns]
        if any(internal.get(_integer(v.get('variable_id'),'input term variable identity'))!=v.get('id') for v in columns):raise ValueError('Input term variable identities disagree.')
        if block is not None and identities==[ids[-1]]:block_terms+=1;continue
        if not identities or any(v not in positions for v in identities):raise ValueError('Unsupported block interaction or unknown input model term.')
        input_terms.append(sorted(positions[v] for v in identities))
    validate_terms(input_terms,len(factors))
    if block_terms!=(1 if block is not None else 0):raise ValueError('Native block term inclusion is inconsistent.')
    reference_terms=[];post_terms=[];constant_terms=0;post_block_terms=0
    for term in _items(termlist.get('model_terms'),'saved model terms',67):
        term=_dict(term,'saved model term');pids=_items(term.get('predictor_ids'),'saved term predictor identities',2)
        identities=[post_ids.get(_integer(v,'term predictor identity')) for v in pids]
        coefficients=_items(term.get('coefficients'),'saved coefficients',32);ses=_items(term.get('standard_error_coefficients'),'saved coefficient standard errors',32)
        if not coefficients or len(coefficients)!=len(ses) or not all(_number(v) for v in coefficients+ses) or any(v<0 for v in ses):raise ValueError('Invalid saved coefficient data.')
        if identities==['constant']:
            if len(coefficients)!=1:raise ValueError('Invalid intercept coefficient dimension.')
            constant_terms+=1;reference_terms.append({'kind':'constant','estimate':coefficients[0],'standard_error':ses[0]})
        elif block is not None and identities==[ids[-1]]:
            if len(coefficients)!=len(block_levels):raise ValueError('Native block coefficient dimensions disagree with block levels.')
            post_block_terms+=1
            reference_terms.extend({'kind':'block','level':level,'estimate':value,'standard_error':se} for level,value,se in zip(block_levels,coefficients,ses))
        else:
            if not identities or any(v not in positions for v in identities) or len(coefficients)!=1:raise ValueError('Unsupported native saved polynomial term.')
            normalized=sorted(positions[v] for v in identities);post_terms.append(normalized)
            reference_terms.append({'kind':'polynomial','term':normalized,'estimate':coefficients[0],'standard_error':ses[0]})
    if constant_terms!=1 or post_block_terms!=block_terms or len(post_terms)!=len(input_terms) or {tuple(v) for v in post_terms}!={tuple(v) for v in input_terms}:raise ValueError('Input and saved model terms disagree.')
    tables=metadata.get('tables',{});graphs=metadata.get('graphs',{});o=settings()
    o.update(confidence=confidence,coding='effect',ss_type='sequential' if continuous.get('sequential_sum_of_squares') else 'adjusted',graphs='four' if graphs.get('display_fourpack') or any(graphs.get(k) for k in ('display_histogram','display_normal','display_fits','display_order')) else 'none')
    for key,saved_key in [('method','display_method_table'),('anova','display_anova_table'),('model_summary','display_summary_table'),('coefficients','display_coefficients')]:
        if type(tables.get(saved_key)) is bool:o[key]=tables[saved_key]
    o['diagnostics']='all' if tables.get('all_diagnostic_rows') else 'unusual' if tables.get('display_diagnostics_table',True) else 'none'
    recipe={'action':'analyze_response_surface','parameters':dict(response_index=response,factor_indices=factors,coding=coding,terms=input_terms,options=o)}
    if block is not None:recipe['parameters']['block_index']=block_index
    from .recipes import columns
    columns(recipe)
    mse=obj.get('mean_square_error');df=_integer(obj.get('error_degrees_of_freedom'),'error degrees of freedom')
    if not _number(mse) or mse<0 or df<1:raise ValueError('Invalid native residual inference state.')
    return {'supported':True,'command_id':cid,'worksheet_id':wid,'worksheet_name':sheet.name,'model_id':model_id,'model_uri':uri,'recipe':recipe,
            'source_column_map':{str(index):identity for index,identity in zip(indices,ids)},
            'source_column_ids':{'response':ids[0],'factors':ids[1:1+len(factors)],'block':ids[-1] if block is not None else None},
            'verification_reference':{'coefficients':reference_terms,'mse':mse,'df_error':df,'row_count':_integer(rows.get('row_count'),'saved row count'),'coding':'effect'},
            'warnings':['Refit is an independent StatCraft calculation using current worksheet values; saved native output remains unchanged.']}


def read_native_models(project):
    """Return command-ID keyed supported setups or explicit unsupported reasons.

    This function parses metadata only; it neither fits a model nor mutates the
    supplied project. Missing members and unsupported semantics remain visible.
    """
    if project is None:return {}
    metadata=project.metadata if isinstance(project.metadata,dict) else {};reader=_Reader(project.retained_members)
    commands={};ambiguous=set()
    command_collection=metadata.get('Commands',{})
    command_items=command_collection.get('Items',[]) if isinstance(command_collection,dict) else []
    if not isinstance(command_items,list):command_items=[]
    for item in command_items[:1000]:
        if not isinstance(item,dict) or not isinstance(item.get('Id'),str):continue
        if item['Id'] in commands:ambiguous.add(item['Id'])
        commands[item['Id']]=item
    for cid in ambiguous:commands.pop(cid,None)
    result={};processed=0
    model_collection=metadata.get('Models',{})
    model_items=model_collection.get('Items',[]) if isinstance(model_collection,dict) else []
    if not isinstance(model_items,list):model_items=[]
    for family in model_items[:64]:
        if not isinstance(family,dict) or family.get('Type')!='ResponseSurfaceRegression':continue
        family_items=family.get('Items',[])
        if not isinstance(family_items,list):continue
        for item in family_items[:MAX_MODELS]:
            if not isinstance(item,dict):continue
            uri=item.get('Data');processed+=1
            if processed>MAX_MODELS:return result
            if not isinstance(uri,str) or not uri.startswith('/models/') or '..' in uri.split('/') or '\\' in uri:continue
            raw=reader.resolve(uri);model=raw.get('Model') if isinstance(raw,dict) else None
            model_meta=model.get('metadata',{}) if isinstance(model,dict) else {};cid=model_meta.get('command_id')
            key=cid if isinstance(cid,str) and cid else uri
            try:descriptor=_decode(project,model,uri,item.get('Id'),commands)
            except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError,RecursionError) as exc:
                descriptor={'supported':False,'command_id':cid,'worksheet_id':model_meta.get('worksheet_id'),'model_uri':uri,'error':str(exc),'warnings':['The native model cannot be refitted automatically: '+str(exc)]}
            if key in result:
                result[key]={'supported':False,'command_id':cid,'model_uri':uri,'error':'Multiple saved models claim the same command identity.','warnings':['Ambiguous saved native model identity; automatic refit is unavailable.']}
            else:result[key]=descriptor
    return result


def compare_native_model(result,descriptor,relative_tolerance=1e-7,absolute_tolerance=1e-9):
    """Compare an explicit fresh fit with saved native coefficient/inference data.

    This is a bounded same-data comparison, not a native execution oracle.
    Differences are reported, never hidden or used to overwrite native output.
    """
    reference=descriptor.get('verification_reference')
    if not descriptor.get('supported') or not isinstance(reference,dict):raise ValueError('Select a supported recovered native model.')
    if not isinstance(result,dict) or result.get('analysis')!='response_surface':raise ValueError('Compare a fitted response-surface result.')
    if not _number(relative_tolerance) or not _number(absolute_tolerance) or relative_tolerance<0 or absolute_tolerance<0:raise ValueError('Comparison tolerances must be finite and nonnegative.')
    coefficients=result.get('coefficients',[]);terms=result.get('surface_terms',result.get('terms',[]));levels=result.get('block_levels',[])
    count=max(0,len(levels)-1);polynomial={tuple(term):coefficients[1+count+i] for i,term in enumerate(terms) if 1+count+i<len(coefficients)}
    blocks={level:coefficients[1+i] for i,level in enumerate(levels[:-1]) if 1+i<len(coefficients)}
    comparisons=[]
    def append(label,actual,expected):
        matched=_number(actual) and _number(expected) and math.isclose(actual,expected,rel_tol=relative_tolerance,abs_tol=absolute_tolerance)
        comparisons.append({'label':label,'actual':actual,'native':expected,'difference':actual-expected if _number(actual) and _number(expected) else None,'matches':bool(matched)})
    for item in reference['coefficients']:
        if item['kind']=='constant':actual=coefficients[0] if coefficients else {};label='Constant'
        elif item['kind']=='polynomial':actual=polynomial.get(tuple(item['term']),{});label='Term '+str(item['term'])
        else:
            # The effect-coded reference level is expanded natively but absent
            # as an independent parameter. Compare only free coefficients.
            if item['level'] not in blocks:continue
            actual=blocks[item['level']];label='Block '+str(item['level'])
        append(label,actual.get('estimate'),item['estimate']);append(label+' SE',actual.get('standard_error'),item['standard_error'])
    append('MSE',result.get('ms_error'),reference['mse']);append('Error DF',result.get('df_error'),reference['df_error'])
    return {'matches_saved_native':bool(comparisons) and all(v['matches'] for v in comparisons),'comparisons':comparisons,'relative_tolerance':relative_tolerance,'absolute_tolerance':absolute_tolerance,'scope':'Saved native coefficients, free coefficient standard errors, residual mean square and error degrees of freedom; independent fresh fit, not native execution.'}


def resolve_model_recipe(project,descriptor):
    """Resolve current source positions by native identity after worksheet edits."""
    if not isinstance(descriptor,dict) or not descriptor.get('supported') or not isinstance(descriptor.get('recipe'),dict):
        raise ValueError('Select a supported recovered native model.')
    wid=descriptor.get('worksheet_id')
    if project is None or wid not in project.worksheet_ids:raise ValueError('The native model source worksheet is unavailable.')
    sheet=project.worksheets[project.worksheet_ids.index(wid)];columns=_source_columns(sheet)
    identities=descriptor['source_column_ids'];recipe=copy.deepcopy(descriptor['recipe']);p=recipe['parameters']
    try:
        p['response_index']=columns[identities['response']]
        p['factor_indices']=[columns[identity] for identity in identities['factors']]
        if identities['block'] is not None:p['block_index']=columns[identities['block']]
    except KeyError as exc:raise ValueError('A recovered native model source column was deleted or lost its identity.') from exc
    from .recipes import columns as recipe_columns
    recipe_columns(recipe)
    return recipe


def resolve_entry_recipe(entry, worksheet=None):
    """Extract and resolve the typed model recipe from a StatCraft or native entry."""
    if not isinstance(entry, dict) or entry.get('source_unavailable'):
        return None
    origin = entry.get('origin')
    if origin == 'native':
        if not entry.get('native_model', {}).get('supported'):
            return None
        nm = entry['native_model']
        recipe = copy.deepcopy(nm.get('recipe'))
        if not isinstance(recipe, dict) or not recipe.get('parameters'):
            return None
        if worksheet is not None:
            ws_name = getattr(worksheet, 'name', None)
            entry_ws_name = entry.get('worksheet_name') or nm.get('worksheet_name')
            if ws_name and entry_ws_name and ws_name != entry_ws_name:
                return None
            try:
                cols = _source_columns(worksheet)
                identities = nm.get('source_column_ids', {})
                p = recipe['parameters']
                if identities.get('response') in cols:
                    p['response_index'] = cols[identities['response']]
                if identities.get('factors'):
                    p['factor_indices'] = [cols[fid] for fid in identities['factors'] if fid in cols]
                if identities.get('block') and identities['block'] in cols:
                    p['block_index'] = cols[identities['block']]
            except Exception:
                pass
        return recipe
    raw = entry.get('recipe')
    return copy.deepcopy(raw) if isinstance(raw, dict) else None
