"""Verification gate for native StatCraft One-Sample t test."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .one_sample_t_chart import OneSampleTPlotWidget
from .one_sample_t_dialogs import (
    OneSampleTDialog,
    OneSampleTOptionsDialog,
    OneSampleTGraphsDialog,
)
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_one_sample_t(app, p, w, temp, checkpoint):
    checkpoint("One-Sample t (Stat > Basic Statistics > 1-Sample t...) native dialogs, plots, and MPX roundtrip")
    p.new()
    s1_vals = [10.2, 11.5, 12.0, 11.8, 12.4, 10.9, 11.2, 12.1]
    s2_vals = [15.1, 14.8, 16.2, 15.5, 15.9, 14.5, 16.0, 15.2]
    p.worksheet = Worksheet("OneSampleDemo", [
        Column("Thickness", "number", s1_vals),
        Column("Strength", "number", s2_vals),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "one_sample_t_action")
    assert w.one_sample_t_action.isEnabled()

    # 1. Single raw column mode through dialog
    dlg = OneSampleTDialog(p.worksheet, w)
    assert dlg.combo_data.currentIndex() == 0  # Raw columns
    dlg.sample_cols_edit.setText("C1")
    dlg.test_cb.setChecked(True)
    dlg.hyp_edit.setText("10.0")

    # Options subdialog
    opt_dlg = OneSampleTOptionsDialog(dlg.settings, dlg)
    opt_dlg.conf_edit.setText("95.0")
    opt_dlg.alt_combo.setCurrentIndex(1)  # not_equal
    opt_dlg._accept()
    dlg.settings.update(opt_dlg.options)

    # Graphs subdialog
    grp_dlg = OneSampleTGraphsDialog(dlg.settings["graphs"], dlg)
    grp_dlg.hist_cb.setChecked(True)
    grp_dlg.ivp_cb.setChecked(True)
    grp_dlg.box_cb.setChecked(True)
    grp_dlg._accept()
    dlg.settings["graphs"] = grp_dlg.graphs

    dlg._on_ok()
    assert dlg.result_payload is not None
    payload = dlg.result_payload

    # Run single-column test through Presenter
    entry_single = p.one_sample_t(settings=payload)
    assert entry_single is not None
    w.show_result(entry_single)
    res = entry_single["result"]
    assert len(res["samples"]) == 1
    s0 = res["samples"][0]
    assert s0["n"] == 8
    assert s0["t_statistic"] is not None and s0["t_statistic"] > 0
    assert "Descriptive Statistics" in format_entry(entry_single)
    assert "H0: μ = 10" in format_entry(entry_single)

    # 2. Multiple raw columns mode
    dlg_multi = OneSampleTDialog(p.worksheet, w)
    dlg_multi.sample_cols_edit.setText("C1 C2")
    dlg_multi.hyp_edit.setText("12.0")
    dlg_multi._on_ok()
    entry_multi = p.one_sample_t(settings=dlg_multi.result_payload)
    assert entry_multi is not None
    assert len(entry_multi["result"]["samples"]) == 2

    # 3. Summarized data mode
    dlg_sum = OneSampleTDialog(p.worksheet, w)
    dlg_sum.combo_data.setCurrentIndex(1)  # Summarized
    dlg_sum.size_edit.setText("20")
    dlg_sum.mean_edit.setText("105.0")
    dlg_sum.sd_edit.setText("3.5")
    dlg_sum.test_cb.setChecked(True)
    dlg_sum.hyp_edit.setText("100.0")
    dlg_sum._on_ok()
    entry_sum = p.one_sample_t(settings=dlg_sum.result_payload)
    assert entry_sum is not None
    sum_res = entry_sum["result"]["samples"][0]
    assert sum_res["n"] == 20
    assert sum_res["df"] == 19
    assert sum_res["t_statistic"] > 0

    # 4. Chart rendering
    widget = OneSampleTPlotWidget(entry_single)
    widget.resize(600, 400)
    image = QImage(QSize(600, 400), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    widget.render(image)
    assert not image.isNull()

    # 5. Save artifacts to outputs folder
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
                break
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_mpx_path = out_dir / "StatCraft-one-sample-t-demo.mpx"
    p.save(demo_mpx_path)
    assert demo_mpx_path.exists() and demo_mpx_path.stat().st_size > 0

    # MPX Reopen & Rerun
    p2 = Presenter()
    p2.load(demo_mpx_path)
    assert len(p2.history) >= 2
    first_res = p2.history[0]
    p2.set_cell(0, 0, "99.0")
    assert p2.result_stale(first_res)
    rerun_entry = p2.rerun_result(first_res)
    assert not p2.result_stale(rerun_entry)

    # Save images and text report
    image.save(str(out_dir / "StatCraft-one-sample-t-plot-preview-50.png"))
    image.save(str(out_dir / "StatCraft-one-sample-t-plot.png"))

    (out_dir / "StatCraft-one-sample-t-report.txt").write_text(format_entry(entry_single), encoding="utf-8")

    dlg_img = QImage(QSize(520, 320), QImage.Format.Format_ARGB32)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)
    dlg_img.save(str(out_dir / "StatCraft-one-sample-t-dialog-preview-50.png"))
    dlg_img.save(str(out_dir / "StatCraft-one-sample-t-dialog.png"))

    # Word & PowerPoint export
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    png_bytes = bytes(buf.data())
    snapshot = OfficeSnapshot(
        entry_single["title"],
        format_entry(entry_single),
        png_bytes,
    )
    export_docx(str(out_dir / "StatCraft-one-sample-t-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-one-sample-t-example.pptx"), snapshot)

    return "passed"
