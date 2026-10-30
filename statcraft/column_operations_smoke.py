"""Desktop/frozen acceptance of header operations and imported MPX columns."""
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QApplication,QListWidget,QRadioButton,QDialogButtonBox
from ._mpx_fixture import write_blob_fixture


def verify_column_operations(app,p,w,temp,checkpoint):
    checkpoint('header selections, insertion and moving used columns')
    p.new();p.add_worksheet('Column operations');p.rename_column(0,'Input');p.rename_column(1,'Response')
    p.set_cell(0,0,'2');p.set_cell(0,1,'4');p.assign_formula(2,'C1+C2')
    p.set_cell(1,0,'3');p.set_cell(1,1,'7');source_graph=p.scatter_plot(0,1)
    w.page=0;w.refresh();w.table.setColumnWidth(0,140);w._hidden_columns={1};w.refresh()
    w._select_column_header(0,Qt.KeyboardModifier.NoModifier)
    w._select_column_header(2,Qt.KeyboardModifier.ShiftModifier)
    assert w._selected_columns=={0,1,2}
    w._select_column_header(1,Qt.KeyboardModifier.ControlModifier)
    assert w._selected_columns=={0,2}
    w.insert_columns_action_handler()
    assert len(p.worksheet.columns)==18 and p.worksheet.columns[2].name=='Input'
    assert p.worksheet.columns[4].metadata['formula']=='C3+C4'
    assert source_graph['recipe']['parameters']['x_index']==2 and source_graph['recipe']['parameters']['y_index']==3
    assert w._selected_columns=={0,1}
    assert w.table.columnWidth(2)==140 and w._hidden_columns=={3}
    w.undo();app.processEvents();assert len(p.worksheet.columns)==16
    assert w.table.columnWidth(0)==140 and w._hidden_columns=={1}
    assert source_graph['recipe']['parameters']['x_index']==0 and source_graph['recipe']['parameters']['y_index']==1
    w.redo();app.processEvents();assert w._hidden_columns=={3}
    w.undo();app.processEvents();w.unhide_all_columns()
    # The name row can target a different column from the data grid.
    w.table.clearSelection();w._selected_columns=set();w.table.setCurrentCell(0,0)
    w.column_names.setFocus();w.column_names.setCurrentCell(0,4);w.column_names.clearSelection();w.column_names.setCurrentCell(0,4)
    w.insert_columns_action_handler();assert len(p.worksheet.columns)==17
    assert p.worksheet.columns[2].metadata['formula']=='C1+C2'
    w.undo();app.processEvents()
    w.select_worksheet_column(0);w.select_worksheet_column(1,extend=True)
    def move():
        dialog=QApplication.activeModalWidget();available=dialog.findChild(QListWidget)
        assert len(available.selectedItems())==2
        next(button for button in dialog.findChildren(QRadioButton) if button.text()=='After last column in use').setChecked(True)
        dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
    QTimer.singleShot(0,move);w.move_columns_dialog();app.processEvents()
    assert p.worksheet.columns[1].name=='Input' and p.worksheet.columns[2].name=='Response'
    assert p.worksheet.columns[0].metadata['formula']=='C2+C3'
    assert source_graph['recipe']['parameters']['x_index']==1 and source_graph['recipe']['parameters']['y_index']==2
    assert w._selected_columns=={1,2}
    w.undo();app.processEvents()
    w.select_worksheet_column(3);w.select_worksheet_column(5,extend=True)
    w.delete_selected_columns();assert len(p.worksheet.columns)==16
    w.undo();app.processEvents()
    checkpoint('imported blob MPX insertion, edit, move, delete and save-copy')
    source=Path(temp)/'column-source.mpx';target=Path(temp)/'column-copy.mpx'
    write_blob_fixture(source);before=source.read_bytes();w.load_path(source);w.select_worksheet_column(0)
    w.insert_columns_action_handler();assert len(p.worksheet.columns)==2
    p.rename_column(0,'Inserted');p.set_cell(0,0,'42');w.refresh()
    p.move_columns([0],'after_last');w.refresh()
    assert p.worksheet.columns[1].name=='Inserted'
    w.select_worksheet_column(0);w.delete_selected_columns();assert len(p.worksheet.columns)==1
    w.undo();app.processEvents();assert len(p.worksheet.columns)==2
    w.save_path(target);w.load_path(target);assert source.read_bytes()==before
    assert [(col.name,col.values) for col in p.worksheet.columns]==[('Measurements',[1,2,3]),('Inserted',[42])]
    assert w.table.horizontalHeaderItem(1).text()=='C2'
