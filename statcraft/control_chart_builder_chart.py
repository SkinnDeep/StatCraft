"""Interactive Qt Chart Widget for JMP Control Chart Builder Platform.

Renders dual stacked vector canvas:
- Primary Chart (Individual Values / Sample Means) with phase separation and step limits
- Dispersion Chart (Moving Range / Sample Range / Sample StDev)
- Highlighting of Nelson / Western Electric out-of-control alarm points
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .graph_interaction import GraphInteractionMixin
from .chart_theme import chart_painter

INK = "#1e293b"
MUTED = "#64748b"
BORDER = "#cbd5e1"
GRID = "#f1f5f9"
LINE_COLOR = "#0284c7"
POINT_COLOR = "#0369a1"
ALARM_COLOR = "#dc2626"
UCL_COLOR = "#ef4444"
LCL_COLOR = "#ef4444"
CL_COLOR = "#10b981"
PHASE_LINE = "#94a3b8"
CARD_BG = "#ffffff"


class ControlChartBuilderWidget(GraphInteractionMixin, QWidget):
    """Interactive dual-panel chart for Control Chart Builder."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(object)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry)
        self.setMouseTracking(True)
        self.setMinimumSize(850, 600)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.show_phase_lines = True
        self.show_limit_labels = True
        self.show_alarms = True

        self.panels: List[Dict[str, Any]] = []
        self._hover_info: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Header bar with interactive controls
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(16)

        title_lbl = QLabel(f"<b>Control Chart Builder</b> — {self.result.get('y_name', 'Y')}")
        title_lbl.setStyleSheet("font-size: 14px; color: #0f172a;")
        hdr_layout.addWidget(title_lbl)

        hdr_layout.addStretch()

        type_badge = QLabel(f"<b>{self.result.get('chart_type', 'XBAR-R').upper()}</b>")
        type_badge.setStyleSheet(
            "background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;"
        )
        hdr_layout.addWidget(type_badge)

        self.chk_phases = QCheckBox("Phase Lines")
        self.chk_phases.setChecked(True)
        self.chk_phases.toggled.connect(self._toggle_phases)
        hdr_layout.addWidget(self.chk_phases)

        self.chk_labels = QCheckBox("Limit Labels")
        self.chk_labels.setChecked(True)
        self.chk_labels.toggled.connect(self._toggle_labels)
        hdr_layout.addWidget(self.chk_labels)

        self.chk_alarms = QCheckBox("Highlight Alarms")
        self.chk_alarms.setChecked(True)
        self.chk_alarms.toggled.connect(self._toggle_alarms)
        hdr_layout.addWidget(self.chk_alarms)

        layout.addLayout(hdr_layout)
        layout.addStretch(1)

    def _toggle_phases(self, checked: bool) -> None:
        self.show_phase_lines = checked
        self.update()

    def _toggle_labels(self, checked: bool) -> None:
        self.show_limit_labels = checked
        self.update()

    def _toggle_alarms(self, checked: bool) -> None:
        self.show_alarms = checked
        self.update()

    def paintEvent(self, event) -> None:
        p = chart_painter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = self.width()
        h = self.height()
        top_offset = 45

        # Background
        p.fillRect(0, 0, w, h, QColor("#ffffff"))

        pts = self.result.get("points", [])
        disp_pts = self.result.get("disp_points", [])
        if not pts:
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "No control chart data available.")
            p.end()
            return

        n_subgroups = len(pts)
        margin_left = 75
        margin_right = 110
        margin_bottom = 40
        plot_w = max(100.0, float(w - margin_left - margin_right))

        # Split canvas into top panel (Primary) and bottom panel (Dispersion)
        avail_h = max(100.0, float(h - top_offset - margin_bottom))
        panel_h = (avail_h - 25.0) / 2.0

        rect_top = QRectF(margin_left, top_offset + 10, plot_w, panel_h)
        rect_bot = QRectF(margin_left, top_offset + panel_h + 25, plot_w, panel_h)

        self.panels = [
            {"name": "primary", "rect": rect_top},
            {"name": "dispersion", "rect": rect_bot},
        ]

        # Draw Top Panel: Primary Chart
        self._draw_chart_panel(
            p,
            rect=rect_top,
            points=pts,
            title=f"{self.result.get('primary_label', 'Sample Mean')} Chart",
            is_primary=True,
            n_subgroups=n_subgroups,
        )

        # Draw Bottom Panel: Dispersion Chart
        self._draw_chart_panel(
            p,
            rect=rect_bot,
            points=disp_pts,
            title=f"{self.result.get('disp_label', 'Sample Range')} Chart",
            is_primary=False,
            n_subgroups=n_subgroups,
        )

        # Draw X-axis subgroup labels
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(MUTED))
        step_x = plot_w / max(1, n_subgroups)
        label_interval = max(1, n_subgroups // 25)
        for i in range(0, n_subgroups, label_interval):
            pt = pts[i]
            x_pos = margin_left + i * step_x + step_x / 2.0
            lbl = str(pt.get("label", i + 1))
            p.drawText(
                QRectF(x_pos - 25, rect_bot.bottom() + 6, 50, 20),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                lbl,
            )

        p.end()

    def _draw_chart_panel(
        self,
        p: QPainter,
        rect: QRectF,
        points: List[Dict[str, Any]],
        title: str,
        is_primary: bool,
        n_subgroups: int,
    ) -> None:
        # Background card
        p.setPen(QPen(QColor(BORDER), 1))
        p.setBrush(QBrush(QColor("#fcfdfd")))
        p.drawRoundedRect(rect, 4, 4)

        # Title
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        p.setPen(QColor(INK))
        p.drawText(QRectF(rect.left() + 8, rect.top() + 6, 250, 20), Qt.AlignmentFlag.AlignLeft, title)

        # Compute Y min/max bounds across points & limits
        valid_y: List[float] = []
        for pt in points:
            val = pt.get("value")
            if val is not None:
                valid_y.append(val)
            for k in ("ucl", "cl", "lcl"):
                if pt.get(k) is not None:
                    valid_y.append(pt[k])

        if not valid_y:
            return

        y_min = min(valid_y)
        y_max = max(valid_y)
        y_pad = max((y_max - y_min) * 0.15, 0.05)
        y_low = y_min - y_pad
        y_high = y_max + y_pad
        if abs(y_high - y_low) < 1e-9:
            y_high += 1.0
            y_low -= 1.0

        def to_screen_y(val: float) -> float:
            ratio = (val - y_low) / (y_high - y_low)
            return rect.bottom() - 10 - ratio * (rect.height() - 25)

        step_x = rect.width() / max(1, n_subgroups)

        # Grid lines and Y axis ticks
        p.setFont(QFont("Segoe UI", 8))
        n_ticks = 4
        for t in range(n_ticks + 1):
            val_t = y_low + t * (y_high - y_low) / n_ticks
            y_pos = to_screen_y(val_t)
            p.setPen(QPen(QColor(GRID), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(rect.left(), y_pos), QPointF(rect.right(), y_pos))

            p.setPen(QColor(MUTED))
            p.drawText(
                QRectF(rect.left() - 65, y_pos - 8, 58, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{val_t:.3f}",
            )

        # Draw Phase Vertical Dividers
        curr_phase = points[0].get("phase") if points else None
        phase_transitions: List[Tuple[int, str]] = []
        for idx in range(1, len(points)):
            ph = points[idx].get("phase")
            if ph != curr_phase:
                phase_transitions.append((idx, ph))
                curr_phase = ph

        if self.show_phase_lines:
            for idx, ph_name in phase_transitions:
                trans_x = rect.left() + idx * step_x
                p.setPen(QPen(QColor(PHASE_LINE), 1.5, Qt.PenStyle.DashDotLine))
                p.drawLine(QPointF(trans_x, rect.top()), QPointF(trans_x, rect.bottom()))

                # Phase header badge
                p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
                p.setPen(QColor("#475569"))
                p.drawText(
                    QRectF(trans_x + 6, rect.top() + 6, 120, 18),
                    Qt.AlignmentFlag.AlignLeft,
                    ph_name,
                )

        # Draw Control Limits (UCL, CL, LCL) steps per subgroup
        p.setPen(QPen(QColor(UCL_COLOR), 1.2, Qt.PenStyle.DashLine))
        for i in range(len(points)):
            pt = points[i]
            x1 = rect.left() + i * step_x
            x2 = x1 + step_x
            if pt.get("ucl") is not None:
                p.setPen(QPen(QColor(UCL_COLOR), 1.2, Qt.PenStyle.DashLine))
                yu = to_screen_y(pt["ucl"])
                p.drawLine(QPointF(x1, yu), QPointF(x2, yu))
            if pt.get("cl") is not None:
                p.setPen(QPen(QColor(CL_COLOR), 1.2, Qt.PenStyle.SolidLine))
                yc = to_screen_y(pt["cl"])
                p.drawLine(QPointF(x1, yc), QPointF(x2, yc))
            if pt.get("lcl") is not None:
                p.setPen(QPen(QColor(LCL_COLOR), 1.2, Qt.PenStyle.DashLine))
                yl = to_screen_y(pt["lcl"])
                p.drawLine(QPointF(x1, yl), QPointF(x2, yl))

        # Right-hand side limit labels for the last phase
        if self.show_limit_labels and points:
            last_pt = points[-1]
            p.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            if last_pt.get("ucl") is not None:
                p.setPen(QColor(UCL_COLOR))
                p.drawText(
                    QRectF(rect.right() + 6, to_screen_y(last_pt["ucl"]) - 8, 90, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"UCL={last_pt['ucl']:.3f}",
                )
            if last_pt.get("cl") is not None:
                p.setPen(QColor(CL_COLOR))
                p.drawText(
                    QRectF(rect.right() + 6, to_screen_y(last_pt["cl"]) - 8, 90, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"CL={last_pt['cl']:.3f}",
                )
            if last_pt.get("lcl") is not None:
                p.setPen(QColor(LCL_COLOR))
                p.drawText(
                    QRectF(rect.right() + 6, to_screen_y(last_pt["lcl"]) - 8, 90, 16),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"LCL={last_pt['lcl']:.3f}",
                )

        # Draw connecting line through points
        path = QPainterPath()
        started = False
        coords: List[Tuple[float, float, Dict[str, Any]]] = []

        for i, pt in enumerate(points):
            val = pt.get("value")
            if val is None:
                continue
            sx = rect.left() + i * step_x + step_x / 2.0
            sy = to_screen_y(val)
            coords.append((sx, sy, pt))
            if not started:
                path.moveTo(sx, sy)
                started = True
            else:
                path.lineTo(sx, sy)

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(LINE_COLOR), 1.5))
        p.drawPath(path)

        # Draw Point Markers
        for sx, sy, pt in coords:
            alarm = pt.get("alarm", False) and self.show_alarms
            if alarm:
                # Crimson out-of-control alarm marker
                p.setPen(QPen(QColor("#7f1d1d"), 1))
                p.setBrush(QBrush(QColor(ALARM_COLOR)))
                p.drawRect(QRectF(sx - 4.5, sy - 4.5, 9, 9))

                # Red halo ring
                p.setPen(QPen(QColor(239, 68, 68, 90), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(sx, sy), 8, 8)
            else:
                p.setPen(QPen(QColor("#ffffff"), 1.2))
                p.setBrush(QBrush(QColor(POINT_COLOR)))
                p.drawEllipse(QPointF(sx, sy), 3.5, 3.5)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        pts = self.result.get("points", [])
        if not pts or not self.panels:
            return

        n_subgroups = len(pts)
        margin_left = 75
        margin_right = 110
        plot_w = max(100.0, float(self.width() - margin_left - margin_right))
        step_x = plot_w / max(1, n_subgroups)

        if margin_left <= pos.x() <= self.width() - margin_right:
            idx = int((pos.x() - margin_left) / step_x)
            if 0 <= idx < n_subgroups:
                pt = pts[idx]
                disp_pt = self.result.get("disp_points", [])[idx] if idx < len(self.result.get("disp_points", [])) else {}
                val_disp_str = f"{disp_pt.get('value'):.4f}" if disp_pt.get("value") is not None else "N/A"
                alarm_str = " (OUT OF CONTROL)" if pt.get("alarm") else ""
                tooltip = (
                    f"Subgroup {pt.get('label', idx + 1)} [{pt.get('phase', 'Phase')}]\n"
                    f"{self.result.get('primary_label', 'Mean')}: {pt.get('value'):.4f}{alarm_str}\n"
                    f"{self.result.get('disp_label', 'Range')}: {val_disp_str}\n"
                    f"UCL: {pt.get('ucl', 0):.4f} | CL: {pt.get('cl', 0):.4f} | LCL: {pt.get('lcl', 0):.4f}"
                )
                QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)
                return
        QToolTip.hideText()
