"""Verification gate for native StatCraft Two-Sample t test."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .two_sample_t_chart import TwoSampleTPlotWidget
from .two_sample_t_dialogs import (
    TwoSampleTDialog,
    TwoSampleTOptionsDialog,
    TwoSampleTGraphsDialog,
)
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_two_sample_t(app, p, w, temp, checkpoint):
    checkpoint("Two-Sample t (Stat > Basic Statistics > 2-Sample t...) native dialogs, plots, and MPX roundtrip")
    p.new()
    s1_vals = [10.2, 11.5, 12.0, 11.8, 12.4, 10.9, 11.2, 12.1]
    s2_vals = [8.5, 9.2, 8.8, 9.5, 9.0, 8.7, 9.1, 8.9]
    p.worksheet = Worksheet("TwoSampleDemo", [
        Column("Treatment", "number", s1_vals),
        Column("Control", "number", s2_vals),
        Column("Response", "number", s1_vals + s2_vals),
        Column("Group", "text", ["Trt"] * len(s1_vals) + ["Ctrl"] * len(s2_vals)),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "two_sample_t_action")
    assert w.two_sample_t_action.isEnabled()

    # 1. Unstacked mode through dialog
    dlg = TwoSampleTDialog(p.worksheet, w)
    assert dlg.combo_data.currentIndex() == 1  # Unstacked
    dlg.sample1_edit.setText("C1")
    dlg.sample2_edit.setText("C2")

    # Options subdialog
    opt_dlg = TwoSampleTOptionsDialog(dlg.settings, dlg)
    opt_dlg.conf_edit.setText("95.0")
    opt_dlg.hyp_edit.setText("0.0")
    opt_dlg.pooled_cb.setChecked(False)
    opt_dlg._accept()
    dlg.settings.update(opt_dlg.options)

    # Graphs subdialog
    grp_dlg = TwoSampleTGraphsDialog(dlg.settings["graphs"], dlg)
    grp_dlg.ivp_cb.setChecked(True)
    grp_dlg.box_cb.setChecked(True)
    grp_dlg._accept()
    dlg.settings["graphs"] = grp_dlg.graphs

    dlg._on_ok()
    assert dlg.result_payload is not None
    payload = dlg.result_payload

    # Run unstacked test through Presenter
    entry_unstacked = p.two_sample_t(settings=payload)
    assert entry_unstacked is not None
    w.show_result(entry_unstacked)
    res_u = entry_unstacked["result"]
    assert res_u["sample1"]["n"] == 8
    assert res_u["sample2"]["n"] == 8
    assert res_u["t_statistic"] > 0
    assert "Descriptive Statistics" in format_entry(entry_unstacked)

    # 2. Stacked mode
    dlg_st = TwoSampleTDialog(p.worksheet, w)
    dlg_st.combo_data.setCurrentIndex(0)  # Stacked
    dlg_st.samples_edit.setText("C3")
    dlg_st.ids_edit.setText("C4")
    dlg_st.settings["assume_equal_variances"] = True
    dlg_st._on_ok()
    entry_stacked = p.two_sample_t(settings=dlg_st.result_payload)
    assert entry_stacked is not None
    res_s = entry_stacked["result"]
    assert res_s["assume_equal_variances"] is True
    assert res_s["df"] == 14  # 8 + 8 - 2 = 14

    # 3. Summarized mode
    dlg_sum = TwoSampleTDialog(p.worksheet, w)
    dlg_sum.combo_data.setCurrentIndex(2)  # Summarized
    dlg_sum.size1_edit.setText("12")
    dlg_sum.mean1_edit.setText("15.5")
    dlg_sum.sd1_edit.setText("2.1")
    dlg_sum.size2_edit.setText("12")
    dlg_sum.mean2_edit.setText("11.2")
    dlg_sum.sd2_edit.setText("1.9")
    dlg_sum._on_ok()
    entry_sum = p.two_sample_t(settings=dlg_sum.result_payload)
    assert entry_sum is not None
    assert entry_sum["result"]["df"] > 0

    # 4. Chart rendering
    widget = TwoSampleTPlotWidget(entry_unstacked)
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

    demo_mpx_path = out_dir / "StatCraft-two-sample-t-demo.mpx"
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
    image.save(str(out_dir / "StatCraft-two-sample-t-plot-preview-49.png"))
    image.save(str(out_dir / "StatCraft-two-sample-t-plot.png"))

    (out_dir / "StatCraft-two-sample-t-report.txt").write_text(format_entry(entry_unstacked), encoding="utf-8")

    dlg_img = QImage(QSize(520, 320), QImage.Format.Format_ARGB32)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)
    dlg_img.save(str(out_dir / "StatCraft-two-sample-t-dialog-preview-49.png"))
    dlg_img.save(str(out_dir / "StatCraft-two-sample-t-dialog.png"))

    # Word & PowerPoint export
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    png_bytes = bytes(buf.data())
    snapshot = OfficeSnapshot(
        entry_unstacked["title"],
        format_entry(entry_unstacked),
        png_bytes,
    )
    export_docx(str(out_dir / "StatCraft-two-sample-t-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-two-sample-t-example.pptx"), snapshot)

    return "passed"
