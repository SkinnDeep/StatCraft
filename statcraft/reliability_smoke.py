"""Verification gate for native StatCraft.6 Reliability Distribution Analysis."""

import os
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .reliability_dialogs import ReliabilityDistributionDialog
from .reliability_chart import ReliabilityPlotWidget
from .recipes import run as rerun_recipe


def verify_reliability_distribution(app, p, w, temp, checkpoint):
    checkpoint("Reliability Distribution Analysis (Weibull & Lognormal Right-Censoring) dialog, report, plot, and MPX rerun")
    p.new()

    np.random.seed(42)
    # 50 positive failure/censor times
    lifetimes = (np.random.weibull(1.7, 50) * 150.0 + 5.0).round(2).tolist()
    # Censor indicator: 1 = failure, 0 = right-censored
    censors = [0 if (i % 4 == 0) else 1 for i in range(50)]

    p.worksheet = Worksheet("ReliabilityDemo", [
        Column("Hours", "number", lifetimes),
        Column("Status", "number", censors),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and parameter selection
    dlg = ReliabilityDistributionDialog(p.worksheet, w)
    dlg.edit_var.setText("Hours")
    dlg.combo_dist.setCurrentIndex(0)  # Weibull
    dlg.edit_censor_col.setText("Status")
    dlg.edit_censor_val.setText("0")
    dlg._on_ok()

    assert dlg.selected_params is not None
    assert dlg.selected_params["dist_name"] == "weibull"
    assert dlg.selected_params["censor_index"] == 1

    # 2. Presenter execution
    entry = p.reliability_distribution(settings=dlg.selected_params)
    assert entry is not None
    assert entry["recipe"]["action"] == "reliability_distribution"
    res = entry["result"]
    assert res["analysis"] == "reliability_distribution"
    assert res["dist_name"] == "weibull"
    assert res["n_total"] == 50
    assert res["n_censored"] > 0
    assert "shape" in res["parameters"]
    assert "scale" in res["parameters"]
    assert len(res["percentile_table"]) == 6

    # 3. Report generation
    rep = format_entry(entry)
    assert "Distribution Analysis: Hours" in rep
    assert "Censoring Information" in rep
    assert "Table of Parameters" in rep
    assert "Table of Percentiles" in rep

    # 4. Chart Widget rendering
    widget = ReliabilityPlotWidget(entry, parent=w)
    widget.resize(800, 600)
    img = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    widget.render(img)
    assert not img.isNull()

    w.show_result(entry)
    assert w.selected_entry is entry

    # 5. MPX Roundtrip & Recipe Rerun
    mpx_path = os.path.join(temp, "reliability_distribution_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) == 1
    entry_loaded = p2.history[0]
    assert entry_loaded["result"].get("analysis") == "reliability_distribution"

    rerun_res = rerun_recipe(p2, entry_loaded["recipe"])
    assert rerun_res is not None
    assert rerun_res["result"].get("analysis") == "reliability_distribution"
    assert np.isclose(rerun_res["result"]["mttf"], res["mttf"])
