"""Source and frozen-package One-Way ANOVA acceptance."""
import copy
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .app import format_entry
from .model import Column, Worksheet
from .modern_charts import ChartWidget, supported
from .office_export import OfficeSnapshot, export_docx, export_pptx
from .oneway import oneway_settings
from .oneway_dialogs import (
    OneWayAnovaDialog,
    OneWayComparisonsDialog,
    OneWayGraphsDialog,
    OneWayOptionsDialog,
    OneWayResultsDialog,
    OneWayStorageDialog,
)
from .oneway_report import text_report


def fixture() -> Worksheet:
    tensile = [7.0, 7.0, 15.0, 11.0, 9.0, 12.0, 17.0, 12.0, 18.0, 18.0, 14.0, 18.0, 18.0, 19.0, 19.0]
    blend = ['Low', 'Low', 'Low', 'Low', 'Low', 'Med', 'Med', 'Med', 'Med', 'Med', 'High', 'High', 'High', 'High', 'High']
    return Worksheet(
        'FabricDurability',
        [
            Column('Tensile', 'number', tensile),
            Column('Blend', 'text', blend),
            Column('Cotton15', 'number', [7.0, 7.0, 15.0, 11.0, 9.0]),
            Column('Cotton20', 'number', [12.0, 17.0, 12.0, 18.0, 18.0]),
            Column('Cotton25', 'number', [14.0, 18.0, 18.0, 19.0, 19.0]),
        ],
    )


def verify_oneway_anova(app, p, w, temp, checkpoint):
    checkpoint('One-Way ANOVA stacked and unstacked modes, child dialogs, multiple comparisons, graphs, storage, and MPX persistence')
    p.new()
    p.worksheet = fixture()
    w.page = 0
    w.refresh()

    assert w.oneway_anova_action.isEnabled()

    # 1. Test OneWayAnovaDialog with stacked response and factor + all 5 child dialogs
    dlg = OneWayAnovaDialog(w)
    assert dlg.mode_combo.currentIndex() == 0  # Stacked
    dlg.response_edit.setText('C1')
    dlg.factor_edit.setText('C2')

    # Options dialog
    opt_dlg = OneWayOptionsDialog(dlg, dlg.options)
    opt_dlg.conf_edit.setText('95.0')
    opt_dlg.chk_equal_var.setChecked(True)
    opt_dlg.validate()
    dlg.options = opt_dlg.options

    # Comparisons dialog
    comp_dlg = OneWayComparisonsDialog(dlg, dlg.options, ['Low', 'Med', 'High'])
    comp_dlg.chk_tukey.setChecked(True)
    comp_dlg.chk_fisher.setChecked(True)
    comp_dlg.chk_dunnett.setChecked(True)
    comp_dlg.cbo_control.setCurrentText('Low')
    comp_dlg.chk_hsu.setChecked(True)
    comp_dlg.validate()
    dlg.options = comp_dlg.options

    # Graphs dialog
    gr_dlg = OneWayGraphsDialog(dlg, dlg.options)
    gr_dlg.chk_interval.setChecked(True)
    gr_dlg.rad_four.setChecked(True)
    gr_dlg.validate()
    dlg.options = gr_dlg.options

    # Results dialog
    res_dlg = OneWayResultsDialog(dlg, dlg.options)
    res_dlg.chk_method.setChecked(True)
    res_dlg.chk_factor.setChecked(True)
    res_dlg.chk_anova.setChecked(True)
    res_dlg.chk_summary.setChecked(True)
    res_dlg.chk_means.setChecked(True)
    res_dlg.validate()
    dlg.options = res_dlg.options

    # Storage dialog
    st_dlg = OneWayStorageDialog(dlg, dlg.options)
    st_dlg.chk_fits.setChecked(True)
    st_dlg.chk_res.setChecked(True)
    st_dlg.validate()
    dlg.options = st_dlg.options

    cols_before = len(p.worksheet.columns)
    dlg.validate()
    assert dlg.entry is not None
    assert dlg.entry['recipe']['action'] == 'oneway_anova'
    res = dlg.entry['result']
    assert res['analysis'] == 'oneway_anova'
    assert res['anova_table']['df_factor'] == 2
    assert res['anova_table']['df_error'] == 12
    assert abs(res['anova_table']['f_value'] - 9.5889) < 0.05
    assert 'tukey' in res['comparisons']
    assert 'fisher' in res['comparisons']
    assert 'dunnett' in res['comparisons']
    assert 'hsu_mcb' in res['comparisons']

    # Stored columns check: FITS and RESI
    cols_after = len(p.worksheet.columns)
    assert cols_after == cols_before + 2
    names = [c.name for c in p.worksheet.columns]
    assert 'FITS' in names
    assert 'RESI' in names

    # Chart check
    assert supported(dlg.entry)
    chart = ChartWidget(dlg.entry)
    assert len(chart.panels) >= 3  # Interval plot, differences, 4-in-1
    pix = chart.grab()
    assert not pix.isNull()
    assert pix.width() > 100

    # 2. Test Unstacked ANOVA
    entry_unstacked = p.oneway_anova_unstacked([2, 3, 4], options=oneway_settings({'confidence': 0.95}))
    assert entry_unstacked['recipe']['action'] == 'oneway_anova'
    assert entry_unstacked['result']['analysis'] == 'oneway_anova'
    assert abs(entry_unstacked['result']['anova_table']['f_value'] - 9.5889) < 0.05

    # 3. Test Text Report
    rep = text_report(res)
    assert 'One-way ANOVA: Tensile versus Blend' in rep
    assert 'Analysis of Variance' in rep
    assert 'Model Summary' in rep
    assert 'Tukey Pairwise Comparisons' in rep

    # 4. Test Column Moves and recipe remapping
    p.move_columns([0], destination='after_last')
    w.refresh()
    remap_params = p.history[0]['recipe']['parameters']
    assert remap_params['response_index'] != 0  # Tensile was moved from index 0

    # 5. Test MPX Save & Reopen
    mpx_file = Path(temp) / 'oneway_smoke_roundtrip.mpx'
    w.save_path(str(mpx_file))
    assert mpx_file.exists()

    p.new()
    w.load_path(str(mpx_file))
    assert len(p.history) >= 2
    reloaded_entry = p.history[0]
    assert reloaded_entry['recipe']['action'] == 'oneway_anova'
    assert supported(reloaded_entry)

    # 6. Test Office Export
    snap = OfficeSnapshot('One-Way ANOVA', rep)
    docx_file = Path(temp) / 'oneway_report.docx'
    pptx_file = Path(temp) / 'oneway_report.pptx'
    export_docx(str(docx_file), snap)
    export_pptx(str(pptx_file), snap)
    assert docx_file.exists() and docx_file.stat().st_size > 500
    assert pptx_file.exists() and pptx_file.stat().st_size > 500
