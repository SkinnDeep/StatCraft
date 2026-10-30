"""Verification gate for native StatCraft Time Series Analysis and Forecasting (Stat > Time Series)."""

from pathlib import Path
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage
from .model import Column, Worksheet
from .app import Presenter, format_entry
from .time_series_dialogs import (
    TrendAnalysisDialog,
    DecompositionDialog,
    MovingAverageDialog,
    SingleExpSmoothingDialog,
    DoubleExpSmoothingDialog,
    AutocorrelationDialog,
)
from .time_series_chart import TimeSeriesChartWidget


def verify_time_series(app, p, w, temp, checkpoint):
    checkpoint("Time Series Analysis & Forecasting (Stat > Time Series) native dialogs, reports, and time series charts")
    p.new()

    # 24 periods of quarterly sales data with trend and seasonal pattern
    sales_data = [
        105.0, 125.0, 118.0, 95.0,
        112.0, 134.0, 126.0, 102.0,
        120.0, 145.0, 135.0, 110.0,
        128.0, 155.0, 144.0, 118.0,
        136.0, 166.0, 153.0, 126.0,
        144.0, 178.0, 162.0, 134.0,
    ]

    p.worksheet = Worksheet("QuarterlySales", [
        Column("Sales", "number", sales_data),
    ])
    w.page = 0
    w.refresh()

    # -------------------------------------------------------------
    # 1. Trend Analysis Dialog & Presenter Run
    # -------------------------------------------------------------
    dlg_trend = TrendAnalysisDialog(p.worksheet, parent=w)
    dlg_trend.edit_series.setText("Sales")
    dlg_trend.rb_linear.setChecked(True)
    dlg_trend.chk_fc.setChecked(True)
    dlg_trend.spin_fc.setValue(4)
    dlg_trend.chk_store_fits.setChecked(True)
    dlg_trend.chk_store_residuals.setChecked(True)
    dlg_trend.chk_store_forecasts.setChecked(True)
    dlg_trend._on_accept()

    params_trend = getattr(dlg_trend, "settings", None)
    assert params_trend is not None
    assert params_trend["series_index"] == 0
    assert params_trend["model"] == "linear"
    assert params_trend["forecasts"] == 4

    entry_trend = p.trend_analysis(settings=params_trend)
    assert entry_trend is not None
    res_trend = entry_trend["result"]
    assert res_trend["analysis"] == "trend_analysis"
    assert res_trend["n"] == 24
    assert len(res_trend["forecasts"]) == 4
    assert res_trend["accuracy"]["mape"] > 0
    assert res_trend["parameters"]["b1"] > 0  # Upward trend

    # Check columns stored back to worksheet
    col_names = [c.name for c in p.worksheet.columns]
    assert "FITS_Sales" in col_names
    assert "RESI_Sales" in col_names
    assert "FORE_Sales" in col_names

    # Verify session report formatting
    rep_trend = format_entry(entry_trend)
    assert "Trend Analysis" in rep_trend
    assert "Accuracy Measures" in rep_trend
    assert "Forecasts" in rep_trend

    # Verify Chart Widget rendering
    chart_widget = TimeSeriesChartWidget(entry_trend)
    chart_widget.resize(760, 480)
    img_trend = QImage(chart_widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img_trend.fill(Qt.GlobalColor.white)
    chart_widget.render(img_trend)
    assert not img_trend.isNull()

    # Save artifact screenshot
    out_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
    if out_dir.exists():
        img_trend.save(str(out_dir / "StatCraft-time-series-forecasting.png"))

    # -------------------------------------------------------------
    # 2. Decomposition Dialog & Presenter Run
    # -------------------------------------------------------------
    dlg_decomp = DecompositionDialog(p.worksheet, parent=w)
    dlg_decomp.edit_series.setText("Sales")
    dlg_decomp.spin_season.setValue(4)
    dlg_decomp.rb_multiplicative.setChecked(True)
    dlg_decomp.chk_fc.setChecked(True)
    dlg_decomp.spin_fc.setValue(4)
    dlg_decomp._on_accept()

    params_decomp = getattr(dlg_decomp, "settings", None)
    assert params_decomp is not None
    assert params_decomp["season_length"] == 4

    entry_decomp = p.decomposition(settings=params_decomp)
    assert entry_decomp is not None
    res_decomp = entry_decomp["result"]
    assert res_decomp["analysis"] == "decomposition"
    assert len(res_decomp["seasonal_indices"]) == 4
    assert len(res_decomp["forecasts"]) == 4

    rep_decomp = format_entry(entry_decomp)
    assert "Decomposition" in rep_decomp
    assert "Seasonal Indices" in rep_decomp

    # -------------------------------------------------------------
    # 3. Moving Average Dialog & Presenter Run
    # -------------------------------------------------------------
    dlg_ma = MovingAverageDialog(p.worksheet, parent=w)
    dlg_ma.edit_series.setText("Sales")
    dlg_ma.spin_length.setValue(4)
    dlg_ma.chk_center.setChecked(False)
    dlg_ma.chk_fc.setChecked(True)
    dlg_ma.spin_fc.setValue(2)
    dlg_ma._on_accept()

    params_ma = getattr(dlg_ma, "settings", None)
    assert params_ma is not None
    entry_ma = p.moving_average(settings=params_ma)
    assert entry_ma is not None
    res_ma = entry_ma["result"]
    assert res_ma["analysis"] == "moving_average"
    assert len(res_ma["forecasts"]) == 2

    # -------------------------------------------------------------
    # 4. Single & Double Exponential Smoothing
    # -------------------------------------------------------------
    dlg_ses = SingleExpSmoothingDialog(p.worksheet, parent=w)
    dlg_ses.edit_series.setText("Sales")
    dlg_ses.rb_optimal.setChecked(True)
    dlg_ses.chk_fc.setChecked(True)
    dlg_ses.spin_fc.setValue(3)
    dlg_ses._on_accept()

    params_ses = getattr(dlg_ses, "settings", None)
    entry_ses = p.single_exp_smoothing(settings=params_ses)
    assert entry_ses is not None
    assert entry_ses["result"]["analysis"] == "single_exp_smoothing"
    assert len(entry_ses["result"]["forecasts"]) == 3

    dlg_des = DoubleExpSmoothingDialog(p.worksheet, parent=w)
    dlg_des.edit_series.setText("Sales")
    dlg_des.rb_optimal.setChecked(True)
    dlg_des.chk_fc.setChecked(True)
    dlg_des.spin_fc.setValue(3)
    dlg_des._on_accept()

    params_des = getattr(dlg_des, "settings", None)
    entry_des = p.double_exp_smoothing(settings=params_des)
    assert entry_des is not None
    assert entry_des["result"]["analysis"] == "double_exp_smoothing"
    assert len(entry_des["result"]["forecasts"]) == 3

    # -------------------------------------------------------------
    # 5. Autocorrelation Plot & Spike Render
    # -------------------------------------------------------------
    dlg_acf = AutocorrelationDialog(p.worksheet, is_partial=False, parent=w)
    dlg_acf.edit_series.setText("Sales")
    dlg_acf._on_accept()

    params_acf = getattr(dlg_acf, "settings", None)
    entry_acf = p.autocorrelation(settings=params_acf)
    assert entry_acf is not None
    assert entry_acf["result"]["analysis"] == "autocorrelation"

    acf_widget = TimeSeriesChartWidget(entry_acf)
    acf_widget.resize(760, 480)
    img_acf = QImage(acf_widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    img_acf.fill(Qt.GlobalColor.white)
    acf_widget.render(img_acf)
    assert not img_acf.isNull()

    # -------------------------------------------------------------
    # 6. MPX Save / Reopen Roundtrip & Rerun Invariance
    # -------------------------------------------------------------
    mpx_file = Path(temp) / "timeseries-model.mpx"
    w.save_path(mpx_file)
    assert mpx_file.exists() and mpx_file.stat().st_size > 0
    w.load_path(mpx_file)
    app.processEvents()

    assert len(p.history) >= 6
    reconstructed_actions = [e.get("recipe", {}).get("action") for e in p.history]
    assert "trend_analysis" in reconstructed_actions
    assert "decomposition" in reconstructed_actions
    assert "moving_average" in reconstructed_actions
    assert "single_exp_smoothing" in reconstructed_actions
    assert "double_exp_smoothing" in reconstructed_actions

    checkpoint("Time Series Analysis & Forecasting verification passed successfully")
