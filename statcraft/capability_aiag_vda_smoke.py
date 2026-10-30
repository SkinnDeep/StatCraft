"""Verification gate for native StatCraft.6 AIAG/VDA Standardized Capability and Machine Capability."""

import os
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .capability_dialogs import CapabilityDialog, CapabilityOptionsDialog
from .capability_chart import CapabilityPlotWidget
from .recipes import run as rerun_recipe


def verify_capability_aiag_vda(app, p, w, temp, checkpoint):
    checkpoint("AIAG/VDA Standardized Capability (Machine Capability Cm/Cmk and Between/Within Cbw/Cbwk) dialog, report, plot, and MPX rerun")
    p.new()

    np.random.seed(101)
    # 50 continuous parts from single CNC machine: N(50.0, 0.75), LSL=46.0, USL=54.0
    measurements = [round(x, 3) for x in np.random.normal(50.0, 0.75, 50)]

    p.worksheet = Worksheet("MachineStudy", [
        Column("Diameter", "number", measurements),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and validation for Machine Capability
    dlg = CapabilityDialog(p.worksheet, w, analysis_mode="normal", study_type="machine", naming_convention="aiag_vda")
    assert dlg.windowTitle() == "Machine Capability Analysis (Normal Distribution)"
    assert dlg.rb_single_col.isChecked()

    dlg.edit_single_col.setText("Diameter")
    dlg.edit_sub_size.setText("1")
    dlg.edit_lsl.setText("46.0")
    dlg.edit_usl.setText("54.0")

    # Options subdialog
    opt_dlg = CapabilityOptionsDialog(dlg.options, parent=dlg)
    opt_dlg.edit_target.setText("50.0")
    opt_dlg.chk_include_ci.setChecked(True)
    opt_dlg.rb_aiag_vda.setChecked(True)
    opt_dlg._accept()
    dlg.options.update(opt_dlg.options)

    dlg._accept()
    assert dlg.selected_params is not None
    assert dlg.selected_params.get("study_type") == "machine"
    assert dlg.selected_params.get("naming_convention") == "aiag_vda"

    # 2. Presenter execution
    entry = p.normal_capability(settings=dlg.selected_params)
    assert entry is not None
    assert "Machine Capability" in entry["title"]

    res = entry.get("result", {})
    assert res.get("analysis") == "capability"
    assert res.get("study_type") == "machine"
    assert res.get("naming_convention") == "aiag_vda"
    assert res.get("sample_n") == 50
    assert res.get("cm") is not None
    assert res.get("cmk") is not None
    assert res.get("ci_cm") is not None
    assert res.get("ci_cmk") is not None

    # 3. Report formatting verification
    rep = format_entry(entry)
    assert "Machine Capability Report for Diameter" in rep
    assert "Machine Capability" in rep
    assert "Cm" in rep
    assert "Cmk" in rep
    assert "Overall Capability" in rep
    assert "Pp" in rep
    assert "Ppk" in rep

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
    mpx_path = os.path.join(temp, "machine_capa_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) >= 1
    hist_entry = p2.history[-1]
    assert "Machine Capability" in hist_entry["title"]
    assert hist_entry["result"].get("study_type") == "machine"

    # Rerun recipe
    rerun_res = rerun_recipe(p2, hist_entry["recipe"])
    assert rerun_res is not None
    assert rerun_res["result"].get("study_type") == "machine"
    assert np.isclose(rerun_res["result"]["cm"], res["cm"])
    assert np.isclose(rerun_res["result"]["cmk"], res["cmk"])
