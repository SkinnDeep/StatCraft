"""Smoke verification test for Power and Sample Size (Stat > Power and Sample Size)."""

from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from .power_dialogs import (
    OneSampleZPowerDialog,
    OneSampleTPowerDialog,
    TwoSampleTPowerDialog,
    PairedTPowerDialog,
    OneProportionPowerDialog,
    TwoProportionsPowerDialog,
    OneWayAnovaPowerDialog,
    FactorialPowerDialog,
)
from .power_chart import PowerCurveWidget
from .recipes import run as run_recipe


def verify_power(app, p, w, temp, checkpoint):
    """Smoke test verifying power & sample size dialogs, calculations, charts, and MPX persistence."""
    checkpoint("Power and Sample Size (Stat > Power and Sample Size) dialogs, reports, and charts")
    p.new()
    w.page = 0
    w.refresh()

    # 1. Dialog Smoke Tests
    dlg_1z = OneSampleZPowerDialog(parent=w)
    dlg_1z.edit_diffs.setText("1.0 2.0")
    dlg_1z.edit_target_powers.setText("0.8 0.9")
    dlg_1z._validate_and_accept()
    st_1z = dlg_1z.settings
    assert st_1z["differences"] == [1.0, 2.0]
    dlg_1z.close()

    dlg_1t = OneSampleTPowerDialog(parent=w)
    dlg_1t.edit_diffs.setText("1.0 2.0")
    dlg_1t._validate_and_accept()
    dlg_1t.close()

    dlg_2t = TwoSampleTPowerDialog(parent=w)
    dlg_2t.edit_diffs.setText("1.0 2.0")
    dlg_2t._validate_and_accept()
    dlg_2t.close()

    dlg_pt = PairedTPowerDialog(parent=w)
    dlg_pt.edit_diffs.setText("1.0 2.0")
    dlg_pt._validate_and_accept()
    dlg_pt.close()

    dlg_1p = OneProportionPowerDialog(parent=w)
    dlg_1p.edit_props.setText("0.6 0.7")
    dlg_1p._validate_and_accept()
    dlg_1p.close()

    dlg_2p = TwoProportionsPowerDialog(parent=w)
    dlg_2p.edit_p1.setText("0.6 0.7")
    dlg_2p._validate_and_accept()
    dlg_2p.close()

    dlg_a = OneWayAnovaPowerDialog(parent=w)
    dlg_a.edit_max_diffs.setText("1.0 1.5")
    dlg_a._validate_and_accept()
    dlg_a.close()

    dlg_f = FactorialPowerDialog(parent=w)
    dlg_f.edit_effects.setText("1.0 2.0")
    dlg_f._validate_and_accept()
    dlg_f.close()

    # 2. Presenter Execution & Statistical Assertions
    # 2a. 1-Sample Z
    entry_1z = p.one_sample_z_power(settings={"differences": [1.0, 2.0], "target_powers": [0.8, 0.9], "sigma": 1.0})
    assert entry_1z is not None
    assert entry_1z["result"]["analysis"] == "one_sample_z_power"
    assert len(entry_1z["result"]["rows"]) == 4

    # 2b. 1-Sample t
    entry_1t = p.one_sample_t_power(settings={"differences": [1.0], "target_powers": [0.8], "sigma": 1.0})
    assert entry_1t is not None
    assert entry_1t["result"]["analysis"] == "one_sample_t_power"
    assert entry_1t["result"]["rows"][0]["sample_size"] == 10

    # 2c. 2-Sample t
    entry_2t = p.two_sample_t_power(settings={"differences": [1.0], "target_powers": [0.8], "sigma": 1.0})
    assert entry_2t is not None
    assert entry_2t["result"]["analysis"] == "two_sample_t_power"
    assert entry_2t["result"]["rows"][0]["sample_size"] == 17

    # 2d. Paired t
    entry_pt = p.paired_t_power(settings={"differences": [1.0], "target_powers": [0.8], "stdev_diff": 1.0})
    assert entry_pt is not None
    assert entry_pt["result"]["analysis"] == "paired_t_power"

    # 2e. 1 Proportion
    entry_1p = p.one_proportion_power(settings={"comparison_proportions": [0.7], "baseline_p0": 0.5, "target_powers": [0.8]})
    assert entry_1p is not None
    assert entry_1p["result"]["analysis"] == "one_proportion_power"

    # 2f. 2 Proportions
    entry_2p = p.two_proportions_power(settings={"p1_values": [0.7], "p2": 0.5, "target_powers": [0.8]})
    assert entry_2p is not None
    assert entry_2p["result"]["analysis"] == "two_proportions_power"

    # 2g. One-Way ANOVA
    entry_a = p.oneway_anova_power(settings={"levels": 4, "max_differences": [1.5], "target_powers": [0.8], "sigma": 1.0})
    assert entry_a is not None
    assert entry_a["result"]["analysis"] == "oneway_anova_power"
    assert entry_a["result"]["rows"][0]["sample_size"] == 11

    # 2h. 2-Level Factorial
    entry_f = p.factorial_power(settings={"factors": 3, "corner_points": 8, "effects": [1.5], "target_powers": [0.8], "sigma": 1.0})
    assert entry_f is not None
    assert entry_f["result"]["analysis"] == "factorial_power"

    # 3. Chart Rendering Smoke Tests
    brain_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    chart_pow = PowerCurveWidget(entry_1z)
    chart_pow.resize(760, 480)
    img_pow = QImage(QSize(760, 480), QImage.Format.Format_ARGB32_Premultiplied)
    chart_pow.render(img_pow)
    if brain_dir.exists():
        img_pow.save(str(brain_dir / "StatCraft-power-curve.png"))

    # 4. Recipe Invariance & Rerun Roundtrip
    for entry in [entry_1z, entry_1t, entry_2t, entry_pt, entry_1p, entry_2p, entry_a, entry_f]:
        recipe = entry["recipe"]
        rerun_entry = run_recipe(p, recipe)
        assert rerun_entry["result"]["analysis"] == entry["result"]["analysis"]

    checkpoint("Power and Sample Size smoke test passed completely.")
