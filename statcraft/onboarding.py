"""Starter Sample Datasets & Interactive Guided Onboarding Tour for First-Time Users."""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .connect_hub import create_chemical_process_sample
from .model import Column, Worksheet


SAMPLE_DATASETS: List[Dict[str, str]] = [
    {
        "key": "chemical_process",
        "title": "Chemical Process Yield (DOE & Regression)",
        "category": "Regression / ANOVA",
        "rows_hint": "25 runs × 4 variables",
        "description": (
            "Reaction yield optimization dataset measuring Yield (%) across Reactor Temperature (°C), "
            "Pressure (psi), and Catalyst formulation (Alpha / Beta). Ideal for Multiple Regression, "
            "Fit Y by X, Residuals Diagnostics, and Response Prediction."
        ),
        "recommended": "Try: Stat > Regression > Regression… or Stat > Fit Y by X…",
    },
    {
        "key": "six_sigma_shafts",
        "title": "Precision Shaft Manufacturing (Capability & SPC)",
        "category": "Six Sigma / Quality",
        "rows_hint": "30 shafts × 4 variables",
        "description": (
            "CNC-machined steel shaft outer diameters (mm, nominal 10.00 ± 0.30 mm) across two lines "
            "(Line_A, Line_B) and two shifts (Day, Night). Includes subtle mean drift ideal for Normal "
            "Capability (LSL=9.70, USL=10.30) and Control Chart Builder."
        ),
        "recommended": "Try: Stat > Quality Tools > Capability Analysis > Normal… (LSL 9.70, USL 10.30)",
    },
    {
        "key": "wafer_defects",
        "title": "Semiconductor Wafer Defect Map (Spatial & Screening)",
        "category": "Semiconductor / Graph Studio",
        "rows_hint": "36 dies × 5 variables",
        "description": (
            "Die-level spatial inspection across a 6×6 wafer grid measuring Die_X, Die_Y, "
            "Defect_Density, Oxide_Thickness_nm, and radial Wafer_Zone. Built for interactive Wafer Plots "
            "and multi-metric Process Screening."
        ),
        "recommended": "Try: Graph > Graph Builder > Wafer Plot… or Stat > Quality Tools > Process Screening…",
    },
    {
        "key": "reliability_motors",
        "title": "Electric Motor Accelerated Life Test (Survival)",
        "category": "Reliability / Survival",
        "rows_hint": "24 units × 4 variables",
        "description": (
            "Elevated-temperature stress testing of brushless motor windings tracking Failure_Hours, "
            "Ambient_Temp_C (85 / 105 / 125 °C), Event_Observed (1 = failed, 0 = right-censored), "
            "and Vendor."
        ),
        "recommended": "Try: Stat > Reliability/Survival > Accelerated Life Testing… or Distribution Analysis…",
    },
]


def build_sample_worksheet(key: str) -> Worksheet:
    """Construct one of the built-in deterministic starter sample worksheets."""
    if key == "chemical_process":
        return create_chemical_process_sample()

    if key == "six_sigma_shafts":
        diameters = []
        lines = []
        shifts = []
        batches = []
        for i in range(30):
            line = "Line_A" if i < 15 else "Line_B"
            shift = "Day" if (i % 2 == 0) else "Night"
            drift = 0.04 if i >= 20 else 0.0
            noise = round(math.sin(i * 1.9) * 0.065 + math.cos(i * 0.7) * 0.025, 4)
            diameters.append(round(10.00 + drift + noise, 4))
            lines.append(line)
            shifts.append(shift)
            batches.append(f"B{(i // 5) + 1:02d}")
        ws = Worksheet("Precision_Shafts", [
            Column("Diameter_mm", "number", diameters, metadata={"lsl": 9.70, "target": 10.00, "usl": 10.30}),
            Column("Line", "text", lines),
            Column("Shift", "text", shifts),
            Column("Batch", "text", batches),
        ])
        ws.validate()
        return ws

    if key == "wafer_defects":
        die_x, die_y, defects, thickness, zones = [], [], [], [], []
        for r in range(-3, 3):
            for c in range(-3, 3):
                rad = math.hypot(r + 0.5, c + 0.5)
                die_x.append(float(c + 1))
                die_y.append(float(r + 1))
                base_def = 1.2 + 0.85 * (rad ** 1.4) + max(0.0, math.sin(r + c) * 0.9)
                defects.append(round(base_def, 2))
                thickness.append(round(120.0 - 1.8 * rad + math.cos(c * 0.8) * 1.1, 2))
                zones.append("Edge" if rad >= 2.8 else ("Mid" if rad >= 1.6 else "Center"))
        ws = Worksheet("Wafer_Inspection", [
            Column("Die_X", "number", die_x),
            Column("Die_Y", "number", die_y),
            Column("Defect_Density", "number", defects),
            Column("Oxide_Thickness_nm", "number", thickness),
            Column("Wafer_Zone", "text", zones),
        ])
        ws.validate()
        return ws

    if key == "reliability_motors":
        hours, temps, events, vendors = [], [], [], []
        specs = [(85.0, 2200.0), (105.0, 1150.0), (125.0, 540.0)]
        for idx in range(24):
            temp_c, char_life = specs[idx % 3]
            scale_factor = 0.65 + (idx // 3) * 0.11 + math.sin(idx) * 0.05
            hrs = round(char_life * scale_factor, 1)
            cens = 0.0 if (temp_c == 85.0 and idx >= 18) else 1.0
            hours.append(hrs)
            temps.append(temp_c)
            events.append(cens)
            vendors.append("Vendor_X" if idx % 2 == 0 else "Vendor_Y")
        ws = Worksheet("Motor_ALT_Reliability", [
            Column("Failure_Hours", "number", hours),
            Column("Temp_C", "number", temps),
            Column("Event_Observed", "number", events),
            Column("Vendor", "text", vendors),
        ])
        ws.validate()
        return ws

    raise ValueError(f"Unknown sample dataset: {key}")


class SampleLibraryDialog(QDialog):
    """Browse and load curated sample datasets tailored for first-time exploration."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("StatCraft Sample Dataset Library")
        self.resize(700, 440)
        self.selected_key: Optional[str] = None

        root = QVBoxLayout(self)
        root.setSpacing(10)

        intro = QLabel("Pick a realistic starter dataset to explore StatCraft graphs, regressions, capability studies, and R code translation:")
        intro.setWordWrap(True)
        root.addWidget(intro)

        body = QHBoxLayout()
        self.dataset_list = QListWidget()
        self.dataset_list.setMinimumWidth(260)
        for spec in SAMPLE_DATASETS:
            item = QListWidgetItem(f"{spec['title']}\n({spec['category']} · {spec['rows_hint']})")
            item.setData(Qt.ItemDataRole.UserRole, spec["key"])
            self.dataset_list.addItem(item)
        body.addWidget(self.dataset_list, 1)

        self.details_browser = QTextBrowser()
        body.addWidget(self.details_browser, 1)
        root.addLayout(body, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.load_btn = QPushButton("Load Sample Dataset")
        self.load_btn.setDefault(True)
        self.load_btn.clicked.connect(self._accept_selected)
        footer.addWidget(cancel_btn)
        footer.addWidget(self.load_btn)
        root.addLayout(footer)

        self.dataset_list.currentRowChanged.connect(self._update_details)
        self.dataset_list.itemDoubleClicked.connect(lambda _item: self._accept_selected())
        if self.dataset_list.count() > 0:
            self.dataset_list.setCurrentRow(0)

    def _update_details(self, row: int):
        if 0 <= row < len(SAMPLE_DATASETS):
            s = SAMPLE_DATASETS[row]
            self.details_browser.setHtml(
                f"<h3>{s['title']}</h3>"
                f"<p><b>Category:</b> {s['category']}<br><b>Size:</b> {s['rows_hint']}</p>"
                f"<p>{s['description']}</p>"
                f"<p><b>Recommended workflow:</b><br><code>{s['recommended']}</code></p>"
            )

    def _accept_selected(self):
        row = self.dataset_list.currentRow()
        if 0 <= row < len(SAMPLE_DATASETS):
            self.selected_key = SAMPLE_DATASETS[row]["key"]
            self.accept()


class GuidedTourDialog(QDialog):
    """Interactive 5-step first-timer tour connecting data, visuals, analysis, and exports."""

    def __init__(self, parent: Optional[QWidget] = None, actions: Optional[Dict[str, Callable[[], Any]]] = None):
        super().__init__(parent)
        self.setWindowTitle("StatCraft Interactive Quick Tour")
        self.resize(620, 380)
        self._actions = actions or {}
        self.current_step = 0
        self.steps = [
            {
                "title": "Step 1 of 5 — Start with Real Process Data",
                "body": (
                    "Load the 25-run <b>Chemical Process Yield</b> dataset (or open your own "
                    "<b>.xlsx</b>, <b>.csv</b>, <b>.mpx</b>, or <b>.jmp</b> file from File &gt; Open)."
                ),
                "action_label": "Load Chemical Process Sample",
                "action_key": "load_sample",
            },
            {
                "title": "Step 2 of 5 — Catch Bad Data Before Modeling",
                "body": (
                    "Run <b>Pre-Flight Data Doctor</b> (Data &gt; Pre-Flight Data Doctor) to detect "
                    "hidden whitespace in factor names, zero-variance columns, missing-value codes (-999/NA), "
                    "and severe collinearity in milliseconds."
                ),
                "action_label": "Run Data Health Doctor",
                "action_key": "data_doctor",
            },
            {
                "title": "Step 3 of 5 — Visualize & Brush Outliers",
                "body": (
                    "Open <b>Graph Builder</b> or <b>Fit Y by X</b> to explore scatterplots, histograms, "
                    "boxplots, or 3D response surfaces. Drag across points to highlight rows live in your worksheet."
                ),
                "action_label": "Open Graph Builder",
                "action_key": "graph_builder",
            },
            {
                "title": "Step 4 of 5 — Fit Models & Read Plain-English Briefs",
                "body": (
                    "Launch any procedure from <b>Stat</b>, press <b>Ctrl+K</b> for the Command Palette, "
                    "or use <b>Assistant &gt; Guided Analysis Wizard</b>. Every result includes summary tables, "
                    "4-in-1 diagnostics, and a plain-English Executive Brief."
                ),
                "action_label": "Open Command Palette (Ctrl+K)",
                "action_key": "command_palette",
            },
            {
                "title": "Step 5 of 5 — Share Reports & Reproducible R Code",
                "body": (
                    "Export vector <b>SVG</b>, standalone <b>HTML / Markdown</b>, <b>Excel (.xlsx)</b>, "
                    "or translate any analysis to runnable <b>Tidyverse / Base R</b> with one click."
                ),
                "action_label": "Finish Tour",
                "action_key": "close",
            },
        ]

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.step_title = QLabel()
        self.step_title.setStyleSheet("font-size: 13pt; font-weight: 700;")
        layout.addWidget(self.step_title)

        self.step_body = QTextBrowser()
        layout.addWidget(self.step_body, 1)

        row = QHBoxLayout()
        self.try_btn = QPushButton()
        self.try_btn.clicked.connect(self._run_step_action)
        row.addWidget(self.try_btn)
        row.addStretch()

        self.prev_btn = QPushButton("Back")
        self.prev_btn.clicked.connect(self.prev_step)
        self.next_btn = QPushButton("Next Step")
        self.next_btn.clicked.connect(self.next_step)
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)
        layout.addLayout(row)

        self._render_step()

    def _render_step(self):
        step = self.steps[self.current_step]
        self.step_title.setText(step["title"])
        self.step_body.setHtml(f"<div style='font-size:10.5pt; line-height:1.5;'>{step['body']}</div>")
        self.try_btn.setText(step["action_label"])
        self.prev_btn.setEnabled(self.current_step > 0)
        self.next_btn.setText("Done" if self.current_step == len(self.steps) - 1 else "Next Step")

    def prev_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._render_step()

    def next_step(self):
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self._render_step()
        else:
            self.accept()

    def _run_step_action(self):
        key = self.steps[self.current_step]["action_key"]
        if key == "close":
            self.accept()
            return
        fn = self._actions.get(key)
        if callable(fn):
            fn()
