"""Comprehensive unit tests for Multivariate Analysis in StatCraft."""

import unittest
import numpy as np
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.multivariate import (
    pca,
    item_analysis,
    cluster_observations,
    cluster_kmeans,
    cluster_variables,
    discriminant_analysis,
    simple_correspondence,
)
from statcraft.multivariate_report import (
    format_pca_report,
    format_item_analysis_report,
    format_cluster_observations_report,
    format_cluster_kmeans_report,
    format_cluster_variables_report,
    format_discriminant_analysis_report,
    format_simple_correspondence_report,
)
from statcraft.recipes import columns as recipe_columns


class TestMultivariateEngine(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        self.var1 = [12.0, 14.5, 11.2, 16.8, 15.0, 18.2, 13.1, 17.5, 10.8, 19.0]
        self.var2 = [22.1, 25.0, 20.5, 29.2, 27.0, 31.5, 24.0, 30.1, 19.8, 33.0]
        self.var3 = [5.1, 6.2, 4.8, 7.5, 6.8, 8.0, 5.5, 7.8, 4.5, 8.5]
        self.data_3v = [self.var1, self.var2, self.var3]
        self.names_3v = ["Length", "Width", "Height"]

    def test_pca_correlation(self):
        res = pca(self.data_3v, var_names=self.names_3v, matrix_type="correlation")
        self.assertEqual(res["analysis"], "pca")
        self.assertEqual(res["n_obs"], 10)
        self.assertEqual(res["n_vars"], 3)
        self.assertEqual(len(res["eigenvalues"]), 3)
        self.assertAlmostEqual(sum(res["eigenvalues"]), 3.0, places=5)
        self.assertGreater(res["proportions"][0], 0.95)
        self.assertAlmostEqual(res["cumulative"][-1], 1.0, places=5)
        rep = format_pca_report(res)
        self.assertIn("Principal Component Analysis", rep)
        self.assertIn("Eigenanalysis of the Correlation Matrix", rep)
        self.assertIn("Eigenvalue", rep)
        self.assertIn("Eigenvectors", rep)

    def test_pca_covariance(self):
        res = pca(self.data_3v, var_names=self.names_3v, matrix_type="covariance")
        self.assertEqual(res["matrix_type"], "covariance")
        self.assertIn("Covariance Matrix", res["matrix_title"])
        stds = np.std(np.array(self.data_3v).T, axis=0, ddof=1)
        expected_total_var = np.sum(stds ** 2)
        self.assertAlmostEqual(sum(res["eigenvalues"]), expected_total_var, places=5)
        rep = format_pca_report(res)
        self.assertIn("Eigenanalysis of the Covariance Matrix", rep)

    def test_item_analysis(self):
        q1 = [4, 5, 3, 5, 4, 3, 5, 4, 2, 5, 4, 3]
        q2 = [4, 4, 3, 5, 5, 4, 5, 4, 3, 4, 4, 3]
        q3 = [3, 5, 4, 4, 4, 3, 5, 3, 2, 5, 4, 4]
        q4 = [4, 5, 3, 5, 4, 4, 5, 4, 3, 5, 5, 3]
        res = item_analysis([q1, q2, q3, q4], var_names=["Q1", "Q2", "Q3", "Q4"])
        self.assertEqual(res["analysis"], "item_analysis")
        self.assertEqual(res["n_items"], 4)
        self.assertEqual(res["n_obs"], 12)
        self.assertGreater(res["cronbach_alpha"], 0.70)
        self.assertGreater(res["standardized_alpha"], 0.70)
        self.assertEqual(len(res["item_stats"]), 4)
        for st in res["item_stats"]:
            self.assertIn("item_mean", st)
            self.assertIn("item_adj_total_corr", st)
            self.assertIn("alpha_deleted", st)
        rep = format_item_analysis_report(res)
        self.assertIn("Item Analysis of Q1, Q2, Q3, Q4", rep)
        self.assertIn("Cronbach's alpha", rep)
        self.assertIn("Item-Total Statistics", rep)

    def test_cluster_observations(self):
        res = cluster_observations(
            self.data_3v,
            var_names=self.names_3v,
            linkage_method="average",
            distance_measure="euclidean",
            standardize="none",
            n_clusters=3,
        )
        self.assertEqual(res["analysis"], "cluster_observations")
        self.assertEqual(res["n_obs"], 10)
        self.assertEqual(res["k_clusters"], 3)
        self.assertEqual(len(res["amalgamation"]), 9)
        self.assertEqual(len(res["cluster_summary"]), 3)
        self.assertEqual(len(res["centroids"]), 3)
        self.assertGreater(res["total_within_ss"], 0.0)
        self.assertIn("icoord", res["dendrogram_data"])
        rep = format_cluster_observations_report(res)
        self.assertIn("Cluster Analysis of Observations", rep)
        self.assertIn("Amalgamation Steps", rep)
        self.assertIn("Final Partition", rep)
        self.assertIn("Cluster Centroids", rep)

    def test_cluster_kmeans(self):
        res = cluster_kmeans(
            self.data_3v,
            var_names=self.names_3v,
            k_clusters=3,
            max_iter=50,
        )
        self.assertEqual(res["analysis"], "cluster_kmeans")
        self.assertEqual(res["k_clusters"], 3)
        self.assertEqual(len(res["centroids"]), 3)
        self.assertEqual(len(res["cluster_labels"]), 10)
        self.assertAlmostEqual(res["within_ss"] + res["between_ss"], res["total_ss"], places=4)
        rep = format_cluster_kmeans_report(res)
        self.assertIn("K-Means Cluster Analysis", rep)
        self.assertIn("Final Partition", rep)
        self.assertIn("Distances Between Cluster Centroids", rep)

    def test_cluster_variables(self):
        res = cluster_variables(
            self.data_3v,
            var_names=self.names_3v,
            linkage_method="complete",
        )
        self.assertEqual(res["analysis"], "cluster_variables")
        self.assertEqual(res["n_vars"], 3)
        self.assertEqual(len(res["amalgamation"]), 2)
        self.assertIn("dendrogram_data", res)
        rep = format_cluster_variables_report(res)
        self.assertIn("Cluster Analysis of Variables", rep)
        self.assertIn("Amalgamation Steps", rep)

    def test_discriminant_analysis(self):
        groups = ["A", "A", "A", "A", "A", "B", "B", "B", "B", "B"]
        x1 = [1.1, 1.3, 1.2, 1.5, 1.4, 8.2, 8.5, 8.1, 8.9, 8.4]
        x2 = [2.1, 2.4, 2.2, 2.5, 2.3, 9.1, 9.4, 9.2, 9.8, 9.5]
        res = discriminant_analysis(
            group_col=groups,
            pred_data=[x1, x2],
            group_name="Class",
            pred_names=["X1", "X2"],
            method="linear",
            priors="equal",
        )
        self.assertEqual(res["analysis"], "discriminant_analysis")
        self.assertEqual(res["n_obs"], 10)
        self.assertEqual(res["unique_groups"], ["A", "B"])
        self.assertEqual(len(res["linear_coefficients"]), 2)
        self.assertAlmostEqual(res["total_pct_correct"], 100.0)
        self.assertAlmostEqual(res["cv_total_pct_correct"], 100.0)
        rep = format_discriminant_analysis_report(res)
        self.assertIn("Discriminant Analysis: Class versus X1, X2", rep)
        self.assertIn("Linear Discriminant Function for Class", rep)
        self.assertIn("Summary of Classification", rep)
        self.assertIn("Summary of Cross-Validation (Jackknife)", rep)

    def test_simple_correspondence(self):
        table = [
            [25.0, 15.0, 10.0],
            [10.0, 30.0, 15.0],
            [5.0, 12.0, 28.0],
        ]
        res = simple_correspondence(
            table=table,
            row_names=["Senior", "Middle", "Junior"],
            col_names=["Site1", "Site2", "Site3"],
        )
        self.assertEqual(res["analysis"], "simple_correspondence")
        self.assertEqual(res["n_rows"], 3)
        self.assertEqual(res["n_cols"], 3)
        self.assertEqual(res["total_count"], 150.0)
        self.assertGreater(res["total_inertia"], 0.0)
        self.assertEqual(len(res["row_coordinates"]), 3)
        self.assertEqual(len(res["col_coordinates"]), 3)
        rep = format_simple_correspondence_report(res)
        self.assertIn("Simple Correspondence Analysis", rep)
        self.assertIn("Inertia Decomposition", rep)


class TestMultivariatePresenterAndPersistence(unittest.TestCase):
    def setUp(self):
        self.ws = Worksheet()
        self.ws.columns = [
            Column("X1", "number", [10.0, 12.0, 11.0, 15.0, 14.0, 18.0, 17.0, 20.0]),
            Column("X2", "number", [20.0, 22.0, 21.0, 26.0, 25.0, 30.0, 29.0, 34.0]),
            Column("X3", "number", [5.0, 6.0, 5.5, 7.5, 7.0, 8.5, 8.0, 9.5]),
            Column("Group", "text", ["G1", "G1", "G1", "G1", "G2", "G2", "G2", "G2"]),
            Column("T1", "number", [15.0, 10.0, 5.0]),
            Column("T2", "number", [12.0, 25.0, 8.0]),
        ]
        self.p = Presenter()
        self.p.worksheet = self.ws

    def test_presenter_pca_recipe_columns(self):
        settings = {"variable_indices": [0, 1, 2], "matrix_type": "correlation"}
        rec = self.p.pca(settings)
        self.assertIsNotNone(rec)
        self.assertIn("Principal Component Analysis", rec["title"])
        cols = recipe_columns(rec["recipe"])
        self.assertEqual(cols, [0, 1, 2])

    def test_presenter_item_analysis_recipe_columns(self):
        settings = {"variable_indices": [0, 1, 2]}
        rec = self.p.item_analysis(settings)
        self.assertIsNotNone(rec)
        self.assertIn("Item Analysis", rec["title"])
        cols = recipe_columns(rec["recipe"])
        self.assertEqual(cols, [0, 1, 2])

    def test_presenter_cluster_observations_recipe_columns(self):
        settings = {"variable_indices": [0, 1, 2], "linkage_method": "average", "n_clusters": 2}
        rec = self.p.cluster_observations(settings)
        self.assertIsNotNone(rec)
        self.assertIn("Cluster Analysis of Observations", rec["title"])
        cols = recipe_columns(rec["recipe"])
        self.assertEqual(cols, [0, 1, 2])

    def test_presenter_cluster_kmeans_recipe_columns(self):
        settings = {"variable_indices": [0, 1, 2], "k_clusters": 2}
        rec = self.p.cluster_kmeans(settings)
        self.assertIsNotNone(rec)
        self.assertIn("K-Means Cluster Analysis", rec["title"])
        cols = recipe_columns(rec["recipe"])
        self.assertEqual(cols, [0, 1, 2])

    def test_presenter_cluster_variables_recipe_columns(self):
        settings = {"variable_indices": [0, 1, 2], "linkage_method": "average"}
        rec = self.p.cluster_variables(settings)
        self.assertIsNotNone(rec)
        self.assertIn("Cluster Analysis of Variables", rec["title"])
        cols = recipe_columns(rec["recipe"])
        self.assertEqual(cols, [0, 1, 2])

    def test_presenter_discriminant_analysis_recipe_columns(self):
        settings = {"group_index": 3, "predictor_indices": [0, 1], "method": "linear"}
        rec = self.p.discriminant_analysis(settings)
        self.assertIsNotNone(rec)
        self.assertIn("Discriminant Analysis", rec["title"])
        cols = recipe_columns(rec["recipe"])
        self.assertEqual(sorted(cols), [0, 1, 3])

    def test_presenter_simple_correspondence_recipe_columns(self):
        settings = {"column_indices": [4, 5]}
        rec = self.p.simple_correspondence(settings)
        self.assertIsNotNone(rec)
        self.assertIn("Simple Correspondence Analysis", rec["title"])
        cols = recipe_columns(rec["recipe"])
        self.assertEqual(cols, [4, 5])


if __name__ == "__main__":
    unittest.main()
