"""Dynamic Taguchi main effects and optional measured response-versus-signal panels."""
import math
from .doe_analysis_charts import TaguchiEffectsWidget
from .modern_charts import ChartWidget,RED


class DynamicTaguchiWidget(TaguchiEffectsWidget):
    def _prepare(self):
        super()._prepare()
        self.signal_panel_count=0
        rows=self.result.get('rows',[])
        if self.result.get('options',{}).get('show_signal_plots',False):
            for row in rows[:24]:
                signals=row['signal_values'];order=sorted(range(len(signals)),key=signals.__getitem__)
                xs=[signals[i] for i in order];ys=[row['responses'][i] for i in order]
                fits=[row['fitted'][i] for i in order]
                self.panels.append(dict(kind='scatter',metric='signal',dynamic_signal=True,
                    title='Response versus Signal: Row '+str(row['row']+1),
                    x=xs,y=ys,row_indices=[row['row']+1]*len(xs),xlabel='Signal',ylabel='Response',
                    lines=[('Fitted response',fits,RED)]))
                self.signal_panel_count+=1
        self.panel_columns=min(3,max(len(self.result.get('factor_indices',[])),2 if self.signal_panel_count else 1))
        self.setMinimumSize(max(720,self.panel_columns*360),max(360,math.ceil(len(self.panels)/self.panel_columns)*300+60))
        if self.signal_panel_count:
            self.note='Level averages with grand means; response-versus-signal panels show measured values and fitted lines.'
            if len(rows)>24:self.note='Response-versus-signal plots show the first 24 of '+str(len(rows))+' complete runs; all runs enter the analysis.'

    def _draw_panel(self,painter,area,panel):
        if panel.get('dynamic_signal'):
            return ChartWidget._draw_panel(self,painter,area,panel)
        return super()._draw_panel(painter,area,panel)

