"""Verification gate for native StatCraft Paired t test."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .paired_t_chart import PairedTPlotWidget
from .paired_t_dialogs import (
    PairedTDialog,
    PairedTOptionsDialog,
    PairedTGraphsDialog,
)
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_paired_t(app, p, w, temp, checkpoint):
    checkpoint("Paired t (Stat > Basic Statistics > Paired t...) native dialogs, plots, and MPX roundtrip")
    p.new()
    s1_vals = [12.5, 13.0, 14.2, 11.8, 13.5, 12.0, 14.0, 13.2]
    s2_vals = [10.0, 11.5, 12.0, 10.5, 11.0, 10.8, 12.2, 11.5]
    p.worksheet = Worksheet("PairedDemo", [
        Column("PreTreatment", "number", s1_vals),
        Column("PostTreatment", "number", s2_vals),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "paired_t_action")
    assert w.paired_t_action.isEnabled()

    # 1. Raw paired columns mode through dialog
    dlg = PairedTDialog(p.worksheet, w)
    assert dlg.combo_data.currentIndex() == 0  # Each sample is in a column
    dlg.sample1_edit.setText("C1")
    dlg.sample2_edit.setText("C2")

    # Options subdialog
    opt_dlg = PairedTOptionsDialog(dlg.settings, dlg)
    opt_dlg.conf_edit.setText("95.0")
    opt_dlg.hyp_edit.setText("0.0")
    opt_dlg.alt_combo.setCurrentIndex(1)  # not_equal
    opt_dlg._accept()
    dlg.settings.update(opt_dlg.options)

    # Graphs subdialog
    grp_dlg = PairedTGraphsDialog(dlg.settings["graphs"], dlg)
    grp_dlg.hist_cb.setChecked(True)
    grp_dlg.ivp_cb.setChecked(True)
    grp_dlg.box_cb.setChecked(True)
    grp_dlg._accept()
    dlg.settings["graphs"] = grp_dlg.graphs

    dlg._on_ok()
    assert dlg.result_payload is not None
    payload = dlg.result_payload

    # Run paired test through Presenter
    entry_paired = p.paired_t(settings=payload)
    assert entry_paired is not None
    w.show_result(entry_paired)
    res = entry_paired["result"]
    assert res["differences"]["n"] == 8
    assert res["differences"]["mean"] > 0
    assert res["t_statistic"] > 0
    assert "Descriptive Statistics" in format_entry(entry_paired)
    assert "Estimation for Paired Difference" in format_entry(entry_paired)
    assert "Null hypothesis" in format_entry(entry_paired)

    # 2. Summarized data mode
    dlg_sum = PairedTDialog(p.worksheet, w)
    dlg_sum.combo_data.setCurrentIndex(1)  # Summarized
    dlg_sum.size_edit.setText("16")
    dlg_sum.mean_edit.setText("3.2")
    dlg_sum.sd_edit.setText("0.9")
    dlg_sum._on_ok()
    entry_sum = p.paired_t(settings=dlg_sum.result_payload)
    assert entry_sum is not None
    sum_res = entry_sum["result"]["differences"]
    assert sum_res["n"] == 16
    assert sum_res["df"] == 15
    assert entry_sum["result"]["t_statistic"] > 0

    # 3. Chart rendering
    widget = PairedTPlotWidget(entry_paired)
    widget.resize(600, 400)
    image = QImage(QSize(600, 400), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    widget.render(image)
    assert not image.isNull()

    # 4. Save artifacts to outputs folder
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
                break
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_mpx_path = out_dir / "StatCraft-paired-t-demo.mpx"
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
    image.save(str(out_dir / "StatCraft-paired-t-plot-preview-51.png"))
    image.save(str(out_dir / "StatCraft-paired-t-plot.png"))

    (out_dir / "StatCraft-paired-t-report.txt").write_text(format_entry(entry_paired), encoding="utf-8")

    dlg_img = QImage(QSize(520, 300), QImage.Format.Format_ARGB32)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)
    dlg_img.save(str(out_dir / "StatCraft-paired-t-dialog-preview-51.png"))
    dlg_img.save(str(out_dir / "StatCraft-paired-t-dialog.png"))

    # Word & PowerPoint export
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    png_bytes = bytes(buf.data())
    snapshot = OfficeSnapshot(
        entry_paired["title"],
        format_entry(entry_paired),
        png_bytes,
    )
    export_docx(str(out_dir / "StatCraft-paired-t-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-paired-t-example.pptx"), snapshot)

    return "passed"
