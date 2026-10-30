"""Worksheet column standardization engine.

Provides methods corresponding to StatCraft Calc > Standardize:
- Subtract mean and divide by std dev (Z-score)
- Subtract mean
- Divide by std dev
- Subtract min and divide by range (0 to 1)
- Subtract median
"""
from __future__ import annotations

import statistics
from .engine import normalize_numeric


def standardize_column(values: list, method: str = 'zscore') -> list[float | None]:
    # Extract numeric values while preserving indices
    nums = []
    for v in values:
        norm = normalize_numeric(v)
        if norm is not None:
            nums.append(float(norm))

    if not nums:
        return [None] * len(values)

    n = len(nums)
    mean_val = statistics.fmean(nums)
    stdev_val = statistics.stdev(nums) if n > 1 else 0.0
    med_val = statistics.median(nums)
    min_val = min(nums)
    max_val = max(nums)
    span = max_val - min_val

    result = []
    for v in values:
        norm = normalize_numeric(v)
        if norm is None:
            result.append(None)
            continue
        x = float(norm)

        if method == 'zscore':
            val = (x - mean_val) / stdev_val if stdev_val > 0 else 0.0
        elif method == 'subtract_mean':
            val = x - mean_val
        elif method == 'divide_stdev':
            val = x / stdev_val if stdev_val > 0 else 0.0
        elif method == 'range_0_1':
            val = (x - min_val) / span if span > 0 else 0.0
        elif method == 'subtract_median':
            val = x - med_val
        else:
            raise ValueError(f"Unknown standardization method: {method}")

        result.append(round(val, 6))

    return result
