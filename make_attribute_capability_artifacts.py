"""Generate original attribute capability demonstration project and verified images."""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TEMP=ROOT/'work'/'attribute-capability-artifact-temp'
TEMP.mkdir(exist_ok=True)
os.environ['TEMP']=str(TEMP)
os.environ['TMP']=str(TEMP)
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path[:0]=[str(ROOT/'work/statcraft-build-deps'),str(ROOT/'work/statcraft')]

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.attribute_capability_dialogs import AttributeCapabilityDialog
from statcraft.verification_fonts import load_verification_fonts


def main():
    app=QApplication.instance() or QApplication(sys.argv)
    load_verification_fonts(app)
    p=Presenter()
    p.worksheet=Worksheet('Attribute Capability',[
        Column('Unanswered Calls',values=[4,1,3,5,2,4,8,1,3,2,None,3,2,1,4,3,2,4,1,3,4,2,1,2]),
        Column('Total Calls',values=[47,39,55,67,45,43,39,40,38,46,42,40,43,51,44,46,40,43,48,51,45,42,46,50]),
        Column('Surface Defects',values=[2,3,1,4,2,0,3,None,1,3,2,1,4,2,1,3,2,1,2,4,3,1,2,1]),
        Column('Inspected Area',values=[2.4,2.8,2.5,3.1,2.6,2.5,2.4,2.8,2.6,2.4,2.7,2.8,2.7,2.9,2.5,2.8,2.7,2.5,2.7,2.9,2.8,2.6,2.5,2.8])])
    binomial=p.attribute_capability('binomial',0,size_index=1,options={'target':.05})
    p.attribute_capability('poisson',2,size_index=3,options={'target':1.0})
    outputs=ROOT/'outputs';outputs.mkdir(exist_ok=True)
    project=outputs/'StatCraft-attribute-capability-demo.mpx'
    p.save(project)
    w=ModernWindow(p);w.resize(1280,900);w.show();w.show_result(binomial);app.processEvents()
    chart=w._active_chart_widget
    if chart is None or type(chart).__name__!='AttributeCapabilityChartWidget':
        raise AssertionError('Real output path did not instantiate attribute capability chart.')
    chart.resize(1100,740);app.processEvents()
    assert chart.grab().save(str(outputs/'StatCraft-attribute-capability.png'))
    dialog=AttributeCapabilityDialog(w,p.worksheet,'binomial')
    dialog.controls['count_index'].setText('C1: "Unanswered Calls"')
    dialog.controls['size_mode'].setCurrentIndex(1)
    dialog.controls['size_index'].setText('C2: "Total Calls"')
    dialog.controls['target'].setText('5')
    dialog.show();app.processEvents()
    assert dialog.grab().save(str(outputs/'StatCraft-attribute-capability-dialog.png'))
    assert dialog.get_configuration()['size_index']==1
    dialog.close();p.dirty=False;p._results_dirty=False;w.close()
    q=Presenter();q.load(project)
    assert len(q.history)==2
    for entry in list(q.history):
        assert q.rerun_result(entry)['result']['n_samples']==23
    print('Created attribute capability demo MPX and two images; real-window chart and saved reruns verified.')


if __name__=='__main__':main()
