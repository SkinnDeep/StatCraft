"""Verification gate for native StatCraft.6 Shewhart Extended Limits and Warning Bands."""

import os
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .modern_charts import ChartWidget
from .subgroup_control_dialogs import XbarRChartDialog, ControlChartOptionsDialog
from .imr_dialogs import IMRChartDialog, IMROptionsDialog
from .imr_chart import IMRChartWidget
from .recipes import run as rerun_recipe


def verify_shewhart_extended_limits(app, p, w, temp, checkpoint):
    checkpoint("Shewhart Extended Limits & Warning Bands (Xbar-R, Xbar-S, and I-MR) dialogs, reports, plots, and MPX rerun")
    p.new()

    np.random.seed(42)
    # 20 subgroups of size 5
    n_sub = 20
    sg_sz = 5
    total_pts = n_sub * sg_sz
    vals = np.random.normal(50.0, 2.0, total_pts).tolist()
    # Add shift at subgroup 12
    for i in range(11 * sg_sz, 12 * sg_sz):
        vals[i] += 5.0

    sg_ids = []
    for g in range(1, n_sub + 1):
        sg_ids.extend([g] * sg_sz)

    p.worksheet = Worksheet("ExtendedLimitsDemo", [
        Column("Measurement", "number", vals),
        Column("Subgroup", "number", sg_ids),
    ])
    w.page = 0
    w.refresh()

    # 1. Dialog instantiation and validation for Xbar-R Chart with Extended Limits
    dlg_xr = XbarRChartDialog(w)
    assert dlg_xr.windowTitle() == "Xbar-R Chart"
    dlg_xr.combo_arrangement.setCurrentIndex(0)  # Stacked
    dlg_xr.resp_edit.setText("Measurement")
    dlg_xr.sub_size_edit.setText("Subgroup")

    # Configure Limits Tab via Options dialog
    opt_dlg = ControlChartOptionsDialog(dlg_xr, dlg_xr.options, chart_type='xbar_r')
    opt_dlg.ksigma_edit.setText("1 2 3")
    opt_dlg.chk_warning.setChecked(True)
    opt_dlg.edit_warn_k.setText("2.0")
    opt_dlg.chk_zones.setChecked(True)
    opt_dlg.validate()
    dlg_xr.options.update(opt_dlg.options)

    dlg_xr.run_analysis()
    assert dlg_xr.entry is not None
    entry_xr = dlg_xr.entry
    res_xr = entry_xr["result"]

    assert 'xbar_uwl' in res_xr, "xbar_uwl missing in res_xr"
    assert 'xbar_lwl' in res_xr, "xbar_lwl missing in res_xr"
    assert 'disp_uwl' in res_xr, "disp_uwl missing in res_xr"
    assert 'disp_lwl' in res_xr, "disp_lwl missing in res_xr"
    assert res_xr['xbar_ucl'][0] > res_xr['xbar_uwl'][0] > res_xr['xbar_center']

    # Report verification
    rep_xr = format_entry(entry_xr)
    assert "Upper Warning Limit (UWL)" in rep_xr
    assert "Lower Warning Limit (LWL)" in rep_xr

    # Chart canvas rendering via ChartWidget
    chart_xr = ChartWidget(entry_xr)
    chart_xr.resize(800, 600)
    img_xr = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
    img_xr.fill(Qt.GlobalColor.white)
    chart_xr.render(img_xr)
    assert not img_xr.isNull()

    # 2. I-MR Chart with Warning Limits
    dlg_imr = IMRChartDialog(p.worksheet, w)
    dlg_imr.edit_vars.setText("Measurement")
    
    opt_imr = IMROptionsDialog(dlg_imr, dlg_imr.options)
    opt_imr.k_sigma_edit.setText("3.0")
    opt_imr.chk_warning.setChecked(True)
    opt_imr.edit_warn_k.setText("2.0")
    opt_imr.chk_zones.setChecked(True)
    opt_imr._save_and_accept()
    dlg_imr.options = opt_imr.options

    dlg_imr._on_ok()
    assert dlg_imr.selected_params is not None
    
    entry_imr = p.imr_chart(settings=dlg_imr.selected_params)
    res_imr = entry_imr["result"]

    assert 'i_uwl' in res_imr, "i_uwl missing in res_imr"
    assert 'i_lwl' in res_imr, "i_lwl missing in res_imr"
    assert 'mr_uwl' in res_imr, "mr_uwl missing in res_imr"
    assert 'mr_lwl' in res_imr, "mr_lwl missing in res_imr"

    rep_imr = format_entry(entry_imr)
    assert "I UWL:" in rep_imr
    assert "I LWL:" in rep_imr

    widget_imr = IMRChartWidget(entry_imr, parent=w)
    widget_imr.resize(800, 600)
    img_imr = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
    img_imr.fill(Qt.GlobalColor.white)
    widget_imr.render(img_imr)
    assert not img_imr.isNull()

    # 3. MPX project save, reopen, and rerun
    mpx_path = os.path.join(temp, "shewhart_extended_limits_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) == 2

    # Verify reload of Xbar-R
    entry_xr_loaded = p2.history[0]
    assert entry_xr_loaded["result"].get("analysis") == "subgroup_control"
    rerun_res = rerun_recipe(p2, entry_xr_loaded["recipe"])
    assert rerun_res is not None
    assert 'xbar_uwl' in rerun_res["result"]
    assert np.isclose(rerun_res["result"]["xbar_uwl"][0], res_xr["xbar_uwl"][0])

    # Verify reload of I-MR
    entry_imr_loaded = p2.history[1]
    assert entry_imr_loaded["result"].get("analysis") == "imr_control"
    rerun_imr = rerun_recipe(p2, entry_imr_loaded["recipe"])
    assert rerun_imr is not None
    assert 'i_uwl' in rerun_imr["result"]
    assert np.isclose(rerun_imr["result"]["i_uwl"], res_imr["i_uwl"])

    w.show_result(entry_imr)
    assert w.selected_entry is entry_imr
