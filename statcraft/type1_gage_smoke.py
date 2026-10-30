"""Verification gate for native StatCraft Type 1 Gage Study (Stat > Quality Tools > Gage Study > Type 1 Gage Study)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .type1_gage_dialogs import Type1GageDialog, Type1GageInfoDialog, Type1GageOptionsDialog
from .type1_gage_chart import Type1GageChartWidget


def verify_type1_gage(app, p, w, temp, checkpoint):
    checkpoint("Type 1 Gage Study (Stat > Quality Tools > Gage Study > Type 1 Gage Study) native dialog, reports, and run chart widget")
    p.new()

    # 50 repeated measurements of a 100mm reference gage pin
    measurements = [
        100.02, 100.01, 100.03, 100.00, 99.98, 100.02, 100.04, 100.01, 100.02, 100.00,
        100.03, 100.01, 99.99, 100.02, 100.03, 100.05, 100.00, 100.02, 100.01, 100.03,
        99.98, 100.02, 100.01, 100.00, 100.03, 100.02, 100.04, 100.01, 100.00, 100.02,
        100.03, 99.99, 100.01, 100.02, 100.00, 100.04, 100.02, 100.01, 100.03, 99.98,
        100.01, 100.02, 100.00, 100.03, 100.02, 100.01, 100.04, 100.00, 100.02, 100.03,
    ]

    p.worksheet = Worksheet("GageStudyDemo", [
        Column("Diameter", "number", measurements),
    ])
    w.page = 0
    w.refresh()

    # -------------------------------------------------------------
    # 1. Dialog Configuration & Options
    # -------------------------------------------------------------
    dlg = Type1GageDialog(p.worksheet, initial_vars=["Diameter"], parent=w)
    dlg.edit_measurement.setText("Diameter")
    dlg.edit_reference.setText("100.0")
    dlg.radio_tol.setChecked(True)
    dlg.edit_tol.setText("0.5")

    dlg.gage_info = {
        "gage_name": "Micrometer-01",
        "date_of_study": "2026-10-22",
        "reported_by": "Quality Engineering",
        "misc": "Standard Calibration Check"
    }
    dlg.options = {
        "cg_percent": 20.0,
        "study_var": 6.0,
        "resolution": 0.005,
        "perform_bias_test": True,
        "title": "Type 1 Gage Study for Diameter (Micrometer-01)"
    }

    dlg._validate_and_accept()
    params = dlg.result_params
    assert params is not None
    assert params["measurement_index"] == 0
    assert params["reference"] == 100.0
    assert params["settings"]["tolerance_val"] == 0.5
    assert params["settings"]["tolerance_type"] == "tolerance"

    # -------------------------------------------------------------
    # 2. Presenter Execution & Numerical Parity Check
    # -------------------------------------------------------------
    entry = p.type1_gage(
        measurement_index=params["measurement_index"],
        reference=params["reference"],
        settings=params["settings"],
        measurement_name=params["measurement_name"]
    )
    assert entry is not None
    assert entry["recipe"]["action"] == "type1_gage"
    res = entry["result"]
    assert res["analysis"] == "type1_gage"
    assert res["n"] == 50
    assert res["reference"] == 100.0
    assert res["tolerance"] == 0.5
    assert res["mean"] > 100.0
    assert res["std"] > 0.0
    assert res["cg"] > 0.0
    assert res["cgk"] > 0.0
    assert res["pct_var_repeatability"] > 0.0
    assert res["pct_var_rep_and_bias"] >= res["pct_var_repeatability"]
    assert res["df"] == 49
    assert res["t_stat"] is not None
    assert 0.0 <= res["p_value"] <= 1.0
    assert res["resolution"] == 0.005

    # -------------------------------------------------------------
    # 3. Session Report Formatting
    # -------------------------------------------------------------
    rep = format_entry(entry)
    assert "Type 1 Gage Study for Diameter (Micrometer-01)" in rep
    assert "Gage name" in rep
    assert "Micrometer-01" in rep
    assert "Reference:  100" in rep
    assert "Tolerance:  0.5" in rep
    assert "Descriptive Statistics" in rep
    assert "Sample Size (N)" in rep
    assert "50" in rep
    assert "Bias Test" in rep
    assert "T-Statistic" in rep
    assert "Cg (Repeatability)" in rep
    assert "Cgk (Repeatability and Bias)" in rep

    # -------------------------------------------------------------
    # 4. Interactive Qt Graphic Widget Rendering
    # -------------------------------------------------------------
    widget = Type1GageChartWidget(entry)
    img = QImage(QSize(860, 520), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    widget.render(img)
    assert not img.isNull()

    artifact_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    if artifact_dir.exists():
        img.save(str(artifact_dir / "StatCraft-type1-gage-study.png"))

    checkpoint("Type 1 Gage Study verification passed successfully")
