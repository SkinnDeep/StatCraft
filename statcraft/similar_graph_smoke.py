"""Desktop/frozen acceptance of the native-evidenced replacement workflow."""
import copy
from pathlib import Path
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QApplication,QTableWidgetItem,QDialogButtonBox
from .model import Worksheet,Column
from .recipes import run


def verify_similar_graph(app,p,w,temp,checkpoint):
    checkpoint('Make Similar original/new variable grid, source sheet and MPX')
    p.new();p.worksheet=Worksheet('Source graphs',[
        Column('Trial',values=[1,2,3,4,5,6]),Column('Strength',values=[3,5,6,9,11,12]),
        Column('Batch','text',['A','B','A','B','A','B']),Column('New response',values=[6,8,11,16,19,22])])
    source=p.scatter_plot(0,1,'regression_groups',2)
    p.update_graph_styles(source,{'p0:s0':{'color':'#de3421','marker':'diamond'}})
    p.add_worksheet('Another worksheet');before=copy.deepcopy(source);w.refresh()
    def replace():
        dialog=QApplication.activeModalWidget()
        assert [dialog.roles.horizontalHeaderItem(i).text() for i in range(3)]==['Role','Original Variable','New Variable']
        assert 'Strength' in dialog.roles.item(0,1).text()
        assert not dialog.roles.item(0,1).flags() & Qt.ItemFlag.ItemIsEditable
        dialog.roles.setItem(0,2,QTableWidgetItem('C4'))
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,replace);w.make_similar_graph(source);app.processEvents()
    created=p.history[-1];assert created is not source and source==before
    assert created['recipe']['parameters']['y_index']==3 and created['recipe']['parameters']['group_index']==2
    assert created['worksheet_id']==source['worksheet_id'] and p.native_project.active_index==0
    assert created['graph_styles']==source['graph_styles'] and created['entry_id']!=source['entry_id']
    assert w._active_chart_widget.error is None and not w._active_graph_frame.capture().isNull()
    count=len(p.history);QTimer.singleShot(0,lambda:QApplication.activeModalWidget().reject())
    w.make_similar_graph(source);assert len(p.history)==count
    target=Path(temp)/'similar-graph.mpx';w.save_path(target);w.load_path(target)
    saved=next(e for e in p.history if e['entry_id']==created['entry_id']);w.show_result(saved);app.processEvents()
    assert saved['graph_styles']==source['graph_styles'] and not p.result_stale(saved)
    hist=run(p,dict(action='graph',parameters=dict(method='histogram',indices=[1],bins=9)))
    p.update_histogram_settings(hist,{'bins':333,'scale':'Percent','fit':'Normal'})
    QTimer.singleShot(0,lambda:QApplication.activeModalWidget().buttons.button(QDialogButtonBox.StandardButton.Ok).click())
    w.make_similar_graph(hist);app.processEvents()
    assert p.history[-1]['histogram_settings']['bins']==333
    assert len(w._active_chart_widget.panels[0]['counts'])==333 and w._active_chart_widget.error is None
