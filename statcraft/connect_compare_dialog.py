"""StatCraft Connect — Cross-Engine Execution Comparison Dialog.

Compares StatCraft native statistical computations against R engine outputs
using identical source data, aligned settings, and explicit numerical tolerances.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QGroupBox,
    QGridLayout,
    QApplication,
    QFrame,
)

from .connect import ConnectedAnalysis
from .connect_r import compare_implementations
from .r_bridge import is_r_available, execute_r_code


def _is_dark_active(widget=None) -> bool:
    if widget is not None:
        try:
            win = widget.window()
            if win and hasattr(win, "_dark_mode"):
                return bool(win._dark_mode)
        except Exception:
            pass
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return False


def run_cross_engine_comparison(
    connected: ConnectedAnalysis,
    worksheet: Any,
    tolerance: float = 1e-4,
) -> Dict[str, Any]:
    """Execute R script with comparison instrumentation and verify against StatCraft."""
    if not is_r_available():
        return {
            "success": False,
            "error": "R is not detected on this system. Install R to enable execution comparison.",
        }

    # Append comparison extractor to R script
    instrumented_code = (
        connected.r_script
        + "\n\n# --- STATCRAFT CROSS-ENGINE COMPARISON PROBE ---\n"
        + "tryCatch({\n"
        + "  m_obj <- if (exists('fit')) fit else if (exists('model')) model else NULL\n"
        + "  if (is.null(m_obj)) stop('No fitted model object found.')\n"
        + "  if (inherits(m_obj, 'aov')) {\n"
        + "    m_sum <- summary(m_obj)\n"
        + "    tab <- m_sum[[1]]\n"
        + "    cat('\\n===STATCRAFT_COMPARE_BEGIN===\\n')\n"
        + "    for (rn in rownames(tab)) {\n"
        + "      rn_clean <- trimws(rn)\n"
        + "      if (rn_clean != '') {\n"
        + "        cat(sprintf('ANOVA_ROW|%s|%d|%.9f|%.9f|%.9f|%.9f\\n', rn_clean, tab[rn, 'Df'], tab[rn, 'Sum Sq'], tab[rn, 'Mean Sq'], ifelse(is.na(tab[rn, 'F value']), 0, tab[rn, 'F value']), ifelse(is.na(tab[rn, 'Pr(>F)']), 1, tab[rn, 'Pr(>F)'])))\n"
        + "      }\n"
        + "    }\n"
        + "    f_stat <- tab[1, 'F value']\n"
        + "    p_val <- tab[1, 'Pr(>F)']\n"
        + "    ss_factor <- tab[1, 'Sum Sq']\n"
        + "    ss_total <- sum(tab[, 'Sum Sq'], na.rm=TRUE)\n"
        + "    r_sq <- ss_factor / ss_total\n"
        + "    cat(sprintf('STAT|f_stat|%.9f\\n', if (!is.na(f_stat)) f_stat else 0))\n"
        + "    cat(sprintf('STAT|p_value|%.9f\\n', if (!is.na(p_val)) p_val else 1))\n"
        + "    cat(sprintf('STAT|r_squared|%.9f\\n', if (!is.na(r_sq)) r_sq else 0))\n"
        + "    cat(sprintf('STAT|df_factor|%d\\n', as.integer(tab[1, 'Df'])))\n"
        + "    cat(sprintf('STAT|df_error|%d\\n', as.integer(tab[2, 'Df'])))\n"
        + "    cat(sprintf('STAT|n|%d\\n', length(m_obj$residuals)))\n"
        + "    cat('===STATCRAFT_COMPARE_END===\\n')\n"
        + "  } else {\n"
        + "    m_sum <- summary(m_obj)\n"
        + "    cf <- coef(m_sum)\n"
        + "    cat('\\n===STATCRAFT_COMPARE_BEGIN===\\n')\n"
        + "    for (rn in rownames(cf)) {\n"
        + "      cat(sprintf('TERM|%s|%.9f|%.9f|%.9f\\n', rn, cf[rn, 1], cf[rn, 2], cf[rn, 4]))\n"
        + "    }\n"
        + "    cat(sprintf('STAT|r_squared|%.9f\\n', if (!is.null(m_sum$r.squared)) m_sum$r.squared else 0))\n"
        + "    cat(sprintf('STAT|adj_r_squared|%.9f\\n', if (!is.null(m_sum$adj.r.squared)) m_sum$adj.r.squared else 0))\n"
        + "    cat(sprintf('STAT|sigma|%.9f\\n', if (!is.null(m_sum$sigma)) m_sum$sigma else 0))\n"
        + "    cat(sprintf('STAT|n|%d\\n', length(m_obj$residuals)))\n"
        + "    cat('===STATCRAFT_COMPARE_END===\\n')\n"
        + "  }\n"
        + "}, error = function(e) {\n"
        + "  cat(sprintf('===STATCRAFT_COMPARE_ERROR|%s===\\n', conditionMessage(e)))\n"
        + "})\n"
    )

    res = execute_r_code(instrumented_code, worksheet=worksheet, persist_session=True)
    if not res.get("success"):
        return {
            "success": False,
            "error": res.get("stderr") or "R script execution failed.",
        }

    stdout = res.get("stdout", "")
    match = re.search(r"===STATCRAFT_COMPARE_BEGIN===\n(.*?)\n===STATCRAFT_COMPARE_END===", stdout, re.DOTALL)
    if not match:
        err_m = re.search(r"===STATCRAFT_COMPARE_ERROR\|(.*?)===", stdout)
        err_txt = err_m.group(1) if err_m else "Failed to parse R model metrics."
        return {"success": False, "error": err_txt}

    block = match.group(1)
    r_coefs = {}
    r_stats = {}

    for line in block.splitlines():
        line = line.strip()
        if line.startswith("TERM|"):
            parts = line.split("|")
            if len(parts) >= 3:
                try:
                    r_coefs[parts[1]] = float(parts[2])
                except ValueError:
                    pass
        elif line.startswith("STAT|"):
            parts = line.split("|")
            if len(parts) >= 3:
                try:
                    r_stats[parts[1]] = float(parts[2])
                except ValueError:
                    pass

    if connected.analysis_type == "oneway_anova":
        comp = compare_implementations(connected, r_stats, tolerance=tolerance)
    else:
        comp = compare_implementations(connected, r_coefs, tolerance=tolerance)
    return {
        "success": True,
        "comparison": comp,
        "r_stats": r_stats,
        "stdout": stdout,
    }


class CompareImplementationsDialog(QDialog):
    """Side-by-side numerical execution comparison between StatCraft and R."""

    def __init__(
        self,
        connected: ConnectedAnalysis,
        comp_result: Dict[str, Any],
        parent: Optional[Any] = None,
    ):
        super().__init__(parent)
        self.connected = connected
        self.comp_result = comp_result
        self.comparison = comp_result.get("comparison", {})
        self.r_stats = comp_result.get("r_stats", {})

        self.setWindowTitle("StatCraft Connect — Execution Comparison")
        self.resize(780, 580)
        self.setMinimumSize(680, 480)
        self.setSizeGripEnabled(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        dark = _is_dark_active(self)
        is_anova = self.connected.analysis_type == "oneway_anova"

        # Header Card
        header_card = QFrame()
        if dark:
            header_card.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 8px;")
        else:
            header_card.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 8px;")
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(10, 8, 10, 8)

        v_info = QVBoxLayout()
        v_info.setSpacing(4)
        title_lbl = QLabel(f"<b>Model:</b> {self.connected.title}")
        title_lbl.setStyleSheet("font-size: 11pt; color: #f4f4f5;" if dark else "font-size: 11pt; color: #0f172a;")
        engine_str = "R <code>base::aov</code>" if is_anova else "R <code>base::lm</code>"
        meta_lbl = QLabel(
            f"<b>Engines:</b> StatCraft Native ({self.connected.analysis_type}) vs. {engine_str} | "
            f"<b>N:</b> {len(self.connected.fitted_row_ids)} observations"
        )
        meta_lbl.setStyleSheet("color: #a1a1aa; font-size: 9pt;" if dark else "color: #475569; font-size: 9pt;")
        v_info.addWidget(title_lbl)
        v_info.addWidget(meta_lbl)
        h_layout.addLayout(v_info, 1)

        aligned = self.comparison.get("aligned", False)
        status_badge = QLabel("  [OK] Complete Agreement  " if aligned else "  [!] Discrepancy Detected  ")
        if aligned:
            if dark:
                status_badge.setStyleSheet(
                    "background-color: #064e3b; color: #6ee7b7; border: 1px solid #059669; font-weight: bold; border-radius: 4px; padding: 6px 12px; font-size: 10pt;"
                )
            else:
                status_badge.setStyleSheet(
                    "background-color: #dcfce7; color: #15803d; font-weight: bold; border-radius: 4px; padding: 6px 12px; font-size: 10pt;"
                )
        else:
            if dark:
                status_badge.setStyleSheet(
                    "background-color: #451a03; color: #fcd34d; border: 1px solid #b45309; font-weight: bold; border-radius: 4px; padding: 6px 12px; font-size: 10pt;"
                )
            else:
                status_badge.setStyleSheet(
                    "background-color: #fef3c7; color: #b45309; font-weight: bold; border-radius: 4px; padding: 6px 12px; font-size: 10pt;"
                )
        h_layout.addWidget(status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(header_card)

        # Comparison Table
        table_lbl = QLabel("<b>ANOVA Metrics & Tolerances</b>" if is_anova else "<b>Parameter Estimates & Tolerances</b>")
        table_lbl.setStyleSheet("font-size: 9.5pt; color: #f4f4f5;" if dark else "font-size: 9.5pt; color: #1e293b;")
        layout.addWidget(table_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        if is_anova:
            self.table.setHorizontalHeaderLabels([
                "Metric / Source",
                "StatCraft Value",
                "R aov Value",
                "Absolute Diff",
                "Tolerance",
                "Status",
            ])
        else:
            self.table.setHorizontalHeaderLabels([
                "Term",
                "StatCraft Estimate",
                "R Estimate",
                "Absolute Diff",
                "Tolerance",
                "Status",
            ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        comps = self.comparison.get("comparisons", [])
        self.table.setRowCount(len(comps))
        for row_idx, item in enumerate(comps):
            term_item = QTableWidgetItem(str(item.get("term", "")))
            sc_val = item.get("statcraft")
            sc_str = f"{sc_val:.8f}" if sc_val is not None else "—"
            sc_item = QTableWidgetItem(sc_str)
            sc_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            r_val = item.get("r")
            r_str = f"{r_val:.8f}" if r_val is not None else "—"
            r_item = QTableWidgetItem(r_str)
            r_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            diff_val = item.get("diff")
            diff_str = f"{diff_val:.2e}" if diff_val is not None else "—"
            diff_item = QTableWidgetItem(diff_str)
            diff_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            tol_item = QTableWidgetItem(f"{self.comparison.get('tolerance', 1e-4):.1e}")
            tol_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            status_str = "Aligned" if item.get("aligned") else "Discrepancy"
            status_item = QTableWidgetItem(status_str)
            if item.get("aligned"):
                status_item.setForeground(QColor("#6ee7b7" if dark else "#15803d"))
            else:
                status_item.setForeground(QColor("#fcd34d" if dark else "#b45309"))

            self.table.setItem(row_idx, 0, term_item)
            self.table.setItem(row_idx, 1, sc_item)
            self.table.setItem(row_idx, 2, r_item)
            self.table.setItem(row_idx, 3, diff_item)
            self.table.setItem(row_idx, 4, tol_item)
            self.table.setItem(row_idx, 5, status_item)

        layout.addWidget(self.table, 1)

        # Model Diagnostics Comparison Group
        diag_group = QGroupBox("Model Summary & Fit Diagnostics")
        diag_layout = QGridLayout(diag_group)

        diag_layout.addWidget(QLabel("<b>Metric</b>"), 0, 0)
        diag_layout.addWidget(QLabel("<b>StatCraft Native</b>"), 0, 1)
        diag_layout.addWidget(QLabel(f"<b>{engine_str}</b>"), 0, 2)
        diag_layout.addWidget(QLabel("<b>Alignment</b>"), 0, 3)

        sc_stats = self.connected.fit_statistics
        n_sc = len(self.connected.fitted_row_ids)
        n_r = int(self.r_stats.get("n", n_sc))

        if is_anova:
            f_sc = sc_stats.get("f_stat")
            f_r = self.r_stats.get("f_stat")
            p_sc = sc_stats.get("p_value")
            p_r = self.r_stats.get("p_value")
            r2_sc = sc_stats.get("r_squared")
            r2_r = self.r_stats.get("r_squared")
            df_f_sc = sc_stats.get("df_factor")
            df_f_r = self.r_stats.get("df_factor")
            df_e_sc = sc_stats.get("df_error")
            df_e_r = self.r_stats.get("df_error")

            metrics = [
                ("Sample Size (N)", f"{n_sc}", f"{n_r}", "Equal" if n_sc == n_r else "Mismatch"),
                ("Factor DF", f"{df_f_sc}" if df_f_sc is not None else "—", f"{int(df_f_r)}" if df_f_r is not None else "—", "Equal" if df_f_sc == df_f_r else "Mismatch"),
                ("Error DF", f"{df_e_sc}" if df_e_sc is not None else "—", f"{int(df_e_r)}" if df_e_r is not None else "—", "Equal" if df_e_sc == df_e_r else "Mismatch"),
                ("F-Statistic", f"{f_sc:.6f}" if f_sc is not None else "—", f"{f_r:.6f}" if f_r is not None else "—", "Aligned" if (f_sc is not None and f_r is not None and abs(f_sc - f_r) <= 1e-4) else "Discrepancy"),
                ("P-Value", f"{p_sc:.6f}" if p_sc is not None else "—", f"{p_r:.6f}" if p_r is not None else "—", "Aligned" if (p_sc is not None and p_r is not None and abs(p_sc - p_r) <= 1e-4) else "Discrepancy"),
                ("R-Squared", f"{r2_sc:.6f}" if r2_sc is not None else "—", f"{r2_r:.6f}" if r2_r is not None else "—", "Aligned" if (r2_sc is not None and r2_r is not None and abs(r2_sc - r2_r) <= 1e-4) else "Discrepancy"),
            ]
        else:
            r2_sc = sc_stats.get("r_squared")
            r2_r = self.r_stats.get("r_squared")
            adj_sc = sc_stats.get("adjusted_r_squared")
            adj_r = self.r_stats.get("adj_r_squared")
            s_sc = sc_stats.get("residual_stdev")
            s_r = self.r_stats.get("sigma")

            metrics = [
                ("Sample Size (N)", f"{n_sc}", f"{n_r}", "Equal" if n_sc == n_r else "Mismatch"),
                ("R-Squared", f"{r2_sc:.6f}" if r2_sc is not None else "—", f"{r2_r:.6f}" if r2_r is not None else "—", "Aligned" if (r2_sc is not None and r2_r is not None and abs(r2_sc - r2_r) <= 1e-4) else "Discrepancy"),
                ("Adjusted R-Squared", f"{adj_sc:.6f}" if adj_sc is not None else "—", f"{adj_r:.6f}" if adj_r is not None else "—", "Aligned" if (adj_sc is not None and adj_r is not None and abs(adj_sc - adj_r) <= 1e-4) else "Discrepancy"),
                ("Residual Std Error (s)", f"{s_sc:.6f}" if s_sc is not None else "—", f"{s_r:.6f}" if s_r is not None else "—", "Aligned" if (s_sc is not None and s_r is not None and abs(s_sc - s_r) <= 1e-4) else "Discrepancy"),
            ]

        for row_i, (m_name, sc_s, r_s, stat_s) in enumerate(metrics, start=1):
            diag_layout.addWidget(QLabel(m_name), row_i, 0)
            diag_layout.addWidget(QLabel(sc_s), row_i, 1)
            diag_layout.addWidget(QLabel(r_s), row_i, 2)
            lbl = QLabel(stat_s)
            is_good = stat_s in ("Equal", "Aligned")
            lbl.setStyleSheet(f"color: {'#6ee7b7' if dark else '#15803d'}; font-weight: bold;" if is_good else f"color: {'#fcd34d' if dark else '#b45309'};")
            diag_layout.addWidget(lbl, row_i, 3)

        layout.addWidget(diag_group)

        # Settings Verification Note
        if is_anova:
            note_text = "<b>Settings Alignment:</b> Analysis of Variance (aov) model, balanced/unbalanced group factor coding, listwise missing-value policy."
        else:
            note_text = "<b>Settings Alignment:</b> Ordinary Least Squares (OLS) estimation, complete-case listwise missing-value policy, identical 95% confidence intervals."
        note = QLabel(note_text)
        note.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        note.setWordWrap(True)
        layout.addWidget(note)
        note.setStyleSheet("color: #64748b; font-size: 8.5pt;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        copy_btn = QPushButton("Copy Summary")
        copy_btn.clicked.connect(self._copy_summary)
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _copy_summary(self):
        comps = self.comparison.get("comparisons", [])
        lines = [
            f"StatCraft Connect — Execution Comparison Report",
            f"Model: {self.connected.title}",
            f"Engines: StatCraft Native vs. R base::lm",
            f"Overall Status: {'Aligned' if self.comparison.get('aligned') else 'Discrepancy'}",
            f"",
            f"{'Term':<20} {'StatCraft':<15} {'R':<15} {'Diff':<12} {'Status'}",
            f"{'-'*70}",
        ]
        for c in comps:
            sc_val = f"{c.get('statcraft', 0):.8f}" if c.get('statcraft') is not None else "—"
            r_val = f"{c.get('r', 0):.8f}" if c.get('r') is not None else "—"
            diff_val = f"{c.get('diff', 0):.2e}" if c.get('diff') is not None else "—"
            lines.append(f"{str(c.get('term')):<20} {sc_val:<15} {r_val:<15} {diff_val:<12} {c.get('status')}")
        QApplication.clipboard().setText("\n".join(lines))
