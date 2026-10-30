"""Verification gate for native StatCraft Multivariate Control Charts (T-Squared, Generalized Variance, MEWMA)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .multivariate_control_dialogs import MultivariateChartDialog, MultivariateOptionsDialog
from .multivariate_control_chart import MultivariateControlChartWidget


def verify_multivariate_control(app, p, w, temp, checkpoint):
    checkpoint("Multivariate Control Charts (Stat > Control Charts > Multivariate Charts > T², Generalized Variance, MEWMA) native dialogs, reports, and chart widget")
    p.new()

    # Create multivariate test dataset with 3 variables across 20 observations
    # Injected outlier at observation 15 in Temperature to trigger Test 1 signal
    temp_data = [
        98.2, 99.1, 98.6, 97.9, 98.4, 98.8, 99.3, 98.5, 98.1, 98.7,
        99.0, 98.3, 98.9, 98.4, 112.5, 98.6, 98.2, 98.8, 99.1, 98.5,
    ]
    press_data = [
        25.1, 24.8, 25.3, 25.0, 24.9, 25.2, 25.4, 25.0, 24.7, 25.1,
        25.3, 24.9, 25.0, 25.2, 28.6, 25.1, 24.8, 25.2, 25.0, 24.9,
    ]
    yield_data = [
        84.5, 85.1, 84.8, 85.0, 84.6, 85.3, 85.5, 84.9, 84.7, 85.2,
        85.4, 84.8, 85.1, 85.0, 72.1, 84.9, 85.2, 85.0, 84.8, 85.3,
    ]
    sg_ids = [
        1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5,
    ]

    p.worksheet = Worksheet("ChemicalProcess", [
        Column("Temperature", "number", temp_data),
        Column("Pressure", "number", press_data),
        Column("Yield", "number", yield_data),
        Column("BatchID", "number", sg_ids),
    ])
    w.page = 0
    w.refresh()

    # -------------------------------------------------------------
    # 1. Hotelling's T-Squared Chart Dialog & Execution (Individual obs)
    # -------------------------------------------------------------
    dlg_t2 = MultivariateChartDialog(p.worksheet, chart_type="TSQUARED", parent=w)
    dlg_t2.edit_vars.setText("Temperature Pressure Yield")
    dlg_t2.edit_subgroup.setText("1")

    opt_t2 = MultivariateOptionsDialog("TSQUARED", dlg_t2.options, parent=dlg_t2)
    opt_t2.edit_alpha.setText("0.0027")
    opt_t2._save_and_accept()
    dlg_t2.options = opt_t2.options

    dlg_t2._on_accept()
    cfg_t2 = dlg_t2.get_configuration()
    assert cfg_t2["chart_type"] == "TSQUARED"
    assert cfg_t2["variable_names"] == ["Temperature", "Pressure", "Yield"]

    entry_t2 = p.multivariate_control_chart(settings=cfg_t2)
    assert entry_t2 is not None
    assert entry_t2["recipe"]["action"] == "multivariate_control_chart"
    res_t2 = entry_t2["result"]
    assert res_t2["analysis"] == "multivariate_control"
    assert res_t2["chart_type"] == "TSQUARED"
    assert res_t2["k_subgroups"] == 20
    assert res_t2["p_variables"] == 3
    assert res_t2["ucl_val"] > 0
    # Observation 15 should trigger Test 1 signal
    assert 15 in res_t2["signals"]
    assert 15 in res_t2["decompositions"]
    # Check variable decompositions
    decomps = res_t2["decompositions"][15]
    assert "Temperature" in decomps and "Pressure" in decomps and "Yield" in decomps

    # Report verification
    rep_t2 = format_entry(entry_t2)
    assert "T² Control Chart of Temperature, Pressure, Yield" in rep_t2
    assert "Mean Vector" in rep_t2
    assert "Covariance Matrix" in rep_t2
    assert "Test 1: One point beyond control limits." in rep_t2
    assert "Individual Variable Contributions" in rep_t2

    # Chart Widget render & Artifact capture
    widget_t2 = MultivariateControlChartWidget(entry_t2)
    img_t2 = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_t2.fill(Qt.GlobalColor.white)
    widget_t2.render(img_t2)
    assert not img_t2.isNull()

    artifact_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    if artifact_dir.exists():
        img_t2.save(str(artifact_dir / "StatCraft-multivariate-control-chart.png"))

    # -------------------------------------------------------------
    # 2. Generalized Variance Chart Dialog & Execution (Subgroups of 4)
    # -------------------------------------------------------------
    dlg_gv = MultivariateChartDialog(p.worksheet, chart_type="GENVAR", parent=w)
    dlg_gv.edit_vars.setText("Temperature Pressure Yield")
    dlg_gv.edit_subgroup.setText("4")

    opt_gv = MultivariateOptionsDialog("GENVAR", dlg_gv.options, parent=dlg_gv)
    opt_gv.edit_k_sigma.setText("3.0")
    opt_gv._save_and_accept()
    dlg_gv.options = opt_gv.options

    dlg_gv._on_accept()
    cfg_gv = dlg_gv.get_configuration()
    assert cfg_gv["chart_type"] == "GENVAR"

    entry_gv = p.multivariate_control_chart(settings=cfg_gv)
    assert entry_gv is not None
    res_gv = entry_gv["result"]
    assert res_gv["analysis"] == "multivariate_control"
    assert res_gv["chart_type"] == "GENVAR"
    assert res_gv["k_subgroups"] == 5
    assert res_gv["center_line"] >= 0
    assert res_gv["ucl_val"] > res_gv["center_line"]

    rep_gv = format_entry(entry_gv)
    assert "Generalized Variance Chart of Temperature, Pressure, Yield" in rep_gv
    assert "Pooled Covariance Matrix" in rep_gv or "Covariance Matrix" in rep_gv

    widget_gv = MultivariateControlChartWidget(entry_gv)
    img_gv = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_gv.fill(Qt.GlobalColor.white)
    widget_gv.render(img_gv)
    assert not img_gv.isNull()

    # -------------------------------------------------------------
    # 3. Multivariate EWMA (MEWMA) Chart Dialog & Execution
    # -------------------------------------------------------------
    dlg_mewma = MultivariateChartDialog(p.worksheet, chart_type="MEWMA", parent=w)
    dlg_mewma.edit_vars.setText("Temperature Pressure Yield")
    dlg_mewma.edit_subgroup.setText("1")
    dlg_mewma.edit_weight.setText("0.2")
    dlg_mewma.edit_arl.setText("200.0")

    opt_mewma = MultivariateOptionsDialog("MEWMA", dlg_mewma.options, parent=dlg_mewma)
    opt_mewma.edit_weight.setText("0.2")
    opt_mewma.edit_arl.setText("200.0")
    opt_mewma.edit_omit.setText("15")
    opt_mewma._save_and_accept()
    dlg_mewma.options = opt_mewma.options

    dlg_mewma._on_accept()
    cfg_mewma = dlg_mewma.get_configuration()
    assert cfg_mewma["chart_type"] == "MEWMA"
    assert cfg_mewma["options"]["weight"] == 0.2
    assert cfg_mewma["options"]["arl"] == 200.0
    assert cfg_mewma["options"]["omit_subgroups"] == "15"

    entry_mewma = p.multivariate_control_chart(settings=cfg_mewma)
    assert entry_mewma is not None
    res_mewma = entry_mewma["result"]
    assert res_mewma["analysis"] == "multivariate_control"
    assert res_mewma["chart_type"] == "MEWMA"
    assert res_mewma["k_subgroups"] == 20
    assert res_mewma["ucl_val"] > 0
    # Outlier at 15 should cause MEWMA signal
    assert 15 in res_mewma["signals"] or 16 in res_mewma["signals"]

    rep_mewma = format_entry(entry_mewma)
    assert "Multivariate EWMA Chart of Temperature, Pressure, Yield" in rep_mewma
    assert "Weight (r):" in rep_mewma

    widget_mewma = MultivariateControlChartWidget(entry_mewma)
    img_mewma = QImage(QSize(820, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img_mewma.fill(Qt.GlobalColor.white)
    widget_mewma.render(img_mewma)
    assert not img_mewma.isNull()

    checkpoint("Multivariate Control Charts verification passed successfully")
