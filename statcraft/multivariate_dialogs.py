"""Qt Dialogs for Multivariate Analysis with native StatCraft fidelity.

Covers:
- PcaDialog
- ItemAnalysisDialog
- ClusterObservationsDialog
- ClusterKMeansDialog
- ClusterVariablesDialog
- DiscriminantAnalysisDialog
- SimpleCorrespondenceDialog
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .model import Worksheet


class _MultivariateBaseDialog(QDialog):
    """Base dialog providing standard column selector list and variable binding."""

    def __init__(self, worksheet: Worksheet, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle(title)
        self.resize(560, 440)
        self.last_active_edit: Optional[QLineEdit] = None

    def _create_column_picker(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("Columns:")
        layout.addWidget(lbl)

        self.col_list = QListWidget()
        for idx, col in enumerate(self.worksheet.columns):
            name = col.name if col.name else f"C{idx + 1}"
            kind_tag = " (T)" if col.kind == "text" else ""
            item = QListWidgetItem(f"C{idx + 1}  {name}{kind_tag}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.col_list.addItem(item)

        self.col_list.itemDoubleClicked.connect(self._on_column_double_clicked)
        layout.addWidget(self.col_list)

        btn_select = QPushButton("Select >>")
        btn_select.clicked.connect(self._on_select_clicked)
        layout.addWidget(btn_select)
        return container

    def _on_column_double_clicked(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        col = self.worksheet.columns[idx]
        name = col.name if col.name else f"C{idx + 1}"
        if self.last_active_edit:
            curr = self.last_active_edit.text().strip()
            if curr:
                self.last_active_edit.setText(f"{curr} '{name}'")
            else:
                self.last_active_edit.setText(f"'{name}'")

    def _on_select_clicked(self) -> None:
        item = self.col_list.currentItem()
        if item:
            self._on_column_double_clicked(item)

    def _register_edit(self, edit: QLineEdit) -> None:
        edit.installEventFilter(self)
        if self.last_active_edit is None:
            self.last_active_edit = edit

    def eventFilter(self, obj, event):
        if event.type() == event.Type.FocusIn and isinstance(obj, QLineEdit):
            self.last_active_edit = obj
        return super().eventFilter(obj, event)

    def _parse_column_indices(self, text: str) -> List[int]:
        tokens = []
        in_quotes = False
        curr = ""
        for ch in text:
            if ch in ("'", '"'):
                in_quotes = not in_quotes
            elif ch in (",", " ") and not in_quotes:
                if curr.strip():
                    tokens.append(curr.strip())
                curr = ""
            else:
                curr += ch
        if curr.strip():
            tokens.append(curr.strip())

        indices = []
        for tok in tokens:
            cleaned = tok.strip("'\"")
            # Look up by name first
            found = False
            for idx, col in enumerate(self.worksheet.columns):
                name = col.name if col.name else f"C{idx + 1}"
                if name.lower() == cleaned.lower() or f"c{idx + 1}" == cleaned.lower():
                    indices.append(idx)
                    found = True
                    break
            if not found:
                if cleaned.upper().startswith("C") and cleaned[1:].isdigit():
                    idx = int(cleaned[1:]) - 1
                    if 0 <= idx < len(self.worksheet.columns):
                        indices.append(idx)
        return indices


# ==============================================================================
# 1. PCA DIALOG
# ==============================================================================

class PcaDialog(_MultivariateBaseDialog):
    """Dialog for Principal Components Analysis."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Principal Components Analysis", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        # Left picker
        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        # Right form
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_vars = QLineEdit()
        self._register_edit(self.edit_vars)
        form.addRow("Variables:", self.edit_vars)

        # Matrix type
        self.combo_matrix = QComboBox()
        self.combo_matrix.addItems(["Correlation", "Covariance"])
        form.addRow("Analyze:", self.combo_matrix)

        # Number of components
        self.spin_components = QSpinBox()
        self.spin_components.setRange(0, 100)
        self.spin_components.setSpecialValueText("All")
        self.spin_components.setValue(0)
        form.addRow("Number of Components:", self.spin_components)

        right_layout.addLayout(form)

        # Graph selection
        grp_graphs = QGroupBox("Graphs")
        grp_layout = QVBoxLayout(grp_graphs)
        self.chk_scree = QCheckBox("Scree Plot")
        self.chk_scree.setChecked(True)
        self.chk_loading = QCheckBox("Loading Plot (PC1 & PC2)")
        self.chk_score = QCheckBox("Score Plot (PC1 & PC2)")
        self.chk_biplot = QCheckBox("Biplot")
        grp_layout.addWidget(self.chk_scree)
        grp_layout.addWidget(self.chk_loading)
        grp_layout.addWidget(self.chk_score)
        grp_layout.addWidget(self.chk_biplot)
        right_layout.addWidget(grp_graphs)

        right_layout.addStretch()

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        indices = self._parse_column_indices(self.edit_vars.text())
        if len(indices) < 2:
            QMessageBox.warning(self, "Invalid Input", "Please select at least 2 variables for PCA.")
            return

        k_comp = self.spin_components.value()
        self.settings = {
            "variable_indices": indices,
            "matrix_type": self.combo_matrix.currentText().lower(),
            "n_components": k_comp if k_comp > 0 else None,
            "scree_plot": self.chk_scree.isChecked(),
            "loading_plot": self.chk_loading.isChecked(),
            "score_plot": self.chk_score.isChecked(),
            "biplot": self.chk_biplot.isChecked(),
        }
        self.accept()


# ==============================================================================
# 2. ITEM ANALYSIS DIALOG
# ==============================================================================

class ItemAnalysisDialog(_MultivariateBaseDialog):
    """Dialog for Item Analysis & Cronbach's Alpha."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Item Analysis", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_items = QLineEdit()
        self._register_edit(self.edit_items)
        form.addRow("Variables / Items:", self.edit_items)
        right_layout.addLayout(form)

        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        indices = self._parse_column_indices(self.edit_items.text())
        if len(indices) < 2:
            QMessageBox.warning(self, "Invalid Input", "Please select at least 2 items for Item Analysis.")
            return

        self.settings = {
            "variable_indices": indices,
        }
        self.accept()


# ==============================================================================
# 3. CLUSTER OBSERVATIONS DIALOG
# ==============================================================================

class ClusterObservationsDialog(_MultivariateBaseDialog):
    """Dialog for Hierarchical Clustering of Observations."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Cluster Observations", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_vars = QLineEdit()
        self._register_edit(self.edit_vars)
        form.addRow("Variables:", self.edit_vars)

        self.combo_linkage = QComboBox()
        self.combo_linkage.addItems(["Average", "Single", "Complete", "Centroid", "Ward", "Median", "McQuitty"])
        form.addRow("Linkage Method:", self.combo_linkage)

        self.combo_dist = QComboBox()
        self.combo_dist.addItems(["Euclidean", "Squared Euclidean", "Manhattan", "Maximum"])
        form.addRow("Distance Measure:", self.combo_dist)

        self.combo_std = QComboBox()
        self.combo_std.addItems(["None", "Standardize (Z-score)", "Range 0 to 1"])
        form.addRow("Standardize:", self.combo_std)

        self.spin_clusters = QSpinBox()
        self.spin_clusters.setRange(2, 50)
        self.spin_clusters.setValue(3)
        form.addRow("Number of Clusters:", self.spin_clusters)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        indices = self._parse_column_indices(self.edit_vars.text())
        if len(indices) < 1:
            QMessageBox.warning(self, "Invalid Input", "Please select at least 1 variable for clustering.")
            return

        dist_val = self.combo_dist.currentText().lower().replace(" ", "_")
        std_val = "zscore" if "Standardize" in self.combo_std.currentText() else ("range" if "Range" in self.combo_std.currentText() else "none")

        self.settings = {
            "variable_indices": indices,
            "linkage_method": self.combo_linkage.currentText().lower(),
            "distance_measure": dist_val,
            "standardize": std_val,
            "n_clusters": self.spin_clusters.value(),
        }
        self.accept()


# ==============================================================================
# 4. CLUSTER K-MEANS DIALOG
# ==============================================================================

class ClusterKMeansDialog(_MultivariateBaseDialog):
    """Dialog for K-Means Clustering."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Cluster K-Means", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_vars = QLineEdit()
        self._register_edit(self.edit_vars)
        form.addRow("Variables:", self.edit_vars)

        self.spin_k = QSpinBox()
        self.spin_k.setRange(2, 50)
        self.spin_k.setValue(3)
        form.addRow("Number of Clusters:", self.spin_k)

        self.spin_max_iter = QSpinBox()
        self.spin_max_iter.setRange(10, 500)
        self.spin_max_iter.setValue(100)
        form.addRow("Maximum Iterations:", self.spin_max_iter)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        indices = self._parse_column_indices(self.edit_vars.text())
        if len(indices) < 1:
            QMessageBox.warning(self, "Invalid Input", "Please select at least 1 variable for K-means clustering.")
            return

        self.settings = {
            "variable_indices": indices,
            "k_clusters": self.spin_k.value(),
            "max_iter": self.spin_max_iter.value(),
        }
        self.accept()


# ==============================================================================
# 5. CLUSTER VARIABLES DIALOG
# ==============================================================================

class ClusterVariablesDialog(_MultivariateBaseDialog):
    """Dialog for Hierarchical Clustering of Variables."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Cluster Variables", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_vars = QLineEdit()
        self._register_edit(self.edit_vars)
        form.addRow("Variables:", self.edit_vars)

        self.combo_linkage = QComboBox()
        self.combo_linkage.addItems(["Average", "Single", "Complete", "Centroid", "Ward"])
        form.addRow("Linkage Method:", self.combo_linkage)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        indices = self._parse_column_indices(self.edit_vars.text())
        if len(indices) < 2:
            QMessageBox.warning(self, "Invalid Input", "Please select at least 2 variables to cluster.")
            return

        self.settings = {
            "variable_indices": indices,
            "linkage_method": self.combo_linkage.currentText().lower(),
        }
        self.accept()


# ==============================================================================
# 6. DISCRIMINANT ANALYSIS DIALOG
# ==============================================================================

class DiscriminantAnalysisDialog(_MultivariateBaseDialog):
    """Dialog for Discriminant Analysis."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Discriminant Analysis", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_group = QLineEdit()
        self._register_edit(self.edit_group)
        form.addRow("Group / Class Column:", self.edit_group)

        self.edit_preds = QLineEdit()
        self._register_edit(self.edit_preds)
        form.addRow("Predictors:", self.edit_preds)

        self.combo_method = QComboBox()
        self.combo_method.addItems(["Linear", "Quadratic"])
        form.addRow("Discriminant Function:", self.combo_method)

        self.combo_priors = QComboBox()
        self.combo_priors.addItems(["Equal", "Proportional"])
        form.addRow("Prior Probabilities:", self.combo_priors)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        grp_idx = self._parse_column_indices(self.edit_group.text())
        if not grp_idx:
            QMessageBox.warning(self, "Invalid Input", "Please specify a group column.")
            return

        preds = self._parse_column_indices(self.edit_preds.text())
        if not preds:
            QMessageBox.warning(self, "Invalid Input", "Please select at least 1 predictor variable.")
            return

        self.settings = {
            "group_index": grp_idx[0],
            "predictor_indices": preds,
            "method": self.combo_method.currentText().lower(),
            "priors": self.combo_priors.currentText().lower(),
        }
        self.accept()


# ==============================================================================
# 7. SIMPLE CORRESPONDENCE DIALOG
# ==============================================================================

class SimpleCorrespondenceDialog(_MultivariateBaseDialog):
    """Dialog for Simple Correspondence Analysis."""

    def __init__(self, worksheet: Worksheet, settings: Optional[Dict[str, Any]] = None, parent: Optional[QWidget] = None):
        super().__init__(worksheet, "Simple Correspondence Analysis", parent)
        self.settings = copy.deepcopy(settings) if settings else {}
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)

        picker = self._create_column_picker()
        picker.setFixedWidth(180)
        main_layout.addWidget(picker)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)

        form = QFormLayout()
        self.edit_cols = QLineEdit()
        self._register_edit(self.edit_cols)
        form.addRow("Columns of Contingency Table:", self.edit_cols)

        right_layout.addLayout(form)
        right_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        right_layout.addWidget(buttons)

        main_layout.addWidget(right_container)

    def _validate_and_accept(self) -> None:
        cols = self._parse_column_indices(self.edit_cols.text())
        if len(cols) < 2:
            QMessageBox.warning(self, "Invalid Input", "Please select at least 2 columns forming the contingency table.")
            return

        self.settings = {
            "column_indices": cols,
        }
        self.accept()
