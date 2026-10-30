import tempfile,unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication,QEvent
from statcraft.app import Presenter
from statcraft.model import Worksheet,Column
from statcraft.modern_app import ModernWindow
from statcraft.data_prep_dialogs import ReshapeDialog,CombineDialog
from statcraft.verification_fonts import load_verification_fonts


class PreparationDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False);load_verification_fonts(cls.app)

    def setUp(self):
        self.p=Presenter();self.p.worksheet=Worksheet('Source',[Column('Force',values=[1,2]),Column('Other',values=[3,4]),Column('Group','text',['A','B'])])
        self.w=ModernWindow(self.p);self.w.show();self.app.processEvents()

    def tearDown(self):
        self.p.dirty=False;self.p._results_dirty=False;self.w.close();self.w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_named_variable_transfer_uses_column_identity(self):
        d=ReshapeDialog(self.w,'stack');self.assertIn('Force',d.available.item(0).text())
        d.available.item(0).setSelected(True);d.available.item(1).setSelected(True);d.transfer()
        self.assertIn('Force',d.controls['indices'].text());self.w.page=5;d.validate()
        self.assertFalse(d.error.text());self.assertEqual(self.p.worksheet.columns[0].values,[1,2,3,4]);self.assertEqual(self.w.page,0)

    def test_validation_leaves_document_unchanged(self):
        d=ReshapeDialog(self.w,'stack');d.controls['indices'].setText('C1 C3');d.validate()
        self.assertIn('same data type',d.error.text());self.assertIsNone(self.p.native_project);self.assertFalse(self.p.dirty)

    def test_duplicate_destination_name_is_atomic(self):
        d=ReshapeDialog(self.w,'transpose');d.controls['indices'].setText('C1 C2');d.controls['name'].setText('Source');d.validate()
        self.assertIn('already exists',d.error.text());self.assertIsNone(self.p.native_project)

    def test_merge_mode_disables_keys_and_rejects_same_sheet(self):
        d=CombineDialog(self.w,'merge');d.controls['how'].setCurrentIndex(3)
        self.assertFalse(d.controls['left_key'].isEnabled());d.validate();self.assertIn('different worksheets',d.error.text())

    def test_complete_interface_mpx_workflow(self):
        from statcraft.data_prep_smoke import verify_data_preparation
        with tempfile.TemporaryDirectory() as temp:verify_data_preparation(self.app,self.p,self.w,temp,lambda *args:None)


if __name__=='__main__':unittest.main()
