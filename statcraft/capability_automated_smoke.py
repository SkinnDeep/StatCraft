"""Verification gate for native StatCraft.6 Nonparametric and Automated Capability Analysis."""

import os
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .capability_automated_dialogs import CapabilityNonparametricDialog, CapabilityAutomatedDialog
from .capability_automated_chart import NonparametricCapabilityPlotWidget
from .recipes import run as rerun_recipe


def verify_capability_automated(app, p, w, temp, checkpoint):
    checkpoint("Nonparametric & Automated Capability (Distribution Tournament & Empirical Percentiles) dialog, report, plot, and MPX rerun")
    p.new()

    np.random.seed(42)
    # 60 positive values from skewed distribution
    skewed_data = (np.random.weibull(1.8, 60) * 14.0 + 2.0).round(2).tolist()

    p.worksheet = Worksheet("AutoCapDemo", [
        Column("Strength", "number", skewed_data),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation for Nonparametric Capability
    dlg_nonp = CapabilityNonparametricDialog(p.worksheet, w)
    dlg_nonp.edit_single_col.setText("Strength")
    dlg_nonp.edit_lsl.setText("3.0")
    dlg_nonp.edit_usl.setText("38.0")
    dlg_nonp.chk_aiag_vda.setChecked(True)
    dlg_nonp._on_ok()

    assert dlg_nonp.selected_params is not None
    assert dlg_nonp.selected_params["naming_convention"] == "aiag_vda"

    # Presenter execution for Nonparametric Capability
    entry_nonp = p.capability_nonparametric(settings=dlg_nonp.selected_params)
    assert entry_nonp is not None
    assert entry_nonp["recipe"]["action"] == "capability_nonparametric"
    res_nonp = entry_nonp["result"]
    assert res_nonp["analysis"] == "capability_nonparametric"
    assert res_nonp["p_median"] > 0
    assert "cnp" in res_nonp["indices"]
    assert "cnpk" in res_nonp["indices"]

    rep_nonp = format_entry(entry_nonp)
    assert "Nonparametric Capability Analysis" in rep_nonp
    assert "Empirical Percentiles" in rep_nonp
    assert "Cnp:" in rep_nonp

    # Chart rendering
    widget_nonp = NonparametricCapabilityPlotWidget(entry_nonp, parent=w)
    widget_nonp.resize(800, 600)
    img = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    widget_nonp.render(img)
    assert not img.isNull()

    # 2. Automated Capability Analysis (Distribution Tournament)
    dlg_auto = CapabilityAutomatedDialog(p.worksheet, w)
    dlg_auto.edit_single_col.setText("Strength")
    dlg_auto.edit_lsl.setText("3.0")
    dlg_auto.edit_usl.setText("38.0")
    dlg_auto._on_ok()

    entry_auto = p.capability_automated(settings=dlg_auto.selected_params)
    assert entry_auto is not None
    assert entry_auto["recipe"]["action"] == "capability_automated"
    res_auto = entry_auto["result"]
    assert res_auto["analysis"] == "capability_automated"
    assert len(res_auto["tournament"]) >= 3
    assert "best_fit" in res_auto

    rep_auto = format_entry(entry_auto)
    assert "Automated Capability Analysis" in rep_auto
    assert "Goodness-of-Fit Tournament Summary" in rep_auto

    w.show_result(entry_auto)
    assert w.selected_entry is entry_auto

    # 3. MPX Roundtrip & Recipe Rerun
    mpx_path = os.path.join(temp, "capability_automated_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) == 2

    # Rerun nonparametric entry
    rerun_nonp = rerun_recipe(p2, p2.history[0]["recipe"])
    assert rerun_nonp is not None
    assert rerun_nonp["result"]["analysis"] == "capability_nonparametric"
    assert np.isclose(rerun_nonp["result"]["p_median"], res_nonp["p_median"])

    # Rerun automated entry
    rerun_auto = rerun_recipe(p2, p2.history[1]["recipe"])
    assert rerun_auto is not None
    assert rerun_auto["result"]["analysis"] == "capability_automated"
    assert rerun_auto["result"]["best_fit"]["distribution"] == res_auto["best_fit"]["distribution"]
