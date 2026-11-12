"""Qt Chart widget for Process Capability Analysis (Normal Distribution)."""

import math
from typing import Any, Dict, List
import numpy as np
from scipy.stats import norm

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath
from PySide6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QSlider
from .chart_theme import chart_painter


def _ci_text(bounds):
    return '(' + ', '.join('*' if value is None else f'{value:.2f}' for value in bounds) + ')'


def performance_table(res, stats_type='capability', is_bw=False, unit='PPM'):
    """Values and headings used by the plot, preserving unavailable Z values."""
    within=res.get('within_perf', {});overall=res.get('overall_perf', {})
    if stats_type == 'zbench':
        headers=['Between/Within' if is_bw else 'Within', 'Overall']
        rows=[]
        for label,key,spec in [('Z.LSL','z_lsl','lsl'),('Z.USL','z_usl','usl'),('Z.Bench','z_bench',None)]:
            if spec is None or res.get(spec) is not None:
                rows.append((label,[within.get(key),overall.get(key)]))
        return headers,rows
    observed=res.get('observed_perf', {})
    headers=['Observed', 'Exp. Between/Within' if is_bw else 'Exp. Within', 'Exp. Overall']
    rows=[]
    for label,key,spec in [(f'{unit} < LSL','below','lsl'),(f'{unit} > USL','above','usl'),(f'{unit} Total','total',None)]:
        if spec is None or res.get(spec) is not None:
            rows.append((label,[observed.get(key),within.get('expected_'+key),overall.get('expected_'+key)]))
    return headers,rows


class CapabilityPlotWidget(QWidget):
    """StatCraft Process Capability Report Plot Widget."""

    objectSelected = Signal(str)
    objectActivated = Signal(str)
    brushRowsSelected = Signal(list)

    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entry = entry
        self.error = None
        self.panels = []
        self.override_lsl: Optional[float] = None
        self.override_usl: Optional[float] = None
        self.drift_pct: float = 0.0
        self.setMinimumSize(780, 520)

    @property
    def is_simulation_active(self) -> bool:
        return (self.override_lsl is not None or self.override_usl is not None or abs(self.drift_pct) > 1e-6)

    def set_simulation(self, override_lsl=None, override_usl=None, drift_pct=0.0):
        self.override_lsl = override_lsl
        self.override_usl = override_usl
        self.drift_pct = float(drift_pct)
        self.update()

    def reset_simulation(self):
        self.override_lsl = None
        self.override_usl = None
        self.drift_pct = 0.0
        self.update()

    def paintEvent(self, event):
        painter = chart_painter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, QColor("#FFFFFF"))

        res = self.entry.get("result", {})
        if not res:
            return

        var_name = res.get("variable_name", "Data")
        is_bw = (res.get("analysis_mode") == "between_within")
        default_title = f"Between/Within Capability Report for {var_name}" if is_bw else f"Process Capability Report for {var_name}"
        title = res.get("title") or default_title
        obs = res.get("observations", [])
        if not obs:
            return

        lsl = self.override_lsl if self.override_lsl is not None else res.get("lsl")
        usl = self.override_usl if self.override_usl is not None else res.get("usl")
        target = res.get("target")
        mean = res.get("mean", 0.0)
        drift_mult = 1.0 + (self.drift_pct / 100.0)
        sd_within = res.get("stdev_within", 1.0) * drift_mult
        sd_bw = (res.get("stdev_between_within", sd_within) if is_bw else sd_within) * drift_mult
        sd_overall = res.get("stdev_overall", 1.0) * drift_mult
        n_obs = res.get("sample_n", len(obs))
        stats_type = res.get("stats_type", "capability")
        include_ci = res.get("include_ci", False)
        unit = "%" if res.get("display_unit", "ppm").lower() == "percent" else "PPM"

        render_res = dict(res)
        if self.is_simulation_active:
            render_res["lsl"] = lsl
            render_res["usl"] = usl
            render_res["stdev_within"] = sd_within
            render_res["stdev_overall"] = sd_overall
            if lsl is not None and usl is not None and sd_within > 0:
                render_res["cp"] = (usl - lsl) / (6.0 * sd_within)
            else:
                render_res["cp"] = None
            sim_cpl = (mean - lsl) / (3.0 * sd_within) if (lsl is not None and sd_within > 0) else None
            sim_cpu = (usl - mean) / (3.0 * sd_within) if (usl is not None and sd_within > 0) else None
            render_res["cpl"] = sim_cpl
            render_res["cpu"] = sim_cpu
            render_res["cpk"] = min(sim_cpl, sim_cpu) if (sim_cpl is not None and sim_cpu is not None) else (sim_cpl if sim_cpl is not None else sim_cpu)

            if lsl is not None and usl is not None and sd_overall > 0:
                render_res["pp"] = (usl - lsl) / (6.0 * sd_overall)
            else:
                render_res["pp"] = None
            sim_ppl = (mean - lsl) / (3.0 * sd_overall) if (lsl is not None and sd_overall > 0) else None
            sim_ppu = (usl - mean) / (3.0 * sd_overall) if (usl is not None and sd_overall > 0) else None
            render_res["ppl"] = sim_ppl
            render_res["ppu"] = sim_ppu
            render_res["ppk"] = min(sim_ppl, sim_ppu) if (sim_ppl is not None and sim_ppu is not None) else (sim_ppl if sim_ppl is not None else sim_ppu)

        # Overall dimensions
        w = rect.width()
        h = rect.height()

        # Title
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(20, 8, w - 40, 26), Qt.AlignmentFlag.AlignCenter, title)

        if self.is_simulation_active:
            painter.setPen(QColor("#B45309"))
            painter.setBrush(QBrush(QColor("#FEF3C7")))
            sim_badge = QRectF(w - 230, 8, 210, 22)
            painter.drawRoundedRect(sim_badge, 4, 4)
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(sim_badge, Qt.AlignmentFlag.AlignCenter, "⚡ LIVE WHAT-IF SIMULATION")

        # Layout partitioning
        left_box_w = 150
        right_box_w = 190
        margin = 15
        top = 40
        bottom_box_h = 100
        bottom = h - bottom_box_h - margin

        plot_left = left_box_w + 2 * margin + 35
        plot_right = w - right_box_w - 2 * margin
        plot_top = top + 34
        plot_bottom = bottom - 42
        plot_w = plot_right - plot_left
        plot_h = plot_bottom - plot_top

        # Draw 1: Process Data Box (Left)
        self._draw_process_data_box(painter, margin, top, left_box_w, bottom - top, render_res, is_bw)

        # Draw 2: Overall & Within Capability Boxes (Right)
        cap_h = (bottom - top - 10) / 2
        self._draw_overall_capability_box(painter, w - right_box_w - margin, top, right_box_w, cap_h, render_res)
        self._draw_within_capability_box(painter, w - right_box_w - margin, top + cap_h + 10, right_box_w, cap_h, render_res, is_bw)

        # Draw 3: Performance Box (Bottom)
        self._draw_performance_box(painter, margin, bottom + 5, w - 2 * margin, bottom_box_h, res, unit, stats_type, is_bw)

        # Draw 4: Histogram and Curves in the Main Plot Area
        if plot_w > 80 and plot_h > 80:
            self._draw_plot_area(
                painter, plot_left, plot_top, plot_right, plot_bottom,
                obs, mean, sd_bw, sd_overall, lsl, usl, target, is_bw, var_name
            )

    def _draw_process_data_box(self, painter, x, y, width, height, res, is_bw=False):
        rect = QRectF(x, y, width, height)
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(x + 8, y + 6, width - 16, 20), Qt.AlignmentFlag.AlignLeft, "Process Data")

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        items = []
        if res.get("lsl") is not None:
            items.append(("LSL", f"{res['lsl']:g}"))
        if res.get("target") is not None:
            items.append(("Target", f"{res['target']:g}"))
        if res.get("usl") is not None:
            items.append(("USL", f"{res['usl']:g}"))
        items.append(("Sample Mean", f"{res.get('mean', 0.0):.4g}"))
        items.append(("Sample N", f"{res.get('sample_n', 0)}"))
        if is_bw:
            items.append(("StDev(B/W)", f"{res.get('stdev_between_within', 0.0):.4g}"))
            items.append(("StDev(Between)", f"{res.get('stdev_between', 0.0):.4g}"))
            items.append(("StDev(Within)", f"{res.get('stdev_within', 0.0):.4g}"))
            items.append(("StDev(Overall)", f"{res.get('stdev_overall', 0.0):.4g}"))
        else:
            items.append(("StDev(Within)", f"{res.get('stdev_within', 0.0):.4g}"))
            items.append(("StDev(Overall)", f"{res.get('stdev_overall', 0.0):.4g}"))

        curr_y = y + 28
        row_step = 17 if len(items) > 7 else 20
        for label, val in items:
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(x + 8, curr_y, width * 0.6, 18), Qt.AlignmentFlag.AlignLeft, label)
            painter.setPen(QColor("#0F172A"))
            painter.drawText(QRectF(x + width * 0.55, curr_y, width * 0.40, 18), Qt.AlignmentFlag.AlignRight, val)
            curr_y += row_step

    def _draw_overall_capability_box(self, painter, x, y, width, height, res):
        rect = QRectF(x, y, width, height)
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(x + 8, y + 6, width - 16, 20), Qt.AlignmentFlag.AlignLeft, "Overall Capability")

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        items = []
        if res.get("pp") is not None:
            items.append(("Pp", f"{res['pp']:.2f}"))
        if res.get("ppl") is not None:
            items.append(("PPL", f"{res['ppl']:.2f}"))
        if res.get("ppu") is not None:
            items.append(("PPU", f"{res['ppu']:.2f}"))
        if res.get("ppk") is not None:
            items.append(("Ppk", f"{res['ppk']:.2f}"))

        curr_y = y + 28
        for label, val in items:
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(x + 8, curr_y, width * 0.5, 18), Qt.AlignmentFlag.AlignLeft, label)
            painter.setPen(QColor("#0F172A"))
            painter.drawText(QRectF(x + width * 0.5, curr_y, width * 0.45, 18), Qt.AlignmentFlag.AlignRight, val)
            curr_y += 18

        if res.get("include_ci"):
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
            ci_pp = res.get("ci_pp")
            ci_ppk = res.get("ci_ppk")
            if ci_pp and (ci_pp[0] is not None or ci_pp[1] is not None):
                c_str = f"Pp CI: {_ci_text(ci_pp)}"
                painter.drawText(QRectF(x + 8, curr_y, width - 16, 16), Qt.AlignmentFlag.AlignLeft, c_str)
                curr_y += 16
            if ci_ppk and (ci_ppk[0] is not None or ci_ppk[1] is not None):
                c_str = f"Ppk CI: {_ci_text(ci_ppk)}"
                painter.drawText(QRectF(x + 8, curr_y, width - 16, 16), Qt.AlignmentFlag.AlignLeft, c_str)

    def _draw_within_capability_box(self, painter, x, y, width, height, res, is_bw=False):
        rect = QRectF(x, y, width, height)
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(rect, 4, 4)

        is_machine = (res.get("study_type") == "machine")
        is_aiag_vda = (res.get("naming_convention") == "aiag_vda")

        if is_machine:
            box_title = "Machine Capability"
            p_lbl, pl_lbl, pu_lbl, pk_lbl = "Cm", "CmL", "CmU", "Cmk"
        elif is_bw and is_aiag_vda:
            box_title = "Between/Within (AIAG/VDA)"
            p_lbl, pl_lbl, pu_lbl, pk_lbl = "Cbw", "CbwL", "CbwU", "Cbwk"
        elif is_bw:
            box_title = "Potential (Between/Within) Capability"
            p_lbl, pl_lbl, pu_lbl, pk_lbl = "Cp", "CPL", "CPU", "Cpk"
        else:
            box_title = "Potential (Within) Capability"
            p_lbl, pl_lbl, pu_lbl, pk_lbl = "Cp", "CPL", "CPU", "Cpk"

        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(QRectF(x + 8, y + 6, width - 16, 20), Qt.AlignmentFlag.AlignLeft, box_title)

        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))
        items = []
        if res.get("cp") is not None:
            items.append((p_lbl, f"{res['cp']:.2f}"))
        if res.get("cpl") is not None:
            items.append((pl_lbl, f"{res['cpl']:.2f}"))
        if res.get("cpu") is not None:
            items.append((pu_lbl, f"{res['cpu']:.2f}"))
        if res.get("cpk") is not None:
            items.append((pk_lbl, f"{res['cpk']:.2f}"))
        if res.get("cpm") is not None:
            items.append(("Cpm", f"{res['cpm']:.2f}"))

        curr_y = y + 28
        for label, val in items:
            painter.setPen(QColor("#475569"))
            painter.drawText(QRectF(x + 8, curr_y, width * 0.5, 18), Qt.AlignmentFlag.AlignLeft, label)
            painter.setPen(QColor("#0F172A"))
            painter.drawText(QRectF(x + width * 0.5, curr_y, width * 0.45, 18), Qt.AlignmentFlag.AlignRight, val)
            curr_y += 18

        if res.get("include_ci"):
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Normal))
            ci_cp = res.get("ci_cp")
            ci_cpk = res.get("ci_cpk")
            if ci_cp and (ci_cp[0] is not None or ci_cp[1] is not None):
                c_str = f"{p_lbl} CI: {_ci_text(ci_cp)}"
                painter.drawText(QRectF(x + 8, curr_y, width - 16, 16), Qt.AlignmentFlag.AlignLeft, c_str)
                curr_y += 16
            if ci_cpk and (ci_cpk[0] is not None or ci_cpk[1] is not None):
                c_str = f"{pk_lbl} CI: {_ci_text(ci_cpk)}"
                painter.drawText(QRectF(x + 8, curr_y, width - 16, 16), Qt.AlignmentFlag.AlignLeft, c_str)

    def _draw_performance_box(self, painter, x, y, width, height, res, unit, stats_type, is_bw=False):
        rect = QRectF(x, y, width, height)
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QBrush(QColor("#F8FAFC")))
        painter.drawRoundedRect(rect, 4, 4)

        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        header = f"Performance ({unit})" if stats_type != "zbench" else "Benchmark Z's"
        painter.drawText(QRectF(x + 8, y + 6, width - 16, 20), Qt.AlignmentFlag.AlignLeft, header)

        headers,rows=performance_table(res,stats_type,is_bw,unit)
        col_w=(width-160)/len(headers)
        painter.setFont(QFont('Segoe UI',8,QFont.Weight.DemiBold))
        for index,heading in enumerate(headers):
            painter.drawText(QRectF(x+150+index*col_w,y+26,col_w,18),Qt.AlignmentFlag.AlignRight,heading)
        painter.setFont(QFont('Segoe UI',8,QFont.Weight.Normal))
        for index,(name,values) in enumerate(rows):
            curr_y=y+44+index*18
            painter.setPen(QColor('#475569'))
            painter.drawText(QRectF(x+12,curr_y,138,18),Qt.AlignmentFlag.AlignLeft,name)
            painter.setPen(QColor('#0F172A'))
            for col,value in enumerate(values):
                text='*' if value is None else f'{value:.2f}'
                painter.drawText(QRectF(x+150+col*col_w,curr_y,col_w,18),Qt.AlignmentFlag.AlignRight,text)

    def _draw_plot_area(self, painter, left, top, right, bottom, obs, mean, sd_within, sd_overall, lsl, usl, target, is_bw=False, xlabel="Measurement"):
        # Calculate X limits
        data_min = min(obs)
        data_max = max(obs)
        x_min = min(data_min, lsl if lsl is not None else data_min, target if target is not None else data_min)
        x_max = max(data_max, usl if usl is not None else data_max, target if target is not None else data_max)

        # Add 10% padding
        span = x_max - x_min
        if span <= 0:
            span = 1.0
        x_min -= 0.10 * span
        x_max += 0.10 * span

        # Histogram bins (Sturges rule)
        n_bins = max(5, int(math.ceil(math.log2(len(obs)) + 1)) + 2)
        counts, bin_edges = np.histogram(obs, bins=n_bins, range=(x_min, x_max))
        bin_width = bin_edges[1] - bin_edges[0]

        # Calculate max density or frequency
        # Convert counts to density so curves match histogram height
        # Total area under histogram = N * bin_width
        # Curve height at x = N * bin_width * norm.pdf(x, mean, sd)
        scale_factor = len(obs) * bin_width

        def curve_y_val(x, sd):
            if sd <= 0:
                return 0.0
            return scale_factor * norm.pdf(x, mean, sd)

        max_hist = max(counts) if len(counts) > 0 else 1
        max_curve_within = curve_y_val(mean, sd_within)
        max_curve_overall = curve_y_val(mean, sd_overall)
        y_max = max(max_hist, max_curve_within, max_curve_overall) * 1.15

        # Coordinate transforms
        def to_screen_x(xv):
            return left + (xv - x_min) / (x_max - x_min) * (right - left)

        def to_screen_y(yv):
            return bottom - (yv / y_max) * (bottom - top)

        # Draw axes
        painter.setPen(QPen(QColor("#94A3B8"), 1))
        painter.drawLine(QPointF(left, bottom), QPointF(right, bottom))
        painter.drawLine(QPointF(left, top), QPointF(left, bottom))

        # Keep measurement and frequency scales readable in screen and Office captures.
        painter.setFont(QFont('Segoe UI',8))
        painter.setPen(QColor('#475569'))
        for tick in range(6):
            xv=x_min+(x_max-x_min)*tick/5
            sx=to_screen_x(xv)
            painter.drawLine(QPointF(sx,bottom),QPointF(sx,bottom+4))
            painter.drawText(QRectF(sx-32,bottom+5,64,16),Qt.AlignmentFlag.AlignCenter,f'{xv:.4g}')
            yv=y_max*tick/5
            sy=to_screen_y(yv)
            painter.drawLine(QPointF(left-4,sy),QPointF(left,sy))
            painter.drawText(QRectF(left-39,sy-8,32,16),Qt.AlignmentFlag.AlignRight,f'{yv:.3g}')
        painter.drawText(QRectF(left,bottom+23,right-left,18),Qt.AlignmentFlag.AlignCenter,xlabel)

        # Draw Histogram bars
        painter.setBrush(QBrush(QColor("#E0E7FF")))
        painter.setPen(QPen(QColor("#6366F1"), 1))
        for i in range(len(counts)):
            bx1 = to_screen_x(bin_edges[i])
            bx2 = to_screen_x(bin_edges[i + 1])
            by = to_screen_y(counts[i])
            bar_rect = QRectF(bx1, by, max(1.0, bx2 - bx1), bottom - by)
            painter.drawRect(bar_rect)

        # Draw Fitted Curves
        x_grid = np.linspace(x_min, x_max, 200)

        # 1. Within normal curve (solid line, dark blue)
        path_within = QPainterPath()
        path_within.moveTo(to_screen_x(x_grid[0]), to_screen_y(curve_y_val(x_grid[0], sd_within)))
        for xv in x_grid[1:]:
            path_within.lineTo(to_screen_x(xv), to_screen_y(curve_y_val(xv, sd_within)))
        painter.setPen(QPen(QColor("#1D4ED8"), 2, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path_within)

        # 2. Overall normal curve (dashed line, gray/black)
        path_overall = QPainterPath()
        path_overall.moveTo(to_screen_x(x_grid[0]), to_screen_y(curve_y_val(x_grid[0], sd_overall)))
        for xv in x_grid[1:]:
            path_overall.lineTo(to_screen_x(xv), to_screen_y(curve_y_val(xv, sd_overall)))
        painter.setPen(QPen(QColor("#334155"), 2, Qt.PenStyle.DashLine))
        painter.drawPath(path_overall)

        # Draw Spec limit lines: LSL, USL, Target
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))

        if lsl is not None:
            lx = to_screen_x(lsl)
            painter.setPen(QPen(QColor("#DC2626"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(lx, top), QPointF(lx, bottom))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QRectF(lx - 45, top - 32, 90, 30), Qt.AlignmentFlag.AlignCenter, f"LSL\n{lsl:g}")

        if usl is not None:
            ux = to_screen_x(usl)
            painter.setPen(QPen(QColor("#DC2626"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(ux, top), QPointF(ux, bottom))
            painter.setPen(QColor("#DC2626"))
            painter.drawText(QRectF(ux - 45, top - 32, 90, 30), Qt.AlignmentFlag.AlignCenter, f"USL\n{usl:g}")

        if target is not None:
            tx = to_screen_x(target)
            painter.setPen(QPen(QColor("#16A34A"), 1.5, Qt.PenStyle.DashDotLine))
            painter.drawLine(QPointF(tx, top), QPointF(tx, bottom))
            painter.setPen(QColor("#16A34A"))
            painter.drawText(QRectF(tx - 45, top - 32, 90, 30), Qt.AlignmentFlag.AlignCenter, f"Target\n{target:g}")

        # Curve legend in plot area
        leg_w = 95 if is_bw else 70
        leg_x = right - (leg_w + 35)
        leg_y = top + 15
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Normal))

        # Solid Within / Between/Within
        within_label = "Between/Within" if is_bw else "Within"
        painter.setPen(QPen(QColor("#1D4ED8"), 2, Qt.PenStyle.SolidLine))
        painter.drawLine(QPointF(leg_x, leg_y + 6), QPointF(leg_x + 24, leg_y + 6))
        painter.setPen(QColor("#111827"))
        painter.drawText(QRectF(leg_x + 30, leg_y, leg_w, 16), Qt.AlignmentFlag.AlignLeft, within_label)

        # Dashed Overall
        painter.setPen(QPen(QColor("#334155"), 2, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(leg_x, leg_y + 22), QPointF(leg_x + 24, leg_y + 22))
        painter.setPen(QColor("#111827"))
        painter.drawText(QRectF(leg_x + 30, leg_y + 16, leg_w, 16), Qt.AlignmentFlag.AlignLeft, "Overall")


class CapabilityWhatIfStrip(QFrame):
    """Collapsible live What-If Spec & Tolerance Simulation Bar."""

    def __init__(self, plot_widget: CapabilityPlotWidget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.setObjectName("capabilityWhatIfStrip")
        self.setStyleSheet("""
            #capabilityWhatIfStrip {
                background: #F8FAFC;
                border-top: 1px solid #E2E8F0;
                border-radius: 0 0 8px 8px;
                padding: 6px;
            }
        """)

        res = plot_widget.entry.get("result", {})
        self.orig_lsl = res.get("lsl")
        self.orig_usl = res.get("usl")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)

        title_lbl = QLabel("⚡ Live What-If Sliders:")
        title_lbl.setStyleSheet("font-weight: bold; color: #0284C7; font-size: 11px;")
        layout.addWidget(title_lbl)

        # LSL Control
        layout.addWidget(QLabel("LSL:"))
        self.lsl_spin = QDoubleSpinBox()
        self.lsl_spin.setRange(-1e9, 1e9)
        self.lsl_spin.setDecimals(3)
        self.lsl_spin.setValue(self.orig_lsl if self.orig_lsl is not None else -10.0)
        self.lsl_spin.valueChanged.connect(self._on_values_changed)
        layout.addWidget(self.lsl_spin)

        # USL Control
        layout.addWidget(QLabel("USL:"))
        self.usl_spin = QDoubleSpinBox()
        self.usl_spin.setRange(-1e9, 1e9)
        self.usl_spin.setDecimals(3)
        self.usl_spin.setValue(self.orig_usl if self.orig_usl is not None else 10.0)
        self.usl_spin.valueChanged.connect(self._on_values_changed)
        layout.addWidget(self.usl_spin)

        # StDev Drift Dial
        layout.addWidget(QLabel("StDev Shift (%):"))
        self.drift_spin = QDoubleSpinBox()
        self.drift_spin.setRange(-50.0, 100.0)
        self.drift_spin.setSuffix("%")
        self.drift_spin.setValue(0.0)
        self.drift_spin.valueChanged.connect(self._on_values_changed)
        layout.addWidget(self.drift_spin)

        # Reset button
        self.reset_btn = QPushButton("Reset to Actual")
        self.reset_btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.reset_btn.clicked.connect(self._on_reset)
        layout.addWidget(self.reset_btn)

        layout.addStretch()

    def _on_values_changed(self):
        lsl_val = self.lsl_spin.value() if self.orig_lsl is not None else None
        usl_val = self.usl_spin.value() if self.orig_usl is not None else None
        drift = self.drift_spin.value()
        self.plot_widget.set_simulation(override_lsl=lsl_val, override_usl=usl_val, drift_pct=drift)

    def _on_reset(self):
        if self.orig_lsl is not None:
            self.lsl_spin.setValue(self.orig_lsl)
        if self.orig_usl is not None:
            self.usl_spin.setValue(self.orig_usl)
        self.drift_spin.setValue(0.0)
        self.plot_widget.reset_simulation()


class CapabilityContainerWidget(QWidget):
    """Container holding CapabilityPlotWidget with live What-If Simulation strip."""

    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plot = CapabilityPlotWidget(entry, self)
        layout.addWidget(self.plot, 1)

        self.strip = CapabilityWhatIfStrip(self.plot, self)
        layout.addWidget(self.strip, 0)

    # Proxy signals and methods
    @property
    def objectSelected(self):
        return self.plot.objectSelected

    @property
    def objectActivated(self):
        return self.plot.objectActivated

    @property
    def brushRowsSelected(self):
        return self.plot.brushRowsSelected

