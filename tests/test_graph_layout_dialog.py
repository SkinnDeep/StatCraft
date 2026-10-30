import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from statcraft.graph_layout_dialog import GraphLayoutDialog


def graph(index):
    return {'id':str(index),'title':'Graph '+str(index),'worksheet_name':'Data',
            'result':{'graph':'histogram'}}


class GraphLayoutDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_explicit_selection_order_and_reference_contract(self):
        entries=[graph(i) for i in range(3)]; dialog=GraphLayoutDialog(entries)
        try:
            self.assertEqual(dialog.selected.count(),0)
            self.assertFalse(dialog.validate())
            for i in range(3):dialog.available.item(i).setSelected(True)
            dialog.add_entries()
            self.assertIs(dialog.selected_entries()[0],entries[0])
            self.assertIn('[Data]',dialog.selected.item(0).text())
            dialog.selected.clearSelection(); dialog.selected.item(2).setSelected(True)
            dialog.move_selected(-1)
            self.assertEqual([entry['id'] for entry in dialog.selected_entries()],['0','2','1'])
            dialog.remove_entries()
            self.assertEqual([entry['id'] for entry in dialog.selected_entries()],['0','1'])
            self.assertTrue(dialog.validate())
        finally:dialog.close()

    def test_capacity_and_reopening(self):
        entries=[graph(i) for i in range(3)]
        dialog=GraphLayoutDialog([],layout={'rows':1,'columns':2,'title':'Saved','graphs':entries})
        try:
            self.assertEqual(dialog.settings(),{'rows':1,'columns':2,'title':'Saved'})
            self.assertEqual(dialog.selected.count(),3)
            self.assertFalse(dialog.validate())
            self.assertIn('capacity',dialog.error.text())
            dialog.columns.setValue(9)
            self.assertTrue(dialog.validate())
            self.assertEqual(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).text(),'Finish')
        finally:dialog.close()


if __name__=='__main__':unittest.main()
