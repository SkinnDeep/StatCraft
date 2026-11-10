"""Independent, bounded typed worksheet reshaping; inputs are never modified."""
from .model import Column, Worksheet
from .io import MAX_CELLS


def _columns(sheet, indices, minimum=1):
    if not isinstance(indices, (list, tuple)) or len(indices)<minimum or len(set(indices))!=len(indices):
        raise ValueError('Choose distinct source columns.')
    if any(type(i) is not int or not 0<=i<len(sheet.columns) for i in indices):
        raise ValueError('Choose existing source columns.')
    return [sheet.columns[i] for i in indices]


def _bound(rows, columns):
    if rows*columns>MAX_CELLS or columns>10000:
        raise ValueError('The prepared worksheet exceeds the supported cell or column limit.')


def _names(labels):
    used=set(); result=[]
    for label in labels:
        base=str(label)[:110] or 'Column'; name=base; suffix=2
        while name.casefold() in used:
            name=base+'_'+str(suffix); suffix+=1
        used.add(name.casefold());result.append(name)
    return result


def _sheet(name, columns):
    if not isinstance(name,str) or not name.strip() or name!=name.strip() or len(name)>128:
        raise ValueError('Use a worksheet name of 1–128 characters without surrounding blanks.')
    names=_names([c.name for c in columns])
    for c,label in zip(columns,names):c.name=label
    return Worksheet(name, columns)


def stack_columns(sheet, indices, name='Stacked', omit_missing=False):
    columns=_columns(sheet,indices,2)
    if len({c.kind for c in columns})!=1:raise ValueError('Stack columns of the same data type.')
    _bound(sum(len(c.values) for c in columns),2)
    values=[]; labels=[]
    for c in columns:
        for value in c.values:
            if omit_missing and value is None:continue
            values.append(value);labels.append(c.name)
    return _sheet(name,[Column('Values',columns[0].kind,values),Column('Source','text',labels)])


def unstack_columns(sheet, indices, group_index, name='Unstacked', include_missing=False):
    columns=_columns(sheet,indices); group=_columns(sheet,[group_index])[0]
    if group_index in indices:raise ValueError('Choose a separate subscript column.')
    rows=max([len(group.values)]+[len(c.values) for c in columns]);groups={}
    for row in range(rows):
        key=group.values[row] if row<len(group.values) else None
        if key is None and not include_missing:continue
        groups.setdefault(key,[]).append(row)
    if not groups:raise ValueError('No subscript groups contain observations.')
    height=max(map(len,groups.values()));_bound(height,len(groups)*len(columns))
    output=[]
    for c in columns:
        for key,positions in groups.items():
            label='Missing' if key is None else str(key)
            output.append(Column(c.name+'_'+label,c.kind,[c.values[r] if r<len(c.values) else None for r in positions]+[None]*(height-len(positions))))
    return _sheet(name,output)


def transpose(sheet, indices, name='Transposed'):
    columns=_columns(sheet,indices)
    kinds = {c.kind for c in columns}
    is_mixed = len(kinds) > 1
    target_kind = 'text' if is_mixed else (list(kinds)[0] if kinds else 'text')
    rows=max(len(c.values) for c in columns) if columns else 0
    if not rows:raise ValueError('Choose columns containing data.')
    _bound(len(columns),rows+1)
    output=[Column('Source','text',[c.name for c in columns])]
    for r in range(rows):
        row_vals = []
        for c in columns:
            val = c.values[r] if r < len(c.values) else None
            if is_mixed and val is not None:
                val = str(val)
            row_vals.append(val)
        output.append(Column('Row ' + str(r + 1), target_kind, row_vals))
    return _sheet(name,output)


def stack_worksheets(sheets, name='Stacked worksheets', match='position', source=True):
    if len(sheets)<2:raise ValueError('Choose at least two worksheets.')
    if match not in ('position','name'):raise ValueError('Choose a supported column matching option.')
    if any(not s.columns for s in sheets):raise ValueError('Each worksheet must contain columns.')
    if match=='position':
        if len({len(s.columns) for s in sheets})!=1:raise ValueError('Position matching requires equal column counts.')
        maps=[list(range(len(s.columns))) for s in sheets];labels=sheets[0].headers
    else:
        labels=[];maps=[]
        for s in sheets:
            if len(set(s.headers))!=len(s.headers):raise ValueError('Name matching requires unique column names in each worksheet.')
            for label in s.headers:
                if label not in labels:labels.append(label)
        maps=[[s.headers.index(label) if label in s.headers else None for label in labels] for s in sheets]
    _bound(sum(s.row_count for s in sheets),len(labels)+int(source))
    output=[]
    for j,label in enumerate(labels):
        kinds={s.columns[m[j]].kind for s,m in zip(sheets,maps) if m[j] is not None}
        if len(kinds)!=1:raise ValueError('Matched columns must have the same data type: '+label)
        values=[]
        for s,m in zip(sheets,maps):
            c=s.columns[m[j]] if m[j] is not None else None
            values.extend((list(c.values)+[None]*(s.row_count-len(c.values))) if c else [None]*s.row_count)
        output.append(Column(label,next(iter(kinds)),values))
    if source:output.append(Column('Source worksheet','text',[s.name for s in sheets for _ in range(s.row_count)]))
    return _sheet(name,output)


def merge_worksheets(left, right, left_key=None, right_key=None, name='Merged', how='left'):
    if how not in ('left','inner','full','position'):raise ValueError('Choose a supported merge option.')
    count=len(left.columns)+len(right.columns)
    if how=='position':
        rows=max(left.row_count,right.row_count);_bound(rows,count)
        pairs=[(r if r<left.row_count else None,r if r<right.row_count else None) for r in range(rows)]
    else:
        a=_columns(left,[left_key])[0];b=_columns(right,[right_key])[0]
        if a.kind!=b.kind:raise ValueError('Merge keys must have the same data type.')
        def lookup(c):
            found={}
            for r,v in enumerate(c.values):
                if v is None:continue
                if v in found:raise ValueError('This merge requires unique nonmissing keys in each worksheet.')
                found[v]=r
            return found
        lookup(a);index=lookup(b);pairs=[];used=set()
        _bound(left.row_count+(right.row_count if how=='full' else 0),count)
        for r in range(left.row_count):
            key=a.values[r] if r<len(a.values) else None
            other=index.get(key) if key is not None else None
            if other is not None:used.add(other)
            if other is not None or how!='inner':pairs.append((r,other))
        if how=='full':pairs.extend((None,r) for r in range(right.row_count) if r not in used)
    output=[]
    for side,s in enumerate((left,right)):
        for c in s.columns:
            output.append(Column(c.name,c.kind,[c.values[pair[side]] if pair[side] is not None and pair[side]<len(c.values) else None for pair in pairs]))
    return _sheet(name,output)


def store_prepared(presenter, sheet, destination='worksheet'):
    """A new project lets native MPX inputs participate without rewriting their structure."""
    sheet.validate();_bound(sheet.row_count,len(sheet.columns))
    if destination=='project':
        from .app import Presenter
        target=Presenter();target.worksheet=sheet;target.dirty=True
        return target
    if destination!='worksheet':raise ValueError('Choose a supported destination.')
    target=presenter.add_worksheet(sheet.name)
    target.columns=sheet.columns;target.constants=[];target.matrices=[];target.metadata={}
    return presenter


def split_worksheet(sheet, by_indices, include_missing=True):
    """Split a worksheet into multiple worksheets based on distinct combinations of By columns."""
    if not by_indices:
        raise ValueError("Choose at least one By variable.")
    by_cols = _columns(sheet, by_indices, 1)
    row_count = sheet.row_count
    groups = {}
    for r in range(row_count):
        vals = tuple(c.values[r] if r < len(c.values) else None for c in by_cols)
        if not include_missing and any(v is None for v in vals):
            continue
        key_parts = []
        for v in vals:
            if v is None:
                key_parts.append("*")
            elif isinstance(v, float) and v.is_integer():
                key_parts.append(str(int(v)))
            else:
                key_parts.append(str(v).strip())
        key = " ".join(key_parts).strip()
        if not key:
            key = "Group"
        if key not in groups:
            groups[key] = []
        groups[key].append(r)

    if not groups:
        raise ValueError("No data rows remain to create split worksheets.")

    new_sheets = []
    for grp_name, rows in groups.items():
        sub_cols = []
        for c in sheet.columns:
            new_vals = [c.values[r] if r < len(c.values) else None for r in rows]
            sub_cols.append(Column(c.name, c.kind, new_vals, metadata=dict(c.metadata)))
        sheet_title = f"{sheet.name} - {grp_name}"[:128]
        new_sheets.append(_sheet(sheet_title, sub_cols))
    return new_sheets


def make_indicator_variables(sheet, col_index, prefix=""):
    """Create binary 0/1 indicator columns for each distinct non-missing value."""
    src = _columns(sheet, [col_index], 1)[0]
    row_count = sheet.row_count
    seen = {}
    ordered_keys = []
    for r in range(row_count):
        val = src.values[r] if r < len(src.values) else None
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        key = str(int(val)) if (isinstance(val, float) and val.is_integer()) else str(val)
        if key not in seen:
            seen[key] = val
            ordered_keys.append(key)
    if not ordered_keys:
        raise ValueError("Source column contains no non-missing values to encode.")

    _bound(row_count, len(sheet.columns) + len(ordered_keys))
    base_prefix = prefix.strip() if prefix and prefix.strip() else src.name
    existing_names = {c.name.casefold() for c in sheet.columns}
    indicator_cols = []
    for key in ordered_keys:
        candidate = f"{base_prefix}_{key}"[:110]
        final_name = candidate
        suffix = 2
        while final_name.casefold() in existing_names:
            final_name = f"{candidate}_{suffix}"[:110]
            suffix += 1
        existing_names.add(final_name.casefold())
        vals = []
        for r in range(row_count):
            v = src.values[r] if r < len(src.values) else None
            if v is None or (isinstance(v, str) and not v.strip()):
                vals.append(None)
            else:
                k = str(int(v)) if (isinstance(v, float) and v.is_integer()) else str(v)
                vals.append(1.0 if k == key else 0.0)
        indicator_cols.append(Column(final_name, "number", vals))
    return indicator_cols


def subset_by_condition(sheet, condition_expr, new_name="Subset"):
    """Filter worksheet rows matching a boolean calculator expression."""
    from .calculator import evaluate_advanced
    flags = evaluate_advanced(condition_expr, sheet)
    matched_rows = [
        r for r, v in enumerate(flags)
        if v is not None and v not in (0, 0.0, False, "")
    ]
    if not matched_rows:
        raise ValueError("No rows matched the specified condition.")
    sub_cols = []
    for c in sheet.columns:
        new_vals = [c.values[r] if r < len(c.values) else None for r in matched_rows]
        sub_cols.append(Column(c.name, c.kind, new_vals, metadata=dict(c.metadata)))
    clean_name = (new_name or f"{sheet.name} (Subset)").strip()[:128]
    return _sheet(clean_name, sub_cols)


def _parse_datetime_cell(val, kind, custom_fmt=""):
    from datetime import datetime
    from .model import serial_to_datetime
    if val is None:
        return None
    if kind == "date" and isinstance(val, (int, float)):
        return serial_to_datetime(val)
    text = str(val).strip()
    if not text or text == "*":
        return None
    if custom_fmt and custom_fmt.strip():
        return datetime.strptime(text, custom_fmt.strip())
    for fmt in (
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y",
        "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"Unable to parse date/time value '{text}'.") from exc


def round_datetime_column(sheet, col_index, unit="Day"):
    """Truncate/round a Date/Time column to Year, Month, Day, Hour, or Minute."""
    from .model import datetime_to_serial
    src = _columns(sheet, [col_index], 1)[0]
    u = unit.strip().lower()
    if u not in ("year", "month", "day", "hour", "minute"):
        raise ValueError("Choose Year, Month, Day, Hour, or Minute.")
    out_serials = []
    for v in src.values:
        dt = _parse_datetime_cell(v, src.kind)
        if dt is None:
            out_serials.append(None)
            continue
        if u == "year":
            rd = dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif u == "month":
            rd = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif u == "day":
            rd = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif u == "hour":
            rd = dt.replace(minute=0, second=0, microsecond=0)
        else:
            rd = dt.replace(second=0, microsecond=0)
        out_serials.append(datetime_to_serial(rd))
    return out_serials


def convert_text_to_datetime_column(sheet, col_index, fmt=""):
    """Parse a Text column into typed StatCraft date serial numbers."""
    from .model import datetime_to_serial
    src = _columns(sheet, [col_index], 1)[0]
    out_serials = []
    for v in src.values:
        dt = _parse_datetime_cell(v, src.kind, fmt)
        out_serials.append(None if dt is None else datetime_to_serial(dt))
    return out_serials
