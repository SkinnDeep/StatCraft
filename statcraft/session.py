"""Original inert session format, separate from native commands and output."""
import copy
import json
from . import io

MEMBER = '/statcraft/session.json'
SCHEMA = 'statcraft-session'


def validate(records, worksheet_ids):
    if not isinstance(records, list) or len(records) > 100:
        raise io.FormatError('Session results must be an array of at most 100 entries.')
    for entry in records:
        if (not isinstance(entry, dict) or
                not isinstance(entry.get('title'), str) or len(entry['title']) > 4096 or
                not isinstance(entry.get('time'), str) or len(entry['time']) > 100 or
                not isinstance(entry.get('result'), dict) or
                entry.get('origin') != 'statcraft' or
                entry.get('worksheet_id') not in worksheet_ids or
                not isinstance(entry.get('worksheet_name'), str)):
            raise io.FormatError('Invalid saved StatCraft result entry or worksheet reference.')
        if 'source_unavailable' in entry and (not isinstance(entry['source_unavailable'],str) or not entry['source_unavailable'] or len(entry['source_unavailable'])>4096):
            raise io.FormatError('Invalid saved source-column availability state.')
        if entry['result'].get('graph')=='categorical_points':
            from .categorical_points import validate_result
            try:validate_result(entry['result'])
            except (ValueError,TypeError,KeyError,IndexError) as exc:raise io.FormatError('Invalid saved categorical graph: '+str(exc)) from exc
        if entry['result'].get('graph')=='dotplot_graphs':
            from .dotplot_graphs import validate_result
            try:validate_result(entry['result'])
            except (ValueError,TypeError,KeyError,IndexError) as exc:raise io.FormatError('Invalid saved dotplot: '+str(exc)) from exc
        if entry['result'].get('graph')=='boxplot_graphs':
            from .boxplot_graphs import validate_result
            try:validate_result(entry['result'])
            except (ValueError,TypeError,KeyError,IndexError) as exc:raise io.FormatError('Invalid saved boxplot: '+str(exc)) from exc
        if entry['result'].get('graph')=='histogram_graphs':
            from .histogram_graphs import validate_result
            try:validate_result(entry['result'])
            except (ValueError,TypeError,KeyError,IndexError) as exc:raise io.FormatError('Invalid saved histogram: '+str(exc)) from exc
        if entry['result'].get('graph') in ('panel_graph','graph_layout'):
            from .compositions import validate_composition
            try:validate_composition(entry['result'])
            except ValueError as exc:raise io.FormatError('Invalid saved graph composition: '+str(exc)) from exc
        from .brushing import brushable_rows
        try:brushable_rows(entry)
        except ValueError as exc:raise io.FormatError('Invalid graph source rows: '+str(exc)) from exc
        if 'graph_presentation' in entry:
            from .graph_presentation import validate_presentation
            try:validate_presentation(entry['graph_presentation'])
            except ValueError as exc:raise io.FormatError('Invalid saved graph presentation: '+str(exc)) from exc
        if 'graph_styles' in entry:
            from .graph_styles import validate_styles
            try:validate_styles(entry['graph_styles'])
            except ValueError as exc:raise io.FormatError('Invalid saved graph styles: '+str(exc)) from exc
        if 'histogram_settings' in entry:
            from .histogram_options import validate_histogram_settings,build_histogram_panel
            try:
                if entry['result'].get('graph')!='histogram':raise ValueError('Histogram settings require a histogram.')
                build_histogram_panel(entry['result'].get('histogram_source'),validate_histogram_settings(entry['histogram_settings']))
            except ValueError as exc:raise io.FormatError('Invalid saved histogram settings: '+str(exc)) from exc
    try:
        raw = json.dumps({'schema': SCHEMA, 'version': 1, 'results': records},
                         ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (ValueError, TypeError, RecursionError, OverflowError) as exc:
        raise io.FormatError('Session results must contain finite JSON data.') from exc
    if len(raw) > io.MAX_MEMBER_BYTES:
        raise io.FormatError('Saved session exceeds the member size limit.')
    return raw


def decode(raw, worksheet_ids):
    document = io._json(raw)
    if (not isinstance(document, dict) or document.get('schema') != SCHEMA or
            type(document.get('version')) is not int or document['version'] != 1 or
            set(document) != {'schema', 'version', 'results'}):
        raise io.UnsupportedFormatError('Unsupported StatCraft session schema/version.')
    validate(document['results'], worksheet_ids)
    return copy.deepcopy(document['results'])
