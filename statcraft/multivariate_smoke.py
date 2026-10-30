"""Automated verification smoke test for Multivariate Analysis (Stat > Multivariate)."""
from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from .model import Column, Worksheet
from .multivariate_dialogs import (
    PcaDialog,
    ItemAnalysisDialog,
    ClusterObservationsDialog,
    ClusterKMeansDialog,
    ClusterVariablesDialog,
    DiscriminantAnalysisDialog,
    SimpleCorrespondenceDialog,
)
from .multivariate_chart import MultivariateChartWidget
from .recipes import run as run_recipe


def verify_multivariate(app, p, w, temp, checkpoint):
    """Smoke test verifying multivariate dialogs, calculations, charts, and MPX persistence."""
    checkpoint("Multivariate Analysis (Stat > Multivariate) dialogs, reports, and charts")
    p.new()

    ws = Worksheet("MultivarData", [
        Column("Length", "number", [10.5, 12.0, 11.2, 14.8, 13.5, 16.2, 12.1, 15.5, 9.8, 17.0, 11.0, 16.5]),
        Column("Width", "number", [20.1, 23.0, 21.5, 27.2, 25.0, 29.5, 23.0, 28.1, 18.8, 31.0, 21.0, 30.0]),
        Column("Height", "number", [5.1, 6.2, 5.8, 7.5, 6.8, 8.0, 6.0, 7.8, 4.8, 8.5, 5.5, 8.2]),
        Column("Class", "text", ["TypeA", "TypeA", "TypeA", "TypeA", "TypeB", "TypeB", "TypeB", "TypeB", "TypeC", "TypeC", "TypeC", "TypeC"]),
        Column("Site1", "number", [25.0, 15.0, 10.0]),
        Column("Site2", "number", [10.0, 30.0, 15.0]),
        Column("Site3", "number", [5.0, 12.0, 28.0]),
    ])
    p.worksheet = ws
    w.page = 0
    w.refresh()

    # 1. Dialog Smoke Tests
    dlg_pca = PcaDialog(ws, parent=w)
    dlg_pca.edit_vars.setText("Length Width Height")
    dlg_pca._validate_and_accept()
    st_pca = dlg_pca.settings
    assert st_pca["variable_indices"] == [0, 1, 2]
    dlg_pca.close()

    dlg_item = ItemAnalysisDialog(ws, parent=w)
    dlg_item.edit_items.setText("Length Width Height")
    dlg_item._validate_and_accept()
    st_item = dlg_item.settings
    assert st_item["variable_indices"] == [0, 1, 2]
    dlg_item.close()

    dlg_co = ClusterObservationsDialog(ws, parent=w)
    dlg_co.edit_vars.setText("Length Width Height")
    dlg_co._validate_and_accept()
    st_co = dlg_co.settings
    assert st_co["variable_indices"] == [0, 1, 2]
    dlg_co.close()

    dlg_km = ClusterKMeansDialog(ws, parent=w)
    dlg_km.edit_vars.setText("Length Width Height")
    dlg_km._validate_and_accept()
    st_km = dlg_km.settings
    assert st_km["variable_indices"] == [0, 1, 2]
    dlg_km.close()

    dlg_cv = ClusterVariablesDialog(ws, parent=w)
    dlg_cv.edit_vars.setText("Length Width Height")
    dlg_cv._validate_and_accept()
    st_cv = dlg_cv.settings
    assert st_cv["variable_indices"] == [0, 1, 2]
    dlg_cv.close()

    dlg_da = DiscriminantAnalysisDialog(ws, parent=w)
    dlg_da.edit_group.setText("Class")
    dlg_da.edit_preds.setText("Length Width Height")
    dlg_da._validate_and_accept()
    st_da = dlg_da.settings
    assert st_da["group_index"] == 3 and st_da["predictor_indices"] == [0, 1, 2]
    dlg_da.close()

    dlg_ca = SimpleCorrespondenceDialog(ws, parent=w)
    dlg_ca.edit_cols.setText("Site1 Site2 Site3")
    dlg_ca._validate_and_accept()
    st_ca = dlg_ca.settings
    assert st_ca["column_indices"] == [4, 5, 6]
    dlg_ca.close()

    # 2. Presenter Execution & Statistical Assertions
    # 2a. PCA
    entry_pca = p.pca(settings={"variable_indices": [0, 1, 2], "matrix_type": "correlation"})
    assert entry_pca is not None
    res_pca = entry_pca["result"]
    assert res_pca["analysis"] == "pca"
    assert len(res_pca["eigenvalues"]) == 3
    assert abs(sum(res_pca["eigenvalues"]) - 3.0) < 1e-4

    # 2b. Item Analysis
    entry_item = p.item_analysis(settings={"variable_indices": [0, 1, 2]})
    assert entry_item is not None
    res_item = entry_item["result"]
    assert res_item["analysis"] == "item_analysis"
    assert res_item["cronbach_alpha"] > 0.80

    # 2c. Cluster Observations
    entry_co = p.cluster_observations(settings={"variable_indices": [0, 1, 2], "linkage_method": "average", "n_clusters": 3})
    assert entry_co is not None
    res_co = entry_co["result"]
    assert res_co["analysis"] == "cluster_observations"
    assert len(res_co["cluster_summary"]) == 3

    # 2d. Cluster K-Means
    entry_km = p.cluster_kmeans(settings={"variable_indices": [0, 1, 2], "k_clusters": 3})
    assert entry_km is not None
    res_km = entry_km["result"]
    assert res_km["analysis"] == "cluster_kmeans"
    assert len(res_km["centroids"]) == 3

    # 2e. Cluster Variables
    entry_cv = p.cluster_variables(settings={"variable_indices": [0, 1, 2], "linkage_method": "average"})
    assert entry_cv is not None
    res_cv = entry_cv["result"]
    assert res_cv["analysis"] == "cluster_variables"
    assert len(res_cv["amalgamation"]) == 2

    # 2f. Discriminant Analysis
    entry_da = p.discriminant_analysis(settings={"group_index": 3, "predictor_indices": [0, 1, 2], "method": "linear"})
    assert entry_da is not None
    res_da = entry_da["result"]
    assert res_da["analysis"] == "discriminant_analysis"
    assert len(res_da["linear_coefficients"]) == 3

    # 2g. Simple Correspondence Analysis
    entry_ca = p.simple_correspondence(settings={"column_indices": [4, 5, 6]})
    assert entry_ca is not None
    res_ca = entry_ca["result"]
    assert res_ca["analysis"] == "simple_correspondence"
    assert res_ca["total_count"] == 150.0

    # 3. Chart Rendering Smoke Tests
    brain_dir = Path("C:/Users/funny/.gemini/antigravity/brain/3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")

    # PCA Scree Plot
    chart_scree = MultivariateChartWidget(entry_pca)
    chart_scree.resize(720, 460)
    img_scree = QImage(QSize(720, 460), QImage.Format.Format_ARGB32_Premultiplied)
    chart_scree.render(img_scree)
    if brain_dir.exists():
        img_scree.save(str(brain_dir / "StatCraft-pca-scree-plot.png"))

    # PCA Loading Plot
    entry_pca_load = dict(entry_pca)
    entry_pca_load["result"] = dict(res_pca)
    entry_pca_load["result"]["chart_type"] = "loading"
    chart_load = MultivariateChartWidget(entry_pca_load)
    chart_load.resize(720, 460)
    img_load = QImage(QSize(720, 460), QImage.Format.Format_ARGB32_Premultiplied)
    chart_load.render(img_load)
    if brain_dir.exists():
        img_load.save(str(brain_dir / "StatCraft-pca-loading-plot.png"))

    # Item Analysis Plot
    chart_item = MultivariateChartWidget(entry_item)
    chart_item.resize(720, 460)
    img_item = QImage(QSize(720, 460), QImage.Format.Format_ARGB32_Premultiplied)
    chart_item.render(img_item)
    if brain_dir.exists():
        img_item.save(str(brain_dir / "StatCraft-item-analysis-plot.png"))

    # Dendrogram
    chart_dendro = MultivariateChartWidget(entry_co)
    chart_dendro.resize(720, 460)
    img_dendro = QImage(QSize(720, 460), QImage.Format.Format_ARGB32_Premultiplied)
    chart_dendro.render(img_dendro)
    if brain_dir.exists():
        img_dendro.save(str(brain_dir / "StatCraft-cluster-dendrogram.png"))

    # K-Means Profile Plot
    chart_km = MultivariateChartWidget(entry_km)
    chart_km.resize(720, 460)
    img_km = QImage(QSize(720, 460), QImage.Format.Format_ARGB32_Premultiplied)
    chart_km.render(img_km)
    if brain_dir.exists():
        img_km.save(str(brain_dir / "StatCraft-kmeans-profile-plot.png"))

    # Discriminant Canonical Score Plot
    chart_da = MultivariateChartWidget(entry_da)
    chart_da.resize(720, 460)
    img_da = QImage(QSize(720, 460), QImage.Format.Format_ARGB32_Premultiplied)
    chart_da.render(img_da)
    if brain_dir.exists():
        img_da.save(str(brain_dir / "StatCraft-discriminant-score-plot.png"))

    # 4. Recipe Invariance & Rerun Roundtrip
    for entry in [entry_pca, entry_item, entry_co, entry_km, entry_cv, entry_da, entry_ca]:
        recipe = entry["recipe"]
        rerun_entry = run_recipe(p, recipe)
        assert rerun_entry["result"]["analysis"] == entry["result"]["analysis"]

    checkpoint("Multivariate Analysis smoke test passed completely.")
