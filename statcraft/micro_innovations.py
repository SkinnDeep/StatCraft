"""Workflow-speed micro-innovations for StatCraft's Qt desktop workspace."""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (
    QObject,
    QRunnable,
    QStringListModel,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


# ---------------------------------------------------------------------------
# 1. Zero-Recompute Column-Dirty Conditional Formatting Cache
# ---------------------------------------------------------------------------
class ConditionalFormatCache:
    """Memoizes per-column conditional formatting highlights across grid refreshes."""

    def __init__(self) -> None:
        self._cache: dict[int, tuple[tuple[Any, ...], dict[str, str]]] = {}

    def invalidate(self, column: Any | None = None) -> None:
        if column is None:
            self._cache.clear()
        else:
            self._cache.pop(id(column), None)

    def get_highlights(self, column: Any, row_count: int) -> dict[str, str]:
        rules = column.metadata.get("conditional_rules")
        if not rules:
            self._cache.pop(id(column), None)
            return {}
        sig = (
            len(column.values),
            tuple(column.values),
            column.kind,
            int(row_count),
            json.dumps(rules, sort_keys=True, default=str),
        )
        cached = self._cache.get(id(column))
        if cached is not None and cached[0] == sig:
            return cached[1]
        from .conditional_formatting import effective_highlights

        result = effective_highlights(column, row_count)
        self._cache[id(column)] = (sig, result)
        return result


# ---------------------------------------------------------------------------
# 2. Command-Line (`Ctrl+M`) Autocomplete & Signature Hint Strip
# ---------------------------------------------------------------------------
COMMAND_SIGNATURES: dict[str, str] = {
    "DESCRIBE": "DESCRIBE C1 [C2 ...] — Descriptive statistics",
    "INFO": "INFO — Worksheet column summary",
    "CORRELATION": "CORRELATION C1 C2 [...] — Pearson correlation matrix",
    "NORMALITY": "NORMALITY C1 — Anderson-Darling normality test",
    "LET": "LET C2 = expression — Column formula / arithmetic",
    "NAME": "NAME C1 'NewName' — Rename worksheet column",
    "ERASE": "ERASE C1 [C2 ...] — Erase column contents",
    "SET": "SET C1 — Enter patterned or literal values",
    "HISTOGRAM": "HISTOGRAM C1 — Histogram with summary",
    "BOXPLOT": "BOXPLOT C1 [* GroupCol] — Boxplot",
    "PLOT": "PLOT Y * X — Scatter plot",
    "REGRESS": "REGRESS Y X1 [X2 ...] — Linear regression",
    "ONEWAY": "ONEWAY Y Group — One-way ANOVA",
    "TTEST": "TTEST mu C1 — One-sample t-test",
    "TWOSAMPLE": "TWOSAMPLE C1 C2 — Two-sample t-test",
    "XBARCHART": "XBARCHART C1 subgroup_size — Xbar-R control chart",
    "IMR": "IMR C1 — Individuals & Moving Range chart",
    "CAPABILITY": "CAPABILITY C1 subgroup; LSL l; USL u. — Process capability",
    "TALLY": "TALLY C1 — Frequency table for discrete/text column",
    "INDICATOR": "INDICATOR C1 — Create binary indicator columns",
    "SUBSET": "SUBSET C1 ... — Subset worksheet",
    "RANDOM": "RANDOM n C1; NORMAL mean sd. — Generate random data",
    "SORT": "SORT C1 ... — Sort columns",
    "RANK": "RANK C1 C2 — Store ranks of C1 into C2",
    "CCF": "CCF C1 C2 — Cross-correlation function",
    "BOOTSTRAP": "BOOTSTRAP C1 — Bootstrap confidence interval",
    "RANDTEST": "RANDTEST C1 C2 — Randomization permutation test",
    "PGOF": "PGOF C1 — Poisson goodness-of-fit test",
    "NBREG": "NBREG Y X1 ... — Negative binomial regression",
    "BANOVA": "BANOVA Y = A B — Balanced ANOVA",
    "NESTED": "NESTED Y = A B(A) — Fully nested ANOVA",
    "MANOVA": "MANOVA Y1 Y2 = Factor — One-way MANOVA",
    "REML": "REML Y = Fixed | Random — Mixed effects model",
    "COXPH": "COXPH Time Censor X1 ... — Cox proportional hazards",
    "SIXSIGMA": "SIXSIGMA C1; LSL l; USL u; SUBGROUP n. — Six Sigma report",
    "RANDOMFOREST": "RANDOMFOREST Y X1 ... — Random forest model",
    "TREENET": "TREENET Y X1 ... — Gradient boosting model",
    "MARS": "MARS Y X1 ... — Multivariate adaptive regression splines",
    "BESTMODEL": "BESTMODEL Y X1 ... — AutoML model leaderboard",
    "MONTECARLO": "MONTECARLO — Monte Carlo process simulation",
}


class CommandLineAssistant(QObject):
    """Attaches verb + column autocomplete and live syntax hints to command_editor."""

    def __init__(self, editor: Any, hint_label: QLabel, get_worksheet: Callable[[], Any]) -> None:
        super().__init__(editor)
        self.editor = editor
        self.hint_label = hint_label
        self.get_worksheet = get_worksheet
        self._model = QStringListModel(sorted(COMMAND_SIGNATURES.keys()), self)
        self._completer: QCompleter | None = None
        editor.textChanged.connect(self._on_text_changed)
        editor.installEventFilter(self)

    @property
    def completer(self) -> QCompleter:
        if self._completer is None:
            comp = QCompleter(self._model, self)
            comp.setWidget(self.editor)
            comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.activated.connect(self._insert_completion)
            self._completer = comp
        return self._completer

    def refresh_tokens(self) -> list[str]:
        tokens = list(sorted(COMMAND_SIGNATURES.keys()))
        sheet = self.get_worksheet()
        if sheet is not None:
            for idx, col in enumerate(getattr(sheet, "columns", [])):
                tokens.append(f"C{idx + 1}")
                if col.name and col.name != f"C{idx + 1}":
                    safe = col.name.replace("'", "\\'")
                    tokens.append(f"'{safe}'")
        self._model.setStringList(tokens)
        return tokens

    def current_word_prefix(self) -> str:
        cursor = self.editor.textCursor()
        block_text = cursor.block().text()
        pos = cursor.positionInBlock()
        left = block_text[:pos]
        parts = left.replace(";", " ").split()
        if not left or left[-1].isspace():
            return ""
        return parts[-1] if parts else ""

    def _on_text_changed(self) -> None:
        text = self.editor.toPlainText().strip()
        first_verb = text.split()[0].upper() if text.split() else ""
        hint = COMMAND_SIGNATURES.get(first_verb, "Tip: Tab/Enter accepts completion • ';' adds subcommands")
        self.hint_label.setText(hint)

        prefix = self.current_word_prefix()
        if len(prefix) < 2:
            self.completer.popup().hide()
            return
        self.refresh_tokens()
        self.completer.setCompletionPrefix(prefix)
        popup = self.completer.popup()
        if self.completer.completionCount() == 0:
            popup.hide()
            return
        cr = self.editor.cursorRect()
        cr.setWidth(max(240, popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width()))
        self.completer.complete(cr)

    def _insert_completion(self, completion: str) -> None:
        cursor = self.editor.textCursor()
        prefix = self.current_word_prefix()
        if prefix:
            cursor.movePosition(cursor.MoveOperation.Left, cursor.MoveMode.KeepAnchor, len(prefix))
        cursor.insertText(completion + " ")
        self.editor.setTextCursor(cursor)

    def eventFilter(self, obj: QObject, event: Any) -> bool:
        if obj is self.editor and self._completer is not None and event.type() == event.Type.KeyPress:
            popup = self._completer.popup()
            if popup.isVisible() and event.key() in (
                Qt.Key.Key_Enter,
                Qt.Key.Key_Return,
                Qt.Key.Key_Tab,
            ):
                idx = popup.currentIndex()
                if idx.isValid():
                    self._insert_completion(idx.data())
                    popup.hide()
                    return True
        return super().eventFilter(obj, event)


# ---------------------------------------------------------------------------
# 3. MRU Column Tracker & Pinned Procedures Manager
# ---------------------------------------------------------------------------
class MRUColumnTracker:
    """Tracks most recently used column names/references for quick dialog insertion."""

    def __init__(self, max_items: int = 6) -> None:
        self.max_items = max_items
        self._recent: list[str] = []

    def record(self, refs: list[str] | tuple[str, ...]) -> None:
        for ref in refs:
            clean = str(ref).strip()
            if not clean:
                continue
            if clean in self._recent:
                self._recent.remove(clean)
            self._recent.insert(0, clean)
        self._recent = self._recent[: self.max_items]

    def items(self, limit: int = 3) -> list[str]:
        return self._recent[:limit]


_GLOBAL_MRU_COLUMNS = MRUColumnTracker()


def global_mru_columns() -> MRUColumnTracker:
    return _GLOBAL_MRU_COLUMNS


class PinnedProceduresManager:
    """Stores pinned toolbar analysis procedures for 1-click replay."""

    def __init__(self, max_items: int = 8) -> None:
        self.max_items = max_items
        self._items: list[tuple[str, Callable[[], Any]]] = []

    def pin(self, label: str, callback: Callable[[], Any]) -> None:
        self._items = [(l, cb) for (l, cb) in self._items if l != label]
        self._items.insert(0, (label, callback))
        self._items = self._items[: self.max_items]

    def unpin(self, label: str) -> None:
        self._items = [(l, cb) for (l, cb) in self._items if l != label]

    def list_items(self) -> list[tuple[str, Callable[[], Any]]]:
        return list(self._items)


# ---------------------------------------------------------------------------
# 4. Live Dependency Stale Tracker & Output Banner
# ---------------------------------------------------------------------------
class SheetVersionTracker:
    """Monotonic per-worksheet revision counter to detect stale output reports."""

    def __init__(self) -> None:
        self._versions: dict[int, int] = {}

    def version(self, sheet: Any) -> int:
        if sheet is None:
            return 0
        return self._versions.get(id(sheet), 0)

    def bump(self, sheet: Any) -> int:
        if sheet is None:
            return 0
        nxt = self._versions.get(id(sheet), 0) + 1
        self._versions[id(sheet)] = nxt
        return nxt


class StaleOutputBanner(QFrame):
    """Non-intrusive banner shown on output reports when upstream worksheet data changed."""

    rerunRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("staleOutputBanner")
        self.setStyleSheet(
            "QFrame#staleOutputBanner { background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 5px; }"
            "QLabel { color: #92400e; font-size: 8.5pt; font-weight: 600; background: transparent; }"
            "QPushButton { background-color: #d97706; color: white; border: none; border-radius: 4px; padding: 3px 10px; font-weight: 600; font-size: 8.5pt; }"
            "QPushButton:hover { background-color: #b45309; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 5, 10, 5)
        row.setSpacing(8)
        self.msg_label = QLabel("Worksheet data changed since this analysis ran.")
        row.addWidget(self.msg_label, 1)
        self.rerun_btn = QPushButton("Update / Re-run")
        self.rerun_btn.clicked.connect(self.rerunRequested.emit)
        row.addWidget(self.rerun_btn)


# ---------------------------------------------------------------------------
# 5. Non-Blocking QThreadPool Compute Queue + Toast Progress
# ---------------------------------------------------------------------------
class _ComputeSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _ComputeTask(QRunnable):
    def __init__(self, fn: Callable[[], Any]) -> None:
        super().__init__()
        self.fn = fn
        self.signals = _ComputeSignals()
        self.cancelled = False

    def run(self) -> None:
        if self.cancelled:
            return
        try:
            res = self.fn()
            if not self.cancelled:
                self.signals.finished.emit(res)
        except Exception as exc:
            if not self.cancelled:
                self.signals.failed.emit(str(exc))


class ComputeProgressToast(QFrame):
    """Compact floating progress pill shown during async background computations."""

    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("computeProgressToast")
        self.setStyleSheet(
            "QFrame#computeProgressToast { background-color: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; }"
            "QLabel { color: #f8fafc; font-size: 8.5pt; font-weight: 600; background: transparent; }"
            "QToolButton { color: #fca5a5; border: none; font-weight: 700; padding: 2px 6px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 5, 8, 5)
        row.setSpacing(8)
        self.label = QLabel("Running analysis…")
        row.addWidget(self.label)
        self.cancel_btn = QToolButton()
        self.cancel_btn.setText("Cancel")
        self.cancel_btn.clicked.connect(self.cancelRequested.emit)
        row.addWidget(self.cancel_btn)
        self.hide()


class BackgroundComputeManager(QObject):
    """Dispatches heavy analyses onto QThreadPool without freezing the UI thread."""

    def __init__(self, toast: ComputeProgressToast, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.toast = toast
        self.pool = QThreadPool.globalInstance()
        self._active_task: _ComputeTask | None = None
        self.toast.cancelRequested.connect(self.cancel_active)

    def cancel_active(self) -> None:
        if self._active_task is not None:
            self._active_task.cancelled = True
            self._active_task = None
        self.toast.hide()

    def submit(
        self,
        title: str,
        fn: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self.cancel_active()
        task = _ComputeTask(fn)
        self._active_task = task
        self.toast.label.setText(f"⏳ {title}…")
        self.toast.show()

        def _done(res: Any) -> None:
            if self._active_task is task:
                self._active_task = None
                self.toast.hide()
            on_success(res)

        def _err(msg: str) -> None:
            if self._active_task is task:
                self._active_task = None
                self.toast.hide()
            if on_error:
                on_error(msg)

        task.signals.finished.connect(_done)
        task.signals.failed.connect(_err)
        self.pool.start(task)


# ---------------------------------------------------------------------------
# 6. Floating Quick-Bar on Every Chart
# ---------------------------------------------------------------------------
def build_chart_quick_bar(graph_frame: Any, chart: Any, entry: dict[str, Any], window: Any) -> QWidget:
    """Compact header quick-bar for Grid, Log Y, CI/PI toggles, and 1-click SVG/PNG copy."""
    bar = QWidget(graph_frame)
    bar.setObjectName("chartQuickBar")
    row = QHBoxLayout(bar)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(3)

    def _mk_btn(text: str, tip: str, checkable: bool = False) -> QToolButton:
        b = QToolButton(bar)
        b.setText(text)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setStyleSheet(
            "QToolButton { font-size: 7.8pt; padding: 2px 6px; border: 1px solid #cbd5e1; border-radius: 3px; }"
            "QToolButton:checked { background-color: #0284c7; color: white; border-color: #0369a1; }"
        )
        return b

    grid_btn = _mk_btn("Grid", "Toggle chart gridlines", checkable=True)
    grid_btn.setChecked(True)

    def _toggle_grid(checked: bool) -> None:
        fig = getattr(chart, "figure", None)
        if fig is None:
            return
        for ax in fig.get_axes():
            ax.grid(checked, alpha=0.25 if checked else 0.0)
        if hasattr(chart, "canvas"):
            chart.canvas.draw_idle()

    grid_btn.toggled.connect(_toggle_grid)
    row.addWidget(grid_btn)

    log_btn = _mk_btn("Log Y", "Toggle logarithmic Y axis", checkable=True)

    def _toggle_log_y(checked: bool) -> None:
        fig = getattr(chart, "figure", None)
        if fig is None:
            return
        for ax in fig.get_axes():
            try:
                ax.set_yscale("log" if checked else "linear")
            except Exception:
                pass
        if hasattr(chart, "canvas"):
            chart.canvas.draw_idle()

    log_btn.toggled.connect(_toggle_log_y)
    row.addWidget(log_btn)

    # Show CI / PI quick toggles when the chart has fitted-line/regression bands
    meta = entry.get("result", {}) if isinstance(entry, dict) else {}
    raw_graphs = meta.get("graphs", []) if isinstance(meta, dict) else []
    if isinstance(raw_graphs, dict):
        g0 = raw_graphs
    elif isinstance(raw_graphs, (list, tuple)) and raw_graphs and isinstance(raw_graphs[0], dict):
        g0 = raw_graphs[0]
    else:
        g0 = {}
    bands = g0.get("bands") or g0.get("fitted_bands")
    if isinstance(bands, dict) or "Fitted Line" in str(entry.get("title", "")):
        for band_key, label_txt in (("show_ci", "CI"), ("show_pi", "PI")):
            b_btn = _mk_btn(label_txt, f"Toggle 95% {label_txt} band", checkable=True)
            b_btn.setChecked(bool(g0.get(band_key, True)))

            def _toggle_band(checked: bool, k: str = band_key) -> None:
                if isinstance(g0, dict):
                    g0[k] = checked
                if hasattr(chart, "render"):
                    try:
                        chart.render()
                    except Exception:
                        pass

            b_btn.toggled.connect(_toggle_band)
            row.addWidget(b_btn)

    svg_btn = _mk_btn("SVG", "Copy chart as SVG")
    svg_btn.clicked.connect(lambda: getattr(window, "copy_chart_svg", lambda *_: None)())
    row.addWidget(svg_btn)

    png_btn = _mk_btn("PNG", "Copy chart image to clipboard")

    def _copy_png() -> None:
        canvas = getattr(chart, "canvas", None)
        if canvas is not None:
            QApplication.clipboard().setPixmap(canvas.grab())
            if hasattr(window, "statusBar"):
                window.statusBar().showMessage("Copied chart PNG to clipboard.", 3500)

    png_btn.clicked.connect(_copy_png)
    row.addWidget(png_btn)

    graph_frame.export_hidden.append(bar)
    return bar


# ---------------------------------------------------------------------------
# 7. Zero-Dialog Clipboard Paste Strip
# ---------------------------------------------------------------------------
class PasteToastBar(QFrame):
    """Inline dismissible toast shown after multi-cell clipboard pastes."""

    promoteHeadersRequested = Signal()
    undoRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pasteToastBar")
        self.setStyleSheet(
            "QFrame#pasteToastBar { background-color: #eff6ff; border-top: 1px solid #bfdbfe; padding: 2px 8px; }"
            "QLabel { color: #1e3a8a; font-size: 8.5pt; font-weight: 600; background: transparent; }"
            "QPushButton { background-color: #ffffff; border: 1px solid #93c5fd; border-radius: 3px; padding: 2px 8px; font-size: 8pt; color: #1e40af; }"
            "QPushButton:hover { background-color: #dbeafe; }"
            "QToolButton { border: none; color: #1e3a8a; font-weight: bold; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(8)
        self.info_label = QLabel("")
        row.addWidget(self.info_label, 1)
        self.header_btn = QPushButton("Treat 1st Row as Headers")
        self.header_btn.clicked.connect(self.promoteHeadersRequested.emit)
        row.addWidget(self.header_btn)
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.clicked.connect(self.undoRequested.emit)
        row.addWidget(self.undo_btn)
        self.close_btn = QToolButton()
        self.close_btn.setText("×")
        self.close_btn.clicked.connect(self.hide)
        row.addWidget(self.close_btn)
        self.hide()
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.timeout.connect(self.hide)

    def show_paste(self, rows: int, cols: int, allow_header_promote: bool = True) -> None:
        self.info_label.setText(f"Pasted {rows} row{'s' if rows != 1 else ''} × {cols} col{'s' if cols != 1 else ''}")
        self.header_btn.setVisible(allow_header_promote and rows >= 2)
        self.show()
        self._auto_timer.start(12000)


# ---------------------------------------------------------------------------
# 8. Excel-Style Formula Bar + Enhanced Live Selection Summary
# ---------------------------------------------------------------------------
class FormulaBarWidget(QFrame):
    """Slim formula/value bar above the worksheet header showing active cell or column formula."""

    commitValue = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("formulaBarWidget")
        self.setFixedHeight(26)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 2, 6, 2)
        row.setSpacing(6)
        self.addr_label = QLabel("C1 [R1]")
        self.addr_label.setFixedWidth(78)
        self.addr_label.setStyleSheet("font-weight: 700; font-size: 8.5pt;")
        row.addWidget(self.addr_label)
        fx = QLabel("fx")
        fx.setStyleSheet("font-style: italic; font-weight: 700; color: #0284c7; font-size: 9pt;")
        row.addWidget(fx)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Cell value or '= formula' for column…")
        self.input.setFrame(False)
        self.input.returnPressed.connect(lambda: self.commitValue.emit(self.input.text()))
        row.addWidget(self.input, 1)

    def sync(self, col_idx: int, row_idx: int, col_name: str, value_text: str, formula: str | None = None) -> None:
        addr = f"C{col_idx + 1} [R{row_idx + 1}]"
        self.addr_label.setText(addr)
        self.addr_label.setToolTip(f"{col_name or addr} (row {row_idx + 1})")
        if formula:
            self.input.setText(f"= {formula}")
        else:
            self.input.setText(value_text)


def format_selection_summary(
    numeric_vals: list[float],
    nonempty_count: int,
    missing_count: int = 0,
    first_nonempty: str | None = None,
) -> str:
    """Builds concise live selection statistics for the status bar."""
    if len(numeric_vals) >= 2:
        s_sum = sum(numeric_vals)
        s_mean = s_sum / len(numeric_vals)
        s_sd = statistics.stdev(numeric_vals)
        s_min = min(numeric_vals)
        s_max = max(numeric_vals)
        total_cnt = max(len(numeric_vals), nonempty_count)
        miss_part = f" | Missing: {missing_count}" if missing_count > 0 else ""
        return (
            f"Count: {total_cnt}{miss_part} | Sum: {s_sum:g} | Mean: {s_mean:g} | SD: {s_sd:g} "
            f"| Min: {s_min:g} | Max: {s_max:g}"
        )
    if len(numeric_vals) == 1:
        return f"Count: {max(1, nonempty_count)} | Value: {numeric_vals[0]:g}"
    if nonempty_count == 1:
        return f"Count: 1 | Value: {first_nonempty}"
    if nonempty_count >= 2:
        miss_part = f" | Missing: {missing_count}" if missing_count > 0 else ""
        return f"Count: {nonempty_count}{miss_part}"
    return ""


# ---------------------------------------------------------------------------
# 9. Column Header Filter / Search Popover
# ---------------------------------------------------------------------------
class ColumnFilterPopover(QDialog):
    """Compact column filter, quick-sort, outlier highlight, and subset-to-sheet popover."""

    def __init__(self, column: Any, col_index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.column = column
        self.col_index = col_index
        self.chosen_action: str | None = None
        self.selected_values: set[str] = set()
        self.setWindowTitle(f"Filter & Sort — C{col_index + 1}: {column.name}")
        self.resize(320, 390)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        sort_row = QHBoxLayout()
        btn_asc = QPushButton("Sort A→Z / Low→High")
        btn_desc = QPushButton("Sort Z→A / High→Low")
        btn_asc.clicked.connect(lambda: self._finish("sort_asc"))
        btn_desc.clicked.connect(lambda: self._finish("sort_desc"))
        sort_row.addWidget(btn_asc)
        sort_row.addWidget(btn_desc)
        layout.addLayout(sort_row)

        if column.kind == "number":
            btn_out = QPushButton("Highlight Outliers (> 3 SD)")
            btn_out.clicked.connect(lambda: self._finish("highlight_outliers"))
            layout.addWidget(btn_out)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter distinct values…")
        self.search_box.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_box)

        self.list_widget = QListWidget()
        seen: list[str] = []
        seen_set: set[str] = set()
        for v in column.values:
            txt = "*" if v is None else str(v)
            if txt not in seen_set:
                seen_set.add(txt)
                seen.append(txt)
            if len(seen) >= 200:
                break
        for txt in seen:
            item = QListWidgetItem(txt)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        sel_row = QHBoxLayout()
        all_btn = QPushButton("All")
        none_btn = QPushButton("None")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        sel_row.addWidget(all_btn)
        sel_row.addWidget(none_btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        subset_btn = QPushButton("Subset Matching Rows to New Worksheet")
        subset_btn.clicked.connect(lambda: self._finish("subset"))
        layout.addWidget(subset_btn)

    def _filter_list(self, query: str) -> None:
        q = query.strip().lower()
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            it.setHidden(bool(q) and q not in it.text().lower())

    def _set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if not it.isHidden():
                it.setCheckState(state)

    def _finish(self, action: str) -> None:
        self.chosen_action = action
        self.selected_values = {
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        }
        self.accept()


# ---------------------------------------------------------------------------
# 10. 1-Click Multi-Chart Report Packager (Executive Slide Deck)
# ---------------------------------------------------------------------------
def build_executive_pptx(entries: list[dict[str, Any]], out_path: str | Path) -> Path:
    """Generates a PowerPoint deck using python-pptx when available or StatCraft's OOXML exporter."""
    import io

    def _entry_summary(entry: dict[str, Any]) -> str:
        result = entry.get("result", {}) if isinstance(entry, dict) else {}
        tables = result.get("tables", []) if isinstance(result, dict) else []
        text = str(result.get("text", "")).strip()
        if tables and isinstance(tables[0], dict):
            t0 = tables[0]
            headers = [str(h) for h in t0.get("headers", [])]
            rows = t0.get("rows", [])[:12]
            lines = [" | ".join(headers)] if headers else []
            for r in rows:
                lines.append(" | ".join(str(c) for c in r))
            return "\n".join(lines)
        return "\n".join(text.splitlines()[:18])

    def _entry_png(entry: dict[str, Any]) -> bytes:
        result = entry.get("result", {}) if isinstance(entry, dict) else {}
        graphs = result.get("graphs", []) if isinstance(result, dict) else []
        if not graphs:
            return b""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return b""
        fig, ax = plt.subplots(figsize=(6.0, 4.4), dpi=140)
        g0 = graphs[0] if isinstance(graphs[0], dict) else {}
        plotted = False
        for s in g0.get("series", []):
            if isinstance(s, dict) and s.get("x") and s.get("y"):
                ax.plot(s["x"], s["y"], marker="o" if len(s["x"]) <= 40 else None, label=s.get("name"))
                plotted = True
        if not plotted and isinstance(g0.get("bars"), dict):
            b = g0["bars"]
            ax.bar(b.get("labels", []), b.get("values", []))
        ax.set_title(str(g0.get("title", entry.get("title", ""))))
        ax.grid(True, alpha=0.25)
        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)
        return buf.getvalue()

    target = Path(out_path)
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]
        for entry in entries:
            slide = prs.slides.add_slide(blank_layout)
            title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12.3), Inches(0.6))
            p = title_box.text_frame.paragraphs[0]
            p.text = str(entry.get("title", "Analysis Result"))
            p.font.size = Pt(22)
            p.font.bold = True
            left_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.05), Inches(5.7), Inches(5.9))
            left_box.text_frame.word_wrap = True
            lp = left_box.text_frame.paragraphs[0]
            lp.text = _entry_summary(entry) or "(No text summary)"
            lp.font.size = Pt(11)
            png_bytes = _entry_png(entry)
            if png_bytes:
                slide.shapes.add_picture(io.BytesIO(png_bytes), Inches(6.45), Inches(1.1), width=Inches(6.35))
        prs.save(str(target))
        return target
    except ImportError:
        from .office_export import OfficeSnapshot, export_pptx
        sections = []
        first_png = b""
        for entry in entries:
            title = str(entry.get("title", "Analysis Result"))
            summary = _entry_summary(entry) or "(No text summary)"
            sections.append(f"=== {title} ===\n{summary}")
            if not first_png:
                first_png = _entry_png(entry)
        snapshot = OfficeSnapshot(
            title=f"StatCraft Executive Deck ({len(entries)} analyses)",
            report="\n\n".join(sections),
            png=first_png,
        )
        export_pptx(target, snapshot)
        return target


class ExecutiveSlideDeckDialog(QDialog):
    """Lets users pick output history items and export a combined PowerPoint deck."""

    def __init__(self, history: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history = history
        self.setWindowTitle("Export Executive Slide Deck (PowerPoint)")
        self.resize(440, 380)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select analyses to include in your PowerPoint deck:"))
        self.list_widget = QListWidget()
        for entry in history:
            item = QListWidgetItem(str(entry.get("title", "Result")))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_entries(self) -> list[dict[str, Any]]:
        return [
            self.history[i]
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]
