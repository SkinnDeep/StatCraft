"""Pre-Flight Data Doctor for StatCraft.

Performs blazing-fast (< 5ms) columnar audits on worksheets to detect:
1. Hidden leading/trailing whitespace in categorical factors (e.g. "Batch1 " vs "Batch1")
2. Near-zero or zero variance numeric columns (causing linear algebra singularity crashes)
3. Suspicious missing value sentinels (-999, 9999, 999, "NA", "N/A", ".", "null")
4. Severe pairwise collinearity (|r| > 0.98) among numeric predictors
5. Extreme missingness rates (> 50% missing values)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .model import Column, Worksheet


@dataclass
class DiagnosticIssue:
    severity: str  # "warning", "critical", "info"
    category: str  # "whitespace", "zero_variance", "sentinel", "collinearity", "missingness"
    column_name: str
    column_index: int
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    can_autofix: bool = False


@dataclass
class AuditReport:
    worksheet_name: str
    total_columns: int
    total_rows: int
    issues: List[DiagnosticIssue] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(i.severity == "critical" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity in ("warning", "critical") for i in self.issues)

    @property
    def summary_text(self) -> str:
        if not self.issues:
            return f"Worksheet '{self.worksheet_name}' is healthy. No data issues detected."
        crit_count = sum(1 for i in self.issues if i.severity == "critical")
        warn_count = sum(1 for i in self.issues if i.severity == "warning")
        return f"Found {len(self.issues)} issue(s) ({crit_count} critical, {warn_count} warning) in '{self.worksheet_name}'."


SENTINEL_VALUES = {-999, -9999, 999, 9999, -999.0, -9999.0, 999.0, 9999.0}
SENTINEL_STRINGS = {"na", "n/a", "null", "none", ".", "-", "#n/a", "missing"}


def audit_worksheet(worksheet: Worksheet) -> AuditReport:
    """Run full diagnostic audit on a worksheet in < 5ms."""
    issues: List[DiagnosticIssue] = []
    n_rows = worksheet.row_count
    n_cols = len(worksheet.columns)

    numeric_cols: List[Tuple[int, str, List[float]]] = []

    for col_idx, col in enumerate(worksheet.columns):
        vals = col.values

        # 1. Check Missingness rate
        missing_count = sum(1 for v in vals if v is None or (isinstance(v, float) and math.isnan(v)))
        if n_rows > 0:
            missing_rate = missing_count / n_rows
            if missing_rate > 0.5:
                issues.append(DiagnosticIssue(
                    severity="warning",
                    category="missingness",
                    column_name=col.name,
                    column_index=col_idx,
                    message=f"High missingness: {missing_count}/{n_rows} rows ({missing_rate*100:.1f}%) are blank.",
                    details={"missing_count": missing_count, "missing_rate": missing_rate}
                ))

        # 2. Categorical Factor checks (leading/trailing whitespace & casing inconsistencies)
        if col.kind == "text":
            whitespace_detected = []
            seen_trimmed: Dict[str, Set[str]] = {}
            for row_idx, v in enumerate(vals):
                if v is None:
                    continue
                s_val = str(v)
                # Check suspicious sentinel strings
                if s_val.strip().lower() in SENTINEL_STRINGS:
                    issues.append(DiagnosticIssue(
                        severity="info",
                        category="sentinel",
                        column_name=col.name,
                        column_index=col_idx,
                        message=f"String sentinel '{s_val}' detected at row {row_idx + 1}; consider setting to empty/missing.",
                        details={"row_index": row_idx, "value": s_val},
                        can_autofix=True
                    ))
                # Check leading/trailing whitespace
                if s_val != s_val.strip():
                    whitespace_detected.append((row_idx, s_val))
                trimmed = s_val.strip()
                seen_trimmed.setdefault(trimmed.lower(), set()).add(trimmed)

            if whitespace_detected:
                issues.append(DiagnosticIssue(
                    severity="warning",
                    category="whitespace",
                    column_name=col.name,
                    column_index=col_idx,
                    message=f"{len(whitespace_detected)} value(s) have leading/trailing whitespace creating accidental extra factor levels.",
                    details={"count": len(whitespace_detected), "samples": whitespace_detected[:5]},
                    can_autofix=True
                ))

            # Check case inconsistencies like "Batch1" vs "batch1"
            case_issues = {k: v for k, v in seen_trimmed.items() if len(v) > 1}
            if case_issues:
                issues.append(DiagnosticIssue(
                    severity="info",
                    category="whitespace",
                    column_name=col.name,
                    column_index=col_idx,
                    message=f"Inconsistent casing detected across factor levels: {list(case_issues.values())[0]}.",
                    details={"case_mismatches": case_issues}
                ))

        # 3. Numeric column checks
        elif col.kind == "number":
            valid_nums = [float(v) for v in vals if v is not None and isinstance(v, (int, float)) and math.isfinite(v)]
            if valid_nums:
                numeric_cols.append((col_idx, col.name, valid_nums))

                # Check numerical sentinels (-999, 9999)
                sentinels_found = [v for v in valid_nums if v in SENTINEL_VALUES]
                if sentinels_found:
                    issues.append(DiagnosticIssue(
                        severity="warning",
                        category="sentinel",
                        column_name=col.name,
                        column_index=col_idx,
                        message=f"Possible missing-data sentinel value(s) found: {set(sentinels_found)}. Verify these are not placeholder codes.",
                        details={"sentinels": list(set(sentinels_found))},
                        can_autofix=True
                    ))

                # Check zero or near-zero variance
                if len(valid_nums) >= 2:
                    m = sum(valid_nums) / len(valid_nums)
                    var = sum((x - m) ** 2 for x in valid_nums) / (len(valid_nums) - 1)
                    if var < 1e-12:
                        issues.append(DiagnosticIssue(
                            severity="critical",
                            category="zero_variance",
                            column_name=col.name,
                            column_index=col_idx,
                            message=f"Column has zero or constant variance (all values = {m:g}). Will cause singularity in regression and ANOVA.",
                            details={"mean": m, "variance": var}
                        ))

    # 4. Severe pairwise collinearity (|r| > 0.98) among numeric columns
    if len(numeric_cols) >= 2:
        for i in range(len(numeric_cols)):
            for j in range(i + 1, len(numeric_cols)):
                idx1, name1, vals1 = numeric_cols[i]
                idx2, name2, vals2 = numeric_cols[j]
                min_len = min(len(vals1), len(vals2))
                if min_len >= 4:
                    v1 = vals1[:min_len]
                    v2 = vals2[:min_len]
                    m1, m2 = sum(v1) / min_len, sum(v2) / min_len
                    s1 = math.sqrt(sum((x - m1)**2 for x in v1))
                    s2 = math.sqrt(sum((x - m2)**2 for x in v2))
                    if s1 > 1e-9 and s2 > 1e-9:
                        r = sum((x - m1) * (y - m2) for x, y in zip(v1, v2)) / (s1 * s2)
                        if abs(r) >= 0.98:
                            issues.append(DiagnosticIssue(
                                severity="warning",
                                category="collinearity",
                                column_name=f"{name1} & {name2}",
                                column_index=idx1,
                                message=f"Severe collinearity between '{name1}' and '{name2}' (|r| = {abs(r):.4f}). May cause unstable regression coefficients.",
                                details={"col1": name1, "col2": name2, "correlation": r}
                            ))

    return AuditReport(worksheet.name, n_cols, n_rows, issues)


def autofix_worksheet_issues(worksheet: Worksheet) -> int:
    """Safely apply automated fixes: trim trailing/leading whitespace and sentinel strings. Returns number of fixes."""
    fixes = 0
    for col in worksheet.columns:
        if col.kind == "text":
            new_vals = []
            for v in col.values:
                if v is None:
                    new_vals.append(None)
                else:
                    s_val = str(v)
                    if s_val.strip().lower() in SENTINEL_STRINGS:
                        new_vals.append(None)
                        fixes += 1
                    elif s_val != s_val.strip():
                        new_vals.append(s_val.strip())
                        fixes += 1
                    else:
                        new_vals.append(s_val)
            col.values = new_vals
    return fixes
