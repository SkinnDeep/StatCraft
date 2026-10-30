import os,sys,tempfile,unittest,hashlib
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from statcraft.native_output_smoke import fixture,verify_native_outputs
from statcraft.app import Presenter

class NativeOutputWorkflows(unittest.TestCase):
    def test_native_groups_are_loaded_once_and_not_added_to_owned_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=fixture(Path(tmp)/'native.mpx');before=path.read_bytes();p=Presenter();p.load(path)
            self.assertEqual(len(p.history),1);self.assertEqual(p.history[0]['origin'],'native')
            self.assertEqual(len(p.history[0]['result']['graphs']),3)
            p.save(Path(tmp)/'copy.mpx');q=Presenter();q.load(Path(tmp)/'copy.mpx')
            self.assertEqual(p.history,q.history);self.assertEqual(q.native_project.session_records,[])
            self.assertEqual(before,path.read_bytes())
    def test_native_gallery_auto_open_and_capture_all_saved_geometry(self):
        from PySide6.QtWidgets import QApplication
        from statcraft.modern_app import ModernWindow
        app=QApplication.instance() or QApplication([]);p=Presenter();w=ModernWindow(p)
        with tempfile.TemporaryDirectory() as tmp:verify_native_outputs(app,p,w,tmp,lambda x:None)
        w.presenter.dirty=False;w.presenter._results_dirty=False;w.close();w.deleteLater()

if __name__=='__main__':unittest.main()
