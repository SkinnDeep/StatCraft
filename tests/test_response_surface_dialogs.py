import tempfile,unittest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter
from statcraft.modern_app import ModernWindow
from statcraft.response_surface_dialogs import CreateSurfaceDialog,CreateSurfaceSettings,AnalyzeSurfaceDialog,SurfaceTermsDialog
from statcraft.response_surface_smoke import verify_response_surface
from statcraft.verification_fonts import load_verification_fonts


class SurfaceDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False);load_verification_fonts(cls.app)

    def setUp(self):self.p=Presenter();self.w=ModernWindow(self.p);self.w.show();self.app.processEvents()

    def tearDown(self):
        self.p.dirty=False;self.p._results_dirty=False;self.w.close();self.w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);self.app.processEvents()

    def test_available_designs_matrix_selects_real_catalog_configurations(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from statcraft.response_surface import create
        d=CreateSurfaceDialog(self.w);c=CreateSurfaceSettings(d,'Display Available Designs');c.show();self.app.processEvents()
        table=c.available_table
        self.assertEqual((table.rowCount(),table.columnCount()),(12,11))
        self.assertEqual([table.item(1,i).text() for i in range(2,11)],[str(k) for k in range(2,11)])
        self.assertEqual(table.item(2,2).text(),'13');self.assertEqual(table.item(3,2).text(),'14')
        self.assertEqual(table.item(4,8).text(),'154');self.assertEqual(table.item(8,10).text(),'158')
        self.assertEqual(table.item(10,10).text(),'170');self.assertEqual(table.rowSpan(2,0),2)
        item=table.item(5,5);QTest.mouseClick(table.viewport(),Qt.MouseButton.LeftButton,pos=table.visualItemRect(item).center());self.app.processEvents()
        self.assertEqual(c.selected_spec['fraction'],2);self.assertGreater(c.selected_spec['blocks'],1)
        self.assertIn('33 runs',c.selection_label.text());self.assertEqual(c.changes,{})
        c.validate();self.assertFalse(c.error.text());d.apply_design(c.changes['selected_design'])
        sheet=create(**d.parameters());self.assertEqual(sheet.row_count,33);self.assertEqual(len(sheet.columns),9)
        self.assertEqual(sheet.metadata['doe']['blocks'],c.selected_spec['blocks'])
        self.assertEqual(d.count.currentText(),'5');self.assertEqual(d.fraction,2)
        c.deleteLater();d.deleteLater()

    def test_every_numbered_matrix_cell_creates_its_displayed_runs(self):
        from PySide6.QtCore import Qt
        from statcraft.response_surface import create
        d=CreateSurfaceDialog(self.w);c=CreateSurfaceSettings(d,'Display Available Designs');tested=0
        for row in range(2,12):
            for col in range(2,11):
                item=c.available_table.item(row,col);spec=item.data(Qt.ItemDataRole.UserRole)
                if not spec:
                    self.assertFalse(item.flags()&Qt.ItemFlag.ItemIsSelectable);continue
                d.apply_design(spec);sheet=create(**d.parameters())
                self.assertEqual(sheet.row_count,int(item.text()),(row,col,spec));self.assertEqual(sheet.metadata['doe']['blocks'],spec['blocks']);tested+=1
        self.assertGreater(tested,30);c.deleteLater();d.deleteLater()

    def test_cancel_catalog_preserves_family_factors_and_settings(self):
        d=CreateSurfaceDialog(self.w);before=d.parameters();c=CreateSurfaceSettings(d,'Display Available Designs')
        c.available_table.setCurrentCell(10,9);c.reject()
        self.assertEqual(d.parameters(),before);self.assertEqual(c.changes,{})
        c.deleteLater();d.deleteLater()

    def test_available_designs_button_opens_the_catalog_modal(self):
        from unittest.mock import patch
        d=CreateSurfaceDialog(self.w)
        with patch.object(CreateSurfaceSettings,'exec',return_value=0) as modal:
            d.option_buttons['Display Available Designs'].click()
        modal.assert_called_once()
        self.assertEqual(d.centers,6)
        d.deleteLater()

    def test_box_behnken_counts_and_centers_update(self):
        d=CreateSurfaceDialog(self.w);d.box.setChecked(True);self.assertGreaterEqual(d.count.count(),7);self.assertEqual(d.count.currentText(),'3');self.assertEqual(d.centers,3)
        d.validate();self.assertFalse(d.error.text());self.assertEqual(self.p.worksheet.row_count,15)

    def test_design_settings_default_custom_centers_alpha_and_replication(self):
        d=CreateSurfaceDialog(self.w);c=CreateSurfaceSettings(d,'Designs')
        self.assertEqual(c.design_table.item(0,1).text(),'13')
        self.assertEqual(c.design_table.item(0,2).text(),'1')
        c.default_centers.setChecked(True)
        self.assertEqual(c.controls['centers'].value(),5)
        self.assertFalse(c.controls['centers'].isEnabled())
        self.assertEqual(c.run_count.text(),'13')
        c.custom_centers.setChecked(True);c.controls['centers'].setValue(9)
        c.controls['replicates'].setValue(2)
        self.assertEqual(c.run_count.text(),'34')
        c.alpha_buttons[1].setChecked(True)
        self.assertEqual(c.controls['alpha_mode'].currentIndex(),1)
        self.assertFalse(c.controls['alpha'].isEnabled())
        c.alpha_buttons[2].setChecked(True);c.controls['alpha'].setValue(1.7)
        self.assertTrue(c.controls['alpha'].isEnabled())
        c.validate();self.assertFalse(c.error.text())
        self.assertEqual(c.changes['centers'],9)
        self.assertEqual(c.changes['replicates'],2)
        self.assertEqual(c.changes['alpha_mode'],'custom')
        self.assertEqual(c.changes['alpha'],1.7)
        self.assertEqual(d.centers,6)
        c.deleteLater();d.deleteLater()

    def test_blocked_design_row_applies_splits_and_replication_to_real_creation(self):
        from statcraft.response_surface import create
        d=CreateSurfaceDialog(self.w);c=CreateSurfaceSettings(d,'Designs')
        self.assertGreater(c.design_table.rowCount(),1)
        row=next(i for i,spec in enumerate(c.design_choices) if spec['blocks']==2)
        c.design_table.setCurrentCell(row,0)
        self.assertEqual(c.controls['center_cube'].value(),3);self.assertEqual(c.controls['center_axial'].value(),3)
        self.assertEqual(c.run_count.text(),'14');self.assertEqual(c.block_count.text(),'2')
        c.controls['replicates'].setValue(2);c.controls['block_replicates'].setChecked(True)
        self.assertEqual(c.run_count.text(),'28');self.assertEqual(c.block_count.text(),'4')
        c.validate();self.assertFalse(c.error.text())
        params=d.parameters();params.update(c.changes);sheet=create(**params)
        self.assertEqual(sheet.row_count,28);self.assertEqual(len(set(sheet.columns[3].values)),4)
        c.deleteLater();d.deleteLater()

    def test_custom_center_split_updates_actual_alpha_and_warns_for_nonorthogonal_blocks(self):
        import math
        d=CreateSurfaceDialog(self.w);c=CreateSurfaceSettings(d,'Designs');row=next(i for i,spec in enumerate(c.design_choices) if spec['blocks']==2);c.design_table.setCurrentCell(row,0)
        c.custom_centers.setChecked(True);c.controls['center_cube'].setValue(4)
        self.assertEqual(c.run_count.text(),'15');self.assertIn(format(math.sqrt(1.75),'.6g'),c.effective_alpha.text())
        c.alpha_buttons[1].setChecked(True);self.assertIn('not provide orthogonal',c.preview_warning.text())
        c.validate();self.assertFalse(c.error.text())
        c.deleteLater();d.deleteLater()

    def test_box_behnken_larger_count_and_factor_editor_preserve_names(self):
        from statcraft.response_surface import create
        d=CreateSurfaceDialog(self.w);d.box.setChecked(True);d.count.setCurrentText('10');c=CreateSurfaceSettings(d,'Factors')
        self.assertEqual(c.controls['factors'].rowCount(),10);self.assertEqual(c.controls['factors'].item(9,0).text(),'J')
        sheet=create(**d.parameters());self.assertEqual(sheet.row_count,170)
        c.deleteLater();d.deleteLater()

    def test_analysis_automatically_selects_blocks_and_supports_ten_factors(self):
        from statcraft.response_surface import create
        from statcraft.response_surface_catalog import catalog
        from statcraft.model import Column
        spec=next(s for s in catalog() if s['kind']=='central_composite' and s['factors']==10 and s['blocks']>1)
        d=CreateSurfaceDialog(self.w);d.apply_design(spec);self.p.worksheet=create(**d.parameters());self.p.worksheet.columns.append(Column('Yield',values=[1.]*self.p.worksheet.row_count))
        analysis=AnalyzeSurfaceDialog(self.w);analysis.controls['response_index'].setText('C15')
        values,names=analysis.roles();self.assertEqual(len(values['factor_indices']),10);self.assertEqual(values['block_index'],3)
        analysis.controls['block_index'].setText('C5');self.assertRaisesRegex(ValueError,'separate',analysis.roles)
        analysis.deleteLater();d.deleteLater()

    def test_cancel_design_options_does_not_apply(self):
        d=CreateSurfaceDialog(self.w);c=CreateSurfaceSettings(d,'Designs');c.controls['centers'].setValue(12);self.assertEqual(c.run_count.text(),'20');c.reject();self.assertEqual(d.centers,6);self.assertEqual(c.changes,{})

    def test_separate_project_creation_leaves_source_window_unchanged(self):
        original=self.p.worksheet;d=CreateSurfaceDialog(self.w);d.destination.setCurrentText('New project');d.validate()
        self.assertFalse(d.error.text());self.assertIs(self.p.worksheet,original);self.assertIsNone(self.p.native_project)
        child=self.app._prepared_windows[-1];self.assertIs(child.presenter,d.target);self.assertTrue(child.isMaximized())
        child.presenter.dirty=False;child.presenter._results_dirty=False;child.close();child.deleteLater();self.app.processEvents()

    def test_no_results_mode_still_creates_worksheet(self):
        d=CreateSurfaceDialog(self.w);d.display='none';d.validate();self.assertFalse(d.error.text());self.assertIsNone(d.entry);self.assertEqual(self.p.history,[]);self.assertTrue(self.p.dirty)

    def test_duplicate_sheet_name_is_rejected_before_mutation(self):
        d=CreateSurfaceDialog(self.w);d.name.setText(self.p.worksheet.name);d.validate();self.assertIn('already exists',d.error.text());self.assertIsNone(self.p.native_project)

    def test_term_dialog_supports_squares_and_hierarchy(self):
        d=SurfaceTermsDialog(self.w,['A','B'],[[0],[1]]);d.add_order();self.assertIn([0,0],d.chosen());d.selected.setCurrentRow(0);d.remove();d.validate();self.assertIn('main effect',d.error.text())

    def test_complete_create_analyze_children_mpx_workflow(self):
        with tempfile.TemporaryDirectory() as temp:verify_response_surface(self.app,self.p,self.w,temp,lambda *args:None)


if __name__=='__main__':unittest.main()
