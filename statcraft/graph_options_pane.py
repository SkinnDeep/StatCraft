"""Docked graph annotations, guided by recovered graph-editor form behavior.

The More options section is an original bounded Cartesian-scale control. Its
destination is not claimed equivalent to the unrecovered native host link.
"""
from PySide6.QtCore import Qt, QTimer, Signal, QSignalBlocker
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QToolButton, QPushButton, QScrollArea, QLineEdit, QCheckBox, QRadioButton,
    QButtonGroup, QFormLayout, QFrame,QStyle,QStyleOptionButton)
from .graph_presentation import graph_presentation, validate_presentation


def _paint_indicator(widget,radio):
    option=QStyleOptionButton();widget.initStyleOption(option)
    element=QStyle.SubElement.SE_RadioButtonIndicator if radio else QStyle.SubElement.SE_CheckBoxIndicator
    rect=widget.style().subElementRect(element,option,widget).adjusted(1,1,-1,-1)
    painter=QPainter(widget);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(rect.adjusted(-1,-1,1,1),QColor('white'))
    accent=QColor('#87009c');painter.setPen(QPen(accent if widget.isChecked() else QColor('#707070'),1))
    painter.setBrush(accent if widget.isChecked() and not radio else QColor('white'))
    if radio:
        painter.drawEllipse(rect)
        if widget.isChecked():painter.setBrush(accent);painter.drawEllipse(rect.adjusted(3,3,-3,-3))
    else:
        painter.drawRoundedRect(rect,1,1)
        if widget.isChecked():
            painter.setPen(QPen(QColor('white'),1.6))
            painter.drawLine(rect.left()+2,rect.center().y(),rect.center().x()-1,rect.bottom()-2)
            painter.drawLine(rect.center().x()-1,rect.bottom()-2,rect.right()-2,rect.top()+2)
    painter.end()


class AnnotationCheckBox(QCheckBox):
    def paintEvent(self,event):
        super().paintEvent(event);_paint_indicator(self,False)


class AnnotationRadioButton(QRadioButton):
    def paintEvent(self,event):
        super().paintEvent(event);_paint_indicator(self,True)


class GraphOptionsPane(QWidget):
    changed = Signal(object, dict)
    closeRequested = Signal()
    objectEditRequested=Signal()
    histogramEditRequested=Signal()

    def __init__(self, parent=None, apply_callback=None):
        super().__init__(parent)
        self.apply_callback = apply_callback
        self.bound_entry = None
        self._loading = False
        self._flushing = False
        self._baseline = None
        self.controls = {}
        self.axis_groups = {}
        self.setObjectName('graphOptionsPane')
        self.setMinimumWidth(290)
        self.setMaximumWidth(480)
        self.setStyleSheet('''
            QWidget { background: white; }
            QWidget#graphOptionsPane { border-left: 1px solid #d4d4d4; }
            QLabel { color: #202020; }
            QLineEdit { background: white; border: 1px solid #e1e4e8; padding: 6px; min-height: 18px; }
            QToolButton { border: none; background: transparent; padding: 3px; }
            QPushButton#moreGraphOptions { text-align: left; color: #007eb7; border: none; background: white; text-decoration: underline; }
        ''')
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(165)
        self.timer.timeout.connect(self.flush)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        header = QWidget(); header.setStyleSheet('background: white;')
        top = QHBoxLayout(header); top.setContentsMargins(12, 4, 10, 4)
        heading = QLabel('Options'); heading.setStyleSheet('font-size: 15pt;')
        top.addWidget(heading); top.addStretch()
        self.close_button = QToolButton(); self.close_button.setText('×')
        self.close_button.setStyleSheet('font-size: 22pt; color: #333;')
        self.close_button.setToolTip('Close Options'); self.close_button.setAccessibleName('Close Options')
        self.close_button.clicked.connect(self._close)
        top.addWidget(self.close_button); outer.addWidget(header)
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); outer.addWidget(line)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(); body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 5, 14, 12); body_layout.setSpacing(12)
        self.annotations_header = QToolButton(); self.annotations_header.setText('Text Annotations')
        self.annotations_header.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.annotations_header.setArrowType(Qt.ArrowType.DownArrow)
        self.annotations_header.setCheckable(True); self.annotations_header.setChecked(True)
        self.annotations_header.setStyleSheet('font-size: 13pt; padding: 5px 0;')
        body_layout.addWidget(self.annotations_header)
        self.annotations_body = QWidget(); notes = QVBoxLayout(self.annotations_body)
        notes.setContentsMargins(0, 0, 0, 0); notes.setSpacing(16)
        for key, caption in (('title', 'Title:'), ('subtitle', 'Subtitle:'), ('footnote', 'Footnote:')):
            block = QVBoxLayout(); block.setSpacing(8)
            check = AnnotationCheckBox(caption); field = QLineEdit(); field.setMaxLength(145)
            field.setAccessibleName(caption.rstrip(':'))
            self.controls[key + '_enabled'] = check; self.controls[key] = field
            check.toggled.connect(self._schedule)
            field.textEdited.connect(lambda text, key=key: self._annotation_edited(key, text))
            field.editingFinished.connect(self.flush)
            block.addWidget(check); block.addWidget(field); notes.addLayout(block)
        for axis in ('x', 'y'):
            block = QVBoxLayout(); block.setSpacing(4)
            block.addWidget(QLabel(axis.upper() + '-axis label:'))
            group = QButtonGroup(self); self.axis_groups[axis] = group
            for position, caption in (('off', 'Off'), ('low', 'Low'), ('high', 'High')):
                radio = AnnotationRadioButton(caption); radio.setObjectName(axis + '_' + position)
                self.controls[axis + '_' + position] = radio
                group.addButton(radio); block.addWidget(radio)
                radio.toggled.connect(self._schedule)
            field = QLineEdit(); field.setMaxLength(145)
            field.setAccessibleName(axis.upper() + '-axis label')
            self.controls[axis + '_label'] = field
            field.textEdited.connect(lambda text, axis=axis: self._axis_edited(axis))
            field.editingFinished.connect(self.flush)
            block.addSpacing(4); block.addWidget(field); notes.addLayout(block)
        body_layout.addWidget(self.annotations_body)
        self.annotations_header.toggled.connect(self._toggle_annotations)
        self.more_button = QPushButton('More options'); self.more_button.setObjectName('moreGraphOptions')
        self.more_button.setToolTip('Show StatCraft axis limits and grid settings')
        self.more_button.setCheckable(True); body_layout.addWidget(self.more_button)
        self.more_body = QWidget(); more = QVBoxLayout(self.more_body); more.setContentsMargins(0, 0, 0, 0)
        note = QLabel('Scales'); note.setStyleSheet('font-size: 12pt;'); more.addWidget(note)
        form = QFormLayout()
        for axis in ('x', 'y'):
            for edge in ('min', 'max'):
                key = axis + '_' + edge
                field = QLineEdit(); field.setPlaceholderText('Automatic')
                field.setAccessibleName(axis.upper() + '-axis ' + ('minimum' if edge == 'min' else 'maximum'))
                self.controls[key] = field; form.addRow(axis.upper() + ' ' + edge + ':', field)
                field.textEdited.connect(self._schedule); field.editingFinished.connect(self.flush)
        more.addLayout(form)
        ref_form = QFormLayout()
        for axis in ('x', 'y'):
            rkey = axis + '_ref_line'
            rfield = QLineEdit(); rfield.setPlaceholderText('e.g. 5, 10'); rfield.setMaxLength(145)
            rfield.setAccessibleName(axis.upper() + '-axis reference lines')
            self.controls[rkey] = rfield; ref_form.addRow(axis.upper() + ' Ref Lines:', rfield)
            rfield.textEdited.connect(self._schedule); rfield.editingFinished.connect(self.flush)
        more.addLayout(ref_form)
        self.controls['grid_enabled'] = QCheckBox('Major grid lines')
        self.controls['grid_enabled'].toggled.connect(self._schedule)
        more.addWidget(self.controls['grid_enabled'])
        for key, caption in (('x_log', 'Logarithmic X scale'), ('y_log', 'Logarithmic Y scale'), ('show_mean_line', 'Show mean reference line'), ('show_data_labels', 'Show data value labels')):
            chk = QCheckBox(caption); chk.toggled.connect(self._schedule)
            self.controls[key] = chk; more.addWidget(chk)
        caveat = QLabel('Enter both limits, or leave both blank for automatic scaling. Limits apply to Cartesian plots; other types retain their own scales.')
        caveat.setWordWrap(True); caveat.setStyleSheet('color: #666; font-size: 9pt;'); more.addWidget(caveat)
        self.more_body.hide(); self.more_button.toggled.connect(self.more_body.setVisible)
        body_layout.addWidget(self.more_body)
        self.object_button=QPushButton('Object Properties...');self.object_button.clicked.connect(self.objectEditRequested)
        self.histogram_button=QPushButton('Histogram Scales and Fits...');self.histogram_button.clicked.connect(self.histogramEditRequested)
        body_layout.addWidget(self.object_button);body_layout.addWidget(self.histogram_button)
        self.error = QLabel(); self.error.setWordWrap(True); self.error.setStyleSheet('color: #a32020;')
        self.error.setObjectName('graphOptionsError'); body_layout.addWidget(self.error)
        body_layout.addStretch(1); scroll.setWidget(body); outer.addWidget(scroll)

    def _toggle_annotations(self, checked):
        self.annotations_header.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.annotations_body.setVisible(checked)

    def _annotation_edited(self, key, text):
        if self._loading: return
        self.controls[key + '_enabled'].setChecked(bool(text))
        self._schedule()

    def _axis_edited(self, axis):
        if self._loading: return
        if self.controls[axis + '_off'].isChecked():
            self.controls[axis + '_low'].setChecked(True)
        self._schedule()

    def _schedule(self, *unused):
        if not self._loading and self.bound_entry is not None:
            self.timer.start()

    def load_entry(self, entry):
        # Flush before rebinding: pending keystrokes must never edit another graph.
        if self.bound_entry is not None:
            self.flush()
        self.timer.stop()
        self._loading = True
        self.bound_entry = entry
        self.error.clear()
        try:
            settings = graph_presentation(entry)
            blockers = [QSignalBlocker(control) for control in self.controls.values()]
            for key, value in settings.items():
                if key in ('x_position', 'y_position'):
                    self.controls[key[0] + '_' + value].setChecked(True)
                elif key.endswith('_enabled') or key in ('x_log', 'y_log', 'show_data_labels', 'show_mean_line'):
                    self.controls[key].setChecked(bool(value))
                else:
                    self.controls[key].setText('' if value is None else str(value))
            self._baseline = settings
            del blockers
        except ValueError as exc:
            self.error.setText(str(exc))
            self._baseline = None
        finally:
            self._loading = False
        self.setEnabled(entry is not None)
        result=entry.get('result',{}) if isinstance(entry,dict) else {}
        self.histogram_button.setVisible(result.get('graph')=='histogram')
        panels=result.get('panels',[])
        cartesian=result.get('graph')!='expanded' or any(p.get('kind') in ('xy','bars','binbars','intervals') or p.get('kind')=='surface' and p.get('contour') for p in panels if isinstance(p,dict))
        if result.get('analysis')=='native_saved_output':
            from .native_graph_view import cartesian as native_cartesian
            cartesian=native_cartesian(entry)
        if result.get('graph') in ('panel_graph','graph_layout'):cartesian=False
        static_plot=result.get('analysis') in ('multiple_capability','nested_gage_rr','gage_linearity_and_bias','attribute_agreement_analysis','reliability_distribution','capability_nonnormal','capability_nonparametric','capability_automated','mixture_multi_optimization','mixture_multi_evaluation')
        if static_plot:cartesian=False
        mixture_exploration=result.get('analysis') in ('mixture_contour','mixture_optimization')
        if mixture_exploration:cartesian=False
        composite=result.get('graph') in ('panel_graph','graph_layout')
        self.object_button.setEnabled(not composite and not static_plot)
        for axis in ('x','y'):
            for key in ('label','off','low','high'):self.controls[axis+'_'+key].setEnabled(not composite and not static_plot and not mixture_exploration)
        for key in ('x_min','x_max','y_min','y_max','grid_enabled','x_ref_line','y_ref_line','x_log','y_log','show_mean_line','show_data_labels'):
            self.controls[key].setEnabled(cartesian)
            self.controls[key].setToolTip('' if cartesian else 'Cartesian plots support this control; this graph retains its own scale.')
        if mixture_exploration:self.controls['grid_enabled'].setEnabled(True)

    def _settings(self):
        values = {}
        for key in ('title', 'subtitle', 'footnote', 'x_label', 'y_label', 'x_ref_line', 'y_ref_line'):
            values[key] = self.controls[key].text()
        for key in ('title_enabled', 'subtitle_enabled', 'footnote_enabled', 'grid_enabled', 'x_log', 'y_log', 'show_data_labels', 'show_mean_line'):
            values[key] = self.controls[key].isChecked()
        for axis in ('x', 'y'):
            values[axis + '_position'] = next((p for p in ('off', 'low', 'high') if self.controls[axis + '_' + p].isChecked()), 'low')
            for edge in ('min', 'max'):
                key = axis + '_' + edge; raw = self.controls[key].text().strip()
                try: values[key] = float(raw) if raw else None
                except ValueError: raise ValueError(axis.upper() + '-axis limits must be finite numbers or blank.') from None
        return validate_presentation(values)

    def flush(self):
        """Commit valid changed drafts; invalid input leaves the last graph intact."""
        self.timer.stop()
        if self._loading or self._flushing or self.bound_entry is None: return True
        self._flushing = True
        try:
            settings = self._settings()
            if settings != self._baseline:
                accepted = self.apply_callback(self.bound_entry, dict(settings)) if self.apply_callback else None
                if accepted is False:
                    if not self.error.text(): self.error.setText('These settings could not be applied to this graph.')
                    return False
                self._baseline = dict(settings)
                self.changed.emit(self.bound_entry, dict(settings))
            self.error.clear()
            return True
        except (ValueError, TypeError, OverflowError) as exc:
            self.error.setText(str(exc))
            return False
        finally:
            self._flushing = False

    def _close(self):
        self.flush()
        self.closeRequested.emit()
