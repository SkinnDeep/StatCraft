"""High-fidelity Qt/QPainter renderer for Individuals-Moving Range (I-MR) Control Charts.

Matches StatCraft visual styling:
- Top panel: I Chart of <Variable> (Individual values, Mean center line, UCL, LCL, Test markers)
- Bottom panel: Moving Range Chart of <Variable> (Moving ranges, MR center line, UCL, LCL, Test markers)
- Anti-aliased crisp lines and markers
- Right-hand limit and center annotations
- Full GraphInteractionMixin integration with objectSelected, objectActivated, brushRowsSelected
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .graph_interaction import GraphInteractionMixin

BLUE = "#0061a8"
INK = "#1a2b38"
MUTED = "#5b6b77"
BORDER = "#ced6dc"
RED = "#c23934"
GREEN = "#1b7837"
GRID = "#e8ecef"


def _fmt(val: Optional[float], dec: int = 3) -> str:
    if val is None or math.isnan(val):
        return ""
    return f"{val:.{dec}f}"


def _bounds(values: List[float], pad_frac: float = 0.15) -> Tuple[float, float]:
    clean = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
    if not clean:
        return (0.0, 1.0)
    lo, hi = min(clean), max(clean)
    if lo == hi:
        delta = max(0.5, abs(lo) * 0.05)
        return (lo - delta, hi + delta)
    pad = (hi - lo) * pad_frac
    return (lo - pad, hi + pad)


class IMRChartWidget(GraphInteractionMixin, QWidget):
    """Dual-panel control chart widget for Individuals and Moving Range."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.entry = entry
        self.result = entry.get("result", entry) if isinstance(entry, dict) else {}
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(QSize(760, 680))

        self.panels: List[Dict[str, Any]] = []
        self._prepare_panels()

    def _prepare_panels(self) -> None:
        r = self.result
        var_name = r.get("variable_name", r.get("variable", "Data"))
        obs = r.get("observations", [])
        mrs = r.get("moving_ranges", [])
        n_pts = len(obs)

        # Panel 1: I Chart
        i_center = r.get("i_center", r.get("mean", 0.0))
        i_lcl = r.get("i_lcl")
        i_ucl = r.get("i_ucl")
        i_tests = r.get("test_failures", {})
        if not i_tests and r.get("i_signals"):
            i_tests = {pt: [1] for pt in r.get("i_signals", [])}

        self.panels.append({
            "panel_type": "i_chart",
            "title": f"I Chart of {var_name}",
            "ylabel": "Individual Value",
            "xlabel": "Observation",
            "values": obs,
            "center": i_center,
            "center_label": f"__\nX={_fmt(i_center)}",
            "lcl": i_lcl,
            "ucl": i_ucl,
            "uwl": r.get("i_uwl"),
            "lwl": r.get("i_lwl"),
            "signals": i_tests,
            "n_pts": n_pts,
        })

        # Panel 2: MR Chart
        mr_center = r.get("mr_center", r.get("disp_center", 0.0))
        mr_lcl = r.get("mr_lcl", r.get("disp_lcl"))
        mr_ucl = r.get("mr_ucl", r.get("disp_ucl"))
        mr_signals = {pt: [1] for pt in r.get("mr_signals", [])}

        self.panels.append({
            "panel_type": "mr_chart",
            "title": f"Moving Range Chart of {var_name}",
            "ylabel": "Moving Range",
            "xlabel": "Observation",
            "values": mrs,
            "center": mr_center,
            "center_label": f"__\nMR={_fmt(mr_center)}",
            "lcl": mr_lcl,
            "ucl": mr_ucl,
            "uwl": r.get("mr_uwl"),
            "lwl": r.get("mr_lwl"),
            "signals": mr_signals,
            "n_pts": n_pts,
        })

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect()
        p.fillRect(rect, Qt.GlobalColor.white)

        w, h = rect.width(), rect.height()
        margin_t = 12
        margin_b = 24
        gap = 18
        available_h = h - margin_t - margin_b - gap
        panel_h = available_h / 2.0

        for i, panel_data in enumerate(self.panels):
            top_y = margin_t + i * (panel_h + gap)
            area = QRectF(10, top_y, w - 20, panel_h)
            self._draw_control_panel(p, area, panel_data)

    def _draw_control_panel(self, p: QPainter, area: QRectF, d: Dict[str, Any]) -> None:
        p.save()
        # Title
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        p.setPen(QColor(INK))
        p.drawText(
            QRectF(area.left() + 70, area.top() + 2, area.width() - 150, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            d["title"],
        )

        n_pts = d.get("n_pts", 0)
        if n_pts <= 0:
            p.restore()
            return

        values = d["values"]
        center = d.get("center")
        lcl = d.get("lcl")
        ucl = d.get("ucl")
        signals = d.get("signals", {})

        # Compute Y bounds
        all_y: List[float] = [v for v in values if v is not None]
        if center is not None:
            all_y.append(center)
        if lcl is not None:
            all_y.append(lcl)
        if ucl is not None:
            all_y.append(ucl)

        xb = (0.5, n_pts + 0.5)
        yb = _bounds(all_y, pad_frac=0.18)

        # Plot rectangle with margins
        plot_l = area.left() + 65
        plot_r = area.right() - 85
        plot_t = area.top() + 26
        plot_b = area.bottom() - 28
        plot_w = max(10, plot_r - plot_l)
        plot_h = max(10, plot_b - plot_t)
        plot_rect = QRectF(plot_l, plot_t, plot_w, plot_h)

        def to_x(idx: float) -> float:
            return plot_l + ((idx - xb[0]) / (xb[1] - xb[0])) * plot_w

        def to_y(val: float) -> float:
            return plot_b - ((val - yb[0]) / (yb[1] - yb[0])) * plot_h

        # Background grid and border
        p.setPen(QPen(QColor(BORDER), 1.0))
        p.drawRect(plot_rect)

        # Axes labels
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QColor(MUTED))
        # Y axis label
        p.save()
        p.translate(plot_l - 45, plot_t + plot_h / 2.0)
        p.rotate(-90)
        p.drawText(QRectF(-80, -10, 160, 20), Qt.AlignmentFlag.AlignCenter, d.get("ylabel", ""))
        p.restore()

        # X axis label
        p.drawText(
            QRectF(plot_l, plot_b + 8, plot_w, 18),
            Qt.AlignmentFlag.AlignCenter,
            d.get("xlabel", "Observation"),
        )

        # Clip inside plot rectangle for data lines
        p.save()
        p.setClipRect(plot_rect.adjusted(-1, -1, 1, 1))

        # 1. Draw Center Line (green dashed)
        if center is not None and yb[0] <= center <= yb[1]:
            p.setPen(QPen(QColor(GREEN), 1.3, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(plot_l, to_y(center)), QPointF(plot_r, to_y(center)))

        # 2. Draw Control Limits (red dashed)
        p.setPen(QPen(QColor(RED), 1.2, Qt.PenStyle.DashLine))
        if ucl is not None and yb[0] <= ucl <= yb[1]:
            p.drawLine(QPointF(plot_l, to_y(ucl)), QPointF(plot_r, to_y(ucl)))
        if lcl is not None and yb[0] <= lcl <= yb[1]:
            p.drawLine(QPointF(plot_l, to_y(lcl)), QPointF(plot_r, to_y(lcl)))

        # 2b. Draw Warning Limits (amber dashed)
        uwl = d.get("uwl")
        lwl = d.get("lwl")
        AMBER = "#D97706"
        p.setPen(QPen(QColor(AMBER), 1.1, Qt.PenStyle.DashLine))
        if uwl is not None and yb[0] <= uwl <= yb[1]:
            p.drawLine(QPointF(plot_l, to_y(uwl)), QPointF(plot_r, to_y(uwl)))
        if lwl is not None and yb[0] <= lwl <= yb[1]:
            p.drawLine(QPointF(plot_l, to_y(lwl)), QPointF(plot_r, to_y(lwl)))

        # 3. Connect points with blue line
        p.setPen(QPen(QColor(BLUE), 1.4, Qt.PenStyle.SolidLine))
        path_pts = QPainterPath()
        started = False
        for i, v in enumerate(values, 1):
            if v is None:
                started = False
                continue
            pt = QPointF(to_x(i), to_y(v))
            if not started:
                path_pts.moveTo(pt)
                started = True
            else:
                path_pts.lineTo(pt)
        p.drawPath(path_pts)

        # 4. Draw markers and test numbers
        font_test = QFont("Segoe UI", 8, QFont.Weight.Bold)
        for i, v in enumerate(values, 1):
            if v is None:
                continue
            pt = QPointF(to_x(i), to_y(v))
            if i in signals:
                # Out-of-control red marker
                p.setPen(QPen(QColor(RED), 1.5))
                p.setBrush(QColor(RED))
                p.drawEllipse(pt, 3.8, 3.8)

                # Label with test numbers
                test_nums = signals[i]
                test_str = ",".join(str(t) for t in test_nums)
                p.setFont(font_test)
                p.setPen(QColor(RED))
                y_offset = -14 if (center is None or v >= center) else 14
                p.drawText(
                    QRectF(pt.x() - 20, pt.y() + y_offset - 6, 40, 14),
                    Qt.AlignmentFlag.AlignCenter,
                    test_str,
                )
            else:
                # Normal point
                p.setPen(QPen(QColor(BLUE), 1.2))
                p.setBrush(QColor("white"))
                p.drawEllipse(pt, 3.2, 3.2)

        p.restore()  # End plot rect clipping

        # 5. Right-side margin limit callouts
        p.setFont(QFont("Segoe UI", 8))
        callout_x = plot_r + 6

        if ucl is not None and yb[0] <= ucl <= yb[1]:
            p.setPen(QColor(RED))
            p.drawText(
                QRectF(callout_x, to_y(ucl) - 8, 75, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"UCL={ucl:.3f}",
            )

        if uwl is not None and yb[0] <= uwl <= yb[1]:
            p.setPen(QColor(AMBER))
            p.drawText(
                QRectF(callout_x, to_y(uwl) - 8, 75, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"UWL={uwl:.3f}",
            )

        if center is not None and yb[0] <= center <= yb[1]:
            p.setPen(QColor(GREEN))
            cl_label = d.get("center_label", f"CL={center:.3f}").replace("\n", " ")
            p.drawText(
                QRectF(callout_x, to_y(center) - 8, 75, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                cl_label,
            )

        if lwl is not None and yb[0] <= lwl <= yb[1]:
            p.setPen(QColor(AMBER))
            p.drawText(
                QRectF(callout_x, to_y(lwl) - 8, 75, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"LWL={lwl:.3f}",
            )

        if lcl is not None and yb[0] <= lcl <= yb[1]:
            p.setPen(QColor(RED))
            p.drawText(
                QRectF(callout_x, to_y(lcl) - 8, 75, 16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"LCL={lcl:.3f}",
            )

        p.restore()
