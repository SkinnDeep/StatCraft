"""Verification gate for native StatCraft Time-Weighted Control Charts (EWMA, Moving Average, CUSUM)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .time_weighted_control_dialogs import TimeWeightedChartDialog, TimeWeightedOptionsDialog
from .time_weighted_control_chart import TimeWeightedControlChartWidget


def verify_time_weighted_control(app, p, w, temp, checkpoint):
    checkpoint("Time-Weighted Control Charts (Stat > Control Charts > Time-Weighted Charts > EWMA, Moving Average, CUSUM) native dialogs, reports, and chart widget")
    p.new()

    # Create test worksheet with subgroup measurements and intentional shift/spike
    # Subgroups of size 5
    measurements = [
        10.1, 9.8, 10.2, 10.0, 9.9,   # sg 1 mean ~10.0
        10.0, 10.3, 9.7, 10.1, 9.9,   # sg 2
        9.9, 10.1, 10.2, 10.0, 9.8,   # sg 3
        10.2, 10.0, 10.1, 9.9, 10.3,  # sg 4
        10.0, 9.8, 10.1, 10.2, 9.9,   # sg 5
        10.1, 10.0, 10.3, 9.8, 10.2,  # sg 6
        10.8, 11.2, 11.0, 10.9, 11.1, # sg 7 (Shift up!)
        11.5, 11.8, 11.2, 11.6, 11.4, # sg 8 (Sustained shift)
        11.3, 11.4, 11.6, 11.2, 11.5, # sg 9
        11.7, 11.9, 11.8, 11.6, 11.5, # sg 10
    ]
    subgroup_ids = [1]*5 + [2]*5 + [3]*5 + [4]*5 + [5]*5 + [6]*5 + [7]*5 + [8]*5 + [9]*5 + [10]*5

    # Multi-column data for row-of-columns test
    c1 = [10.1, 10.0, 9.9, 10.2, 10.0, 10.1, 10.8, 11.5, 11.3, 11.7]
    c2 = [9.8, 10.3, 10.1, 10.0, 9.8, 10.0, 11.2, 11.8, 11.4, 11.9]
    c3 = [10.2, 9.7, 10.2, 10.1, 10.1, 10.3, 11.0, 11.2, 11.6, 11.8]
    c4 = [10.0, 10.1, 10.0, 9.9, 10.2, 9.8, 10.9, 11.6, 11.2, 11.6]
    c5 = [9.9, 9.9, 9.8, 10.3, 9.9, 10.2, 11.1, 11.4, 11.5, 11.5]

    p.worksheet = Worksheet("TimeWeightedDemo", [
        Column("Measurements", "number", measurements),
        Column("SubgroupID", "number", subgroup_ids),
        Column("C1", "number", c1),
        Column("C2", "number", c2),
        Column("C3", "number", c3),
        Column("C4", "number", c4),
        Column("C5", "number", c5),
    ])
    w.page = 0
    w.refresh()

    # -------------------------------------------------------------
    # 1. EWMA Chart Dialog & Execution
    # -------------------------------------------------------------
    dlg_ewma = TimeWeightedChartDialog(p.worksheet, chart_type="EWMA", parent=w)
    dlg_ewma.edit_var.setText("Measurements")
    dlg_ewma.edit_subgroup.setText("SubgroupID")
    dlg_ewma.edit_param.setText("0.2")

    # Options subdialog
    opt_ewma = TimeWeightedOptionsDialog("EWMA", dlg_ewma.options, parent=dlg_ewma)
    opt_ewma.edit_k.setText("3.0")
    opt_ewma._save_and_accept()
    dlg_ewma.options = opt_ewma.options

    dlg_ewma._on_ok()
    cfg_ewma = dlg_ewma.get_configuration()
    assert cfg_ewma["chart_type"] == "EWMA"
    assert cfg_ewma["columns"] == ["Measurements"]

    entry_ewma = p.time_weighted_control_chart(settings=cfg_ewma)
    assert entry_ewma is not None
    assert entry_ewma["recipe"]["action"] == "time_weighted_control_chart"
    res_ewma = entry_ewma["result"]
    assert res_ewma["analysis"] == "time_weighted_control"
    assert res_ewma["chart_type"] == "EWMA"
    assert res_ewma["k_subgroups"] == 10
    assert len(res_ewma["values"]) == 10
    # Because of shift starting at sg 7, later subgroups should signal out of control
    assert len(res_ewma["signals"]) > 0
    # Dynamic control limits expand
    assert res_ewma["ucl"][0] < res_ewma["ucl"][9]

    # Report verification
    rep_ewma = format_entry(entry_ewma)
    assert "EWMA Chart of Measurements" in rep_ewma
    assert "Weight of EWMA:" in rep_ewma
    assert "Test 1: One point beyond control limits." in rep_ewma

    # Widget render verification
    widget_ewma = TimeWeightedControlChartWidget(entry_ewma)
    img_ewma = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_ewma.fill(Qt.GlobalColor.white)
    widget_ewma.render(img_ewma)
    assert not img_ewma.isNull()

    # -------------------------------------------------------------
    # 2. Moving Average Chart Dialog & Execution
    # -------------------------------------------------------------
    dlg_ma = TimeWeightedChartDialog(p.worksheet, chart_type="MA", parent=w)
    dlg_ma.edit_var.setText("Measurements")
    dlg_ma.edit_subgroup.setText("5")
    dlg_ma.edit_param.setText("3")
    dlg_ma._on_ok()
    cfg_ma = dlg_ma.get_configuration()
    assert cfg_ma["chart_type"] == "MA"
    assert cfg_ma["span"] == 3

    entry_ma = p.time_weighted_control_chart(settings=cfg_ma)
    assert entry_ma is not None
    res_ma = entry_ma["result"]
    assert res_ma["chart_type"] == "MA"
    assert res_ma["k_subgroups"] == 10
    assert len(res_ma["signals"]) > 0

    rep_ma = format_entry(entry_ma)
    assert "Moving Average Chart of Measurements" in rep_ma
    assert "Length of MA (Span): 3" in rep_ma

    widget_ma = TimeWeightedControlChartWidget(entry_ma)
    img_ma = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_ma.fill(Qt.GlobalColor.white)
    widget_ma.render(img_ma)
    assert not img_ma.isNull()

    # -------------------------------------------------------------
    # 3. CUSUM Chart Dialog & Execution
    # -------------------------------------------------------------
    dlg_cusum = TimeWeightedChartDialog(p.worksheet, chart_type="CUSUM", parent=w)
    dlg_cusum.edit_var.setText("Measurements")
    dlg_cusum.edit_subgroup.setText("5")
    dlg_cusum.edit_param.setText("10.0")  # Target 10.0

    opt_cusum = TimeWeightedOptionsDialog("CUSUM", dlg_cusum.options, parent=dlg_cusum)
    opt_cusum.chk_fir.setChecked(True)
    opt_cusum.edit_fir.setText("2.0")
    opt_cusum._save_and_accept()
    dlg_cusum.options = opt_cusum.options

    dlg_cusum._on_ok()
    cfg_cusum = dlg_cusum.get_configuration()
    assert cfg_cusum["chart_type"] == "CUSUM"

    entry_cusum = p.time_weighted_control_chart(settings=cfg_cusum)
    assert entry_cusum is not None
    res_cusum = entry_cusum["result"]
    assert res_cusum["chart_type"] == "CUSUM"
    assert res_cusum["h"] == 4.0
    assert res_cusum["k"] == 0.5
    assert len(res_cusum["c_plus"]) == 10
    assert len(res_cusum["c_minus"]) == 10
    assert len(res_cusum["signals"]) > 0

    rep_cusum = format_entry(entry_cusum)
    assert "CUSUM Chart of Measurements" in rep_cusum
    assert "h (Decision Int):" in rep_cusum
    assert "FIR (Headstart):" in rep_cusum

    widget_cusum = TimeWeightedControlChartWidget(entry_cusum)
    img_cusum = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_cusum.fill(Qt.GlobalColor.white)
    widget_cusum.render(img_cusum)
    assert not img_cusum.isNull()

    # -------------------------------------------------------------
    # 4. Row of columns arrangement test (C1..C5)
    # -------------------------------------------------------------
    cfg_row = {
        "chart_type": "EWMA",
        "arranged_mode": 1,
        "columns": ["C1", "C2", "C3", "C4", "C5"],
        "weight": 0.2,
        "options": {},
    }
    entry_row = p.time_weighted_control_chart(settings=cfg_row)
    assert entry_row is not None
    res_row = entry_row["result"]
    assert res_row["k_subgroups"] == 10
    assert all(s == 5 for s in res_row["subgroup_sizes"])

    # -------------------------------------------------------------
    # 5. Project save, load, and MPX recipe reproduction
    # -------------------------------------------------------------
    proj_path = Path(temp) / "time_weighted_verify.mpx"
    p.save(proj_path)
    assert proj_path.exists() and proj_path.stat().st_size > 0

    p2 = Presenter()
    p2.load(proj_path)
    assert len(p2.history) >= 4
    last_act = p2.history[-1]["recipe"]["action"]
    assert last_act == "time_weighted_control_chart"

    # Save verification snapshot
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.exists():
                out_dir = candidate
                break

    if out_dir.exists():
        snap_path = out_dir / "StatCraft-time-weighted-control-chart.png"
        img_ewma.save(str(snap_path))
