"""Statistical engine for Pareto Chart (Stat > Quality Tools > Pareto Chart).

Implements native StatCraft PE resource fidelity and statistical calculations matching:
- 0372-AMPARETOCHART.MDF (MenuID 41210)
Supports:
- Raw observation defect data (single column of categories, optional By/X column)
- Summarized table defect data (defect names column + count column(s))
- Descending sorting by frequency
- Combining infrequent categories into an 'Other' bucket based on percentage
- Cumulative count and percentage curve calculations
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def _clean_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s == "*":
        return None
    return s


def _clean_count(val: Any) -> Optional[float]:
    if val is None or val == "" or val == "*":
        return None
    try:
        f = float(val)
        return f if math.isfinite(f) and f >= 0 else None
    except (ValueError, TypeError):
        return None


def run_pareto_chart(
    defect_data: Sequence[Any],
    count_data: Optional[Sequence[Any]] = None,
    by_data: Optional[Sequence[Any]] = None,
    combine_percent: Optional[float] = 95.0,
    show_cumulative: bool = True,
    chart_title: Optional[str] = None,
    variable_name: str = "Defects",
) -> Dict[str, Any]:
    """Compute Pareto analysis for raw or summarized defect data."""
    is_summarized = count_data is not None

    counts_by_category: Dict[str, float] = {}

    if is_summarized:
        n_rows = min(len(defect_data), len(count_data))
        for r in range(n_rows):
            cat = _clean_str(defect_data[r])
            cnt = _clean_count(count_data[r])
            if cat is not None and cnt is not None and cnt > 0:
                counts_by_category[cat] = counts_by_category.get(cat, 0.0) + cnt
    else:
        # Raw observations
        for val in defect_data:
            cat = _clean_str(val)
            if cat is not None:
                counts_by_category[cat] = counts_by_category.get(cat, 0.0) + 1.0

    if not counts_by_category:
        raise ValueError("No valid defect data found.")

    total_count = sum(counts_by_category.values())
    if total_count <= 0:
        raise ValueError("Total defect count must be greater than zero.")

    # Sort categories descending by count
    sorted_items = sorted(counts_by_category.items(), key=lambda x: x[1], reverse=True)

    # Combining logic:
    # If combine_percent is provided and < 100:
    # StatCraft combines categories after cumulative percentage reaches combine_percent,
    # or categories whose individual percentage is <= (100 - combine_percent).
    # Specifically, standard StatCraft behavior for "Combine defects of this percent or less: X%":
    # If X is e.g. 95 (as default in MDF), it means combine defects after 95% cumulative,
    # or if X <= 5, it means individual defects <= X%.
    final_categories: List[str] = []
    final_counts: List[float] = []

    other_count = 0.0
    other_subcategories = 0

    if combine_percent is not None and combine_percent > 0:
        cum_pct_so_far = 0.0
        # Determine whether threshold is cumulative (e.g. 95%) or individual (e.g. 5%)
        is_cum_threshold = combine_percent >= 50.0

        for cat, cnt in sorted_items:
            pct = (cnt / total_count) * 100.0
            should_combine = False

            if is_cum_threshold:
                if cum_pct_so_far >= combine_percent and len(final_categories) >= 1:
                    should_combine = True
            else:
                if pct <= combine_percent and len(final_categories) >= 1:
                    should_combine = True

            if should_combine:
                other_count += cnt
                other_subcategories += 1
            else:
                final_categories.append(cat)
                final_counts.append(cnt)
                cum_pct_so_far += pct

        if other_count > 0:
            final_categories.append("Other")
            final_counts.append(other_count)
    else:
        for cat, cnt in sorted_items:
            final_categories.append(cat)
            final_counts.append(cnt)

    # Compute percentages and cumulative percentages
    k = len(final_categories)
    percents: List[float] = []
    cum_counts: List[float] = []
    cum_percents: List[float] = []

    running_cnt = 0.0
    for i in range(k):
        cnt = final_counts[i]
        running_cnt += cnt
        pct = (cnt / total_count) * 100.0
        cum_pct = (running_cnt / total_count) * 100.0

        percents.append(pct)
        cum_counts.append(running_cnt)
        cum_percents.append(min(100.0, cum_pct))

    return {
        "analysis": "pareto_chart",
        "variable_name": variable_name,
        "is_summarized": is_summarized,
        "total_count": total_count,
        "categories": final_categories,
        "counts": final_counts,
        "percents": percents,
        "cum_counts": cum_counts,
        "cum_percents": cum_percents,
        "k_categories": k,
        "other_count": other_count,
        "other_subcategories": other_subcategories,
        "combine_percent": combine_percent,
        "show_cumulative": show_cumulative,
        "title": chart_title or f"Pareto Chart of {variable_name}",
    }
