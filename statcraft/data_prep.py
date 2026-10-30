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
    if len({c.kind for c in columns})!=1:raise ValueError('Transpose columns of the same data type.')
    rows=max(len(c.values) for c in columns)
    if not rows:raise ValueError('Choose columns containing data.')
    _bound(len(columns),rows+1)
    output=[Column('Source','text',[c.name for c in columns])]
    output.extend(Column('Row '+str(r+1),columns[0].kind,[c.values[r] if r<len(c.values) else None for c in columns]) for r in range(rows))
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
