"""Standalone preview entry point and reproducible packaged-runtime smoke test."""
import json
import sys
from pathlib import Path

from statcraft.app import main


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        import tkinter as tk
        from statcraft.app import StatCraftApp, Presenter, histogram_data, boxplot_data
        from statcraft.model import Worksheet, Column
        from statcraft.analyses import describe
        from statcraft.io import save_project, load_project
        import tempfile

        result = {"preview": True, "frozen": bool(getattr(sys, "frozen", False))}
        root = tk.Tk()
        root.withdraw()
        app = StatCraftApp(root)
        app.presenter.worksheet = Worksheet('Smoke', [Column('x', values=[1, 2, 3, 4, 5]), Column('y', values=[2, 4, 5, 8, 9])])
        app.refresh()
        app._show_entry(app.presenter.describe_columns([0, 1]))
        root.deiconify()
        root.update()
        app.main_panes.sashpos(0,180)
        app.set_view_mode('both')
        root.update()
        assert len(app.report_table.get_children()) == 2
        assert app.report_table.item(app.report_table.get_children()[0], 'values')[3] == '3'
        box = app.grid.bbox('0','c0')
        assert box and app.grid.identify_row(box[1]+5) == '0', (box,app.grid.winfo_width(),app.grid.winfo_height(),app.grid.get_children())
        assert app.grid.identify_column(box[0]+5) == '#1'
        app._inline_edit(0,0)
        assert app.editor is not None
        app.editor[0].delete(0,'end'); app.editor[0].insert(0,'42')
        assert app._commit_editor() and app.presenter.worksheet.columns[0].values[0] == 42
        app.undo_edit(); assert app.presenter.worksheet.columns[0].values[0] == 1
        from types import SimpleNamespace
        app.navigate_cell(SimpleNamespace(state=0),0,1)
        assert app.active == (0,1)
        app.navigate_cell(SimpleNamespace(state=1),1,0)
        assert app.selection_anchor == (0,1) and app.selection_end == (1,1)
        app.set_view_mode('data'); assert len(app.work_panes.panes()) == 1
        app.set_view_mode('output'); assert len(app.work_panes.panes()) == 1
        app.set_view_mode('both'); assert len(app.work_panes.panes()) == 2
        app.navigator_visible.set(False); app.toggle_navigator(); assert len(app.main_panes.panes()) == 1
        app.navigator_visible.set(True); app.toggle_navigator(); assert len(app.main_panes.panes()) == 2
        result['native_workspace_grid_editing_and_panes'] = 'passed'
        root.withdraw()
        app._draw_graph('Histogram', 'histogram', histogram_data([1, 2, 3, 4, 5], 3), 'x', 'Frequency', 'Test')
        app._draw_graph('Scatterplot', 'scatter', [(1, 2), (2, 4), (3, 5)], 'x', 'y', 'Test')
        app._draw_graph('Boxplot', 'boxplot', boxplot_data([1, 2, 3, 4, 5]), 'x', '', 'Test')
        from statcraft.quality import individuals_moving_range, normal_capability
        app._draw_control_chart({'variable': 'x', **individuals_moving_range([1, 2, 3, 4, 5])})
        app._draw_capability({'variable': 'x', **normal_capability([1, 2, 3, 4, 5], 0, 6, 3)})
        from statcraft.attribute_quality import p_chart, u_chart
        app._draw_attribute_chart(p_chart([1, None, 8], [20, None, 40]))
        app._draw_attribute_chart(u_chart([2, 4, 8], [1, 2, 4]))
        from statcraft.subgroup_quality import xbar_r
        app._draw_control_chart({'chart':'Xbar-R','variable':'Synthetic data','subgroup_labels':['A','B','C'], **xbar_r([[1,3],[4,6],[7,9]])})
        app.presenter.worksheet = Worksheet('Grouped', [Column('Group', 'text', ['A', 'B']*3), Column('Y', values=[1,4,2,5,3,6])])
        app._show_entry(app.presenter.stacked_anova(1, 0))
        assert abs(app.presenter.history[-1]['result']['f'] - 13.5) < 1e-10
        variance_entry = app.presenter.equal_variances_stacked(1,0,'Levene')
        assert variance_entry['result']['p_value'] == 1
        app._show_entry(variance_entry)
        result['stacked_anova_and_attribute_charts'] = 'passed'
        root.update_idletasks()
        graphs = [widget for widget in root.winfo_children() if isinstance(widget, tk.Toplevel)]
        assert len(graphs) == 8
        for graph in graphs:
            canvases = [widget for widget in graph.winfo_children() if isinstance(widget, tk.Canvas)]
            assert len(canvases) == 1 and len(canvases[0].find_all()) > 10
        root.destroy()
        result["tk_widgets"] = "passed"
        result['graph_rendering'] = 'passed'
        summary = describe([1, 2, 3, 4, 5, None])
        assert summary["mean"] == 3 and summary["missing"] == 1
        result["calculation"] = "passed"
        from statcraft.probability import calculate
        from statcraft.calculator import evaluate
        from statcraft.model import Worksheet, Column
        assert calculate('Normal', 'CDF', 0, [0, 1])['result'] == .5
        assert evaluate('C1*2', Worksheet('Test', [Column('x', values=[1, 2])])) == [2, 4]
        result['probability_and_calculator'] = 'passed'
        from statcraft.inference import one_sample_t, paired_t, two_sample_t, one_way_anova, linear_regression
        assert one_sample_t([1, 2, 3, 4, 5], mu=3)['p_value'] == 1
        assert paired_t([2, 4, 5], [1, 2, 4])['count'] == 3
        assert two_sample_t([1, 2, 3], [2, 3, 4])['df'] > 0
        assert one_way_anova([[1, 2, 3], [4, 5, 6]])['p_value'] < .05
        regression = linear_regression([1, 2, 3, 4, 5], [2, 4, 5, 8, 9])
        assert regression['slope'] > 0
        result['inference'] = 'passed'
        from statcraft.regression import multiple_regression
        fitted = multiple_regression([[-1,-1,-1,-1,1,1,1,1],[-1,-1,1,1,-1,-1,1,1]], [11.5,10.5,5.5,4.5,15.5,14.5,9.5,8.5])
        assert abs(fitted['coefficients'][1]['estimate'] - 2) < 1e-10
        result['multiple_regression_and_quality'] = 'passed'
        with tempfile.TemporaryDirectory(prefix="StatCraft-test-") as folder:
            path = Path(folder) / "test.statcraft"
            presenter = Presenter()
            save_project(presenter.worksheet, path)
            assert load_project(path).name == presenter.worksheet.name
            from statcraft._mpx_fixture import write_fixture
            from statcraft.mpx import load_mpx
            source = Path(folder) / 'source.mpx'
            target = Path(folder) / 'copy.mpx'
            write_fixture(source)
            presenter.load(source)
            assert len(presenter.native_project.worksheets) == 2
            native_root = tk.Tk()
            native_root.withdraw()
            native_app = StatCraftApp(native_root, presenter)
            native_app.refresh()
            assert len(native_app.sheet_selector['values']) == 2
            native_app.sheet_selector.current(0)
            native_app.change_worksheet()
            assert presenter.worksheet.name == 'Second'
            native_app._draw_graph('Saved histogram', 'histogram', histogram_data([2,3,4], 3), 'Measurements', 'Frequency', 'Snapshot test')
            presenter.describe_column(0)
            presenter._record('Saved P', p_chart([1,2,3], [10,20,30]))
            presenter._record('Saved U', u_chart([1,2,3], [1,2,3]))
            native_root.update_idletasks()
            native_root.destroy()
            presenter.select_worksheet(1)
            presenter.set_cell(0, 0, '7')
            assert presenter.undo() and presenter.worksheet.columns[0].values[0] == 1
            assert presenter.redo() and presenter.worksheet.columns[0].values[0] == 7
            presenter.select_worksheet(0)
            presenter.save(target)
            copied = load_mpx(target)
            assert copied.worksheets[1].columns[0].values == [7, 2, 3]
            assert copied.retained_members['/unknown/retained.bin'] == b'Original synthetic opaque payload\x00\xff'
            reopened = Presenter(); reopened.load(target)
            assert not reopened.dirty
            own = [entry for entry in reopened.history if entry.get('origin') == 'statcraft']
            assert len(own) == 4
            restored_root = tk.Tk(); restored_root.withdraw()
            restored_app = StatCraftApp(restored_root, reopened)
            before = len(reopened.history)
            for entry in own:
                restored_app.restore_result(entry)
            restored_root.update_idletasks()
            restored_graphs = [widget for widget in restored_root.winfo_children() if isinstance(widget, tk.Toplevel)]
            assert len(restored_graphs) == 3
            for graph in restored_graphs:
                canvases = [widget for widget in graph.winfo_children() if isinstance(widget, tk.Canvas)]
                assert len(canvases) == 1 and len(canvases[0].find_all()) > 10
            assert len(reopened.history) == before and not reopened.dirty
            summary_entry = next(entry for entry in own if 'mean' in entry['result'])
            reopened.select_worksheet(0)
            reopened.set_cell(0, 0, '8')
            restored_app.refresh()
            assert reopened.result_stale(summary_entry)
            selection_index = next(i for i, entry in enumerate(reopened.history) if entry is summary_entry)
            assert '[Changed]' in restored_app.history_list.get(selection_index)
            restored_app.history_list.selection_set(selection_index)
            restored_app.rerun_selected_result()
            assert len(reopened.history) == before + 1
            assert reopened.history[-1]['result']['mean'] == 5
            assert reopened.result_stale(reopened.history[-1]) is False and reopened.dirty
            assert summary_entry['result']['mean'] == 3
            updated_copy = Path(folder) / 'updated-copy.mpx'
            reopened.save(updated_copy)
            final = Presenter(); final.load(updated_copy)
            assert final.history[-1]['result']['mean'] == 5
            assert final.result_stale(final.history[-1]) is False and not final.dirty
            result['mpx_result_tracking_and_rerun'] = 'passed'
            restored_root.destroy()
            result['mpx_result_and_graph_snapshot_roundtrip'] = 'passed'
            result['mpx_open_select_edit_save_copy'] = 'passed'
            from statcraft._mpx_fixture import write_subgroup_fixture
            subgroup_source = Path(folder) / 'subgroups.mpx'
            subgroup_copy = Path(folder) / 'subgroups-copy.mpx'
            write_subgroup_fixture(subgroup_source)
            subgroup_presenter = Presenter(); subgroup_presenter.load(subgroup_source)
            subgroup_entry = subgroup_presenter.xbar_r_stacked(0, 1)
            variance_old = subgroup_presenter.equal_variances_stacked(0,1,'Bartlett')
            subgroup_presenter.save(subgroup_copy)
            subgroup_reopened = Presenter(); subgroup_reopened.load(subgroup_copy)
            stored = next(entry for entry in subgroup_reopened.history if entry.get('origin') == 'statcraft')
            subgroup_root = tk.Tk(); subgroup_root.withdraw()
            subgroup_app = StatCraftApp(subgroup_root, subgroup_reopened)
            subgroup_app.restore_result(stored)
            assert stored['result']['means'] == [2,5,8]
            assert 'i_center' not in stored['result']
            subgroup_reopened.set_cell(0,0,'5')
            subgroup_app.refresh()
            assert subgroup_reopened.result_stale(stored)
            fresh = subgroup_reopened.rerun_result(stored)
            subgroup_app._show_entry(fresh); subgroup_app.restore_result(fresh)
            assert fresh['result']['means'] == [4,5,8]
            assert subgroup_root.title().endswith('*')
            subgroup_root.update_idletasks()
            subgroup_graphs = [widget for widget in subgroup_root.winfo_children() if isinstance(widget, tk.Toplevel)]
            assert len(subgroup_graphs) == 2
            for graph in subgroup_graphs:
                canvases = [widget for widget in graph.winfo_children() if isinstance(widget, tk.Canvas)]
                assert len(canvases) == 1 and len(canvases[0].find_all()) > 30
            restored_variance = next(entry for entry in subgroup_reopened.history if entry['result'].get('variance_test'))
            subgroup_reopened.set_cell(0,0,'10')
            assert subgroup_reopened.result_stale(restored_variance)
            fresh_variance = subgroup_reopened.rerun_result(restored_variance)
            subgroup_app._show_entry(fresh_variance)
            assert fresh_variance['result']['test_statistic'] > restored_variance['result']['test_statistic']
            variance_copy = Path(folder) / 'variance-copy.mpx'
            subgroup_reopened.save(variance_copy)
            variance_final = Presenter(); variance_final.load(variance_copy)
            assert variance_final.history[-1]['result']['test_statistic'] == fresh_variance['result']['test_statistic']
            assert variance_final.result_stale(variance_final.history[-1]) is False
            result['equal_variances_mpx_rerun_roundtrip'] = 'passed'
            subgroup_root.destroy()
            result['xbar_r_mpx_snapshot_and_rerun'] = 'passed'
        result["project_roundtrip"] = "passed"
        Path(sys.argv[2]).write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        main()
