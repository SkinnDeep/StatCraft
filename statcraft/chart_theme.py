"""Shared Dark/Light chart theming utilities and QPainter adapter for StatCraft."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


@dataclass(frozen=True)
class ChartTheme:
    dark: bool
    bg: str
    panel_bg: str
    card_bg: str
    plot_bg: str
    ink: str
    muted: str
    border: str
    grid: str
    accent_blue: str
    accent_red: str
    accent_green: str
    callout_bg: str
    callout_border: str


LIGHT_THEME = ChartTheme(
    dark=False,
    bg="#ffffff",
    panel_bg="#fcfdfd",
    card_bg="#ffffff",
    plot_bg="#ffffff",
    ink="#1e293b",
    muted="#64748b",
    border="#cbd5e1",
    grid="#e2e8f0",
    accent_blue="#0369a1",
    accent_red="#dc2626",
    accent_green="#1b7837",
    callout_bg="#f8fafc",
    callout_border="#cbd5e1",
)

DARK_THEME = ChartTheme(
    dark=True,
    bg="#18181b",
    panel_bg="#1f1f23",
    card_bg="#1f1f23",
    plot_bg="#18181b",
    ink="#f4f4f5",
    muted="#a1a1aa",
    border="#3f3f46",
    grid="#27272a",
    accent_blue="#38bdf8",
    accent_red="#f87171",
    accent_green="#34d399",
    callout_bg="#27272a",
    callout_border="#3f3f46",
)


def is_dark_mode(widget: Optional[QWidget] = None) -> bool:
    """Detect whether Dark Mode is active for a chart or child widget."""
    cur = widget
    while cur is not None:
        if hasattr(cur, "_dark_mode"):
            return bool(getattr(cur, "_dark_mode"))
        parent = cur.parentWidget() if hasattr(cur, "parentWidget") else None
        if parent is None and hasattr(cur, "window"):
            win = cur.window()
            if win is not cur:
                cur = win
                continue
        cur = parent
    app = QApplication.instance()
    if app is not None:
        for top in app.topLevelWidgets():
            if hasattr(top, "_dark_mode"):
                return bool(getattr(top, "_dark_mode"))
        pal_bg = app.palette().window().color()
        if pal_bg.isValid() and pal_bg.lightness() < 128:
            return True
    return False


def get_chart_theme(widget: Optional[QWidget] = None) -> ChartTheme:
    return DARK_THEME if is_dark_mode(widget) else LIGHT_THEME


_LIGHT_HEX_MAP = {
    # Pure whites / canvases -> dark zinc canvas
    "#ffffff": "#18181b",
    "#fcfdfd": "#1f1f23",
    "#fafafa": "#1f1f23",
    "#f8fafc": "#1f1f23",
    "#f8f9fa": "#1f1f23",
    "#f1f5f9": "#27272a",
    "#f3f4f6": "#27272a",
    # Light borders / gridlines -> muted slate borders
    "#e8ecef": "#27272a",
    "#e5e7eb": "#27272a",
    "#e2e8f0": "#2e2e36",
    "#e0e0e0": "#3f3f46",
    "#d4d4d4": "#3f3f46",
    "#d9d9d9": "#3f3f46",
    "#ced6dc": "#3f3f46",
    "#cbd5e1": "#3f3f46",
    "#c6cfd6": "#3f3f46",
    # Dark ink -> bright zinc text
    "#000000": "#f4f4f5",
    "#0f172a": "#f4f4f5",
    "#111827": "#f4f4f5",
    "#1a2b38": "#f4f4f5",
    "#1e293b": "#f4f4f5",
    "#202020": "#f4f4f5",
    "#232a30": "#f4f4f5",
    "#263440": "#f4f4f5",
    "#333333": "#e4e4e7",
    "#334155": "#e4e4e7",
    # Muted labels -> light zinc muted
    "#475569": "#cbd5e1",
    "#555555": "#a1a1aa",
    "#5b6b77": "#a1a1aa",
    "#5e6d78": "#a1a1aa",
    "#64748b": "#a1a1aa",
    "#666666": "#a1a1aa",
    "#697884": "#a1a1aa",
    # Deep blues -> vivid sky blue so text/axes remain readable on #18181b
    "#1e3a8a": "#60a5fa",
    "#1e40af": "#60a5fa",
    "#0061a8": "#38bdf8",
    "#0369a1": "#38bdf8",
    "#056eb2": "#38bdf8",
}


def remap_dark_color(color: QColor, role: str = "any") -> QColor:
    """Map light-chart neutral & deep-ink colors cleanly for Dark Mode while preserving hue."""
    if not isinstance(color, QColor):
        color = QColor(color)
    if not color.isValid():
        return color
    alpha = color.alpha()
    hex6 = f"#{color.red():02x}{color.green():02x}{color.blue():02x}".lower()
    mapped = _LIGHT_HEX_MAP.get(hex6)
    if mapped is not None:
        out = QColor(mapped)
        out.setAlpha(alpha)
        return out
    r, g, b = color.red(), color.green(), color.blue()
    # Low-saturation neutrals not in exact map
    max_c, min_c = max(r, g, b), min(r, g, b)
    if max_c - min_c <= 22:
        lum = (r + g + b) / 3.0
        if role == "brush" and lum >= 235:
            return QColor(24, 24, 27, alpha)
        if lum >= 220:
            return QColor(39, 39, 42, alpha)
        if lum <= 65:
            return QColor(244, 244, 245, alpha)
        if lum <= 135:
            return QColor(161, 161, 170, alpha)
    return color


class _DarkQPainter(QPainter):
    """QPainter wrapper that translates hardcoded light-theme colors into dark-mode equivalents."""

    def __init__(self, *args):
        super().__init__(*args)
        if self.isActive():
            super().setPen(QColor(DARK_THEME.ink))

    def fillRect(self, *args):  # type: ignore[override]
        if args and isinstance(args[-1], (QColor, Qt.GlobalColor)):
            col = QColor(args[-1])
            mapped = remap_dark_color(col, role="brush")
            if len(args) == 2:
                return super().fillRect(args[0], mapped)
            if len(args) == 5:
                return super().fillRect(args[0], args[1], args[2], args[3], mapped)
        elif args and isinstance(args[-1], QBrush):
            b = QBrush(args[-1])
            if b.style() != Qt.BrushStyle.NoBrush:
                b.setColor(remap_dark_color(b.color(), role="brush"))
            if len(args) == 2:
                return super().fillRect(args[0], b)
            if len(args) == 5:
                return super().fillRect(args[0], args[1], args[2], args[3], b)
        return super().fillRect(*args)

    def setPen(self, pen):  # type: ignore[override]
        if isinstance(pen, QPen):
            if pen.style() != Qt.PenStyle.NoPen:
                c = remap_dark_color(pen.color(), role="pen")
                if c != pen.color():
                    p2 = QPen(pen)
                    p2.setColor(c)
                    return super().setPen(p2)
        elif isinstance(pen, (QColor, Qt.GlobalColor)):
            return super().setPen(remap_dark_color(QColor(pen), role="pen"))
        return super().setPen(pen)

    def setBrush(self, brush):  # type: ignore[override]
        if isinstance(brush, QBrush):
            if brush.style() != Qt.BrushStyle.NoBrush:
                c = remap_dark_color(brush.color(), role="brush")
                if c != brush.color():
                    b2 = QBrush(brush)
                    b2.setColor(c)
                    return super().setBrush(b2)
        elif isinstance(brush, (QColor, Qt.GlobalColor)):
            return super().setBrush(remap_dark_color(QColor(brush), role="brush"))
        elif isinstance(brush, Qt.BrushStyle):
            return super().setBrush(brush)
        return super().setBrush(brush)

    def fillPath(self, path, brush):  # type: ignore[override]
        if isinstance(brush, QBrush):
            if brush.style() != Qt.BrushStyle.NoBrush:
                b2 = QBrush(brush)
                b2.setColor(remap_dark_color(brush.color(), role="brush"))
                return super().fillPath(path, b2)
        elif isinstance(brush, (QColor, Qt.GlobalColor)):
            return super().fillPath(path, remap_dark_color(QColor(brush), role="brush"))
        return super().fillPath(path, brush)


def chart_painter(widget: QWidget, device=None) -> QPainter:
    """Create a theme-aware QPainter for `widget` (or optional paint device)."""
    target = device if device is not None else widget
    if is_dark_mode(widget):
        return _DarkQPainter(target)
    return QPainter(target)


def resolve_axis_label(chart: QWidget, axis: str, default: str) -> str:
    """Honor GraphOptionsPane custom axis label and Off/Low/High position."""
    positions = getattr(chart, "annotation_positions", {}) or {}
    if positions.get(axis) == "off":
        return ""
    axes = getattr(chart, "annotation_axes", {}) or {}
    return str(axes.get(axis, default))


def apply_axis_limits(chart: QWidget, axis: str, low: float, high: float) -> tuple[float, float]:
    """Honor GraphOptionsPane X/Y min and max limits when both finite bounds are set."""
    limits = (getattr(chart, "annotation_limits", {}) or {}).get(axis)
    if limits and len(limits) == 2 and limits[0] is not None and limits[1] is not None:
        lo, hi = float(limits[0]), float(limits[1])
        if hi > lo:
            return lo, hi
    return low, high


def grid_enabled(chart: QWidget) -> bool:
    """Return whether major gridlines should be painted for `chart`."""
    return bool(getattr(chart, "annotation_grid", True))


def draw_ref_lines(
    painter: QPainter,
    chart: QWidget,
    plot_rect: QRectF,
    to_x,
    to_y,
    x_bounds: tuple[float, float],
    y_bounds: tuple[float, float],
) -> None:
    """Draw GraphOptionsPane vertical (X) and horizontal (Y) reference lines."""
    x_refs = getattr(chart, "annotation_x_ref", None) or []
    y_refs = getattr(chart, "annotation_y_ref", None) or []
    if not x_refs and not y_refs:
        return
    painter.save()
    painter.setPen(QPen(QColor("#7c3aed"), 1.3, Qt.PenStyle.DashDotLine))
    x_lo, x_hi = min(x_bounds), max(x_bounds)
    y_lo, y_hi = min(y_bounds), max(y_bounds)
    for xv in x_refs:
        if x_lo <= xv <= x_hi:
            px = to_x(xv)
            painter.drawLine(int(round(px)), int(round(plot_rect.top())), int(round(px)), int(round(plot_rect.bottom())))
    for yv in y_refs:
        if y_lo <= yv <= y_hi:
            py = to_y(yv)
            painter.drawLine(int(round(plot_rect.left())), int(round(py)), int(round(plot_rect.right())), int(round(py)))
    painter.restore()
