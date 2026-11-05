"""Interactive Qt Dashboard Widget for JMP Process Screening Platform.

Displays multi-process capability, stability screening, and alarm diagnostics:
- KPI summary badges (% Stable, % Capable, Alarms)
- Interactive search and filter pills (All, Unstable, Incapable, Alarms)
- Color-coded health badges and stability indicators
- 1-click drilldown to Control Chart Builder
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .graph_interaction import GraphInteractionMixin


class ProcessScreeningWidget(GraphInteractionMixin, QWidget):
    """Interactive multi-process screening platform widget."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.processes = self.result.get("processes", [])
        self.active_filter = "all"
        self.search_text = ""

        self.setMinimumSize(920, 620)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #f8fafc; font-family: 'Segoe UI', sans-serif;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Header & Title Bar
        header_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title_lbl = QLabel(f"<b>Process Screening Platform</b>")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #0f172a;")
        sub_lbl = QLabel(f"Evaluating {self.result.get('total_screened', len(self.processes))} process variables across stability and capability")
        sub_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_bar.addLayout(title_box)

        header_bar.addStretch()

        btn_copy = QPushButton("Copy TSV")
        btn_copy.setToolTip("Copy entire screening table to clipboard")
        btn_copy.setStyleSheet(
            "QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 5px 12px; font-weight: 600; color: #334155; } "
            "QPushButton:hover { background: #f1f5f9; border-color: #94a3b8; }"
        )
        btn_copy.clicked.connect(self._copy_tsv)
        header_bar.addWidget(btn_copy)

        main_layout.addLayout(header_bar)

        # 2. KPI Summary Cards Bar
        cards_bar = QHBoxLayout()
        cards_bar.setSpacing(12)

        tot = self.result.get("total_screened", len(self.processes))
        st_pct = self.result.get("stable_percent", 0.0)
        cap_pct = self.result.get("capable_percent", 0.0)
        alm_cnt = self.result.get("alarms_processes_count", 0)

        cards_bar.addWidget(self._make_kpi_card("Total Screened", str(tot), "#0284c7", "#e0f2fe"))
        cards_bar.addWidget(self._make_kpi_card("Stable Processes", f"{st_pct}%", "#16a34a", "#dcfce7"))
        cards_bar.addWidget(self._make_kpi_card("Capable (Ppk ≥ 1.33)", f"{cap_pct}%", "#0284c7", "#e0f2fe"))
        cards_bar.addWidget(self._make_kpi_card("Processes with Alarms", str(alm_cnt), "#dc2626" if alm_cnt > 0 else "#16a34a", "#fee2e2" if alm_cnt > 0 else "#dcfce7"))

        main_layout.addLayout(cards_bar)

        # 3. Interactive Filter & Search Controls
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by process name...")
        self.search_input.setStyleSheet(
            "QLineEdit { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 8px; font-size: 11px; max-width: 220px; } "
            "QLineEdit:focus { border: 1.5px solid #0284c7; }"
        )
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_bar.addWidget(self.search_input)

        self.btn_all = self._make_filter_btn("All Processes", "all", active=True)
        self.btn_unstable = self._make_filter_btn("Unstable Only", "unstable")
        self.btn_incapable = self._make_filter_btn("Incapable Only (Ppk < 1.33)", "incapable")
        self.btn_alarms = self._make_filter_btn("Alarms Only", "alarms")

        filter_bar.addWidget(self.btn_all)
        filter_bar.addWidget(self.btn_unstable)
        filter_bar.addWidget(self.btn_incapable)
        filter_bar.addWidget(self.btn_alarms)
        filter_bar.addStretch()

        main_layout.addLayout(filter_bar)

        # 4. Interactive Screening Table
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(
            "QTableWidget { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; gridline-color: #f1f5f9; font-size: 11px; } "
            "QTableWidget::item { padding: 6px 8px; } "
            "QTableWidget::item:selected { background: #e0f2fe; color: #0f172a; } "
            "QHeaderView::section { background: #f8fafc; color: #334155; font-weight: 700; border: none; border-bottom: 1px solid #cbd5e1; padding: 6px 8px; }"
        )

        headers = [
            "Status", "Process", "N", "Mean", "Overall SD", "Within SD",
            "Stability Index", "Alarms", "Cp", "Cpk", "Pp", "Ppk", "Defect PPM"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        main_layout.addWidget(self.table)

        self._populate_table()

    def _make_kpi_card(self, title: str, value: str, text_color: str, bg_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px;")
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 10, 12, 10)
        l.setSpacing(4)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
        l.addWidget(t_lbl)

        v_lbl = QLabel(value)
        v_lbl.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {text_color};")
        l.addWidget(v_lbl)
        return card

    def _make_filter_btn(self, text: str, key: str, active: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setProperty("filter_key", key)
        self._style_filter_btn(btn, active)
        btn.clicked.connect(lambda: self._set_filter(key))
        return btn

    def _style_filter_btn(self, btn: QPushButton, active: bool) -> None:
        if active:
            btn.setStyleSheet(
                "QPushButton { background: #0284c7; color: #ffffff; border: 1px solid #0284c7; border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 600; }"
            )
        else:
            btn.setStyleSheet(
                "QPushButton { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 12px; padding: 4px 12px; font-size: 11px; font-weight: 500; } "
                "QPushButton:hover { background: #e2e8f0; }"
            )

    def _set_filter(self, key: str) -> None:
        self.active_filter = key
        for b in (self.btn_all, self.btn_unstable, self.btn_incapable, self.btn_alarms):
            is_active = (b.property("filter_key") == key)
            b.setChecked(is_active)
            self._style_filter_btn(b, is_active)
        self._populate_table()

    def _on_search_changed(self, text: str) -> None:
        self.search_text = text.strip().lower()
        self._populate_table()

    def _populate_table(self) -> None:
        # Filter processes
        filtered = []
        for p in self.processes:
            if self.search_text and self.search_text not in p["process"].lower():
                continue
            if self.active_filter == "unstable" and p["stability_index"] < 1.25:
                continue
            if self.active_filter == "incapable" and (p["ppk"] is not None and p["ppk"] >= 1.33):
                continue
            if self.active_filter == "alarms" and p["alarms_count"] == 0:
                continue
            filtered.append(p)

        self.table.setRowCount(len(filtered))
        for row_idx, p in enumerate(filtered):
            # Status Badge
            st_item = QTableWidgetItem(f" ● {p['status_label']}")
            st_item.setForeground(QColor(p["status_color"]))
            font = st_item.font()
            font.setBold(True)
            st_item.setFont(font)
            self.table.setItem(row_idx, 0, st_item)

            # Process Name
            p_item = QTableWidgetItem(p["process"])
            p_item.setData(Qt.ItemDataRole.UserRole, p)
            self.table.setItem(row_idx, 1, p_item)

            # Numbers
            self.table.setItem(row_idx, 2, self._align_num(str(p["n"])))
            self.table.setItem(row_idx, 3, self._align_num(f"{p['mean']:.4f}"))
            self.table.setItem(row_idx, 4, self._align_num(f"{p['stdev_overall']:.4f}"))
            self.table.setItem(row_idx, 5, self._align_num(f"{p['stdev_within']:.4f}"))

            # Stability Index
            si_item = self._align_num(f"{p['stability_index']:.3f}")
            si_item.setForeground(QColor(p["stability_color"]))
            font_si = si_item.font()
            font_si.setBold(True)
            si_item.setFont(font_si)
            self.table.setItem(row_idx, 6, si_item)

            # Alarms
            alm_item = self._align_num(str(p["alarms_count"]))
            if p["alarms_count"] > 0:
                alm_item.setForeground(QColor("#dc2626"))
                font_alm = alm_item.font()
                font_alm.setBold(True)
                alm_item.setFont(font_alm)
            self.table.setItem(row_idx, 7, alm_item)

            # Capability
            self.table.setItem(row_idx, 8, self._align_num(f"{p['cp']:.2f}" if p["cp"] is not None else "—"))
            self.table.setItem(row_idx, 9, self._align_num(f"{p['cpk']:.2f}" if p["cpk"] is not None else "—"))
            self.table.setItem(row_idx, 10, self._align_num(f"{p['pp']:.2f}" if p["pp"] is not None else "—"))

            # Ppk
            ppk_item = self._align_num(f"{p['ppk']:.2f}" if p["ppk"] is not None else "—")
            if p["ppk"] is not None:
                if p["ppk"] >= 1.33:
                    ppk_item.setForeground(QColor("#16a34a"))
                else:
                    ppk_item.setForeground(QColor("#dc2626"))
                font_ppk = ppk_item.font()
                font_ppk.setBold(True)
                ppk_item.setFont(font_ppk)
            self.table.setItem(row_idx, 11, ppk_item)

            # PPM
            self.table.setItem(row_idx, 12, self._align_num(f"{p['ppm_defect']:.1f}"))

    def _align_num(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _on_row_double_clicked(self, row: int, col: int) -> None:
        p_item = self.table.item(row, 1)
        if p_item is None:
            return
        p_data = p_item.data(Qt.ItemDataRole.UserRole)
        if not p_data:
            return
        col_idx = p_data.get("col_index")
        # Notify parent to launch Control Chart Builder for this column
        win = self.window()
        if hasattr(win, "presenter") and hasattr(win, "show_result"):
            try:
                entry = win.presenter.control_chart_builder(y_indices=[col_idx])
                win.show_result(entry)
            except Exception:
                pass

    def _copy_tsv(self) -> None:
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t")
        headers = [self.table.horizontalHeaderItem(c).text() for c in range(self.table.columnCount())]
        writer.writerow(headers)

        for r in range(self.table.rowCount()):
            row_vals = [self.table.item(r, c).text() if self.table.item(r, c) else "" for c in range(self.table.columnCount())]
            writer.writerow(row_vals)

        QGuiApplication.clipboard().setText(buf.getvalue())
