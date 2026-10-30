from pathlib import Path
from statistics import NormalDist
from PySide6.QtWidgets import QApplication
from statcraft.modern_app import ModernWindow
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
out=Path(__file__).resolve().parents[2]/'outputs'
app=QApplication([]); p=Presenter()
data=[10+.2*NormalDist().inv_cdf((i-.375)/(40+.25)) for i in range(1,41)]
p.worksheet=Worksheet('Measurements',[Column('Diameter',values=data)])
w=ModernWindow(p); w.resize(1440,960); w.show_result(p.normality(0)); w.show()
w.result_tabs.setCurrentIndex(1); w.work_splitter.setSizes([1000,0]); app.processEvents()
w.grab().save(str(out/'StatCraft-normal-probability-plot.png'))
p.dirty=False; p._results_dirty=False; w.close()
