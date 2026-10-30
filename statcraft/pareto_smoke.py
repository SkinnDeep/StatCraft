"""Verification gate for native StatCraft Pareto Chart (Stat > Quality Tools > Pareto Chart)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .pareto_dialogs import ParetoChartDialog
from .pareto_chart import ParetoChartWidget


def verify_pareto_chart(app, p, w, temp, checkpoint):
    checkpoint("Pareto Chart (Stat > Quality Tools > Pareto Chart) native dialog, reports, and dual-axis chart widget")
    p.new()

    # Create test worksheet with raw defect occurrences and summarized tables
    raw_defects = [
        "Scratch", "Dent", "Scratch", "Burr", "Scratch", "Dent",
        "Crack", "Scratch", "Blemish", "Dent", "Scratch", "Burr",
        "Scratch", "Dent", "Scratch", "Blemish", "Misalign", "Scratch",
        "Warp", "Pinhole", "Scratch", "Dent", "Crack", "Burr",
    ]
    summ_categories = [
        "Scratches", "Dents", "Burrs", "Blemishes", "Cracks",
        "Misalignment", "Warpage", "Pinholes", "Contamination",
    ]
    summ_counts = [48, 26, 14, 9, 6, 4, 3, 2, 1]  # Total 113

    p.worksheet = Worksheet("ParetoQualityDemo", [
        Column("RawDefects", "text", raw_defects),
        Column("DefectNames", "text", summ_categories),
        Column("DefectCounts", "number", summ_counts),
    ])
    w.page = 0
    w.refresh()

    # -------------------------------------------------------------
    # 1. Raw Observations Mode Dialog & Execution
    # -------------------------------------------------------------
    dlg_raw = ParetoChartDialog(p.worksheet, parent=w)
    dlg_raw.combo_arrange.setCurrentIndex(0)  # Each defect in separate row
    dlg_raw.edit_defects_raw.setText("RawDefects")
    dlg_raw.radio_combine_yes.setChecked(True)
    dlg_raw.edit_combine_pct.setText("95.0")
    dlg_raw.chk_cumulative.setChecked(True)

    dlg_raw._on_accept()
    cfg_raw = dlg_raw.get_configuration()
    assert not cfg_raw["is_summarized"]
    assert cfg_raw["defect_column"] == "RawDefects"
    assert cfg_raw["combine_percent"] == 95.0

    entry_raw = p.pareto_chart(settings=cfg_raw)
    assert entry_raw is not None
    assert entry_raw["recipe"]["action"] == "pareto_chart"
    res_raw = entry_raw["result"]
    assert res_raw["analysis"] == "pareto_chart"
    assert res_raw["total_count"] == 24.0
    assert res_raw["categories"][0] == "Scratch"
    assert res_raw["counts"][0] == 9.0
    assert res_raw["cum_percents"][-1] == 100.0

    rep_raw = format_entry(entry_raw)
    assert "Pareto Chart of RawDefects" in rep_raw
    assert "Scratch" in rep_raw
    assert "Total" in rep_raw

    widget_raw = ParetoChartWidget(entry_raw)
    img_raw = QImage(QSize(840, 540), QImage.Format.Format_ARGB32_Premultiplied)
    img_raw.fill(Qt.GlobalColor.white)
    widget_raw.render(img_raw)
    assert not img_raw.isNull()

    artifact_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    if artifact_dir.exists():
        img_raw.save(str(artifact_dir / "StatCraft-pareto-chart.png"))

    # -------------------------------------------------------------
    # 2. Summarized Table Mode Dialog & Execution
    # -------------------------------------------------------------
    dlg_summ = ParetoChartDialog(p.worksheet, parent=w)
    dlg_summ.combo_arrange.setCurrentIndex(1)  # Summarized values in table
    dlg_summ._on_arrange_changed(1)
    dlg_summ.edit_labels_summ.setText("DefectNames")
    dlg_summ.edit_counts_summ.setText("DefectCounts")
    dlg_summ.radio_combine_yes.setChecked(True)
    dlg_summ.edit_combine_pct.setText("95.0")

    dlg_summ._on_accept()
    cfg_summ = dlg_summ.get_configuration()
    assert cfg_summ["is_summarized"]
    assert cfg_summ["defect_column"] == "DefectNames"
    assert cfg_summ["count_column"] == "DefectCounts"

    entry_summ = p.pareto_chart(settings=cfg_summ)
    assert entry_summ is not None
    res_summ = entry_summ["result"]
    assert res_summ["analysis"] == "pareto_chart"
    assert res_summ["total_count"] == 113.0
    assert res_summ["categories"][0] == "Scratches"
    assert res_summ["counts"][0] == 48.0
    assert "Other" in res_summ["categories"]
    assert res_summ["cum_percents"][-1] == 100.0

    rep_summ = format_entry(entry_summ)
    assert "Pareto Chart of DefectNames" in rep_summ
    assert "Scratches" in rep_summ
    assert "Other" in rep_summ
    assert "Total" in rep_summ

    widget_summ = ParetoChartWidget(entry_summ)
    img_summ = QImage(QSize(840, 540), QImage.Format.Format_ARGB32_Premultiplied)
    img_summ.fill(Qt.GlobalColor.white)
    widget_summ.render(img_summ)
    assert not img_summ.isNull()

    checkpoint("Pareto Chart verification passed successfully")
