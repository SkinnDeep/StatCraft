"""Generate between/within capability demonstration project and verified images."""
import os
import sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
TEMP=ROOT/'work'/'bw-capability-artifact-temp'
TEMP.mkdir(exist_ok=True)
os.environ['TEMP']=str(TEMP)
os.environ['TMP']=str(TEMP)
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(ROOT/'work/statcraft-build-deps'),str(ROOT/'work/statcraft')]

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.capability_dialogs import CapabilityDialog
from statcraft.capability_chart import CapabilityPlotWidget
from statcraft.verification_fonts import load_verification_fonts


def main():
    app=QApplication.instance() or QApplication(sys.argv)
    load_verification_fonts(app)
    np.random.seed(101)

    # 25 batches of 5 parts = 125 observations
    thickness = []
    batch = []
    for b in range(25):
        batch_effect = np.random.normal(0, 1.2)
        for _ in range(5):
            thickness.append(round(50.0 + batch_effect + np.random.normal(0, 0.6), 3))
            batch.append(b + 1)

    p = Presenter()
    p.worksheet = Worksheet('Coating Process', [
        Column('Thickness', 'number', thickness),
        Column('Batch', 'number', batch),
    ])

    settings = {
        'analysis_mode': 'between_within',
        'single_column': True,
        'column_name': 'Thickness',
        'subgroup_spec': 'Batch',
        'lsl': 45.0,
        'usl': 55.0,
        'options': {'target': 50.0, 'tolerance_k': 6.0, 'include_ci': True}
    }
    entry = p.normal_capability(settings=settings)

    outputs = ROOT / 'outputs'
    outputs.mkdir(exist_ok=True)
    project = outputs / 'StatCraft-between-within-capability-demo.mpx'
    p.save(project)

    w = ModernWindow(p)
    w.resize(1280, 900)
    w.show()
    w.show_result(entry)
    app.processEvents()

    chart = w._active_chart_widget
    if chart is None or type(chart).__name__ != 'CapabilityPlotWidget':
        raise AssertionError('Real output path did not instantiate CapabilityPlotWidget.')
    chart.resize(1100, 740)
    app.processEvents()
    assert chart.grab().save(str(outputs / 'StatCraft-between-within-capability.png'))

    dialog = CapabilityDialog(p.worksheet, w, analysis_mode='between_within')
    dialog.edit_single_col.setText('Thickness')
    dialog.edit_sub_size.setText('Batch')
    dialog.edit_lsl.setText('45.0')
    dialog.edit_usl.setText('55.0')
    dialog.show()
    app.processEvents()
    assert dialog.grab().save(str(outputs / 'StatCraft-between-within-capability-dialog.png'))
    dialog.close()
    p.dirty = False
    p._results_dirty = False
    w.close()

    q = Presenter()
    q.load(project)
    assert len(q.history) == 1
    res = q.history[0]['result']
    assert res.get('analysis_mode') == 'between_within'
    assert res.get('sample_n') == 125
    assert res.get('subgroup_count') == 25
    print('Created between/within capability demo MPX and two verified images.')


if __name__ == '__main__':
    main()
