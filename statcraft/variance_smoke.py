"""Verification gate for native StatCraft One-Sample & Two-Sample Variance tests."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .one_variance_dialogs import OneVarianceDialog, OneVarianceOptionsDialog
from .two_variances_dialogs import (
    TwoVariancesDialog,
    TwoVariancesOptionsDialog,
    TwoVariancesGraphsDialog,
    TwoVariancesResultsDialog,
)
from .two_variances_charts import TwoVariancesSummaryPlotWidget
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_variances(app, p, w, temp, checkpoint):
    checkpoint("One-Sample & Two-Sample Variances (Stat > Basic Statistics > 1 Variance... & 2 Variances...) native dialogs, reports, and MPX roundtrip")
    p.new()
    s1_vals = [12.5, 13.2, 11.8, 14.0, 12.9, 13.5, 11.2, 14.5, 12.1, 13.0] * 3  # 30 observations
    s2_vals = [10.2, 10.8, 9.9, 11.5, 10.4, 11.1, 9.5, 11.8, 10.1, 10.6] * 3   # 30 observations
    stacked_vals = s1_vals + s2_vals
    group_ids = ["A"] * 30 + ["B"] * 30

    p.worksheet = Worksheet("VarianceDemo", [
        Column("Strength_A", "number", s1_vals),
        Column("Strength_B", "number", s2_vals),
        Column("Strength_All", "number", stacked_vals),
        Column("Group_ID", "text", group_ids),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "one_variance_action")
    assert w.one_variance_action.isEnabled()
    assert hasattr(w, "two_variances_action")
    assert w.two_variances_action.isEnabled()

    # ==========================================
    # 1. ONE-SAMPLE VARIANCE TESTS
    # ==========================================
    # 1a. Raw column mode through dialog
    dlg1 = OneVarianceDialog(p.worksheet, w)
    assert dlg1.mode_combo.currentIndex() == 0
    dlg1.sample_cols_edit.setText("C1")
    dlg1.test_check.setChecked(True)
    dlg1.hyp_type_combo.setCurrentIndex(0)  # hypothesized SD
    dlg1.hyp_val_edit.setText("1.0")

    opt1 = OneVarianceOptionsDialog(dlg1.options, is_variance=False, parent=dlg1)
    opt1.conf_edit.setText("95.0")
    opt1.alt_combo.setCurrentIndex(0)  # not_equal
    opt1._accept()
    dlg1.options.update(opt1.options)

    dlg1._accept()
    assert dlg1.result_payload is not None
    entry1_raw = p.one_variance(settings=dlg1.result_payload)
    assert entry1_raw is not None
    w.show_result(entry1_raw)
    res1 = entry1_raw["result"]["samples"][0]
    assert res1["n"] == 30
    assert res1["stdev"] > 0
    assert res1["chi2"]["p_value"] is not None
    assert res1["bonett"]["p_value"] is not None
    rep1_text = format_entry(entry1_raw)
    assert "Test and CI for One Variance: Strength_A" in rep1_text
    assert "Chi-Square" in rep1_text
    assert "Bonett" in rep1_text

    # 1b. Summarized mode (Standard deviation)
    dlg1_sum = OneVarianceDialog(p.worksheet, w)
    dlg1_sum.mode_combo.setCurrentIndex(1)
    dlg1_sum.sd_size_edit.setText("35")
    dlg1_sum.sd_val_edit.setText("1.25")
    dlg1_sum.test_check.setChecked(True)
    dlg1_sum.hyp_type_combo.setCurrentIndex(1)  # hypothesized variance
    dlg1_sum.hyp_val_edit.setText("2.0")
    dlg1_sum._accept()

    entry1_sum = p.one_variance(settings=dlg1_sum.result_payload)
    assert entry1_sum is not None
    res1_sum = entry1_sum["result"]["samples"][0]
    assert res1_sum["n"] == 35
    assert res1_sum["chi2"]["statistic"] > 0

    # ==========================================
    # 2. TWO-SAMPLE VARIANCE TESTS
    # ==========================================
    # 2a. Unstacked columns mode through dialog
    dlg2 = TwoVariancesDialog(p.worksheet, w)
    assert dlg2.mode_combo.currentIndex() == 1
    dlg2.s1_edit.setText("C1")
    dlg2.s2_edit.setText("C2")

    opt2 = TwoVariancesOptionsDialog(dlg2.options, is_summarized=False, parent=dlg2)
    opt2.ratio_combo.setCurrentIndex(0)  # SD ratio
    opt2.conf_edit.setText("95.0")
    opt2.hyp_edit.setText("1.0")
    opt2.alt_combo.setCurrentIndex(0)    # not_equal
    opt2.norm_check.setChecked(True)
    opt2._accept()
    dlg2.options.update(opt2.options)

    dlg2._accept()
    assert dlg2.result_payload is not None
    entry2_unstacked = p.two_variances(settings=dlg2.result_payload)
    assert entry2_unstacked is not None
    w.show_result(entry2_unstacked)
    res2 = entry2_unstacked["result"]
    assert res2["sample1"]["n"] == 30
    assert res2["sample2"]["n"] == 30
    assert res2["f_test"]["p_value"] is not None
    assert res2["bonett"]["p_value"] is not None
    assert res2["levene"]["p_value"] is not None
    rep2_text = format_entry(entry2_unstacked)
    assert "Test and CI for Two Variances: Strength_A, Strength_B" in rep2_text
    assert "F Test" in rep2_text

    # 2b. Stacked columns mode through dialog
    dlg2_st = TwoVariancesDialog(p.worksheet, w)
    dlg2_st.mode_combo.setCurrentIndex(0)
    dlg2_st.stacked_samples_edit.setText("C3")
    dlg2_st.stacked_ids_edit.setText("C4")
    dlg2_st._accept()
    entry2_stacked = p.two_variances(settings=dlg2_st.result_payload)
    assert entry2_stacked is not None
    assert entry2_stacked["result"]["f_test"]["statistic"] > 0

    # 2c. Summarized variances mode through dialog
    dlg2_sum = TwoVariancesDialog(p.worksheet, w)
    dlg2_sum.mode_combo.setCurrentIndex(3)  # Sample variances
    dlg2_sum.sum_s1_size.setText("25")
    dlg2_sum.sum_s1_val.setText("4.0")
    dlg2_sum.sum_s2_size.setText("30")
    dlg2_sum.sum_s2_val.setText("2.5")
    dlg2_sum._accept()
    entry2_sum = p.two_variances(settings=dlg2_sum.result_payload)
    assert entry2_sum is not None
    assert entry2_sum["result"]["f_test"]["df1"] == 24
    assert entry2_sum["result"]["f_test"]["df2"] == 29

    # ==========================================
    # 3. CHART RENDERING & ARTIFACTS
    # ==========================================
    chart_widget = TwoVariancesSummaryPlotWidget(entry2_unstacked)
    chart_widget.resize(600, 360)
    chart_img = QImage(QSize(600, 360), QImage.Format.Format_ARGB32)
    chart_img.fill(Qt.GlobalColor.white)
    chart_widget.render(chart_img)
    assert not chart_img.isNull()

    # Render dialog images
    dlg1_img = QImage(QSize(480, 300), QImage.Format.Format_ARGB32)
    dlg1_img.fill(Qt.GlobalColor.white)
    dlg1.render(dlg1_img)

    dlg2_img = QImage(QSize(480, 300), QImage.Format.Format_ARGB32)
    dlg2_img.fill(Qt.GlobalColor.white)
    dlg2.render(dlg2_img)

    # Save outputs
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
                break
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_mpx_path = out_dir / "StatCraft-one-and-two-variances-demo.mpx"
    p.save(demo_mpx_path)
    assert demo_mpx_path.exists() and demo_mpx_path.stat().st_size > 0

    # MPX Reopen & Rerun
    p2 = Presenter()
    p2.load(demo_mpx_path)
    assert len(p2.history) >= 2
    first_res = p2.history[0]
    p2.set_cell(0, 0, "25.0")
    assert p2.result_stale(first_res)
    rerun_entry = p2.rerun_result(first_res)
    assert not p2.result_stale(rerun_entry)

    # Write files
    (out_dir / "StatCraft-one-variance-report.txt").write_text(format_entry(entry1_raw), encoding="utf-8")
    (out_dir / "StatCraft-two-variances-report.txt").write_text(format_entry(entry2_unstacked), encoding="utf-8")
    dlg1_img.save(str(out_dir / "StatCraft-one-variance-dialog-preview-57.png"))
    dlg1_img.save(str(out_dir / "StatCraft-one-variance-dialog.png"))
    dlg2_img.save(str(out_dir / "StatCraft-two-variances-dialog-preview-57.png"))
    dlg2_img.save(str(out_dir / "StatCraft-two-variances-dialog.png"))
    chart_img.save(str(out_dir / "StatCraft-two-variances-summary-plot-preview-57.png"))
    chart_img.save(str(out_dir / "StatCraft-two-variances-summary-plot.png"))

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    chart_img.save(buf, "PNG")
    png_bytes = bytes(buf.data())

    snapshot1 = OfficeSnapshot(entry1_raw["title"], format_entry(entry1_raw), None)
    snapshot2 = OfficeSnapshot(entry2_unstacked["title"], format_entry(entry2_unstacked), png_bytes)
    export_docx(str(out_dir / "StatCraft-one-variance-example.docx"), snapshot1)
    export_pptx(str(out_dir / "StatCraft-one-variance-example.pptx"), snapshot1)
    export_docx(str(out_dir / "StatCraft-two-variances-example.docx"), snapshot2)
    export_pptx(str(out_dir / "StatCraft-two-variances-example.pptx"), snapshot2)

    return "passed"
