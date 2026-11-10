"""Restricted, original worksheet expression calculator. Never evaluates Python."""
import ast
import math
import operator
from .model import finite_number

FUNCTIONS = {'ABS': abs, 'SQRT': math.sqrt, 'LOG': math.log,
             'LOG10': math.log10, 'EXP': math.exp, 'SIN': math.sin,
             'COS': math.cos, 'ROUND': round}
BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}


def parse_expression(expression):
    """Parse only the bounded expression syntax; never execute Python."""
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 4096:
        raise ValueError('Enter a formula of at most 4096 characters.')
    try:
        tree = ast.parse(expression.replace('^', '**'), mode='eval')
    except (SyntaxError, RecursionError) as exc:
        raise ValueError('Invalid formula syntax.') from exc
    if len(list(ast.walk(tree))) > 128:
        raise ValueError('Formula is too complex.')
    return tree


def column_references(expression):
    return {int(node.id[1:])-1 for node in ast.walk(parse_expression(expression))
            if isinstance(node,ast.Name) and node.id.startswith('C') and node.id[1:].isdigit()}


def evaluate(expression, worksheet):
    """Return one value per row; missing inputs propagate. Supports C/K references."""
    tree = parse_expression(expression)

    def validate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            finite_number(node.value)
        elif isinstance(node, ast.Name):
            if node.id[:1] not in ('C','K') or not node.id[1:].isdigit():
                raise ValueError('Use column references C1, C2, ... or stored constants K1, K2, ...')
            index = int(node.id[1:]) - 1
            entries=worksheet.columns if node.id.startswith('C') else worksheet.constants
            if not 0 <= index < len(entries) or entries[index].kind != 'number':
                raise ValueError('Formula reference must be an existing numeric column or constant.')
            entries[index].validate()
            if node.id.startswith('K') and len(entries[index].values)!=1:
                raise ValueError('A stored constant must contain exactly one value.')
        elif isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            validate(node.left); validate(node.right)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            validate(node.operand)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS:
            if node.keywords or len(node.args) != 1:
                raise ValueError('Functions take exactly one input.')
            validate(node.args[0])
        else:
            raise ValueError('Unsupported expression. Use arithmetic, columns and the listed functions.')
    validate(tree.body)

    def cell(node, row):
        if isinstance(node, ast.Constant): return float(node.value)
        if isinstance(node, ast.Name):
            entries=worksheet.columns if node.id.startswith('C') else worksheet.constants
            values=entries[int(node.id[1:])-1].values
            position=row if node.id.startswith('C') else 0
            return values[position] if position<len(values) else None
        if isinstance(node, ast.BinOp):
            left, right = cell(node.left, row), cell(node.right, row)
            if left is None or right is None: return None
            if isinstance(node.op, ast.Pow) and abs(right) > 10000:
                raise ValueError('Exponent magnitude is too large.')
            return finite_number(BINARY[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp):
            value = cell(node.operand, row)
            return None if value is None else -value if isinstance(node.op, ast.USub) else value
        value = cell(node.args[0], row)
        return None if value is None else finite_number(FUNCTIONS[node.func.id](value))
    result = []
    for row in range(worksheet.row_count):
        try: result.append(cell(tree.body, row))
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            raise ValueError(f'Formula failed at row {row + 1}: {exc}') from exc
    return result


# ==============================================================================
# Extended Minitab Calculator Engine (Multi-Arg Math, Stats, Logic, Text)
# ==============================================================================

_UNARY_MATH = {
    'ABS': abs,
    'SQRT': math.sqrt,
    'LOG': math.log,
    'LN': math.log,
    'LOG10': math.log10,
    'EXP': math.exp,
    'SIN': math.sin,
    'COS': math.cos,
    'TAN': math.tan,
    'ASIN': math.asin,
    'ACOS': math.acos,
    'ATAN': math.atan,
    'SINH': math.sinh,
    'COSH': math.cosh,
    'TANH': math.tanh,
    'CEILING': math.ceil,
    'CEIL': math.ceil,
    'FLOOR': math.floor,
    'TRUNC': math.trunc,
    'SIGN': lambda x: 0.0 if x == 0 else (1.0 if x > 0 else -1.0),
    'DEGREES': math.degrees,
    'RADIANS': math.radians,
}

_BINARY_MATH = {
    'POWER': math.pow,
    'POW': math.pow,
    'MOD': operator.mod,
    'ATAN2': math.atan2,
}

_COL_STATS = frozenset((
    'MEAN', 'STDEV', 'STD', 'VARIANCE', 'VAR', 'MEDIAN', 'SUM', 'SSQ',
    'MIN', 'MAX', 'RANGE', 'COUNT', 'N', 'NMISS', 'Q1', 'Q3', 'IQR',
))

_ROW_STATS = frozenset((
    'ROWMEAN', 'ROWSUM', 'ROWMIN', 'ROWMAX', 'ROWSTDEV', 'ROWCOUNT',
))

_COMPARISONS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}


def _preprocess_expression(expression: str, worksheet) -> str:
    """Resolve bracketed column names like [Yield Strength] into C1/C2 tokens safely."""
    import re
    expr = expression.strip()
    if expr.startswith('='):
        expr = expr[1:].strip()
    if not expr or len(expr) > 4096:
        raise ValueError('Enter a formula of at most 4096 characters.')

    def _replace_brackets(m):
        target = m.group(1).strip()
        for idx, col in enumerate(worksheet.columns):
            if col.name.strip().casefold() == target.casefold():
                return f'C{idx + 1}'
        raise ValueError(f"Unknown column name reference: [{target}]")

    return re.sub(r'\[([^\[\]]+)\]', _replace_brackets, expr)


def evaluate_advanced(expression: str, worksheet):
    """Evaluate extended Minitab Calculator syntax safely via bounded AST traversal."""
    processed = _preprocess_expression(expression, worksheet)
    try:
        tree = ast.parse(processed.replace('^', '**'), mode='eval')
    except (SyntaxError, RecursionError) as exc:
        raise ValueError('Invalid formula syntax.') from exc
    if len(list(ast.walk(tree))) > 512:
        raise ValueError('Formula exceeds maximum complexity limit.')

    from .calc_data import compute_column_statistics, _single_stat, _finite_row_nums

    def _resolve_ref(name: str):
        upper = name.upper()
        if len(upper) >= 2 and upper[0] in ('C', 'K') and upper[1:].isdigit():
            idx = int(upper[1:]) - 1
            entries = worksheet.columns if upper[0] == 'C' else worksheet.constants
            if not 0 <= idx < len(entries):
                raise ValueError(f"Reference '{upper}' does not exist in worksheet.")
            entries[idx].validate()
            return upper[0], entries[idx]
        # Exact unquoted identifier column lookup
        for col in worksheet.columns:
            if col.name == name:
                col.validate()
                return 'C', col
        raise ValueError(f"Unknown column or constant reference: {name}")

    def _col_stat(col_name: str, func_name: str, q_val=None):
        kind_char, entry = _resolve_ref(col_name)
        if kind_char != 'C':
            raise ValueError(f"{func_name} requires a worksheet column (e.g., C1).")
        if func_name == 'PERCENTILE':
            import numpy as np
            nums = _finite_row_nums(entry.values)
            if not nums:
                return None
            q = float(q_val)
            if 0 <= q <= 1:
                q = q * 100.0
            if not 0 <= q <= 100:
                raise ValueError('Percentile must be between 0 and 100 (or 0 and 1).')
            return float(np.percentile(sorted(nums), q))
        key = 'stdev' if func_name in ('STDEV', 'STD') else func_name
        if key in ('VARIANCE', 'VAR'):
            s = compute_column_statistics(entry.values, 'StDev')
            return None if s is None else s * s
        return compute_column_statistics(entry.values, key)

    # Pre-validate AST structure before executing rows
    def validate(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                finite_number(node.value)
            elif isinstance(node.value, str) or node.value is None or isinstance(node.value, bool):
                pass
            else:
                raise ValueError('Unsupported literal constant in formula.')
        elif isinstance(node, ast.Name):
            if node.id.upper() in ('PI', 'E', 'TRUE', 'FALSE'):
                return
            _resolve_ref(node.id)
        elif isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            validate(node.left); validate(node.right)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            validate(node.operand)
        elif isinstance(node, ast.Compare):
            if any(type(op) not in _COMPARISONS for op in node.ops):
                raise ValueError('Unsupported comparison operator.')
            validate(node.left)
            for comp in node.comparators:
                validate(comp)
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for v in node.values:
                validate(v)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.keywords:
                raise ValueError('Keyword arguments are not supported.')
            fname = node.func.id.upper()
            if fname in ('PI', 'E', 'MISSING'):
                if len(node.args) != 0:
                    raise ValueError(f'{fname}() takes no arguments.')
                return
            if fname in _COL_STATS:
                if len(node.args) != 1 or not isinstance(node.args[0], ast.Name):
                    raise ValueError(f'{fname}(C1) takes one column reference.')
                _resolve_ref(node.args[0].id)
                return
            if fname == 'PERCENTILE':
                if len(node.args) != 2 or not isinstance(node.args[0], ast.Name):
                    raise ValueError('PERCENTILE(C1, q) requires a column reference and percentile.')
                _resolve_ref(node.args[0].id)
                validate(node.args[1])
                return
            for arg in node.args:
                validate(arg)
        else:
            raise ValueError('Unsupported expression syntax in formula.')

    validate(tree.body)

    def _to_bool(val):
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val != 0.0
        if isinstance(val, str):
            return bool(val.strip())
        return bool(val)

    def eval_node(node, row):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return 1.0 if node.value else 0.0
            if isinstance(node.value, (int, float)):
                return float(node.value)
            return node.value
        if isinstance(node, ast.Name):
            up = node.id.upper()
            if up == 'PI':
                return math.pi
            if up == 'E':
                return math.e
            if up == 'TRUE':
                return 1.0
            if up == 'FALSE':
                return 0.0
            kind_char, entry = _resolve_ref(node.id)
            pos = row if kind_char == 'C' else 0
            return entry.values[pos] if pos < len(entry.values) else None
        if isinstance(node, ast.BinOp):
            left, right = eval_node(node.left, row), eval_node(node.right, row)
            if isinstance(node.op, ast.Add) and (isinstance(left, str) or isinstance(right, str)):
                if left is None or right is None:
                    return None
                return str(left) + str(right)
            if left is None or right is None:
                return None
            if isinstance(node.op, ast.Pow) and abs(float(right)) > 10000:
                raise ValueError('Exponent magnitude is too large.')
            return finite_number(BINARY[type(node.op)](float(left), float(right)))
        if isinstance(node, ast.UnaryOp):
            val = eval_node(node.operand, row)
            if isinstance(node.op, ast.Not):
                return 1.0 if not _to_bool(val) else 0.0
            if val is None:
                return None
            return -float(val) if isinstance(node.op, ast.USub) else float(val)
        if isinstance(node, ast.Compare):
            left_val = eval_node(node.left, row)
            cur = left_val
            for op, comp in zip(node.ops, node.comparators):
                right_val = eval_node(comp, row)
                if cur is None or right_val is None:
                    if isinstance(op, ast.Eq):
                        res = (cur is None and right_val is None)
                    elif isinstance(op, ast.NotEq):
                        res = not (cur is None and right_val is None)
                    else:
                        return 0.0
                else:
                    if isinstance(cur, str) or isinstance(right_val, str):
                        res = _COMPARISONS[type(op)](str(cur), str(right_val))
                    else:
                        res = _COMPARISONS[type(op)](float(cur), float(right_val))
                if not res:
                    return 0.0
                cur = right_val
            return 1.0
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for v in node.values:
                    if not _to_bool(eval_node(v, row)):
                        return 0.0
                return 1.0
            else:
                for v in node.values:
                    if _to_bool(eval_node(v, row)):
                        return 1.0
                return 0.0
        if isinstance(node, ast.Call):
            fname = node.func.id.upper()
            if fname == 'PI':
                return math.pi
            if fname == 'E':
                return math.e
            if fname == 'MISSING':
                return None
            if fname in _COL_STATS:
                return _col_stat(node.args[0].id, fname)
            if fname == 'PERCENTILE':
                q_val = eval_node(node.args[1], row)
                if q_val is None:
                    return None
                return _col_stat(node.args[0].id, 'PERCENTILE', q_val)
            if fname in _ROW_STATS:
                args_vals = [eval_node(a, row) for a in node.args]
                nums = _finite_row_nums(args_vals)
                skey = fname[3:].lower()  # MEAN, SUM, MIN, MAX, STDEV, COUNT
                return _single_stat(nums, len(args_vals), skey)
            if fname == 'IF':
                if len(node.args) != 3:
                    raise ValueError('IF(condition, true_val, false_val) requires 3 arguments.')
                cond = eval_node(node.args[0], row)
                return eval_node(node.args[1], row) if _to_bool(cond) else eval_node(node.args[2], row)
            if fname == 'AND':
                return 1.0 if all(_to_bool(eval_node(a, row)) for a in node.args) else 0.0
            if fname == 'OR':
                return 1.0 if any(_to_bool(eval_node(a, row)) for a in node.args) else 0.0
            if fname == 'NOT':
                if len(node.args) != 1:
                    raise ValueError('NOT(x) requires 1 argument.')
                return 0.0 if _to_bool(eval_node(node.args[0], row)) else 1.0
            if fname == 'ISMISS':
                if len(node.args) != 1:
                    raise ValueError('ISMISS(x) requires 1 argument.')
                val = eval_node(node.args[0], row)
                is_miss = val is None or (isinstance(val, str) and not val.strip()) or (isinstance(val, float) and math.isnan(val))
                return 1.0 if is_miss else 0.0
            if fname == 'ROUND':
                if not 1 <= len(node.args) <= 2:
                    raise ValueError('ROUND(x[, digits]) takes 1 or 2 arguments.')
                val = eval_node(node.args[0], row)
                if val is None:
                    return None
                ndigits = int(eval_node(node.args[1], row)) if len(node.args) == 2 else 0
                return finite_number(round(float(val), ndigits))
            if fname in _UNARY_MATH:
                if len(node.args) != 1:
                    raise ValueError(f'{fname} requires 1 argument.')
                val = eval_node(node.args[0], row)
                return None if val is None else finite_number(_UNARY_MATH[fname](float(val)))
            if fname in _BINARY_MATH:
                if len(node.args) != 2:
                    raise ValueError(f'{fname} requires 2 arguments.')
                a, b = eval_node(node.args[0], row), eval_node(node.args[1], row)
                if a is None or b is None:
                    return None
                return finite_number(_BINARY_MATH[fname](float(a), float(b)))
            if fname == 'UPPER':
                val = eval_node(node.args[0], row)
                return None if val is None else str(val).upper()
            if fname == 'LOWER':
                val = eval_node(node.args[0], row)
                return None if val is None else str(val).lower()
            if fname == 'TRIM':
                val = eval_node(node.args[0], row)
                return None if val is None else str(val).strip()
            if fname == 'LEN':
                val = eval_node(node.args[0], row)
                return 0.0 if val is None else float(len(str(val)))
            if fname == 'CONCAT':
                parts = [eval_node(a, row) for a in node.args]
                return ''.join('' if p is None else str(p) for p in parts)
            if fname == 'LEFT':
                if len(node.args) != 2:
                    raise ValueError('LEFT(text, n) requires 2 arguments.')
                s, n = eval_node(node.args[0], row), eval_node(node.args[1], row)
                return None if s is None or n is None else str(s)[:max(0, int(n))]
            if fname == 'RIGHT':
                if len(node.args) != 2:
                    raise ValueError('RIGHT(text, n) requires 2 arguments.')
                s, n = eval_node(node.args[0], row), eval_node(node.args[1], row)
                if s is None or n is None:
                    return None
                cnt = max(0, int(n))
                return '' if cnt == 0 else str(s)[-cnt:]
            if fname == 'MID':
                if len(node.args) != 3:
                    raise ValueError('MID(text, start, length) requires 3 arguments.')
                s, st, ln = eval_node(node.args[0], row), eval_node(node.args[1], row), eval_node(node.args[2], row)
                if s is None or st is None or ln is None:
                    return None
                start0 = max(0, int(st) - 1)
                return str(s)[start0:start0 + max(0, int(ln))]
            if fname == 'CONTAINS':
                if len(node.args) != 2:
                    raise ValueError('CONTAINS(text, sub) requires 2 arguments.')
                s, sub = eval_node(node.args[0], row), eval_node(node.args[1], row)
                if s is None or sub is None:
                    return 0.0
                return 1.0 if str(sub).lower() in str(s).lower() else 0.0
            if fname == 'REPLACE':
                if len(node.args) != 3:
                    raise ValueError('REPLACE(text, old, new) requires 3 arguments.')
                s, old, new = eval_node(node.args[0], row), eval_node(node.args[1], row), eval_node(node.args[2], row)
                if s is None:
                    return None
                return str(s).replace('' if old is None else str(old), '' if new is None else str(new))
            raise ValueError(f'Unknown function: {fname}')
        raise ValueError('Unsupported expression node.')

    result = []
    for row in range(worksheet.row_count):
        try:
            result.append(eval_node(tree.body, row))
        except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            raise ValueError(f'Formula failed at row {row + 1}: {exc}') from exc
    return result

