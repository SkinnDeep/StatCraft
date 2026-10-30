"""Verification gate for native StatCraft Between/Within Capability Analysis."""

import os
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .capability_dialogs import CapabilityDialog, CapabilityOptionsDialog
from .capability_chart import CapabilityPlotWidget
from .recipes import run as rerun_recipe


def verify_capability_between_within(app, p, w, temp, checkpoint):
    checkpoint("Between/Within Capability Analysis (Stat > Quality Tools > Capability Analysis > Between/Within...) dialog, report, plot, and MPX rerun")
    p.new()

    np.random.seed(42)
    # Generate 20 subgroups of size 5 with distinct between-subgroup variance
    subgroups = []
    measurements = []
    c2_data = []
    for g in range(20):
        g_center = 25.0 + np.random.normal(0, 1.2)
        for i in range(5):
            val = g_center + np.random.normal(0, 0.4)
            measurements.append(val)
            subgroups.append(g + 1)
            c2_data.append(val + 0.2)

    p.worksheet = Worksheet("BetweenWithinDemo", [
        Column("Diameter", "number", measurements),
        Column("Batch", "number", subgroups),
        Column("Diameter2", "number", c2_data),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and validation
    dlg = CapabilityDialog(p.worksheet, w, analysis_mode="between_within")
    assert dlg.windowTitle() == "Between/Within Capability Analysis"
    assert dlg.analysis_mode == "between_within"
    assert dlg.rb_single_col.isChecked()

    dlg.edit_single_col.setText("Diameter")
    dlg.edit_sub_size.setText("5")
    dlg.edit_lsl.setText("20.0")
    dlg.edit_usl.setText("30.0")

    # Options subdialog
    opt_dlg = CapabilityOptionsDialog(dlg.options, parent=dlg)
    opt_dlg.edit_k.setText("6.0")
    opt_dlg.edit_target.setText("25.0")
    opt_dlg.chk_include_ci.setChecked(True)
    opt_dlg._accept()
    dlg.options.update(opt_dlg.options)

    dlg._accept()
    assert dlg.selected_params is not None
    assert dlg.selected_params.get("analysis_mode") == "between_within"

    # 2. Presenter execution
    entry = p.normal_capability(settings=dlg.selected_params)
    assert entry is not None
    assert "Between/Within Capability" in entry["title"]

    res = entry.get("result", {})
    assert res.get("analysis_mode") == "between_within"
    assert res.get("sample_n") == 100
    assert res.get("subgroup_count") == 20
    assert res.get("stdev_between") is not None
    assert res.get("stdev_between_within") is not None
    assert res.get("stdev_within") is not None
    assert res.get("stdev_overall") is not None
    assert res.get("cp") is not None
    assert res.get("cpk") is not None
    assert res.get("pp") is not None
    assert res.get("ppk") is not None

    # 3. Report formatting verification
    rep = format_entry(entry)
    assert "Between/Within Capability Report for Diameter" in rep
    assert "Process Data" in rep
    assert "StDev(Between/Within)" in rep
    assert "StDev(Between)" in rep
    assert "StDev(Within)" in rep
    assert "StDev(Overall)" in rep
    assert "Potential (Between/Within) Capability" in rep
    assert 'Exp. "Between/Within"' in rep

    # 4. Chart widget rendering verification
    chart_widget = CapabilityPlotWidget(entry)
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
    mpx_path = os.path.join(temp, "between_within_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) >= 1
    hist_entry = p2.history[-1]
    assert "Between/Within Capability" in hist_entry["title"]
    assert hist_entry["result"].get("analysis_mode") == "between_within"

    # Rerun recipe
    rerun_res = rerun_recipe(p2, hist_entry["recipe"])
    assert rerun_res is not None
    assert rerun_res["result"].get("analysis_mode") == "between_within"
    assert np.isclose(rerun_res["result"]["stdev_between_within"], res["stdev_between_within"])
