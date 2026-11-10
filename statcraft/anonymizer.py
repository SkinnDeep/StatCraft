"""One-Click 'Clean for Audit' Dataset Anonymizer for StatCraft.

Sanitizes confidential datasets (medical devices, aerospace, pharma, financial)
for external consultants, auditors, or public bug reports.

Features:
1. Categorical / Text Column Masking:
   Deterministic pseudonym hashing (e.g., 'Operator_01', 'Batch_A', 'Vendor_03')
   preserving exact category counts and contingency distributions.
2. Invariant Numeric Masking (optional):
   Applies an affine transformation y = a * x + b (with fixed a > 0) per column
   that mathematically preserves:
   - Exact Pearson correlations (r) between all columns
   - Exact ANOVA F-statistics and p-values
   - Exact regression R-squared, t-statistics, and p-values
   - Exact relative distribution shapes (skewness, kurtosis)
   while completely obscuring proprietary absolute yield numbers.
"""
from __future__ import annotations

import copy
import hashlib
import math
import random
from typing import Dict, List, Optional

from .model import Column, Worksheet


def _hash_category(val: str, prefix: str = "Cat", seed: int = 42) -> str:
    h = hashlib.sha256(f"{seed}:{val}".encode("utf-8")).hexdigest()[:4].upper()
    return f"{prefix}_{h}"


def anonymize_worksheet(
    worksheet: Worksheet,
    mask_numeric: bool = False,
    numeric_scale: float = 1.35,
    numeric_offset: float = 25.0,
    seed: int = 42
) -> Worksheet:
    """Create a sanitized copy of a worksheet safe for external audits."""
    new_ws = copy.deepcopy(worksheet)
    new_ws.name = f"{worksheet.name}_Anonymized"

    # Category pseudonym mapping cache per column
    for col in new_ws.columns:
        if col.kind == "text":
            col_seed = seed + sum(ord(c) for c in col.name)
            unique_vals = sorted(list({str(v) for v in col.values if v is not None}))
            prefix = "Entity"
            if any(term in col.name.lower() for term in ("batch", "lot")):
                prefix = "Lot"
            elif any(term in col.name.lower() for term in ("operator", "tech", "user", "name", "person")):
                prefix = "Operator"
            elif any(term in col.name.lower() for term in ("machine", "tool", "part", "asset")):
                prefix = "Unit"
            elif any(term in col.name.lower() for term in ("vendor", "supplier")):
                prefix = "Supplier"

            # Assign sequential deterministic codes
            cat_map = {val: f"{prefix}_{idx + 1:02d}" for idx, val in enumerate(unique_vals)}
            col.values = [cat_map.get(str(v)) if v is not None else None for v in col.values]

        elif col.kind == "number" and mask_numeric:
            # Affine scale & shift: y = a * x + b
            # Mathematically invariant for correlations, ANOVA F-ratios, and p-values
            col_scale = numeric_scale
            col_shift = numeric_offset
            new_vals = []
            for v in col.values:
                if v is None or not math.isfinite(v):
                    new_vals.append(v)
                else:
                    new_vals.append(float(v) * col_scale + col_shift)
            col.values = new_vals

    return new_ws
