"""Synthetic preview 28 workbook and visual QA of native-evidenced graph mapping."""
from pathlib import Path
from PySide6.QtWidgets import QApplication,QTableWidgetItem
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.similar_graph_dialog import create_similar_dialog,run_similar_graphs
from statcraft.variable_dialogs import format_variable_reference

out=Path(__file__).resolve().parents[2]/'outputs'
p=Presenter();p.worksheet=Worksheet('Process measurements',[
    Column('Trial',values=list(range(1,13))),Column('Strength (N)',values=[563,568,565,574,572,580,577,582,578,586,583,589]),
    Column('Batch','text',['A','B']*6),Column('Adjusted strength',values=[565,571,566,577,574,583,579,585,580,589,585,592])]+[
    Column('C'+str(i),metadata={'auto_type':True}) for i in range(5,17)])
source=p.scatter_plot(0,1,'regression_groups',2)
p.update_graph_styles(source,{'p0:s0':{'color':'#276b9b','marker':'diamond'},'p0:s1':{'color':'#cf672b','marker':'square'}})
app=QApplication([]);w=ModernWindow(p);w.show();w.show_result(source);w.work_splitter.setSizes([560,270]);app.processEvents()
dialog=create_similar_dialog(w,p.worksheet,source);dialog.roles.setItem(0,2,QTableWidgetItem(format_variable_reference(3,p.worksheet)))
dialog.show();app.processEvents();dialog.grab().save(str(out/'StatCraft-make-similar-preview.png'))
created=run_similar_graphs(p,source,dialog.recipes(),appearance=dialog.appearance_settings())[0]
dialog.close();dialog.deleteLater();w.refresh();w.show_result(created);app.processEvents()
w.save_path(out/'StatCraft-columns-similar-demo.mpx')
w._active_graph_frame.capture().save(str(out/'StatCraft-similar-graph-export.png'))
w.select_worksheet_column(1);w.select_worksheet_column(3,extend=True)
w.insert_columns_action_handler();app.processEvents();w.grab().save(str(out/'StatCraft-column-insertion-preview.png'))
w.undo();w.save_path(out/'StatCraft-columns-similar-demo.mpx')
p.dirty=False;p._results_dirty=False;w.close();w.deleteLater()
QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents()
