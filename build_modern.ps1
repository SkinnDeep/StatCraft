$ErrorActionPreference = 'Stop'
$taskWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskPython = 'C:/Users/funny/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$env:PYTHONPATH = (Join-Path $taskWorkspace 'work/statcraft-build-deps') + ';' + $PSScriptRoot
$env:PYTHONHASHSEED = '0'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:TEMP = Join-Path $taskWorkspace 'work'
$env:TMP = $env:TEMP
Push-Location $taskWorkspace
try {
    & $taskPython work/statcraft/verify_tests.py
    if ($LASTEXITCODE -ne 0) { throw 'Source verification failed.' }
    & $taskPython work/statcraft/launch_modern.py --self-test work/modern-source-smoke.json
    if ($LASTEXITCODE -ne 0) { throw 'Qt verification failed.' }
    & $taskPython -m PyInstaller --noconfirm --distpath work/statcraft-modern-next --workpath work/statcraft-modern-freeze work/statcraft/modern.spec
    if ($LASTEXITCODE -ne 0) { throw 'Packaging failed.' }
    $taskExe = Join-Path $taskWorkspace 'work/statcraft-modern-next/StatCraft.exe'
    $taskSmoke = Join-Path $taskWorkspace 'work/modern-packaged-smoke.json'
    $taskProcess = Start-Process -FilePath $taskExe -ArgumentList @('--self-test', $taskSmoke) -WindowStyle Hidden -PassThru -Wait
    if ($taskProcess.ExitCode -ne 0) { throw 'Packaged verification failed.' }
    $taskResult = Get-Content -LiteralPath $taskSmoke -Raw | ConvertFrom-Json
    if (-not $taskResult.frozen -or $taskResult.qt_widgets -ne 'passed' -or $taskResult.mpx_save_reopen_rerun -ne 'passed' -or $taskResult.mpx_binary_blob_load_edit_save -ne 'passed') { throw 'Incomplete packaged verification.' }
    if ($taskResult.mpx_append_numeric_column_save_reopen_rerun -ne 'passed' -or $taskResult.fractional_generators_terms_aliases_mpx_rerun -ne 'passed') { throw 'New MPX/DOE packaged verification incomplete.' }
    if ($taskResult.mpx_numeric_rows_dialog_blob_save_reopen_rerun -ne 'passed') { throw 'Numeric row-growth packaged verification incomplete.' }
    if ($taskResult.new_mpx_workbook_tabs_rename_duplicate_save_rerun -ne 'passed') { throw 'New MPX workbook packaged verification incomplete.' }
    if ($taskResult.owned_mpx_text_grid_groups_missing_save_rerun -ne 'passed') { throw 'Text MPX workbook packaged verification incomplete.' }
    if ($taskResult.owned_mpx_dates_type_display_clipboard_precision_save -ne 'passed') { throw 'Date MPX workbook packaged verification incomplete.' }
    foreach ($taskFlag in @('stored_constants_matrices_editors_calculator_mpx','worksheet_tab_enter_editor_navigation_delete_confirmation','all_26_graph_menu_actions_dialogs_render_graph_first_mpx_rerun','statcraft_22_toolbar_21_icons_chrome_statusbar_workflows','statcraft_selection_highlighting_context_menus_navigator_logo')) {
        if ($taskResult.$taskFlag -ne 'passed') { throw ('New packaged workflow incomplete: '+$taskFlag) }
    }
    if ($taskResult.docked_graph_editor_live_annotations_axes_mpx_and_removed_header -ne 'passed') { throw 'Graph Options pane packaged verification incomplete.' }
    foreach ($taskFlag in @('graph_object_hit_testing_doubleclick_styles_undo_export_mpx','histogram_scales_normal_fit_counts_density_cumulative_mpx','graph_style_renderers_3d_camera_preserved')) {
        if ($taskResult.$taskFlag -ne 'passed') { throw ('Graph editing verification incomplete: '+$taskFlag) }
    }
    foreach ($taskFlag in @('automatic_formula_dependencies_global_menu_atomic_undo_mpx','dynamic_conditional_colors_formula_edits_manual_styles_mpx','value_order_text_modes_counts_groups_tables_mpx_rerun','worksheet_tab_scroll_preserves_sheet_rows_and_row_page_navigation')) {
        if ($taskResult.$taskFlag -ne 'passed') { throw ('New worksheet workflow incomplete: '+$taskFlag) }
    }
    foreach ($taskFlag in @('interactive_brushing_source_rows_navigation','by_variable_panels_styles_shared_scales_mpx_rerun','ordered_graph_layouts_edit_undo_mpx_snapshots')) {
        if ($taskResult.$taskFlag -ne 'passed') { throw ('Composition verification incomplete: '+$taskFlag) }
    }
    foreach ($taskFlag in @('column_header_insert_move_delete_formula_mpx_copy','make_similar_original_new_roles_options_source_mpx')) {
        if ($taskResult.$taskFlag -ne 'passed') { throw ('Column/similar graph verification incomplete: '+$taskFlag) }
    }
    if ($taskResult.histogram_variants_group_fits_roles_styles_mpx_similar_layout -ne 'passed') { throw 'Histogram creation verification incomplete.' }
    if ($taskResult.boxplot_variants_group_roles_display_mpx_similar_layout -ne 'passed') { throw 'Boxplot creation verification incomplete.' }
    if ($taskResult.dotplot_seven_variants_stacking_roles_brushing_mpx_similar_layout -ne 'passed') { throw 'Dotplot creation verification incomplete.' }
    if ($taskResult.individual_interval_eight_variants_display_ci_se_pool_bonferroni_mpx -ne 'passed') { throw 'Individual/interval graph verification incomplete.' }
    if ($taskResult.graph_builder_live_drop_roles_nine_types_isolation_mpx_similar -ne 'passed') { throw 'Graph Builder verification incomplete.' }
    if ($taskResult.printing_preview_pdf_worksheet_pagination_native_cancel -ne 'passed') { throw 'Printing verification incomplete.' }
    if ($taskResult.office_native_docx_pptx_graph_report_context_cancel -ne 'passed') { throw 'Office export verification incomplete.' }
    if ($taskResult.output_zoom_proxy_geometry_interaction_heatmap_office -ne 'passed') { throw 'Output zoom verification incomplete.' }
    if ($taskResult.output_workspace_tabs_close_reopen_report_mpx -ne 'passed') { throw 'Output workspace verification incomplete.' }
    if ($taskResult.typed_data_preparation_dialogs_native_source_mpx -ne 'passed') { throw 'Data preparation verification incomplete.' }
    if ($taskResult.glm_fixed_factors_interactions_child_dialogs_residuals_mpx -ne 'passed') { throw 'General linear model verification incomplete.' }
    if ($taskResult.response_surface_designs_children_quadratic_lof_mpx -ne 'passed') { throw 'Response surface verification incomplete.' }
    if ($taskResult.gage_rr_crossed_anova_options_six_graphs_rows_mpx_columns -ne 'passed') { throw 'Crossed Gage R&R verification incomplete.' }
    if ($taskResult.prediction_three_models_values_columns_intervals_children_mpx_remapping -ne 'passed') { throw 'Prediction workflow verification incomplete.' }
    if ($taskResult.binary_logistic_fit_events_terms_roc_predict_mpx_remapping -ne 'passed') { throw 'Binary logistic regression verification incomplete.' }
    if ($taskResult.response_optimizer_desirability_constraints_plot_mpx_remapping -ne 'passed') { throw 'Response optimizer verification incomplete.' }
    if ($taskResult.model_plots_factorial_contour_surface_predict_five_models_mpx_remapping -ne 'passed') { throw 'Model plots verification incomplete.' }
    if ($taskResult.oneway_anova_stacked_unstacked_comparisons_graphs_mpx -ne 'passed') { throw 'One-Way ANOVA verification incomplete.' }
    if ($taskResult.subgroup_control_charts_xbar_r_xbar_s_eight_tests_mpx -ne 'passed') { throw 'Subgroup control charts verification incomplete.' }
    if ($taskResult.test_equal_variances_dialog_summary_plot_storage_mpx -ne 'passed') { throw 'Test for Equal Variances verification incomplete.' }
    if ($taskResult.two_sample_t_dialog_plots_mpx -ne 'passed') { throw 'Two-Sample t verification incomplete.' }
    if ($taskResult.one_sample_z_dialog_plots_mpx -ne 'passed') { throw 'One-Sample Z verification incomplete.' }
    if ($taskResult.one_sample_proportion_dialog_reports_mpx -ne 'passed') { throw 'One-Sample Proportion verification incomplete.' }
    if ($taskResult.two_sample_proportion_dialog_reports_mpx -ne 'passed') { throw 'Two-Sample Proportion verification incomplete.' }
    if ($taskResult.one_sample_poisson_dialog_reports_mpx -ne 'passed') { throw 'One-Sample Poisson Rate verification incomplete.' }
    if ($taskResult.two_sample_poisson_dialog_reports_mpx -ne 'passed') { throw 'Two-Sample Poisson Rate verification incomplete.' }
    if ($taskResult.one_sample_t_dialog_plots_mpx -ne 'passed') { throw 'One-Sample t verification incomplete.' }
    if ($taskResult.paired_t_dialog_plots_mpx -ne 'passed') { throw 'Paired t verification incomplete.' }
    if ($taskResult.one_and_two_variances_dialogs_reports_mpx -ne 'passed') { throw 'One and Two Variances verification incomplete.' }
    if ($taskResult.capability_analysis_normal_dialogs_reports_plot_mpx -ne 'passed') { throw 'Capability Analysis verification incomplete.' }
    if ($taskResult.capability_sixpack_normal_dialogs_reports_plot_mpx -ne 'passed') { throw 'Capability Sixpack verification incomplete.' }
    if ($taskResult.imr_control_chart_dialogs_reports_plot_mpx -ne 'passed') { throw 'I-MR Control Chart verification incomplete.' }
    if ($taskResult.attribute_control_charts_p_np_c_u_dialogs_reports_plot_mpx -ne 'passed') { throw 'Attribute Control Charts verification incomplete.' }
    if ($taskResult.time_weighted_control_charts_ewma_ma_cusum_dialogs_reports_plot_mpx -ne 'passed') { throw 'Time-Weighted Control Charts verification incomplete.' }
    if ($taskResult.rare_event_control_charts_g_t_dialogs_reports_plot_mpx -ne 'passed') { throw 'Rare Event Control Charts verification incomplete.' }
    if ($taskResult.multivariate_control_charts_tsquared_genvar_mewma_mpx -ne 'passed') { throw 'Multivariate Control Charts verification incomplete.' }
    if ($taskResult.pareto_chart_dialog_reports_plot_mpx -ne 'passed') { throw 'Pareto Chart verification incomplete.' }
    if ($taskResult.type1_gage_dialog_reports_plot_mpx -ne 'passed') { throw 'Type 1 Gage Study verification incomplete.' }
    if ($taskResult.tolerance_intervals_dialog_reports_plot_mpx -ne 'passed') { throw 'Tolerance Intervals verification incomplete.' }
    if ($taskResult.attribute_capability_dialog_graph_mpx_bindings -ne 'passed') { throw 'Attribute capability verification incomplete.' }
    if ($taskResult.capability_between_within_dialog_reports_plot_mpx -ne 'passed') { throw 'Between/Within capability verification incomplete.' }
    if ($taskResult.acceptance_control_chart_dialog_reports_plot_mpx -ne 'passed') { throw 'Acceptance Control Chart verification incomplete.' }
    if ($taskResult.capability_aiag_vda_machine_dialog_reports_plot_mpx -ne 'passed') { throw 'AIAG/VDA machine capability verification incomplete.' }
    if ($taskResult.shewhart_extended_limits_warning_bands_mpx -ne 'passed') { throw 'Shewhart extended limits & warning bands verification incomplete.' }
    if ($taskResult.capability_nonnormal_distribution_transform_mpx -ne 'passed') { throw 'Nonnormal capability verification incomplete.' }
    if ($taskResult.reliability_distribution_analysis_right_censoring_mpx -ne 'passed') { throw 'Reliability distribution analysis verification incomplete.' }
    if ($taskResult.capability_nonparametric_and_automated_tournament_mpx -ne 'passed') { throw 'Nonparametric and Automated capability verification incomplete.' }
    if ($taskResult.msa_advanced_nested_linearity_mpx -ne 'passed') { throw 'Advanced MSA verification incomplete.' }
    if ($taskResult.new_analysis_graphs_sources_statistical_integrity_mpx -ne 'passed') { throw 'New analysis integrity verification incomplete.' }
    if ($taskResult.multiple_variable_capability_dialogs_graphs_sources_mpx -ne 'passed') { throw 'Multiple variable capability verification incomplete.' }
    if ($taskResult.doe_planner_eleven_families_live_preview_excel_converter_mpx -ne 'passed') { throw 'DOE planner / Excel conversion verification incomplete.' }
    if ($taskResult.mixture_taguchi_models_prediction_dialogs_graphs_sources_mpx -ne 'passed') { throw 'Mixture / Taguchi workflow verification incomplete.' }
    if ($taskResult.dynamic_taguchi_slopes_sn_reference_dialog_graphs_sources_mpx -ne 'passed') { throw 'Dynamic Taguchi verification incomplete.' }
    if ($taskResult.mixture_contours_optimizer_constraints_dialog_graphs_sources_mpx -ne 'passed') { throw 'Mixture contour/optimizer verification incomplete.' }
    if ($taskResult.mixture_multiple_desirability_interactive_profiles_reoptimize_sources_mpx -ne 'passed') { throw 'Multiple mixture optimizer verification incomplete.' }
    if ($taskResult.mixture_process_blocks_covariates_fit_prediction_dialogs_sources_mpx -ne 'passed') { throw 'Mixture process model verification incomplete.' }
    if ($taskResult.mixture_process_conditional_contours_optimizer_coded_holds_intervals_sources_mpx -ne 'passed') { throw 'Conditional mixture exploration verification incomplete.' }
    if ($taskResult.native_mpx_saved_reports_graphs_gallery_capture_copy -ne 'passed') { throw 'Native saved MPX output verification incomplete.' }
    if ($taskResult.response_surface_58_catalog_matrix_blocks_prediction_graphs_mpx -ne 'passed') { throw 'Functional response-surface catalog verification incomplete.' }
    if ($taskResult.chart_hover_histograms_points_saved_native_layout_capture -ne 'passed') { throw 'Graph hover verification incomplete.' }
    if ($taskResult.mixture_joint_optimizer_mpx -ne 'passed') { throw 'Joint mixture/process optimizer verification incomplete.' }
    if ($taskResult.native_model_reconstruction_mpx -ne 'passed') { throw 'Native model reconstruction verification incomplete.' }
    if ($taskResult.time_series_forecasting_models_mpx -ne 'passed') { throw 'Time Series forecasting models verification incomplete.' }
    if ($taskResult.nonparametrics_statistical_tests_mpx -ne 'passed') { throw 'Nonparametric statistical tests verification incomplete.' }
    if ($taskResult.multivariate_statistical_analysis_mpx -ne 'passed') { throw 'Multivariate statistical analysis verification incomplete.' }
    if ($taskResult.equivalence_tests_tost_mpx -ne 'passed') { throw 'Equivalence tests TOST verification incomplete.' }
    if ($taskResult.power_and_sample_size_mpx -ne 'passed') { throw 'Power and sample size verification incomplete.' }
    if ($taskResult.tables_and_chi_square_mpx -ne 'passed') { throw 'Tables and chi-square verification incomplete.' }
    $taskStartup = Join-Path $taskWorkspace 'work/startup-packaged-verified.json'
    $taskStartupProcess = Start-Process -FilePath $taskExe -ArgumentList @('--verify-startup', $taskStartup, 'C:/Users/funny/Downloads/quiz1.mpx') -WindowStyle Hidden -PassThru
    if (-not $taskStartupProcess.WaitForExit(60000)) { Stop-Process -Id $taskStartupProcess.Id; throw 'Startup did not exit cleanly.' }
    if ($taskStartupProcess.ExitCode -ne 0) { throw 'Startup verification failed.' }
    $taskStartupResult = Get-Content -LiteralPath $taskStartup -Raw | ConvertFrom-Json
    if (-not $taskStartupResult.frozen -or -not $taskStartupResult.maximized -or -not $taskStartupResult.splash_dismissed -or -not $taskStartupResult.project_loaded) { throw 'Startup verification incomplete.' }
    Copy-Item -LiteralPath $taskExe -Destination (Join-Path $taskWorkspace 'outputs/StatCraft-preview99.exe')
    try { Copy-Item -LiteralPath $taskExe -Destination (Join-Path $taskWorkspace 'outputs/StatCraft.exe') -ErrorAction Stop }
    catch { Write-Warning 'StatCraft.exe is in use. Verified update is outputs/StatCraft-preview99.exe.' }
    Write-Output 'Verified Qt executable published as outputs/StatCraft-preview99.exe'
} finally { Pop-Location }

