"""Cause-and-Effect (Fishbone / Ishikawa) Diagram engine matching Minitab 22 specifications (%Fishbone).

References:
- Ishikawa, K. (1982). Guide to Quality Control. Asian Productivity Organization.
- Minitab 22 Statistical Methods Reference: Cause-and-Effect Diagram (%Fishbone).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

DEFAULT_BRANCH_LABELS = [
    "Personnel",
    "Machines",
    "Materials",
    "Methods",
    "Measurements",
    "Environment",
]


def build_cause_and_effect(
    branches: Sequence[Dict[str, Any]],
    effect: str = "Effect",
    title: str = "",
    no_empty: bool = False,
    no_labels: bool = False,
) -> Dict[str, Any]:
    """Construct structured Cause-and-Effect model from branch causes and metadata.

    Args:
        branches: Sequence of dicts with 'label' (str) and 'causes' (list of str or non-empty items).
        effect: Name of the effect / problem statement (right end of spine).
        title: Custom diagram title.
        no_empty: If True, suppress branches that contain no causes.
        no_labels: If True, suppress the branch category label boxes.
    """
    clean_branches: List[Dict[str, Any]] = []

    for idx, b in enumerate(branches):
        default_lbl = DEFAULT_BRANCH_LABELS[idx] if idx < len(DEFAULT_BRANCH_LABELS) else f"Branch {idx + 1}"
        raw_label = str(b.get("label", "") or "").strip() or default_lbl
        raw_causes = b.get("causes", [])

        # Clean causes list: non-empty, string-converted, stripped
        cleaned_causes = []
        for c in raw_causes:
            if c is not None:
                s = str(c).strip()
                if s and s.lower() != "nan" and s.lower() != "none":
                    cleaned_causes.append(s)

        if no_empty and not cleaned_causes:
            continue

        clean_branches.append({
            "branch_index": idx + 1,
            "label": "" if no_labels else raw_label,
            "causes": cleaned_causes,
            "count": len(cleaned_causes),
        })

    effect_clean = str(effect or "Quality Characteristic / Effect").strip()
    title_clean = str(title or f"Cause-and-Effect Diagram for {effect_clean}").strip()

    total_causes = sum(b["count"] for b in clean_branches)

    return {
        "analysis": "cause_and_effect",
        "title": title_clean,
        "effect": effect_clean,
        "branches": clean_branches,
        "branch_count": len(clean_branches),
        "total_causes": total_causes,
        "options": {
            "no_empty": no_empty,
            "no_labels": no_labels,
        },
    }
