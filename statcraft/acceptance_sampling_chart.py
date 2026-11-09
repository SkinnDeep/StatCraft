"""High-fidelity Qt Interactive Chart Widget for Acceptance Sampling by Attributes.

Renders Minitab-standard Acceptance Sampling curves:
- Operating Characteristic (OC) Curve with AQL and RQL markers
- Average Outgoing Quality (AOQ) Curve with AOQL reference line
- Average Total Inspection (ATI) Curve
- Interactive hover tooltips showing curve coordinates
- KPI cards: Sample Size n, Acceptance Number c, AQL, RQL, AOQL
- One-click "Copy Chart" and "Save PNG" buttons
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AcceptanceSamplingCanvas(QWidget):
    """Drawing canvas for Acceptance Sampling curves (OC, AOQ, ATI)."""

    def __init__(self, curves_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.curves = curves_data
        self.mode = "oc"  # 'oc', 'aoq', or 'ati'
        self.setMouseTracking(True)
        self.hover_pos: Optional[QPointF] = None
        self.hover_info: Optional[Tuple[float, float]] = None

    def set_mode(self, mode: str):
        self.mode = mode
        self.hover_info = None
        self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        self.hover_pos = pos
        self.update()

    def leaveEvent(self, event):
        self.hover_pos = None
        self.hover_info = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        painter.fillRect(self.rect(), QColor("#ffffff"))

        lm = 75.0
        rm = 40.0
        tm = 30.0
        bm = 60.0

        pw = w - lm - rm
        ph = h - tm - bm
        if pw <= 20 or ph <= 20:
            painter.end()
            return

        p_vals = self.curves.get("p_values", [])
        if not p_vals:
            painter.end()
            return

        p_max = float(self.curves.get("p_max", 0.10))

        # Determine Y limits and active curve
        if self.mode == "aoq":
            y_vals = self.curves.get("aoq_values", [])
            max_y = max(y_vals) * 1.25 if y_vals and max(y_vals) > 0 else 0.05
            y_label = "Average Outgoing Quality (AOQ)"
            line_color = QColor("#0284c7")
        elif self.mode == "ati" and self.curves.get("ati_values"):
            y_vals = self.curves.get("ati_values", [])
            max_y = max(y_vals) * 1.10 if y_vals and max(y_vals) > 0 else 1000.0
            y_label = "Average Total Inspection (ATI)"
            line_color = QColor("#16a34a")
        else:  # 'oc'
            y_vals = self.curves.get("oc_values", [])
            max_y = 1.05
            y_label = "Probability of Acceptance P(Accept)"
            line_color = QColor("#2563eb")

        def to_screen(pv: float, yv: float) -> QPointF:
            sx = lm + (pv / p_max) * pw
            sy = tm + (1.0 - (yv / max_y)) * ph
            return QPointF(sx, sy)

        # Plot backdrop
        plot_rect = QRectF(lm, tm, pw, ph)
        painter.setPen(QPen(QColor("#cbd5e1"), 1.0))
        painter.setBrush(QColor("#fafbfc"))
        painter.drawRect(plot_rect)

        # Subtle grid lines
        painter.setPen(QPen(QColor("#f1f5f9"), 1.0, Qt.PenStyle.DashLine))
        n_ticks = 5
        for step in range(1, n_ticks + 1):
            gx = lm + (step / n_ticks) * pw
            painter.drawLine(QPointF(gx, tm), QPointF(gx, tm + ph))
            gy = tm + (step / n_ticks) * ph
            painter.drawLine(QPointF(lm, gy), QPointF(lm + pw, gy))

        # Draw main curve
        if len(p_vals) == len(y_vals) and len(p_vals) > 1:
            curve_path = QPainterPath()
            start_pt = to_screen(p_vals[0], y_vals[0])
            curve_path.moveTo(start_pt)
            for pv, yv in zip(p_vals[1:], y_vals[1:]):
                curve_path.lineTo(to_screen(pv, yv))

            painter.setPen(QPen(line_color, 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(curve_path)

        # Special reference lines
        if self.mode == "oc":
            # AQL vertical line
            aql = self.curves.get("aql")
            if aql and aql <= p_max:
                pt_aql = to_screen(aql, 0.0)
                painter.setPen(QPen(QColor("#16a34a"), 1.2, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(pt_aql.x(), tm), QPointF(pt_aql.x(), tm + ph))
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#15803d"))
                painter.drawText(QRectF(pt_aql.x() + 4, tm + 8, 80, 16),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"AQL: {aql*100:.1f}%")

            # RQL vertical line
            rql = self.curves.get("rql")
            if rql and rql <= p_max:
                pt_rql = to_screen(rql, 0.0)
                painter.setPen(QPen(QColor("#dc2626"), 1.2, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(pt_rql.x(), tm), QPointF(pt_rql.x(), tm + ph))
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#b91c1c"))
                painter.drawText(QRectF(pt_rql.x() + 4, tm + 26, 80, 16),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"RQL: {rql*100:.1f}%")

        elif self.mode == "aoq":
            # AOQL horizontal reference line
            aoql = self.curves.get("aoql", 0.0)
            if aoql > 0:
                pt_aoql = to_screen(0.0, aoql)
                painter.setPen(QPen(QColor("#d97706"), 1.2, Qt.PenStyle.DashLine))
                painter.drawLine(QPointF(lm, pt_aoql.y()), QPointF(lm + pw, pt_aoql.y()))
                painter.setFont(QFont("Segoe UI", 8))
                painter.setPen(QColor("#b45309"))
                painter.drawText(QRectF(lm + pw - 120, pt_aoql.y() - 18, 115, 16),
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"AOQL: {aoql*100:.2f}%")

        # Axis ticks and numbers
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#475569"))

        # X-axis ticks (Percent Defective p)
        for step in range(n_ticks + 1):
            val_p = (step / n_ticks) * p_max
            fmt_p = f"{val_p * 100.0:.1f}%"
            px = lm + (step / n_ticks) * pw
            painter.drawLine(QPointF(px, tm + ph), QPointF(px, tm + ph + 4))
            painter.drawText(QRectF(px - 25, tm + ph + 6, 50, 16),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, fmt_p)

        # Y-axis ticks
        for step in range(n_ticks + 1):
            val_y = (step / n_ticks) * max_y
            if self.mode == "ati":
                fmt_y = f"{int(round(val_y)):,}"
            elif self.mode == "aoq":
                fmt_y = f"{val_y * 100.0:.2f}%"
            else:
                fmt_y = f"{val_y:.2f}"

            py = tm + (1.0 - (step / n_ticks)) * ph
            painter.drawLine(QPointF(lm - 4, py), QPointF(lm, py))
            painter.drawText(QRectF(10, py - 8, lm - 16, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, fmt_y)

        # Axis Labels
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor("#0f172a"))

        # X-Axis label
        painter.drawText(QRectF(lm, h - 28, pw, 22),
                         Qt.AlignmentFlag.AlignCenter, "Percent Defective (Incoming Lot Quality p)")

        # Y-Axis label (rotated)
        painter.save()
        painter.translate(18, tm + ph / 2.0)
        painter.rotate(-90)
        painter.drawText(QRectF(-ph / 2.0, -12, ph, 24),
                         Qt.AlignmentFlag.AlignCenter, y_label)
        painter.restore()

        # Hover crosshair and tooltip
        if self.hover_pos and plot_rect.contains(self.hover_pos):
            hx = self.hover_pos.x()
            # Calculate corresponding p
            hp = ((hx - lm) / pw) * p_max
            hp = max(0.0, min(p_max, hp))

            # Interpolate y
            idx = int(round((hp / p_max) * (len(p_vals) - 1)))
            idx = max(0, min(len(y_vals) - 1, idx))
            hy = y_vals[idx]
            h_pt = to_screen(p_vals[idx], hy)

            # Dot at curve
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.setBrush(line_color)
            painter.drawEllipse(h_pt, 5.0, 5.0)

            # Tooltip
            if self.mode == "ati":
                tip_text = f"Defect: {p_vals[idx]*100:.2f}%\nATI: {int(round(hy)):,}"
            elif self.mode == "aoq":
                tip_text = f"Defect: {p_vals[idx]*100:.2f}%\nAOQ: {hy*100:.3f}%"
            else:
                tip_text = f"Defect: {p_vals[idx]*100:.2f}%\nP(Accept): {hy:.4f}"

            painter.setFont(QFont("Segoe UI", 8.5))
            fm = painter.fontMetrics()
            tip_w = max(fm.horizontalAdvance(line) for line in tip_text.splitlines()) + 16.0
            tip_h = len(tip_text.splitlines()) * 16.0 + 10.0

            tx = h_pt.x() + 10
            if tx + tip_w > w - 10:
                tx = h_pt.x() - tip_w - 10
            ty = h_pt.y() - tip_h - 10
            if ty < 10:
                ty = h_pt.y() + 14

            tip_rect = QRectF(tx, ty, tip_w, tip_h)
            painter.setPen(QPen(line_color, 1.0))
            painter.setBrush(QColor(15, 23, 42, 230))
            painter.drawRoundedRect(tip_rect, 4.0, 4.0)

            painter.setPen(QColor("#ffffff"))
            text_rect = QRectF(tx + 8, ty + 5, tip_w - 16, tip_h - 10)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, tip_text)

        painter.end()


class AcceptanceSamplingChartWidget(QWidget):
    """Full-featured interactive widget with OC/AOQ/ATI tabs, KPI cards, and export."""

    def __init__(self, result: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.result = result
        self.curves = result.get("curves", {})
        self.curves["aql"] = result.get("aql")
        self.curves["rql"] = result.get("rql")
        self.curves["aoql"] = result.get("aoql")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(10)

        # Header Bar: Title + Curve Selectors + Export Buttons
        top_bar = QHBoxLayout()
        title_text = self.result.get("settings", {}).get("title") or "Acceptance Sampling by Attributes"
        lbl_title = QLabel(title_text)
        lbl_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: #0f172a;")
        top_bar.addWidget(lbl_title)
        top_bar.addSpacing(15)

        # Curve Selector Buttons
        self.btn_oc = QPushButton("📈 OC Curve")
        self.btn_oc.setCheckable(True)
        self.btn_oc.setChecked(True)
        self.btn_oc.clicked.connect(lambda: self._select_mode("oc"))
        top_bar.addWidget(self.btn_oc)

        self.btn_aoq = QPushButton("📊 AOQ Curve")
        self.btn_aoq.setCheckable(True)
        self.btn_aoq.clicked.connect(lambda: self._select_mode("aoq"))
        top_bar.addWidget(self.btn_aoq)

        has_ati = bool(self.curves.get("ati_values"))
        if has_ati:
            self.btn_ati = QPushButton("📉 ATI Curve")
            self.btn_ati.setCheckable(True)
            self.btn_ati.clicked.connect(lambda: self._select_mode("ati"))
            top_bar.addWidget(self.btn_ati)
        else:
            self.btn_ati = None

        top_bar.addStretch()

        btn_copy = QPushButton("📋 Copy Chart")
        btn_copy.setStyleSheet("padding: 4px 10px; font-size: 8.5pt;")
        btn_copy.clicked.connect(self._copy_to_clipboard)
        top_bar.addWidget(btn_copy)

        btn_save = QPushButton("💾 Save PNG")
        btn_save.setStyleSheet("padding: 4px 10px; font-size: 8.5pt;")
        btn_save.clicked.connect(self._save_png)
        top_bar.addWidget(btn_save)
        layout.addLayout(top_bar)

        # KPI Summary Cards Bar
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)

        def make_kpi(lbl: str, val: str, sub: str = "", highlight: bool = False):
            frame = QFrame()
            bg_col = "#f1f5f9" if not highlight else "#eff6ff"
            border_col = "#cbd5e1" if not highlight else "#93c5fd"
            frame.setStyleSheet(f"background-color: {bg_col}; border: 1px solid {border_col}; border-radius: 6px;")
            flay = QVBoxLayout(frame)
            flay.setContentsMargins(10, 6, 10, 6)
            flay.setSpacing(2)

            l = QLabel(lbl)
            l.setFont(QFont("Segoe UI", 8))
            l.setStyleSheet("color: #64748b; font-weight: 600;")
            flay.addWidget(l)

            v = QLabel(val)
            v.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            v.setStyleSheet("color: #0f172a;" if not highlight else "color: #0284c7;")
            flay.addWidget(v)

            if sub:
                s = QLabel(sub)
                s.setFont(QFont("Segoe UI", 7.5))
                s.setStyleSheet("color: #64748b;")
                flay.addWidget(s)
            return frame

        n_val = self.result.get("sample_size", 0)
        c_val = self.result.get("acceptance_number", 0)
        cards_layout.addWidget(make_kpi("Sampling Plan", f"n = {n_val},  c = {c_val}", f"Accept if ≤ {c_val} defectives", highlight=True))

        aql_pct = self.result.get("aql", 0.01) * 100.0
        p_acc_aql = self.result.get("actual_p_accept_aql", 0.95)
        cards_layout.addWidget(make_kpi("AQL", f"{aql_pct:.2f}%", f"P(Accept): {p_acc_aql:.4f}"))

        rql_pct = self.result.get("rql", 0.05) * 100.0
        p_acc_rql = self.result.get("actual_p_accept_rql", 0.10)
        cards_layout.addWidget(make_kpi("RQL / LTPD", f"{rql_pct:.2f}%", f"Consumer Risk: {p_acc_rql:.4f}"))

        aoql_pct = self.result.get("aoql", 0.0) * 100.0
        cards_layout.addWidget(make_kpi("AOQL", f"{aoql_pct:.3f}%", f"At Incoming: {self.result.get('p_at_aoql', 0.0)*100.0:.2f}%"))

        layout.addLayout(cards_layout)

        # Canvas
        self.canvas = AcceptanceSamplingCanvas(self.curves, self)
        layout.addWidget(self.canvas, 1)

        self._style_selector_buttons("oc")

    def _select_mode(self, mode: str):
        self.canvas.set_mode(mode)
        self._style_selector_buttons(mode)

    def _style_selector_buttons(self, mode: str):
        active_qss = "QPushButton { background: #0284c7; color: #ffffff; border: 1px solid #0369a1; border-radius: 4px; padding: 4px 10px; font-weight: 600; font-size: 8.5pt; }"
        inactive_qss = "QPushButton { background: #ffffff; color: #334155; border: 1px solid #cbd5e1; border-radius: 4px; padding: 4px 10px; font-size: 8.5pt; } QPushButton:hover { background: #f1f5f9; }"

        self.btn_oc.setChecked(mode == "oc")
        self.btn_oc.setStyleSheet(active_qss if mode == "oc" else inactive_qss)

        self.btn_aoq.setChecked(mode == "aoq")
        self.btn_aoq.setStyleSheet(active_qss if mode == "aoq" else inactive_qss)

        if self.btn_ati:
            self.btn_ati.setChecked(mode == "ati")
            self.btn_ati.setStyleSheet(active_qss if mode == "ati" else inactive_qss)

    def render_chart_pixmap(self, width: int = 800, height: int = 600) -> QPixmap:
        pm = QPixmap(width, height)
        pm.fill(QColor("#ffffff"))
        self.render(pm)
        return pm

    def _copy_to_clipboard(self):
        pixmap = self.canvas.grab()
        QApplication.clipboard().setPixmap(pixmap)

    def _save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Acceptance Sampling Chart", "Acceptance_Sampling_Chart.png", "PNG Images (*.png)")
        if path:
            pixmap = self.canvas.grab()
            pixmap.save(path, "PNG")
