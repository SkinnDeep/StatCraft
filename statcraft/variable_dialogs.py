from .dialog_theme import (
    dialog_stylesheet,
    gallery_button_stylesheet,
    is_dark_active as _is_dark_active,
    subtle_label_style,
)

"""Original worksheet-variable selectors with explicit roles and column identities."""
import re
import shlex
import json
from PySide6.QtCore import Qt, QSize, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QDialogButtonBox, QAbstractItemView, QComboBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QToolButton, QGridLayout, QButtonGroup)
from .model import finite_number


_REFERENCE = re.compile(r'[cC]([1-9][0-9]*)(?:-([tTdD]))?')
_RANGE_RE = re.compile(r'^[cC]([1-9][0-9]*)\s*[-–]\s*[cC]([1-9][0-9]*)$')
_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[^\s\'\"]+')


def format_variable_reference(index, worksheet):
    """Readable positional identity; the quoted label never selects by name."""
    column = worksheet.columns[index]
    address = 'C'+str(index+1)+('-T' if column.kind=='text' else '-D' if column.kind=='date' else '')
    return address+': '+json.dumps(column.name,ensure_ascii=False)


def format_variable_list(indices, worksheet):
    return ' '.join(format_variable_reference(index,worksheet) for index in indices)


def _variable_tokens(text):
    tokens=[]; end=0
    for match in _TOKENS.finditer(text):
        if text[end:match.start()].strip() or end and match.start()==end:
            raise ValueError('Separate variables with spaces and close quoted column names.')
        raw=match.group(); quoted=raw[0] in ('"',"'")
        if quoted:
            try: token=json.loads(raw) if raw[0]=='"' else shlex.split(raw)[0]
            except (ValueError,IndexError) as exc: raise ValueError('Close quoted column names, or use C1, C2, …') from exc
        else: token=raw
        tokens.append((token,quoted)); end=match.end()
    if text[end:].strip(): raise ValueError('Close quoted column names, or use C1, C2, …')
    return tokens


def _require_eligible_column(worksheet, index: int, token: str, kinds) -> None:
    if index < 0 or index >= len(worksheet.columns):
        raise ValueError('Unknown column: ' + token)
    col = worksheet.columns[index]
    if col.kind not in kinds:
        expected = '/'.join('numeric' if k == 'number' else str(k) for k in kinds)
        raise ValueError(
            f"Column C{index + 1} ('{col.name}') is not eligible for this field ({col.kind} given; requires {expected} columns)."
        )


def resolve_variables(text, worksheet, kinds=('number',)):
    tokens=_variable_tokens(text)
    indices=[]
    position=0
    while position<len(tokens):
        token,quoted=tokens[position]; position+=1
        if not quoted:
            m_range = _RANGE_RE.match(token)
            if not m_range and _REFERENCE.fullmatch(token) and position + 1 < len(tokens):
                if tokens[position][0] in ('-', '–') and not tokens[position][1]:
                    m_next = _REFERENCE.fullmatch(tokens[position + 1][0]) if not tokens[position + 1][1] else None
                    if m_next:
                        m_start = _REFERENCE.fullmatch(token)
                        start = int(m_start.group(1)) - 1
                        end = int(m_next.group(1)) - 1
                        position += 2
                        step = 1 if end >= start else -1
                        for idx in range(start, end + step, step):
                            _require_eligible_column(worksheet, idx, f"C{idx+1}", kinds)
                            if idx not in indices:
                                indices.append(idx)
                        continue
            if m_range:
                start = int(m_range.group(1)) - 1
                end = int(m_range.group(2)) - 1
                step = 1 if end >= start else -1
                for idx in range(start, end + step, step):
                    _require_eligible_column(worksheet, idx, f"C{idx+1}", kinds)
                    if idx not in indices:
                        indices.append(idx)
                continue
        decorated=not quoted and token.endswith(':')
        reference=_REFERENCE.fullmatch(token[:-1] if decorated else token) if not quoted else None
        if decorated:
            if reference is None or position>=len(tokens) or not tokens[position][1]:
                raise ValueError('A column reference with a colon must include its quoted header name.')
            position+=1
        if reference:
            index=int(reference.group(1))-1
        else:
            matches=[i for i,c in enumerate(worksheet.columns) if c.name==token]
            if len(matches)!=1: raise ValueError('Unknown or ambiguous column: '+token+'. Use its C number.')
            index=matches[0]
        _require_eligible_column(worksheet, index, token, kinds)
        if reference and reference.group(2) and worksheet.columns[index].kind != {'t':'text','d':'date'}[reference.group(2).lower()]:
            raise ValueError('The column type does not match its address: '+token)
        if index in indices: raise ValueError('A variable is selected more than once: '+token)
        indices.append(index)
    return indices


class _AutoErrorLabel(QLabel):
    """QLabel that automatically toggles visibility when non-empty error text is set."""
    def setText(self, text):
        super().setText(text)
        self.setVisible(bool(str(text or "").strip()))


class VariableEntry(QLineEdit):
    def __init__(self, focus_callback, parent=None):
        super().__init__(parent); self.focus_callback=focus_callback
    def focusInEvent(self,event):
        super().focusInEvent(event); self.focus_callback()
        self.selectAll()


class ProcedureDialog(QDialog):
    _LAST_DIALOG_STATE = {}
    def __init__(self,parent,title,worksheet,selectors=(),fields=(),note=''):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(680, 440)
        self.resize(720, 480)
        self.setSizeGripEnabled(True)
        self.worksheet=worksheet; self.selectors=list(selectors); self.fields=list(fields)
        self.controls={}; self.parameters=None; self.active_key=None
        dark = _is_dark_active(parent or self)
        if dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #18181b;
                    color: #f4f4f5;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QLabel {
                    color: #f4f4f5;
                    font-size: 9pt;
                }
                QLabel#secondary {
                    color: #a1a1aa;
                    font-size: 8.5pt;
                    padding-bottom: 4px;
                }
                QLabel#error {
                    color: #f87171;
                    background-color: #450a0a;
                    border: 1px solid #7f1d1d;
                    border-radius: 4px;
                    padding: 6px 10px;
                    font-size: 8.5pt;
                    font-weight: 500;
                }
                QListWidget {
                    background-color: #1f1f23;
                    color: #f4f4f5;
                    border: 1px solid #27272a;
                    border-radius: 6px;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                    font-size: 8.5pt;
                    padding: 4px;
                }
                QListWidget::item {
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                QListWidget::item:hover {
                    background-color: #27272a;
                }
                QListWidget::item:selected {
                    background-color: #0284c7;
                    color: #ffffff;
                    font-weight: 600;
                }
                QLineEdit, QComboBox {
                    background-color: #1f1f23;
                    color: #f4f4f5;
                    border: 1px solid #3f3f46;
                    border-radius: 5px;
                    padding: 5px 8px;
                    font-size: 9pt;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 1.5px solid #38bdf8;
                    background-color: #1f1f23;
                }
                QPushButton {
                    background-color: #27272a;
                    color: #f4f4f5;
                    border: 1px solid #3f3f46;
                    border-radius: 5px;
                    padding: 5px 14px;
                    font-size: 9pt;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #3f3f46;
                    border-color: #71717a;
                }
                QPushButton:pressed {
                    background-color: #18181b;
                }
                QPushButton:disabled {
                    background-color: #18181b;
                    color: #71717a;
                    border-color: #27272a;
                }
                QDialogButtonBox QPushButton {
                    min-width: 72px;
                }
                QDialogButtonBox QPushButton[text="&OK"], QDialogButtonBox QPushButton[text="OK"] {
                    background: #0284c7;
                    color: #ffffff;
                    border: 1px solid #0369a1;
                    font-weight: 600;
                }
                QDialogButtonBox QPushButton[text="&OK"]:hover, QDialogButtonBox QPushButton[text="OK"]:hover {
                    background: #0369a1;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    color: #0f172a;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                }
                QLabel {
                    color: #0f172a;
                    font-size: 9pt;
                }
                QLabel#secondary {
                    color: #475569;
                    font-size: 8.5pt;
                    padding-bottom: 4px;
                }
                QLabel#error {
                    color: #b91c1c;
                    background-color: #fef2f2;
                    border: 1px solid #fca5a5;
                    border-radius: 4px;
                    padding: 6px 10px;
                    font-size: 8.5pt;
                    font-weight: 500;
                }
                QListWidget {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    font-family: 'Segoe UI', -apple-system, sans-serif;
                    font-size: 8.5pt;
                    padding: 4px;
                }
                QListWidget::item {
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                QListWidget::item:hover {
                    background-color: #f1f5f9;
                }
                QListWidget::item:selected {
                    background-color: #e0f2fe;
                    color: #005a9e;
                    font-weight: 600;
                }
                QLineEdit, QComboBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                    padding: 5px 8px;
                    font-size: 9pt;
                }
                QLineEdit:focus, QComboBox:focus {
                    border: 1.5px solid #0078d7;
                    background-color: #ffffff;
                }
                QPushButton {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 5px;
                    padding: 5px 14px;
                    font-size: 9pt;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    border-color: #94a3b8;
                }
                QPushButton:pressed {
                    background-color: #e2e8f0;
                }
                QPushButton:disabled {
                    background-color: #f8fafc;
                    color: #94a3b8;
                    border-color: #e2e8f0;
                }
                QDialogButtonBox QPushButton {
                    min-width: 72px;
                }
                QDialogButtonBox QPushButton[text="&OK"], QDialogButtonBox QPushButton[text="OK"] {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0078d7, stop:1 #005a9e);
                    color: #ffffff;
                    border: 1px solid #005a9e;
                    font-weight: 600;
                }
                QDialogButtonBox QPushButton[text="&OK"]:hover, QDialogButtonBox QPushButton[text="OK"]:hover {
                    background: #005a9e;
                }
            """)
        layout=QVBoxLayout(self)
        if note:
            info=QLabel(note); info.setWordWrap(True); info.setObjectName('secondary'); layout.addWidget(info)
        body=QHBoxLayout(); self.available=QListWidget()
        self.available.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.available.setMinimumWidth(220); self.available.setMinimumHeight(240)
        left=QVBoxLayout(); left.addWidget(QLabel('Available variables'))
        self.var_filter = QLineEdit()
        self.var_filter.setPlaceholderText("Filter variables...")
        self.var_filter.setClearButtonEnabled(True)
        self.var_filter.textChanged.connect(self._filter_available_variables)
        left.addWidget(self.var_filter)
        from .micro_innovations import global_mru_columns
        mru_refs = global_mru_columns().items(3)
        if mru_refs and self.selectors:
            mru_row = QHBoxLayout()
            mru_row.setSpacing(4)
            mru_lbl = QLabel("Recent:")
            mru_lbl.setStyleSheet("font-size: 8pt; color: #64748b;")
            mru_row.addWidget(mru_lbl)
            for ref in mru_refs:
                chip = QPushButton(ref.split(":")[0])
                chip.setAutoDefault(False)
                chip.setToolTip(f"Insert {ref}")
                chip.setStyleSheet("font-size: 7.8pt; padding: 1px 6px;")
                chip.clicked.connect(lambda checked=False, r=ref: self._insert_mru_ref(r))
                mru_row.addWidget(chip)
            mru_row.addStretch()
            left.addLayout(mru_row)
        left.addWidget(self.available)
        self.select_button=QPushButton('Select'); self.select_button.setAutoDefault(False)
        self.select_button.clicked.connect(self.transfer); left.addWidget(self.select_button)
        self.available.itemDoubleClicked.connect(lambda item:self.transfer())
        self.available.itemSelectionChanged.connect(lambda:self.select_button.setEnabled(bool(self.available.selectedItems())))
        if self.selectors: body.addLayout(left,1)
        form=QFormLayout(); form.setVerticalSpacing(14)
        for spec in self.selectors:
            key=spec['key']; entry=VariableEntry(lambda key=key:self.activate(key))
            entry.setPlaceholderText('Select columns, or enter C1 C2' if spec.get('multiple') else 'Select a column, or enter C1')
            self.controls[key]=entry; form.addRow(spec['label'],entry)
        for spec in self.fields:
            if 'choices' in spec:
                control=QComboBox(); control.addItems(spec['choices'])
                if 'default' in spec: control.setCurrentText(str(spec['default']))
            elif spec.get('boolean'):
                control=QCheckBox(spec.get('text','')); control.setChecked(bool(spec.get('default',False)))
            else:
                control=QLineEdit(str(spec.get('default','')))
                control.setPlaceholderText(spec.get('placeholder','Optional' if spec.get('optional') else ''))
            self.controls[spec['key']]=control; form.addRow(spec['label'],control)
        right=QVBoxLayout(); right.addLayout(form); right.addStretch(); body.addLayout(right,2); layout.addLayout(body)
        self.error=_AutoErrorLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True); self.error.setVisible(False); layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Reset)
        reset_btn = buttons.button(QDialogButtonBox.StandardButton.Reset)
        if reset_btn:
            reset_btn.clicked.connect(self.reset_dialog)
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        if self.selectors:
            self.activate(self.selectors[0]['key']); self.controls[self.active_key].setFocus()

        ws_name = getattr(self.worksheet, 'name', '')
        col_sig = tuple((c.name, c.kind) for c in getattr(self.worksheet, 'columns', []))
        state_key = (id(self.worksheet), ws_name, self.windowTitle(), col_sig)
        if state_key in self._LAST_DIALOG_STATE:
            saved = self._LAST_DIALOG_STATE[state_key]
            for k, val in saved.items():
                if k in self.controls:
                    ctrl = self.controls[k]
                    if isinstance(ctrl, QComboBox):
                        ctrl.setCurrentText(str(val))
                    elif isinstance(ctrl, QCheckBox):
                        ctrl.setChecked(bool(val))
                    elif isinstance(ctrl, QLineEdit):
                        ctrl.setText(str(val))
        elif self.selectors:
            selected_cols = sorted(
                i for i in getattr(parent, '_selected_columns', ())
                if isinstance(i, int) and 0 <= i < len(self.worksheet.columns)
            )
            if selected_cols:
                for spec in self.selectors:
                    key = spec['key']
                    ctrl = self.controls.get(key)
                    if ctrl is None or ctrl.text().strip():
                        continue
                    kinds = spec.get('kinds', ('number',))
                    eligible = [i for i in selected_cols if self.worksheet.columns[i].kind in kinds]
                    if eligible:
                        is_multi = bool(spec.get('multiple') or spec.get('multi') or spec.get('maximum', 1) > 1)
                        picked = eligible if is_multi else [eligible[0]]
                        ctrl.setText(' '.join(format_variable_reference(i, self.worksheet) for i in picked))
                        break

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F3:
            self.reset_dialog()
            return
        super().keyPressEvent(event)

    def reset_dialog(self):
        for spec in self.selectors:
            key = spec['key']
            if key in self.controls:
                self.controls[key].clear()
        for spec in self.fields:
            key = spec['key']
            if key in self.controls:
                ctrl = self.controls[key]
                if 'default' in spec:
                    if isinstance(ctrl, QComboBox):
                        ctrl.setCurrentText(str(spec['default']))
                    elif isinstance(ctrl, QLineEdit):
                        ctrl.setText(str(spec['default']))
                    elif isinstance(ctrl, QCheckBox):
                        ctrl.setChecked(bool(spec.get('default', False)))
                else:
                    if isinstance(ctrl, (QLineEdit,)):
                        ctrl.clear()
                    elif isinstance(ctrl, QCheckBox):
                        ctrl.setChecked(False)
        if hasattr(self, 'error'):
            self.error.setVisible(False)
        if self.selectors:
            self.activate(self.selectors[0]['key'])
            self.controls[self.active_key].setFocus()

    def _filter_available_variables(self, text):
        query = text.strip().lower()
        for i in range(self.available.count()):
            item = self.available.item(i)
            item.setHidden(bool(query and query not in item.text().lower()))

    def activate(self,key):
        if key==self.active_key: return
        self.active_key=key; self.available.clear()
        if hasattr(self, 'error'): self.error.setVisible(False)
        spec=next(s for s in self.selectors if s['key']==key)
        for i,column in enumerate(self.worksheet.columns):
            if column.kind in spec.get('kinds',('number',)):
                label=format_variable_reference(i,self.worksheet)
                item=QListWidgetItem(label); item.setToolTip(label); item.setData(Qt.ItemDataRole.UserRole,i); self.available.addItem(item)
        if hasattr(self, 'var_filter') and self.var_filter.text().strip():
            self._filter_available_variables(self.var_filter.text())
        self.select_button.setEnabled(False)

    def transfer(self):
        if self.active_key is None: return
        selected=self.available.selectedItems()
        if not selected: return
        spec=next(s for s in self.selectors if s['key']==self.active_key)
        control=self.controls[self.active_key]
        refs=[format_variable_reference(item.data(Qt.ItemDataRole.UserRole),self.worksheet) for item in selected]
        is_multi = bool(spec.get('multiple') or spec.get('multi'))
        if is_multi:
            sel_indices = [item.data(Qt.ItemDataRole.UserRole) for item in selected]
            existing = control.text().strip()
            existing_indices = []
            if existing:
                try:
                    existing_indices = resolve_variables(
                        existing, self.worksheet, spec.get('kinds', ('number',))
                    )
                except ValueError:
                    existing_indices = [int(m[0]) - 1 for m in _REFERENCE.findall(existing)]
            added_refs = []
            seen_idx = set(existing_indices)
            for idx in sel_indices:
                if idx not in seen_idx:
                    seen_idx.add(idx)
                    added_refs.append(format_variable_reference(idx, self.worksheet))
            if added_refs:
                joined = ' '.join(added_refs)
                control.setText(f"{existing} {joined}".strip() if existing else joined)
            control.setFocus()
        else:
            control.setText(refs[0])
            current_idx = next((i for i, s in enumerate(self.selectors) if s['key'] == self.active_key), -1)
            next_key = None
            if current_idx != -1 and current_idx + 1 < len(self.selectors):
                for s in self.selectors[current_idx + 1:]:
                    if not self.controls[s['key']].text().strip():
                        next_key = s['key']
                        break
                if next_key is None and current_idx + 1 < len(self.selectors):
                    next_key = self.selectors[current_idx + 1]['key']
            if next_key is not None:
                self.activate(next_key)
                self.controls[next_key].setFocus()
            else:
                control.setFocus()

    def values(self):
        values={}
        for spec in self.selectors:
            raw_sel=self.controls[spec['key']].text()
            is_multi = bool(spec.get('multiple') or spec.get('multi'))
            is_optional = bool(spec.get('optional'))
            if is_optional and not raw_sel.strip():
                values[spec['key']] = [] if is_multi else None
                continue
            indices=resolve_variables(raw_sel,self.worksheet,spec.get('kinds',('number',)))
            minimum=spec.get('minimum', spec.get('min_count', 0 if is_optional else 1)) if is_multi else (0 if is_optional else 1)
            maximum=spec.get('maximum', spec.get('max_count')) if is_multi else 1
            if len(indices)<minimum or (maximum is not None and len(indices)>maximum):
                raise ValueError(spec['label']+': select '+(str(minimum) if maximum==minimum else 'at least '+str(minimum))+' columns.')
            values[spec['key']]=indices if is_multi else (indices[0] if indices else None)
        for first,second in (('response_index','factor_index'),('count_index','size_index'),('first_index','second_index')):
            if first in values and second in values and values[first]==values[second]: raise ValueError('Choose separate variables for the two roles.')
        if 'response_index' in values and values['response_index'] in values.get('predictor_indices',[]):
            raise ValueError('The response cannot also be a predictor.')
        for spec in self.fields:
            control=self.controls[spec['key']]
            if isinstance(control,QComboBox): value=control.currentText()
            elif isinstance(control,QCheckBox): value=control.isChecked()
            else:
                raw=control.text().strip()
                if spec.get('optional') and not raw: value=None
                elif spec.get('numeric'):
                    value=finite_number(float(raw))
                    if spec.get('integer'):
                        if int(value)!=value: raise ValueError(spec['label']+' must be an integer.')
                        value=int(value)
                else: value=control.text()
            values[spec['key']]=value
        return values

    def _insert_mru_ref(self, ref):
        if self.active_key is None or self.active_key not in self.controls:
            return
        ctrl = self.controls[self.active_key]
        cur = ctrl.text().strip()
        spec = next((s for s in self.selectors if s['key'] == self.active_key), {})
        if (spec.get('multiple') or spec.get('multi')) and cur:
            ctrl.setText(f"{cur} {ref}")
        else:
            ctrl.setText(ref)

    def validate(self):
        try:
            self.parameters=self.values()
            self.error.setVisible(False)
            from .micro_innovations import global_mru_columns
            used = []
            for spec in self.selectors:
                val = self.parameters.get(spec['key'])
                if isinstance(val, int) and 0 <= val < len(self.worksheet.columns):
                    used.append(format_variable_reference(val, self.worksheet))
                elif isinstance(val, list):
                    for idx in val:
                        if isinstance(idx, int) and 0 <= idx < len(self.worksheet.columns):
                            used.append(format_variable_reference(idx, self.worksheet))
            if used:
                global_mru_columns().record(used)
        except (ValueError,TypeError,OverflowError) as exc:
            msg = str(exc)
            self.error.setText(msg)
            self.error.setVisible(True)
            for spec in self.selectors + self.fields:
                lbl = spec.get('label', '')
                if lbl and (lbl in msg or lbl.rstrip(':') in msg):
                    ctrl = self.controls.get(spec['key'])
                    if ctrl:
                        ctrl.setFocus()
                        if hasattr(ctrl, "selectAll"):
                            ctrl.selectAll()
                        break
            return

        self._save_dialog_state()
        self.accept()

    def _save_dialog_state(self):
        ws_name = getattr(self.worksheet, 'name', '')
        col_sig = tuple((c.name, c.kind) for c in getattr(self.worksheet, 'columns', []))
        state_key = (id(self.worksheet), ws_name, self.windowTitle(), col_sig)
        saved = {}
        for k, ctrl in self.controls.items():
            if isinstance(ctrl, QComboBox):
                saved[k] = ctrl.currentText()
            elif isinstance(ctrl, QCheckBox):
                saved[k] = ctrl.isChecked()
            elif isinstance(ctrl, QLineEdit):
                saved[k] = ctrl.text()
        self._LAST_DIALOG_STATE[state_key] = saved


def _dialog_state_key(worksheet, key_name: str):
    ws_name = getattr(worksheet, 'name', '')
    col_sig = tuple((c.name, c.kind) for c in getattr(worksheet, 'columns', []))
    return (id(worksheet), ws_name, key_name, col_sig)


def save_dialog_state(worksheet, key_name: str, state: dict) -> None:
    if worksheet is None or not isinstance(state, dict):
        return
    import copy
    ProcedureDialog._LAST_DIALOG_STATE[_dialog_state_key(worksheet, key_name)] = copy.deepcopy(state)


def load_dialog_state(worksheet, key_name: str) -> dict | None:
    if worksheet is None:
        return None
    import copy
    saved = ProcedureDialog._LAST_DIALOG_STATE.get(_dialog_state_key(worksheet, key_name))
    return copy.deepcopy(saved) if saved is not None else None


class ScatterTypeDialog(QDialog):
    def __init__(self,parent,default_mode=None):
        from .scatter import MODES
        initial_mode = default_mode if default_mode in MODES else 'simple'
        super().__init__(parent); self.setSizeGripEnabled(True); self.setWindowTitle('Scatterplots'); self.mode=initial_mode
        dark=_is_dark_active(parent or self); self.setStyleSheet(dialog_stylesheet(dark))
        layout=QVBoxLayout(self); grid=QGridLayout(); self.buttons=QButtonGroup(self); self.mode_buttons={}
        for index,(mode,title) in enumerate(MODES.items()):
            button=QToolButton(); button.setText(title.replace(' and ',' and\n'))
            button.setCheckable(True); button.setChecked(mode==initial_mode); button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            pix=QPixmap(240,160); pix.setDevicePixelRatio(2); pix.fill(QColor('#18181b' if _is_dark_active(parent or self) else 'white'))
            painter=QPainter(pix); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor('#a1a1aa' if _is_dark_active(parent or self) else '#6e7f8f'),1)); painter.drawLine(12,68,111,68); painter.drawLine(12,68,12,8)
            grouped=mode in ('groups','regression_groups','connect_groups')
            for group in range(2 if grouped else 1):
                color=QColor('#b97743' if group else '#3e739b'); painter.setPen(QPen(color,1.4)); painter.setBrush(color)
                points=[QPointF(24+i*18,58-i*8-group*12+(i%2)*4) for i in range(5)]
                if mode in ('connect','connect_groups'):
                    for a,b in zip(points,points[1:]): painter.drawLine(a,b)
                if mode in ('regression','regression_groups'): painter.drawLine(QPointF(20,62-group*12),QPointF(102,22-group*12))
                for point in points: painter.drawEllipse(point,2.5,2.5)
            painter.end(); button.setIcon(QIcon(pix)); button.setIconSize(QSize(120,80)); button.setMinimumSize(155,132)
            button.setStyleSheet(gallery_button_stylesheet(_is_dark_active(parent or self)))
            button.clicked.connect(lambda checked=False,mode=mode:setattr(self,'mode',mode))
            self.buttons.addButton(button); self.mode_buttons[mode]=button
            grid.addWidget(button,index//4,index%4)
        layout.addLayout(grid); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)


class RoleTable(QTableWidget):
    def focusInEvent(self,event):
        super().focusInEvent(event)
        if hasattr(self,'activate'): self.activate()


class ScatterDialog(QDialog):
    def __init__(self,parent,worksheet,mode='simple'):
        from .scatter import MODES
        if mode not in MODES: raise ValueError('Unsupported scatterplot type.')
        super().__init__(parent); self.setSizeGripEnabled(True); self.setWindowTitle('Scatterplot: '+MODES[mode]); self.resize(800,540)
        self.mode=mode; self.grouped=mode in ('groups','regression_groups','connect_groups')
        self.active='pairs'; self.labels={'title':'','x_label':'','y_label':''}
        self.settings=None
        self.worksheet=worksheet; self.pairs=None
        dark = _is_dark_active(parent or self)
        self.setStyleSheet(dialog_stylesheet(dark))
        layout=QVBoxLayout(self); body=QHBoxLayout(); left=QVBoxLayout()
        left.addWidget(QLabel('Available variables'))
        self.var_filter=QLineEdit(); self.var_filter.setPlaceholderText('Filter variables...'); self.var_filter.setClearButtonEnabled(True)
        self.var_filter.textChanged.connect(self._filter_available_variables); left.addWidget(self.var_filter)
        self.available=QListWidget(); self.available.setMinimumWidth(210)
        for i,c in enumerate(worksheet.columns):
            if c.kind=='number':
                label=format_variable_reference(i,worksheet)
                item=QListWidgetItem(label); item.setToolTip(label); item.setData(Qt.ItemDataRole.UserRole,i); self.available.addItem(item)
        left.addWidget(self.available); select=QPushButton('Select'); select.setAutoDefault(False)
        select.clicked.connect(self.transfer); self.available.itemDoubleClicked.connect(lambda item:self.transfer()); left.addWidget(select); body.addLayout(left,1)
        right=QVBoxLayout(); self.roles=RoleTable(8,2); self.roles.setHorizontalHeaderLabels(['Y variables','X variables'])
        self.roles.activate=lambda:self.activate('pairs')
        self.roles.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.roles.setCurrentCell(0,0); right.addWidget(self.roles)
        form=QFormLayout(); self.group_entry=VariableEntry(lambda:self.activate('group'))
        self.group_entry.setPlaceholderText('Select a numeric or text group column')
        if self.grouped: form.addRow('Categorical variable for grouping',self.group_entry)
        self.order=QComboBox(); self.order.addItems(['Increasing X','Increasing Y','Worksheet'])
        if mode in ('connect','connect_groups'): form.addRow('Connection order',self.order)
        right.addLayout(form)
        labels=QPushButton('Labels…'); labels.setAutoDefault(False); labels.clicked.connect(self.edit_labels); right.addWidget(labels)
        hint=QLabel('Click a Y or X cell, then double-click an available variable or click Select.\nEach completed row creates one scatterplot. You can also type C numbers or quoted column names.')
        hint.setWordWrap(True); hint.setStyleSheet(subtle_label_style(dark, font_size="8pt")); right.addWidget(hint); body.addLayout(right,2); layout.addLayout(body)
        self.error=_AutoErrorLabel(); self.error.setObjectName('error'); self.error.setWordWrap(True); self.error.setVisible(False); layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Reset)
        reset_btn = buttons.button(QDialogButtonBox.StandardButton.Reset)
        if reset_btn:
            reset_btn.clicked.connect(self.reset_dialog)
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self._restore_dialog_state()

    def _filter_available_variables(self, text):
        query = text.strip().lower()
        for i in range(self.available.count()):
            item = self.available.item(i)
            item.setHidden(bool(query and query not in item.text().lower()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F3:
            self.reset_dialog()
            return
        super().keyPressEvent(event)

    def reset_dialog(self):
        self.roles.clearContents()
        self.roles.setCurrentCell(0, 0)
        self.group_entry.clear()
        self.order.setCurrentIndex(0)
        self.labels = {'title': '', 'x_label': '', 'y_label': ''}
        self.error.setVisible(False)
        self.activate('pairs')

    def _restore_dialog_state(self):
        saved = load_dialog_state(self.worksheet, f"ScatterDialog:{self.mode}")
        if not saved:
            return
        for row, (y_txt, x_txt) in enumerate(saved.get('pairs', ())):
            if row >= self.roles.rowCount():
                break
            if y_txt:
                self.roles.setItem(row, 0, QTableWidgetItem(str(y_txt)))
            if x_txt:
                self.roles.setItem(row, 1, QTableWidgetItem(str(x_txt)))
        if 'group' in saved:
            self.group_entry.setText(str(saved['group']))
        if 'order' in saved:
            self.order.setCurrentText(str(saved['order']))
        if isinstance(saved.get('labels'), dict):
            self.labels = {k: str(saved['labels'].get(k, '')) for k in ('title', 'x_label', 'y_label')}

    def _save_dialog_state(self):
        saved_pairs = []
        for row in range(self.roles.rowCount()):
            y_txt = self.roles.item(row, 0).text() if self.roles.item(row, 0) else ''
            x_txt = self.roles.item(row, 1).text() if self.roles.item(row, 1) else ''
            if y_txt or x_txt:
                saved_pairs.append((y_txt, x_txt))
        save_dialog_state(
            self.worksheet,
            f"ScatterDialog:{self.mode}",
            {
                'pairs': saved_pairs,
                'group': self.group_entry.text(),
                'order': self.order.currentText(),
                'labels': dict(self.labels),
            },
        )

    def edit_labels(self):
        dialog=QDialog(self); dialog.setWindowTitle('Scatterplot Labels')
        dialog.setStyleSheet(dialog_stylesheet(_is_dark_active(self)))
        layout=QVBoxLayout(dialog); form=QFormLayout(); edits={}
        for key,title in (('title','Title'),('x_label','X-axis label'),('y_label','Y-axis label')):
            edit=QLineEdit(self.labels[key]); edit.setMaxLength(256); edit.setPlaceholderText('Use default'); edits[key]=edit; form.addRow(title,edit)
        layout.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted: self.labels={key:edit.text() for key,edit in edits.items()}

    def activate(self,role):
        if self.active==role: return
        self.active=role; self.available.clear()
        for i,column in enumerate(self.worksheet.columns):
            if column.kind=='number' or role=='group' and column.kind=='text':
                label=format_variable_reference(i,self.worksheet); item=QListWidgetItem(label); item.setToolTip(label)
                item.setData(Qt.ItemDataRole.UserRole,i); self.available.addItem(item)
        if hasattr(self, 'var_filter') and self.var_filter.text().strip():
            self._filter_available_variables(self.var_filter.text())

    def transfer(self):
        item=self.available.currentItem()
        if item is None: return
        if self.active=='group':
            self.group_entry.setText(format_variable_reference(item.data(Qt.ItemDataRole.UserRole),self.worksheet)); return
        row,col=self.roles.currentRow(),self.roles.currentColumn()
        if row<0: row,col=0,0
        label=format_variable_reference(item.data(Qt.ItemDataRole.UserRole),self.worksheet)
        selected=QTableWidgetItem(label); selected.setToolTip(label); self.roles.setItem(row,col,selected)
        self.roles.setCurrentCell(min(row+1,self.roles.rowCount()-1),col)

    def values(self):
        pairs=[]
        for row in range(self.roles.rowCount()):
            raw=[self.roles.item(row,c).text().strip() if self.roles.item(row,c) else '' for c in range(2)]
            if not any(raw): continue
            selected=[resolve_variables(text,self.worksheet) for text in raw]
            if any(len(indices)!=1 for indices in selected): raise ValueError('Row '+str(row+1)+': select exactly one Y and one X variable.')
            if not self.worksheet.complete_rows([selected[0][0],selected[1][0]]): raise ValueError('Row '+str(row+1)+': the selected variables have no complete numeric pairs.')
            pairs.append((selected[0][0],selected[1][0]))
        if not pairs: raise ValueError('Select at least one Y/X pair.')
        return pairs

    def validate(self):
        self.roles.setFocus(); QApplication.processEvents()
        try:
            self.pairs=self.values()
            selected=resolve_variables(self.group_entry.text(),self.worksheet,('number','text')) if self.grouped else []
            if self.grouped and len(selected)!=1: raise ValueError('Select exactly one grouping variable.')
            self.settings=dict(mode=self.mode,group_index=selected[0] if selected else None,order=self.order.currentText(),**self.labels)
            from .scatter import build
            for y,x in self.pairs: build(self.worksheet,x,y,**self.settings)
            self.error.setVisible(False)
        except (ValueError,TypeError) as exc:
            self.error.setText(str(exc))
            self.error.setVisible(True)
            return
        self._save_dialog_state()
        self.accept()
