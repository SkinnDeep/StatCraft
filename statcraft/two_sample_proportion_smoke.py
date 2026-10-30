"""Verification gate for native StatCraft Two-Sample Proportion test."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .two_sample_proportion_dialogs import (
    TwoSampleProportionDialog,
    TwoSampleProportionOptionsDialog,
)
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_two_sample_proportion(app, p, w, temp, checkpoint):
    checkpoint("Two-Sample Proportion (Stat > Basic Statistics > 2 Proportions...) native dialogs, reports, and MPX roundtrip")
    p.new()
    s1_vals = [1] * 35 + [0] * 15
    s2_vals = [1] * 25 + [0] * 25
    p.worksheet = Worksheet("TwoPropDemo", [
        Column("BatchA", "number", s1_vals),
        Column("BatchB", "number", s2_vals),
        Column("Combined", "number", s1_vals + s2_vals),
        Column("Group", "text", ["A"] * 50 + ["B"] * 50),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "two_proportions_action")
    assert w.two_proportions_action.isEnabled()

    # 1. Unstacked mode through dialog (Default)
    dlg = TwoSampleProportionDialog(p.worksheet, w)
    assert dlg.combo_data.currentIndex() == 1
    dlg.sample1_edit.setText("C1")
    dlg.sample2_edit.setText("C2")

    # Options subdialog
    opt_dlg = TwoSampleProportionOptionsDialog(dlg.settings, dlg)
    opt_dlg.conf_edit.setText("95.0")
    opt_dlg.hyp_edit.setText("0.0")
    opt_dlg.alt_combo.setCurrentIndex(1)  # not_equal
    opt_dlg.method_combo.setCurrentIndex(1)  # pooled
    opt_dlg._accept()
    dlg.settings.update(opt_dlg.options)

    dlg._on_ok()
    assert dlg.result_payload is not None
    payload = dlg.result_payload

    # Run unstacked test through Presenter
    entry_unstack = p.two_sample_proportion(settings=payload)
    assert entry_unstack is not None
    w.show_result(entry_unstack)
    res = entry_unstack["result"]
    assert res["sample1"]["n"] == 50 and res["sample1"]["events"] == 35
    assert res["sample2"]["n"] == 50 and res["sample2"]["events"] == 25
    assert res["z_statistic"] is not None and res["z_statistic"] > 0
    rep_text = format_entry(entry_unstack)
    assert "Test and CI for Two Proportions" in rep_text
    assert "Estimation for Difference" in rep_text
    assert "Normal approximation" in rep_text
    assert "Fisher's exact" in rep_text

    # 2. Stacked mode through dialog
    dlg_stacked = TwoSampleProportionDialog(p.worksheet, w)
    dlg_stacked.combo_data.setCurrentIndex(0)  # Stacked
    dlg_stacked.samples_edit.setText("C3")
    dlg_stacked.ids_edit.setText("C4")
    dlg_stacked._on_ok()
    entry_stacked = p.two_sample_proportion(settings=dlg_stacked.result_payload)
    assert entry_stacked is not None
    assert entry_stacked["result"]["sample1"]["n"] == 50

    # 3. Summarized data mode through dialog
    dlg_sum = TwoSampleProportionDialog(p.worksheet, w)
    dlg_sum.combo_data.setCurrentIndex(2)  # Summarized
    dlg_sum.events1_edit.setText("35")
    dlg_sum.trials1_edit.setText("50")
    dlg_sum.events2_edit.setText("25")
    dlg_sum.trials2_edit.setText("50")
    dlg_sum._on_ok()
    entry_sum = p.two_sample_proportion(settings=dlg_sum.result_payload)
    assert entry_sum is not None
    assert entry_sum["result"]["sample1"]["events"] == 35
    assert entry_sum["result"]["sample2"]["events"] == 25

    # 4. Save artifacts to outputs folder
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
                break
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_mpx_path = out_dir / "StatCraft-two-sample-proportion-demo.mpx"
    p.save(demo_mpx_path)
    assert demo_mpx_path.exists() and demo_mpx_path.stat().st_size > 0

    # MPX Reopen & Rerun
    p2 = Presenter()
    p2.load(demo_mpx_path)
    assert len(p2.history) >= 2
    first_res = p2.history[0]
    p2.set_cell(0, 0, "0")
    assert p2.result_stale(first_res)
    rerun_entry = p2.rerun_result(first_res)
    assert not p2.result_stale(rerun_entry)

    # Save dialog image and text report
    (out_dir / "StatCraft-two-sample-proportion-report.txt").write_text(format_entry(entry_unstack), encoding="utf-8")

    dlg_img = QImage(QSize(540, 320), QImage.Format.Format_ARGB32)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)
    dlg_img.save(str(out_dir / "StatCraft-two-sample-proportion-dialog-preview-54.png"))
    dlg_img.save(str(out_dir / "StatCraft-two-sample-proportion-dialog.png"))

    # Word & PowerPoint export
    snapshot = OfficeSnapshot(
        entry_unstack["title"],
        format_entry(entry_unstack),
        None,
    )
    export_docx(str(out_dir / "StatCraft-two-sample-proportion-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-two-sample-proportion-example.pptx"), snapshot)

    return "passed"
