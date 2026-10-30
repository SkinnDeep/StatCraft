"""Verification gate for native StatCraft Rare Event Control Charts (G Chart & T Chart)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .rare_event_control_dialogs import RareEventChartDialog, RareEventOptionsDialog
from .rare_event_control_chart import RareEventControlChartWidget


def verify_rare_event_control(app, p, w, temp, checkpoint):
    checkpoint("Rare Event Control Charts (Stat > Control Charts > Rare Event Charts > G, T) native dialogs, reports, and chart widget")
    p.new()

    # Create test worksheet with counts between events and time intervals
    # Opportunities between events with a spike and a run of zeros (Benneyan)
    g_counts = [12, 15, 8, 14, 11, 150, 10, 13, 0, 0, 0, 9, 12, 14, 11]  # 150 is spike; 0,0,0 is Benneyan
    t_intervals = [3.5, 4.2, 2.8, 5.1, 3.9, 18.2, 4.0, 3.8, 0.2, 0.1, 0.15, 3.7, 4.5, 3.9, 4.1]
    event_dates = [
        "2026-01-01", "2026-01-05", "2026-01-09", "2026-01-12", "2026-01-18",
        "2026-01-22", "2026-02-15", "2026-02-19", "2026-02-23", "2026-02-24",
        "2026-02-25", "2026-02-26", "2026-03-02", "2026-03-06", "2026-03-10",
    ]

    p.worksheet = Worksheet("RareEventDemo", [
        Column("Opportunities", "number", g_counts),
        Column("TimeBetween", "number", t_intervals),
        Column("EventDates", "text", event_dates),
    ])
    w.page = 0
    w.refresh()

    # -------------------------------------------------------------
    # 1. G Chart Dialog & Execution
    # -------------------------------------------------------------
    dlg_g = RareEventChartDialog(p.worksheet, chart_type="G", parent=w)
    dlg_g.edit_var.setText("Opportunities")
    dlg_g.combo_form.setCurrentIndex(1)  # Opportunities
    dlg_g.combo_method.setCurrentIndex(0)  # Between events

    opt_g = RareEventOptionsDialog("G", dlg_g.options, parent=dlg_g)
    opt_g.chk_test1.setChecked(True)
    opt_g.chk_benneyan.setChecked(True)
    opt_g.edit_b_thresh.setText("3")
    opt_g._save_and_accept()
    dlg_g.options = opt_g.options

    dlg_g._on_ok()
    cfg_g = dlg_g.get_configuration()
    assert cfg_g["chart_type"] == "G"
    assert cfg_g["columns"] == ["Opportunities"]

    entry_g = p.rare_event_control_chart(settings=cfg_g)
    assert entry_g is not None
    assert entry_g["recipe"]["action"] == "rare_event_control_chart"
    res_g = entry_g["result"]
    assert res_g["analysis"] == "rare_event_control"
    assert res_g["chart_type"] == "G"
    assert res_g["k_subgroups"] == 15
    assert res_g["center_line"] > 0
    assert res_g["ucl_val"] > res_g["center_line"]
    # Point 6 (value 45) should trigger Test 1
    assert 6 in res_g["test1_signals"]
    # Points 10 and 11 should trigger Benneyan test (after 3 consecutive 0s)
    assert len(res_g["benneyan_signals"]) > 0

    # Report verification
    rep_g = format_entry(entry_g)
    assert "G Chart of Opportunities" in rep_g
    assert "Counting Method:" in rep_g
    assert "Proportion (p):" in rep_g
    assert "Test 1: One point beyond control limits." in rep_g
    assert "Benneyan Test:" in rep_g

    # Widget render verification
    widget_g = RareEventControlChartWidget(entry_g)
    img_g = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_g.fill(Qt.GlobalColor.white)
    widget_g.render(img_g)
    assert not img_g.isNull()

    # -------------------------------------------------------------
    # 2. T Chart Dialog & Execution
    # -------------------------------------------------------------
    dlg_t = RareEventChartDialog(p.worksheet, chart_type="T", parent=w)
    dlg_t.edit_var.setText("TimeBetween")
    dlg_t.combo_form.setCurrentIndex(1)  # Numeric intervals
    dlg_t.combo_method.setCurrentIndex(0)  # Days

    opt_t = RareEventOptionsDialog("T", dlg_t.options, parent=dlg_t)
    opt_t.combo_dist.setCurrentIndex(0)  # Weibull
    opt_t.edit_shape.setText("1.0")
    opt_t._save_and_accept()
    dlg_t.options = opt_t.options

    dlg_t._on_ok()
    cfg_t = dlg_t.get_configuration()
    assert cfg_t["chart_type"] == "T"

    entry_t = p.rare_event_control_chart(settings=cfg_t)
    assert entry_t is not None
    res_t = entry_t["result"]
    assert res_t["chart_type"] == "T"
    assert res_t["k_subgroups"] == 15
    assert res_t["ucl_val"] > res_t["center_line"]
    assert 6 in res_t["test1_signals"]

    rep_t = format_entry(entry_t)
    assert "T Chart of TimeBetween" in rep_t
    assert "Shape (Beta):" in rep_t

    widget_t = RareEventControlChartWidget(entry_t)
    img_t = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_t.fill(Qt.GlobalColor.white)
    widget_t.render(img_t)
    assert not img_t.isNull()

    # -------------------------------------------------------------
    # 3. Dates of Events Form Test
    # -------------------------------------------------------------
    cfg_dates = {
        "chart_type": "T",
        "form_of_data": 0,  # Dates
        "columns": ["EventDates"],
        "units": "Days",
        "options": {"distribution": "Exponential"},
    }
    entry_dates = p.rare_event_control_chart(settings=cfg_dates)
    assert entry_dates is not None
    res_dates = entry_dates["result"]
    assert res_dates["k_subgroups"] == 14  # 15 dates => 14 intervals

    # -------------------------------------------------------------
    # 4. MPX Roundtrip & Recipe Rerun
    # -------------------------------------------------------------
    proj_path = Path(temp) / "rare_event_verify.mpx"
    p.save(proj_path)
    assert proj_path.exists() and proj_path.stat().st_size > 0

    p2 = Presenter()
    p2.load(proj_path)
    assert len(p2.history) >= 3
    last_act = p2.history[-1]["recipe"]["action"]
    assert last_act == "rare_event_control_chart"

    # Save verification snapshot
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.exists():
                out_dir = candidate
                break

    if out_dir.exists():
        snap_path = out_dir / "StatCraft-rare-event-control-chart.png"
        img_g.save(str(snap_path))
