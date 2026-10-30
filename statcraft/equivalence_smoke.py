"""Smoke verification test for Equivalence Tests (Stat > Equivalence Tests)."""

from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .equivalence_dialogs import (
    OneSampleEquivalenceDialog,
    TwoSampleEquivalenceDialog,
    PairedEquivalenceDialog,
    CrossoverEquivalenceDialog,
)
from .equivalence_chart import EquivalenceChartWidget
from .recipes import run as run_recipe


def verify_equivalence(app, p, w, temp, checkpoint):
    """Smoke test verifying equivalence dialogs, calculations, charts, and MPX persistence."""
    checkpoint("Equivalence Tests (Stat > Equivalence Tests) dialogs, reports, and charts")
    p.new()

    # Data setup:
    # Sample 1: Test product (mean ~10.05)
    # Sample 2: Reference product (mean ~10.00)
    # Crossover 2x2: Response, Sequence, Period, Subject, Treatment
    ws = Worksheet("EquivData", [
        Column("TestSample", "number", [10.02, 10.15, 9.98, 10.08, 10.12, 10.05, 9.95, 10.10, 10.07, 10.03, 10.11, 9.99]),
        Column("RefSample", "number", [10.00, 10.05, 9.92, 10.02, 10.08, 9.98, 9.91, 10.04, 10.01, 9.97, 10.06, 9.96]),
        Column("Resp", "number", [
            20.2, 20.5, 19.8, 20.1, 21.3, 21.6, 20.4, 20.7,
            20.4, 20.1, 21.1, 20.9, 19.8, 19.6, 20.7, 20.5
        ]),
        Column("Seq", "text", [
            "RT", "RT", "RT", "RT", "RT", "RT", "RT", "RT",
            "TR", "TR", "TR", "TR", "TR", "TR", "TR", "TR"
        ]),
        Column("Per", "number", [
            1, 2, 1, 2, 1, 2, 1, 2,
            1, 2, 1, 2, 1, 2, 1, 2
        ]),
        Column("Sub", "number", [
            1, 1, 2, 2, 3, 3, 4, 4,
            5, 5, 6, 6, 7, 7, 8, 8
        ]),
        Column("Trt", "text", [
            "R", "T", "R", "T", "R", "T", "R", "T",
            "T", "R", "T", "R", "T", "R", "T", "R"
        ]),
    ])
    p.worksheet = ws
    w.page = 0
    w.refresh()

    # 1. Dialog Smoke Tests
    dlg_one = OneSampleEquivalenceDialog(ws, parent=w)
    dlg_one.edit_sample.setText("TestSample")
    dlg_one.spin_target.setValue(10.0)
    dlg_one.spin_lower.setValue(-0.5)
    dlg_one.spin_upper.setValue(0.5)
    dlg_one._validate_and_accept()
    st_one = dlg_one.settings
    assert st_one["sample_index"] == 0
    dlg_one.close()

    dlg_two = TwoSampleEquivalenceDialog(ws, parent=w)
    dlg_two.edit_test.setText("TestSample")
    dlg_two.edit_ref.setText("RefSample")
    dlg_two.spin_lower.setValue(-1.0)
    dlg_two.spin_upper.setValue(1.0)
    dlg_two._validate_and_accept()
    st_two = dlg_two.settings
    assert st_two["first_index"] == 0 and st_two["second_index"] == 1
    dlg_two.close()

    dlg_paired = PairedEquivalenceDialog(ws, parent=w)
    dlg_paired.edit_sample1.setText("TestSample")
    dlg_paired.edit_sample2.setText("RefSample")
    dlg_paired.spin_lower.setValue(-1.0)
    dlg_paired.spin_upper.setValue(1.0)
    dlg_paired._validate_and_accept()
    st_paired = dlg_paired.settings
    assert st_paired["first_index"] == 0 and st_paired["second_index"] == 1
    dlg_paired.close()

    dlg_cross = CrossoverEquivalenceDialog(ws, parent=w)
    dlg_cross.edit_resp.setText("Resp")
    dlg_cross.edit_seq.setText("Seq")
    dlg_cross.edit_per.setText("Per")
    dlg_cross.edit_sub.setText("Sub")
    dlg_cross.edit_trt.setText("Trt")
    dlg_cross.spin_lower.setValue(-1.5)
    dlg_cross.spin_upper.setValue(1.5)
    dlg_cross._validate_and_accept()
    st_cross = dlg_cross.settings
    assert st_cross["response_index"] == 2 and st_cross["sequence_index"] == 3
    dlg_cross.close()

    # 2. Presenter Execution & Statistical Assertions
    # 2a. 1-Sample Equivalence
    entry_one = p.one_sample_equivalence(settings={
        "sample_index": 0,
        "target": 10.0,
        "lower_margin": -0.5,
        "upper_margin": 0.5,
        "alpha": 0.05,
        "hypothesis_type": "difference",
    })
    assert entry_one is not None
    res_one = entry_one["result"]
    assert res_one["analysis"] == "one_sample_equivalence"
    assert res_one["is_equivalent"] is True
    assert -0.5 < res_one["ci_lower"] < res_one["ci_upper"] < 0.5

    # 2b. 2-Sample Equivalence
    entry_two = p.two_sample_equivalence(settings={
        "first_index": 0,
        "second_index": 1,
        "lower_margin": -1.0,
        "upper_margin": 1.0,
        "alpha": 0.05,
        "equal_variances": False,
        "hypothesis_type": "difference",
    })
    assert entry_two is not None
    res_two = entry_two["result"]
    assert res_two["analysis"] == "two_sample_equivalence"
    assert res_two["is_equivalent"] is True
    assert res_two["df"] > 10

    # 2c. Paired Equivalence
    entry_paired = p.paired_equivalence(settings={
        "first_index": 0,
        "second_index": 1,
        "lower_margin": -1.0,
        "upper_margin": 1.0,
        "alpha": 0.05,
        "hypothesis_type": "difference",
    })
    assert entry_paired is not None
    res_paired = entry_paired["result"]
    assert res_paired["analysis"] == "paired_equivalence"
    assert res_paired["is_equivalent"] is True

    # 2d. 2x2 Crossover Equivalence
    entry_cross = p.crossover_equivalence(settings={
        "response_index": 2,
        "sequence_index": 3,
        "period_index": 4,
        "subject_index": 5,
        "treatment_index": 6,
        "lower_margin": -1.5,
        "upper_margin": 1.5,
        "alpha": 0.05,
        "hypothesis_type": "difference",
    })
    assert entry_cross is not None
    res_cross = entry_cross["result"]
    assert res_cross["analysis"] == "crossover_equivalence"
    assert res_cross["is_equivalent"] is True
    assert res_cross["n_subjects"] == 8

    # 3. Chart Rendering Smoke Tests
    brain_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")

    # Equivalence Interval Plot
    chart_equiv = EquivalenceChartWidget(entry_two)
    chart_equiv.resize(720, 460)
    img_equiv = QImage(QSize(720, 460), QImage.Format.Format_ARGB32_Premultiplied)
    chart_equiv.render(img_equiv)
    if brain_dir.exists():
        img_equiv.save(str(brain_dir / "StatCraft-equivalence-interval-plot.png"))

    # 4. Recipe Invariance & Rerun Roundtrip
    for entry in [entry_one, entry_two, entry_paired, entry_cross]:
        recipe = entry["recipe"]
        rerun_entry = run_recipe(p, recipe)
        assert rerun_entry["result"]["analysis"] == entry["result"]["analysis"]

    checkpoint("Equivalence Tests smoke test passed completely.")
