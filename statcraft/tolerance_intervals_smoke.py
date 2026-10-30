"""Verification gate for native StatCraft Tolerance Intervals (Stat > Quality Tools > Tolerance Intervals)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .tolerance_intervals_dialogs import ToleranceIntervalsDialog
from .tolerance_intervals_chart import ToleranceIntervalChartWidget


def verify_tolerance_intervals(app, p, w, temp, checkpoint):
    checkpoint("Tolerance Intervals (Stat > Quality Tools > Tolerance Intervals) native dialog, reports, and interval chart widget")
    p.new()

    # 40 tensile strength measurements
    strength_data = [
        102.5, 98.4, 105.1, 99.8, 101.2, 103.7, 97.9, 104.5, 100.3, 102.1,
        106.0, 99.1, 101.8, 103.2, 98.7, 105.4, 102.0, 100.9, 104.1, 101.5,
        103.0, 99.5, 102.8, 100.6, 105.8, 101.9, 98.2, 103.9, 102.4, 101.0,
        104.8, 100.1, 102.7, 103.5, 99.3, 105.0, 101.7, 102.9, 100.5, 104.2,
    ]

    p.worksheet = Worksheet("StrengthStudy", [
        Column("Strength", "number", strength_data),
    ])
    w.page = 0
    w.refresh()

    # -------------------------------------------------------------
    # 1. Raw Data Mode Dialog & Execution
    # -------------------------------------------------------------
    dlg_raw = ToleranceIntervalsDialog(p.worksheet, initial_vars=["Strength"], parent=w)
    dlg_raw.combo_arrange.setCurrentIndex(0)
    dlg_raw.edit_vars.setText("Strength")
    dlg_raw.edit_min_pct.setText("90.0")
    dlg_raw.options = {
        "conf_level": 95.0,
        "interval_type": "two_sided",
    }
    dlg_raw.show_graphs = True

    dlg_raw._validate_and_accept()
    params_raw = dlg_raw.result_params
    assert params_raw is not None
    assert not params_raw["is_summarized"]
    assert params_raw["variable_indices"] == [0]
    assert params_raw["settings"]["min_percent"] == 90.0
    assert params_raw["settings"]["conf_level"] == 95.0

    entry_raw = p.tolerance_intervals(settings=params_raw)
    assert entry_raw is not None
    assert entry_raw["recipe"]["action"] == "tolerance_intervals"
    res_raw = entry_raw["result"]
    assert res_raw["analysis"] == "tolerance_intervals"
    assert res_raw["n"] == 40
    assert not res_raw["is_summarized"]
    assert res_raw["k"] > 1.5
    assert res_raw["normal_lower"] < res_raw["mean"] < res_raw["normal_upper"]
    assert res_raw["nonparametric"] is not None
    assert res_raw["nonparametric"]["lower"] == min(strength_data)
    assert res_raw["nonparametric"]["upper"] == max(strength_data)

    rep_raw = format_entry(entry_raw)
    assert "Tolerance Intervals (Normal Distribution)" in rep_raw
    assert "Strength" in rep_raw
    assert "Descriptive Statistics" in rep_raw
    assert "Normal Method" in rep_raw
    assert "Nonparametric Method" in rep_raw

    widget_raw = ToleranceIntervalChartWidget(entry_raw)
    img_raw = QImage(QSize(860, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_raw.fill(Qt.GlobalColor.white)
    widget_raw.render(img_raw)
    assert not img_raw.isNull()

    artifact_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    if artifact_dir.exists():
        img_raw.save(str(artifact_dir / "StatCraft-tolerance-intervals.png"))

    # -------------------------------------------------------------
    # 2. Summarized Data Mode Dialog & Execution
    # -------------------------------------------------------------
    dlg_summ = ToleranceIntervalsDialog(p.worksheet, parent=w)
    dlg_summ.combo_arrange.setCurrentIndex(1)
    dlg_summ._on_arrange_changed(1)
    dlg_summ.edit_n.setText("100")
    dlg_summ.edit_mean.setText("50.0")
    dlg_summ.edit_std.setText("4.0")
    dlg_summ.edit_min_pct.setText("95.0")
    dlg_summ.options = {
        "conf_level": 99.0,
        "interval_type": "two_sided",
    }

    dlg_summ._validate_and_accept()
    params_summ = dlg_summ.result_params
    assert params_summ is not None
    assert params_summ["is_summarized"]
    assert params_summ["n"] == 100
    assert params_summ["mean"] == 50.0
    assert params_summ["std"] == 4.0

    entry_summ = p.tolerance_intervals(settings=params_summ)
    assert entry_summ is not None
    res_summ = entry_summ["result"]
    assert res_summ["analysis"] == "tolerance_intervals"
    assert res_summ["n"] == 100
    assert res_summ["is_summarized"]
    assert res_summ["nonparametric"] is None
    assert res_summ["normal_lower"] < 50.0 < res_summ["normal_upper"]

    rep_summ = format_entry(entry_summ)
    assert "Tolerance Intervals (Normal Distribution)" in rep_summ
    assert "Summarized Data" in rep_summ
    assert "Nonparametric interval not available for summarized data" in rep_summ

    checkpoint("Tolerance Intervals verification passed successfully")
