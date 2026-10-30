"""Verification gate for native StatCraft Two-Sample Poisson Rate test."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .two_sample_poisson_dialogs import (
    TwoSamplePoissonDialog,
    TwoSamplePoissonOptionsDialog,
)
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_two_sample_poisson(app, p, w, temp, checkpoint):
    checkpoint("Two-Sample Poisson Rate (Stat > Basic Statistics > 2-Sample Poisson Rate...) native dialogs, reports, and MPX roundtrip")
    p.new()
    s1_vals = [2, 1, 0, 3, 2, 1, 4, 0, 1, 2] * 5  # 50 observations, sum = 80
    s2_vals = [1, 2, 1, 0, 3, 2, 1, 2, 0, 1] * 5  # 50 observations, sum = 65
    p.worksheet = Worksheet("TwoPoissonDemo", [
        Column("Machine_A", "number", s1_vals),
        Column("Machine_B", "number", s2_vals),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "two_sample_poisson_action")
    assert w.two_sample_poisson_action.isEnabled()

    # 1. Unstacked columns mode through dialog
    dlg = TwoSamplePoissonDialog(p.worksheet, w)
    assert dlg.mode_combo.currentIndex() == 1  # Unstacked mode
    dlg.s1_edit.setText("C1")
    dlg.s2_edit.setText("C2")

    # Options subdialog
    opt_dlg = TwoSamplePoissonOptionsDialog(dlg.options, dlg)
    opt_dlg.conf_edit.setText("95.0")
    opt_dlg.alt_combo.setCurrentIndex(0)  # not_equal
    opt_dlg.diff_edit.setText("0.0")
    opt_dlg.method_combo.setCurrentIndex(1)  # pooled
    opt_dlg._accept()
    dlg.options.update(opt_dlg.options)

    dlg._accept()
    assert dlg.result_payload is not None
    payload = dlg.result_payload

    # Run unstacked test through Presenter
    entry_unstacked = p.two_sample_poisson(settings=payload)
    assert entry_unstacked is not None
    w.show_result(entry_unstacked)
    res = entry_unstacked["result"]
    assert res["x1"] == 80
    assert res["x2"] == 65
    assert res["n1"] == 50
    assert res["n2"] == 50
    assert res["z_value"] is not None
    assert res["p_value"] is not None
    assert res["exact_p_value"] is not None

    rep_text = format_entry(entry_unstacked)
    assert "Test and CI for Two-Sample Poisson Rates" in rep_text
    assert "Descriptive Statistics" in rep_text
    assert "Machine_A" in rep_text
    assert "Machine_B" in rep_text
    assert "Difference" in rep_text

    # 2. Summarized data mode with Separate rates
    dlg_sum = TwoSamplePoissonDialog(p.worksheet, w)
    dlg_sum.mode_combo.setCurrentIndex(2)  # Summarized
    dlg_sum.sum_s1_size.setText("50")
    dlg_sum.sum_s1_events.setText("120")
    dlg_sum.sum_s2_size.setText("50")
    dlg_sum.sum_s2_events.setText("90")

    opt_dlg2 = TwoSamplePoissonOptionsDialog(dlg_sum.options, dlg_sum)
    opt_dlg2.method_combo.setCurrentIndex(0)  # separate
    opt_dlg2._accept()
    dlg_sum.options.update(opt_dlg2.options)

    dlg_sum._accept()
    entry_sum = p.two_sample_poisson(settings=dlg_sum.result_payload)
    assert entry_sum is not None
    sum_res = entry_sum["result"]
    assert sum_res["x1"] == 120
    assert sum_res["x2"] == 90
    assert sum_res["z_value"] is not None
    rep_sum = format_entry(entry_sum)
    assert "Test and CI for Two-Sample Poisson Rates" in rep_sum
    assert "Normal approximation" in rep_sum

    # 3. Save artifacts to outputs folder
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
                break
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_mpx_path = out_dir / "StatCraft-two-sample-poisson-demo.mpx"
    p.save(demo_mpx_path)
    assert demo_mpx_path.exists() and demo_mpx_path.stat().st_size > 0

    # MPX Reopen & Rerun
    p2 = Presenter()
    p2.load(demo_mpx_path)
    assert len(p2.history) >= 2
    first_res = p2.history[0]
    p2.set_cell(0, 0, "5")
    assert p2.result_stale(first_res)
    rerun_entry = p2.rerun_result(first_res)
    assert not p2.result_stale(rerun_entry)

    # Save dialog image and text report
    (out_dir / "StatCraft-two-sample-poisson-report.txt").write_text(format_entry(entry_unstacked), encoding="utf-8")

    dlg_img = QImage(QSize(560, 360), QImage.Format.Format_ARGB32)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)
    dlg_img.save(str(out_dir / "StatCraft-two-sample-poisson-dialog-preview-56.png"))
    dlg_img.save(str(out_dir / "StatCraft-two-sample-poisson-dialog.png"))

    # Word & PowerPoint export
    snapshot = OfficeSnapshot(
        entry_unstacked["title"],
        format_entry(entry_unstacked),
        None,
    )
    export_docx(str(out_dir / "StatCraft-two-sample-poisson-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-two-sample-poisson-example.pptx"), snapshot)

    return "passed"
