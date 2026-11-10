import re
from typing import List, Any


def autofill_sequence(sample_values: List[Any], count: int) -> List[Any]:
    """Extrapolate a pattern from a sequence of sample values.
    
    Supports:
    - Arithmetic progressions (int/float)
    - Single numbers (increment by 1)
    - Prefixed counters ('Batch_01', 'Run 1')
    - Repeating categorical cycles ('A', 'B' -> 'A', 'B' or 'Low', 'Med', 'High')
    - Single strings (repeat identical value)
    """
    if count <= 0 or not sample_values:
        return []

    # Filter out None if trailing
    vals = list(sample_values)
    while vals and vals[-1] is None:
        vals.pop()
    if not vals:
        return [None] * count

    # 1. Numeric sequence
    all_numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals)
    if all_numeric:
        is_all_int = all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in vals)
        if len(vals) == 1:
            start = vals[0]
            step = 1 if is_all_int else 1.0
            return [int(start + step * (i + 1)) if is_all_int else float(start + step * (i + 1)) for i in range(count)]

        # Check for constant difference (linear progression)
        diffs = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
        avg_diff = sum(diffs) / len(diffs)
        is_linear = all(abs(d - avg_diff) < 1e-9 for d in diffs)

        if is_linear:
            last = vals[-1]
            if is_all_int and round(avg_diff) == avg_diff:
                step = int(round(avg_diff))
                return [int(round(last + step * (i + 1))) for i in range(count)]
            else:
                return [float(last + avg_diff * (i + 1)) for i in range(count)]

        # Check for repeating numeric cycle
        period = _find_period(vals)
        if period is not None and period < len(vals):
            return [vals[(len(vals) + i) % period] for i in range(count)]

        # Fallback to repeating the whole block
        return [vals[i % len(vals)] for i in range(count)]

    # 2. String sequence
    str_vals = [str(v) if v is not None else "" for v in vals]

    # Check for prefix + numeric counter: e.g. "Batch_01", "Run 1"
    match_pattern = re.compile(r'^(.*?)(\d+)$')
    parsed = [match_pattern.match(s) for s in str_vals]
    if all(m is not None for m in parsed):
        prefixes = [m.group(1) for m in parsed]
        if len(set(prefixes)) == 1:
            prefix = prefixes[0]
            num_strs = [m.group(2) for m in parsed]
            pad_len = max(len(s) for s in num_strs) if any(s.startswith("0") for s in num_strs) else 0
            nums = [int(s) for s in num_strs]
            if len(nums) == 1:
                step = 1
            else:
                diffs = [nums[i] - nums[i - 1] for i in range(1, len(nums))]
                avg_diff = sum(diffs) / len(diffs)
                step = int(round(avg_diff)) if all(d == diffs[0] for d in diffs) else 1

            last_num = nums[-1]
            generated = []
            for i in range(count):
                next_val = last_num + step * (i + 1)
                if pad_len > 0:
                    generated.append(f"{prefix}{next_val:0{pad_len}d}")
                else:
                    generated.append(f"{prefix}{next_val}")
            return generated

    # Check for repeating period / cycle in strings
    period = _find_period(str_vals)
    if period is not None:
        return [str_vals[(len(str_vals) + i) % period] for i in range(count)]

    # Fallback: cycle through sample strings
    return [str_vals[i % len(str_vals)] for i in range(count)]


def _find_period(sequence: List[Any]):
    """Find the smallest repeating period in sequence, or len(sequence) if it's a full cycle."""
    n = len(sequence)
    if n <= 1:
        return 1
    for p in range(1, n // 2 + 1):
        if all(sequence[i] == sequence[i % p] for i in range(p, n)):
            return p
    return n
