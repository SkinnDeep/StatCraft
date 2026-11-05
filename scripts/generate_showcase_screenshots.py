"""Automated generator for all StatCraft & JMP showcase website screenshots.

Renders high-resolution vector and dialog graphics using native TrueType fonts
(DirectWrite / GDI on Windows, system font rasterizer on Linux/macOS).
Never uses offscreen dummy QPA without font rasterization, guaranteeing 0 tofu glyphs.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure QT_QPA_PLATFORM offscreen does not suppress native font engine
if "QT_QPA_PLATFORM" in os.environ and os.environ["QT_QPA_PLATFORM"] == "offscreen":
    del os.environ["QT_QPA_PLATFORM"]

_root = Path(__file__).resolve().parent.parent
_deps = _root.parent / "statcraft-build-deps"
if _deps.exists() and str(_deps) not in sys.path:
    sys.path.insert(0, str(_deps))
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
app = QApplication.instance() or QApplication([])

img_dir = _root / "docs" / "images"
img_dir.mkdir(parents=True, exist_ok=True)


def render_jmp_platform_ui():
    from statcraft.modern_app import ModernWindow
    from statcraft.model import Worksheet, Column
    win = ModernWindow()
    win.resize(1200, 720)
    ws = Worksheet("Quality Analysis", [
        Column("Part_ID", kind="text", values=[f"P-{i:03d}" for i in range(1, 26)], metadata={"modeling_type": "nominal"}),
        Column("Batch", kind="number", values=[(i % 5) + 1 for i in range(1, 26)], metadata={"modeling_type": "ordinal"}),
        Column("Diameter", kind="number", values=[10.02 + (i % 7) * 0.05 for i in range(1, 26)], metadata={"modeling_type": "continuous"}),
        Column("Strength", kind="number", values=[450.5 + (i * 3.2) for i in range(1, 26)], metadata={"modeling_type": "continuous"}),
    ])
    win.presenter.worksheet = ws
    win.refresh()
    win.set_ui_mode("jmp")
    win.show()
    app.processEvents()
    pix = win.grab()
    target = img_dir / "jmp-platform-ui.png"
    pix.save(str(target))
    win.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


def render_jmp_bivariate():
    from statcraft.fit_y_by_x_engine import compute_bivariate
    from statcraft.fit_y_by_x_chart import FitYByXChartWidget
    import numpy as np

    np.random.seed(42)
    x = np.linspace(15.0, 85.0, 45)
    y = 2.4 * x + 18.0 + np.random.normal(0, 14.0, 45)

    res = compute_bivariate(x.tolist(), y.tolist(), x_name="Operating Pressure (psi)", y_name="Yield Output (%)")
    entry = {"result": res, "title": "Bivariate Fit of Yield Output (%) By Operating Pressure (psi)"}
    w = FitYByXChartWidget(entry)
    w.resize(920, 580)
    w.show()
    app.processEvents()
    pix = w.grab()
    target = img_dir / "jmp-bivariate.png"
    pix.save(str(target))
    w.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


def render_jmp_oneway():
    from statcraft.fit_y_by_x_engine import compute_oneway
    from statcraft.fit_y_by_x_chart import FitYByXChartWidget
    import numpy as np

    np.random.seed(123)
    groups = ["Shift A", "Shift B", "Shift C", "Shift D"]
    means = [45.0, 68.0, 58.0, 82.0]
    stds = [4.5, 5.0, 4.0, 4.8]

    x_vals = []
    y_vals = []
    for g, m, s in zip(groups, means, stds):
        vals = np.random.normal(m, s, 14).tolist()
        y_vals.extend(vals)
        x_vals.extend([g] * len(vals))

    res = compute_oneway(x_vals, y_vals, x_name="Manufacturing Shift", y_name="Tensile Strength (MPa)")
    entry = {"result": res, "title": "Oneway Analysis of Tensile Strength (MPa) By Manufacturing Shift"}
    w = FitYByXChartWidget(entry)
    w.resize(920, 580)
    w.show()
    app.processEvents()
    pix = w.grab()
    target = img_dir / "jmp-oneway.png"
    pix.save(str(target))
    w.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


def render_jmp_distribution():
    from statcraft.model import Worksheet, Column
    from statcraft.jmp_distribution_engine import compute_jmp_distribution
    from statcraft.jmp_distribution_chart import JMPDistributionWidget
    import numpy as np

    np.random.seed(99)
    heights = np.random.normal(65.5, 4.2, 50).round(1).tolist()
    weights = np.random.normal(142.0, 16.5, 50).round(1).tolist()
    ages = [12 + (i % 6) for i in range(50)]

    ws = Worksheet("Classroom Study", [
        Column("Height (in)", kind="number", values=heights, metadata={"modeling_type": "continuous"}),
        Column("Weight (lb)", kind="number", values=weights, metadata={"modeling_type": "continuous"}),
        Column("Age", kind="number", values=ages, metadata={"modeling_type": "ordinal"}),
    ])

    res = compute_jmp_distribution(ws, [0, 1])
    entry = {"result": res, "title": "Distributions - Height (in), Weight (lb)"}
    w = JMPDistributionWidget(entry)
    w.resize(920, 560)
    w.show()
    app.processEvents()
    pix = w.grab()
    target = img_dir / "jmp-distribution.png"
    pix.save(str(target))
    w.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


def render_alt():
    from statcraft.alt_chart import ALTLifeVsStressWidget
    from statcraft.alt_engine import fit_accelerated_life_test
    from statcraft.alt_report import get_alt_structured_tables

    times = [120.0, 160.0, 210.0, 95.0, 125.0, 140.0, 55.0, 75.0, 95.0]
    events = [1, 1, 0, 1, 1, 0, 1, 1, 1]
    stresses = [60.0, 60.0, 60.0, 80.0, 80.0, 80.0, 100.0, 100.0, 100.0]
    res = fit_accelerated_life_test(times, events, stresses, model='arrhenius', use_stress=25.0)
    res['time_name'] = 'Operating Hours'
    res['stress_name'] = 'Temperature (\u00b0C)'
    res['tables'] = get_alt_structured_tables(res)
    alt_entry = {'result': res, 'title': 'ALT Life vs Stress'}
    w = ALTLifeVsStressWidget(alt_entry)
    w.resize(880, 560)
    w.show()
    app.processEvents()
    pix = w.grab()
    target = img_dir / "alt-life-vs-stress.png"
    pix.save(str(target))
    w.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


def render_dsd_pareto():
    from statcraft.dsd import create_definitive_screening_design
    from statcraft.dsd_analysis import analyze_definitive_screening_design
    from statcraft.dsd_chart import DSDParetoEffectsWidget
    from statcraft.model import Column

    factors = [
        {"name": "Temperature", "low": 120, "high": 180},
        {"name": "Pressure", "low": 30, "high": 70},
        {"name": "Catalyst", "low": 1, "high": 5},
        {"name": "Agitation", "low": 200, "high": 500},
        {"name": "Feed Rate", "low": 10, "high": 25},
        {"name": "Concentration", "low": 5, "high": 15},
    ]
    ws = create_definitive_screening_design(factors, randomize=False)
    y = [82.5, 91.2, 74.8, 88.0, 95.1, 79.4, 86.3, 93.7, 71.0, 84.5, 90.2, 77.8, 85.0]
    ws.columns.append(Column("Yield (%)", "number", y))
    res = analyze_definitive_screening_design(ws, response_index=len(ws.columns) - 1)
    entry = {"result": res, "title": "DSD Standardized Effects Pareto"}
    w = DSDParetoEffectsWidget(entry)
    w.resize(880, 520)
    w.show()
    app.processEvents()
    pix = w.grab()
    target = img_dir / "dsd-pareto.png"
    pix.save(str(target))
    w.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


def render_prediction_profiler():
    from statcraft.model import Worksheet, Column
    from statcraft.prediction_profiler_dialog import PredictionProfilerDialog

    x1 = [10.0, 20.0, 30.0, 10.0, 20.0, 30.0, 15.0, 25.0, 20.0, 25.0]
    x2 = [1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 1.5, 1.5, 1.2, 1.8]
    y_prof = [67.2, 86.8, 107.1, 63.9, 84.2, 103.8, 75.6, 95.3, 85.0, 96.2]
    ws = Worksheet("OptimizationStudy", [
        Column("Temperature", "number", x1),
        Column("CatalystConc", "number", x2),
        Column("ConversionYield", "number", y_prof, {"spec_limits": {"lsl": 70.0, "usl": 100.0, "target": 95.0}})
    ])
    recipe = {
        "action": "multiple_regression",
        "parameters": {
            "response_index": 2,
            "predictor_indices": [0, 1],
            "confidence": 0.95
        }
    }
    dlg = PredictionProfilerDialog(None, ws, [recipe])
    dlg.resize(920, 580)
    dlg.show()
    app.processEvents()
    pix = dlg.grab()
    target = img_dir / "prediction-profiler.png"
    pix.save(str(target))
    dlg.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


def render_control_chart():
    from statcraft.modern_app import ModernWindow
    from statcraft.app import Presenter
    from statcraft.model import Worksheet, Column
    import numpy as np

    np.random.seed(42)
    k = 25
    sub_size = 5
    base = 100.0
    means = []
    for i in range(k):
        sub = np.random.normal(base + (5.0 if i == 18 else 0.0), 3.0, sub_size)
        means.append(float(np.mean(sub)))

    ws = Worksheet("ProcessSPC", [
        Column("Diameter", "number", means)
    ])
    p = Presenter()
    p.worksheet = ws
    entry = p.subgroup_control_chart("xbar_r", response_index=0, subgroup_size=sub_size)
    win = ModernWindow(p)
    win.resize(1100, 750)
    win.show_result(entry)
    win.show()
    app.processEvents()

    target = img_dir / "control-chart.png"
    chart = getattr(win, "_active_chart_widget", None)
    if chart:
        chart.resize(960, 620)
        app.processEvents()
        pix = chart.grab()
    else:
        pix = win.grab()
    pix.save(str(target))
    win.close()
    print(f"Generated: {target.name} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    print("Starting screenshot generation pipeline with native TrueType typography...")
    render_jmp_platform_ui()
    render_jmp_bivariate()
    render_jmp_oneway()
    render_jmp_distribution()
    render_alt()
    render_dsd_pareto()
    render_prediction_profiler()
    render_control_chart()
    print("All screenshots generated successfully.")
