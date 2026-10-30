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
