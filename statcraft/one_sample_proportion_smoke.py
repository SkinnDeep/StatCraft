"""Verification gate for native StatCraft One-Sample Proportion test."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .one_sample_proportion_dialogs import (
    OneSampleProportionDialog,
    OneSampleProportionOptionsDialog,
)
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_one_sample_proportion(app, p, w, temp, checkpoint):
    checkpoint("One-Sample Proportion (Stat > Basic Statistics > 1 Proportion...) native dialogs, reports, and MPX roundtrip")
    p.new()
    s1_vals = [1] * 15 + [0] * 35
    s2_vals = [1] * 25 + [0] * 25
    p.worksheet = Worksheet("OnePropDemo", [
        Column("Defects", "number", s1_vals),
        Column("Flaws", "number", s2_vals),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "one_proportion_action")
    assert w.one_proportion_action.isEnabled()

    # 1. Single raw column mode through dialog (Exact method)
    dlg = OneSampleProportionDialog(p.worksheet, w)
    assert dlg.combo_data.currentIndex() == 0  # Raw columns
    dlg.sample_cols_edit.setText("C1")
    dlg.test_cb.setChecked(True)
    dlg.hyp_edit.setText("0.5")

    # Options subdialog
    opt_dlg = OneSampleProportionOptionsDialog(dlg.settings, dlg)
    opt_dlg.conf_edit.setText("95.0")
    opt_dlg.alt_combo.setCurrentIndex(1)  # not_equal
    opt_dlg.method_combo.setCurrentIndex(0)  # exact
    opt_dlg._accept()
    dlg.settings.update(opt_dlg.options)

    dlg._on_ok()
    assert dlg.result_payload is not None
    payload = dlg.result_payload

    # Run single-column test through Presenter
    entry_single = p.one_sample_proportion(settings=payload)
    assert entry_single is not None
    w.show_result(entry_single)
    res = entry_single["result"]
    assert len(res["samples"]) == 1
    s0 = res["samples"][0]
    assert s0["n"] == 50
    assert s0["events"] == 15
    assert s0["p_value"] is not None
    rep_text = format_entry(entry_single)
    assert "Test and CI for One Proportion: Defects" in rep_text
    assert "Descriptive Statistics" in rep_text
    assert "Exact" in rep_text
    assert "H0: p = 0.5" in rep_text

    # 2. Multiple raw columns mode
    dlg_multi = OneSampleProportionDialog(p.worksheet, w)
    dlg_multi.sample_cols_edit.setText("C1 C2")
    dlg_multi.hyp_edit.setText("0.4")
    dlg_multi._on_ok()
    entry_multi = p.one_sample_proportion(settings=dlg_multi.result_payload)
    assert entry_multi is not None
    assert len(entry_multi["result"]["samples"]) == 2

    # 3. Summarized data mode with Normal approximation
    dlg_sum = OneSampleProportionDialog(p.worksheet, w)
    dlg_sum.combo_data.setCurrentIndex(1)  # Summarized
    dlg_sum.events_edit.setText("32")
    dlg_sum.trials_edit.setText("50")
    dlg_sum.test_cb.setChecked(True)
    dlg_sum.hyp_edit.setText("0.5")

    opt_dlg2 = OneSampleProportionOptionsDialog(dlg_sum.settings, dlg_sum)
    opt_dlg2.method_combo.setCurrentIndex(1)  # Normal approximation
    opt_dlg2._accept()
    dlg_sum.settings.update(opt_dlg2.options)

    dlg_sum._on_ok()
    entry_sum = p.one_sample_proportion(settings=dlg_sum.result_payload)
    assert entry_sum is not None
    sum_res = entry_sum["result"]["samples"][0]
    assert sum_res["n"] == 50
    assert sum_res["events"] == 32
    assert sum_res["z_statistic"] is not None
    rep_sum = format_entry(entry_sum)
    assert "Normal approximation" in rep_sum
    assert "Z-Value" in rep_sum

    # 4. Save artifacts to outputs folder
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
                break
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_mpx_path = out_dir / "StatCraft-one-sample-proportion-demo.mpx"
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
    (out_dir / "StatCraft-one-sample-proportion-report.txt").write_text(format_entry(entry_single), encoding="utf-8")

    dlg_img = QImage(QSize(520, 320), QImage.Format.Format_ARGB32)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)
    dlg_img.save(str(out_dir / "StatCraft-one-sample-proportion-dialog-preview-53.png"))
    dlg_img.save(str(out_dir / "StatCraft-one-sample-proportion-dialog.png"))

    # Word & PowerPoint export
    snapshot = OfficeSnapshot(
        entry_single["title"],
        format_entry(entry_single),
        None,
    )
    export_docx(str(out_dir / "StatCraft-one-sample-proportion-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-one-sample-proportion-example.pptx"), snapshot)

    return "passed"
