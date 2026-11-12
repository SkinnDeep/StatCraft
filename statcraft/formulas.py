"""Independent dependency-aware column formulas, with transactional calculation."""
import copy
import heapq
import re
from . import calculator,engine


def calculation_order(worksheet,targets=None):
    expressions={i:c.metadata['formula'] for i,c in enumerate(worksheet.columns) if c.metadata.get('formula')}
    dependencies={i:calculator.column_references(expr, worksheet) for i,expr in expressions.items()}
    for index,refs in dependencies.items():
        if any(r<0 or r>=len(worksheet.columns) for r in refs):
            raise ValueError('Formula in C'+str(index+1)+' refers to a column that does not exist.')
    selected=set(expressions) if targets is None else set(targets)&expressions.keys()
    pending=list(selected)
    while pending:
        for ref in dependencies[pending.pop()]&expressions.keys():
            if ref not in selected:selected.add(ref);pending.append(ref)
    incoming={i:dependencies[i]&selected for i in selected}
    dependents={i:set() for i in selected}
    for index,refs in incoming.items():
        for ref in refs:dependents[ref].add(index)
    ready=[i for i,refs in incoming.items() if not refs];heapq.heapify(ready)
    ordered=[]
    while ready:
        index=heapq.heappop(ready);ordered.append(index)
        for dest in sorted(dependents[index]):
            incoming[dest].remove(index)
            if not incoming[dest]:heapq.heappush(ready,dest)
    if len(ordered)!=len(selected):
        involved=', '.join('C'+str(i+1) for i in sorted(selected-set(ordered)))
        raise ValueError('Circular column formulas involving '+involved+'. Remove the circular reference.')
    return ordered


def recalculate(worksheet,targets=None):
    ordered=calculation_order(worksheet,targets)
    if not ordered:return 0
    candidate=copy.deepcopy(worksheet)
    for index in ordered:
        column=candidate.columns[index]
        try:
            raw_values = calculator.evaluate_advanced(column.metadata['formula'], candidate)
            if any(isinstance(v, str) for v in raw_values):
                column.kind = 'text'
                column.values = [None if v is None else str(v) for v in raw_values]
            else:
                column.kind = 'number'
                column.values = [None if v is None else engine.normalize_numeric(v) for v in raw_values]
        except ValueError as exc:
            raise ValueError('Formula in C'+str(index+1)+': '+str(exc)) from exc
    for index in ordered:
        worksheet.columns[index].kind=candidate.columns[index].kind
        worksheet.columns[index].values=candidate.columns[index].values
    return len(ordered)


def refresh_after_edit(worksheet,before,enabled=True):
    if not enabled:return
    if (len(worksheet.columns)!=len(before.columns)
        or worksheet.constants!=before.constants
        or any((a.kind,a.values,a.metadata.get('formula'))!=(b.kind,b.values,b.metadata.get('formula'))
               for a,b in zip(worksheet.columns,before.columns))):
        recalculate(worksheet)


def remap_references(worksheet,old_columns):
    """Keep column references attached to their data during structural edits."""
    positions={id(col):i for i,col in enumerate(worksheet.columns)}
    mapping={i:positions[id(col)] for i,col in enumerate(old_columns) if id(col) in positions}
    def replace(match):
        old=int(match.group(1))-1
        if old not in mapping:
            raise ValueError('C'+str(old+1)+' is used by a formula. Remove the dependent formula before deleting its source column.')
        return 'C'+str(mapping[old]+1)
    for column in worksheet.columns:
        if column.metadata.get('formula'):
            column.metadata['formula']=re.sub(r'\bC(\d+)\b',replace,column.metadata['formula'], flags=re.IGNORECASE)
