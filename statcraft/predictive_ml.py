"""Predictive Analytics & Machine Learning Engine (Offline NumPy / SciPy).

Provides native Minitab Predictive Analytics & JMP Predictive Modeling parity:
- Random Forests (Regression & Classification, OOB error, Permutation/Reduction Importance)
- TreeNet Stochastic Gradient Boosting (Regression L2/Huber & Classification, Optimal Trees, PDP)
- MARS Multivariate Adaptive Regression Splines (Forward Hinge Basis + GCV Backward Pruning)
- Discover Best Model AutoML Leaderboard (CART vs Random Forests vs TreeNet vs MARS vs Linear/Logistic)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Tabular Feature Matrix & Preprocessing Helpers
# ---------------------------------------------------------------------------

def prepare_ml_dataset(
    worksheet: Any,
    response_index: int,
    predictor_indices: Sequence[int],
    task: str = "auto",
) -> Dict[str, Any]:
    """Extract numeric/categorical predictors into clean encoded NumPy arrays.

    Returns encoded float matrix `X` of shape (n, p_encoded), `y` array,
    `classes` list (for classification), `feature_names` (length p_encoded),
    and `col_groups` mapping original predictor names -> encoded column indices.
    """
    if response_index is None or not (0 <= int(response_index) < len(worksheet.columns)):
        raise ValueError("Select a valid response variable.")
    pred_list = [int(i) for i in predictor_indices if i is not None and int(i) != int(response_index)]
    if not pred_list:
        raise ValueError("Select at least one predictor variable separate from the response.")
    for idx in pred_list:
        if not (0 <= idx < len(worksheet.columns)):
            raise ValueError(f"Invalid predictor column index: {idx}")

    resp_col = worksheet.columns[int(response_index)]
    pred_cols = [worksheet.columns[i] for i in pred_list]
    n_rows = min([len(resp_col.values)] + [len(c.values) for c in pred_cols])

    valid_rows: List[int] = []
    for r in range(n_rows):
        if resp_col.values[r] is None:
            continue
        if any(c.values[r] is None for c in pred_cols):
            continue
        valid_rows.append(r)

    if len(valid_rows) < 6:
        raise ValueError("At least 6 complete non-missing rows are required for predictive modeling.")

    # Encode predictors (numeric kept directly; text mapped via ordinal/indicator one-hot)
    encoded_cols: List[np.ndarray] = []
    feature_names: List[str] = []
    col_groups: Dict[str, List[int]] = {}
    orig_predictor_names: List[str] = []

    for col in pred_cols:
        orig_predictor_names.append(col.name)
        raw = [col.values[r] for r in valid_rows]
        if col.kind == "number":
            arr = np.asarray([float(v) for v in raw], dtype=float)
            idx_pos = len(encoded_cols)
            encoded_cols.append(arr)
            feature_names.append(col.name)
            col_groups[col.name] = [idx_pos]
        else:
            cats = sorted({str(v) for v in raw})
            if len(cats) <= 1:
                continue
            group_indices: List[int] = []
            # Drop first reference level for linear/MARS collinearity safety
            for cat in cats[1:]:
                ind = np.asarray([1.0 if str(v) == cat else 0.0 for v in raw], dtype=float)
                group_indices.append(len(encoded_cols))
                encoded_cols.append(ind)
                feature_names.append(f"{col.name}[{cat}]")
            col_groups[col.name] = group_indices

    if not encoded_cols:
        raise ValueError("Predictors must contain at least one non-constant feature.")

    X = np.column_stack(encoded_cols)

    # Determine Regression vs Classification task
    raw_y = [resp_col.values[r] for r in valid_rows]
    t_norm = task.strip().lower()
    if t_norm == "auto":
        if resp_col.kind != "number":
            inferred_task = "classification"
        else:
            uniq = {float(v) for v in raw_y}
            inferred_task = "classification" if len(uniq) == 2 and uniq.issubset({0.0, 1.0}) else "regression"
    elif t_norm in ("classification", "class", "binary"):
        inferred_task = "classification"
    else:
        inferred_task = "regression"

    if inferred_task == "classification":
        str_y = [str(int(v)) if resp_col.kind == "number" and float(v).is_integer() else str(v) for v in raw_y]
        classes = sorted(set(str_y))
        if len(classes) < 2:
            raise ValueError("Classification requires at least 2 distinct response classes.")
        cls_map = {c: i for i, c in enumerate(classes)}
        y = np.asarray([cls_map[s] for s in str_y], dtype=int)
    else:
        if resp_col.kind != "number":
            raise ValueError("Regression requires a numeric response variable.")
        classes = []
        y = np.asarray([float(v) for v in raw_y], dtype=float)

    return {
        "X": X,
        "y": y,
        "task": inferred_task,
        "classes": classes,
        "response_name": resp_col.name,
        "feature_names": feature_names,
        "predictor_names": orig_predictor_names,
        "col_groups": col_groups,
        "n": len(valid_rows),
        "valid_rows": valid_rows,
        "total_rows": n_rows,
    }


def _compute_roc_curve(y_true: np.ndarray, p1: np.ndarray, n_pts: int = 25) -> List[Dict[str, float]]:
    pos = max(1, int(np.sum(y_true == 1)))
    neg = max(1, int(np.sum(y_true == 0)))
    threshs = np.linspace(1.0, 0.0, n_pts)
    pts = []
    for th in threshs:
        pred1 = p1 >= th
        tpr = float(np.sum(pred1 & (y_true == 1))) / pos
        fpr = float(np.sum(pred1 & (y_true == 0))) / neg
        pts.append({"fpr": fpr, "tpr": tpr})
    return pts


def _format_mars_equation(basis_rows: Sequence[Dict[str, Any]]) -> str:
    parts = [f"{basis_rows[0]['coef']:.5g}"]
    for row in basis_rows[1:]:
        c = float(row["coef"])
        if abs(c) < 1e-12:
            continue
        sign = " + " if c >= 0 else " - "
        parts.append(f"{sign}{abs(c):.5g} * {row['basis']}")
    return "".join(parts)


def _align_predictions(ds: Dict[str, Any], pred_vals: Any, y_arr: np.ndarray, eff_task: str, classes: Sequence[str]):
    total = int(ds["total_rows"])
    v_rows = ds["valid_rows"]
    fits: List[Any] = [None] * total
    resids: List[Any] = [None] * total
    if eff_task == "regression":
        for pos, r_idx in enumerate(v_rows):
            fv = float(pred_vals[pos])
            fits[r_idx] = fv
            resids[r_idx] = float(y_arr[pos]) - fv
    else:
        idx_cls = np.argmax(pred_vals, axis=1)
        for pos, r_idx in enumerate(v_rows):
            fits[r_idx] = str(classes[int(idx_cls[pos])])
            resids[r_idx] = float(pred_vals[pos, 1]) if len(classes) == 2 else float(np.max(pred_vals[pos]))
    return fits, resids


def _aggregate_importance(
    raw_imp: np.ndarray,
    col_groups: Dict[str, List[int]],
    predictor_names: List[str],
) -> List[Dict[str, Any]]:
    """Aggregate encoded feature importances back to original predictors on 0-100 scale."""
    grouped: Dict[str, float] = {}
    for pname in predictor_names:
        idxs = col_groups.get(pname, [])
        grouped[pname] = float(sum(raw_imp[i] for i in idxs if i < len(raw_imp)))
    top_val = max(grouped.values(), default=0.0)
    rows = []
    for pname, val in sorted(grouped.items(), key=lambda kv: kv[1], reverse=True):
        rel = (val / top_val * 100.0) if top_val > 1e-15 else 0.0
        rows.append({"predictor": pname, "relative_importance": rel, "raw_importance": val})
    return rows


def _roc_auc_binary(y_true: np.ndarray, y_prob: np.ndarray) -> Optional[float]:
    pos = int(np.sum(y_true == 1))
    neg = int(np.sum(y_true == 0))
    if pos == 0 or neg == 0:
        return None
    ranks = stats.rankdata(y_prob)
    auc = (float(np.sum(ranks[y_true == 1])) - pos * (pos + 1) / 2.0) / (pos * neg)
    return float(auc)


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    resid = y_true - y_pred
    mse = float(np.mean(resid * resid))
    rmse = math.sqrt(mse)
    mae = float(np.mean(np.abs(resid)))
    sst = float(np.sum((y_true - float(np.mean(y_true))) ** 2))
    r2 = 1.0 - float(np.sum(resid * resid)) / sst if sst > 1e-15 else 0.0
    return {"r2": r2, "rmse": rmse, "mse": mse, "mae": mae}


def _classification_metrics(y_true: np.ndarray, probs: np.ndarray, classes: Sequence[str]) -> Dict[str, Any]:
    pred_idx = np.argmax(probs, axis=1)
    acc = float(np.mean(pred_idx == y_true))
    k = len(classes)
    cm = np.zeros((k, k), dtype=int)
    for t, p in zip(y_true, pred_idx):
        cm[int(t), int(p)] += 1
    p_true = np.clip(probs[np.arange(len(y_true)), y_true], 1e-12, 1.0)
    logloss = -float(np.mean(np.log(p_true)))
    auc = _roc_auc_binary(y_true, probs[:, 1]) if k == 2 else None
    return {
        "accuracy": acc,
        "error_rate": 1.0 - acc,
        "log_loss": logloss,
        "roc_auc": auc,
        "confusion_matrix": cm.tolist(),
    }


def _train_test_split(n: int, val_frac: float, y: np.ndarray, task: str, rng: np.random.Generator) -> Tuple[np.ndarray, np.ndarray]:
    if task == "classification":
        tr_idx, va_idx = [], []
        for cls in np.unique(y):
            c_idx = np.where(y == cls)[0].copy()
            rng.shuffle(c_idx)
            n_val = max(1, int(round(len(c_idx) * val_frac))) if len(c_idx) >= 3 else 0
            va_idx.extend(c_idx[:n_val].tolist())
            tr_idx.extend(c_idx[n_val:].tolist())
        if len(va_idx) >= 2 and len(tr_idx) >= 4:
            return np.asarray(sorted(tr_idx), dtype=int), np.asarray(sorted(va_idx), dtype=int)
    perm = rng.permutation(n)
    n_val = max(2, min(n - 4, int(round(n * val_frac))))
    return perm[n_val:], perm[:n_val]


# ---------------------------------------------------------------------------
# Fast Vectorized CART Decision Tree Kernel
# ---------------------------------------------------------------------------

@dataclass
class _FastNode:
    is_leaf: bool = True
    value: Any = 0.0  # float for reg, np.ndarray class probs for cls
    feature: int = -1
    threshold: float = 0.0
    left: Optional["_FastNode"] = None
    right: Optional["_FastNode"] = None


class FastDecisionTree:
    """Vectorized NumPy CART tree for fast regression/classification ensembles."""

    def __init__(
        self,
        task: str = "regression",
        max_depth: int = 8,
        min_samples_leaf: int = 2,
        max_features: Optional[int] = None,
        n_classes: int = 0,
        rng: Optional[np.random.Generator] = None,
    ):
        self.task = task
        self.max_depth = max(1, int(max_depth))
        self.min_samples_leaf = max(1, int(min_samples_leaf))
        self.max_features = max_features
        self.n_classes = n_classes
        self.rng = rng or np.random.default_rng(42)
        self.root: Optional[_FastNode] = None
        self.feature_importances_: Optional[np.ndarray] = None

    def fit(self, X: np.ndarray, y: np.ndarray, sample_weight: Optional[np.ndarray] = None) -> "FastDecisionTree":
        n, p = X.shape
        self.feature_importances_ = np.zeros(p, dtype=float)
        idx = np.arange(n, dtype=int)
        if sample_weight is not None and len(idx) != n:
            raise ValueError("Sample weights length mismatch.")
        self.root = self._build(X, y, idx, depth=0)
        return self

    def _leaf_value(self, y_sub: np.ndarray) -> Any:
        if self.task == "regression":
            return float(np.mean(y_sub))
        counts = np.bincount(y_sub.astype(int), minlength=self.n_classes).astype(float)
        return counts / max(1.0, float(np.sum(counts)))

    def _build(self, X: np.ndarray, y: np.ndarray, idx: np.ndarray, depth: int) -> _FastNode:
        n = len(idx)
        y_sub = y[idx]
        leaf_val = self._leaf_value(y_sub)
        if depth >= self.max_depth or n < 2 * self.min_samples_leaf:
            return _FastNode(is_leaf=True, value=leaf_val)

        if self.task == "regression":
            if float(np.var(y_sub)) < 1e-12:
                return _FastNode(is_leaf=True, value=leaf_val)
        else:
            if len(np.unique(y_sub)) <= 1:
                return _FastNode(is_leaf=True, value=leaf_val)

        p = X.shape[1]
        if self.max_features is not None and self.max_features < p:
            cand_feats = self.rng.choice(p, size=max(1, int(self.max_features)), replace=False)
        else:
            cand_feats = np.arange(p)

        best_gain = 1e-12
        best_feat = -1
        best_thresh = 0.0
        min_leaf = self.min_samples_leaf

        if self.task == "regression":
            total_sum = float(np.sum(y_sub))
            total_sq = float(np.sum(y_sub * y_sub))
            parent_sse = total_sq - (total_sum * total_sum) / n
            for f in cand_feats:
                xf = X[idx, f]
                order = np.argsort(xf, kind="mergesort")
                xs = xf[order]
                ys = y_sub[order]
                # valid split positions strictly separating distinct consecutive values
                diff_mask = xs[min_leaf - 1 : n - min_leaf] < xs[min_leaf : n - min_leaf + 1] - 1e-12
                if not np.any(diff_mask):
                    continue
                csum = np.cumsum(ys)
                left_n = np.arange(min_leaf, n - min_leaf + 1, dtype=float)
                right_n = n - left_n
                left_sum = csum[min_leaf - 1 : n - min_leaf]
                right_sum = total_sum - left_sum
                # Maximizing (left_sum^2 / nL + right_sum^2 / nR) minimizes SSE
                score = (left_sum * left_sum) / left_n + (right_sum * right_sum) / right_n
                score = np.where(diff_mask, score, -np.inf)
                pos = int(np.argmax(score))
                best_child_sse = total_sq - float(score[pos])
                gain = parent_sse - best_child_sse
                if gain > best_gain:
                    best_gain = gain
                    best_feat = int(f)
                    split_k = min_leaf - 1 + pos
                    best_thresh = 0.5 * (float(xs[split_k]) + float(xs[split_k + 1]))
        else:
            k_cls = self.n_classes
            onehot = np.eye(k_cls, dtype=float)[y_sub.astype(int)]
            total_c = np.sum(onehot, axis=0)
            parent_gini_weighted = n - float(np.sum(total_c * total_c)) / n
            for f in cand_feats:
                xf = X[idx, f]
                order = np.argsort(xf, kind="mergesort")
                xs = xf[order]
                ohs = onehot[order]
                diff_mask = xs[min_leaf - 1 : n - min_leaf] < xs[min_leaf : n - min_leaf + 1] - 1e-12
                if not np.any(diff_mask):
                    continue
                ccounts = np.cumsum(ohs, axis=0)[min_leaf - 1 : n - min_leaf]
                left_n = np.arange(min_leaf, n - min_leaf + 1, dtype=float)
                right_n = n - left_n
                rcounts = total_c - ccounts
                # Maximizing sum(cL^2)/nL + sum(cR^2)/nR minimizes weighted Gini impurity
                score = np.sum(ccounts * ccounts, axis=1) / left_n + np.sum(rcounts * rcounts, axis=1) / right_n
                score = np.where(diff_mask, score, -np.inf)
                pos = int(np.argmax(score))
                gain = float(score[pos]) - (n - parent_gini_weighted)
                if gain > best_gain:
                    best_gain = gain
                    best_feat = int(f)
                    split_k = min_leaf - 1 + pos
                    best_thresh = 0.5 * (float(xs[split_k]) + float(xs[split_k + 1]))

        if best_feat < 0:
            return _FastNode(is_leaf=True, value=leaf_val)

        if self.feature_importances_ is not None:
            self.feature_importances_[best_feat] += best_gain

        left_mask = X[idx, best_feat] <= best_thresh
        left_idx = idx[left_mask]
        right_idx = idx[~left_mask]
        if len(left_idx) < min_leaf or len(right_idx) < min_leaf:
            return _FastNode(is_leaf=True, value=leaf_val)

        return _FastNode(
            is_leaf=False,
            value=leaf_val,
            feature=best_feat,
            threshold=best_thresh,
            left=self._build(X, y, left_idx, depth + 1),
            right=self._build(X, y, right_idx, depth + 1),
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        n = X.shape[0]
        if self.task == "regression":
            out = np.empty(n, dtype=float)
            self._pred_into(self.root, X, np.arange(n, dtype=int), out)
            return out
        out_p = np.empty((n, self.n_classes), dtype=float)
        self._pred_into(self.root, X, np.arange(n, dtype=int), out_p)
        return out_p

    def _pred_into(self, node: Optional[_FastNode], X: np.ndarray, idx: np.ndarray, out: np.ndarray) -> None:
        if node is None or len(idx) == 0:
            return
        if node.is_leaf:
            out[idx] = node.value
            return
        go_left = X[idx, node.feature] <= node.threshold
        self._pred_into(node.left, X, idx[go_left], out)
        self._pred_into(node.right, X, idx[~go_left], out)

    def assign_leaf_indices(self, X: np.ndarray) -> Tuple[np.ndarray, List[int]]:
        """Assign each row in X to a unique integer leaf index."""
        n = X.shape[0]
        leaf_ids = np.empty(n, dtype=int)
        counter = [0]

        def walk(node: Optional[_FastNode], idx: np.ndarray) -> None:
            if node is None or len(idx) == 0:
                return
            if node.is_leaf:
                lid = counter[0]
                counter[0] += 1
                leaf_ids[idx] = lid
                return
            go_left = X[idx, node.feature] <= node.threshold
            walk(node.left, idx[go_left])
            walk(node.right, idx[~go_left])

        walk(self.root, np.arange(n, dtype=int))
        return leaf_ids, list(range(counter[0]))


# ---------------------------------------------------------------------------
# 1. Random Forests (Classification & Regression + Out-of-Bag Error)
# ---------------------------------------------------------------------------

def random_forest_fit(
    worksheet: Any,
    response_index: int,
    predictor_indices: Sequence[int],
    task: str = "auto",
    n_trees: int = 80,
    max_depth: int = 8,
    min_samples_leaf: int = 2,
    max_features: str = "auto",
    seed: int = 42,
) -> Dict[str, Any]:
    """Fit a Random Forest with genuine Out-of-Bag (OOB) validation & variable importance."""
    ds = prepare_ml_dataset(worksheet, response_index, predictor_indices, task=task)
    X, y, eff_task = ds["X"], ds["y"], ds["task"]
    n, p = X.shape
    classes = ds["classes"]
    n_cls = len(classes)

    if isinstance(max_features, str):
        if max_features.lower() == "all":
            mtry = p
        elif max_features.lower() == "sqrt" or (max_features.lower() == "auto" and eff_task == "classification"):
            mtry = max(1, int(round(math.sqrt(p))))
        else:
            mtry = max(min(p, 2), int(round(p / 3.0)))
    else:
        mtry = max(1, min(p, int(max_features)))

    nt = max(5, min(500, int(n_trees)))
    rng = np.random.default_rng(int(seed))

    oob_sum = np.zeros(n, dtype=float) if eff_task == "regression" else np.zeros((n, n_cls), dtype=float)
    oob_cnt = np.zeros(n, dtype=int)
    in_sum = np.zeros_like(oob_sum)
    imp_total = np.zeros(p, dtype=float)
    oob_curve: List[Dict[str, Any]] = []
    trees: List[FastDecisionTree] = []

    stride = max(1, nt // 8)
    for t_idx in range(nt):
        boot = rng.integers(0, n, size=n)
        in_bag = np.zeros(n, dtype=bool)
        in_bag[boot] = True
        oob_mask = ~in_bag

        tree = FastDecisionTree(
            task=eff_task,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            max_features=mtry,
            n_classes=n_cls,
            rng=rng,
        )
        tree.fit(X[boot], y[boot])
        trees.append(tree)
        if tree.feature_importances_ is not None:
            imp_total += tree.feature_importances_

        in_sum += tree.predict(X)
        if np.any(oob_mask):
            oob_idx = np.where(oob_mask)[0]
            oob_sum[oob_idx] += tree.predict(X[oob_idx])
            oob_cnt[oob_idx] += 1

        if (t_idx + 1) % stride == 0 or t_idx == nt - 1:
            valid_oob = oob_cnt > 0
            if np.any(valid_oob):
                if eff_task == "regression":
                    preds_oob = oob_sum[valid_oob] / oob_cnt[valid_oob]
                    m = _regression_metrics(y[valid_oob], preds_oob)
                    oob_curve.append({"trees": t_idx + 1, "metric": m["rmse"], "r2": m["r2"]})
                else:
                    probs_oob = oob_sum[valid_oob] / oob_cnt[valid_oob][:, None]
                    err = float(np.mean(np.argmax(probs_oob, axis=1) != y[valid_oob]))
                    oob_curve.append({"trees": t_idx + 1, "metric": err, "accuracy": 1.0 - err})

    valid_oob = oob_cnt > 0
    roc_pts = []
    if eff_task == "regression":
        train_pred = in_sum / nt
        train_metrics = _regression_metrics(y, train_pred)
        oob_pred = oob_sum[valid_oob] / oob_cnt[valid_oob] if np.any(valid_oob) else train_pred
        oob_y = y[valid_oob] if np.any(valid_oob) else y
        oob_metrics = _regression_metrics(oob_y, oob_pred)
        fits_row, resids_row = _align_predictions(ds, train_pred, y, eff_task, classes)
    else:
        train_probs = in_sum / nt
        train_metrics = _classification_metrics(y, train_probs, classes)
        oob_probs = oob_sum[valid_oob] / oob_cnt[valid_oob][:, None] if np.any(valid_oob) else train_probs
        oob_y = y[valid_oob] if np.any(valid_oob) else y
        oob_metrics = _classification_metrics(oob_y, oob_probs, classes)
        if len(classes) == 2:
            roc_pts = _compute_roc_curve(oob_y, oob_probs[:, 1])
        fits_row, resids_row = _align_predictions(ds, train_probs, y, eff_task, classes)

    importance = _aggregate_importance(imp_total, ds["col_groups"], ds["predictor_names"])
    return {
        "analysis": "random_forest",
        "task": eff_task,
        "response": ds["response_name"],
        "predictors": ds["predictor_names"],
        "classes": classes,
        "n": n,
        "n_trees": nt,
        "mtry": mtry,
        "max_depth": int(max_depth),
        "train_metrics": train_metrics,
        "oob_metrics": oob_metrics,
        "oob_covered": int(np.sum(valid_oob)),
        "oob_curve": oob_curve,
        "variable_importance": importance,
        "roc_curve": roc_pts,
        "_fits": fits_row,
        "_residuals": resids_row,
        "_trees": trees,
        "_ds": ds,
    }


def _predict_forest(model_res: Dict[str, Any], X: np.ndarray) -> np.ndarray:
    trees: List[FastDecisionTree] = model_res["_trees"]
    if model_res["task"] == "regression":
        return np.mean([t.predict(X) for t in trees], axis=0)
    return np.mean([t.predict(X) for t in trees], axis=0)


# ---------------------------------------------------------------------------
# 2. TreeNet® Stochastic Gradient Boosting
# ---------------------------------------------------------------------------

def treenet_fit(
    worksheet: Any,
    response_index: int,
    predictor_indices: Sequence[int],
    task: str = "auto",
    n_trees: int = 100,
    learning_rate: float = 0.08,
    max_depth: int = 3,
    subsample: float = 0.8,
    loss: str = "ls",
    validation_fraction: float = 0.2,
    seed: int = 42,
) -> Dict[str, Any]:
    """Fit Friedman's Stochastic Gradient Boosting (TreeNet) model."""
    ds = prepare_ml_dataset(worksheet, response_index, predictor_indices, task=task)
    X, y, eff_task = ds["X"], ds["y"], ds["task"]
    n, p = X.shape
    classes = ds["classes"]
    if eff_task == "classification" and len(classes) > 2:
        # Collapse multi-class or handle one-vs-rest cleanly via highest frequency class vs rest?
        # Even better: support true K-class Softmax Gradient Boosting cleanly!
        pass

    nt = max(5, min(500, int(n_trees)))
    lr = float(np.clip(learning_rate, 0.005, 1.0))
    sub = float(np.clip(subsample, 0.3, 1.0))
    rng = np.random.default_rng(int(seed))

    if validation_fraction > 0 and n >= 12:
        tr_idx, va_idx = _train_test_split(n, float(validation_fraction), y, eff_task, rng)
    else:
        tr_idx = np.arange(n, dtype=int)
        va_idx = np.arange(n, dtype=int)

    X_tr, y_tr = X[tr_idx], y[tr_idx]
    X_va, y_va = X[va_idx], y[va_idx]
    n_tr = len(tr_idx)

    imp_total = np.zeros(p, dtype=float)
    stages: List[Any] = []
    history: List[Dict[str, float]] = []

    if eff_task == "regression":
        use_huber = loss.strip().lower() == "huber"
        init_val = float(np.median(y_tr) if use_huber else np.mean(y_tr))
        f_tr = np.full(n_tr, init_val, dtype=float)
        f_va = np.full(len(va_idx), init_val, dtype=float)

        best_va_loss = float("inf")
        best_iter = nt
        for m in range(nt):
            resid = y_tr - f_tr
            if use_huber:
                delta = max(1e-6, float(np.percentile(np.abs(resid), 90)))
                grad = np.clip(resid, -delta, delta)
            else:
                grad = resid

            sub_n = max(4, int(round(n_tr * sub)))
            sub_idx = rng.choice(n_tr, size=sub_n, replace=False) if sub_n < n_tr else np.arange(n_tr)

            tree = FastDecisionTree(task="regression", max_depth=max_depth, min_samples_leaf=2, rng=rng)
            tree.fit(X_tr[sub_idx], grad[sub_idx])
            if tree.feature_importances_ is not None:
                imp_total += tree.feature_importances_
            stages.append(tree)

            f_tr += lr * tree.predict(X_tr)
            f_va += lr * tree.predict(X_va)
            tr_mse = float(np.mean((y_tr - f_tr) ** 2))
            va_mse = float(np.mean((y_va - f_va) ** 2))
            if va_mse < best_va_loss:
                best_va_loss = va_mse
                best_iter = m + 1
            if (m + 1) % max(1, nt // 8) == 0 or m == nt - 1:
                history.append({"trees": m + 1, "train_loss": math.sqrt(tr_mse), "val_loss": math.sqrt(va_mse)})

        # Evaluate at optimal number of trees
        f_tr_opt = np.full(n_tr, init_val, dtype=float)
        f_va_opt = np.full(len(va_idx), init_val, dtype=float)
        for tree in stages[:best_iter]:
            f_tr_opt += lr * tree.predict(X_tr)
            f_va_opt += lr * tree.predict(X_va)

        train_metrics = _regression_metrics(y_tr, f_tr_opt)
        val_metrics = _regression_metrics(y_va, f_va_opt)
    else:
        n_cls = len(classes)
        if n_cls == 2:
            p_base = float(np.clip(np.mean(y_tr), 1e-4, 1.0 - 1e-4))
            init_val = math.log(p_base / (1.0 - p_base))
            f_tr = np.full(n_tr, init_val, dtype=float)
            f_va = np.full(len(va_idx), init_val, dtype=float)

            best_va_loss = float("inf")
            best_iter = nt
            for m in range(nt):
                prob_tr = 1.0 / (1.0 + np.exp(-np.clip(f_tr, -30.0, 30.0)))
                grad = y_tr - prob_tr

                sub_n = max(4, int(round(n_tr * sub)))
                sub_idx = rng.choice(n_tr, size=sub_n, replace=False) if sub_n < n_tr else np.arange(n_tr)

                tree = FastDecisionTree(task="regression", max_depth=max_depth, min_samples_leaf=2, rng=rng)
                tree.fit(X_tr[sub_idx], grad[sub_idx])
                if tree.feature_importances_ is not None:
                    imp_total += tree.feature_importances_

                # Newton leaf adjustment gamma = sum(grad) / sum(p*(1-p))
                leaf_ids, u_leaves = tree.assign_leaf_indices(X_tr)
                node_vals: Dict[int, float] = {}
                w_tr = np.maximum(1e-6, prob_tr * (1.0 - prob_tr))

                def _adjust_leaves(node: Optional[_FastNode], lid_counter: List[int]) -> None:
                    if node is None:
                        return
                    if node.is_leaf:
                        lid = lid_counter[0]
                        lid_counter[0] += 1
                        mask = leaf_ids == lid
                        if np.any(mask):
                            gamma = float(np.sum(grad[mask])) / float(np.sum(w_tr[mask]))
                            node.value = float(np.clip(gamma, -4.0, 4.0))
                            node_vals[lid] = node.value
                        return
                    _adjust_leaves(node.left, lid_counter)
                    _adjust_leaves(node.right, lid_counter)

                _adjust_leaves(tree.root, [0])
                stages.append(tree)

                f_tr += lr * tree.predict(X_tr)
                f_va += lr * tree.predict(X_va)

                p_va = 1.0 / (1.0 + np.exp(-np.clip(f_va, -30.0, 30.0)))
                p_tr_now = 1.0 / (1.0 + np.exp(-np.clip(f_tr, -30.0, 30.0)))
                tr_ll = -float(np.mean(y_tr * np.log(np.clip(p_tr_now, 1e-12, 1.0)) + (1 - y_tr) * np.log(np.clip(1 - p_tr_now, 1e-12, 1.0))))
                va_ll = -float(np.mean(y_va * np.log(np.clip(p_va, 1e-12, 1.0)) + (1 - y_va) * np.log(np.clip(1 - p_va, 1e-12, 1.0))))
                if va_ll < best_va_loss:
                    best_va_loss = va_ll
                    best_iter = m + 1
                if (m + 1) % max(1, nt // 8) == 0 or m == nt - 1:
                    history.append({"trees": m + 1, "train_loss": tr_ll, "val_loss": va_ll})

            def _eval_bin(X_in: np.ndarray) -> np.ndarray:
                raw_s = np.full(X_in.shape[0], init_val, dtype=float)
                for tr in stages[:best_iter]:
                    raw_s += lr * tr.predict(X_in)
                p1 = 1.0 / (1.0 + np.exp(-np.clip(raw_s, -30.0, 30.0)))
                return np.column_stack([1.0 - p1, p1])

            train_metrics = _classification_metrics(y_tr, _eval_bin(X_tr), classes)
            val_metrics = _classification_metrics(y_va, _eval_bin(X_va), classes)
        else:
            # Multi-class Softmax Boosting (K trees per stage)
            init_probs = np.bincount(y_tr, minlength=n_cls).astype(float) / max(1, n_tr)
            init_vec = np.log(np.clip(init_probs, 1e-4, 1.0))
            f_tr = np.tile(init_vec, (n_tr, 1))
            f_va = np.tile(init_vec, (len(va_idx), 1))
            onehot_tr = np.eye(n_cls, dtype=float)[y_tr]

            best_va_loss = float("inf")
            best_iter = nt
            for m in range(nt):
                ex_tr = np.exp(f_tr - np.max(f_tr, axis=1, keepdims=True))
                p_tr_mat = ex_tr / np.sum(ex_tr, axis=1, keepdims=True)
                grad_mat = onehot_tr - p_tr_mat

                sub_n = max(4, int(round(n_tr * sub)))
                sub_idx = rng.choice(n_tr, size=sub_n, replace=False) if sub_n < n_tr else np.arange(n_tr)

                k_trees: List[FastDecisionTree] = []
                for k in range(n_cls):
                    tree = FastDecisionTree(task="regression", max_depth=max_depth, min_samples_leaf=2, rng=rng)
                    tree.fit(X_tr[sub_idx], grad_mat[sub_idx, k])
                    if tree.feature_importances_ is not None:
                        imp_total += tree.feature_importances_
                    k_trees.append(tree)
                    f_tr[:, k] += lr * tree.predict(X_tr)
                    f_va[:, k] += lr * tree.predict(X_va)
                stages.append(k_trees)

                ex_va = np.exp(f_va - np.max(f_va, axis=1, keepdims=True))
                p_va_mat = ex_va / np.sum(ex_va, axis=1, keepdims=True)
                va_ll = -float(np.mean(np.log(np.clip(p_va_mat[np.arange(len(y_va)), y_va], 1e-12, 1.0))))
                if va_ll < best_va_loss:
                    best_va_loss = va_ll
                    best_iter = m + 1
                if (m + 1) % max(1, nt // 8) == 0 or m == nt - 1:
                    tr_ll = -float(np.mean(np.log(np.clip(p_tr_mat[np.arange(n_tr), y_tr], 1e-12, 1.0))))
                    history.append({"trees": m + 1, "train_loss": tr_ll, "val_loss": va_ll})

            def _eval_multi(X_in: np.ndarray) -> np.ndarray:
                scores = np.tile(init_vec, (X_in.shape[0], 1))
                for k_trees in stages[:best_iter]:
                    for k, tr in enumerate(k_trees):
                        scores[:, k] += lr * tr.predict(X_in)
                ex = np.exp(scores - np.max(scores, axis=1, keepdims=True))
                return ex / np.sum(ex, axis=1, keepdims=True)

            train_metrics = _classification_metrics(y_tr, _eval_multi(X_tr), classes)
            val_metrics = _classification_metrics(y_va, _eval_multi(X_va), classes)
            init_val = init_vec  # type: ignore[assignment]

    importance = _aggregate_importance(imp_total, ds["col_groups"], ds["predictor_names"])

    # Compute 5-point Partial Dependence Profile on top predictor
    pdp_points: List[Dict[str, float]] = []
    if importance:
        top_name = importance[0]["predictor"]
        top_cols = ds["col_groups"].get(top_name, [])
        if len(top_cols) == 1:
            col_j = top_cols[0]
            grid = np.linspace(float(np.min(X[:, col_j])), float(np.max(X[:, col_j])), 5)
            X_tmp = X.copy()
            for gv in grid:
                X_tmp[:, col_j] = gv
                if eff_task == "regression":
                    s = np.full(n, init_val, dtype=float)
                    for tr in stages[:best_iter]:
                        s += lr * tr.predict(X_tmp)
                    pdp_points.append({"x": float(gv), "y_hat": float(np.mean(s))})
                elif len(classes) == 2:
                    s = np.full(n, init_val, dtype=float)
                    for tr in stages[:best_iter]:
                        s += lr * tr.predict(X_tmp)
                    pdp_points.append({"x": float(gv), "prob_class1": float(np.mean(1.0 / (1.0 + np.exp(-np.clip(s, -30, 30)))))})

    roc_pts = []
    if eff_task == "classification" and len(classes) == 2:
        p_full = 1.0 / (1.0 + np.exp(-np.clip(
            np.full(n, float(init_val), dtype=float) + sum((lr * tr.predict(X) for tr in stages[:best_iter]), np.zeros(n)),
            -30.0, 30.0,
        )))
        roc_pts = _compute_roc_curve(y, p_full)
    full_pred = _predict_treenet({"_lr": lr, "_stages": stages[:best_iter], "_init": init_val, "task": eff_task, "classes": classes}, X)
    fits_row, resids_row = _align_predictions(ds, full_pred, y, eff_task, classes)

    return {
        "analysis": "treenet_gbm",
        "task": eff_task,
        "loss": loss if eff_task == "regression" else "binomial_deviance",
        "response": ds["response_name"],
        "predictors": ds["predictor_names"],
        "classes": classes,
        "n": n,
        "n_train": len(tr_idx),
        "n_val": len(va_idx),
        "n_trees_requested": nt,
        "optimal_trees": best_iter,
        "learning_rate": lr,
        "max_depth": int(max_depth),
        "subsample": sub,
        "train_metrics": train_metrics,
        "val_metrics": val_metrics,
        "history": history,
        "variable_importance": importance,
        "top_pdp": pdp_points,
        "roc_curve": roc_pts,
        "_fits": fits_row,
        "_residuals": resids_row,
        "_init": init_val,
        "_stages": stages[:best_iter],
        "_lr": lr,
        "_ds": ds,
    }


def _predict_treenet(model_res: Dict[str, Any], X: np.ndarray) -> np.ndarray:
    lr = model_res["_lr"]
    stages = model_res["_stages"]
    init = model_res["_init"]
    if model_res["task"] == "regression":
        s = np.full(X.shape[0], float(init), dtype=float)
        for tr in stages:
            s += lr * tr.predict(X)
        return s
    if len(model_res["classes"]) == 2:
        s = np.full(X.shape[0], float(init), dtype=float)
        for tr in stages:
            s += lr * tr.predict(X)
        p1 = 1.0 / (1.0 + np.exp(-np.clip(s, -30.0, 30.0)))
        return np.column_stack([1.0 - p1, p1])
    scores = np.tile(np.asarray(init, dtype=float), (X.shape[0], 1))
    for k_trees in stages:
        for k, tr in enumerate(k_trees):
            scores[:, k] += lr * tr.predict(X)
    ex = np.exp(scores - np.max(scores, axis=1, keepdims=True))
    return ex / np.sum(ex, axis=1, keepdims=True)


# ---------------------------------------------------------------------------
# 3. MARS® Multivariate Adaptive Regression Splines
# ---------------------------------------------------------------------------

@dataclass
class _HingeTerm:
    label: str
    factor_indices: Tuple[int, ...]
    knots: Tuple[float, ...]
    signs: Tuple[int, ...]  # +1 -> max(0, x - t), -1 -> max(0, t - x)
    parent_pos: Optional[int] = None

    def evaluate(self, X: np.ndarray) -> np.ndarray:
        vals = np.ones(X.shape[0], dtype=float)
        for f, k, s in zip(self.factor_indices, self.knots, self.signs):
            diff = (X[:, f] - k) if s > 0 else (k - X[:, f])
            vals *= np.maximum(0.0, diff)
        return vals


def _gcv_score(y: np.ndarray, B: np.ndarray, penalty_d: float) -> Tuple[float, np.ndarray]:
    n, m = B.shape
    beta, _, _, _ = np.linalg.lstsq(B, y, rcond=None)
    resid = y - B @ beta
    mse = float(np.mean(resid * resid))
    eff_df = m + penalty_d * max(0, m - 1) / 2.0
    denom = max(1e-6, 1.0 - eff_df / max(n, eff_df + 1.0))
    return mse / (denom * denom), beta


def _design_from_terms(X: np.ndarray, terms: Sequence[_HingeTerm]) -> np.ndarray:
    cols = [np.ones(X.shape[0], dtype=float)]
    cols.extend(t.evaluate(X) for t in terms)
    return np.column_stack(cols)


def mars_fit(
    worksheet: Any,
    response_index: int,
    predictor_indices: Sequence[int],
    task: str = "auto",
    max_terms: int = 16,
    max_degree: int = 2,
    penalty: float = 2.0,
) -> Dict[str, Any]:
    """Fit Friedman's MARS model via Forward Hinge Selection & GCV Backward Pruning."""
    ds = prepare_ml_dataset(worksheet, response_index, predictor_indices, task=task)
    X, y, eff_task = ds["X"], ds["y"], ds["task"]
    classes = ds["classes"]
    if eff_task == "classification" and len(classes) > 2:
        raise ValueError("MARS Classification currently supports binary responses (2 classes).")

    n, p = X.shape
    f_names = ds["feature_names"]
    y_work = y.astype(float)
    max_t = max(2, min(max(4, n - 2), int(max_terms)))
    deg_lim = 2 if int(max_degree) >= 2 else 1

    # Candidate knots per numeric predictor (quantile subset <= 18 knots for speed)
    cand_knots: Dict[int, np.ndarray] = {}
    for j in range(p):
        uvals = np.unique(X[:, j])
        if len(uvals) <= 2:
            cand_knots[j] = uvals[:1]
        elif len(uvals) <= 18:
            cand_knots[j] = uvals[1:-1]
        else:
            qs = np.linspace(10, 90, 15)
            cand_knots[j] = np.unique(np.percentile(uvals, qs))

    # Forward Stepwise Pass
    terms: List[_HingeTerm] = []
    B = np.ones((n, 1), dtype=float)
    best_gcv, _ = _gcv_score(y_work, B, penalty)

    while len(terms) + 1 < max_t:
        # Check residual reduction via orthogonal projection onto candidate hinges
        beta_curr, _, _, _ = np.linalg.lstsq(B, y_work, rcond=None)
        sse_curr = float(np.sum((y_work - B @ beta_curr) ** 2))
        best_pair: Optional[List[_HingeTerm]] = None
        best_sse = sse_curr * (1.0 - 1e-4)

        parent_candidates: List[Optional[int]] = [None]
        if deg_lim == 2:
            parent_candidates.extend(i for i, t in enumerate(terms) if len(t.factor_indices) == 1)

        for par_idx in parent_candidates:
            par_vec = np.ones(n, dtype=float) if par_idx is None else terms[par_idx].evaluate(X)
            used_feats = set() if par_idx is None else set(terms[par_idx].factor_indices)
            for j in range(p):
                if j in used_feats:
                    continue
                for k_val in cand_knots[j]:
                    h_pos = par_vec * np.maximum(0.0, X[:, j] - k_val)
                    h_neg = par_vec * np.maximum(0.0, k_val - X[:, j])
                    if np.count_nonzero(h_pos > 0) < 2 and np.count_nonzero(h_neg > 0) < 2:
                        continue
                    cols_try = [B]
                    pair_terms: List[_HingeTerm] = []
                    base_factors = () if par_idx is None else terms[par_idx].factor_indices
                    base_knots = () if par_idx is None else terms[par_idx].knots
                    base_signs = () if par_idx is None else terms[par_idx].signs
                    par_lbl = "" if par_idx is None else f"{terms[par_idx].label} * "

                    if np.count_nonzero(h_pos > 0) >= 2:
                        cols_try.append(h_pos[:, None])
                        pair_terms.append(_HingeTerm(
                            label=f"{par_lbl}max(0, {f_names[j]} - {k_val:.4g})",
                            factor_indices=base_factors + (j,),
                            knots=base_knots + (float(k_val),),
                            signs=base_signs + (1,),
                            parent_pos=par_idx,
                        ))
                    if np.count_nonzero(h_neg > 0) >= 2:
                        cols_try.append(h_neg[:, None])
                        pair_terms.append(_HingeTerm(
                            label=f"{par_lbl}max(0, {k_val:.4g} - {f_names[j]})",
                            factor_indices=base_factors + (j,),
                            knots=base_knots + (float(k_val),),
                            signs=base_signs + (-1,),
                            parent_pos=par_idx,
                        ))
                    B_try = np.hstack(cols_try)
                    b_try, _, _, _ = np.linalg.lstsq(B_try, y_work, rcond=None)
                    sse_try = float(np.sum((y_work - B_try @ b_try) ** 2))
                    if sse_try < best_sse:
                        best_sse = sse_try
                        best_pair = pair_terms

        if not best_pair:
            break
        for nt_term in best_pair:
            if len(terms) + 1 >= max_t:
                break
            terms.append(nt_term)
        B = _design_from_terms(X, terms)

    # Backward Pruning Pass minimizing GCV
    best_terms = list(terms)
    best_B = _design_from_terms(X, best_terms)
    best_gcv, best_beta = _gcv_score(y_work, best_B, penalty)

    cur_terms = list(terms)
    while cur_terms:
        prune_cand = None
        prune_gcv = float("inf")
        for drop_i in range(len(cur_terms)):
            sub_t = [t for k, t in enumerate(cur_terms) if k != drop_i]
            B_sub = _design_from_terms(X, sub_t)
            gcv_sub, _ = _gcv_score(y_work, B_sub, penalty)
            if gcv_sub < prune_gcv:
                prune_gcv = gcv_sub
                prune_cand = sub_t
        if prune_cand is None:
            break
        cur_terms = prune_cand
        B_cur = _design_from_terms(X, cur_terms)
        gcv_cur, beta_cur = _gcv_score(y_work, B_cur, penalty)
        if gcv_cur <= best_gcv + 1e-10:
            best_gcv = gcv_cur
            best_terms = list(cur_terms)
            best_beta = beta_cur
            best_B = B_cur

    # Optional IRLS logistic refinement for Binary Classification
    logistic_beta = None
    if eff_task == "classification":
        w_beta = np.zeros(best_B.shape[1], dtype=float)
        for _ in range(20):
            eta = np.clip(best_B @ w_beta, -25.0, 25.0)
            mu = 1.0 / (1.0 + np.exp(-eta))
            w = np.maximum(1e-6, mu * (1.0 - mu))
            z = eta + (y_work - mu) / w
            Bw = best_B * w[:, None]
            H = Bw.T @ best_B + 1e-6 * np.eye(best_B.shape[1])
            step = np.linalg.solve(H, Bw.T @ z)
            if float(np.max(np.abs(step - w_beta))) < 1e-6:
                w_beta = step
                break
            w_beta = step
        logistic_beta = w_beta
        probs_p1 = 1.0 / (1.0 + np.exp(-np.clip(best_B @ logistic_beta, -25.0, 25.0)))
        fit_metrics = _classification_metrics(y, np.column_stack([1.0 - probs_p1, probs_p1]), classes)
        active_beta = logistic_beta
    else:
        y_hat = best_B @ best_beta
        fit_metrics = _regression_metrics(y_work, y_hat)
        sst_var = float(np.var(y_work)) if np.var(y_work) > 1e-15 else 1.0
        fit_metrics["gcv_r2"] = max(0.0, 1.0 - best_gcv / sst_var)
        active_beta = best_beta

    # Variable Importance via leave-predictor-out GCV increase
    raw_imp = np.zeros(p, dtype=float)
    for j in range(p):
        sub_t = [t for t in best_terms if j not in t.factor_indices]
        if len(sub_t) < len(best_terms):
            B_wo = _design_from_terms(X, sub_t)
            gcv_wo, _ = _gcv_score(y_work, B_wo, penalty)
            raw_imp[j] = max(0.0, gcv_wo - best_gcv)

    basis_rows = [{"basis": "Intercept", "coef": float(active_beta[0])}]
    for t, c in zip(best_terms, active_beta[1:]):
        basis_rows.append({"basis": t.label, "coef": float(c)})

    roc_pts = []
    if eff_task == "classification":
        probs_all = np.column_stack([1.0 - probs_p1, probs_p1])
        roc_pts = _compute_roc_curve(y, probs_p1)
        fits_row, resids_row = _align_predictions(ds, probs_all, y, eff_task, classes)
    else:
        fits_row, resids_row = _align_predictions(ds, best_B @ best_beta, y_work, eff_task, classes)

    return {
        "analysis": "mars_regression",
        "task": eff_task,
        "response": ds["response_name"],
        "predictors": ds["predictor_names"],
        "classes": classes,
        "n": n,
        "n_basis_terms": len(basis_rows),
        "gcv": float(best_gcv),
        "equation": _format_mars_equation(basis_rows),
        "basis_functions": basis_rows,
        "metrics": fit_metrics,
        "roc_curve": roc_pts,
        "variable_importance": _aggregate_importance(raw_imp, ds["col_groups"], ds["predictor_names"]),
        "_fits": fits_row,
        "_residuals": resids_row,
        "_terms": best_terms,
        "_beta": active_beta,
        "_ds": ds,
    }


def _predict_mars(model_res: Dict[str, Any], X: np.ndarray) -> np.ndarray:
    B = _design_from_terms(X, model_res["_terms"])
    raw = B @ model_res["_beta"]
    if model_res["task"] == "regression":
        return raw
    p1 = 1.0 / (1.0 + np.exp(-np.clip(raw, -25.0, 25.0)))
    return np.column_stack([1.0 - p1, p1])


# ---------------------------------------------------------------------------
# 4. Discover Best Model® (AutoML Leaderboard)
# ---------------------------------------------------------------------------

def discover_best_model(
    worksheet: Any,
    response_index: int,
    predictor_indices: Sequence[int],
    task: str = "auto",
    validation_fraction: float = 0.25,
    seed: int = 42,
) -> Dict[str, Any]:
    """Train & benchmark CART, Random Forests, TreeNet, MARS, and Linear/Logistic on unified holdout."""
    ds = prepare_ml_dataset(worksheet, response_index, predictor_indices, task=task)
    X, y, eff_task = ds["X"], ds["y"], ds["task"]
    n, p = X.shape
    classes = ds["classes"]
    rng = np.random.default_rng(int(seed))
    tr_idx, va_idx = _train_test_split(n, float(validation_fraction), y, eff_task, rng)

    # Build a clean train-only sub-worksheet for consistent model evaluation
    from .model import Column, Worksheet

    sub_cols = []
    # Reconstruct selected columns indexed consistently at rows tr_idx
    orig_indices = [int(response_index)] + [int(i) for i in predictor_indices if int(i) != int(response_index)]
    resp_col = worksheet.columns[int(response_index)]
    pred_cols = [worksheet.columns[i] for i in orig_indices[1:]]
    all_sel = [resp_col] + pred_cols
    n_rows = min(len(c.values) for c in all_sel)
    valid_rows = [r for r in range(n_rows) if all(c.values[r] is not None for c in all_sel)]

    for c in all_sel:
        sub_vals = [c.values[valid_rows[idx]] for idx in tr_idx]
        sub_cols.append(Column(c.name, c.kind, sub_vals))
    tr_ws = Worksheet(columns=sub_cols)
    tr_resp_idx = 0
    tr_pred_idxs = list(range(1, len(sub_cols)))

    X_va = X[va_idx]
    y_va = y[va_idx]
    leaderboard: List[Dict[str, Any]] = []

    def _record_candidate(name: str, val_pred: np.ndarray, key_val: float, summary_str: str) -> None:
        if eff_task == "regression":
            vm = _regression_metrics(y_va, val_pred)
            leaderboard.append({
                "model": name,
                "score": vm["r2"],
                "val_r2": vm["r2"],
                "val_rmse": vm["rmse"],
                "val_mae": vm["mae"],
                "notes": summary_str,
            })
        else:
            vm = _classification_metrics(y_va, val_pred, classes)
            leaderboard.append({
                "model": name,
                "score": vm["accuracy"],
                "val_accuracy": vm["accuracy"],
                "val_log_loss": vm["log_loss"],
                "val_roc_auc": vm["roc_auc"],
                "notes": summary_str,
            })

    # Candidate 1: Parametric Linear / Logistic Regression Baseline
    X_tr_enc = np.column_stack([np.ones(len(tr_idx)), X[tr_idx]])
    X_va_enc = np.column_stack([np.ones(len(va_idx)), X_va])
    if eff_task == "regression":
        beta_ols, _, _, _ = np.linalg.lstsq(X_tr_enc, y[tr_idx], rcond=None)
        _record_candidate("Multiple Linear Regression", X_va_enc @ beta_ols, 0.0, f"{p} features")
    elif len(classes) == 2:
        w_beta = np.zeros(X_tr_enc.shape[1], dtype=float)
        y_tr_f = y[tr_idx].astype(float)
        for _ in range(20):
            eta = np.clip(X_tr_enc @ w_beta, -25.0, 25.0)
            mu = 1.0 / (1.0 + np.exp(-eta))
            w = np.maximum(1e-6, mu * (1.0 - mu))
            z = eta + (y_tr_f - mu) / w
            Bw = X_tr_enc * w[:, None]
            H = Bw.T @ X_tr_enc + 1e-5 * np.eye(X_tr_enc.shape[1])
            w_beta = np.linalg.solve(H, Bw.T @ z)
        p1 = 1.0 / (1.0 + np.exp(-np.clip(X_va_enc @ w_beta, -25.0, 25.0)))
        _record_candidate("Binary Logistic Regression", np.column_stack([1.0 - p1, p1]), 0.0, "Logit IRLS")

    # Candidate 2: Single CART Decision Tree
    cart = FastDecisionTree(task=eff_task, max_depth=6, min_samples_leaf=2, n_classes=len(classes), rng=rng)
    cart.fit(X[tr_idx], y[tr_idx])
    _record_candidate("CART Decision Tree", cart.predict(X_va), 0.0, "Depth <= 6")

    # Candidate 3: Random Forests
    rf = random_forest_fit(tr_ws, tr_resp_idx, tr_pred_idxs, task=eff_task, n_trees=60, seed=int(seed))
    _record_candidate("Random Forests", _predict_forest(rf, X_va), 0.0, f"{rf['n_trees']} trees, mtry={rf['mtry']}")

    # Candidate 4: TreeNet Gradient Boosting
    tn = treenet_fit(tr_ws, tr_resp_idx, tr_pred_idxs, task=eff_task, n_trees=70, validation_fraction=0.15, seed=int(seed))
    _record_candidate("TreeNet Gradient Boosting", _predict_treenet(tn, X_va), 0.0, f"Opt trees={tn['optimal_trees']}")

    # Candidate 5: MARS Splines (regression & binary classification)
    if eff_task == "regression" or len(classes) == 2:
        mrs = mars_fit(tr_ws, tr_resp_idx, tr_pred_idxs, task=eff_task, max_terms=12)
        _record_candidate("MARS Splines", _predict_mars(mrs, X_va), 0.0, f"{mrs['n_basis_terms']} basis terms")

    leaderboard.sort(key=lambda row: row["score"], reverse=True)
    for rank_i, row in enumerate(leaderboard, start=1):
        row["rank"] = rank_i

    return {
        "analysis": "discover_best_model",
        "task": eff_task,
        "response": ds["response_name"],
        "predictors": ds["predictor_names"],
        "classes": classes,
        "n_train": len(tr_idx),
        "n_val": len(va_idx),
        "champion_model": leaderboard[0]["model"],
        "leaderboard": leaderboard,
    }


# ---------------------------------------------------------------------------
# Report Formatter
# ---------------------------------------------------------------------------

def format_predictive_ml_report(result: Dict[str, Any]) -> str:
    kind = result.get("analysis", "")
    header = "─" * 74
    lines: List[str] = []

    def _imp_block(imp_rows: List[Dict[str, Any]]) -> None:
        lines.append("\nRelative Variable Importance (0–100%):")
        lines.append(f"  {'Predictor':<24} {'Rel. Importance':>16}  Bar")
        for row in imp_rows[:10]:
            pct = row["relative_importance"]
            bars = "█" * int(round(pct / 5.0))
            lines.append(f"  {row['predictor']:<24} {pct:>15.1f}%  {bars}")

    if kind == "random_forest":
        lines.append(f"Random Forests® ({result['task'].title()}): {result['response']}")
        lines.append(header)
        lines.append(
            f"Trees: {result['n_trees']}  |  Predictors/Split (mtry): {result['mtry']}  |  "
            f"Max Depth: {result['max_depth']}  |  N: {result['n']} (OOB covered: {result['oob_covered']})"
        )
        tm, om = result["train_metrics"], result["oob_metrics"]
        lines.append("\nModel Performance Summary:")
        if result["task"] == "regression":
            lines.append(f"  OOB R-sq        : {om['r2'] * 100:8.2f}%    |  Train R-sq   : {tm['r2'] * 100:8.2f}%")
            lines.append(f"  OOB RMSE        : {om['rmse']:8.4f}     |  Train RMSE   : {tm['rmse']:8.4f}")
            lines.append(f"  OOB MAE         : {om['mae']:8.4f}     |  Train MAE    : {tm['mae']:8.4f}")
        else:
            lines.append(f"  OOB Accuracy    : {om['accuracy'] * 100:8.2f}%    |  Train Accuracy: {tm['accuracy'] * 100:8.2f}%")
            lines.append(f"  OOB Error Rate  : {om['error_rate'] * 100:8.2f}%    |  OOB Log-Loss  : {om['log_loss']:8.4f}")
            if om.get("roc_auc") is not None:
                lines.append(f"  OOB ROC AUC     : {om['roc_auc']:8.4f}")
        _imp_block(result["variable_importance"])

    elif kind == "treenet_gbm":
        lines.append(f"TreeNet® Gradient Boosting ({result['task'].title()}): {result['response']}")
        lines.append(header)
        lines.append(
            f"Requested Trees: {result['n_trees_requested']}  |  Optimal Trees: {result['optimal_trees']}  |  "
            f"LR: {result['learning_rate']}  |  Subsample: {result['subsample']}  |  N(train/val): {result['n_train']}/{result['n_val']}"
        )
        tm, vm = result["train_metrics"], result["val_metrics"]
        lines.append("\nOptimal Tree Performance:")
        if result["task"] == "regression":
            lines.append(f"  Validation R-sq : {vm['r2'] * 100:8.2f}%    |  Train R-sq   : {tm['r2'] * 100:8.2f}%")
            lines.append(f"  Validation RMSE : {vm['rmse']:8.4f}     |  Train RMSE   : {tm['rmse']:8.4f}")
        else:
            lines.append(f"  Validation Acc  : {vm['accuracy'] * 100:8.2f}%    |  Train Acc    : {tm['accuracy'] * 100:8.2f}%")
            lines.append(f"  Validation Loss : {vm['log_loss']:8.4f}     |  Train Loss   : {tm['log_loss']:8.4f}")
            if vm.get("roc_auc") is not None:
                lines.append(f"  Validation AUC  : {vm['roc_auc']:8.4f}")
        _imp_block(result["variable_importance"])

    elif kind == "mars_regression":
        lines.append(f"MARS® Splines ({result['task'].title()}): {result['response']}")
        lines.append(header)
        m = result["metrics"]
        lines.append(f"N: {result['n']}  |  Selected Basis Functions: {result['n_basis_terms']}  |  GCV: {result['gcv']:.6g}")
        if result.get("equation"):
            lines.append(f"Equation: {result['response']} = {result['equation']}")
        if result["task"] == "regression":
            lines.append(f"R-sq: {m['r2'] * 100:.2f}%  |  GCV R-sq: {m.get('gcv_r2', 0) * 100:.2f}%  |  RMSE: {m['rmse']:.4f}  |  MAE: {m['mae']:.4f}")
        else:
            lines.append(f"Accuracy: {m['accuracy'] * 100:.2f}%  |  Log-Loss: {m['log_loss']:.4f}  |  ROC AUC: {m.get('roc_auc') or 0:.4f}")
        lines.append("\nSelected Basis Functions:")
        lines.append(f"  {'Term':<48} {'Coefficient':>14}")
        for row in result["basis_functions"]:
            lines.append(f"  {row['basis'][:47]:<48} {row['coef']:>14.6g}")
        _imp_block(result["variable_importance"])

    elif kind == "discover_best_model":
        lines.append(f"Discover Best Model® AutoML Leaderboard ({result['task'].title()}): {result['response']}")
        lines.append(header)
        lines.append(f"Holdout Split: {result['n_train']} Train / {result['n_val']} Validation  |  Champion: {result['champion_model']}")
        lines.append("")
        if result["task"] == "regression":
            lines.append(f"  {'Rank':<5} {'Model':<30} {'Val R-sq':>10} {'Val RMSE':>12} {'Val MAE':>12}  Details")
            for row in result["leaderboard"]:
                lines.append(
                    f"  {row['rank']:<5} {row['model']:<30} {row['val_r2'] * 100:>9.2f}% "
                    f"{row['val_rmse']:>12.4f} {row['val_mae']:>12.4f}  {row['notes']}"
                )
        else:
            lines.append(f"  {'Rank':<5} {'Model':<30} {'Val Acc':>10} {'Log-Loss':>12} {'ROC AUC':>10}  Details")
            for row in result["leaderboard"]:
                auc_s = f"{row['val_roc_auc']:.4f}" if row.get("val_roc_auc") is not None else "N/A"
                lines.append(
                    f"  {row['rank']:<5} {row['model']:<30} {row['val_accuracy'] * 100:>9.2f}% "
                    f"{row['val_log_loss']:>12.4f} {auc_s:>10}  {row['notes']}"
                )
    else:
        return str(result)

    return "\n".join(lines)
