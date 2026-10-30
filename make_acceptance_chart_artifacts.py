"""Generate acceptance control chart demonstration project and verified images."""
import os
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEMP = ROOT / 'work' / 'acc-chart-artifact-temp'
TEMP.mkdir(exist_ok=True)
os.environ['TEMP'] = str(TEMP)
os.environ['TMP'] = str(TEMP)
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path[:0] = [str(ROOT / 'work/statcraft-build-deps'), str(ROOT / 'work/statcraft')]

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet, Column
from statcraft.modern_app import ModernWindow
from statcraft.acceptance_dialogs import AcceptanceControlChartDialog
from statcraft.acceptance_chart import AcceptanceControlChartWidget
from statcraft.verification_fonts import load_verification_fonts


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    load_verification_fonts(app)
    np.random.seed(42)

    # 25 subgroups of size 5: N(100, 1.0), LSL = 85, USL = 115
    measurements = []
    subgroups = []
    for g in range(25):
        # Center varies slightly between batches
        g_center = 100.0 + np.random.normal(0, 0.7)
        for _ in range(5):
            measurements.append(round(g_center + np.random.normal(0, 0.8), 3))
            subgroups.append(g + 1)

    p = Presenter()
    p.worksheet = Worksheet('Precision Machining', [
        Column('Diameter', 'number', measurements),
        Column('Subgroup', 'number', subgroups),
    ])

    settings = {
        'single_column': True,
        'column_name': 'Diameter',
        'subgroup_size': 5,
        'lsl': 85.0,
        'usl': 115.0,
        'delta': 0.001,
        'alpha': 0.05,
        'options': {
            'target': 100.0,
            'sigma_method': 'pooled_std',
        }
    }
    entry = p.acceptance_control_chart(settings=settings)

    outputs = ROOT / 'outputs'
    outputs.mkdir(exist_ok=True)
    project = outputs / 'StatCraft-acceptance-chart-demo.mpx'
    p.save(project)

    w = ModernWindow(p)
    w.resize(1280, 900)
    w.show()
    w.show_result(entry)
    app.processEvents()

    chart = w._active_chart_widget
    if chart is None or type(chart).__name__ != 'AcceptanceControlChartWidget':
        raise AssertionError(f'Real output path did not instantiate AcceptanceControlChartWidget, got {type(chart)}')
    chart.resize(1100, 740)
    app.processEvents()
    assert chart.grab().save(str(outputs / 'StatCraft-acceptance-control-chart.png'))

    dialog = AcceptanceControlChartDialog(p.worksheet, w)
    dialog.edit_single_col.setText('Diameter')
    dialog.edit_sub_size.setText('5')
    dialog.edit_lsl.setText('85.0')
    dialog.edit_usl.setText('115.0')
    dialog.edit_delta.setText('0.001')
    dialog.edit_alpha.setText('0.05')
    dialog.show()
    app.processEvents()
    assert dialog.grab().save(str(outputs / 'StatCraft-acceptance-control-dialog.png'))
    dialog.close()

    p.dirty = False
    p._results_dirty = False
    w.close()

    q = Presenter()
    q.load(project)
    assert len(q.history) == 1
    res = q.history[0]['result']
    assert res.get('analysis') == 'acceptance_control'
    assert res.get('sample_n') == 125
    assert res.get('subgroup_count') == 25
    print('Created acceptance control chart demo MPX and two verified images.')


if __name__ == '__main__':
    main()
