"""Verification gate for native StatCraft Test for Equal Variances."""
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .equal_variances_chart import EqualVariancesSummaryPlotWidget
from .equal_variances_dialogs import (
    TestEqualVariancesDialog,
    TestEqualVariancesOptionsDialog,
    TestEqualVariancesStorageDialog,
)
from .office_export import OfficeSnapshot, export_docx, export_pptx


def verify_equal_variances(app, p, w, temp, checkpoint):
    checkpoint("Test for Equal Variances (Stat > ANOVA > Test for Equal Variances...) native dialogs, summary plot, storage, and MPX roundtrip")
    p.new()
    p.worksheet = Worksheet("EqualVarDemo", [
        Column("Yield", "number", [10, 12, 11, 13, 9, 14, 15, 13, 16, 17, 20, 25, 18, 30, 22]),
        Column("Catalyst", "text", ["CatA"] * 5 + ["CatB"] * 5 + ["CatC"] * 5),
        Column("UnstackedA", "number", [10, 12, 11, 13, 9]),
        Column("UnstackedB", "number", [14, 15, 13, 16, 17]),
        Column("UnstackedC", "number", [20, 25, 18, 30, 22]),
    ])
    w.page = 0
    w.refresh()

    assert hasattr(w, "test_equal_variances_action")
    assert w.test_equal_variances_action.isEnabled()

    # 1. Test stacked mode with dialog
    dlg = TestEqualVariancesDialog(p.worksheet, w)
    assert dlg.combo_data.currentIndex() == 0  # Stacked
    dlg.resp_edit.setText("C1")
    dlg.factors_edit.setText("C2")

    # Options subdialog
    opt_dlg = TestEqualVariancesOptionsDialog(dlg.options, dlg)
    opt_dlg.conf_edit.setText("95.0")
    opt_dlg.normal_cb.setChecked(False)
    opt_dlg._accept()
    dlg.options = opt_dlg.options
    assert dlg.options["confidence_level"] == 95.0
    assert not dlg.options["use_normal_distribution"]

    # Storage subdialog
    stor_dlg = TestEqualVariancesStorageDialog(dlg.options["storage"], dlg.options["use_normal_distribution"], dlg)
    stor_dlg.stdev_cb.setChecked(True)
    stor_dlg.var_cb.setChecked(True)
    stor_dlg.bonf_cb.setChecked(True)
    stor_dlg.mci_cb.setChecked(True)
    stor_dlg._accept()
    dlg.options["storage"] = stor_dlg.storage
    assert dlg.options["storage"]["stdevs"]
    assert dlg.options["storage"]["mci"]

    # Accept dialog
    dlg._on_ok()
    assert dlg.result_payload is not None
    payload = dlg.result_payload

    # Run analysis through Presenter
    entry_stacked = p.test_equal_variances(
        stacked=payload["stacked"],
        response_index=payload["response_index"],
        factor_indices=payload["factor_indices"],
        options=payload["options"],
    )
    assert entry_stacked is not None
    w.show_result(entry_stacked)
    res_s = entry_stacked["result"]
    assert len(res_s["groups"]) == 3
    assert "levene" in res_s
    assert "multiple_comparisons" in res_s
    assert res_s["levene"]["test_statistic"] > 0
    assert "Null hypothesis" in format_entry(entry_stacked)

    # Check column storage
    stored_cols = [c.name for c in p.worksheet.columns]
    for required in ["STDEV", "VARIANCES", "BONF1", "BONF2", "MCI1", "MCI2"]:
        assert required in stored_cols, f"Expected stored column {required}"

    # 2. Run unstacked normal (Bartlett)
    dlg_u = TestEqualVariancesDialog(p.worksheet, w)
    dlg_u.combo_data.setCurrentIndex(1)  # Unstacked
    dlg_u.unstacked_edit.setText("C3 C4 C5")
    dlg_u.options["use_normal_distribution"] = True
    dlg_u._on_ok()
    p_u = dlg_u.result_payload
    entry_unstacked = p.test_equal_variances(
        stacked=p_u["stacked"],
        response_indices=p_u["response_indices"],
        options=p_u["options"],
    )
    res_u = entry_unstacked["result"]
    assert res_u["bartlett"] is not None
    assert res_u["bartlett"]["test_statistic"] > 0

    # 3. Chart widget rendering
    widget = EqualVariancesSummaryPlotWidget(entry_stacked)
    widget.resize(680, 420)
    image = QImage(QSize(680, 420), QImage.Format.Format_ARGB32)
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

    demo_mpx_path = out_dir / "StatCraft-equal-variances-demo.mpx"
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
    image.save(str(out_dir / "StatCraft-equal-variances-summary-plot-preview-48.png"))
    image.save(str(out_dir / "StatCraft-equal-variances-summary-plot.png"))

    (out_dir / "StatCraft-equal-variances-report.txt").write_text(format_entry(entry_stacked), encoding="utf-8")

    dlg_img = QImage(QSize(560, 360), QImage.Format.Format_ARGB32)
    dlg_img.fill(Qt.GlobalColor.white)
    dlg.render(dlg_img)
    dlg_img.save(str(out_dir / "StatCraft-equal-variances-dialog-preview-48.png"))
    dlg_img.save(str(out_dir / "StatCraft-equal-variances-dialog.png"))

    # Word & PowerPoint export
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buf, "PNG")
    png_bytes = bytes(buf.data())
    snapshot = OfficeSnapshot(
        entry_stacked["title"],
        format_entry(entry_stacked),
        png_bytes,
    )
    export_docx(str(out_dir / "StatCraft-equal-variances-example.docx"), snapshot)
    export_pptx(str(out_dir / "StatCraft-equal-variances-example.pptx"), snapshot)

    return "passed"
