"""Verification gate for native StatCraft Capability Analysis (Normal Distribution)."""

import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage, QPainter
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .capability_dialogs import (
    CapabilityDialog,
    CapabilityOptionsDialog,
    CapabilityEstimateDialog,
)
from .capability_chart import CapabilityPlotWidget


def verify_capability(app, p, w, temp, checkpoint):
    checkpoint("Capability Analysis (Stat > Quality Tools > Capability Analysis > Normal...) native dialogs, reports, and plot widget")
    p.new()

    np.random.seed(42)
    sample_data = np.random.normal(15.0, 1.0, 100).tolist()
    subgroups = [i // 5 + 1 for i in range(100)]
    c2_data = [x + 0.1 for x in sample_data]

    p.worksheet = Worksheet("CapabilityDemo", [
        Column("Thickness", "number", sample_data),
        Column("Subgroup", "number", subgroups),
        Column("Width", "number", c2_data),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and execution with single column + subgroup size
    dlg = CapabilityDialog(p.worksheet, w)
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
    opt_dlg.combo_ctype.setCurrentIndex(0)  # Two-sided
    opt_dlg.chk_ccpk.setChecked(True)
    opt_dlg._accept()
    dlg.options.update(opt_dlg.options)

    # Estimate subdialog
    est_dlg = CapabilityEstimateDialog(dlg.options, parent=dlg)
    est_dlg.rb_pooled.setChecked(True)
    est_dlg.chk_unbias_within.setChecked(True)
    est_dlg._accept()
    dlg.options.update(est_dlg.options)

    dlg._accept()
    assert dlg.selected_params is not None

    entry = p.normal_capability(settings=dlg.selected_params)
    assert entry is not None
    res = entry.get("result", {})
    assert res.get("sample_n") == 100
    assert res.get("subgroup_count") == 20
    assert res.get("cp") is not None
    assert res.get("cpk") is not None
    assert res.get("pp") is not None
    assert res.get("ppk") is not None
    assert res.get("cpm") is not None
    assert res.get("ccpk") is not None
    assert res.get("ci_cp") is not None
    assert res.get("ci_cpk") is not None

    # Verify report formatting
    report = format_entry(entry)
    assert "Process Capability Report" in report
    assert "Process Data" in report
    assert "Potential (Within) Capability" in report
    assert "Overall Capability" in report
    assert "Performance (parts per million)" in report
    assert "Cp" in report
    assert "Cpk" in report
    assert "Pp" in report
    assert "Ppk" in report

    # 2. Test chart widget rendering
    chart_widget = CapabilityPlotWidget(entry)
    chart_widget.resize(800, 600)
    img = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    chart_widget.render(img)
    assert not img.isNull()
    assert img.width() == 800
    assert img.height() == 600

    # 3. Test single column with subgroup indicator column
    settings_sub_col = {
        "single_column": True,
        "column_name": "Thickness",
        "subgroup_spec": "Subgroup",
        "lsl": 12.0,
        "usl": 18.0,
        "options": {"target": 15.0, "tolerance_k": 6.0}
    }
    entry_sub_col = p.normal_capability(settings=settings_sub_col)
    assert entry_sub_col["result"]["subgroup_count"] == 20

    # 4. Test subgroups across rows of columns
    settings_across = {
        "single_column": False,
        "cols_across": ["Thickness", "Width"],
        "lsl": 12.0,
        "usl": 18.0,
        "options": {"tolerance_k": 6.0}
    }
    entry_across = p.normal_capability(settings=settings_across)
    assert entry_across["result"]["subgroup_count"] == 100
    assert entry_across["result"]["subgroup_avg_size"] == 2.0

    # 5. UI presentation in ModernStatCraft
    w.show_result(entry)
    assert w.selected_entry is entry
