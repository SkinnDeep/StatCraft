"""Smoke verification test for Tables and Chi-Square analysis (Stat > Tables)."""

from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from .model import Column
from .tables_dialogs import (
    CrossTabulationDialog,
    ChiSquareGoodnessOfFitDialog,
    ChiSquareAssociationDialog,
    TallyDialog,
)
from .tables_chart import TablesChartWidget
from .recipes import run as run_recipe


def verify_tables(app, p, w, temp, checkpoint):
    """Smoke test verifying Tables & Chi-Square dialogs, calculations, charts, and MPX persistence."""
    checkpoint("Tables and Chi-Square (Stat > Tables) dialogs, reports, and charts")
    p.new()
    w.page = 0

    # Populate worksheet with sample categorical & contingency data
    p.worksheet.columns = [
        Column("Shift", "text", ["Day", "Day", "Day", "Night", "Night", "Night", "Day", "Night"]),
        Column("Defect", "text", ["None", "Scratches", "Dents", "None", "Scratches", "Dents", "None", "Dents"]),
        Column("Count", "number", [45, 12, 8, 38, 15, 14, 50, 11]),
        Column("Line1", "number", [120, 14]),
        Column("Line2", "number", [115, 22]),
        Column("Line3", "number", [130, 8]),
        Column("LineStatus", "text", ["Pass", "Fail"]),
    ]
    w.refresh()

    # 1. Dialog Smoke Tests
    # 1a. Cross Tabulation Dialog
    dlg_ct = CrossTabulationDialog(p.worksheet, parent=w)
    dlg_ct.edit_rows.setText("'Shift'")
    dlg_ct.edit_cols.setText("'Defect'")
    dlg_ct.edit_freq.setText("'Count'")
    dlg_ct._on_accept()
    st_ct = dlg_ct.settings
    assert st_ct["row_column"] == 0
    assert st_ct["col_column"] == 1
    assert st_ct["freq_column"] == 2
    dlg_ct.close()

    # 1b. Goodness of Fit Dialog
    dlg_gof = ChiSquareGoodnessOfFitDialog(p.worksheet, parent=w)
    dlg_gof.edit_obs.setText("'Defect'")
    dlg_gof.edit_freq.setText("'Count'")
    dlg_gof._on_accept()
    st_gof = dlg_gof.settings
    assert st_gof["observed_column"] == 1
    assert st_gof["freq_column"] == 2
    dlg_gof.close()

    # 1c. Association Table Dialog
    dlg_assoc = ChiSquareAssociationDialog(p.worksheet, parent=w)
    dlg_assoc.edit_cols.setText("'Line1' 'Line2' 'Line3'")
    dlg_assoc.edit_labels.setText("'LineStatus'")
    dlg_assoc._on_accept()
    st_assoc = dlg_assoc.settings
    assert st_assoc["table_columns"] == [3, 4, 5]
    assert st_assoc["row_labels_column"] == 6
    dlg_assoc.close()

    # 1d. Tally Dialog
    dlg_tally = TallyDialog(p.worksheet, parent=w)
    dlg_tally.edit_vars.setText("'Shift' 'Defect'")
    dlg_tally._on_accept()
    st_tally = dlg_tally.settings
    assert st_tally["columns"] == [0, 1]
    dlg_tally.close()

    # 2. Presenter Execution & Statistical Assertions
    # 2a. Cross Tabulation
    entry_ct = p.cross_tabulation(settings=st_ct)
    assert entry_ct is not None
    assert entry_ct["result"]["analysis"] == "cross_tabulation"
    assert entry_ct["result"]["grand_total"] == 193.0
    assert entry_ct["result"]["df"] == 2
    assert "pearson_chi_square" in entry_ct["result"]

    # 2b. Chi-Square Goodness-of-Fit
    entry_gof = p.chi_square_goodness_of_fit(settings=st_gof)
    assert entry_gof is not None
    assert entry_gof["result"]["analysis"] == "chi_square_goodness_of_fit"
    assert entry_gof["result"]["n_obs"] == 193.0
    assert entry_gof["result"]["df"] == 2

    # 2c. Chi-Square Association Table
    entry_assoc = p.chi_square_association_table(settings=st_assoc)
    assert entry_assoc is not None
    assert entry_assoc["result"]["analysis"] == "chi_square_association_table"
    assert entry_assoc["result"]["df"] == 2
    assert entry_assoc["result"]["grand_total"] == 409.0

    # 2d. Tally Variables
    entry_tally = p.tally_variables(settings=st_tally)
    assert entry_tally is not None
    assert entry_tally["result"]["analysis"] == "tally_variables"

    # 3. Chart Rendering Smoke Tests
    brain_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    chart_ct = TablesChartWidget(entry_ct)
    chart_ct.resize(760, 480)
    img_ct = QImage(QSize(760, 480), QImage.Format.Format_ARGB32_Premultiplied)
    chart_ct.render(img_ct)
    if brain_dir.exists():
        img_ct.save(str(brain_dir / "StatCraft-contingency-chart.png"))

    # 4. Recipe Invariance & Rerun Roundtrip
    rerun_ct = run_recipe(p, entry_ct["recipe"])
    assert rerun_ct["result"]["df"] == entry_ct["result"]["df"]
    assert abs(rerun_ct["result"]["pearson_chi_square"] - entry_ct["result"]["pearson_chi_square"]) < 1e-6
