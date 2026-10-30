"""Verification gate for native StatCraft.6 Acceptance Control Charts."""

import os
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .acceptance_dialogs import AcceptanceControlChartDialog, AcceptanceOptionsDialog
from .acceptance_chart import AcceptanceControlChartWidget
from .recipes import run as rerun_recipe


def verify_acceptance_control_chart(app, p, w, temp, checkpoint):
    checkpoint("Acceptance Control Chart (Stat > Control Charts > Variables Charts for Subgroups > Acceptance Control Chart...) dialog, report, plot, and MPX rerun")
    p.new()

    np.random.seed(42)
    # 25 subgroups of size 5: N(100, 1.2), LSL = 85, USL = 115 (high capability)
    subgroups = []
    measurements = []
    c2_data = []
    for g in range(25):
        # Slight mean shift well within acceptance limits
        g_center = 100.0 + np.random.normal(0, 0.8)
        for i in range(5):
            val = round(g_center + np.random.normal(0, 0.9), 3)
            measurements.append(val)
            subgroups.append(g + 1)
            c2_data.append(val + 0.1)

    p.worksheet = Worksheet("AcceptanceDemo", [
        Column("Diameter", "number", measurements),
        Column("Subgroup", "number", subgroups),
        Column("Diameter2", "number", c2_data),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and validation
    dlg = AcceptanceControlChartDialog(p.worksheet, w)
    assert dlg.windowTitle() == "Acceptance Control Chart"
    assert dlg.rb_single_col.isChecked()

    dlg.edit_single_col.setText("Diameter")
    dlg.edit_sub_size.setText("5")
    dlg.edit_lsl.setText("85.0")
    dlg.edit_usl.setText("115.0")
    dlg.edit_delta.setText("0.001")
    dlg.edit_alpha.setText("0.05")

    # Options subdialog
    opt_dlg = AcceptanceOptionsDialog(dlg.options, parent=dlg)
    opt_dlg.edit_target.setText("100.0")
    opt_dlg.rb_pooled.setChecked(True)
    opt_dlg._accept()
    dlg.options.update(opt_dlg.options)

    dlg._accept()
    assert dlg.selected_params is not None

    # 2. Presenter execution
    entry = p.acceptance_control_chart(settings=dlg.selected_params)
    assert entry is not None
    assert "Acceptance Control Chart" in entry["title"]

    res = entry.get("result", {})
    assert res.get("analysis") == "acceptance_control"
    assert res.get("sample_n") == 125
    assert res.get("subgroup_count") == 25
    assert res.get("uacl") is not None
    assert res.get("lacl") is not None
    assert res.get("apl_upper") is not None
    assert res.get("apl_lower") is not None
    assert res.get("center_line") == 100.0
    assert res.get("cp") is not None
    assert res["cp"] > 2.0

    # 3. Report formatting verification
    rep = format_entry(entry)
    assert "Acceptance Control Chart for Diameter" in rep
    assert "Process Parameters" in rep
    assert "Acceptance Control Limits" in rep
    assert "UACL" in rep
    assert "LACL" in rep
    assert "Test Results for Acceptance Control Chart" in rep

    # 4. Chart widget rendering verification
    chart_widget = AcceptanceControlChartWidget(entry)
    chart_widget.resize(800, 600)
    img = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    chart_widget.render(img)
    assert not img.isNull()
    assert img.width() == 800
    assert img.height() == 600

    # 5. UI presentation in ModernStatCraft
    w.show_result(entry)
    assert w.selected_entry is entry

    # 6. MPX project save, reopen, and rerun
    mpx_path = os.path.join(temp, "acceptance_chart_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) >= 1
    hist_entry = p2.history[-1]
    assert "Acceptance Control Chart" in hist_entry["title"]
    assert hist_entry["result"].get("analysis") == "acceptance_control"

    # Rerun recipe
    rerun_res = rerun_recipe(p2, hist_entry["recipe"])
    assert rerun_res is not None
    assert rerun_res["result"].get("analysis") == "acceptance_control"
    assert np.isclose(rerun_res["result"]["uacl"], res["uacl"])
    assert np.isclose(rerun_res["result"]["lacl"], res["lacl"])
