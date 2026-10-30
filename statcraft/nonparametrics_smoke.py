"""Automated verification smoke test for Nonparametric Statistical Tests (Stat > Nonparametrics)."""
from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from .model import Column, Worksheet
from .nonparametrics_dialogs import (
    SignTestDialog,
    OneSampleWilcoxonDialog,
    MannWhitneyDialog,
    KruskalWallisDialog,
    MoodsMedianDialog,
    FriedmanDialog,
    RunsTestDialog,
    PairedWilcoxonDialog,
)
from .nonparametrics_chart import NonparametricChartWidget
from .recipes import run as run_recipe


def verify_nonparametrics(app, p, w, temp, checkpoint):
    """Smoke test verifying nonparametrics dialogs, calculations, charts, and MPX persistence."""
    checkpoint("Nonparametric Statistical Tests (Stat > Nonparametrics) dialogs, reports, and charts")
    p.new()

    ws = Worksheet("NonparamData", [
        Column("SampleA", "number", [1.5, 2.3, 3.1, 4.0, 5.2, 6.1, 7.8, 8.4, 9.2, 10.5, 11.2, 12.0]),
        Column("SampleB", "number", [2.1, 3.4, 4.5, 5.9, 6.8, 7.2, 8.0, 9.5, 10.1, 11.0, 11.8, 12.5]),
        Column("Factor", "text", ["Low", "Low", "Low", "Low", "Med", "Med", "Med", "Med", "High", "High", "High", "High"]),
        Column("Block", "text", ["B1", "B2", "B3", "B4", "B1", "B2", "B3", "B4", "B1", "B2", "B3", "B4"]),
    ])
    p.worksheet = ws
    w.page = 0
    w.refresh()

    # 1. Dialog Smoke Tests
    dlg_sign = SignTestDialog(ws, parent=w)
    dlg_sign.edit_vars.setText("SampleA")
    dlg_sign._on_accept()
    st_sign = dlg_sign.get_settings()
    assert st_sign["variable_indices"] == [0]
    dlg_sign.close()

    dlg_w = OneSampleWilcoxonDialog(ws, parent=w)
    dlg_w.edit_vars.setText("SampleA")
    dlg_w._on_accept()
    st_w = dlg_w.get_settings()
    assert st_w["variable_indices"] == [0]
    dlg_w.close()

    dlg_mw = MannWhitneyDialog(ws, parent=w)
    dlg_mw.edit_sample1.setText("SampleA")
    dlg_mw.edit_sample2.setText("SampleB")
    dlg_mw._on_accept()
    st_mw = dlg_mw.get_settings()
    assert st_mw["first_index"] == 0 and st_mw["second_index"] == 1
    dlg_mw.close()

    dlg_kw = KruskalWallisDialog(ws, parent=w)
    dlg_kw.edit_response.setText("SampleA")
    dlg_kw.edit_factor.setText("Factor")
    dlg_kw._on_accept()
    st_kw = dlg_kw.get_settings()
    assert st_kw["response_index"] == 0 and st_kw["factor_index"] == 2
    dlg_kw.close()

    dlg_mood = MoodsMedianDialog(ws, parent=w)
    dlg_mood.edit_response.setText("SampleA")
    dlg_mood.edit_factor.setText("Factor")
    dlg_mood._on_accept()
    st_mood = dlg_mood.get_settings()
    assert st_mood["response_index"] == 0 and st_mood["factor_index"] == 2
    dlg_mood.close()

    dlg_fr = FriedmanDialog(ws, parent=w)
    dlg_fr.edit_response.setText("SampleA")
    dlg_fr.edit_treatment.setText("Factor")
    dlg_fr.edit_blocks.setText("Block")
    dlg_fr._on_accept()
    st_fr = dlg_fr.get_settings()
    assert st_fr["response_index"] == 0 and st_fr["treatment_index"] == 2 and st_fr["block_index"] == 3
    dlg_fr.close()

    dlg_runs = RunsTestDialog(ws, parent=w)
    dlg_runs.edit_vars.setText("SampleA")
    dlg_runs._on_accept()
    st_runs = dlg_runs.get_settings()
    assert st_runs["variable_indices"] == [0]
    dlg_runs.close()

    dlg_pw = PairedWilcoxonDialog(ws, parent=w)
    dlg_pw.edit_sample1.setText("SampleA")
    dlg_pw.edit_sample2.setText("SampleB")
    dlg_pw._on_accept()
    st_pw = dlg_pw.get_settings()
    assert st_pw["first_index"] == 0 and st_pw["second_index"] == 1
    dlg_pw.close()

    # 2. Presenter Execution
    rec_sign = p.sign_test(settings=st_sign)
    assert rec_sign is not None and rec_sign["result"]["analysis"] == "sign_test"

    rec_w = p.one_sample_wilcoxon(settings=st_w)
    assert rec_w is not None and rec_w["result"]["analysis"] == "one_sample_wilcoxon"

    rec_mw = p.mann_whitney(settings=st_mw)
    assert rec_mw is not None and rec_mw["result"]["analysis"] == "mann_whitney"

    rec_kw = p.kruskal_wallis(settings=st_kw)
    assert rec_kw is not None and rec_kw["result"]["analysis"] == "kruskal_wallis"

    rec_mood = p.moods_median(settings=st_mood)
    assert rec_mood is not None and rec_mood["result"]["analysis"] == "moods_median"

    rec_fr = p.friedman_test(settings=st_fr)
    assert rec_fr is not None and rec_fr["result"]["analysis"] == "friedman_test"

    rec_runs = p.runs_test(settings=st_runs)
    assert rec_runs is not None and rec_runs["result"]["analysis"] == "runs_test"

    rec_pw = p.paired_wilcoxon(settings=st_pw)
    assert rec_pw is not None and rec_pw["result"]["analysis"] == "paired_wilcoxon"

    # 3. Chart Rendering to QImage & Visual Artifacts
    chart_mood = NonparametricChartWidget(rec_mood)
    chart_mood.resize(780, 480)
    img_mood = QImage(QSize(780, 480), QImage.Format.Format_ARGB32_Premultiplied)
    img_mood.fill(0xFFFFFF)
    chart_mood.render(img_mood)
    assert not img_mood.isNull()

    chart_runs = NonparametricChartWidget(rec_runs)
    chart_runs.resize(780, 480)
    img_runs = QImage(QSize(780, 480), QImage.Format.Format_ARGB32_Premultiplied)
    img_runs.fill(0xFFFFFF)
    chart_runs.render(img_runs)
    assert not img_runs.isNull()

    chart_kw = NonparametricChartWidget(rec_kw)
    chart_kw.resize(780, 480)
    img_kw = QImage(QSize(780, 480), QImage.Format.Format_ARGB32_Premultiplied)
    img_kw.fill(0xFFFFFF)
    chart_kw.render(img_kw)
    assert not img_kw.isNull()

    brain_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    if brain_dir.exists():
        img_mood.save(str(brain_dir / "StatCraft-moods-median-plot.png"))
        img_runs.save(str(brain_dir / "StatCraft-runs-test-plot.png"))
        img_kw.save(str(brain_dir / "StatCraft-nonparametric-tests.png"))

    # 4. MPX Persistence & Rerun Invariance
    mpx_file = Path(temp) / "test_nonparametrics.mpx"
    w.save_path(str(mpx_file))
    assert mpx_file.exists() and mpx_file.stat().st_size > 0

    w.load_path(str(mpx_file))
    app.processEvents()

    rerun_sign = run_recipe(p, rec_sign["recipe"])
    assert rerun_sign["result"]["median"] == rec_sign["result"]["median"]

    rerun_kw = run_recipe(p, rec_kw["recipe"])
    assert abs(rerun_kw["result"]["h_statistic"] - rec_kw["result"]["h_statistic"]) < 1e-9

    rerun_mood = run_recipe(p, rec_mood["recipe"])
    assert rerun_mood["result"]["overall_median"] == rec_mood["result"]["overall_median"]

    rerun_runs = run_recipe(p, rec_runs["recipe"])
    assert rerun_runs["result"]["runs"] == rec_runs["result"]["runs"]

    checkpoint("Nonparametric Statistical Tests verification passed successfully")
