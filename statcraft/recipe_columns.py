"""Keep saved analysis recipes attached to their source columns after structure edits."""
import copy
from .recipes import columns

FIELDS = ('recipe', 'dependencies', 'source_unavailable')
LIST_COLUMNS = {'process_indices','component_indices','variable_indices','subgroup_indices','group_indices','response_indices','indices', 'predictor_indices', 'factor_indices', 'covariate_indices', 'by_indices', 'new_indices','continuous_indices','categorical_indices','selected_indices'}


def state(entry):
    return {key:copy.deepcopy(entry[key]) for key in FIELDS if key in entry}


def restore(entry, snapshot):
    for key in FIELDS:
        if key in snapshot: entry[key]=copy.deepcopy(snapshot[key])
        else: entry.pop(key,None)


def capture(presenter, target):
    snapshots=[]
    for entry in presenter.history:
        if entry.get('origin')!='statcraft' or 'recipe' not in entry:
            continue
        try:
            if presenter.result_worksheet(entry) is target:
                snapshots.append({'entry':entry,'before':state(entry)})
        except ValueError:
            continue
    return snapshots


def remap_recipe(recipe, mapping):
    """Only schema-defined column selectors move; factor-term ordinals do not."""
    columns(recipe)
    updated=copy.deepcopy(recipe)
    from .analysis_bindings import ACTIONS, NUMERIC_ACTIONS, remap_settings, remap_numeric_settings
    if updated['action'] in ACTIONS and 'settings' in updated['parameters']:
        updated['parameters']['settings'] = remap_settings(updated['action'], updated['parameters']['settings'], mapping)
        columns(updated)
        return updated
    if updated['action'] in NUMERIC_ACTIONS and 'settings' in updated['parameters']:
        updated['parameters']['settings'] = remap_numeric_settings(updated['action'], updated['parameters']['settings'], mapping)
        columns(updated)
        return updated
    if updated['action'] in ('optimize_mixture_multi','evaluate_mixture_multi'):
        for item in updated['parameters']['responses']:
            item['model_recipe']=remap_recipe(item['model_recipe'],mapping)
        columns(updated)
        return updated
    if updated['action']=='optimize_responses':
        for item in updated['parameters']['responses']:
            item['model_recipe']=remap_recipe(item['model_recipe'],mapping)
        for c in updated['parameters']['options']['constraints']:
            c['index']=mapping[c['index']]
        for s in updated['parameters']['options']['starting_values']:
            s['index']=mapping[s['index']]
        columns(updated)
        return updated
    for key,value in updated['parameters'].items():
        if key in ('source_recipe','model_recipe'):
            updated['parameters'][key]=remap_recipe(value,mapping)
        elif key in LIST_COLUMNS and value is not None:
            updated['parameters'][key]=[None if index is None else mapping[index] for index in value]
        elif key=='index' or key.endswith('_index'):
            if value is not None: updated['parameters'][key]=mapping[value]
    if updated['action'] in ('factorial_plots','model_contour_plot','model_surface_plot'):
        holds=updated['parameters'].get('options',{}).get('hold_values',[])
        if isinstance(holds,list):
            for item in holds:
                item['index']=mapping[item['index']]
    columns(updated)
    return updated


def remap(snapshots, old_columns, new_columns):
    positions={id(column):index for index,column in enumerate(new_columns)}
    mapping={index:positions[id(column)] for index,column in enumerate(old_columns) if id(column) in positions}
    return remap_mapping(snapshots,mapping)


def remap_mapping(snapshots,mapping):
    changed=[]
    for record in snapshots:
        entry=record['entry']
        if not entry.get('source_unavailable'):
            try:
                requested=columns(entry['recipe'])
                if any(index not in mapping for index in requested):
                    entry['source_unavailable']='A source column was deleted. Undo the deletion or run a new analysis with existing columns.'
                else:
                    entry['recipe']=remap_recipe(entry['recipe'],mapping)
                    dependencies=copy.deepcopy(entry.get('dependencies',[]))
                    for dependency in dependencies: dependency['index']=mapping[dependency['index']]
                    entry['dependencies']=sorted(dependencies,key=lambda item:item['index'])
            except (ValueError,KeyError,TypeError,IndexError):
                # A malformed/unsupported historical recipe must never silently
                # become a different valid analysis through position reuse.
                entry['source_unavailable']='The historical source recipe cannot be safely remapped after a column structure change.'
        record['after']=state(entry)
        if record['before']!=record['after']: changed.append(record)
    return changed
