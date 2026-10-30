"""Verification gate for native StatCraft.6 Advanced MSA (Nested Gage R&R, Gage Linearity & Bias, Attribute Agreement)."""

import os
from pathlib import Path
import numpy as np
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .msa_dialogs import GageRRNestedDialog, GageLinearityDialog, AttributeAgreementDialog
from .msa_charts import NestedGageRRChartWidget, GageLinearityChartWidget, AttributeAgreementChartWidget
from .recipes import run as rerun_recipe


def verify_msa_advanced(app, p, w, temp, checkpoint):
    checkpoint("Advanced MSA (Nested Gage R&R, Gage Linearity & Bias, Attribute Agreement) dialogs, reports, plots, and MPX rerun")
    p.new()

    # 1. Dataset for Nested Gage R&R
    # 2 operators, 2 parts per operator, 3 replicates per part = 12 observations
    ops_nested = ["Op1"] * 6 + ["Op2"] * 6
    parts_nested = ["P1", "P1", "P1", "P2", "P2", "P2", "P3", "P3", "P3", "P4", "P4", "P4"]
    meas_nested = [
        10.1, 10.2, 10.1,
        12.0, 12.1, 11.9,
        10.5, 10.4, 10.6,
        12.5, 12.6, 12.4,
    ]

    # Reference & measurement data for Linearity & Bias
    ref_vals = [2.0, 2.0, 4.0, 4.0, 6.0, 6.0, 8.0, 8.0, 10.0, 10.0, 10.0, 10.0]
    meas_lin = [2.1, 2.08, 4.15, 4.22, 6.31, 6.28, 8.42, 8.45, 10.55, 10.60, 10.52, 10.58]

    # Attribute ratings & standard
    attr_ratings = ["Pass", "Pass", "Pass", "Fail", "Fail", "Fail", "Pass", "Pass", "Pass", "Fail", "Fail", "Pass"]
    attr_standards = ["Pass", "Pass", "Pass", "Fail", "Fail", "Fail", "Pass", "Pass", "Pass", "Fail", "Fail", "Fail"]

    p.worksheet = Worksheet("MSADemo", [
        Column("Operator", "text", ops_nested),
        Column("Part", "text", parts_nested),
        Column("Measurement", "number", meas_nested),
        Column("Reference", "number", ref_vals),
        Column("MeasLinearity", "number", meas_lin),
        Column("Rating", "text", attr_ratings),
        Column("Standard", "text", attr_standards),
    ])
    w.page = 0
    w.refresh()

    # --- Part 1: Nested Gage R&R ---
    dlg_nested = GageRRNestedDialog(p.worksheet, w)
    dlg_nested.edit_part.setText("Part")
    dlg_nested.edit_op.setText("Operator")
    dlg_nested.edit_meas.setText("Measurement")
    dlg_nested.options["tolerance"] = 6.0
    dlg_nested._on_ok()

    assert dlg_nested.selected_params is not None
    entry_nested = p.nested_gage_rr(**dlg_nested.selected_params)
    assert entry_nested is not None
    assert entry_nested["recipe"]["action"] == "nested_gage_rr"
    res_nested = entry_nested["result"]
    assert res_nested["analysis"] == "nested_gage_rr"
    assert res_nested["operators_count"] == 2
    assert res_nested["parts_per_operator"] == 2
    assert res_nested["replicates_per_part"] == 3
    assert res_nested["ndc"] is not None and res_nested["ndc"] >= 1

    rep_nested = format_entry(entry_nested)
    assert "Gage R&R Study (Nested)" in rep_nested
    assert "Analysis of Variance for Nested Design" in rep_nested
    assert "Distinct Categories" in rep_nested

    chart_nested = NestedGageRRChartWidget(res_nested, parent=w)
    chart_nested.resize(750, 500)
    img1 = QImage(QSize(750, 500), QImage.Format.Format_ARGB32_Premultiplied)
    img1.fill(Qt.GlobalColor.white)
    chart_nested.render(img1)
    assert not img1.isNull()

    # Save artifact demo
    img1.save("outputs/StatCraft-gage-rr-nested.png")

    # --- Part 2: Gage Linearity and Bias Study ---
    dlg_lin = GageLinearityDialog(p.worksheet, w)
    dlg_lin.edit_ref.setText("Reference")
    dlg_lin.edit_meas.setText("MeasLinearity")
    dlg_lin.edit_pv.setText("8.0")
    dlg_lin._on_ok()

    assert dlg_lin.selected_params is not None
    entry_lin = p.gage_linearity(**dlg_lin.selected_params)
    assert entry_lin is not None
    assert entry_lin["recipe"]["action"] == "gage_linearity"
    res_lin = entry_lin["result"]
    assert res_lin["analysis"] == "gage_linearity_and_bias"
    assert res_lin["pct_linearity"] > 0
    assert len(res_lin["bias_table"]) == 5

    rep_lin = format_entry(entry_lin)
    assert "Gage Linearity and Bias Study" in rep_lin
    assert "Gage Bias Table by Reference Value" in rep_lin
    assert "Overall Gage Bias" in rep_lin

    chart_lin = GageLinearityChartWidget(res_lin, parent=w)
    chart_lin.resize(700, 450)
    img2 = QImage(QSize(700, 450), QImage.Format.Format_ARGB32_Premultiplied)
    img2.fill(Qt.GlobalColor.white)
    chart_lin.render(img2)
    assert not img2.isNull()

    # Save artifact demo
    img2.save("outputs/StatCraft-gage-linearity-bias.png")

    # --- Part 3: Attribute Agreement Analysis ---
    dlg_attr = AttributeAgreementDialog(p.worksheet, w)
    dlg_attr.edit_meas.setText("Rating")
    dlg_attr.edit_sample.setText("Part")
    dlg_attr.edit_app.setText("Operator")
    dlg_attr.edit_std.setText("Standard")
    dlg_attr._on_ok()

    assert dlg_attr.selected_params is not None
    entry_attr = p.attribute_agreement(**dlg_attr.selected_params)
    assert entry_attr is not None
    assert entry_attr["recipe"]["action"] == "attribute_agreement"
    res_attr = entry_attr["result"]
    assert res_attr["analysis"] == "attribute_agreement_analysis"
    assert len(res_attr["within_appraiser"]) == 2
    assert len(res_attr["appraiser_vs_standard"]) == 2
    assert "between_appraisers" in res_attr

    rep_attr = format_entry(entry_attr)
    assert "Attribute Agreement Analysis" in rep_attr
    assert "Within Appraiser Agreement" in rep_attr
    assert "Between Appraisers Agreement" in rep_attr

    chart_attr = AttributeAgreementChartWidget(res_attr, parent=w)
    chart_attr.resize(650, 400)
    img3 = QImage(QSize(650, 400), QImage.Format.Format_ARGB32_Premultiplied)
    img3.fill(Qt.GlobalColor.white)
    chart_attr.render(img3)
    assert not img3.isNull()

    # Save artifact demo
    img3.save("outputs/StatCraft-attribute-agreement.png")

    # Display in window
    w.show_result(entry_nested)
    assert w.selected_entry is entry_nested

    # --- Part 4: MPX Persistence & Recipe Replay ---
    mpx_path = os.path.join(temp, "msa_advanced_test.mpx")
    p.save(mpx_path)
    assert os.path.exists(mpx_path)

    p2 = Presenter()
    p2.load(mpx_path)
    assert len(p2.history) == 3

    # Rerun Nested Gage R&R
    rerun1 = rerun_recipe(p2, p2.history[0]["recipe"])
    assert rerun1 is not None
    assert rerun1["result"]["analysis"] == "nested_gage_rr"
    assert rerun1["result"]["ndc"] == res_nested["ndc"]

    # Rerun Linearity & Bias
    rerun2 = rerun_recipe(p2, p2.history[1]["recipe"])
    assert rerun2 is not None
    assert rerun2["result"]["analysis"] == "gage_linearity_and_bias"
    assert np.isclose(rerun2["result"]["pct_linearity"], res_lin["pct_linearity"])

    # Rerun Attribute Agreement
    rerun3 = rerun_recipe(p2, p2.history[2]["recipe"])
    assert rerun3 is not None
    assert rerun3["result"]["analysis"] == "attribute_agreement_analysis"
    assert len(rerun3["result"]["within_appraiser"]) == 2
