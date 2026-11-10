"""Calc Patterned Data & Random Data Generation.

Provides:
- Make Patterned Data:
  * Simple Set of Numbers
  * Arbitrary Set of Numbers
  * Text Values
- Random Data Generation: Normal, Uniform, Exponential, Poisson, Binomial
"""
from __future__ import annotations

import math
import random


def make_patterned_numbers(from_val: float, to_val: float, step: float = 1.0,
                           repeat_each: int = 1, repeat_sequence: int = 1) -> list[float]:
    if step == 0:
        raise ValueError("Step value cannot be zero.")
    if repeat_each < 1:
        repeat_each = 1
    if repeat_sequence < 1:
        repeat_sequence = 1

    # Generate basic sequence
    seq = []
    curr = float(from_val)
    if step > 0:
        while curr <= to_val + 1e-9:
            seq.append(round(curr, 8))
            curr += step
    else:
        while curr >= to_val - 1e-9:
            seq.append(round(curr, 8))
            curr += step

    if not seq:
        seq = [float(from_val)]

    # Repeat each
    expanded = []
    for val in seq:
        expanded.extend([val] * repeat_each)

    # Repeat sequence
    result = []
    for _ in range(repeat_sequence):
        result.extend(expanded)

    return result


def make_patterned_arbitrary_numbers(items: list[float], repeat_each: int = 1, repeat_sequence: int = 1) -> list[float]:
    if not items:
        raise ValueError("At least one number is required.")
    if repeat_each < 1:
        repeat_each = 1
    if repeat_sequence < 1:
        repeat_sequence = 1

    expanded = []
    for val in items:
        expanded.extend([val] * repeat_each)

    result = []
    for _ in range(repeat_sequence):
        result.extend(expanded)
    return result


def make_patterned_text(items: list[str], repeat_each: int = 1, repeat_sequence: int = 1) -> list[str]:
    if not items:
        raise ValueError("At least one text value is required.")
    if repeat_each < 1:
        repeat_each = 1
    if repeat_sequence < 1:
        repeat_sequence = 1

    expanded = []
    for val in items:
        expanded.extend([val] * repeat_each)

    result = []
    for _ in range(repeat_sequence):
        result.extend(expanded)
    return result


def generate_random_normal(n: int, mean: float = 0.0, stdev: float = 1.0, seed: int | None = None) -> list[float]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if stdev <= 0:
        raise ValueError("Standard deviation must be positive.")

    rng = random.Random(seed) if seed is not None else random.Random()
    return [round(rng.gauss(mean, stdev), 6) for _ in range(n)]


def generate_random_uniform(n: int, low: float = 0.0, high: float = 1.0, seed: int | None = None) -> list[float]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if high <= low:
        raise ValueError("Upper endpoint must be greater than lower endpoint.")

    rng = random.Random(seed) if seed is not None else random.Random()
    return [round(rng.uniform(low, high), 6) for _ in range(n)]


def generate_random_exponential(n: int, scale: float = 1.0, seed: int | None = None) -> list[float]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if scale <= 0:
        raise ValueError("Scale (mean) must be positive.")

    rng = random.Random(seed) if seed is not None else random.Random()
    return [round(rng.expovariate(1.0 / scale), 6) for _ in range(n)]


def generate_random_poisson(n: int, mean: float = 1.0, seed: int | None = None) -> list[int]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if mean <= 0:
        raise ValueError("Mean must be positive.")

    rng = random.Random(seed) if seed is not None else random.Random()
    L = math.exp(-mean)
    result = []
    for _ in range(n):
        k = 0
        p = 1.0
        while True:
            k += 1
            p *= rng.random()
            if p <= L:
                break
        result.append(k - 1)
    return result


def generate_random_binomial(n: int, trials: int = 10, prob: float = 0.5, seed: int | None = None) -> list[int]:
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if trials < 1:
        raise ValueError("Number of trials must be at least 1.")
    if not (0.0 <= prob <= 1.0):
        raise ValueError("Event probability must be between 0 and 1.")

    rng = random.Random(seed) if seed is not None else random.Random()
    result = []
    for _ in range(n):
        successes = sum(1 for _ in range(trials) if rng.random() < prob)
        result.append(successes)
    return result


def make_patterned_datetime(
    start_dt: str,
    end_dt: str | None = None,
    count: int | None = None,
    step: int = 1,
    unit: str = "days",
    repeat_each: int = 1,
    repeat_sequence: int = 1,
    dt_format: str = "%Y-%m-%d"
) -> list[str]:
    """Generate patterned date/time sequence.
    
    Parameters
    ----------
    start_dt : Start date/time string (e.g. '2026-01-01' or '2026-01-01 08:00:00')
    end_dt : Optional end date/time string
    count : Optional number of distinct steps to generate
    step : Increment step magnitude
    unit : 'days', 'weeks', 'months', 'years', 'hours', 'minutes'
    repeat_each : Repetitions per date value
    repeat_sequence : Repetitions of entire sequence
    dt_format : Output datetime format
    """
    from datetime import datetime, timedelta

    if step == 0:
        raise ValueError("Step cannot be zero.")
    if repeat_each < 1:
        repeat_each = 1
    if repeat_sequence < 1:
        repeat_sequence = 1

    # Parse start_dt
    for fmt_try in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            curr = datetime.strptime(start_dt.strip(), fmt_try)
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Unable to parse start date/time: '{start_dt}'")

    end_datetime = None
    if end_dt and end_dt.strip():
        for fmt_try in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
            try:
                end_datetime = datetime.strptime(end_dt.strip(), fmt_try)
                break
            except ValueError:
                continue

    unit_lower = unit.lower().strip()
    distinct_dates = []

    def _advance(dt: datetime, s: int) -> datetime:
        if unit_lower in ("days", "day", "d"):
            return dt + timedelta(days=s)
        elif unit_lower in ("weeks", "week", "w"):
            return dt + timedelta(weeks=s)
        elif unit_lower in ("hours", "hour", "h"):
            return dt + timedelta(hours=s)
        elif unit_lower in ("minutes", "minute", "min"):
            return dt + timedelta(minutes=s)
        elif unit_lower in ("months", "month", "m"):
            year = dt.year + (dt.month + s - 1) // 12
            month = (dt.month + s - 1) % 12 + 1
            day = min(dt.day, 28)
            return dt.replace(year=year, month=month, day=day)
        elif unit_lower in ("years", "year", "y"):
            return dt.replace(year=dt.year + s)
        else:
            return dt + timedelta(days=s)

    if count is not None and count > 0:
        for _ in range(count):
            distinct_dates.append(curr.strftime(dt_format))
            curr = _advance(curr, step)
    elif end_datetime is not None:
        max_safety = 100000
        if step > 0:
            while curr <= end_datetime and len(distinct_dates) < max_safety:
                distinct_dates.append(curr.strftime(dt_format))
                curr = _advance(curr, step)
        else:
            while curr >= end_datetime and len(distinct_dates) < max_safety:
                distinct_dates.append(curr.strftime(dt_format))
                curr = _advance(curr, step)
    else:
        # Default to 10 points
        for _ in range(10):
            distinct_dates.append(curr.strftime(dt_format))
            curr = _advance(curr, step)

    if not distinct_dates:
        distinct_dates = [start_dt]

    expanded = []
    for d in distinct_dates:
        expanded.extend([d] * repeat_each)

    result = []
    for _ in range(repeat_sequence):
        result.extend(expanded)

    return result


def generate_random_distribution(
    distribution: str,
    n: int,
    parameters: list[float] | tuple[float, ...],
    seed: int | None = None,
) -> list[float | int]:
    """Generate random samples from any supported probability distribution."""
    if n <= 0:
        raise ValueError("Number of rows must be at least 1.")
    if n > 1_000_000:
        raise ValueError("Number of rows cannot exceed 1,000,000.")
    import numpy as np
    from .probability import _build_model, DISCRETE_DISTRIBUTIONS, PARAMETERS

    if distribution not in PARAMETERS:
        raise ValueError(f"Unsupported distribution: {distribution}")
    if len(parameters) != len(PARAMETERS[distribution]):
        raise ValueError(f"Expected {len(PARAMETERS[distribution])} parameter(s) for {distribution}.")

    p = tuple(float(x) for x in parameters)
    model = _build_model(distribution, p)
    rng = np.random.default_rng(seed)
    samples = model.rvs(size=n, random_state=rng)
    if distribution in DISCRETE_DISTRIBUTIONS:
        return [int(v) for v in samples]
    return [round(float(v), 6) if math.isfinite(float(v)) else None for v in samples]


def sample_from_columns(
    columns_values: list[list],
    n: int,
    replace: bool = False,
    seed: int | None = None,
) -> list[list]:
    """Sample n rows simultaneously across source columns (with or without replacement)."""
    if not columns_values:
        raise ValueError("Select at least one source column to sample from.")
    row_count = max(len(col) for col in columns_values)
    if row_count == 0:
        raise ValueError("Source columns contain no rows.")
    if n <= 0:
        raise ValueError("Number of rows to sample must be at least 1.")
    if not replace and n > row_count:
        raise ValueError(f"Cannot sample {n} rows without replacement from {row_count} rows.")

    rng = random.Random(seed) if seed is not None else random.Random()
    if replace:
        indices = [rng.randrange(row_count) for _ in range(n)]
    else:
        indices = rng.sample(range(row_count), n)

    return [
        [col[idx] if idx < len(col) else None for idx in indices]
        for col in columns_values
    ]


ROW_STAT_CHOICES = ("Mean", "Sum", "StDev", "Min", "Max", "Median", "Range", "Count", "NMISS", "SSQ")
COLUMN_STAT_CHOICES = ("Mean", "Sum", "StDev", "Min", "Max", "Median", "Range", "Count", "NMISS", "SSQ", "Q1", "Q3", "IQR")


def _finite_row_nums(row_vals: list) -> list[float]:
    nums = []
    for v in row_vals:
        if v is None or isinstance(v, bool):
            continue
        try:
            fv = float(v)
            if math.isfinite(fv):
                nums.append(fv)
        except (ValueError, TypeError):
            continue
    return nums


def _single_stat(nums: list[float], total_items: int, stat_name: str) -> float | None:
    key = stat_name.strip().lower()
    n = len(nums)
    if key in ("count", "n"):
        return float(n)
    if key == "nmiss":
        return float(total_items - n)
    if n == 0:
        return None
    if key == "sum":
        return float(sum(nums))
    if key == "mean":
        return float(sum(nums) / n)
    if key == "min":
        return float(min(nums))
    if key == "max":
        return float(max(nums))
    if key == "range":
        return float(max(nums) - min(nums))
    if key == "ssq":
        return float(sum(x * x for x in nums))
    if key == "median":
        import statistics
        return float(statistics.median(nums))
    if key in ("stdev", "std"):
        if n < 2:
            return None
        mean = sum(nums) / n
        return math.sqrt(sum((x - mean) ** 2 for x in nums) / (n - 1))
    if key in ("q1", "q3", "iqr"):
        import numpy as np
        arr = sorted(nums)
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        if key == "q1":
            return q1
        if key == "q3":
            return q3
        return q3 - q1
    raise ValueError(f"Unsupported statistic: {stat_name}")


def compute_row_statistics(columns_values: list[list], stat_name: str = "Mean") -> list[float | None]:
    """Compute a statistic row-by-row across multiple columns (Calc > Row Statistics)."""
    if not columns_values:
        raise ValueError("Select at least one numeric column.")
    row_count = max(len(col) for col in columns_values)
    result = []
    for r in range(row_count):
        row_items = [col[r] if r < len(col) else None for col in columns_values]
        nums = _finite_row_nums(row_items)
        result.append(_single_stat(nums, len(columns_values), stat_name))
    return result


def compute_column_statistics(values: list, stat_name: str = "Mean") -> float | None:
    """Compute a single scalar statistic over a column (Calc > Column Statistics)."""
    nums = _finite_row_nums(values)
    return _single_stat(nums, len(values), stat_name)

