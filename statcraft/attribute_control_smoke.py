"""Verification gate for native StatCraft Attributes Control Charts (P, NP, C, U Charts)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .attribute_control_dialogs import AttributeChartDialog, AttributeOptionsDialog
from .attribute_control_chart import AttributeControlChartWidget


def verify_attribute_control(app, p, w, temp, checkpoint):
    checkpoint("Attributes Control Charts (Stat > Control Charts > Attributes Charts > P, NP, C, U, Laney P', Laney U') native dialogs, reports, and chart widget")
    p.new()

    # Create test worksheet with counts and sample sizes
    defective_counts = [5, 4, 6, 7, 3, 25, 4, 5, 6, 4, 5, 4, 6, 5, 4]  # Point 6 is an outlier spike
    subgroup_sizes = [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100]
    varying_sizes = [80, 100, 120, 90, 110, 100, 85, 95, 105, 115, 90, 100, 110, 95, 105]
    defect_counts = [2, 3, 1, 4, 2, 12, 3, 1, 2, 4, 3, 2, 1, 3, 2]

    p.worksheet = Worksheet("AttributeDemo", [
        Column("Defectives", "number", defective_counts),
        Column("SampleSize", "number", subgroup_sizes),
        Column("VaryingSize", "number", varying_sizes),
        Column("Defects", "number", defect_counts),
    ])
    w.page = 0
    w.refresh()

    # 1. P Chart Dialog instantiation and parameter selection
    dlg = AttributeChartDialog(p.worksheet, chart_type="P", parent=w)
    dlg.edit_vars.setText("Defectives")
    dlg.edit_subgroup.setText("SampleSize")

    # Options subdialog
    opt_dlg = AttributeOptionsDialog("P", dlg.options, parent=dlg)
    opt_dlg.combo_tests_mode.setCurrentIndex(1)  # Selected tests
    opt_dlg.chk_t1.setChecked(True)
    opt_dlg.chk_t2.setChecked(True)
    opt_dlg._accept()
    dlg.options = opt_dlg.options

    dlg._validate_and_accept()
    assert dlg.selected_params is not None
    assert dlg.selected_params["chart_type"] == "P"
    assert dlg.selected_params["variables"] == [0]

    # 2. Presenter execution - P Chart
    entry_p = p.attribute_control_chart(settings=dlg.selected_params)
    assert entry_p is not None
    assert entry_p["recipe"]["action"] == "attribute_control_chart"
    res_p = entry_p["result"]
    assert res_p["analysis"] == "attribute_control"
    assert res_p["chart"] == "P"
    assert res_p["n_subgroups"] == 15
    assert res_p["center"] > 0
    # Point 6 should fail Test 1
    assert 6 in res_p["test_failures"]
    assert 1 in res_p["test_failures"][6]

    # 3. Report generation
    report_p = format_entry(entry_p)
    assert "P Chart of Defectives" in report_p
    assert "Test Results for P Chart of Defectives" in report_p
    assert "TEST 1." in report_p
    assert "Process Information" in report_p

    # 4. Chart Widget rendering - P Chart
    widget_p = AttributeControlChartWidget(entry_p, parent=w)
    widget_p.resize(800, 500)
    w.show_result(entry_p)
    app.processEvents()

    img = QImage(QSize(800, 500), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    widget_p.render(img)
    assert not img.isNull()

    # 5. NP Chart execution
    np_params = {
        "chart_type": "NP",
        "variables": [0],
        "subgroup_size": 100,
        "is_subgroup_col": False,
        "options": {"k_sigma": 3.0, "tests": {"test1": {"enabled": True, "k": 3.0}}},
    }
    entry_np = p.attribute_control_chart(settings=np_params)
    assert entry_np is not None
    res_np = entry_np["result"]
    assert res_np["chart"] == "NP"
    assert res_np["center_lines"][0] > 0
    assert 6 in res_np["test_failures"]

    # 6. C Chart execution (no subgroup size needed)
    c_params = {
        "chart_type": "C",
        "variables": [3],
        "options": {"k_sigma": 3.0, "tests": {"test1": {"enabled": True, "k": 3.0}}},
    }
    entry_c = p.attribute_control_chart(settings=c_params)
    assert entry_c is not None
    res_c = entry_c["result"]
    assert res_c["chart"] == "C"
    assert res_c["constant_size"] == 1.0
    assert 6 in res_c["test_failures"]

    # 7. U Chart execution (with varying sample sizes)
    u_params = {
        "chart_type": "U",
        "variables": [3],
        "subgroup_col_idx": 2,
        "is_subgroup_col": True,
        "options": {"k_sigma": 3.0},
    }
    entry_u = p.attribute_control_chart(settings=u_params)
    assert entry_u is not None
    res_u = entry_u["result"]
    assert res_u["chart"] == "U"
    assert not res_u["is_constant_size"]

    # 7b. Laney P' Chart execution
    pprime_params = {
        "chart_type": "P'",
        "variables": [0],
        "subgroup_col_idx": 1,
        "is_subgroup_col": True,
        "options": {"k_sigma": 3.0},
    }
    entry_pprime = p.attribute_control_chart(settings=pprime_params)
    assert entry_pprime is not None
    assert entry_pprime["result"]["chart"] == "P'"
    assert entry_pprime["result"]["sigma_z"] > 0
    report_pprime = format_entry(entry_pprime)
    assert "Laney P' Chart of Defectives" in report_pprime
    assert "Sigma Z:" in report_pprime

    # 7c. Laney U' Chart execution
    uprime_params = {
        "chart_type": "U'",
        "variables": [3],
        "subgroup_col_idx": 2,
        "is_subgroup_col": True,
        "options": {"k_sigma": 3.0},
    }
    entry_uprime = p.attribute_control_chart(settings=uprime_params)
    assert entry_uprime is not None
    assert entry_uprime["result"]["chart"] == "U'"
    assert entry_uprime["result"]["sigma_z"] > 0
    report_uprime = format_entry(entry_uprime)
    assert "Laney U' Chart of Defects" in report_uprime
    assert "Sigma Z:" in report_uprime

    # 8. MPX Roundtrip & Recipe Rerun
    save_path = Path(temp) / "attribute_roundtrip.mpx"
    p.save(save_path)
    assert save_path.exists() and save_path.stat().st_size > 0

    p_reopen = Presenter()
    p_reopen.load(save_path)
    assert len(p_reopen.worksheet.columns) >= 4
    assert p_reopen.worksheet.columns[0].name == "Defectives"

    # 9. Save output artifacts
    out_dir = Path.cwd() / "outputs"
    if not out_dir.exists():
        for candidate in [Path(__file__).resolve().parents[3] / "outputs", Path(__file__).resolve().parents[2] / "outputs"]:
            if candidate.exists():
                out_dir = candidate
                break

    if out_dir.exists():
        snap_path = out_dir / "StatCraft-attributes-control-chart.png"
        img.save(str(snap_path))

        contracts_md = out_dir / "statcraft-attributes-control-contracts.md"
        contracts_md.write_text(
            "# Attributes Control Charts Parity Contracts\n\n"
            "## Supported Charts\n"
            "- P Chart: Defective item proportions with constant or varying subgroup sizes.\n"
            "- NP Chart: Defective item counts with specified constant subgroup size.\n"
            "- C Chart: Count of defects per unit of inspection (constant size = 1).\n"
            "- U Chart: Count of defects per unit with varying inspection exposure.\n\n"
            "## Statistical Formulas\n"
            "- P Chart: p = sum(x)/sum(n), sigma_i = sqrt(p(1-p)/n_i), UCL/LCL = p +/- K*sigma_i (clamped to [0, 1]).\n"
            "- NP Chart: CL = n*p, sigma = sqrt(n*p(1-p)), UCL/LCL = n*p +/- K*sigma.\n"
            "- C Chart: CL = c_bar, sigma = sqrt(c_bar), UCL/LCL = c_bar +/- K*sigma (LCL clamped >= 0).\n"
            "- U Chart: CL = u_bar, sigma_i = sqrt(u_bar/n_i), UCL/LCL = u_bar +/- K*sigma_i (LCL clamped >= 0).\n\n"
            "## Nelson Rules 1-4 Supported\n"
            "- Test 1: 1 point > K standard deviations from center line (default K=3.0).\n"
            "- Test 2: K points in a row on same side of center line (default K=9).\n"
            "- Test 3: K points in a row, all increasing or all decreasing (default K=6).\n"
            "- Test 4: K points in a row, alternating up and down (default K=14).\n",
            encoding="utf-8",
        )
