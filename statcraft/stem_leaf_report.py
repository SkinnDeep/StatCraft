"""Stem-and-Leaf Report Formatter for StatCraft."""
from __future__ import annotations


def format_stem_leaf_report(result: dict) -> str:
    lines = result.get('lines', [])
    return "\n".join(lines)
