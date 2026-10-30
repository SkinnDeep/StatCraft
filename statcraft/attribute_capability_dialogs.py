"""Original form based on documented capability inputs, not recovered native geometry."""
import math
from .variable_dialogs import ProcedureDialog, resolve_variables


class AttributeCapabilityDialog(ProcedureDialog):
    def __init__(self, parent, worksheet, method='binomial'):
        if method not in ('binomial', 'poisson'):
            raise ValueError('Choose Binomial or Poisson capability.')
        self.method = method
        binomial = method == 'binomial'
        super().__init__(parent, method.title()+' Capability Analysis', worksheet,
            selectors=(
                {'key':'count_index', 'label':'Defectives:' if binomial else 'Defects:'},
                {'key':'size_index', 'label':'Use sizes in:'}),
            fields=(
                {'key':'size_mode','label':'Sample size:','choices':['Constant size','Use sizes in column']},
                {'key':'sample_size','label':'Constant size:','default':'1'},
                {'key':'historical','label':'Historical p (proportion):' if binomial else 'Historical μ (DPU):','optional':True},
                {'key':'target','label':'Target % defective:' if binomial else 'Target DPU:','default':'0'},
                {'key':'confidence','label':'Confidence level:','default':'95'},
                {'key':'title','label':'Title:','optional':True},
                {'key':'show_graphs','label':'','boolean':True,'text':'Display graphs','default':True}))
        self.controls['size_mode'].currentIndexChanged.connect(self._toggle_size)
        self.controls['historical'].setPlaceholderText('Optional; 0 to 1' if binomial else 'Optional')
        self._toggle_size()

    def _toggle_size(self):
        column = self.controls['size_mode'].currentIndex() == 1
        self.controls['size_index'].setEnabled(column)
        self.controls['sample_size'].setEnabled(not column)
        if not column and self.active_key == 'size_index':
            self.activate('count_index')

    def values(self):
        def number(key, optional=False):
            text=self.controls[key].text().strip()
            if optional and not text:return None
            try:value=float(text)
            except ValueError as exc:raise ValueError('Enter a number for '+key.replace('_',' ')+'.') from exc
            if not math.isfinite(value):raise ValueError('Enter finite values for '+key.replace('_',' ')+'.')
            return value
        def column(key):
            indices=resolve_variables(self.controls[key].text(),self.worksheet)
            if len(indices)!=1:raise ValueError('Select exactly one '+('count' if key=='count_index' else 'sample size')+' column.')
            return indices[0]
        count=column('count_index')
        use_column=self.controls['size_mode'].currentIndex()==1
        size=column('size_index') if use_column else None
        if size==count:raise ValueError('Choose separate columns for counts and sample sizes.')
        sample_size=1.0 if use_column else number('sample_size')
        if sample_size<=0 or self.method=='binomial' and sample_size!=int(sample_size):
            raise ValueError('Sample size must be positive'+(' and an integer.' if self.method=='binomial' else '.'))
        historical=number('historical', True);target=number('target');confidence=number('confidence')
        if not 0<confidence<100:raise ValueError('Confidence level must be between 0 and 100.')
        if historical is not None and (historical<0 or self.method=='binomial' and historical>1):
            raise ValueError('Historical p must be between 0 and 1.' if self.method=='binomial' else 'Historical μ must be nonnegative.')
        if target<0 or self.method=='binomial' and target>100:
            raise ValueError('Target % defective must be between 0 and 100.' if self.method=='binomial' else 'Target DPU must be nonnegative.')
        return {'method':self.method,'count_index':count,'size_index':size,'sample_size':sample_size,
                'options':{'confidence':confidence,'historical':historical,
                           'target':target/100 if self.method=='binomial' else target,
                           'title':self.controls['title'].text().strip(),
                           'show_graphs':self.controls['show_graphs'].isChecked()}}

    def get_configuration(self):return self.values()
