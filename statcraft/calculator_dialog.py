"""Minitab-style Calc > Calculator dialog with variables list, functions browser, keypad, and live formula checkbox."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from .variable_dialogs import load_dialog_state, save_dialog_state


FUNCTION_CATEGORIES = {
    "All functions": [
        ("ABS(number)", "ABS()"),
        ("AND(expr1, expr2)", "and "),
        ("CONCAT(a, b, ...)", "CONCAT(, )"),
        ("COS(radians)", "COS()"),
        ("EXP(number)", "EXP()"),
        ("IF(condition, true_val, false_val)", "IF(, , )"),
        ("ISMISS(val)", "ISMISS()"),
        ("LAG(column, k)", "LAG(, 1)"),
        ("LEFT(text, n)", "LEFT(, )"),
        ("LN(number)", "LN()"),
        ("LOG10(number)", "LOG10()"),
        ("LOWER(text)", "LOWER()"),
        ("MAX(column)", "MAX()"),
        ("MEAN(column)", "MEAN()"),
        ("MEDIAN(column)", "MEDIAN()"),
        ("MID(text, start, len)", "MID(, , )"),
        ("MIN(column)", "MIN()"),
        ("MOD(number, divisor)", "MOD(, )"),
        ("N(column)", "N()"),
        ("NOT(expr)", "not "),
        ("OR(expr1, expr2)", "or "),
        ("PERCENTILE(column, q)", "PERCENTILE(, )"),
        ("POWER(base, exp)", "POWER(, )"),
        ("Q1(column)", "Q1()"),
        ("Q3(column)", "Q3()"),
        ("RANGE(column)", "RANGE()"),
        ("REPLACE(text, old, new)", "REPLACE(, , )"),
        ("RIGHT(text, n)", "RIGHT(, )"),
        ("ROUND(number, digits)", "ROUND(, 2)"),
        ("ROWMAX(col1, col2, ...)", "ROWMAX(, )"),
        ("ROWMEAN(col1, col2, ...)", "ROWMEAN(, )"),
        ("ROWMIN(col1, col2, ...)", "ROWMIN(, )"),
        ("ROWSUM(col1, col2, ...)", "ROWSUM(, )"),
        ("SIN(radians)", "SIN()"),
        ("SQRT(number)", "SQRT()"),
        ("STDEV(column)", "STDEV()"),
        ("SUM(column)", "SUM()"),
        ("TAN(radians)", "TAN()"),
        ("TRIM(text)", "TRIM()"),
        ("UPPER(text)", "UPPER()"),
        ("ZSCORE(column)", "ZSCORE()"),
    ],
    "Arithmetic": [
        ("ABS(number)", "ABS()"),
        ("CEILING(number)", "CEILING()"),
        ("EXP(number)", "EXP()"),
        ("FLOOR(number)", "FLOOR()"),
        ("LN(number)", "LN()"),
        ("LOG10(number)", "LOG10()"),
        ("MOD(number, divisor)", "MOD(, )"),
        ("POWER(base, exp)", "POWER(, )"),
        ("ROUND(number, digits)", "ROUND(, 2)"),
        ("SIGN(number)", "SIGN()"),
        ("SQRT(number)", "SQRT()"),
        ("TRUNC(number)", "TRUNC()"),
    ],
    "Statistics": [
        ("IQR(column)", "IQR()"),
        ("LAG(column, k)", "LAG(, 1)"),
        ("MAX(column)", "MAX()"),
        ("MEAN(column)", "MEAN()"),
        ("MEDIAN(column)", "MEDIAN()"),
        ("MIN(column)", "MIN()"),
        ("N(column)", "N()"),
        ("NMISS(column)", "NMISS()"),
        ("PERCENTILE(column, q)", "PERCENTILE(, )"),
        ("Q1(column)", "Q1()"),
        ("Q3(column)", "Q3()"),
        ("RANGE(column)", "RANGE()"),
        ("ROWCOUNT(col1, col2, ...)", "ROWCOUNT(, )"),
        ("ROWMAX(col1, col2, ...)", "ROWMAX(, )"),
        ("ROWMEAN(col1, col2, ...)", "ROWMEAN(, )"),
        ("ROWMIN(col1, col2, ...)", "ROWMIN(, )"),
        ("ROWSTDEV(col1, col2, ...)", "ROWSTDEV(, )"),
        ("ROWSUM(col1, col2, ...)", "ROWSUM(, )"),
        ("STDEV(column)", "STDEV()"),
        ("SUM(column)", "SUM()"),
        ("VARIANCE(column)", "VARIANCE()"),
        ("ZSCORE(column)", "ZSCORE()"),
    ],
    "Logical": [
        ("AND(expr1, expr2)", "and "),
        ("IF(condition, true_val, false_val)", "IF(, , )"),
        ("ISMISS(val)", "ISMISS()"),
        ("NOT(expr)", "not "),
        ("OR(expr1, expr2)", "or "),
    ],
    "Text": [
        ("CONCAT(a, b, ...)", "CONCAT(, )"),
        ("LEFT(text, n)", "LEFT(, )"),
        ("LOWER(text)", "LOWER()"),
        ("MID(text, start, len)", "MID(, , )"),
        ("REPLACE(text, old, new)", "REPLACE(, , )"),
        ("RIGHT(text, n)", "RIGHT(, )"),
        ("TRIM(text)", "TRIM()"),
        ("UPPER(text)", "UPPER()"),
    ],
}


class CalculatorDialog(QDialog):
    """Interactive Calc > Calculator dialog with variables, functions, keypad, and formula option."""

    _STATE_KEY = "CalculatorDialog"

    def __init__(self, worksheet, parent=None):
        super().__init__(parent)
        self.worksheet = worksheet
        self.setWindowTitle("Calculator")
        self.setMinimumSize(780, 520)

        root = QHBoxLayout(self)

        # Left column: worksheet columns & stored constants
        left = QVBoxLayout()
        left.addWidget(QLabel("Variables & Constants:"))
        self.var_list = QListWidget()
        self.var_list.setMinimumWidth(200)
        for i, col in enumerate(worksheet.columns):
            prefix = f"C{i + 1}"
            item = QListWidgetItem(f"{prefix}  {col.name}")
            item.setData(Qt.ItemDataRole.UserRole, prefix)
            self.var_list.addItem(item)
        for i, const in enumerate(getattr(worksheet, "constants", [])):
            prefix = f"K{i + 1}"
            item = QListWidgetItem(f"{prefix}  {const.name}")
            item.setData(Qt.ItemDataRole.UserRole, prefix)
            self.var_list.addItem(item)
        self.var_list.itemDoubleClicked.connect(
            lambda item: self._insert_text(item.data(Qt.ItemDataRole.UserRole))
        )
        left.addWidget(self.var_list, 1)
        self.insert_var_btn = QPushButton("Insert Variable")
        self.insert_var_btn.clicked.connect(self._insert_selected_variable)
        left.addWidget(self.insert_var_btn)
        root.addLayout(left, 2)

        # Right side: Destination, Expression, Keypad + Functions
        right = QVBoxLayout()
        right.addWidget(QLabel("Store result in variable:"))
        self.dest_combo = QComboBox()
        self.dest_combo.setEditable(True)
        for i, col in enumerate(worksheet.columns):
            self.dest_combo.addItem(f"C{i + 1}")
        self.dest_combo.setCurrentText("Calculated")
        right.addWidget(self.dest_combo)

        right.addWidget(QLabel("Expression:"))
        self.expr_edit = QPlainTextEdit()
        self.expr_edit.setPlaceholderText(
            "e.g. IF(C1 > MEAN(C1), 'High', 'Low')  or  ROUND(C1 * 2, 2)"
        )
        self.expr_edit.setMaximumHeight(96)
        right.addWidget(self.expr_edit)

        self.formula_chk = QCheckBox("Assign as a formula (recalculates automatically)")
        right.addWidget(self.formula_chk)

        mid = QHBoxLayout()
        # Keypad
        pad_box = QVBoxLayout()
        pad_box.addWidget(QLabel("Keypad:"))
        pad_grid = QGridLayout()
        keys = [
            ["7", "8", "9", "+", "("],
            ["4", "5", "6", "-", ")"],
            ["1", "2", "3", "*", "="],
            ["0", ".", " ", "/", "^"],
        ]
        for r, row in enumerate(keys):
            for c, ch in enumerate(row):
                lbl = "Space" if ch == " " else ("==" if ch == "=" else ch)
                ins = " " if ch == " " else (" == " if ch == "=" else (f" {ch} " if ch in "+-*/^" else ch))
                btn = QPushButton(lbl)
                btn.setMinimumWidth(42)
                btn.clicked.connect(lambda _=False, txt=ins: self._insert_text(txt))
                pad_grid.addWidget(btn, r, c)
        pad_box.addLayout(pad_grid)
        pad_box.addStretch(1)
        mid.addLayout(pad_box)

        # Functions browser
        func_box = QVBoxLayout()
        func_box.addWidget(QLabel("Functions:"))
        self.cat_combo = QComboBox()
        self.cat_combo.addItems(list(FUNCTION_CATEGORIES.keys()))
        self.cat_combo.currentTextChanged.connect(self._populate_functions)
        func_box.addWidget(self.cat_combo)
        self.func_list = QListWidget()
        self.func_list.itemDoubleClicked.connect(
            lambda item: self._insert_text(item.data(Qt.ItemDataRole.UserRole), inside_parens=True)
        )
        func_box.addWidget(self.func_list, 1)
        self.insert_func_btn = QPushButton("Insert Function")
        self.insert_func_btn.clicked.connect(self._insert_selected_function)
        func_box.addWidget(self.insert_func_btn)
        mid.addLayout(func_box, 1)
        right.addLayout(mid, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        right.addWidget(btns)
        root.addLayout(right, 4)

        self._populate_functions(self.cat_combo.currentText())

        saved = load_dialog_state(worksheet, self._STATE_KEY)
        if isinstance(saved, dict):
            if saved.get("expression"):
                self.expr_edit.setPlainText(saved["expression"])
            if saved.get("destination"):
                self.dest_combo.setCurrentText(saved["destination"])
            self.formula_chk.setChecked(bool(saved.get("assign_formula", False)))

    def _populate_functions(self, category: str):
        self.func_list.clear()
        for label, template in FUNCTION_CATEGORIES.get(category, ()):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, template)
            self.func_list.addItem(item)

    def _insert_text(self, text: str, inside_parens: bool = False):
        cursor = self.expr_edit.textCursor()
        cursor.insertText(text)
        if inside_parens and "(" in text:
            pos = cursor.position() - len(text) + text.index("(") + 1
            cursor.setPosition(pos)
        self.expr_edit.setTextCursor(cursor)
        self.expr_edit.setFocus()

    def _insert_selected_variable(self):
        item = self.var_list.currentItem()
        if item is not None:
            self._insert_text(item.data(Qt.ItemDataRole.UserRole))

    def _insert_selected_function(self):
        item = self.func_list.currentItem()
        if item is not None:
            self._insert_text(item.data(Qt.ItemDataRole.UserRole), inside_parens=True)

    def _on_accept(self):
        save_dialog_state(
            self.worksheet,
            self._STATE_KEY,
            {
                "expression": self.expr_edit.toPlainText(),
                "destination": self.dest_combo.currentText(),
                "assign_formula": self.formula_chk.isChecked(),
            },
        )
        self.accept()

    def get_parameters(self) -> dict:
        return {
            "expression": self.expr_edit.toPlainText().strip(),
            "destination": self.dest_combo.currentText().strip(),
            "assign_formula": self.formula_chk.isChecked(),
        }
