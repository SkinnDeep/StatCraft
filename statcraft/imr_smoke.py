"""Verification gate for native StatCraft Individuals-Moving Range (I-MR) Chart."""

from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QPainter
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .imr_dialogs import IMRChartDialog, IMROptionsDialog
from .imr_chart import IMRChartWidget


def verify_imr(app, p, w, temp, checkpoint):
    checkpoint("I-MR Control Chart (Stat > Control Charts > Variables Charts for Individuals > I-MR...) native dialogs, reports, and dual-panel chart widget")
    p.new()

    np.random.seed(101)
    sample_data = np.random.normal(25.0, 2.0, 50).tolist()
    # Introduce deliberate special causes:
    # Point 15: extreme spike (Test 1)
    sample_data[14] = 38.0
    # Point 30-38: run of 9 on same side (Test 2)
    for i in range(29, 38):
        sample_data[i] = 27.5

    p.worksheet = Worksheet("IMRDemo", [
        Column("Weight", "number", sample_data),
        Column("Length", "number", [x * 1.5 for x in sample_data]),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and parameter selection
    dlg = IMRChartDialog(p.worksheet, w)
    dlg.edit_vars.setText("Weight Length")
    
    # Options subdialog
    opt_dlg = IMROptionsDialog(dlg, dlg.options)
    opt_dlg.rb_amr.setChecked(True)
    opt_dlg.span_edit.setText("2")
    opt_dlg.chk_t1.setChecked(True)
    opt_dlg.chk_t2.setChecked(True)
    opt_dlg.chk_store_pts.setChecked(True)
    opt_dlg._save_and_accept()
    dlg.options = opt_dlg.options

    dlg._on_ok()
    assert dlg.selected_params is not None
    assert dlg.selected_params["variables"] == [0, 1]

    # 2. Presenter execution
    entry = p.imr_chart(settings=dlg.selected_params)
    assert entry is not None
    assert entry["recipe"]["action"] == "imr_chart"
    res = entry["result"]
    assert res["analysis"] == "imr_control"
    assert res["graph"] == "imr_chart"
    assert res["count"] == 50
    assert res["missing"] == 0
    assert res["i_center"] > 0
    assert res["within_stdev"] > 0
    assert len(res["moving_ranges"]) == 50

    # Test 1 failure at point 15 detected
    assert 15 in res["test_failures"]
    assert 1 in res["test_failures"][15]

    # 3. Report generation
    report_text = format_entry(entry)
    assert "I-MR Chart of Length" in report_text
    assert "Test Results for I Chart" in report_text
    assert "Process Information" in report_text

    # 4. Dual-panel Chart Widget rendering
    widget = IMRChartWidget(entry, parent=w)
    assert len(widget.panels) == 2
    widget.resize(800, 650)
    w.show_result(entry)
    app.processEvents()

    # Verify widget paints without exceptions into an offscreen buffer
    img = QImage(QSize(800, 650), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    widget.render(img)
    assert not img.isNull()

    # 5. MPX Roundtrip & Recipe Rerun
    save_path = Path(temp) / "imr_roundtrip.mpx"
    p.save(save_path)
    assert save_path.exists() and save_path.stat().st_size > 0

    p_reopen = Presenter()
    p_reopen.load(save_path)
    assert len(p_reopen.worksheet.columns) >= 2
    assert p_reopen.worksheet.columns[0].name == "Weight"

    # 6. Save outputs artifacts
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
    if out_dir.exists():
        demo_mpx_path = out_dir / "StatCraft-imr-demo.mpx"
        p.save(demo_mpx_path)
        img.save(str(out_dir / "StatCraft-imr-plot-preview-60.png"))
        img.save(str(out_dir / "StatCraft-imr-plot.png"))
        dlg_img = QImage(QSize(520, 320), QImage.Format.Format_ARGB32)
        dlg_img.fill(Qt.GlobalColor.white)
        dlg.render(dlg_img)
        dlg_img.save(str(out_dir / "StatCraft-imr-dialog-preview-60.png"))
        dlg_img.save(str(out_dir / "StatCraft-imr-dialog.png"))
        (out_dir / "StatCraft-imr-report.txt").write_text(report_text, encoding="utf-8")
