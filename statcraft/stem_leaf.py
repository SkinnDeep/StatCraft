"""Stem-and-Leaf display computation for StatCraft.

Computes standard StatCraft stem-and-leaf plot with:
- Leaf Unit header
- Sample size N and missing count N*
- Depth column (cumulative counts from both tails meeting with modal count in parentheses)
- Stem column
- Sorted leaves column
"""
from __future__ import annotations

import math
from collections import defaultdict


def compute_stem_leaf(values: list[float], variable_name: str = "C1", trim_outliers: bool = True) -> dict:
    valid_values = [float(v) for v in values if v is not None and math.isfinite(v)]
    n_missing = len(values) - len(valid_values)
    n = len(valid_values)

    if n < 1:
        raise ValueError("Stem-and-Leaf display requires at least 1 valid observation.")

    valid_values.sort()

    # Determine magnitude and leaf unit
    data_range = valid_values[-1] - valid_values[0]
    if data_range == 0:
        val = abs(valid_values[0])
        mag = val if val > 0 else 1.0
        leaf_unit = 10.0 ** (math.floor(math.log10(mag)) - 1)
    else:
        # Standard StatCraft leaf unit selection aiming for roughly 5-20 stems
        target_step = data_range / 10.0
        leaf_unit = 10.0 ** math.floor(math.log10(target_step))

    if not math.isfinite(leaf_unit) or leaf_unit <= 0:
        leaf_unit = 1.0

    # Bucket into stems and leaves
    # units = round(v / leaf_unit)
    # stem = units // 10, leaf = units % 10
    stem_buckets = defaultdict(list)
    for v in valid_values:
        total_units = int(math.floor(v / leaf_unit + 0.5))
        stem = total_units // 10
        leaf = total_units % 10
        stem_buckets[stem].append(leaf)

    sorted_stems = sorted(stem_buckets.keys())
    if not sorted_stems:
        sorted_stems = [0]
        stem_buckets[0] = [0]

    # Fill empty stems between min and max if reasonable (< 50 stems)
    min_s = sorted_stems[0]
    max_s = sorted_stems[-1]
    all_stems = list(range(min_s, max_s + 1)) if (max_s - min_s) <= 60 else sorted_stems

    stem_counts = [len(stem_buckets.get(s, [])) for s in all_stems]

    # Calculate StatCraft depths (cumulative from top and bottom toward median)
    cum_up = []
    tot = 0
    for cnt in stem_counts:
        tot += cnt
        cum_up.append(tot)

    cum_down = []
    tot = 0
    for cnt in reversed(stem_counts):
        tot += cnt
        cum_down.append(tot)
    cum_down.reverse()

    # Median location
    half = (n + 1) / 2.0
    median_stem_idx = -1
    for idx, c in enumerate(cum_up):
        if c >= half:
            median_stem_idx = idx
            break

    depth_labels = []
    for idx in range(len(all_stems)):
        cnt = stem_counts[idx]
        if idx < median_stem_idx:
            depth_labels.append(str(cum_up[idx]))
        elif idx == median_stem_idx:
            depth_labels.append(f"({cnt})")
        else:
            depth_labels.append(str(cum_down[idx]))

    # Format text lines
    lines = []
    lines.append(f"Stem-and-Leaf Display: {variable_name}")
    lines.append("")
    lines.append(f"Stem-and-leaf of {variable_name}  N = {n}" + (f"  N* = {n_missing}" if n_missing > 0 else ""))
    lines.append(f"Leaf Unit = {leaf_unit:.6g}")
    lines.append("")

    depth_width = max(len(d) for d in depth_labels)
    depth_width = max(depth_width, 4)

    for depth, stem, cnt in zip(depth_labels, all_stems, stem_counts):
        leaves = stem_buckets.get(stem, [])
        leaves_str = " ".join(str(l) for l in sorted(leaves))
        stem_str = str(stem).rjust(4)
        depth_str = depth.rjust(depth_width)
        lines.append(f"  {depth_str} {stem_str} | {leaves_str}")

    return {
        'analysis': 'stem_leaf',
        'variable': variable_name,
        'n': n,
        'n_missing': n_missing,
        'leaf_unit': leaf_unit,
        'lines': lines,
    }
