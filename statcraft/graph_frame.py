"""Graph annotations around a live chart; numerical result data stays unchanged."""
import copy
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QSizePolicy,QToolButton
from .graph_presentation import graph_presentation,validate_presentation


class AnnotationLabel(QLabel):
    activated=Signal(str)
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.activated.emit(self.annotation_name);event.accept();return
        super().mouseDoubleClickEvent(event)


class GraphFrame(QWidget):
    annotationActivated=Signal(str)
    def __init__(self,chart,entry,parent=None):
        super().__init__(parent);self.chart=chart;self.entry=entry
        chart._frame_managed=True
        chart.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
        self.base_panels=copy.deepcopy(getattr(chart, 'panels', []));self.export_hidden=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0);layout.setSpacing(4)
        self.header=QHBoxLayout();self.title_label=AnnotationLabel();self.title_label.setObjectName('pageHeading')
        self.title_label.setTextFormat(Qt.TextFormat.PlainText);self.title_label.setWordWrap(True)
        self.header.addWidget(self.title_label,1);layout.addLayout(self.header)
        self.subtitle_label=AnnotationLabel();self.subtitle_label.setTextFormat(Qt.TextFormat.PlainText)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter);self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        # Quick-action selection strip for brushed rows
        self.selection_strip = QWidget()
        self.selection_strip.setObjectName('graphSelectionStrip')
        self.selection_strip.setStyleSheet(
            '#graphSelectionStrip { background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 2px 6px; margin: 2px 0px; }'
            'QLabel { color: #166534; font-weight: bold; font-size: 8.5pt; }'
            'QToolButton { background-color: #ffffff; border: 1px solid #86efac; border-radius: 3px; padding: 2px 6px; color: #166534; font-size: 8pt; font-weight: 500; }'
            'QToolButton:hover { background-color: #dcfce7; border-color: #4ade80; }'
        )
        s_layout = QHBoxLayout(self.selection_strip)
        s_layout.setContentsMargins(6, 2, 6, 2)
        s_layout.setSpacing(6)
        self.selection_label = QLabel('0 observations selected')
        s_layout.addWidget(self.selection_label)

        self.btn_highlight = QToolButton(); self.btn_highlight.setText('Highlight in Table')
        self.btn_save = QToolButton(); self.btn_save.setText('Save Selection…')
        self.btn_analyze = QToolButton(); self.btn_analyze.setText('Analyze…')
        self.btn_r = QToolButton(); self.btn_r.setText('Open in R')
        self.btn_clear = QToolButton(); self.btn_clear.setText('✕'); self.btn_clear.setToolTip('Clear Selection')

        s_layout.addWidget(self.btn_highlight)
        s_layout.addWidget(self.btn_save)
        s_layout.addWidget(self.btn_analyze)
        s_layout.addWidget(self.btn_r)
        s_layout.addStretch()
        s_layout.addWidget(self.btn_clear)

        self.selection_strip.hide()
        self.export_hidden.append(self.selection_strip)
        layout.addWidget(self.selection_strip)
        layout.addWidget(chart, 1)
        self.footnote_label=AnnotationLabel();self.footnote_label.setTextFormat(Qt.TextFormat.PlainText)
        self.footnote_label.setWordWrap(True);layout.addWidget(self.footnote_label)
        for name in ('title','subtitle','footnote'):
            label=getattr(self,name+'_label');label.annotation_name=name
            label.activated.connect(self.annotationActivated);label.setToolTip('Double-click to edit '+name)
        self.apply_appearance()

    def update_selection_strip(self, count):
        if count > 0:
            s_sfx = 's' if count != 1 else ''
            self.selection_label.setText(f'{count} observation{s_sfx} selected')
            self.selection_strip.show()
        else:
            self.selection_strip.hide()

    def apply_appearance(self):
        if self.entry.get('result',{}).get('analysis')=='native_saved_output':
            self.base_panels=copy.deepcopy(self.chart.panels)
        if hasattr(self.chart,'refresh_composition'):
            self.chart.refresh_composition();self.base_panels=copy.deepcopy(self.chart.panels)
        from .graph_styles import validate_styles
        self.chart.graph_styles=validate_styles(self.entry.get('graph_styles',{}))
        self.apply(graph_presentation(self.entry))

    def apply(self,settings):
        settings=validate_presentation(settings)
        for name in ('title','subtitle','footnote'):
            label=getattr(self,name+'_label');label.setText(settings[name]);label.setVisible(settings[name+'_enabled'])
        self.chart.title=''
        defaults=graph_presentation({k:v for k,v in self.entry.items() if k!='graph_presentation'})
        self.chart.annotation_axes={key:settings[key+'_label'] for key in ('x','y') if settings[key+'_label']!=defaults[key+'_label']}
        self.chart.annotation_positions={key:settings[key+'_position'] for key in ('x','y')}
        self.chart.annotation_limits={key:(settings[key+'_min'],settings[key+'_max']) for key in ('x','y') if settings[key+'_min'] is not None}
        self.chart.annotation_grid=settings['grid_enabled']
        self.chart.panels=copy.deepcopy(self.base_panels)
        if self.entry.get('histogram_settings') is not None:
            from .histogram_options import build_histogram_panel
            panel=build_histogram_panel(self.entry['result'].get('histogram_source'),self.entry['histogram_settings'])
            panel['xlabel']=self.base_panels[0].get('xlabel','Value');self.chart.panels=[panel]
        for panel in self.chart.panels:
            if isinstance(panel.get('axes'),list):
                for index,key in enumerate(('x','y')):
                    if key in self.chart.annotation_axes:panel['axes'][index]=self.chart.annotation_axes[key]
                    if settings[key+'_position']=='off':panel['axes'][index]=''
        labels=[self.title_label,self.subtitle_label,self.footnote_label]
        annotation_height=sum(max(label.fontMetrics().height(),label.heightForWidth(max(80,self.width()))) for label in labels if not label.isHidden())
        self.setMinimumHeight(self.chart.minimumHeight()+annotation_height+12)
        self.setMinimumWidth(self.chart.minimumWidth())
        self.chart.update();self.updateGeometry()

    def capture(self):
        visible=[widget for widget in self.export_hidden if not widget.isHidden()]
        selected=getattr(self.chart,'selected_object',None)
        brushed=getattr(self.chart,'brushed_rows',set())
        exporting=getattr(self.chart,'_exporting',False)
        try:
            self.chart._exporting=True
            self.chart.selected_object=None
            self.chart.brushed_rows=set()
            for widget in visible:widget.hide()
            return self.grab()
        finally:
            self.chart._exporting=exporting
            self.chart.selected_object=selected;self.chart.update()
            self.chart.brushed_rows=brushed
            for widget in visible:widget.show()
