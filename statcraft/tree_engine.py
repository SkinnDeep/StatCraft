"""Recursive Partitioning Engine (CART® / Decision Trees).

Provides high-performance binary classification and regression tree fitting:
- Continuous (Regression) and Categorical (Classification) response variables.
- Numeric features (threshold splits X <= c) and Categorical features (subset splits X in S).
- Splitting criteria: Variance reduction (SSE) for regression; Gini impurity reduction for classification.
- Variable importance ranking based on total weighted improvement across splits.
- Terminal leaves summary and prediction engine.

References:
- Breiman, Friedman, Olshen, Stone (1984). Classification and Regression Trees (CART).
- Minitab: Stat > Predictive Analytics > CART® Regression & CART® Classification.
- JMP: Analyze > Predictive Modeling > Partition.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np


@dataclass
class TreeNode:
    node_id: int
    depth: int
    is_leaf: bool
    n_samples: int
    # Regression metrics
    mean: float = 0.0
    sd: float = 0.0
    mse: float = 0.0
    # Classification metrics
    predicted_class: Any = None
    class_counts: Dict[str, int] = field(default_factory=dict)
    class_probs: Dict[str, float] = field(default_factory=dict)
    impurity: float = 0.0
    # Split details
    feature_index: Optional[int] = None
    feature_name: Optional[str] = None
    feature_kind: str = "numeric"  # "numeric" or "categorical"
    split_threshold: Optional[float] = None
    split_categories: Optional[List[str]] = None
    improvement: float = 0.0
    left: Optional['TreeNode'] = None
    right: Optional['TreeNode'] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "node_id": self.node_id,
            "depth": self.depth,
            "is_leaf": self.is_leaf,
            "n_samples": self.n_samples,
            "mean": self.mean,
            "sd": self.sd,
            "mse": self.mse,
            "predicted_class": self.predicted_class,
            "class_counts": self.class_counts,
            "class_probs": self.class_probs,
            "impurity": self.impurity,
            "feature_index": self.feature_index,
            "feature_name": self.feature_name,
            "feature_kind": self.feature_kind,
            "split_threshold": self.split_threshold,
            "split_categories": self.split_categories,
            "improvement": self.improvement,
        }
        if self.left is not None:
            d["left"] = self.left.to_dict()
        if self.right is not None:
            d["right"] = self.right.to_dict()
        return d


class DecisionTree:
    """CART-compliant Decision Tree for Regression and Classification."""

    def __init__(
        self,
        tree_type: str = "auto",  # 'regression', 'classification', or 'auto'
        max_depth: int = 5,
        min_split_size: int = 10,
        min_leaf_size: int = 5,
        max_features: Optional[int] = None,
    ):
        self.tree_type = tree_type
        self.max_depth = max_depth
        self.min_split_size = min_split_size
        self.min_leaf_size = min_leaf_size
        self.max_features = max_features

        self.root: Optional[TreeNode] = None
        self.feature_names: List[str] = []
        self.feature_kinds: List[str] = []
        self.classes_: List[str] = []
        self.n_nodes_: int = 0
        self.feature_importances_: Dict[str, float] = {}
        self.terminal_nodes_: List[TreeNode] = []

    def fit(
        self,
        X: Sequence[Sequence[Any]],
        y: Sequence[Any],
        feature_names: Optional[Sequence[str]] = None,
        feature_kinds: Optional[Sequence[str]] = None,
    ) -> 'DecisionTree':
        n_samples = len(y)
        if n_samples == 0:
            raise ValueError("Training data cannot be empty.")
        if len(X) != n_samples:
            raise ValueError(f"X ({len(X)} rows) and y ({len(y)} rows) length mismatch.")

        n_features = len(X[0]) if n_samples > 0 else 0
        if n_features == 0:
            raise ValueError("No predictor features provided.")

        self.feature_names = [str(f) for f in feature_names] if feature_names else [f"X{i+1}" for i in range(n_features)]

        # Determine feature kinds: 'numeric' or 'categorical'
        if feature_kinds is not None:
            self.feature_kinds = list(feature_kinds)
        else:
            self.feature_kinds = []
            for j in range(n_features):
                vals = [X[i][j] for i in range(n_samples) if X[i][j] is not None]
                if all(isinstance(v, (int, float, np.number)) and not isinstance(v, bool) for v in vals):
                    self.feature_kinds.append("numeric")
                else:
                    self.feature_kinds.append("categorical")

        # Determine tree type (regression vs classification)
        y_valid = [v for v in y if v is not None]
        if self.tree_type == "auto":
            is_y_num = all(isinstance(v, (int, float, np.number)) and not isinstance(v, bool) for v in y_valid)
            # If numeric but <= 5 distinct values, consider classification if user didn't specify
            unique_y = set(y_valid)
            if is_y_num and len(unique_y) > 7:
                self.tree_type = "regression"
            elif is_y_num and len(unique_y) <= 5 and all(float(v).is_integer() for v in unique_y):
                self.tree_type = "classification"
            elif is_y_num:
                self.tree_type = "regression"
            else:
                self.tree_type = "classification"

        if self.tree_type == "classification":
            self.classes_ = sorted(list(set(str(v) for v in y_valid)))

        # Preprocess dataset into matrix structure
        X_mat: List[List[Any]] = []
        y_clean: List[Any] = []
        for i in range(n_samples):
            if y[i] is None:
                continue
            row = [X[i][j] for j in range(n_features)]
            X_mat.append(row)
            y_clean.append(y[i] if self.tree_type == "regression" else str(y[i]))

        self.n_nodes_ = 0
        self.feature_importances_ = {name: 0.0 for name in self.feature_names}
        self.terminal_nodes_ = []

        all_indices = list(range(len(y_clean)))
        self.root = self._build_tree(X_mat, y_clean, all_indices, depth=0)

        # Normalize feature importances to sum to 100%
        total_imp = sum(self.feature_importances_.values())
        if total_imp > 1e-12:
            self.feature_importances_ = {
                k: (v / total_imp) * 100.0 for k, v in self.feature_importances_.items()
            }

        return self

    def _calc_node_stats(self, y: List[Any], indices: List[int]) -> Dict[str, Any]:
        n = len(indices)
        if n == 0:
            return {"n": 0, "mean": 0.0, "sd": 0.0, "mse": 0.0, "impurity": 0.0, "counts": {}, "probs": {}, "pred": None}

        sub_y = [y[i] for i in indices]

        if self.tree_type == "regression":
            arr = np.asarray(sub_y, dtype=float)
            mean = float(np.mean(arr))
            sd = float(np.std(arr, ddof=1)) if n > 1 else 0.0
            mse = float(np.mean((arr - mean) ** 2))
            return {
                "n": n,
                "mean": mean,
                "sd": sd,
                "mse": mse,
                "impurity": mse,
                "counts": {},
                "probs": {},
                "pred": mean,
            }
        else:
            counts: Dict[str, int] = {}
            for item in sub_y:
                k = str(item)
                counts[k] = counts.get(k, 0) + 1
            probs = {k: v / n for k, v in counts.items()}
            # Gini impurity = 1 - sum(p_i^2)
            gini = 1.0 - sum(p * p for p in probs.values())
            # Majority class
            best_cls = max(counts.items(), key=lambda it: it[1])[0]
            return {
                "n": n,
                "mean": 0.0,
                "sd": 0.0,
                "mse": 0.0,
                "impurity": gini,
                "counts": counts,
                "probs": probs,
                "pred": best_cls,
            }

    def _build_tree(self, X: List[List[Any]], y: List[Any], indices: List[int], depth: int) -> TreeNode:
        self.n_nodes_ += 1
        curr_node_id = self.n_nodes_

        stats = self._calc_node_stats(y, indices)
        node = TreeNode(
            node_id=curr_node_id,
            depth=depth,
            is_leaf=True,
            n_samples=stats["n"],
            mean=stats["mean"],
            sd=stats["sd"],
            mse=stats["mse"],
            predicted_class=stats["pred"],
            class_counts=stats["counts"],
            class_probs=stats["probs"],
            impurity=stats["impurity"],
        )

        # Stop criteria:
        if (
            depth >= self.max_depth
            or stats["n"] < self.min_split_size
            or stats["impurity"] < 1e-7
        ):
            self.terminal_nodes_.append(node)
            return node

        best_feat_idx: Optional[int] = None
        best_threshold: Optional[float] = None
        best_categories: Optional[List[str]] = None
        best_gain = 0.0
        best_left_idx: List[int] = []
        best_right_idx: List[int] = []

        n_features = len(self.feature_names)
        curr_impurity = stats["impurity"]

        # Search optimal split across features
        for f_idx in range(n_features):
            f_kind = self.feature_kinds[f_idx]
            feat_vals = [X[i][f_idx] for i in indices]

            if f_kind == "numeric":
                # Continuous split X <= threshold
                valid_pairs = [(feat_vals[k], indices[k]) for k in range(len(indices)) if feat_vals[k] is not None and math.isfinite(feat_vals[k])]
                if len(valid_pairs) < (2 * self.min_leaf_size):
                    continue
                valid_pairs.sort(key=lambda p: p[0])

                sorted_vals = [p[0] for p in valid_pairs]
                sorted_idx = [p[1] for p in valid_pairs]

                # Check midpoints between consecutive distinct values
                for s_i in range(self.min_leaf_size - 1, len(valid_pairs) - self.min_leaf_size):
                    val_curr = sorted_vals[s_i]
                    val_next = sorted_vals[s_i + 1]
                    if abs(val_next - val_curr) < 1e-9:
                        continue

                    cand_thresh = (val_curr + val_next) / 2.0
                    left_cand = sorted_idx[: s_i + 1]
                    right_cand = sorted_idx[s_i + 1 :]

                    if len(left_cand) < self.min_leaf_size or len(right_cand) < self.min_leaf_size:
                        continue

                    left_stats = self._calc_node_stats(y, left_cand)
                    right_stats = self._calc_node_stats(y, right_cand)

                    p_l = len(left_cand) / float(len(indices))
                    p_r = len(right_cand) / float(len(indices))
                    child_impurity = p_l * left_stats["impurity"] + p_r * right_stats["impurity"]
                    gain = curr_impurity - child_impurity

                    if gain > best_gain:
                        best_gain = gain
                        best_feat_idx = f_idx
                        best_threshold = cand_thresh
                        best_categories = None
                        best_left_idx = left_cand
                        best_right_idx = right_cand
            else:
                # Categorical split: X in category_subset
                unique_cats = sorted(list(set(str(v) for v in feat_vals if v is not None)))
                if len(unique_cats) < 2 or len(unique_cats) > 12:
                    # Single value or too many combinations
                    continue

                # Test binary subsets
                import itertools
                for r in range(1, len(unique_cats) // 2 + 1):
                    for sub in itertools.combinations(unique_cats, r):
                        sub_set = set(sub)
                        left_cand = [indices[k] for k in range(len(indices)) if str(feat_vals[k]) in sub_set]
                        right_cand = [indices[k] for k in range(len(indices)) if str(feat_vals[k]) not in sub_set and feat_vals[k] is not None]

                        if len(left_cand) < self.min_leaf_size or len(right_cand) < self.min_leaf_size:
                            continue

                        left_stats = self._calc_node_stats(y, left_cand)
                        right_stats = self._calc_node_stats(y, right_cand)

                        p_l = len(left_cand) / float(len(indices))
                        p_r = len(right_cand) / float(len(indices))
                        child_impurity = p_l * left_stats["impurity"] + p_r * right_stats["impurity"]
                        gain = curr_impurity - child_impurity

                        if gain > best_gain:
                            best_gain = gain
                            best_feat_idx = f_idx
                            best_threshold = None
                            best_categories = list(sub)
                            best_left_idx = left_cand
                            best_right_idx = right_cand

        # If significant improvement found, make node internal
        if best_gain > 1e-6 and best_feat_idx is not None:
            node.is_leaf = False
            node.feature_index = best_feat_idx
            node.feature_name = self.feature_names[best_feat_idx]
            node.feature_kind = self.feature_kinds[best_feat_idx]
            node.split_threshold = best_threshold
            node.split_categories = best_categories
            node.improvement = best_gain

            # Accumulate feature importance
            # Weight gain by number of samples at node
            weighted_gain = best_gain * (stats["n"] / float(len(y)))
            self.feature_importances_[node.feature_name] += weighted_gain

            node.left = self._build_tree(X, y, best_left_idx, depth + 1)
            node.right = self._build_tree(X, y, best_right_idx, depth + 1)
        else:
            self.terminal_nodes_.append(node)

        return node

    def predict(self, X: Sequence[Sequence[Any]]) -> List[Any]:
        preds = []
        for row in X:
            node = self.root
            while node is not None and not node.is_leaf:
                f_idx = node.feature_index
                val = row[f_idx]
                if val is None:
                    # Default route to left
                    node = node.left
                elif node.feature_kind == "numeric":
                    if float(val) <= node.split_threshold:
                        node = node.left
                    else:
                        node = node.right
                else:
                    if str(val) in (node.split_categories or []):
                        node = node.left
                    else:
                        node = node.right
            preds.append(node.mean if (node and self.tree_type == "regression") else (node.predicted_class if node else None))
        return preds


def fit_decision_tree(
    X: Sequence[Sequence[Any]],
    y: Sequence[Any],
    feature_names: Optional[Sequence[str]] = None,
    feature_kinds: Optional[Sequence[str]] = None,
    tree_type: str = "auto",
    max_depth: int = 5,
    min_split_size: int = 10,
    min_leaf_size: int = 5,
) -> Dict[str, Any]:
    """Fit a CART-compliant Decision Tree and return comprehensive model summary and diagnostics."""
    tree = DecisionTree(
        tree_type=tree_type,
        max_depth=max_depth,
        min_split_size=min_split_size,
        min_leaf_size=min_leaf_size,
    )
    tree.fit(X, y, feature_names=feature_names, feature_kinds=feature_kinds)

    # In-sample predictions
    y_pred = tree.predict(X)

    # Performance metrics
    n_total = len(y)
    valid_mask = [y[i] is not None and y_pred[i] is not None for i in range(n_total)]
    y_true_v = [y[i] for i in range(n_total) if valid_mask[i]]
    y_pred_v = [y_pred[i] for i in range(n_total) if valid_mask[i]]

    metrics: Dict[str, Any] = {
        "n_samples": len(y_true_v),
        "tree_type": tree.tree_type,
        "n_terminal_nodes": len(tree.terminal_nodes_),
        "max_depth_reached": max(node.depth for node in tree.terminal_nodes_) if tree.terminal_nodes_ else 0,
    }

    if tree.tree_type == "regression":
        y_true_arr = np.asarray(y_true_v, dtype=float)
        y_pred_arr = np.asarray(y_pred_v, dtype=float)
        residuals = y_true_arr - y_pred_arr
        mse = float(np.mean(residuals ** 2))
        rmse = math.sqrt(mse)
        mae = float(np.mean(np.abs(residuals)))
        ss_tot = float(np.sum((y_true_arr - np.mean(y_true_arr)) ** 2))
        ss_res = float(np.sum(residuals ** 2))
        r2 = max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 1e-12 else 0.0

        metrics["r2"] = r2
        metrics["rmse"] = rmse
        metrics["mae"] = mae
        metrics["mse"] = mse
    else:
        # Classification metrics
        correct = sum(1 for i in range(len(y_true_v)) if str(y_true_v[i]) == str(y_pred_v[i]))
        accuracy = correct / len(y_true_v) if y_true_v else 0.0
        misclassification = 1.0 - accuracy

        # Confusion Matrix
        labels = tree.classes_
        conf_mat: Dict[str, Dict[str, int]] = {true_c: {pred_c: 0 for pred_c in labels} for true_c in labels}
        for true_v, pred_v in zip(y_true_v, y_pred_v):
            t_s, p_s = str(true_v), str(pred_v)
            if t_s in conf_mat and p_s in conf_mat[t_s]:
                conf_mat[t_s][p_s] += 1

        metrics["accuracy"] = accuracy
        metrics["misclassification_rate"] = misclassification
        metrics["confusion_matrix"] = conf_mat

    # Variable importance table
    var_imp_list = []
    for f_name, imp in sorted(tree.feature_importances_.items(), key=lambda it: it[1], reverse=True):
        var_imp_list.append({
            "feature": f_name,
            "importance": imp,
        })

    # Terminal nodes summary table
    terminal_table = []
    for node in sorted(tree.terminal_nodes_, key=lambda n: n.node_id):
        # Build path rules from root to node
        rule_parts = []
        curr = node
        # In this simple formulation, path can be identified by node ID
        row_dict: Dict[str, Any] = {
            "node_id": node.node_id,
            "depth": node.depth,
            "n_samples": node.n_samples,
            "pct_samples": (node.n_samples / n_total * 100.0) if n_total > 0 else 0.0,
        }
        if tree.tree_type == "regression":
            row_dict["mean"] = node.mean
            row_dict["sd"] = node.sd
            row_dict["mse"] = node.mse
        else:
            row_dict["predicted_class"] = node.predicted_class
            row_dict["purity"] = (1.0 - node.impurity) * 100.0
            row_dict["class_counts"] = node.class_counts

        terminal_table.append(row_dict)

    return {
        "analysis": "cart_tree",
        "tree_type": tree.tree_type,
        "max_depth": max_depth,
        "min_split_size": min_split_size,
        "min_leaf_size": min_leaf_size,
        "feature_names": tree.feature_names,
        "feature_kinds": tree.feature_kinds,
        "classes": tree.classes_,
        "metrics": metrics,
        "importances": var_imp_list,
        "terminal_nodes": terminal_table,
        "tree_structure": tree.root.to_dict() if tree.root else {},
    }
