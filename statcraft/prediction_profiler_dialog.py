"""Interactive Prediction Profiler Dialog for StatCraft.

Provides a multi-factor dynamic prediction profiler with interactive crosshairs,
confidence interval bands, Derringer-Suich desirability optimization, and real-time
parameter exploration matching SAS JMP's Prediction Profiler.
"""
from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QPointF, Signal, QRectF
from PySide6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF, QCursor
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QGroupBox, QScrollArea, QWidget, QFrame,
    QDialogButtonBox, QMessageBox, QToolTip, QSizePolicy
)

from .model import Worksheet
from .prediction import normalize_recipe
from .prediction_profiler import (
    ProfilerFactor, ProfilerResponse, extract_profiler_specs,
    compute_prediction_profiles, compute_composite_desirability,
    optimize_profiler_settings
)


class ProfilerCellWidget(QWidget):
    """Interactive vector canvas rendering prediction curve, CI band, and draggable crosshairs."""
    factorChanged = Signal(str, float)

    def __init__(self, factor: ProfilerFactor, response_name: str, parent=None):
        super().__init__(parent)
        self.factor = factor
        self.response_name = response_name
        self.trace_data: Optional[dict[str, Any]] = None
        self.current_fit: Optional[float] = None
        self.y_min: float = 0.0
        self.y_max: float = 1.0
        self.is_dragging = False

        self.setMinimumSize(180, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)

    def update_data(self, trace_data: dict[str, Any], current_fit: Optional[float], y_min: float, y_max: float):
        self.trace_data = trace_data
        self.current_fit = current_fit
        self.y_min = y_min
        self.y_max = y_max if y_max > y_min else y_min + 1.0
        self.update()

    def _val_to_pixel(self, x_val: float, y_val: float, rect: QRectF) -> QPointF:
        x_min, x_max = self.factor.min_val, self.factor.max_val
        x_range = max(1e-9, x_max - x_min)
        y_range = max(1e-9, self.y_max - self.y_min)

        px = rect.left() + ((x_val - x_min) / x_range) * rect.width()
        py = rect.bottom() - ((y_val - self.y_min) / y_range) * rect.height()
        return QPointF(px, py)

    def _pixel_to_x_val(self, px: float, rect: QRectF) -> float:
        x_min, x_max = self.factor.min_val, self.factor.max_val
        rel = (px - rect.left()) / max(1.0, rect.width())
        rel = max(0.0, min(1.0, rel))
        return x_min + rel * (x_max - x_min)

    def _plot_rect(self) -> QRectF:
        return QRectF(32, 12, max(10, self.width() - 44), max(10, self.height() - 32))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self._plot_rect()

        # Background
        painter.fillRect(rect, QBrush(QColor("#ffffff")))
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.drawRect(rect)

        # Subtle grid lines
        painter.setPen(QPen(QColor("#f1f5f9"), 1, Qt.PenStyle.DashLine))
        y_mid = (self.y_min + self.y_max) / 2.0
        p_mid_l = self._val_to_pixel(self.factor.min_val, y_mid, rect)
        p_mid_r = self._val_to_pixel(self.factor.max_val, y_mid, rect)
        painter.drawLine(p_mid_l, p_mid_r)

        if not self.trace_data or not self.trace_data.get('xs'):
            painter.end()
            return

        xs = self.trace_data['xs']
        fits = self.trace_data['fits']
        ci_lows = self.trace_data.get('ci_low', [])
        ci_highs = self.trace_data.get('ci_high', [])

        # 1. Draw Confidence Interval shaded band if available
        if ci_lows and ci_highs and len(ci_lows) == len(xs) and all(l is not None and h is not None for l, h in zip(ci_lows, ci_highs)):
            ci_poly = QPolygonF()
            # Top edge
            for x, h in zip(xs, ci_highs):
                ci_poly.append(self._val_to_pixel(float(x), float(h), rect))
            # Bottom edge in reverse
            for x, l in reversed(list(zip(xs, ci_lows))):
                ci_poly.append(self._val_to_pixel(float(x), float(l), rect))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(37, 99, 235, 35)))  # Soft blue shading
            painter.drawPolygon(ci_poly)

        # 2. Draw Prediction trace curve
        path = QPainterPath()
        first = True
        for x, y in zip(xs, fits):
            if y is None or not math.isfinite(y):
                continue
            pt = self._val_to_pixel(float(x), float(y), rect)
            if first:
                path.moveTo(pt)
                first = False
            else:
                path.lineTo(pt)

        painter.setPen(QPen(QColor("#2563eb"), 2, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 3. Draw Horizontal Red Dashed Crosshair (current fit)
        if self.current_fit is not None and math.isfinite(self.current_fit):
            fit_pt = self._val_to_pixel(self.factor.min_val, self.current_fit, rect)
            painter.setPen(QPen(QColor("#dc2626"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(rect.left(), fit_pt.y()), QPointF(rect.right(), fit_pt.y()))

        # 4. Draw Vertical Red Dashed Crosshair (current factor value)
        curr_x = self.trace_data.get('current_x', self.factor.current_val)
        if isinstance(curr_x, (int, float)) and math.isfinite(curr_x):
            x_pt = self._val_to_pixel(float(curr_x), self.y_min, rect)
            painter.setPen(QPen(QColor("#dc2626"), 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(x_pt.x(), rect.top()), QPointF(x_pt.x(), rect.bottom()))

        # Axis tick labels
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        painter.setPen(QColor("#64748b"))

        # X min / max labels
        painter.drawText(QRectF(rect.left() - 10, rect.bottom() + 4, 40, 14), Qt.AlignmentFlag.AlignLeft, f"{self.factor.min_val:.3g}")
        painter.drawText(QRectF(rect.right() - 30, rect.bottom() + 4, 40, 14), Qt.AlignmentFlag.AlignRight, f"{self.factor.max_val:.3g}")

        # Y min / max labels
        painter.drawText(QRectF(2, rect.top() - 6, 28, 14), Qt.AlignmentFlag.AlignRight, f"{self.y_max:.3g}")
        painter.drawText(QRectF(2, rect.bottom() - 8, 28, 14), Qt.AlignmentFlag.AlignRight, f"{self.y_min:.3g}")

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            rect = self._plot_rect()
            if rect.contains(event.position()):
                self.is_dragging = True
                new_x = self._pixel_to_x_val(event.position().x(), rect)
                self.factorChanged.emit(self.factor.name, new_x)

    def mouseMoveEvent(self, event):
        rect = self._plot_rect()
        if self.is_dragging:
            new_x = self._pixel_to_x_val(event.position().x(), rect)
            self.factorChanged.emit(self.factor.name, new_x)
        else:
            # Change cursor if hovering near crosshair
            curr_x = self.trace_data.get('current_x', self.factor.current_val) if self.trace_data else self.factor.current_val
            if isinstance(curr_x, (int, float)):
                pt = self._val_to_pixel(float(curr_x), self.y_min, rect)
                if abs(event.position().x() - pt.x()) < 6 and rect.top() <= event.position().y() <= rect.bottom():
                    self.setCursor(Qt.CursorShape.SplitHCursor)
                else:
                    self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False


class PredictionProfilerDialog(QDialog):
    """JMP-style Interactive Multi-Model Prediction Profiler Dialog."""

    def __init__(self, parent, worksheet: Worksheet, model_recipes: list[dict[str, Any]]):
        super().__init__(parent)
        self.worksheet = worksheet
        self.model_recipes = [normalize_recipe(r) for r in model_recipes]

        self.setWindowTitle("StatCraft Interactive Prediction Profiler (JMP Compatibility Suite)")
        self.resize(880, 580)

        # Extract factors & responses
        self.factors, self.responses = extract_profiler_specs(self.worksheet, self.model_recipes)
        self.current_settings: dict[str, float | str] = {f.name: f.current_val for f in self.factors}
        self.confidence_level = 0.95

        self.cell_widgets: dict[tuple[str, str], ProfilerCellWidget] = {}
        self.spin_boxes: dict[str, QDoubleSpinBox] = {}
        self.response_labels: dict[str, QLabel] = {}

        self._build_ui()
        self.refresh_profiler()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Top Control Bar
        top_bar = QHBoxLayout()

        title_lbl = QLabel("<b>Prediction Profiler</b>")
        title_lbl.setStyleSheet("font-size: 14px; color: #1e293b;")
        top_bar.addWidget(title_lbl)

        top_bar.addSpacing(16)

        self.opt_btn = QPushButton("⚡ Maximize Desirability")
        self.opt_btn.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;")
        self.opt_btn.clicked.connect(self.on_maximize_desirability)
        top_bar.addWidget(self.opt_btn)

        self.reset_btn = QPushButton("↺ Reset Midpoints")
        self.reset_btn.setStyleSheet("padding: 5px 10px;")
        self.reset_btn.clicked.connect(self.on_reset_midpoints)
        top_bar.addWidget(self.reset_btn)

        top_bar.addSpacing(12)

        top_bar.addWidget(QLabel("Confidence:"))
        self.ci_combo = QComboBox()
        self.ci_combo.addItems(["90%", "95%", "99%"])
        self.ci_combo.setCurrentText("95%")
        self.ci_combo.currentTextChanged.connect(self.on_confidence_changed)
        top_bar.addWidget(self.ci_combo)

        top_bar.addStretch()

        self.desirability_lbl = QLabel("Composite Desirability D: <b>1.0000</b>")
        self.desirability_lbl.setStyleSheet("color: #0f766e; font-size: 12px;")
        top_bar.addWidget(self.desirability_lbl)

        main_layout.addLayout(top_bar)

        # Scroll Area for Grid of Plots
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(8)

        # Factor Column Headers
        for col_idx, factor in enumerate(self.factors, start=1):
            lbl = QLabel(f"<b>{factor.name}</b>")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #334155; font-size: 11px;")
            grid.addWidget(lbl, 0, col_idx)

        # Response Rows and Cells
        for row_idx, resp in enumerate(self.responses, start=1):
            # Left response summary panel
            resp_box = QWidget()
            vbox = QVBoxLayout(resp_box)
            vbox.setContentsMargins(4, 4, 4, 4)
            vbox.setSpacing(2)

            name_lbl = QLabel(f"<b>{resp.name}</b>")
            name_lbl.setStyleSheet("color: #1e293b; font-size: 11px;")
            vbox.addWidget(name_lbl)

            pred_lbl = QLabel("Fit: --")
            pred_lbl.setStyleSheet("color: #dc2626; font-weight: bold; font-size: 11px;")
            vbox.addWidget(pred_lbl)

            ci_lbl = QLabel("95% CI: [--, --]")
            ci_lbl.setStyleSheet("color: #64748b; font-size: 9px;")
            vbox.addWidget(ci_lbl)

            d_lbl = QLabel("d: 1.00")
            d_lbl.setStyleSheet("color: #059669; font-size: 10px;")
            vbox.addWidget(d_lbl)
            vbox.addStretch()

            self.response_labels[resp.name] = pred_lbl
            self.response_labels[f"{resp.name}_ci"] = ci_lbl
            self.response_labels[f"{resp.name}_d"] = d_lbl

            grid.addWidget(resp_box, row_idx, 0)

            # Factor Cells for this Response
            for col_idx, factor in enumerate(self.factors, start=1):
                cell = ProfilerCellWidget(factor, resp.name, self)
                cell.factorChanged.connect(self.on_factor_value_changed)
                self.cell_widgets[(resp.name, factor.name)] = cell
                grid.addWidget(cell, row_idx, col_idx)

        # Bottom Factor Input Controls
        bottom_row_idx = len(self.responses) + 1
        grid.addWidget(QLabel("<b>Settings:</b>"), bottom_row_idx, 0, Qt.AlignmentFlag.AlignRight)

        for col_idx, factor in enumerate(self.factors, start=1):
            box = QWidget()
            hbox = QHBoxLayout(box)
            hbox.setContentsMargins(2, 2, 2, 2)
            if factor.kind == 'number':
                spin = QDoubleSpinBox()
                spin.setRange(factor.min_val, factor.max_val)
                step = (factor.max_val - factor.min_val) / 20.0
                spin.setSingleStep(step if step > 0 else 0.1)
                spin.setDecimals(3)
                spin.setValue(float(factor.current_val))
                spin.valueChanged.connect(lambda val, f_name=factor.name: self.on_factor_value_changed(f_name, val))
                self.spin_boxes[factor.name] = spin
                hbox.addWidget(spin)
            else:
                lbl = QLabel(str(factor.current_val))
                lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hbox.addWidget(lbl)
            grid.addWidget(box, bottom_row_idx, col_idx)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Bottom Close Button
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        main_layout.addWidget(btn_box)

    def on_factor_value_changed(self, factor_name: str, new_val: float):
        """Handle factor value modification from either dragging or spinbox."""
        self.current_settings[factor_name] = new_val

        # Update spinbox without retriggering loop
        if factor_name in self.spin_boxes:
            sb = self.spin_boxes[factor_name]
            sb.blockSignals(True)
            sb.setValue(new_val)
            sb.blockSignals(False)

        self.refresh_profiler()

    def on_confidence_changed(self, text: str):
        mapping = {"90%": 0.90, "95%": 0.95, "99%": 0.99}
        self.confidence_level = mapping.get(text, 0.95)
        self.refresh_profiler()

    def on_reset_midpoints(self):
        for f in self.factors:
            if f.kind == 'number':
                mid = (f.min_val + f.max_val) / 2.0
                self.current_settings[f.name] = mid
                if f.name in self.spin_boxes:
                    self.spin_boxes[f.name].setValue(mid)
        self.refresh_profiler()

    def on_maximize_desirability(self):
        optimal = optimize_profiler_settings(
            self.worksheet, self.model_recipes, self.factors, self.responses
        )
        for f_name, opt_val in optimal.items():
            if isinstance(opt_val, (int, float)):
                self.current_settings[f_name] = opt_val
                if f_name in self.spin_boxes:
                    self.spin_boxes[f_name].setValue(opt_val)
        self.refresh_profiler()

    def refresh_profiler(self):
        """Recalculate prediction profiles and update all plot cells."""
        results = compute_prediction_profiles(
            self.worksheet,
            self.model_recipes,
            self.factors,
            self.current_settings,
            n_points=51,
            confidence=self.confidence_level
        )

        # Compute composite desirability
        resp_values = {resp_name: res['current_fit'] for resp_name, res in results.items()}
        comp_d, ind_d = compute_composite_desirability(resp_values, self.responses)
        self.desirability_lbl.setText(f"Composite Desirability D: <b>{comp_d:.4f}</b>")

        # Update each response row and cells
        for resp_name, res in results.items():
            curr_fit = res['current_fit']
            ci_low = res['current_ci_low']
            ci_high = res['current_ci_high']

            # Update left labels
            if resp_name in self.response_labels:
                fit_str = f"{curr_fit:.4g}" if curr_fit is not None else "--"
                self.response_labels[resp_name].setText(f"Fit: {fit_str}")

            if f"{resp_name}_ci" in self.response_labels:
                ci_str = f"[{ci_low:.3g}, {ci_high:.3g}]" if ci_low is not None and ci_high is not None else "[--, --]"
                self.response_labels[f"{resp_name}_ci"].setText(f"{int(self.confidence_level * 100)}% CI: {ci_str}")

            if f"{resp_name}_d" in self.response_labels:
                d_val = ind_d.get(resp_name, 1.0)
                self.response_labels[f"{resp_name}_d"].setText(f"d: {d_val:.4f}")

            # Compute shared Y-scale for this response row
            all_fits = []
            for trace in res['factor_traces'].values():
                all_fits.extend([y for y in trace['fits'] if y is not None and math.isfinite(y)])
                all_fits.extend([y for y in trace.get('ci_low', []) if y is not None and math.isfinite(y)])
                all_fits.extend([y for y in trace.get('ci_high', []) if y is not None and math.isfinite(y)])

            if all_fits:
                y_min = float(min(all_fits))
                y_max = float(max(all_fits))
                span = max(1e-6, y_max - y_min)
                y_min -= span * 0.08
                y_max += span * 0.08
            else:
                y_min, y_max = 0.0, 1.0

            # Update cells
            for factor_name, trace in res['factor_traces'].items():
                cell = self.cell_widgets.get((resp_name, factor_name))
                if cell:
                    cell.update_data(trace, curr_fit, y_min, y_max)
