"""Verification gate for native StatCraft Capability Sixpack (Normal Distribution)."""

from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .sixpack_dialogs import (
    CapabilitySixpackDialog,
    SixpackTestsDialog,
    CapabilityOptionsDialog,
    CapabilityEstimateDialog,
)
from .sixpack_chart import CapabilitySixpackWidget
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_sixpack(app, p, w, temp, checkpoint):
    checkpoint("Capability Sixpack (Stat > Quality Tools > Capability Sixpack > Normal...) native dialogs, reports, and 6-panel chart widget")
    p.new()

    np.random.seed(42)
    sample_data = np.random.normal(15.0, 1.0, 100).tolist()
    subgroups = [i // 5 + 1 for i in range(100)]
    c2_data = [x + 0.1 for x in sample_data]

    p.worksheet = Worksheet("SixpackDemo", [
        Column("Thickness", "number", sample_data),
        Column("Subgroup", "number", subgroups),
        Column("Width", "number", c2_data),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and execution with single column + subgroup size
    dlg = CapabilitySixpackDialog(p.worksheet, w)
    assert dlg.rb_single_col.isChecked()
    dlg.edit_single_col.setText("Thickness")
    dlg.edit_sub_size.setText("5")
    dlg.edit_lsl.setText("12.0")
    dlg.edit_usl.setText("18.0")

    # Options subdialog
    opt_dlg = CapabilityOptionsDialog(dlg.options, parent=dlg)
    opt_dlg.edit_k.setText("6.0")
    opt_dlg.edit_target.setText("15.0")
    opt_dlg.chk_include_ci.setChecked(True)
    opt_dlg.edit_clevel.setText("95.0")
    opt_dlg.combo_ctype.setCurrentIndex(0)
    opt_dlg.chk_ccpk.setChecked(True)
    opt_dlg._accept()
    dlg.options.update(opt_dlg.options)

    # Estimate subdialog
    est_dlg = CapabilityEstimateDialog(dlg.options, parent=dlg)
    est_dlg.rb_pooled.setChecked(True)
    est_dlg.chk_unbias_within.setChecked(True)
    est_dlg._accept()
    dlg.options.update(est_dlg.options)

    # Tests subdialog
    test_dlg = SixpackTestsDialog(dlg.options, parent=dlg)
    test_dlg.chk_test1.setChecked(True)
    test_dlg.chk_test2.setChecked(True)
    test_dlg._accept()
    dlg.options.update(test_dlg.options)

    dlg._accept()
    assert dlg.selected_params is not None

    entry = p.normal_sixpack(settings=dlg.selected_params)
    assert entry is not None
    res = entry.get("result", {})
    assert res.get("sample_n") == 100
    assert res.get("subgroup_count") == 20
    assert res.get("sigma_within") is not None
    assert res.get("sigma_overall") is not None

    # Verify all 6 panels
    assert "panel_xbar" in res
    assert "panel_disp" in res
    assert "panel_last25" in res
    assert "panel_hist" in res
    assert "panel_norm" in res
    assert "panel_summary" in res

    px = res["panel_xbar"]
    assert len(px["x"]) == 20
    assert len(px["y"]) == 20
    assert px["ucl_val"] is not None

    pd = res["panel_disp"]
    assert len(pd["x"]) == 20
    assert pd["ucl_val"] is not None

    plast = res["panel_last25"]
    assert len(plast["points"]) == 100

    pnorm = res["panel_norm"]
    assert pnorm["ad_stat"] is not None
    assert pnorm["p_value"] is not None

    psum = res["panel_summary"]
    assert psum["cp"] is not None
    assert psum["cpk"] is not None
    assert psum["pp"] is not None
    assert psum["ppk"] is not None

    # Verify text report formatting
    report = format_entry(entry)
    assert "Process Capability Sixpack Report" in report
    assert "Process Data" in report
    assert "Control Chart Diagnostics" in report
    assert "Normality Assessment" in report
    assert "Potential (Within) Capability" in report
    assert "Overall Capability" in report
    assert "Performance (parts per million)" in report

    # 2. Test chart widget rendering
    chart_widget = CapabilitySixpackWidget(entry)
    chart_widget.resize(950, 650)
    chart_img = QImage(QSize(950, 650), QImage.Format.Format_ARGB32_Premultiplied)
    chart_img.fill(Qt.GlobalColor.white)
    chart_widget.render(chart_img)
    assert not chart_img.isNull()
    assert chart_img.width() == 950
    assert chart_img.height() == 650

    # Dialog screenshot
    dlg_img = QImage(QSize(580, 430), QImage.Format.Format_ARGB32_Premultiplied)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)

    # 3. Subgroups across rows of columns
    settings_across = {
        "single_column": False,
        "cols_across": ["Thickness", "Width"],
        "lsl": 12.0,
        "usl": 18.0,
        "options": {"tolerance_k": 6.0}
    }
    entry_across = p.normal_sixpack(settings=settings_across)
    assert entry_across["result"]["subgroup_count"] == 100
    assert entry_across["result"]["subgroup_avg_size"] == 2.0

    # 4. UI presentation in ModernWindow
    w.show_result(entry)
    assert w.selected_entry is entry

    # 5. Save outputs and MPX roundtrip
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.parent.exists():
                out_dir = candidate
                break
    out_dir.mkdir(parents=True, exist_ok=True)

    demo_mpx_path = out_dir / "StatCraft-capability-sixpack-normal-demo.mpx"
    p.save(demo_mpx_path)
    assert demo_mpx_path.exists() and demo_mpx_path.stat().st_size > 0

    # MPX Reopen & Rerun
    p2 = Presenter()
    p2.load(demo_mpx_path)
    assert len(p2.history) >= 1
    first_res = p2.history[0]
    p2.set_cell(0, 0, "25.0")
    assert p2.result_stale(first_res)
    rerun_entry = p2.rerun_result(first_res)
    assert not p2.result_stale(rerun_entry)

    # Write files
    (out_dir / "StatCraft-capability-sixpack-report.txt").write_text(format_entry(entry), encoding="utf-8")
    dlg_img.save(str(out_dir / "StatCraft-capability-sixpack-dialog-preview-59.png"))
    dlg_img.save(str(out_dir / "StatCraft-capability-sixpack-dialog.png"))
    chart_img.save(str(out_dir / "StatCraft-capability-sixpack-plot-preview-59.png"))
    chart_img.save(str(out_dir / "StatCraft-capability-sixpack-plot.png"))

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    chart_img.save(buf, "PNG")
    png_bytes = bytes(buf.data())

    snapshot = OfficeSnapshot(entry["title"], format_entry(entry), png_bytes)
    export_docx(str(out_dir / "StatCraft-capability-sixpack-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-capability-sixpack-example.pptx"), snapshot)

    return "passed"
