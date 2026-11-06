"""StatCraft Connect — Hub, Architecture Overview, and Visual Bridge Controls.

Connects Minitab quality & SPC procedures, JMP interactive visual exploration,
and Positron-style R Workbench into a unified, durable statistical workflow.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, TYPE_CHECKING
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QGroupBox,
    QDialogButtonBox,
    QScrollArea,
    QWidget,
)

from .model import Column, Worksheet

if TYPE_CHECKING:
    from .modern_app import ModernWindow
    from .connect import ConnectedAnalysis


def _is_dark_active(widget=None) -> bool:
    if widget is not None:
        try:
            win = widget.window()
            if win and hasattr(win, "_dark_mode"):
                return bool(win._dark_mode)
        except Exception:
            pass
    app = QApplication.instance()
    if app:
        return app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    return False


def create_chemical_process_sample() -> Worksheet:
    """Generate a realistic, deterministic 25-observation chemical engineering dataset.
    
    Variables:
    - Yield (%): Reaction conversion efficiency (Response)
    - Temperature (°C): Continuous process factor [140 - 165]
    - Pressure (psi): Continuous process factor [40 - 65]
    - Catalyst: Categorical text factor ("Alpha" / "Beta")
    """
    temps = [
        140.0, 142.5, 145.0, 147.5, 150.0, 152.5, 155.0, 157.5, 160.0, 162.5,
        141.0, 143.5, 146.0, 148.5, 151.0, 153.5, 156.0, 158.5, 161.0, 163.5,
        140.5, 145.5, 150.5, 155.5, 160.5
    ]
    pressures = [
        40.0, 42.0, 45.0, 47.0, 50.0, 52.0, 55.0, 57.0, 60.0, 62.0,
        60.0, 58.0, 55.0, 52.0, 50.0, 48.0, 45.0, 42.0, 40.0, 62.0,
        41.0, 46.0, 51.0, 56.0, 61.0
    ]
    catalysts = [
        "Alpha", "Alpha", "Alpha", "Alpha", "Alpha", "Beta", "Beta", "Beta", "Beta", "Beta",
        "Alpha", "Alpha", "Alpha", "Beta", "Beta", "Beta", "Alpha", "Alpha", "Beta", "Beta",
        "Alpha", "Beta", "Alpha", "Beta", "Alpha"
    ]
    # Yield = 42.0 + 0.32 * Temp + 0.16 * Pressure + (2.5 if Beta else 0.0) + noise
    yields = []
    for i, (t, p, cat) in enumerate(zip(temps, pressures, catalysts)):
        cat_effect = 2.4 if cat == "Beta" else 0.0
        synthetic_noise = math.sin(i * 1.7) * 0.45
        y = round(42.0 + 0.32 * (t - 140.0) + 0.16 * (p - 40.0) + cat_effect + synthetic_noise, 2)
        yields.append(y)

    ws = Worksheet("Chemical_Process", [
        Column("Yield", "number", yields),
        Column("Temperature", "number", temps),
        Column("Pressure", "number", pressures),
        Column("Catalyst", "text", catalysts),
    ])
    from .connect import ensure_worksheet_identities
    ensure_worksheet_identities(ws)
    return ws


class ConnectOverviewDialog(QDialog):
    """Publication-quality guide explaining how StatCraft Connect unifies Minitab, JMP, and R."""

    def __init__(self, window: "ModernWindow", parent=None):
        super().__init__(parent or window)
        self.window = window
        self.setWindowTitle("StatCraft Connect — What is Connect?")
        self.setMinimumSize(760, 500)
        self.resize(840, 580)
        self.setSizeGripEnabled(True)
        self._init_ui()

    def _init_ui(self):
        dark = _is_dark_active(self)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 18)

        # Header Hero Banner
        hero = QFrame()
        if dark:
            hero.setStyleSheet("background-color: #18181b; border: 1px solid #0284c7; border-radius: 8px; padding: 14px;")
        else:
            hero.setStyleSheet("background-color: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 14px;")
        h_layout = QVBoxLayout(hero)
        h_layout.setSpacing(6)

        title = QLabel("<b>StatCraft Connect</b>: The Bridge Across Statistical Paradigms")
        title.setStyleSheet("font-size: 13pt; color: #0284c7;" if not dark else "font-size: 13pt; color: #38bdf8;")
        h_layout.addWidget(title)

        desc = QLabel(
            "StatCraft Connect unifies <b>three historically disconnected statistical tools</b> into one seamless desktop "
            "workflow. Rather than exporting CSVs, re-specifying models, or losing row selections, Connect preserves your "
            "worksheet data, variable roles, model definitions, and observation identities across all three modes."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 9.5pt; color: #334155;" if not dark else "font-size: 9.5pt; color: #cbd5e1;")
        h_layout.addWidget(desc)
        layout.addWidget(hero)

        # 3 Columns Visual Comparison
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        def make_pillar_card(badge_text: str, badge_color: str, heading: str, items: list[str]) -> QFrame:
            card = QFrame()
            if dark:
                card.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 12px;")
            else:
                card.setStyleSheet("background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px;")
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(8)

            badge = QLabel(f"<b>{badge_text}</b>")
            badge.setStyleSheet(f"color: {badge_color}; font-size: 8.5pt; text-transform: uppercase; font-weight: 700;")
            c_lay.addWidget(badge)

            h_lbl = QLabel(f"<b>{heading}</b>")
            h_lbl.setStyleSheet("font-size: 10.5pt; color: #0f172a;" if not dark else "font-size: 10.5pt; color: #f4f4f5;")
            c_lay.addWidget(h_lbl)

            for it in items:
                bullet = QLabel(f"• {it}")
                bullet.setWordWrap(True)
                bullet.setStyleSheet("font-size: 9pt; color: #475569;" if not dark else "font-size: 9pt; color: #a1a1aa;")
                c_lay.addWidget(bullet)
            c_lay.addStretch()
            return card

        card1 = make_pillar_card(
            "Mode 1 · Classic",
            "#0284c7",
            "Minitab Quality & Procedures",
            [
                "Familiar statistical dialogs with column selector list and [Select] button.",
                "SPC, Capability Sixpack, Gage R&R, ANOVA, and Design of Experiments (DOE).",
                "Formatted publication reports and Minitab Session command language (MTB >).",
            ],
        )

        card2 = make_pillar_card(
            "Mode 2 · Interactive",
            "#10b981",
            "JMP Visual Platforms",
            [
                "Interactive Prediction Profiler with draggable factor crosshairs and live response traces.",
                "Bivariate Fit Y by X platform with real-time linear, polynomial, and spline fits.",
                "Linked observation brushing: select points in scatter plots to highlight rows in the worksheet.",
            ],
        )

        card3 = make_pillar_card(
            "Mode 3 · Code-First",
            "#8b5cf6",
            "Positron-Style R Workbench",
            [
                "Zero-configuration Base R scripting; active worksheet automatically bound as 'df'.",
                "Non-parametric residual bootstrap uncertainty templates (2,000 replications).",
                "Sync R predictions, residuals, and diagnostics back to the sheet with stable row IDs.",
            ],
        )

        cards_layout.addWidget(card1, 1)
        cards_layout.addWidget(card2, 1)
        cards_layout.addWidget(card3, 1)
        layout.addLayout(cards_layout)

        # Core Guarantees Box
        guarantee_box = QFrame()
        if dark:
            guarantee_box.setStyleSheet("background-color: #1f1f23; border: 1px solid #27272a; border-radius: 6px; padding: 10px;")
        else:
            guarantee_box.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px;")
        g_lay = QVBoxLayout(guarantee_box)
        g_lay.setSpacing(4)
        g_title = QLabel("<b>The Connect Guarantee</b>")
        g_title.setStyleSheet("font-size: 9.5pt; color: #0f172a;" if not dark else "font-size: 9.5pt; color: #f4f4f5;")
        g_lay.addWidget(g_title)
        g_text = QLabel(
            "1. <b>Cryptographic Observation Identities</b>: Sorting, filtering, or moving rows never scrambles prediction bindings.<br>"
            "2. <b>Execution Verification</b>: The <i>Compare Implementations</i> tool checks coefficients against R <code>base::lm</code> to 10⁻⁴ tolerance.<br>"
            "3. <b>Zero Re-Entry</b>: Variable roles (Response, Predictors, Factors) flow automatically between dialogs, profilers, and R scripts."
        )
        g_text.setWordWrap(True)
        g_text.setStyleSheet("font-size: 8.5pt; color: #475569;" if not dark else "font-size: 8.5pt; color: #a1a1aa;")
        g_lay.addWidget(g_text)
        layout.addWidget(guarantee_box)

        # Actions & Sample Launcher
        btn_row = QHBoxLayout()
        load_sample_btn = QPushButton("🚀 Load Sample Project & Experience Connect (Chemical Yield)")
        load_sample_btn.setStyleSheet(
            "background-color: #0284c7; color: #ffffff; font-weight: 600; padding: 7px 16px; border-radius: 5px;"
        )
        load_sample_btn.clicked.connect(self._load_sample_and_close)
        btn_row.addWidget(load_sample_btn)
        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_sample_and_close(self):
        self.accept()
        self.window.load_connect_sample()


class ConnectBridgeWidget(QFrame):
    """Visual bridge ribbon displayed on connected results cards."""

    def __init__(self, window: "ModernWindow", entry: Dict[str, Any], conn_dict: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.window = window
        self.entry = entry
        self.conn_dict = conn_dict
        self._init_ui()

    def _init_ui(self):
        from .connect import ConnectedAnalysis, check_analysis_freshness

        conn_obj = ConnectedAnalysis.from_dict(self.conn_dict)
        status, status_msg = check_analysis_freshness(conn_obj, self.window.presenter.worksheet)
        dark = _is_dark_active(self)

        self.setObjectName("connectBridgeCard")
        if dark:
            self.setStyleSheet(
                "QFrame#connectBridgeCard { background-color: #18181b; border: 1px solid #0284c7; border-radius: 6px; padding: 8px 12px; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#connectBridgeCard { background-color: #f0f9ff; border: 1px solid #7dd3fc; border-radius: 6px; padding: 8px 12px; }"
            )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # Top Bar: Identity & Summary
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        badge = QLabel("<b>🔗 STATCRAFT CONNECT</b>")
        badge.setStyleSheet("color: #0284c7; font-size: 9pt;" if not dark else "color: #38bdf8; font-size: 9pt;")
        top_bar.addWidget(badge)

        r2_val = self.entry.get("result", {}).get("r_squared")
        r2_str = f"R² = {r2_val:.4f}" if r2_val is not None else "Fitted Model"
        model_info = QLabel(f"<b>Model:</b> {conn_obj.title}  |  {r2_str}  |  N = {len(conn_obj.fitted_row_ids)}")
        model_info.setStyleSheet("font-size: 8.5pt; color: #334155;" if not dark else "font-size: 8.5pt; color: #cbd5e1;")
        top_bar.addWidget(model_info, 1)

        if status != "current":
            warn_badge = QLabel("⚠ " + ("Data Modified Since Fit" if status == "stale" else "Source Column Missing"))
            warn_color = "#f59e0b" if status == "stale" else "#ef4444"
            warn_badge.setStyleSheet(
                f"color: {warn_color}; font-size: 8pt; font-weight: 600; padding: 2px 6px; border: 1px solid {warn_color}; border-radius: 3px;"
            )
            warn_badge.setToolTip(status_msg)
            top_bar.addWidget(warn_badge)
        else:
            sync_badge = QLabel("✓ In Sync")
            sync_badge.setStyleSheet(
                "color: #10b981; font-size: 8pt; font-weight: 600; padding: 2px 6px; border: 1px solid #10b981; border-radius: 3px;"
            )
            sync_badge.setToolTip("Active worksheet data matches model training state.")
            top_bar.addWidget(sync_badge)

        root.addLayout(top_bar)

        # Mode Action Buttons Ribbon
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)

        lbl_lead = QLabel("Bridge to:")
        lbl_lead.setStyleSheet("font-size: 8.5pt; font-weight: 600; color: #475569;" if not dark else "font-size: 8.5pt; font-weight: 600; color: #94a3b8;")
        btn_bar.addWidget(lbl_lead)

        btn_qss = (
            "QPushButton { background: #27272a; color: #f4f4f5; border: 1px solid #3f3f46; border-radius: 4px; padding: 4px 10px; font-size: 8.5pt; font-weight: 500; }"
            "QPushButton:hover { background: #3f3f46; border-color: #0284c7; color: #38bdf8; }"
            if dark else
            "QPushButton { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; font-size: 8.5pt; font-weight: 500; }"
            "QPushButton:hover { background: #e0f2fe; border-color: #0284c7; color: #005a9e; }"
        )

        b_dialog = QPushButton("📊 Minitab Dialog")
        b_dialog.setStyleSheet(btn_qss)
        b_dialog.setToolTip("Edit variables, model terms, and confidence level in the classic procedure dialog")
        b_dialog.clicked.connect(lambda: self.window.connect_open_dialog(self.entry))
        btn_bar.addWidget(b_dialog)

        arrow1 = QLabel("➔")
        arrow1.setStyleSheet("color: #94a3b8; font-weight: bold;")
        btn_bar.addWidget(arrow1)

        # Contextual label for JMP button based on model type
        if conn_obj.analysis_type in ("oneway_anova", "one_way_anova"):
            jmp_label = "📈 JMP Oneway"
        elif conn_obj.analysis_type == "two_sample_t":
            jmp_label = "📈 JMP Oneway"
        elif conn_obj.analysis_type in ("twoway_anova", "two_way_anova"):
            jmp_label = "📈 JMP Fit Model"
        elif conn_obj.analysis_type in ("binary_logistic", "fit_binary_logistic"):
            jmp_label = "📈 JMP Logistic"
        elif conn_obj.analysis_type in ("normal_capability", "process_capability", "capability"):
            jmp_label = "📈 JMP Capability"
        elif conn_obj.analysis_type in ("individuals_moving_range", "imr_chart", "imr", "xbar_r", "xbar_s", "subgroup_control_chart"):
            jmp_label = "📈 JMP Control Chart Builder"
        elif conn_obj.analysis_type in ("gage_rr", "gage_rr_crossed", "crossed_gage_rr"):
            jmp_label = "📈 JMP Variability Gauge"
        elif conn_obj.analysis_type == "correlation":
            jmp_label = "📈 JMP Multivariate" if len(conn_obj.predictor_names) > 1 else "📈 JMP Bivariate"
        elif conn_obj.analysis_type in ("descriptive_statistics", "describe_columns"):
            jmp_label = "📈 JMP Distribution"
        elif len(conn_obj.predictor_names) == 1 and conn_obj.analysis_type == "multiple_regression":
            jmp_label = "📈 JMP Bivariate"
        else:
            jmp_label = "📈 JMP Profiler"

        b_jmp = QPushButton(jmp_label)
        b_jmp.setStyleSheet(btn_qss)
        b_jmp.setToolTip("Open in JMP interactive visual analysis platform (draggable crosshairs / Oneway / Bivariate)")
        b_jmp.clicked.connect(lambda: self.window.connect_open_explorer(self.entry))
        btn_bar.addWidget(b_jmp)

        arrow2 = QLabel("➔")
        arrow2.setStyleSheet("color: #94a3b8; font-weight: bold;")
        btn_bar.addWidget(arrow2)

        b_r = QPushButton("💻 R Workbench")
        b_r.setStyleSheet(btn_qss)
        b_r.setToolTip("Open generated Base R code in R Workbench with active worksheet automatically bound as 'df'")
        b_r.clicked.connect(lambda: self.window.connect_open_in_r(self.entry))
        btn_bar.addWidget(b_r)

        sep = QLabel("|")
        sep.setStyleSheet("color: #cbd5e1;" if not dark else "color: #3f3f46;")
        btn_bar.addWidget(sep)

        b_compare = QPushButton("⚖️ Compare vs R")
        b_compare.setStyleSheet(btn_qss)
        b_compare.setToolTip("Audit parameter estimates and diagnostics against R base::lm (1e-4 tolerance)")
        b_compare.clicked.connect(lambda: self.window.connect_compare_implementations(self.entry))
        btn_bar.addWidget(b_compare)

        b_sync = QPushButton("📥 Sync to Sheet")
        b_sync.setStyleSheet(btn_qss)
        b_sync.setToolTip("Append model predictions & residuals back into the active worksheet matched by row IDs")
        b_sync.clicked.connect(lambda: self.window.connect_apply_predictions(self.entry))
        btn_bar.addWidget(b_sync)

        act = self.entry.get("recipe", {}).get("action") or conn_obj.analysis_type
        if act in ("analyze_response_surface", "response_surface", "analyze_factorial", "analyze_factorial_terms", "factorial_regression"):
            b_boot = QPushButton("🔬 R Bootstrap")
            b_boot.setStyleSheet(btn_qss)
            b_boot.setToolTip("Generate and execute 2,000-replication non-parametric residual bootstrap uncertainty script in R")
            b_boot.clicked.connect(lambda: self.window.connect_open_r_bootstrap(self.entry))
            btn_bar.addWidget(b_boot)

        b_report = QPushButton("📑 Append to ReportPad")
        b_report.setStyleSheet(btn_qss)
        b_report.setToolTip("Generate comprehensive Connected Model report and append to ReportPad")
        b_report.clicked.connect(lambda: self.window.append_connected_report_to_report_pad(self.entry))
        btn_bar.addWidget(b_report)

        btn_bar.addStretch()
        root.addLayout(btn_bar)
