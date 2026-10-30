"""Source and frozen-package Subgroup Control Charts (Xbar-R and Xbar-S) acceptance."""
import copy
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .app import format_entry
from .model import Column, Worksheet
from .modern_charts import ChartWidget, supported
from .office_export import OfficeSnapshot, export_docx, export_pptx
from .subgroup_control import control_chart_settings
from .subgroup_control_dialogs import (
    XbarRChartDialog,
    XbarSChartDialog,
    ControlChartOptionsDialog,
)
from .subgroup_control_report import text_report


def fixture() -> Worksheet:
    meas = [10.0, 11.0, 12.0, 11.0, 10.0,
            12.0, 13.0, 14.0, 13.0, 12.0,
            15.0, 16.0, 17.0, 16.0, 15.0,
            20.0, 21.0, 22.0, 21.0, 20.0]
    sub_id = ['B1']*5 + ['B2']*5 + ['B3']*5 + ['B4']*5
    return Worksheet(
        'QualityProcess',
        [
            Column('Diameter', 'number', meas),
            Column('Batch', 'text', sub_id),
            Column('S1', 'number', [10.0, 12.0, 15.0, 20.0]),
            Column('S2', 'number', [11.0, 13.0, 16.0, 21.0]),
            Column('S3', 'number', [12.0, 14.0, 17.0, 22.0]),
            Column('S4', 'number', [11.0, 13.0, 16.0, 21.0]),
            Column('S5', 'number', [10.0, 12.0, 15.0, 20.0]),
        ],
    )


def verify_subgroup_control(app, p, w, temp, checkpoint):
    checkpoint('Subgroup Control Charts Xbar-R and Xbar-S, 8 Nelson tests, options dialogs, storage, and MPX persistence')
    p.new()
    p.worksheet = fixture()
    w.page = 0
    w.refresh()

    assert w.xbar_r_action.isEnabled()
    assert w.xbar_s_action.isEnabled()

    # 1. Test XbarRChartDialog with stacked mode and child options
    dlg = XbarRChartDialog(w)
    assert dlg.combo_arrangement.currentIndex() == 0  # Stacked
    dlg.resp_edit.setText('C1')
    dlg.sub_size_edit.setText('C2')

    # Options dialog
    opt_dlg = ControlChartOptionsDialog(dlg, dlg.options, chart_type='xbar_r')
    opt_dlg.ksigma_edit.setText('3.0')
    opt_dlg.chk_perform_all.setChecked(True)
    opt_dlg.chk_s_points.setChecked(True)
    opt_dlg.chk_s_center.setChecked(True)
    opt_dlg.chk_s_limits.setChecked(True)
    opt_dlg.validate()
    dlg.options = opt_dlg.options
    assert dlg.options['tests']['test1']['enabled']
    assert dlg.options['tests']['test2']['enabled']
    assert dlg.options['storage']['points']

    cols_before = len(p.worksheet.columns)
    dlg.run_analysis()
    assert dlg.entry is not None
    assert dlg.entry['recipe']['action'] == 'subgroup_control_chart'
    res = dlg.entry['result']
    assert res['analysis'] == 'subgroup_control'
    assert res['chart_type'] == 'xbar_r'
    assert res['k_subgroups'] == 4
    assert abs(res['xbar_center'] - 15.05) < 1e-4
    assert len(res['means']) == 4

    # Storage check
    cols_after = len(p.worksheet.columns)
    assert cols_after >= cols_before + 3
    col_names = [c.name for c in p.worksheet.columns]
    assert any(c.startswith('XBAR') for c in col_names)
    assert any(c.startswith('RANGE') for c in col_names)

    # Chart check
    assert supported(dlg.entry)
    chart = ChartWidget(dlg.entry)
    assert len(chart.panels) == 2
    assert chart.panels[0]['subpanel'] == 'xbar'
    assert chart.panels[1]['subpanel'] == 'disp'
    pix = chart.grab()
    assert not pix.isNull()
    assert pix.width() > 100

    # 2. Test XbarSChartDialog in unstacked row columns mode
    dlg_s = XbarSChartDialog(w)
    dlg_s.combo_arrangement.setCurrentIndex(1)  # Unstacked
    dlg_s.rows_edit.setText('C3 C4 C5 C6 C7')
    dlg_s.run_analysis()
    assert dlg_s.entry is not None
    assert dlg_s.entry['recipe']['action'] == 'subgroup_control_chart'
    res_s = dlg_s.entry['result']
    assert res_s['analysis'] == 'subgroup_control'
    assert res_s['chart_type'] == 'xbar_s'
    assert res_s['k_subgroups'] == 4

    chart_s = ChartWidget(dlg_s.entry)
    assert len(chart_s.panels) == 2
    assert chart_s.panels[1]['subpanel'] == 'disp'
    assert 'S Chart' in chart_s.panels[1]['title']

    # 3. Test Text Report
    rep = text_report(res)
    assert 'Xbar-R Chart of Diameter' in rep
    assert 'Subgroup Information' in rep
    assert 'Process Parameters and Limit Estimates' in rep

    rep_s = text_report(res_s)
    assert 'Xbar-S Chart' in rep_s
    assert 'S Center Line' in rep_s

    # 4. Test Column Moves and recipe remapping
    p.move_columns([0], destination='after_last')
    w.refresh()
    remap_params = p.history[0]['recipe']['parameters']
    assert remap_params['response_index'] != 0  # Diameter was moved from index 0

    # 5. Test MPX Save & Reopen
    mpx_file = Path(temp) / 'subgroup_control_smoke_roundtrip.mpx'
    w.save_path(str(mpx_file))
    assert mpx_file.exists()

    p.new()
    w.load_path(str(mpx_file))
    assert len(p.history) >= 2
    reloaded_entry = p.history[0]
    assert reloaded_entry['recipe']['action'] == 'subgroup_control_chart'
    assert supported(reloaded_entry)

    # 6. Test Office Export
    snap = OfficeSnapshot('Xbar-R Chart', rep)
    docx_file = Path(temp) / 'xbar_r_report.docx'
    pptx_file = Path(temp) / 'xbar_r_report.pptx'
    export_docx(str(docx_file), snap)
    export_pptx(str(pptx_file), snap)
    assert docx_file.exists() and docx_file.stat().st_size > 500
    assert pptx_file.exists() and pptx_file.stat().st_size > 500
