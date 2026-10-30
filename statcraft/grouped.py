"""Original row-aligned categorical grouping for stacked worksheet analyses."""
from .model import finite_number
from .inference import one_way_anova


def group_pairs(response, factor,order_column=None):
    """Group complete pairs and retain omitted/source row numbers.

    Empty text and None are missing factor values. Text levels are case-sensitive,
    and numeric levels remain numeric. Level order follows first complete occurrence.
    """
    response, factor = list(response), list(factor)
    groups, missing_rows = {}, []
    for row in range(max(len(response), len(factor))):
        value = response[row] if row < len(response) else None
        level = factor[row] if row < len(factor) else None
        if value is None or level is None or level == "":
            missing_rows.append(row + 1)
            continue
        value = finite_number(value)
        if isinstance(level, str):
            key = ("text", level)
        elif type(level) in (int, float):
            level = finite_number(level)
            key = ("number", level)
        else:
            raise ValueError("Factor levels must be text or finite numbers.")
        groups.setdefault(key, []).append(value)
    missing_set = set(missing_rows)
    if order_column is not None:
        from .value_order import ordered_values
        levels=ordered_values(order_column,[key[1] for key in groups])
        groups={key:groups[key] for key in sorted(groups,key=lambda key:levels.index(key[1]))}
    return list(groups.values()), [key[1] for key in groups], missing_rows, [
        row for row in range(1, max(len(response),len(factor))+1) if row not in missing_set]


def stacked_anova(response, factor,order_column=None):
    """Classical equal-variance ANOVA from row-aligned response/factor data."""
    groups, levels, missing_rows, used_rows = group_pairs(response, factor,order_column)
    result = one_way_anova(groups)
    result.update(variables=[str(level) for level in levels], factor_levels=levels,
                  missing=len(missing_rows), missing_rows=missing_rows, used_rows=used_rows)
    if missing_rows:
        result["warnings"].append("Incomplete response/factor pairs omitted: rows " +
                                  ", ".join(map(str, missing_rows[:40])) +
                                  (" …" if len(missing_rows) > 40 else ""))
    result["warnings"].append("Factor levels follow column value order when provided; otherwise first complete occurrence. Empty text is missing. Full native collation and numerical parity remain unverified.")
    return result
