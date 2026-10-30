"""Bounded native-column structure edits without reassigning retained identities."""
import copy
from uuid import uuid4
from . import io
from .mpx_append import validate_plain, append_numeric

NEW_ID = 'statcraft_native_column_id'


def preflight(project, sheet):
    """Fail before modifying a sheet containing unknown native dependencies."""
    index = next(i for i, candidate in enumerate(project.worksheets) if candidate is sheet)
    document = project._original_sheets[project.worksheet_uris[index] + '.json']
    validate_plain(document)
    for column in sheet.columns:
        native = column.metadata.get('imported_variable_metadata', {})
        wrapper = native.get('WorksheetVarBody', {})
        if native.get('ReadOnly', False) or wrapper.get('VarData', {}).get('Locked', False):
            raise io.UnsupportedFormatError('Structural edits involving locked native columns are unsupported.')
    original=project._baseline[index]
    extent=max(original.row_count,max((len(c.values) for c in sheet.columns if any(c.metadata==b.metadata for b in original.columns)),default=0))
    prepare_columns(copy.deepcopy(document),sheet.columns,original.columns,extent,
                    copy.deepcopy(project._appended_ids),project.worksheet_uris[index])
    return index


def independent_metadata():
    return {NEW_ID: str(uuid4())}


def prepare_columns(document, columns, originals, row_extent, cache, uri):
    """Return retained baseline matches and native wrappers in the requested order.

    Existing wrappers remain byte-equivalent JSON objects until their values/name
    are edited by the caller. Removed columns' blob members remain in the archive.
    """
    matches = []
    used = set()
    for column in columns:
        candidates = [i for i, base in enumerate(originals) if column.metadata == base.metadata]
        if candidates:
            if len(candidates) != 1 or candidates[0] in used:
                raise io.UnsupportedFormatError('Native column identities are ambiguous or duplicated.')
            position = candidates[0]
            used.add(position)
            if column.kind != originals[position].kind:
                raise io.UnsupportedFormatError('Native column type changes are unverified.')
            matches.append(position)
        else:
            if column.kind != 'number' or set(column.metadata) - {NEW_ID}:
                raise io.UnsupportedFormatError('New native columns must be independent numeric columns.')
            matches.append(None)
    structural = matches != list(range(len(originals)))
    if structural:
        validate_plain(document)
    old = document['Data']['Columns']
    result = []
    for position, (column, original_index) in enumerate(zip(columns, matches)):
        if original_index is not None:
            result.append(old[original_index])
        else:
            clean = copy.deepcopy(column)
            clean.metadata = {}
            # A persistent edit identity survives moves, repeated saves and undo.
            key = column.metadata.get(NEW_ID)
            append_numeric(document, [clean], len(originals), row_extent, cache,
                           uri + ':new:' + key if key else uri + ':position:' + str(position))
            result.append(old[-1])
    document['Data']['Columns'] = result
    if structural and 'MaxColumns_DEP' in document:
        document['MaxColumns_DEP'] = max(io._count(document['MaxColumns_DEP'], 'MaxColumns_DEP'), len(result))
    return matches, structural
