"""Verification gate for native StatCraft.6 Nonnormal Capability Analysis."""

import os
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .capability_nonnormal_dialogs import CapabilityNonnormalDialog
from .capability_nonnormal_chart import NonnormalCapabilityPlotWidget
from .recipes import run as rerun_recipe


def verify_capability_nonnormal(app, p, w, temp, checkpoint):
    checkpoint("Nonnormal Capability Analysis (Weibull & Box-Cox) dialog, report, plot, and MPX rerun")
    p.new()

    np.random.seed(42)
    # 60 positive values from Weibull distribution
    weibull_data = (np.random.weibull(1.8, 60) * 12.0 + 0.5).round(3).tolist()

    p.worksheet = Worksheet("NonnormalDemo", [
        Column("Lifespan", "number", weibull_data),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and parameter selection
    dlg = CapabilityNonnormalDialog(p.worksheet, w)
    dlg.edit_single_col.setText("Lifespan")
    dlg.combo_dist.setCurrentIndex(0)  # Weibull
    dlg.edit_lsl.setText("2.0")
    dlg.edit_usl.setText("30.0")
    dlg.chk_aiag_vda.setChecked(True)
    dlg._on_ok()

    assert dlg.selected_params is not None
    assert dlg.selected_params["dist_or_transform"] == "weibull"
    assert dlg.selected_params["naming_convention"] == "aiag_vda"

    # 2. Presenter execution
    entry = p.capability_nonnormal(settings=dlg.selected_params)
    assert entry is not None
    assert entry["recipe"]["action"] == "capability_nonnormal"
    res = entry["result"]
    assert res["analysis"] == "capability_nonnormal"
    assert res["method"] == "weibull"
    assert res["p_median"] > 0
    assert "cnp" in res["indices"]
    assert "cnpk" in res["indices"]

    # 3. Report generation
    rep = format_entry(entry)
    assert "Nonnormal Capability Analysis" in rep
    assert "Distribution Parameters" in rep
    assert "Cnp:" in rep
    assert "Cnpk:" in rep

    # 4. Chart Widget rendering
    widget = NonnormalCapabilityPlotWidget(entry, parent=w)
    widget.resize(800, 600)
    img = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    widget.render(img)
    assert not img.isNull()

    w.show_result(entry)
    assert w.selected_entry is entry

    # 5. MPX Roundtrip & Recipe Rerun
    mpx_path = os.path.join(temp, "nonnormal_capability_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) == 1
    entry_loaded = p2.history[0]
    assert entry_loaded["result"].get("analysis") == "capability_nonnormal"

    rerun_res = rerun_recipe(p2, entry_loaded["recipe"])
    assert rerun_res is not None
    assert rerun_res["result"].get("analysis") == "capability_nonnormal"
    assert np.isclose(rerun_res["result"]["p_median"], res["p_median"])
