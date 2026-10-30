"""Generate AIAG/VDA and Machine capability demonstration project and verified images."""
import os
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEMP = ROOT / 'work' / 'aiag-vda-artifact-temp'
TEMP.mkdir(exist_ok=True)
os.environ['TEMP'] = str(TEMP)
os.environ['TMP'] = str(TEMP)
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path[:0] = [str(ROOT / 'work/statcraft-build-deps'), str(ROOT / 'work/statcraft')]

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet, Column
from statcraft.modern_app import ModernWindow
from statcraft.capability_dialogs import CapabilityDialog
from statcraft.capability_chart import CapabilityPlotWidget
from statcraft.verification_fonts import load_verification_fonts


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    load_verification_fonts(app)
    np.random.seed(101)

    # 50 parts machined on a high-precision CNC lathe: N(50.0, 0.72)
    diameter = [round(x, 3) for x in np.random.normal(50.0, 0.72, 50)]

    p = Presenter()
    p.worksheet = Worksheet('CNC Lathe Study', [
        Column('Diameter', 'number', diameter),
    ])

    settings = {
        'analysis_mode': 'normal',
        'study_type': 'machine',
        'single_column': True,
        'column_name': 'Diameter',
        'subgroup_spec': 1,
        'lsl': 46.0,
        'usl': 54.0,
        'options': {
            'target': 50.0,
            'tolerance_k': 6.0,
            'include_ci': True,
            'naming_convention': 'aiag_vda',
            'study_type': 'machine',
        }
    }
    entry = p.normal_capability(settings=settings)

    outputs = ROOT / 'outputs'
    outputs.mkdir(exist_ok=True)
    project = outputs / 'StatCraft-capability-aiag-vda-demo.mpx'
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
    assert chart.grab().save(str(outputs / 'StatCraft-machine-capability.png'))

    dialog = CapabilityDialog(p.worksheet, w, analysis_mode='normal', study_type='machine', naming_convention='aiag_vda')
    dialog.edit_single_col.setText('Diameter')
    dialog.edit_sub_size.setText('1')
    dialog.edit_lsl.setText('46.0')
    dialog.edit_usl.setText('54.0')
    dialog.show()
    app.processEvents()
    assert dialog.grab().save(str(outputs / 'StatCraft-machine-capability-dialog.png'))
    dialog.close()

    p.dirty = False
    p._results_dirty = False
    w.close()

    q = Presenter()
    q.load(project)
    assert len(q.history) == 1
    res = q.history[0]['result']
    assert res.get('study_type') == 'machine'
    assert res.get('naming_convention') == 'aiag_vda'
    assert res.get('sample_n') == 50
    assert res.get('cm') is not None
    assert res.get('cmk') is not None
    print('Created AIAG/VDA machine capability demo MPX and two verified images.')


if __name__ == '__main__':
    main()
