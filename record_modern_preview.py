import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
root=Path(__file__).resolve().parents[2]
out=root/'outputs'
exe=out/'StatCraft-preview46.exe'
smoke=json.loads((root/'work/modern-packaged-smoke.json').read_text())
assert smoke['frozen'] and smoke['qt_widgets']=='passed' and smoke['mpx_save_reopen_rerun']=='passed'
manifest=json.loads((out/'StatCraft-preview-manifest.json').read_text())
manifest['executable']=exe.name
manifest['canonical_executable_matches']=hashlib.sha256((out/'StatCraft.exe').read_bytes()).hexdigest()==hashlib.sha256(exe.read_bytes()).hexdigest()
manifest['packaged_smoke_test']=smoke
manifest['actual_project_verification']=json.loads((root/'work/quiz1-packaged-verified.json').read_text())
manifest['actual_project_analysis_roundtrip']=json.loads((root/'work/quiz1-normality-roundtrip.json').read_text())
manifest['source_tests']=json.loads((root/'work/preview-v2-test-result.json').read_text())
manifest['doe_child_dialog_verification']=json.loads((root/'work/doe-child-dialogs-verified.json').read_text())
manifest['doe_rea_evidence']={'native_findings':'statcraft-doe-factorial-native-findings.md','ui_contract':'statcraft-doe-ui-contract.md','native_methods_interpreted':6,'runtime_visual_parity_verified':False}
manifest['mpx_append_evidence']='statcraft-mpx-append-column-evidence.md'
manifest['fractional_evidence']='statcraft-fractional-doe-findings.md'
manifest['build_priorities']='StatCraft-build-priorities.md'
manifest['actual_project_append_source_verification']=json.loads((root/'work/quiz1-append-verified.json').read_text())
manifest['mpx_numeric_rows_evidence']='statcraft-mpx-numeric-row-evidence.md'
manifest['actual_project_row_growth_source_verification']=json.loads((root/'work/quiz1-row-growth-verified.json').read_text())
manifest['actual_grown_project_packaged_verification']=json.loads((root/'work/quiz1-grown-packaged-verified.json').read_text())
manifest['new_project_envelope_evidence']='statcraft-mpx-new-project-boundary.md'
manifest['worksheet_ui_evidence']='statcraft-worksheet-ui-contract.md'
manifest['owned_workbook_packaged_verification']=json.loads((root/'work/owned-workbook-packaged-verified.json').read_text())
manifest['interactive_check']='Qt editor commits, column-name paste/undo, explicit Y/X role transfer and matching graph axis labels verified; actual quiz1.mpx opens with 1200 rows and the source remains unchanged.'
manifest['supported']=[feature for feature in manifest['supported'] if feature!='Navigator visibility and data/output/both pane modes']
manifest['mpx']['research_fixtures']='Six public worksheet containers plus the user-provided quiz1 project with binary numeric storage; user and public datasets are never bundled.'
manifest['mpx']['numeric_storage']='Observed inline arrays and internal /blobs/blobN?size=N little-endian binary64 members, with bounded size validation.'
tests=json.loads((root/'work/preview-v2-test-result.json').read_text())['tests_run']
assert smoke['mpx_binary_blob_load_edit_save']=='passed'
assert smoke['normality_variance_dialogs_plot_mpx_rerun']=='passed'
assert smoke['six_scatter_modes_group_fits_mpx_rerun']=='passed'
assert smoke['doe_create_analyze_dialogs_mpx_rerun']=='passed'
assert smoke['mpx_append_numeric_column_save_reopen_rerun']=='passed'
assert smoke['fractional_generators_terms_aliases_mpx_rerun']=='passed'
assert smoke['mpx_numeric_rows_dialog_blob_save_reopen_rerun']=='passed'
assert smoke['new_mpx_workbook_tabs_rename_duplicate_save_rerun']=='passed'
assert smoke['owned_mpx_text_grid_groups_missing_save_rerun']=='passed'
assert smoke['owned_mpx_dates_type_display_clipboard_precision_save']=='passed'
for flag in ('stored_constants_matrices_editors_calculator_mpx','worksheet_tab_enter_editor_navigation_delete_confirmation','all_26_graph_menu_actions_dialogs_render_graph_first_mpx_rerun','statcraft_22_toolbar_21_icons_chrome_statusbar_workflows','statcraft_selection_highlighting_context_menus_navigator_logo'):
    assert smoke[flag]=='passed'
assert smoke['docked_graph_editor_live_annotations_axes_mpx_and_removed_header']=='passed'
for flag in ('automatic_formula_dependencies_global_menu_atomic_undo_mpx','dynamic_conditional_colors_formula_edits_manual_styles_mpx'):
    assert smoke[flag]=='passed'
for flag in ('value_order_text_modes_counts_groups_tables_mpx_rerun','worksheet_tab_scroll_preserves_sheet_rows_and_row_page_navigation'):
    assert smoke[flag]=='passed'
for flag in ('graph_object_hit_testing_doubleclick_styles_undo_export_mpx','histogram_scales_normal_fit_counts_density_cumulative_mpx','graph_style_renderers_3d_camera_preserved'):
    assert smoke[flag]=='passed'
manifest['graph_object_editing_rea_evidence']='statcraft-graph-object-editing-contract.md'
manifest['graph_brushing_rea_evidence']='statcraft-graph-brushing-contract.md'
manifest['graph_editing_packaged_verification']=json.loads((root/'work/graph-editing-packaged-verified.json').read_text())
manifest['graph_editing_preview']='StatCraft-graph-editing-preview.png'
manifest['current_pass']='Preview46: Native One-Way ANOVA (Stat > ANOVA > One-Way...) replacing primitive inference dialogs, with stacked and unstacked data modes, equal-variances ANOVA and Welch unequal-variances test, multiple comparisons (Tukey HSD, Fisher LSD, Dunnett against control, Hsu MCB with best, Games-Howell), StatCraft-identical grouping letters (A, B, C...), Means Interval Plot, Differences of Means Interval Plot, 4-in-1 residual diagnostic plots, automatic worksheet column storage of fits/residuals, working child dialogs, Office export and tracked MPX reruns.'
manifest['oneway_evidence']='statcraft-oneway-contract.md'
manifest['oneway_verification']=json.loads((root/'work/oneway-artifacts-verified.json').read_text())
manifest['oneway_packaged_verification']=json.loads((root/'work/oneway-artifacts-verified.json').read_text())
assert smoke['oneway_anova_stacked_unstacked_comparisons_graphs_mpx']=='passed'
feature='One-Way ANOVA with stacked and unstacked data modes, equal/unequal variances (Welch test), multiple comparisons (Tukey, Fisher, Dunnett, Hsu MCB, Games-Howell), grouping letters, interval plots, 4-in-1 residuals, fits/residuals storage and MPX reruns'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['model_plots_evidence']='statcraft-model-plots-contract.md'
manifest['model_plots_verification']=json.loads((root/'work/model-plots-artifacts-verified.json').read_text())
manifest['model_plots_packaged_verification']=json.loads((root/'work/model-plots-packaged-verified.json').read_text())
assert smoke['model_plots_factorial_contour_surface_predict_five_models_mpx_remapping']=='passed'
feature='Model-Driven Factorial Plots, Contour Plot, Surface Plot, and Two-Level Factorial Predict across fitted regression, fixed GLM, two-level factorial, response-surface and binary logistic models: Main Effects and Interaction plots, 2D contour bands/isolines/design points, 3D shaded/wireframe surfaces, hold-values settings, working child dialogs and MPX reruns'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['optimizer_evidence']='statcraft-optimizer-contract.md'
manifest['optimizer_verification']=json.loads((root/'work/optimizer-artifacts-verified.json').read_text())
manifest['optimizer_packaged_verification']=json.loads((root/'work/optimizer-packaged-verified.json').read_text())
assert smoke['response_optimizer_desirability_constraints_plot_mpx_remapping']=='passed'
feature='Response Optimizer across fitted regression, fixed GLM, two-level factorial, response-surface and binary logistic models: single/multi-response Derringer-Suich desirability, predictor constraints and starting values, working Desirability/Options/Graphs/Results/View Model child dialogs, multi-panel Optimization Plot and MPX reruns'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['logistic_evidence']='statcraft-logistic-contract.md'
manifest['logistic_verification']=json.loads((root/'work/logistic-artifacts-verified.json').read_text())
manifest['logistic_packaged_verification']=json.loads((root/'work/logistic-packaged-verified.json').read_text())
assert smoke['binary_logistic_fit_events_terms_roc_predict_mpx_remapping']=='passed'
feature='Binary logistic regression (Fit Binary Logistic Model and Predict): individual binary and grouped event/trial responses, continuous/categorical predictors, hierarchical interactions, Model/Options/Graphs/Results child dialogs, LP separation screening, Wald/LR tests, odds ratios, 2x2 ROC/residual plots with row brushing, logit-scale probability predictions and MPX reruns'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['prediction_evidence']='statcraft-prediction-contract.md'
manifest['prediction_verification']=json.loads((root/'work/prediction-artifacts-verified.json').read_text())
manifest['prediction_packaged_verification']=json.loads((root/'work/prediction-packaged-verified.json').read_text())
assert smoke['prediction_three_models_values_columns_intervals_children_mpx_remapping']=='passed'
feature='Predict from simple/multiple regression, fixed GLM and response-surface models: named manual/column inputs, CI/PI and one-sided bounds, readable equations/results and MPX reruns'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['gage_rr_evidence']='statcraft-gage-rr-contract.md'
manifest['gage_rr_verification']=json.loads((root/'work/gage-rr-artifacts-verified.json').read_text())
manifest['gage_rr_packaged_verification']=json.loads((root/'work/gage-rr-packaged-verified.json').read_text())
assert smoke['gage_rr_crossed_anova_options_six_graphs_rows_mpx_columns']=='passed'
feature='Balanced crossed Gage R&R ANOVA, interaction pooling, variance components, six graphs, tolerance/reference-process comparisons and MPX reruns'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['response_surface_evidence']='statcraft-response-surface-contract.md'
manifest['response_surface_verification']=json.loads((root/'work/response-surface-artifacts-verified.json').read_text())
manifest['response_surface_packaged_verification']=json.loads((root/'work/response-surface-packaged-verified.json').read_text())
assert smoke['response_surface_designs_children_quadratic_lof_mpx']=='passed'
new_feature='Response-surface central composite/Box-Behnken creation and quadratic analysis with working child dialogs, low/high coding, adjusted/sequential tests, lack-of-fit/pure error, readable reports, 2x2 plots and persisted MPX design/model reruns'
if new_feature not in manifest['supported']:manifest['supported'].append(new_feature)
manifest['glm_evidence']='statcraft-glm-contract.md'
manifest['glm_verification']=json.loads((root/'work/glm-artifacts-verified.json').read_text())
manifest['glm_packaged_verification']=json.loads((root/'work/glm-packaged-verified.json').read_text())
assert smoke['glm_fixed_factors_interactions_child_dialogs_residuals_mpx']=='passed'
new_feature='Fixed-factor general linear models with numeric/text factors, covariates, hierarchical interactions, effect/reference coding, adjusted/sequential ANOVA, working child dialogs, compact result tables, 2x2 residual plots and MPX setup/reruns following column edits'
if new_feature not in manifest['supported']:manifest['supported'].append(new_feature)
manifest['data_preparation_evidence']='statcraft-data-preparation-contract.md'
manifest['actual_project_data_preparation_verification']=json.loads((root/'work/quiz1-data-preparation-verified.json').read_text())
manifest['data_preparation_verification']=json.loads((root/'work/data-preparation-artifacts-verified.json').read_text())
manifest['data_preparation_packaged_verification']=json.loads((root/'work/data-preparation-packaged-verified.json').read_text())
assert smoke['typed_data_preparation_dialogs_native_source_mpx']=='passed'
new_feature='Typed column stack/unstack/transpose and worksheet stack/unique-key merge dialogs, missing-value padding, independent native-source projects and MPX persistence'
if new_feature not in manifest['supported']:manifest['supported'].append(new_feature)
manifest['output_workspace_evidence']='statcraft-output-workspace-contract.md'
manifest['output_workspace_verification']=json.loads((root/'work/output-workspace-artifacts-verified.json').read_text())
manifest['output_workspace_packaged_verification']=json.loads((root/'work/output-workspace-packaged-verified.json').read_text())
assert smoke['output_workspace_tabs_close_reopen_report_mpx']=='passed'
feature='Named result-document tabs with close/reopen/reorder/cycle controls, per-result view/zoom/scroll/editor state, independently saved MPX output workspace and editable ReportPad with undoable appends, Office/print support and saved manual notes'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['startup_zoom_evidence']='statcraft-startup-zoom-contract.md'
manifest['startup_verification']=json.loads((root/'work/startup-packaged-verified.json').read_text())
manifest['heatmap_office_verification']=json.loads((root/'work/heatmap-artifacts-verified.json').read_text())
assert smoke['output_zoom_proxy_geometry_interaction_heatmap_office']=='passed'
assert manifest['startup_verification']['maximized'] and manifest['startup_verification']['frozen']
feature='Maximized startup with original brief splash and project arguments, clean window disposal, interactive output zoom preserving source capture and worksheet widths, and real heatmap DOCX/PPTX graph export without renderer-array dumps'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['office_export_evidence']='statcraft-office-export-contract.md'
manifest['office_export_verification']=json.loads((root/'work/office-artifacts-verified.json').read_text())
assert smoke['office_native_docx_pptx_graph_report_context_cancel']=='passed'
feature='Native DOCX and PPTX selected-output exports with editable monospaced report text, embedded full-frame graph PNGs, graph/report pages, automatic wide Word pages, paginated slides, safe atomic saves and correct context targets'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['printing_rea_evidence']='statcraft-printing-contract.md'
manifest['printing_artifact_verification']=json.loads((root/'work/printing-artifacts-verified.json').read_text())
manifest['printing_scope']={'qt_printsupport':True,'physical_printer_verified':False,'native_multi_graph_selection':False,'worksheet_cell_limit':500000,'page_limit':2000,'columns_per_band':6,'graph_pdf_rendering':'full-frame raster capture','report_worksheet_pdf_rendering':'selectable text'}
manifest['source_archive_sha256']=hashlib.sha256((out/'StatCraft-source.zip').read_bytes()).hexdigest()
manifest['printing_preview']='StatCraft-print-preview.png'
assert smoke['printing_preview_pdf_worksheet_pagination_native_cancel']=='passed'
feature='Page setup, print preview, system printing and PDF for full-frame graphs, paginated reports and all-row worksheets with repeated headings, horizontal bands and four print options'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['graph_builder_rea_evidence']='statcraft-graph-builder-contract.md'
manifest['graph_builder_packaged_verification']=json.loads((root/'work/graph-builder-packaged-verified.json').read_text())
manifest['graph_builder_workspace']='StatCraft-graph-builder-workspace.png'
assert smoke['graph_builder_live_drop_roles_nine_types_isolation_mpx_similar']=='passed'
feature='Nine-family Graph Builder with searchable named columns, Qt drag/drop/add/remove roles, applicable options, isolated live previews and atomic Create/cancel, typed source-bound MPX/rerun/column identity, Make Similar and styles/brushing/layout integration'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['categorical_points_rea_evidence']='statcraft-individual-interval-contract.md'
manifest['categorical_points_packaged_verification']=json.loads((root/'work/individual-interval-packaged-verified.json').read_text())
manifest['categorical_points_preview']='StatCraft-individual-interval-preview.png'
manifest['remaining_work']='StatCraft-remaining-work.md'
assert smoke['individual_interval_eight_variants_display_ci_se_pool_bonferroni_mpx']=='passed'
feature='Four individual-value and four interval creation variants, named multiple response/group roles, Data View/jitter/attribute colors, Student-t and SE intervals with one-sided/within-response pooled/Bonferroni options, separate object styles, source-row brushing, tracked MPX/rerun/column identity, Make Similar and layouts'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['dotplot_creation_rea_evidence']='statcraft-dotplot-creation-contract.md'
manifest['dotplot_creation_packaged_verification']=json.loads((root/'work/dotplot-variants-packaged-verified.json').read_text())
manifest['dotplot_creation_preview']='StatCraft-dotplot-variants-preview.png'
assert smoke['dotplot_seven_variants_stacking_roles_brushing_mpx_similar_layout']=='passed'
feature='Seven dotplot variants with real stack/group lanes, named response and multiple grouping roles, category order, Data View attribute assignment, value scale/intervals, source-row brushing, object styles, tracked MPX/rerun/column identity, Make Similar and graph layouts'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['boxplot_creation_rea_evidence']='statcraft-boxplot-creation-contract.md'
manifest['boxplot_creation_packaged_verification']=json.loads((root/'work/boxplot-variants-packaged-verified.json').read_text())
manifest['boxplot_creation_preview']='StatCraft-boxplot-variants-preview.png'
manifest['validation_environment']={'qt_platform':smoke.get('qt_platform','unknown'),'offscreen_fonts':'Installed Windows Segoe UI regular/bold/italic/bold-italic and Consolas regular/bold, not bundled','windows_clipboard_live_verified':False,'reason':'Windows OpenClipboard returns access denied (5) in the execution session; final automated acceptance uses offscreen Qt.'}
assert smoke['boxplot_variants_group_roles_display_mpx_similar_layout']=='passed'
feature='Four boxplot variants, named response and multiple categorical grouping roles, outer/inner category order and response panels, boxes/whiskers/outliers/individual points/means/medians/connect lines, object styles, source-bound MPX recipes, rerun, Make Similar, layouts and full-width export'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['histogram_creation_rea_evidence']='statcraft-histogram-creation-contract.md'
manifest['histogram_creation_packaged_verification']=json.loads((root/'work/histogram-variants-packaged-verified.json').read_text())
manifest['histogram_creation_preview']='StatCraft-histogram-variants-preview.png'
assert smoke['histogram_variants_group_fits_roles_styles_mpx_similar_layout']=='passed'
feature='Four histogram creation variants, multiple named responses and numeric/text grouping, shared-bin overlays/separate panels, group-specific Normal fits and scales, object styles, source-bound MPX recipes and Make Similar; complete multipanel export and graph lifetime fixes'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['column_operations_rea_evidence']='statcraft-column-operations-contract.md'
manifest['actual_project_column_operations']=json.loads((root/'work/quiz1-column-operations-verified.json').read_text())
manifest['column_operations_packaged_verification']=json.loads((root/'work/quiz1-columns-packaged-verified.json').read_text())
manifest['column_similar_demo_packaged_verification']=json.loads((root/'work/columns-similar-packaged-verified.json').read_text())
manifest['make_similar_preview']='StatCraft-make-similar-preview.png'
for flag in ('column_header_insert_move_delete_formula_mpx_copy','make_similar_original_new_roles_options_source_mpx'):
    assert smoke[flag]=='passed'
feature='Header/name-row column selection, multi-column insertion/movement/deletion with formula/view undo, data-only imported MPX structural save-copy preserving retained identities/blobs, and native-evidenced Make Similar role/original/new grid with saved setup and independent tracked graphs'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest.pop('requested_stopping_point',None)
manifest['panel_layout_rea_evidence']='statcraft-panel-layout-contract.md'
manifest['compositions_packaged_verification']=json.loads((root/'work/compositions-packaged-verified.json').read_text())
for flag in ('interactive_brushing_source_rows_navigation','by_variable_panels_styles_shared_scales_mpx_rerun','ordered_graph_layouts_edit_undo_mpx_snapshots'):
    assert smoke[flag]=='passed'
feature='Interactive point/rectangle brushing with source worksheet rows and navigation; BY-variable panel recalculation with shared scales and inherited group styles; ordered editable graph layouts with detached snapshots, undo and authored MPX persistence'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest['value_order_rea_evidence']='statcraft-value-order-contract.md'
manifest['worksheet_navigation_evidence']='statcraft-worksheet-navigation-contract.md'
manifest['worksheet_navigation_native_handlers_verified']=False
manifest['value_order_packaged_verification']=json.loads((root/'work/value-order-packaged-verified.json').read_text())
manifest['formula_recalculation_rea_evidence']='statcraft-formula-recalculation-contract.md'
manifest['formula_workflow_packaged_verification']=json.loads((root/'work/formula-workflow-packaged-verified.json').read_text())
manifest['graph_options_rea_evidence']='statcraft-graph-edit-pane-contract.md'
manifest['current_source_audit']='StatCraft-current-feature-audit.md'
manifest['ranked_parity_backlog']='StatCraft-parity-backlog.md'
manifest['graph_options_screenshot']='StatCraft-graph-options-pane.png'
manifest['graph_options_packaged_verification']=json.loads((root/'work/graph-options-packaged-verified.json').read_text())
manifest['graph_options_scope']='Docked live annotation editor, per-result MPX presentation settings, PNG/clipboard annotations. Cartesian limits/grid are original bounded controls; native More options destination and full object editing remain unrecovered/incomplete.'
manifest['graph_menu_rea_evidence']='statcraft-graph-menu-contract.md'
manifest['graph_coverage']='StatCraft-graph-coverage.md'
manifest['graph_gallery']='StatCraft-graph-gallery.png'
manifest['worksheet_interactions_rea_evidence']='statcraft-worksheet-interactions-evidence.md'
manifest['collections_rea_evidence']='statcraft-mpx-constants-matrices-evidence.md'
manifest['graph_suite_packaged_verification']=json.loads((root/'work/graph-suite-packaged-verified.json').read_text())
manifest['mpx_date_evidence']='statcraft-mpx-date-column-evidence.md'
manifest['date_workbook_packaged_verification']=json.loads((root/'work/date-workbook-packaged-verified.json').read_text())
manifest['mpx_text_evidence']='statcraft-mpx-text-column-evidence.md'
manifest['text_workbook_packaged_verification']=json.loads((root/'work/text-workbook-packaged-verified.json').read_text())
manifest['remaining']=[value.replace('DOE, nonnormal','Fractional, response-surface, mixture, screening and Taguchi DOE; nonnormal') for value in manifest['remaining']]
manifest['remaining']=[value.replace('Fractional, response-surface','Response-surface').replace('full MPX writes','row/type/worksheet structural MPX writes') for value in manifest['remaining']]
manifest['remaining']=[value.replace('row/type/worksheet structural','text/date/type/worksheet structural') for value in manifest['remaining']]
manifest['remaining']=[value.replace('new native project creation','native acceptance of new projects beyond the StatCraft numeric profile') for value in manifest['remaining']]
for feature in ('StatCraft column/row selection highlighting (#004a7c header badge, #eaeaea column fill with #004a7c border, #d8d8d8 active row numbers), full Data Window right-click menu (RT_MENU 9839), Output/Graph dropdown & right-click menu (RT_MENU 19209/23702 excluding StatCraft software items), Navigator WORKSHEET 1 hierarchy without Commands header, and original StatCraft Gaussian-curve + diamond emblem',
                'StatCraft light chrome (#f1f1f1/#f4f4f4/#e6e6e6/#00569a), 11 top-level menus, 21-button Standard+Worksheet toolbar, watermark welcome stage, 16-column compact grid, bottom worksheet chrome bar, blue status bar with pane/zoom/Command Line controls, and Find/Go To/Assign Formula/Move Columns/Sort/Rank/Session Command workflows',
                'All 26 native Graph menu labels/order; working bounded variants for 22 additional charts and a chart launcher',
                'Graph results open on Graph; Tab/Enter editor navigation and worksheet deletion with result cleanup',
                'Owned numeric constants/matrices, column-major edits, missing sidecars, stable C/K/M identities and calculator K references',
                'Original numeric/text/date MPX workbooks with distinct missing dates and epoch values; previous numeric/text profiles remain editable',
                'Readable ISO date/time cells, date entry and clipboard, C-column date labels and full stored serial precision',
                'Original numeric/text MPX workbook creation with distinct missing and empty text cells; previous numeric profile remains editable',
                'Blank-column text auto-detection through typed grid entry, undo and C-column type labels',
                'Pearson/Spearman correlation with row-aligned pairwise or listwise deletion and tracked reruns',
                'Exact one-proportion tests and two-proportion Z/Fisher comparisons with explicit confidence interval methods',
                'Available-variable list with typed role fields; simple scatterplots use Y/X pair rows',
                'Editable column-name row under C identifiers, including undo/redo and MPX label persistence',
                'Observed internal numeric blob references in MPX; same-length binary double edits preserve blob storage',
                'Anderson-Darling normality test with approximate P value and saved normal probability plot',
                'One normal-population variance chi-square test with standard deviation and variance confidence intervals',
                'All six scatterplot modes with grouping, per-group linear fits, connection ordering and saved MPX reruns',
                'Full two-level factorial creation: 2–8 numeric factors, replicates, centers, seeded randomization and one block',
                'Coded factorial least squares through three-way interactions, estimated effects, ANOVA, residual plots and saved MPX analysis reruns',
                'Appended independent numeric columns in plain MPX worksheets within the original row extent; save/reopen/rerun with original identities and members retained',
                'Regular fractional designs with explicit signed generators, defining relations, exact alias tables and resolution',
                'Available/Selected Terms dialog with hierarchical model selection, observed confounding checks and persisted selected-term MPX recipes',
                'Plain typed numeric MPX row growth with matched inline/blob lengths, archive-wide JSON sharing checks, preserved placeholders and saved recipe reruns',
                'Original numeric MPX project creation, multiple worksheets, stable source identities and persisted DOE metadata/results',
                'Bottom worksheet tabs and plus button; rename and duplicate in StatCraft-created workbooks; strict canonical profile protects imported content'):
    if feature not in manifest['supported']: manifest['supported'].append(feature)
manifest['remaining']=[value.replace('text/date/type/worksheet structural','imported text growth, date/type/worksheet structural').replace('StatCraft numeric profile','StatCraft data-only profile') for value in manifest['remaining']]
feature='Docked Edit Graph Options pane with live title/subtitle/footnote controls, X/Y label placement, per-graph MPX presentation persistence and annotated PNG/clipboard export; extra result-state strip removed'
if feature not in manifest['supported']:manifest['supported'].append(feature)
feature='Dependency-aware live column formulas, shared automatic mode, all-worksheet manual calculation, atomic undo/rollback and reference tracking through moves/inserts; dynamic conditional overlays preserve manual colors and reopen in authored MPX'
if feature not in manifest['supported']:manifest['supported'].append(feature)
feature='Text Value Order controls supported categorical graphs and grouped tables with stale-result detection/MPX reruns; independent overflow-tab scrolling preserves worksheet/data-page identity, with wheel/keyboard row-page boundaries'
if feature not in manifest['supported']:manifest['supported'].append(feature)
feature='Supported graph-object hit testing and double-click attributes/scales/annotations; symbols, lines, fills, opacity and visibility; histogram intervals/scale/cumulative/Normal fits from source snapshots; appearance undo, MPX reruns and annotated export'
if feature not in manifest['supported']:manifest['supported'].append(feature)
manifest.update(release='preview-46-oneway-anova',built_at=datetime.now(timezone.utc).isoformat(),
    bytes=exe.stat().st_size,sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
    reverse_engineering_complete=False,full_parity_verified=False,
    ui={'framework':'Qt / PySide6 6.12.0','style':'StatCraft light chrome (#f1f1f1 toolbar, #ffffff/#f3f3f3 navigator, #e6e6e6 output stage, #00569a status bar)',
        'worksheet':'16-column compact Qt grid, #004a7c column/row selection highlighting, RT_MENU 9839 right-click context menu, editable column-name row, entry direction toggle, bottom worksheet chrome bar',
        'reports':'Named result-document tabs, separate Graph/Report/Text view selector, saved ReportPad and workspace; white result cards with dropdown/context menu, WORKSHEET-grouped Navigator, docked live graph Options pane and hidden extra result-state strip; command line/history pane',
        'icons':'Original indigo/cyan Gaussian-curve + diamond StatCraft logo and multiresolution toolbar/context-menu vector icons','python_tk_ui_packaged':False},
    verification={'source_tests':tests,'packaged':smoke},
    source_archive='StatCraft-source.zip',
    library_source_archives=['QtBase-6.12.0-source.zip','PySide6-6.12.0-source.zip'])
(out/'StatCraft-preview-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(out/'StatCraft-preview-manifest.txt').write_text('StatCraft preview43 — binary logistic regression and probability prediction\n\n'+
    'Adds Fit Binary Logistic Model and Predict for individual binary and grouped event/trial responses, with continuous/categorical predictors, hierarchical interactions, LP separation screening, 2x2 ROC/residual plots, row brushing and MPX reruns.\n'+
    'Adds Predict for supported regression, fixed GLM and response-surface models, with named values/columns, intervals, child dialogs, readable reports and tracked MPX reruns.\n'+
    'Adds balanced crossed Gage R&R ANOVA with named roles/options, variance evaluation, six graphs and MPX reruns/source-column remapping.\n'+
    'Executable: '+exe.name+'\nStandalone x64 Windows EXE; no StatCraft runtime, account or activation required.\n'+
    f'{tests} source tests passed. Packaged model-driven Factorial/Contour/Surface Plots and Factorial Predict, Response Optimizer, binary logistic regression and probability prediction, model prediction, crossed Gage R&R, response-surface design/analysis and all implemented child dialogs, quadratic fits/lack-of-fit/pure error/metadata/coding/MPX reruns, GLM fixed factors/interactions, all five child dialogs, compact reports, 2x2 residual geometry and MPX setup/reruns, typed stack/unstack/transpose/worksheet stack/unique-key merge and independent native-source preparation/MPX roundtrip, result-tab lifecycle/MPX workspace/ReportPad notes and snapshots, maximized startup/splash/project argument/clean exit, interactive output zoom and heatmap graphs, native Word/PowerPoint snapshots/editable text/embedded graphs/cancellation, print snapshots/PDF/pagination/preview/cancellation, nine-family live Graph Builder/drop roles/preview isolation/Create/cancel, previous graph/worksheet workflows and complete exports, MPX/rerun/Make Similar/layout and previous column/worksheet workflows passed. Complete native parity remains unverified.\n'+
    'Entire StatCraft reconstruction is unfinished; see StatCraft-completion-status.md.\n'+
    f'SHA256: {manifest["sha256"]}\n',encoding='utf-8')
parts=[]
for path in sorted((root/'work/statcraft/notices').iterdir()):
    if path.is_file() and path.suffix in ('.txt','.terms','.toml'):
        parts.append(path.name+'\n\n'+path.read_text(encoding='utf-8',errors='replace'))
(out/'StatCraft-third-party-notices.txt').write_text('\n\n'.join(parts),encoding='utf-8')
(out/'statcraft-desktop-ui-notes.md').write_text('''# Modern desktop update

Preview 11 replaces the Tk interface with Qt/PySide6, using Windows 11 controls,
an explicit light palette, high-DPI line icons, a resizable navigator, an editable
worksheet table, typed procedure dialogs and structured report tables.
Graphs are embedded in scrollable result tabs; larger plots retain readable
axes without shrinking the worksheet out of view. MPX worksheet navigation,
save-copy, linked report snapshots, stale input indicators and explicit reruns
continue through the existing independent backend.

Preview 12 adds available-variable lists and typed role fields, a Y/X pair table
for simple scatterplots, and an editable column-name row under the C identifiers.
It adds Pearson/Spearman correlation, binary proportion tests, and support for
the observed MPX numeric-double blob form. See StatCraft-preview-12-changes.md.

Preview 13 adds Anderson-Darling normality testing with probability plotting and
one-variance normal-population chi-square inference, including saved MPX recipes
and reruns. See StatCraft-preview-13-changes.md for assumptions and limitations.

Preview 14 adds bounded two-level full factorial creation/analysis and all six
scatterplot variants. DOE dialog labels and main control grouping follow the
installed resource templates recovered with REA. Runtime native defaults,
HTML/native UI selection and exact visual parity remain unverified. See
StatCraft-preview-14-changes.md and statcraft-doe-factorial-native-findings.md.

Preview 15 adds numeric response columns in supported plain MPX worksheets,
regular fractional designs with explicit generators and aliases, and an
Available/Selected Terms dialog. See StatCraft-preview-15-changes.md and
StatCraft-build-priorities.md for scope and the ordered remaining work.

Preview 16 adds numeric row growth in plain MPX worksheets while retaining
inline/blob storage, checking references across archive JSON and preserving
uninitialized native placeholders. See StatCraft-preview-16-changes.md.

Preview 17 adds bottom worksheet tabs with a plus control, File > New > Project
or Worksheet, and rename/duplicate commands. New numeric MPX workbooks retain
worksheets, original StatCraft results and design metadata. Imported foreign
native content retains conservative handling. See StatCraft-preview-17-changes.md.

Preview 18 adds text columns in StatCraft-created MPX projects, including grouped
analysis recipes and explicit missing-versus-empty preservation through original
metadata. Blank-column typed text now selects the text type. Imported native text
growth and native application acceptance remain unverified. See StatCraft-preview-18-changes.md.

Preview 19 adds date columns to StatCraft-created MPX projects, readable ISO
date/time cells, date clipboard handling and missing-date sidecar preservation.
Stored day serial precision is retained independently of display. Native date
formats and native application acceptance remain unverified. See StatCraft-preview-19-changes.md.

Preview 20 adds all 26 Graph menu commands in recovered native order, bounded
working plots, graph-first display, worksheet Tab/Enter navigation and deletion,
and stored numeric constant/matrix editors with calculator K references. Native
Graph Builder canvas, many graph variants/options and native runtime fidelity
remain unfinished. See StatCraft-preview-20-changes.md and StatCraft-graph-coverage.md.

Preview 23 preserves the intervening toolbar, context-menu and worksheet updates,
adds a docked Edit Graph Options pane with live annotation controls and saved
presentation settings, and hides the extra result-state strip. See
StatCraft-preview-23-changes.md and StatCraft-parity-backlog.md for the refreshed
work order. Native whole-graph object editing and numerical parity remain open.

Preview 24 implements live formula dependencies, a shared automatic-calculation
toggle and all-worksheet manual calculation, transaction-aware undo and dynamic
conditional coloring independent of manual highlights. Native formula language,
saved native formula objects and exact overwrite/error behavior remain bounded.
See StatCraft-preview-24-changes.md and the updated ranked backlog.

Preview 25 adds supported categorical graph/table ordering, line-based text
Value Order, stale-result detection and MPX reruns. External worksheet controls
scroll the tab strip independently of row paging; native arrow semantics remain
unrecovered. Row views remain bounded, with wheel/keyboard boundary navigation.
See StatCraft-preview-25-changes.md.

Preview 26 adds supported graph-object hit regions/double-click routes, attribute
editing, histogram scales and Normal fitting from actual source observations,
appearance undo/MPX reruns and export. Per-point and full native editor behavior
remain unfinished. See preview-26 changes.

Preview 27 adds interactive point/rectangle brushing linked to original worksheet
rows, BY-variable graph recalculation with shared scale choices and inherited
group appearance, and ordered 1–9 row/column graph layouts with snapshots,
editing, undo and authored MPX persistence. See preview-27 changes.

Preview 28 fixes header/name-row column targeting, multiple column operations,
after-last-used placement, formula/view undo and imported data-only MPX numeric
insertion/move/delete save-copy. Make Similar Graph uses a prefilled role/original/
new-variable grid and creates independent tracked graphs with retained setup.
Native model/formula/locked structures and native reopening remain unverified.
See StatCraft-preview-28-changes.md.

Preview 29 adds the four histogram chooser variants, named response/group roles,
shared-bin overlays and separate group panels, per-group Normal fits and scale
options, MPX/rerun/Make Similar integration, full multipanel export and welcome
screen graph lifetime fixes. One grouping variable,16 series,100000 retained
observations and Normal fits are bounded scope. See preview-29 changes.

Preview 30 adds the boxplot gallery, named response/multiple group roles, category
scale ordering and response panels, working Data View/Scale/Labels controls,
MPX/rerun/Make Similar/layout integration and full-width exports. See preview-30
changes for bounds and unresolved native behavior.

Preview31 adds seven dotplot variants with real grouped/stacked lanes, named
response/group roles, Data View attribute assignment, value-scale intervals,
source-row brushing and MPX/rerun/Make Similar/layout integration. See preview31
changes for bounds and unresolved native behavior.

Preview32 adds individual-value and interval galleries, named multiple group
roles, Data View/jitter and confidence/SE options, one-sided bounds, within-response
pooled/Bonferroni calculations, object styles, brushing and tracked MPX workflows.
See preview32 changes and the remaining-work report for bounds and gaps.

Preview33 replaces the Graph Builder picker with a real nine-family workspace,
searchable named columns, drag/drop roles, applicable options and isolated live
previews. Typed builder recipes reopen/rerun and support column edits, Make
Similar and graph layouts. See preview33 changes for bounds and REA limits.

Preview34 replaces the Print export alias with page setup, print preview,
system printing and PDF output. Graph frames, wrapped report text and all-row
worksheets use a shared renderer. Four worksheet print options, repeated headings,
column bands and page ranges are supported. Physical printer output and exact
native print behavior remain unverified. See preview34 changes.

Preview35 replaces HTML Word/PowerPoint shortcuts with native DOCX/PPTX
packages, editable report text and embedded graph frames. Wide Word reports use
landscape pages and long presentations paginate. The app requires no Office
installation. Source/frozen checks and independent import/render checks cover
the bounded workflow. Live Office automation and fully editable charts/tables
remain unfinished. See preview35 changes.

Preview36 adds a short original splash and maximized startup, project arguments,
explicit startup-widget cleanup and real transformed graph/report zoom. Worksheet
widths and graph export dimensions remain independent. Heatmap Office exports
contain actual graph images and readable summaries. See preview36 changes.

Preview37 adds named result-document tabs and an independent view selector,
non-destructive close/reopen/reorder/cycle controls, selected-view/zoom/scroll
restoration and a saved MPX workspace. ReportPad now preserves editable notes,
undoable collected summaries, Office/print snapshots and project persistence.
Native report object encoding and rich embedded reports remain unfinished.
See preview37 changes.

Preview38 adds typed stack/unstack/transpose, worksheet stacking and unique-key
merging, named variable selectors and MPX persistence. Imported native sources
prepare into independent projects. Sources remain intact. Native master append
and repeated/composite-key merge workflows remain unfinished. See preview38 changes.

Preview39 adds fixed-factor General Linear Model with categorical factors,
covariates, hierarchical interactions, adjusted/sequential ANOVA and five working
Model/Options/Coding/Graphs/Results child dialogs. Compact reports and 2x2 residual
plots replace raw model arrays. MPX setups restore and rerun across column moves.
Random/nested models, model prediction, means/comparisons, storage and stepwise
remain unfinished. See preview39 changes and the GLM evidence contract.

Preview40 adds one-block response-surface CCD and Box-Behnken creation,
working creation/analysis child dialogs, coded quadratic regression and guarded
pure-error/lack-of-fit tests. Design coding and models save/reopen/rerun through
MPX and follow column moves. Larger/fractional catalogs, blocks/categorical
factors, optimization and model-driven surface/prediction tools remain open.
See preview40 changes and its native evidence contract.

Preview41 adds balanced crossed Gage R&R ANOVA with named roles/options,
interaction pooling, variance/study/tolerance evaluation, six graphs with row
brushing and tracked MPX reruns/column moves. See preview41 changes.

Preview42 adds Predict for supported regression, fixed GLM and response-surface
models, with named manual/column settings, CI/PI and one-sided bounds, working
Options/Results/View Model dialogs and MPX reruns/remapping. See preview42 changes.

Preview43 adds Binary Logistic Regression (`Fit Binary Logistic Model` and
`Predict`) with individual binary and grouped event/trial responses, continuous
and categorical predictors, hierarchical interactions, Model/Options/Graphs/
Results child dialogs, LP separation screening, Wald/LR tests, odds ratios,
2x2 ROC/residual plots with row brushing, logit-scale probability predictions
and MPX reruns/column remapping. See preview43 changes and the logistic evidence
contract.

Preview44 adds Response Optimizer (`Response Optimizer?`) across Multiple
Regression, General Linear Model, 2-Level Factorial DOE, Response Surface
Regression and Binary Logistic Regression, with single- and multi-response
Derringer-Suich desirability, variable constraints and starting values, working
Desirability/Options/Graphs/Results/View Model child dialogs, multi-panel
Optimization Plot and MPX reruns/column remapping. See preview44 changes and
the optimizer evidence contract.

Preview45 adds Model-Driven Factorial Plots (`Factorial Plots?`), Contour Plot
(`Contour Plot?`), and Surface Plot (`Surface Plot?`) across Multiple Regression,
General Linear Model, 2-Level Factorial DOE, Response Surface Regression and
Binary Logistic Regression, plus Two-Level Factorial `Predict?`, with Main Effects
and Interaction plots, 2D contour grids, 3D shaded/wireframe surfaces, hold values,
working child dialogs and MPX reruns/column remapping. See preview45 changes and
the model plots evidence contract.

The UI and packaged workflow checks do not establish complete StatCraft numerical
or file-format parity. Native stored graphs/reports remain preserved and inactive.
Many major feature families are still absent; see the completion-status document.

The runtime uses LGPLv3 Qt/PySide6. Application rebuild inputs and corresponding
unmodified library source archives accompany this preview. No StatCraft program
code or runtime is included in the executable.
''',encoding='utf-8')
print('Modern release manifest and notices updated.')




