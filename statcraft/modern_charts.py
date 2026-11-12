"""Original responsive Qt/QPainter plots for persisted Presenter entries."""
import math
import numbers
from statistics import NormalDist
from PySide6.QtCore import Qt, QRectF, QPointF, QSize,Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget, QSizePolicy
from .graph_hover import point_info,histogram_info,summary_info
from .graph_interaction import GraphInteractionMixin,style_pen,style_color,draw_marker
from .spatial_view import DEFAULT_VIEW, view_state
from .chart_theme import chart_painter

BLUE='#3e739b'; RED='#bb4147'; GREEN='#51846b'; INK='#263440'; MUTED='#697884'


def _number(value):
    if isinstance(value,bool) or not isinstance(value,numbers.Real) or not math.isfinite(value):
        raise ValueError('Plot data must contain finite real numbers or missing gaps.')
    return float(value)


def _values(values):
    return [None if v is None else _number(v) for v in values]


def _fmt(value):
    return '0' if value == 0 else f'{value:.5g}'


def supported(entry):
    r = entry.get("result", entry) if isinstance(entry, dict) else {}
    from .phase6_charts import supported as phase6_supported
    if phase6_supported(r):
        return True
    if isinstance(r, dict) and r.get("analysis") in (
        "graphical_summary", "run_chart", "multivari", "outlier_test", "cross_correlation",
        "fitted_line_plot",
        "anom",
        "cause_and_effect",
        "winters_method", "arima", "trend_analysis", "decomposition", "moving_average", "single_exp_smoothing", "double_exp_smoothing",
        "jmp_distribution", "control_chart_builder", "process_screening",
    ):
        return True
    if isinstance(r,dict) and r.get('analysis')=='native_saved_output':
        return any(g.get('panels') for g in r.get('graphs',[]))
    if isinstance(r,dict) and r.get('analysis') in ('mixture_multi_optimization','mixture_multi_evaluation','mixture_contour','mixture_optimization','mixture_joint_optimization'):
        return True
    if isinstance(r,dict) and r.get('analysis')=='dynamic_taguchi_analysis':
        return bool(r.get('panels')) or (bool(r.get('options',{}).get('show_signal_plots',False)) and bool(r.get('rows')))
    if isinstance(r,dict) and r.get('analysis')=='mixture_process_model':
        return bool(r.get('show_graphs',True))
    if isinstance(r,dict) and r.get('analysis') in ('mixture_model','taguchi_analysis'):
        return bool(r.get('show_graphs',True)) and (r.get('analysis')=='mixture_model' or bool(r.get('panels')))
    if isinstance(r, dict) and (r.get('analysis') in (
            'optimal_design', 'design_evaluation',
            'cart_tree', 'evaluating_measurement_process', 'fit_y_by_x', 'definitive_screening_analysis', 'accelerated_life_testing',
            'nested_gage_rr', 'gage_linearity_and_bias', 'attribute_agreement_analysis',
            'reliability_distribution', 'capability_nonparametric',
            'capability_automated', 'capability_nonnormal', 'multiple_capability') or r.get('graph') in (
            'reliability_distribution', 'capability_nonparametric',
            'capability_automated', 'capability_nonnormal')):
        options = r.get('options') if isinstance(r.get('options'), dict) else {}
        return r.get('show_graphs', options.get('show_graphs', True)) is not False
    if isinstance(r, dict) and r.get('analysis') == 'subgroup_control':
        from .subgroup_control_chart import supported as subgroup_control_supported
        return subgroup_control_supported(r)
    if isinstance(r, dict) and r.get('analysis') == 'multiple_regression':
        options = r.get('options') if isinstance(r.get('options'), dict) else {}
        graphs = r.get('graphs', options.get('graphs', 'four'))
        return graphs != 'none'
    if isinstance(r, dict) and (r.get('graph') in ('attribute_capability', 'attribute_gage', 'symmetry_plot', 'acceptance_sampling_attributes', 'acceptance_sampling_variables') or r.get('analysis') in ('attribute_control', 'time_weighted_control', 'rare_event_control', 'multivariate_control', 'pareto_chart', 'type1_gage', 'tolerance_intervals', 'acceptance_control', 'attribute_gage', 'symmetry_plot', 'acceptance_sampling_attributes', 'acceptance_sampling_variables')):
        return True
    if isinstance(r, dict) and r.get('analysis') == 'oneway_anova':
        from .oneway_chart import supported as oneway_supported
        return oneway_supported(r)
    if isinstance(r, dict) and r.get('analysis') == 'twoway_anova':
        from .twoway_anova_chart import supported as twoway_supported
        return twoway_supported(r)
    if isinstance(r, dict) and r.get('analysis') in ('main_effects_plot', 'interactions_plot'):
        from .anova_plots_chart import supported as anova_plots_supported
        return anova_plots_supported(r)
    if isinstance(r, dict) and (r.get('graph') == 'equal_variances' or r.get('test_equal_variances')):
        return True
    if isinstance(r, dict) and (r.get('two_variances') and r.get('graphs', {}).get('summary_plot', True)):
        return True
    if isinstance(r, dict) and (r.get('graph') == 'one_sample_z' or r.get('one_sample_z')):
        return True
    if isinstance(r, dict) and (r.get('graph') == 'one_sample_t' or r.get('one_sample_t')):
        return True
    if isinstance(r, dict) and (r.get('graph') == 'two_sample_t' or r.get('two_sample_t')):
        return True
    if isinstance(r, dict) and (r.get('graph') == 'paired_t' or r.get('paired_t')):
        return True
    if isinstance(r, dict) and (r.get('graph') in ('capability', 'capability_sixpack', 'imr_chart') or r.get('analysis') in ('capability', 'capability_sixpack_normal', 'imr_control') or 'observed_perf' in r):
        return True
    if isinstance(r,dict) and r.get('analysis')=='factorial_plots':return bool(r.get('main_effects') or r.get('interactions'))
    if isinstance(r,dict) and r.get('analysis') in ('model_contour_plot','model_surface_plot'):return bool(r.get('panels'))
    if isinstance(r,dict) and r.get('analysis')=='response_optimizer':return bool(r.get('options',{}).get('optimization_plot',True))
    if isinstance(r,dict) and r.get('analysis')=='binary_logistic':return r.get('options',{}).get('graphs')=='four'
    if isinstance(r,dict) and r.get('plot_residuals') is False: return False
    return isinstance(r,dict) and (r.get('graph') in ('categorical_points','dotplot_graphs','boxplot_graphs','histogram_graphs','descriptive_graphs','panel_graph','graph_layout','expanded','histogram','scatter','boxplot','normal_probability') or
        r.get('analysis')=='gage_rr' or any(k in r for k in ('xbar_center','i_center','within_stdev')) or
        r.get('chart') in ('P','U') or ('fitted' in r and 'residuals' in r))


supports=supported


class ChartWidget(GraphInteractionMixin,QWidget):
    objectSelected=Signal(str)
    objectActivated=Signal(str)
    brushRowsSelected=Signal(list)
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry=entry if isinstance(entry,dict) else {}
        self.result=self.entry.get('result',self.entry)
        self.title=str(self.entry.get('title','Analysis plot'))
        self.panels=[]; self.panel_columns=1; self.note=''; self.error=None
        self._init_graph_interaction()
        self.view_state = dict(DEFAULT_VIEW)
        self._orbit_start = None
        self._pan_start = None
        self._viewcube_drag_start = None
        self._viewcube_target = None
        self._viewcube_moved = False
        self._drag_start_pos = None
        self._drag_moved = False
        self._is_dragging = False
        self.active_cad_card = None
        self._zoom2d_limits = {}
        self._zoom2d_meta = {}
        self._zoom2d_pan_start = None
        self._zoom2d_pan_panel = None
        self._reset_zoom_rect = None
        self._hidden_legend_series = set()
        self._legend_hit_rects = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self.setMinimumSize(520,350)
        self.setFont(QFont('Segoe UI',10))
        try:
            self._prepare()
        except (ValueError,TypeError,KeyError,IndexError,OverflowError) as exc:
            self.panels=[]; self.error=str(exc)

    def minimumSizeHint(self):
        return QSize(560,460 if len(self.panels)>1 else 360)

    def sizeHint(self):
        return QSize(860,700 if len(self.panels)>1 else 510)

    def _line_panel(self,title,values,center,low,high,signals,ylabel):
        values=_values(values); n=len(values)
        if not n or not any(v is not None for v in values):
            raise ValueError('No finite observations are available for this plot.')
        lines=[]
        for label,data,color in [('UCL',high,RED),('Center',center,GREEN),('LCL',low,RED)]:
            data=_values(data) if isinstance(data,(list,tuple)) else [_number(data)]*n
            if len(data)!=n:raise ValueError('Control limits and observations must be row aligned.')
            # Do not bridge a missing observation, even for scalar limits.
            data=[v if values[i] is not None else None for i,v in enumerate(data)]
            lines.append((label,data,color))
        valid_signals={int(v) for v in signals if isinstance(v,numbers.Integral) and 1<=v<=n}
        return dict(kind='line',title=title,x=list(range(1,n+1)),y=values,
                    lines=lines,signals=valid_signals,xlabel='Subgroup' if 'Xbar' in title or title=='Range' else 'Observation',ylabel=ylabel)

    def _histogram(self,values):
        values=[v for v in _values(values) if v is not None]
        if not values:raise ValueError('Histogram requires finite observations.')
        lo,hi=min(values),max(values)
        if lo==hi:lo-=.5;hi+=.5
        bins=max(1,min(30,math.ceil(math.sqrt(len(values)))))
        width=(hi-lo)/bins
        if not math.isfinite(width) or width<=0:raise ValueError('Histogram range exceeds plotting precision.')
        edges=[lo+i*width for i in range(bins+1)];counts=[0]*bins
        for v in values:counts[min(bins-1,max(0,int((v-lo)/width)))]+=1
        return edges,counts

    def _prepare(self):
        if self.result.get('analysis') in ('mixture_model','mixture_process_model'):
            from .doe_analysis_charts import prepare_mixture
            prepare_mixture(self,self.result);return
        r=self.result
        if not isinstance(r,dict):return
        from .phase6_charts import supported as phase6_supported, prepare as phase6_prepare
        if phase6_supported(r):
            phase6_prepare(self, r)
            return
        if r.get('analysis') == 'subgroup_control':
            from .subgroup_control_chart import prepare
            prepare(self, r)
            return
        if r.get('analysis') == 'oneway_anova':
            from .oneway_chart import prepare
            prepare(self, r)
            return
        if r.get('analysis') == 'twoway_anova':
            from .twoway_anova_chart import prepare as prepare_twoway
            prepare_twoway(self, r)
            return
        if r.get('analysis') in ('main_effects_plot', 'interactions_plot'):
            from .anova_plots_chart import prepare as prepare_anova_plots
            prepare_anova_plots(self, r)
            return
        if r.get('graph') == 'equal_variances' or r.get('test_equal_variances'):
            self.panels = [{'kind': 'equal_variances', 'title': self.title, 'entry': self.entry}]
            self.note = self.entry.get('title', '')
            self.setMinimumSize(620, 380)
            return
        if r.get('two_variances') and r.get('graphs', {}).get('summary_plot', True):
            self.panels = [{'kind': 'two_variances', 'title': self.title, 'entry': self.entry}]
            self.note = self.entry.get('title', '')
            self.setMinimumSize(600, 360)
            return
        if r.get('graph') == 'one_sample_z' or r.get('one_sample_z'):
            self.panels = [{'kind': 'one_sample_z', 'title': self.title, 'entry': self.entry}]
            self.note = self.entry.get('title', '')
            self.setMinimumSize(560, 380)
            return
        if r.get('graph') == 'one_sample_t' or r.get('one_sample_t'):
            self.panels = [{'kind': 'one_sample_t', 'title': self.title, 'entry': self.entry}]
            self.note = self.entry.get('title', '')
            self.setMinimumSize(560, 380)
            return
        if r.get('graph') == 'paired_t' or r.get('paired_t'):
            self.panels = [{'kind': 'paired_t', 'title': self.title, 'entry': self.entry}]
            self.note = self.entry.get('title', '')
            self.setMinimumSize(560, 380)
            return
        if r.get('graph') == 'two_sample_t' or r.get('two_sample_t'):
            self.panels = [{'kind': 'two_sample_t', 'title': self.title, 'entry': self.entry}]
            self.note = self.entry.get('title', '')
            self.setMinimumSize(560, 380)
            return
        if r.get('analysis') in ('factorial_plots','model_contour_plot','model_surface_plot'):
            from .model_plots_chart import prepare
            prepare(self,r);return
        if r.get('analysis')=='response_optimizer':
            from .optimizer_chart import prepare
            prepare(self,r);return
        if r.get('analysis')=='binary_logistic':
            from .logistic_chart import prepare
            prepare(self,r);return
        if r.get('analysis')=='gage_rr':
            from .gage_rr_chart import prepare
            prepare(self,r);return
        graph=r.get('graph')
        if graph=='categorical_points':
            from copy import deepcopy
            from .categorical_points import validate_result
            validate_result(r);self.panels=deepcopy(r['panels']);self.note=r['convention']
            self.setMinimumHeight(len(self.panels)*350+36);self.setMinimumWidth(max(640,max(len(panel['items']) for panel in self.panels)*90+180));return
        if r.get('analysis') in ('general_linear_model','response_surface'):
            from .glm import residual_panels
            self.panels=residual_panels(r);self.note='Residual plots for '+str(r['response_name'])
            if r['options']['graphs']=='four':self.panel_columns=2;self.setMinimumSize(760,680)
            return
        if graph=='dotplot_graphs':
            from copy import deepcopy
            from .dotplot_graphs import validate_result
            from .dotplot_chart import panel_height
            validate_result(r);self.panels=deepcopy(r['panels']);self.note=r['convention']
            self.setMinimumHeight(sum(panel_height(panel) for panel in self.panels)+36);self.setMinimumWidth(760);return
        if graph=='boxplot_graphs':
            import copy
            from .boxplot_graphs import validate_result
            validate_result(r);self.panels=copy.deepcopy(r['panels']);self.note=r.get('convention','')
            self.setMinimumWidth(max(520,max(len(panel['items']) for panel in self.panels)*90+180))
            self.setMinimumHeight(len(self.panels)*330+36);return
        if graph=='descriptive_graphs':
            from copy import deepcopy
            self.panels = deepcopy(r.get('descriptive_graphs', []))
            self.panel_columns = 2 if len(self.panels) > 1 else 1
            self.note = 'Descriptive statistics graphs'
            rows = max(1, math.ceil(len(self.panels) / self.panel_columns))
            self.setMinimumHeight(rows * 300 + 40)
            self.setMinimumWidth(760 if self.panel_columns > 1 else 540)
            return
        if graph=='histogram_graphs':
            import copy
            from .histogram_graphs import validate_result
            validate_result(r);self.panels=copy.deepcopy(r['panels'])
            self.note='Shared equal-width bins within each response; group-specific normalization and Normal fits.'
            self.setMinimumHeight(max(350,len(self.panels)*260+36));return
        if graph=='scatter' and 'series' in r:
            raw=r['series']
            if not isinstance(raw,list) or not 1<=len(raw)<=20: raise ValueError('Scatterplots require 1 to 20 series.')
            series=[]; xs=[]; ys=[]
            for item in raw:
                a,b=_values(item['x']),_values(item['y'])
                if not a or len(a)!=len(b) or any(v is None for v in a+b) or type(item['connect']) is not bool:
                    raise ValueError('Scatterplot series must have paired finite coordinates.')
                fit=item.get('fit')
                if fit is not None:
                    fx,fy=_values(fit['x']),_values(fit['y'])
                    if len(fx)!=2 or len(fy)!=2 or any(v is None for v in fx+fy): raise ValueError('Invalid fitted line coordinates.')
                    fit={'x':fx,'y':fy}; xs+=fx; ys+=fy
                series.append(dict(x=a,y=b,label=str(item['label']),connect=item['connect'],fit=fit,row_indices=item.get('row_indices',[])))
                xs+=a; ys+=b
            self.panels=[dict(kind='multi_scatter',title='',xlabel=str(r['xlabel']),ylabel=str(r['ylabel']),
                              x=xs,y=ys,series=series,legend_title=r.get('group_variable') or '')]
            self.note='N '+str(r.get('count',''))+'   ·   N* '+str(r.get('missing',''))
            if r.get('connection_order'): self.note+='   ·   '+r['connection_order']+' order'
            self.setMinimumHeight(max(350,100+len(series)*25)); return
        if graph=='normal_probability':
            data=r['graph_data']; xs=_values(data['observed']); ys=_values(data['normal_scores'])
            rx=_values(data['reference_x']); ry=_values(data['reference_y'])
            if len(xs)!=len(ys) or not xs or len(rx)!=2 or len(ry)!=2 or any(v is None for v in xs+ys+rx+ry):
                raise ValueError('Normal probability plot coordinates must be paired and finite.')
            self.panels=[dict(kind='normal_probability',title='Normal probability plot',xlabel=str(r.get('variable','Value')),
                              ylabel='Percent',x=xs,y=ys,reference_x=rx,reference_y=ry)]
            stat_lbl = r.get('statistic_name') or 'AD'
            stat_val = r.get('statistic', r.get('anderson_darling'))
            self.note = stat_lbl + ' ' + _fmt(stat_val) + '   ·   P ' + (_fmt(r['p_value']) if r.get('p_value') is not None else 'outside approximation range')
            return
        if graph in ('histogram','scatter','boxplot'):
            data=r.get('graph_data',r.get('data'))
            panel=dict(kind=graph,title='',xlabel=str(r.get('xlabel','Value')),ylabel=str(r.get('ylabel','')))
            if graph=='histogram':
                edges,counts=data;edges=_values(edges);counts=_values(counts)
                if len(edges)!=len(counts)+1 or not counts or any(v is None for v in edges+counts) or any(v<0 for v in counts) or any(b<=a for a,b in zip(edges,edges[1:])):
                    raise ValueError('Histogram edges must increase and match nonnegative counts.')
                panel.update(edges=edges,counts=counts,curves=[],specs=[],ylabel=panel['ylabel'] or 'Frequency')
            elif graph=='scatter':
                points=[(_number(row[0]),_number(row[1])) for row in data if row[0] is not None and row[1] is not None]
                if not points:raise ValueError('Scatterplot has no complete finite pairs.')
                panel.update(x=[p[0] for p in points],y=[p[1] for p in points],row_indices=r.get('plot_rows',[]))
            else:
                box={k:_number(data[k]) for k in ('low','q1','median','q3','high')}
                if not box['low']<=box['q1']<=box['median']<=box['q3']<=box['high']:
                    raise ValueError('Boxplot bounds must be ordered.')
                panel.update(box=box,outliers=[_number(v) for v in data.get('outliers',[])])
            self.panels=[panel];self.note=str(r.get('convention',''));return
        if 'xbar_center' in r:
            for title,key,prefix in [('Xbar','means','xbar'),('Range','ranges','r')]:
                self.panels.append(self._line_panel(title,r[key],r[prefix+'_center'],r[prefix+'_lcl'],r[prefix+'_ucl'],r.get(prefix+'_signals',[]),title))
        elif 'i_center' in r:
            for title,key,prefix in [('Individuals','observations','i'),('Moving range','moving_ranges','mr')]:
                self.panels.append(self._line_panel(title,r[key],r[prefix+'_center'],r[prefix+'_lcl'],r[prefix+'_ucl'],r.get(prefix+'_signals',[]),title))
        elif r.get('chart') in ('P','U'):
            self.panels=[self._line_panel(r['chart']+' chart',r['observations'],r.get('center_line',r['center']),r['lcl'],r['ucl'],r.get('signals',[]),'Proportion' if r['chart']=='P' else 'Defects per unit')]
        elif 'within_stdev' in r and 'overall_stdev' in r and 'observations' in r:
            edges,counts=self._histogram(r['observations']);mean=_number(r['mean'])
            sigmas=[_number(r[k]) for k in ('within_stdev','overall_stdev')]
            if any(s<=0 for s in sigmas):raise ValueError('Normal curves require positive standard deviations.')
            specs=[(label,_number(r[key])) for key,label in [('lsl','LSL'),('usl','USL'),('target','Target')] if r.get(key) is not None]
            bounds=edges+[mean-4*max(sigmas),mean+4*max(sigmas)]+[v for _,v in specs]
            lo,hi=min(bounds),max(bounds);span=hi-lo
            if not math.isfinite(span) or span<=0:raise ValueError('Capability range exceeds plotting precision.')
            xs=[lo+span*i/160 for i in range(161)];curves=[];width=edges[1]-edges[0]
            for label,sigma,color in zip(('Within normal','Overall normal'),sigmas,('#b97a36',BLUE)):
                ys=[math.exp(-.5*((x-mean)/sigma)**2)/math.sqrt(2*math.pi)/sigma*sum(counts)*width for x in xs]
                curves.append((label,xs,ys,color))
            self.panels=[dict(kind='histogram',title='Normal capability',xlabel=str(r.get('variable','Value')),ylabel='Frequency',edges=edges,counts=counts,curves=curves,specs=specs)]
            self.note='   ·   '.join(k.upper()+' '+_fmt(r[k]) for k in ('cp','cpk','pp','ppk') if r.get(k) is not None)
        elif 'fitted' in r and 'residuals' in r:
            if len(r['fitted'])!=len(r['residuals']):raise ValueError('Fitted values and residuals must be paired.')
            self.panels=[dict(kind='scatter',title='Residuals versus fitted values',x=_values(r['fitted']),y=_values(r['residuals']),xlabel='Fitted value',ylabel='Residual',zero=True)]
        if self.panels and not self.note:
            self.note='Three-sigma limits · Red points: Test 1 signals · Missing observations retain gaps' if any(p['kind']=='line' for p in self.panels) else ''

    def _bounds(self,values,zero=False):
        values=[_number(v) for v in values if v is not None]
        if not values:raise ValueError('No finite plotting range.')
        lo,hi=min(values),max(values)
        if zero:lo=min(0,lo)
        if lo==hi:
            delta=max(.5,abs(lo)*.04);lo-=delta;hi+=delta
        else:
            pad=(hi-lo)*.06;lo=lo if zero and lo==0 else lo-pad;hi+=pad
        if not all(math.isfinite(v) for v in (lo,hi,hi-lo)) or hi<=lo:
            raise ValueError('Plot range exceeds supported numeric precision.')
        return lo,hi

    def _text(self,p,rect,text,color=MUTED,align=Qt.AlignmentFlag.AlignCenter):
        p.setPen(QColor(color));p.drawText(rect,align,str(text))

    def _axes(self,p,area,xb,yb,xlabel,ylabel,box=False,integer=False,probability=False,categories=None,y_categories=None,nice_ticks=False,frequency=False):
        labels=getattr(self,'annotation_axes',{});positions=getattr(self,'annotation_positions',{})
        limits=getattr(self,'annotation_limits',{})
        limits=dict(limits,**getattr(self,'panel_annotation_limits',{}).get(self._panel_index,{}))
        zlimits=getattr(self,'_zoom2d_limits',{}).get(self._panel_index,{})
        if zlimits:
            limits.update(zlimits)
        xb=limits.get('x',xb);yb=limits.get('y',yb)
        xlabel=labels.get('x',xlabel);ylabel=labels.get('y',ylabel)
        if nice_ticks:
            from .plot_ticks import nice_limits
            if 'x' not in limits and not categories:xb=nice_limits(*xb)
            if 'y' not in limits and not probability and not y_categories:yb=nice_limits(*yb,integer=frequency)
        extra=max((label.count('\n')*16 for label in categories),default=0) if categories else 0
        left_margin=max(76,min(260,max((len(label)*6+30 for _,label in y_categories),default=76))) if y_categories else 76
        plot=QRectF(area.left()+left_margin,area.top()+28,max(20,area.width()-left_margin-105),max(20,area.height()-92-extra))
        x_log = bool(getattr(self, 'annotation_x_log', False)) and not categories and not box and xb[0] > 0 and xb[1] > 0
        y_log = bool(getattr(self, 'annotation_y_log', False)) and not y_categories and not probability and yb[0] > 0 and yb[1] > 0
        if hasattr(self, '_zoom2d_meta'):
            self._zoom2d_meta[self._panel_index] = {
                'plot': QRectF(plot),
                'xb': (float(xb[0]), float(xb[1])),
                'yb': (float(yb[0]), float(yb[1])),
                'x_log': x_log,
                'y_log': y_log,
                'interactive': (not categories) and (not y_categories) and (not box) and (not probability) and (xb[1] > xb[0]) and (yb[1] > yb[0]),
            }
        if x_log:
            _lx0, _lx1 = math.log10(xb[0]), math.log10(xb[1])
            _xspan = max(1e-12, _lx1 - _lx0)
            x = lambda v, _lx0=_lx0, _xspan=_xspan, _p=plot: _p.left() + (math.log10(max(v, 1e-12)) - _lx0) / _xspan * _p.width()
        else:
            x=lambda v:plot.left()+(v-xb[0])/(xb[1]-xb[0])*plot.width()
        if y_log:
            _ly0, _ly1 = math.log10(yb[0]), math.log10(yb[1])
            _yspan = max(1e-12, _ly1 - _ly0)
            y = lambda v, _ly0=_ly0, _yspan=_yspan, _p=plot: _p.bottom() - (math.log10(max(v, 1e-12)) - _ly0) / _yspan * _p.height()
        else:
            y=lambda v:plot.bottom()-(v-yb[0])/(yb[1]-yb[0])*plot.height()
        self.remember_axes(plot)
        axis=self.graph_style('axis',color=MUTED,line_width=1,visible=True)
        grid=self.graph_style('grid',color='#e9edf0',line_width=1,visible=True)
        p.setFont(QFont('Segoe UI',9))
        ticks = max(2, min(6, int(plot.height()/26)+1))
        if nice_ticks:
            from .plot_ticks import tick_values
            xvalues=tick_values(*xb,count=ticks,integer=integer)
            yvalues=([NormalDist().inv_cdf(value/100) for value in (.1,1,10,50,90,99,99.9) if yb[0]<=NormalDist().inv_cdf(value/100)<=yb[1]] if probability else tick_values(*yb,count=ticks,integer=frequency))
        else:
            xvalues=[xb[0]+(xb[1]-xb[0])*i/(ticks-1) for i in range(ticks)]
            yvalues=[yb[0]+(yb[1]-yb[0])*i/(ticks-1) for i in range(ticks)]
        for yv in yvalues:
            if getattr(self,'annotation_grid',True) and grid['visible'] and not y_categories:
                p.setPen(style_pen(grid));p.drawLine(QPointF(plot.left(),y(yv)),QPointF(plot.right(),y(yv)))
            if not box and not y_categories and axis['visible']:self._text(p,QRectF(area.left()+4,y(yv)-9,62,18),format(100*NormalDist().cdf(yv),'.3g') if probability else _fmt(yv),color=axis['color'],align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        for xv in xvalues:
            label=str(round(xv)) if integer else _fmt(xv)
            if axis['visible'] and not categories:self._text(p,QRectF(x(xv)-42,plot.bottom()+7,84,20),label,axis['color'])
        if axis['visible'] and y_categories:
            for position,label in y_categories:self._text(p,QRectF(area.left()+22,y(position)-10,left_margin-30,20),p.fontMetrics().elidedText(label,Qt.TextElideMode.ElideRight,left_margin-30),axis['color'],Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        if axis['visible'] and categories:
            width=max(30,plot.width()/len(categories))
            for index,label in enumerate(categories):self._text(p,QRectF(x(index+1)-width/2,plot.bottom()+7,width,20+extra),label,axis['color'])
        if axis['visible']:
            p.setPen(style_pen(axis));p.drawLine(plot.bottomLeft(),plot.bottomRight());p.drawLine(plot.topLeft(),plot.bottomLeft())
        if axis['visible'] and positions.get('x')!='off':self._text(p,QRectF(plot.left(),area.top() if positions.get('x')=='high' else plot.bottom()+34+extra,plot.width(),22),xlabel,axis['color'])
        if axis['visible'] and ylabel and positions.get('y')!='off':
            p.save();p.translate(area.right()-12 if positions.get('y')=='high' else area.left()+14,plot.center().y());p.rotate(-90)
            self._text(p,QRectF(-plot.height()/2,-10,plot.height(),20),ylabel,axis['color']);p.restore()
        return plot,x,y

    def _path(self,p,xs,ys,x,y,color,width=1.5,dashed=False,style=None,target=None):
        settings=dict(color=color,line_width=width,line_style='dash' if dashed else 'solid',visible=True)
        settings.update(style or {})
        if not settings['visible'] or settings['line_style']=='none':return
        path=QPainterPath();active=False
        for xv,yv in zip(xs,ys):
            if xv is None or yv is None:active=False;continue
            point=QPointF(x(xv),y(yv))
            if active:path.lineTo(point)
            else:path.moveTo(point);active=True
        pen=style_pen(dict(settings,edge=settings['color']))
        p.setPen(pen);p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path)
        if target:self.remember_path(target,[None if a is None or b is None else QPointF(x(a),y(b)) for a,b in zip(xs,ys)])

    def _draw_panel(self,p,area,d):
        p.setFont(QFont('Segoe UI',10,QFont.Weight.DemiBold))
        self._text(p,QRectF(area.left()+76,area.top(),area.width()-100,22),d['title'],INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        kind=d['kind']
        if kind in ('model_main_effects','model_interaction','model_contour','model_surface'):
            from .model_plots_chart import draw_panel
            draw_panel(self,p,area,d);return
        if kind == 'phase6_chart':
            from .phase6_charts import draw_panel
            draw_panel(self, p, area, d)
            return
        if kind == 'subgroup_control':
            from .subgroup_control_chart import draw_panel
            draw_panel(self, p, area, d)
            return
        if str(kind).startswith('oneway_'):
            from .oneway_chart import draw_panel
            draw_panel(self, p, area, d)
            return
        if str(kind).startswith('twoway_'):
            from .twoway_anova_chart import draw_panel as draw_twoway_panel
            draw_twoway_panel(self, p, area, d)
            return
        if str(kind) in ('main_effects_plot', 'interactions_plot'):
            from .anova_plots_chart import draw_panel as draw_anova_panel
            draw_anova_panel(self, p, area, d)
            return
        if kind == 'equal_variances':
            from .equal_variances_chart import draw_equal_variances_panel
            draw_equal_variances_panel(p, area.toRect(), self.entry)
            return
        if kind == 'two_variances':
            from .two_variances_charts import draw_two_variances_panel
            draw_two_variances_panel(p, area.toRect(), self.entry)
            return
        if kind == 'one_sample_z':
            from .one_sample_z_chart import draw_one_sample_z_panel
            draw_one_sample_z_panel(p, area.toRect(), self.entry.get('result', {}), self.entry.get('title'))
            return
        if kind == 'one_sample_t':
            from .one_sample_t_chart import draw_one_sample_t_panel
            draw_one_sample_t_panel(p, area.toRect(), self.entry.get('result', {}), self.entry.get('title'))
            return
        if kind == 'paired_t':
            from .paired_t_chart import draw_paired_t_panel
            draw_paired_t_panel(p, area.toRect(), self.entry.get('result', {}), self.entry.get('title'))
            return
        if kind == 'two_sample_t':
            from .two_sample_t_chart import draw_two_sample_t_panel
            draw_two_sample_t_panel(p, area.toRect(), self.entry.get('result', {}), self.entry.get('title'))
            return
        if kind=='optimization_plot':
            from .optimizer_chart import draw_panel
            draw_panel(self,p,area,d);return
        if kind=='gage_rr':
            from .gage_rr_chart import draw_panel
            draw_panel(self,p,area,d);return
        if kind=='categorical_points':
            from .categorical_points_chart import draw_categorical_points
            draw_categorical_points(self,p,area,d);return
        if kind=='dotplot_groups':
            from .dotplot_chart import draw_dotplot_groups
            draw_dotplot_groups(self,p,area,d);return
        if kind=='boxplot_groups':
            from .boxplot_chart import draw_boxplot_groups
            draw_boxplot_groups(self,p,area,d);return
        if kind=='histogram_groups':
            from .histogram_chart import draw_histogram_groups
            draw_histogram_groups(self,p,area,d);return
        if kind=='histogram':
            xv=d['edges']+[v for _,xs,_,_ in d['curves'] for v in xs]+[v for _,v in d['specs']]
            yv=d['counts']+[v for _,_,ys,_ in d['curves'] for v in ys]
            xb=self._bounds(xv);yb=self._bounds(yv,True)
        elif kind=='boxplot':xb=self._bounds(list(d['box'].values())+d['outliers']);yb=(0,1)
        else:
            xb=self._bounds(d['x']);yv=d['y']+[v for _,ys,_ in d.get('lines',[]) for v in ys]+d.get('reference_y',[])
            if d.get('zero'):yv=yv+[0]
            yb=self._bounds(yv)
        if d.get('positive_order') and d.get('x'):
            maximum=max(d['x']);xb=(0.,maximum+max(1.,maximum*.04))
        plot,x,y=self._axes(p,area,xb,yb,d['xlabel'],d['ylabel'],kind=='boxplot',kind=='line',kind=='normal_probability',nice_ticks=d.get('nice_axes',False),frequency=d.get('frequency_ticks',False))
        p.save();p.setClipRect(plot.adjusted(-1,-1,1,1))
        if kind=='multi_scatter':
            colors=['#3e739b','#b46e39','#53856e','#9266a5','#b6485a','#628d9a','#858446','#766459']
            for index,series in enumerate(d['series']):
                color=colors[index%len(colors)]
                name='s'+str(index);style=self.graph_style(name,color=color)
                if not style.get('visible',True) or self.is_series_legend_hidden(self._panel_index,index):continue
                if series['connect']: self._path(p,series['x'],series['y'],x,y,color,1.5,style=style,target=name)
                if series['fit']: self._path(p,series['fit']['x'],series['fit']['y'],x,y,color,1.7,style=self.graph_style('fit'+str(index),color=color),target='fit'+str(index))
                for point_index,(a,b) in enumerate(zip(series['x'],series['y'])):
                    rows=series.get('row_indices',[]);row=rows[point_index] if point_index<len(rows) else None
                    self._marker(p,QPointF(x(a),y(b)),color,index,style,name,row,point_info(a,b,d['xlabel'],d['ylabel'],series.get('label',''),row),label_val=_fmt(b))
        elif kind=='histogram':
            style=self.graph_style('bars',fill='#a7bfd2',edge='#ffffff',line_width=1)
            p.setPen(style_pen(style));p.setBrush(style_color(style['fill'],style.get('opacity',1)))
            if style.get('visible',True):
                for i,v in enumerate(d['counts']):
                    rect=QRectF(QPointF(x(d['edges'][i]),y(v)),QPointF(x(d['edges'][i+1]),y(0))).normalized()
                    p.drawRect(rect);self.remember_rect('bars',rect)
                    if getattr(self, 'annotation_data_labels', False) and v > 0:
                        self._text(p, QRectF(rect.left(), rect.top() - 16, rect.width(), 15), str(v), INK)
                    source=self.result.get('histogram_source',self.result.get('observations'))
                    if not isinstance(source,(list,tuple)) or any(isinstance(v,(list,dict)) for v in source):source=None
                    self.remember_hover(rect,histogram_info(d['edges'][i],d['edges'][i+1],v,d.get('ylabel','Frequency'),source=source,last=i==len(d['counts'])-1))
            for index,(_,xs,ys,color) in enumerate(d['curves']):self._path(p,xs,ys,x,y,color,2,style=self.graph_style('fit'+str(index)),target='fit'+str(index))
            for _,v in d['specs']:
                pen=QPen(QColor(RED),1.4,Qt.PenStyle.DashLine);p.setPen(pen);p.drawLine(QPointF(x(v),plot.top()),QPointF(x(v),plot.bottom()))
        elif kind=='boxplot':
            style=self.graph_style('box',color=BLUE,fill='#c2d4e1',line_width=1.7)
            if not style.get('visible',True):p.restore();return
            b=d['box'];middle=plot.center().y();p.setPen(style_pen(style));p.setBrush(style_color(style['fill'],style.get('opacity',1)))
            p.drawLine(QPointF(x(b['low']),middle),QPointF(x(b['high']),middle))
            for v in (b['low'],b['high']):p.drawLine(QPointF(x(v),middle-16),QPointF(x(v),middle+16))
            p.drawRect(QRectF(x(b['q1']),middle-32,x(b['q3'])-x(b['q1']),64))
            p.drawLine(QPointF(x(b['median']),middle-32),QPointF(x(b['median']),middle+32))
            self.remember_rect('box',QRectF(x(b['low'])-5,middle-35,x(b['high'])-x(b['low'])+10,70))
            self.remember_hover(QRectF(x(b['low'])-5,middle-35,x(b['high'])-x(b['low'])+10,70),summary_info('boxplot',[(key,b[key]) for key in ('low','q1','median','q3','high')]))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for v in d['outliers']:draw_marker(p,QPointF(x(v),middle),style)
        else:
            if kind=='normal_probability':self._path(p,d['reference_x'],d['reference_y'],x,y,RED,1.5,style=self.graph_style('fit0'),target='fit0')
            for index,(_,ys,color) in enumerate(d.get('lines',[])):self._path(p,d['x'],ys,x,y,color,1.2,True,style=self.graph_style('ref'+str(index)),target='ref'+str(index))
            if d.get('zero'):self._path(p,[xb[0],xb[1]],[0,0],x,y,GREEN,1.2,True)
            if kind=='line':self._path(p,d['x'],d['y'],x,y,BLUE,1.6,style=self.graph_style('s0'),target='s0')
            for i,(a,b) in enumerate(zip(d['x'],d['y']),1):
                if a is None or b is None:continue
                color=RED if i in d.get('signals',()) else BLUE
                rows=d.get('row_indices',[]);row=rows[i-1] if i-1<len(rows) else None
                shown_y=100*NormalDist().cdf(b) if kind=='normal_probability' else b
                self._marker(p,QPointF(x(a),y(b)),color,0,self.graph_style('s0',color=color),'s0',row,point_info(a,shown_y,d['xlabel'],d['ylabel'],row=row),label_val=_fmt(shown_y))
        self._draw_reference_overlays(p, plot, x, y, d)
        p.restore();p.setFont(QFont('Segoe UI',9))
        if kind=='multi_scatter' and (d['legend_title'] or len(d['series']) > 1):
            if d['legend_title']:
                self._text(p,QRectF(plot.right()+10,plot.top()-24,94,24),p.fontMetrics().elidedText(d['legend_title'],Qt.TextElideMode.ElideRight,90),INK)
            colors=['#3e739b','#b46e39','#53856e','#9266a5','#b6485a','#628d9a','#858446','#766459']
            for index,series in enumerate(d['series']):
                style=self.graph_style('s'+str(index))
                if not style.get('legend_visible',True):continue
                yy=plot.top()+12+index*25; color=colors[index%len(colors)]
                leg_rect=QRectF(plot.right()+10,yy-11,98,22)
                self._legend_hit_rects[(self._panel_index, index)] = leg_rect
                hidden=self.is_series_legend_hidden(self._panel_index, index)
                marker_style=dict(style, opacity=(style.get('opacity', 1.0) * 0.3)) if hidden else style
                self._marker(p,QPointF(plot.right()+18,yy),color,index,marker_style)
                self.remember_rect('s'+str(index),leg_rect)
                text=p.fontMetrics().elidedText(series['label'],Qt.TextElideMode.ElideRight,76)
                if hidden:
                    p.save()
                    f=QFont(p.font()); f.setStrikeOut(True); p.setFont(f)
                    self._text(p,QRectF(plot.right()+28,yy-11,76,22),text,MUTED,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
                    p.restore()
                else:
                    self._text(p,QRectF(plot.right()+28,yy-11,76,22),text,INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        elif kind=='line':
            for i,(label,ys,color) in enumerate(d['lines']):
                style=self.graph_style('ref'+str(i),color=color)
                if not style.get('visible',True):continue
                vals=[v for v in ys if v is not None]
                value=_fmt(vals[-1]) if len(set(vals))==1 else 'varying'
                self._text(p,QRectF(plot.right()+12,plot.top()+i*39,85,34),label+'\n'+value,style['color'],Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        elif kind=='histogram':
            for i,(label,_,_,color) in enumerate(d['curves']):
                style=self.graph_style('fit'+str(i),color=color)
                if style.get('visible',True):self._text(p,QRectF(plot.right()+10,plot.top()+i*28,92,25),label,style['color'],Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            for i,(label,v) in enumerate(d['specs']):self._text(p,QRectF(plot.right()+10,plot.top()+70+i*25,92,25),label+' '+_fmt(v),RED,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)

    def _draw_reference_overlays(self, p, plot, x_fn, y_fn, panel):
        x_refs = getattr(self, 'annotation_x_ref', []) or []
        y_refs = list(getattr(self, 'annotation_y_ref', []) or [])
        mean_tag = None
        if getattr(self, 'annotation_mean_line', False):
            y_vals = []
            if panel.get('y'):
                y_vals.extend(v for v in panel['y'] if v is not None and isinstance(v, (int, float)) and math.isfinite(v))
            for s in panel.get('series', []):
                if isinstance(s, dict) and s.get('y'):
                    y_vals.extend(v for v in s['y'] if v is not None and isinstance(v, (int, float)) and math.isfinite(v))
            if y_vals:
                mean_val = sum(y_vals) / len(y_vals)
                y_refs.append(mean_val)
                mean_tag = mean_val
        if not x_refs and not y_refs:
            return
        p.setFont(QFont('Segoe UI', 8))
        for xv in x_refs:
            try:
                px = x_fn(xv)
            except Exception:
                continue
            if plot.left() - 2 <= px <= plot.right() + 2:
                pen = QPen(QColor('#0284c7'), 1.3, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(QPointF(px, plot.top()), QPointF(px, plot.bottom()))
                self._text(p, QRectF(px + 3, plot.top() + 2, 68, 16), f'Ref {_fmt(xv)}', '#0369a1', Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for idx, yv in enumerate(y_refs):
            try:
                py = y_fn(yv)
            except Exception:
                continue
            if plot.top() - 2 <= py <= plot.bottom() + 2:
                is_mean = (mean_tag is not None and idx == len(y_refs) - 1)
                col_hex = GREEN if is_mean else '#dc2626'
                lbl = f'Mean {_fmt(yv)}' if is_mean else f'Ref {_fmt(yv)}'
                pen = QPen(QColor(col_hex), 1.4, Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(QPointF(plot.left(), py), QPointF(plot.right(), py))
                self._text(p, QRectF(plot.left() + 4, py - 16, 90, 15), lbl, col_hex, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def _marker(self,p,point,color,index,style=None,target=None,row=None,information=None,label_val=None):
        settings=dict(color=color);settings.update(style or {})
        draw_marker(p,point,settings,('circle','square','triangle')[index%3])
        if label_val is not None and getattr(self, 'annotation_data_labels', False) and settings.get('visible', True):
            p.setFont(QFont('Segoe UI', 8))
            self._text(p, QRectF(point.x() - 24, point.y() - 18, 48, 14), str(label_val), INK)
        if target and settings.get('visible',True) and settings.get('marker')!='none':
            self.remember_marker(target,point,settings.get('marker_size',6.4),row)
            if information:self.remember_point_hover(point,information,settings.get('marker_size',6.4))

    def panel_areas(self):
        top=56 if self.title else 6
        columns=max(1,self.panel_columns);rows=max(1,math.ceil(len(self.panels)/columns))
        width=(self.width()-24)/columns;height=(self.height()-top-36)/rows
        return [QRectF(12+(i%columns)*width,top+(i//columns)*height,width,height) for i in range(len(self.panels))]


    def _has_3d_panel(self):
        return any(isinstance(p, dict) and p.get('kind') in ('model_surface', 'surface', 'scatter3d') for p in self.panels)

    def _has_contour_panel(self):
        return any(isinstance(p, dict) and p.get('kind') == 'model_contour' for p in self.panels)

    def set_cad_orientation(self, azimuth, elevation):
        curr = self.view_state
        self.view_state = view_state(
            azimuth,
            elevation,
            curr['zoom'],
            pan_x=curr.get('pan_x', 0.0),
            pan_y=curr.get('pan_y', 0.0),
        )
        self.update()

    def rotate_cad_view(self, dx, dy):
        curr = self.view_state
        px = curr.get('pan_x', 0.0)
        py = curr.get('pan_y', 0.0)
        self.view_state = view_state(
            curr['azimuth'] + dx,
            curr['elevation'] + dy,
            curr['zoom'],
            pan_x=px,
            pan_y=py,
        )
        self.update()

    def pan_cad_view(self, dx, dy):
        curr = self.view_state
        px = curr.get('pan_x', 0.0) + dx
        py = curr.get('pan_y', 0.0) + dy
        self.view_state = view_state(
            curr['azimuth'],
            curr['elevation'],
            curr['zoom'],
            pan_x=px,
            pan_y=py,
        )
        self.update()

    def zoom_cad_view(self, steps):
        curr = self.view_state
        px = curr.get('pan_x', 0.0)
        py = curr.get('pan_y', 0.0)
        new_zoom = curr['zoom'] * math.exp(max(-20.0, min(20.0, steps)) * 0.12)
        self.view_state = view_state(
            curr['azimuth'],
            curr['elevation'],
            new_zoom,
            pan_x=px,
            pan_y=py,
        )
        self.update()

    def reset_cad_view(self):
        self.view_state = dict(DEFAULT_VIEW)
        self.active_cad_card = None
        self.update()

    def _probe_surface_click(self, pos):
        for p in self.panels:
            if isinstance(p, dict) and p.get('kind') == 'model_surface' and p.get('surface_vertices'):
                verts = p['surface_vertices']
                best_v = None
                best_dist = 42.0
                for v in verts:
                    dist = math.hypot(v['pos'].x() - pos.x(), v['pos'].y() - pos.y())
                    if dist < best_dist:
                        best_dist = dist
                        best_v = v
                if best_v is not None:
                    pt = best_v['pt']
                    self.active_cad_card = {
                        'mode': 'probe_3d',
                        'x': pt[0],
                        'y': pt[1],
                        'fit': pt[2],
                    }
                    self.update()
                    return

    def _probe_contour_click(self, pos):
        for p in self.panels:
            if isinstance(p, dict) and p.get('kind') == 'model_contour' and 'plot_rect' in p:
                plot = p['plot_rect']
                if plot.contains(pos):
                    from .model_plots_chart import interpolate_contour_grid
                    x_lo, x_hi = p['x_lo'], p['x_hi']
                    y_lo, y_hi = p['y_lo'], p['y_hi']
                    tx = max(0.0, min(1.0, (pos.x() - plot.left()) / max(1e-12, plot.width())))
                    ty = max(0.0, min(1.0, (plot.bottom() - pos.y()) / max(1e-12, plot.height())))
                    x_val = x_lo + tx * (x_hi - x_lo)
                    y_val = y_lo + ty * (y_hi - y_lo)
                    z_fit = interpolate_contour_grid(p['x_grid'], p['y_grid'], p['z_grid'], x_val, y_val)
                    self.active_cad_card = {
                        'mode': 'probe_2d',
                        'x': x_val,
                        'y': y_val,
                        'fit': z_fit,
                    }
                    self.update()
                    return

    def is_series_legend_hidden(self, panel_idx, series_idx):
        return (int(panel_idx), int(series_idx)) in getattr(self, '_hidden_legend_series', set())

    def _has_2d_zoom(self):
        return bool(getattr(self, '_zoom2d_limits', None))

    def _has_2d_zoomable_panel(self):
        return any(m.get('interactive') for m in getattr(self, '_zoom2d_meta', {}).values())

    def reset_2d_zoom(self):
        self._zoom2d_limits = {}
        self._zoom2d_pan_start = None
        self._zoom2d_pan_panel = None
        self.update()

    def _zoom2d_panel_at(self, pos):
        for idx, meta in getattr(self, '_zoom2d_meta', {}).items():
            if meta.get('interactive') and meta.get('plot') and meta['plot'].contains(pos):
                return idx
        return None

    def _apply_2d_wheel_zoom(self, pos, steps):
        idx = self._zoom2d_panel_at(pos)
        if idx is None:
            interactive_keys = [k for k, m in getattr(self, '_zoom2d_meta', {}).items() if m.get('interactive')]
            if len(interactive_keys) == 1:
                idx = interactive_keys[0]
            else:
                return False
        meta = self._zoom2d_meta.get(idx)
        if not meta or not meta.get('interactive'):
            return False
        plot = meta['plot']
        xb = self._zoom2d_limits.get(idx, {}).get('x', meta['xb'])
        yb = self._zoom2d_limits.get(idx, {}).get('y', meta['yb'])
        scale = max(0.2, min(5.0, 0.85 ** float(steps)))
        fx = max(0.0, min(1.0, (pos.x() - plot.left()) / max(1e-9, plot.width())))
        fy = max(0.0, min(1.0, (plot.bottom() - pos.y()) / max(1e-9, plot.height())))

        def _zoom_axis(bounds, frac, is_log):
            lo, hi = float(bounds[0]), float(bounds[1])
            if hi <= lo:
                return bounds
            if is_log and lo > 0 and hi > 0:
                llo, lhi = math.log10(lo), math.log10(hi)
                lspan = max(1e-12, lhi - llo)
                anchor = llo + frac * lspan
                new_span = max(1e-6, lspan * scale)
                nlo = anchor - frac * new_span
                nhi = nlo + new_span
                return (10 ** nlo, 10 ** nhi)
            span = max(1e-12, hi - lo)
            anchor = lo + frac * span
            new_span = max(1e-9, span * scale)
            nlo = anchor - frac * new_span
            nhi = nlo + new_span
            return (nlo, nhi)

        nx = _zoom_axis(xb, fx, meta.get('x_log', False))
        ny = _zoom_axis(yb, fy, meta.get('y_log', False))
        self._zoom2d_limits[idx] = {'x': nx, 'y': ny}
        self.update()
        return True

    def _pan_2d_panel(self, panel_idx, dx_px, dy_px):
        meta = getattr(self, '_zoom2d_meta', {}).get(panel_idx)
        if not meta or not meta.get('interactive'):
            return False
        plot = meta['plot']
        xb = self._zoom2d_limits.get(panel_idx, {}).get('x', meta['xb'])
        yb = self._zoom2d_limits.get(panel_idx, {}).get('y', meta['yb'])
        dfx = -float(dx_px) / max(1e-9, plot.width())
        dfy = float(dy_px) / max(1e-9, plot.height())

        def _shift(bounds, df, is_log):
            lo, hi = float(bounds[0]), float(bounds[1])
            if is_log and lo > 0 and hi > 0:
                llo, lhi = math.log10(lo), math.log10(hi)
                shift = df * (lhi - llo)
                return (10 ** (llo + shift), 10 ** (lhi + shift))
            shift = df * (hi - lo)
            return (lo + shift, hi + shift)

        self._zoom2d_limits[panel_idx] = {
            'x': _shift(xb, dfx, meta.get('x_log', False)),
            'y': _shift(yb, dfy, meta.get('y_log', False)),
        }
        self.update()
        return True

    def mousePressEvent(self, event):
        self._hide_hover()
        pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            if self._reset_zoom_rect is not None and self._reset_zoom_rect.contains(pos):
                self.reset_2d_zoom()
                event.accept()
                return
            for (p_idx, s_idx), lrect in list(getattr(self, '_legend_hit_rects', {}).items()):
                if lrect.contains(pos):
                    key = (p_idx, s_idx)
                    if key in self._hidden_legend_series:
                        self._hidden_legend_series.remove(key)
                    else:
                        self._hidden_legend_series.add(key)
                    self.update()
                    event.accept()
                    return
        if not self._has_3d_panel() and (
            event.button() == Qt.MouseButton.MiddleButton
            or (event.button() == Qt.MouseButton.LeftButton and bool(event.modifiers() & Qt.KeyboardModifier.AltModifier))
        ):
            p_idx = self._zoom2d_panel_at(pos)
            if p_idx is not None:
                self._zoom2d_pan_start = pos
                self._zoom2d_pan_panel = p_idx
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        target = self.object_at(pos)

        if target and target.startswith('viewcube_'):
            self._viewcube_drag_start = pos
            self._viewcube_target = target
            self._viewcube_moved = False
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if target == 'cad_hud_reset_3d':
            self.reset_cad_view()
            event.accept()
            return
        elif target in ('cad_hud_peak_3d', 'cad_peak_3d'):
            self.active_cad_card = {'mode': 'peak_3d'}
            self.update()
            event.accept()
            return
        elif target in ('cad_hud_min_3d', 'cad_min_3d'):
            self.active_cad_card = {'mode': 'min_3d'}
            self.update()
            event.accept()
            return
        elif target in ('cad_hud_peak_2d', 'cad_peak_2d'):
            self.active_cad_card = {'mode': 'peak_2d'}
            self.update()
            event.accept()
            return
        elif target in ('cad_hud_min_2d', 'cad_min_2d'):
            self.active_cad_card = {'mode': 'min_2d'}
            self.update()
            event.accept()
            return

        if self._has_3d_panel():
            # OnShape standard CAD mouse controls:
            # 1. Middle-click drag (Scroll wheel press) OR Ctrl + Right-click drag: Pan
            is_pan = (
                event.button() == Qt.MouseButton.MiddleButton
                or (event.button() == Qt.MouseButton.RightButton and bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
                or (event.button() == Qt.MouseButton.LeftButton and bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            )
            if is_pan:
                self._pan_start = pos
                self._drag_moved = False
                self._is_dragging = True
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                event.accept()
                return

            # 2. Right-click drag (without Ctrl): Orbit / Rotate
            if event.button() == Qt.MouseButton.RightButton:
                self._orbit_start = pos
                self._drag_start_pos = pos
                self._drag_moved = False
                self._is_dragging = True
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return

            # 3. Left-click: Probe surface point without rotating
            if event.button() == Qt.MouseButton.LeftButton:
                for p in self.panels:
                    if isinstance(p, dict) and p.get('kind') in ('model_surface', 'surface', 'scatter3d'):
                        cube = p.get('cube_rect')
                        if cube and cube.contains(pos):
                            self._probe_surface_click(pos)
                            event.accept()
                            return

        if self._has_contour_panel() and event.button() == Qt.MouseButton.LeftButton:
            for p in self.panels:
                if isinstance(p, dict) and p.get('kind') == 'model_contour':
                    plot = p.get('plot_rect')
                    if plot and plot.contains(pos):
                        self._probe_contour_click(pos)
                        event.accept()
                        return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, '_zoom2d_pan_start', None) is not None and getattr(self, '_zoom2d_pan_panel', None) is not None:
            pos = event.position()
            delta = pos - self._zoom2d_pan_start
            self._zoom2d_pan_start = pos
            self._pan_2d_panel(self._zoom2d_pan_panel, delta.x(), delta.y())
            event.accept()
            return
        pos = event.position()
        if getattr(self, '_viewcube_drag_start', None) is not None:
            dx = pos.x() - self._viewcube_drag_start.x()
            dy = pos.y() - self._viewcube_drag_start.y()
            if abs(dx) > 1.5 or abs(dy) > 1.5 or getattr(self, '_viewcube_moved', False):
                self._viewcube_moved = True
                self._viewcube_drag_start = pos
                self.rotate_cad_view(-dx * 0.65, dy * 0.65)
                event.accept()
                return
        if self._pan_start is not None:
            delta = pos - self._pan_start
            self._pan_start = pos
            self._drag_moved = True
            self.pan_cad_view(delta.x(), delta.y())
            event.accept()
            return

        if self._orbit_start is not None:
            delta = pos - self._orbit_start
            self._orbit_start = pos
            if abs(delta.x()) > 0.5 or abs(delta.y()) > 0.5:
                self._drag_moved = True
            # OnShape standard orbit:
            # Moving mouse right (delta.x > 0) turns model right (azimuth decreases)
            # Moving mouse up (delta.y < 0) tilts model down / camera moves up (elevation increases)
            self.rotate_cad_view(-delta.x() * 0.5, delta.y() * 0.5)
            event.accept()
            return

        if self._has_3d_panel():
            is_near = (pos.x() >= self.width() - 110 and pos.y() <= 200)
            if is_near != getattr(self, '_cad_hint_visible', False):
                self._cad_hint_visible = is_near
                self.update()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, '_zoom2d_pan_start', None) is not None:
            self._zoom2d_pan_start = None
            self._zoom2d_pan_panel = None
            self.unsetCursor()
            event.accept()
            return
        pos = event.position()
        if getattr(self, '_viewcube_drag_start', None) is not None:
            target = self._viewcube_target
            moved = getattr(self, '_viewcube_moved', False)
            self._viewcube_drag_start = None
            self._viewcube_target = None
            self._viewcube_moved = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if not moved and target:
                from .native_output_chart import handle_viewcube_action
                handle_viewcube_action(self, target)
            self.update()
            event.accept()
            return
        if self._pan_start is not None:
            self._pan_start = None
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            event.accept()
            return

        if self._orbit_start is not None:
            self._orbit_start = None
            self._is_dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if self._has_3d_panel():
            steps = event.angleDelta().y() / 120.0
            if steps:
                self.zoom_cad_view(steps)
                event.accept()
                return
        elif self._has_2d_zoomable_panel() and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            steps = event.angleDelta().y() / 120.0
            if steps and self._apply_2d_wheel_zoom(event.position(), steps):
                event.accept()
                return
        super().wheelEvent(event)

    def contextMenuEvent(self, event):
        if self._has_3d_panel():
            event.accept()
            return
        super().contextMenuEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._has_3d_panel():
            self.reset_cad_view()
            event.accept()
            return
        if self._has_2d_zoom() and self._zoom2d_panel_at(event.position()) is not None and self.object_at(event.position()) in (None, 'grid'):
            self.reset_2d_zoom()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self,event):
        self.reset_hover_regions()
        self.hit_regions=[]
        self.brush_regions=[]
        self._zoom2d_meta = {}
        self._legend_hit_rects = {}
        self._reset_zoom_rect = None
        p=chart_painter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor('white'))
        p.setFont(QFont('Segoe UI',13,QFont.Weight.DemiBold))
        title=p.fontMetrics().elidedText(self.title,Qt.TextElideMode.ElideRight,max(80,self.width()-44))
        self._text(p,QRectF(22,14,self.width()-44,30),title,INK,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
        try:
            if not self.panels:
                p.setFont(QFont('Segoe UI',10));self._text(p,QRectF(35,70,self.width()-70,self.height()-110),self.error or 'This result has no chart.',MUTED)
            else:
                for i,(d,area) in enumerate(zip(self.panels,self.panel_areas())):
                    self._panel_index=i;self._draw_panel(p,area,d)
                self.draw_selection(p)
                if self._has_2d_zoom() and not getattr(self, '_exporting', False):
                    btn = QRectF(max(24.0, self.width() - 106.0), 16.0, 84.0, 22.0)
                    self._reset_zoom_rect = btn
                    p.save()
                    p.setPen(QPen(QColor('#94a3b8'), 1))
                    p.setBrush(QColor('#f1f5f9'))
                    p.drawRoundedRect(btn, 4, 4)
                    p.setFont(QFont('Segoe UI', 8, QFont.Weight.DemiBold))
                    self._text(p, btn, 'Reset Zoom', INK)
                    p.restore()
                p.setFont(QFont('Segoe UI',9))
                note=p.fontMetrics().elidedText(self.note,Qt.TextElideMode.ElideRight,max(80,self.width()-44))
                self._text(p,QRectF(22,self.height()-29,self.width()-44,21),note)
        except (ValueError,OverflowError,TypeError,IndexError,KeyError) as exc:
            self.error=str(exc)
            p.fillRect(QRectF(12,54,self.width()-24,self.height()-65),QColor('white'))
            p.setFont(QFont('Segoe UI',10));self._text(p,QRectF(30,70,self.width()-60,self.height()-100),'Plot unavailable: '+str(exc))
        finally:p.end()

