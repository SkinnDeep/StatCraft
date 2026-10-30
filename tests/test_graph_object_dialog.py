import copy
import unittest
from PySide6.QtWidgets import QApplication,QDialogButtonBox
from statcraft.graph_object_dialog import GraphObjectDialog
from statcraft.graph_interaction import style_color


OBJECTS=[{'target':'p0:s0','label':'Data','capabilities':['color','marker','marker_size','opacity'],'defaults':{'color':'#3e739b','marker':'circle','marker_size':6.4,'opacity':1}},
         {'target':'p0:bars','label':'Bars','capabilities':['fill','edge'],'defaults':{'fill':'#a7bfd2','edge':'#ffffff'}}]


class GraphObjectDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=QApplication.instance() or QApplication([])

    def test_switching_preserves_drafts_cancel_preserves_source(self):
        original={'p0:s0':{'color':'#227744'}};before=copy.deepcopy(original)
        dialog=GraphObjectDialog(OBJECTS,original)
        dialog.controls['marker_size'].setValue(12);dialog.object_combo.setCurrentIndex(1)
        self.assertNotIn('marker',dialog.controls)
        dialog.controls['fill'].setText('#ff5500');dialog.object_combo.setCurrentIndex(0)
        self.assertEqual(dialog.controls['marker_size'].value(),12)
        self.assertEqual(dialog.styles()['p0:bars']['fill'],'#ff5500');dialog.reject()
        self.assertEqual(original,before)

    def test_invalid_color_blocks_acceptance_and_switch(self):
        dialog=GraphObjectDialog(OBJECTS,{})
        dialog.controls['color'].setText('bad');dialog.object_combo.setCurrentIndex(1)
        self.assertEqual(dialog.object_combo.currentIndex(),0)
        dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        self.assertNotEqual(dialog.result(),dialog.DialogCode.Accepted);self.assertTrue(dialog.error.text())
        dialog.controls['color'].setText('#11223380');dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).click()
        self.assertEqual(dialog.result(),dialog.DialogCode.Accepted)
        self.assertEqual(dialog.styles()['p0:s0']['color'],'#11223380')

    def test_reset_clears_selected_target_only(self):
        source={'p0:s0':{'color':'#227744'},'p0:bars':{'fill':'#003355'}}
        dialog=GraphObjectDialog(OBJECTS,source);dialog.reset_button.click()
        self.assertNotIn('p0:s0',dialog.styles());self.assertEqual(dialog.styles()['p0:bars'],source['p0:bars'])

    def test_rgba_color_uses_trailing_alpha(self):
        self.assertEqual(style_color('#11223380').getRgb(),(17,34,51,128))
        self.assertEqual(style_color('#112233',.5).getRgb()[:3],(17,34,51))
