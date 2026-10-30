"""Original mixture and static Taguchi analysis forms with positional selectors.

Installed RT_DIALOG 4361/5668/5671 establishes response and option labels;
implemented forms expose a bounded subset, not native dialog/runtime parity.
"""
import math
from .variable_dialogs import ProcedureDialog,format_variable_list


_MIXTURE_DESIGNS={'simplex_centroid','simplex_lattice','extreme_vertices'}


def _verified_factors(worksheet,schema,designs):
    """Use authored descriptors only when every physical slot still matches."""
    metadata=worksheet.metadata.get('doe',{})
    if not isinstance(metadata,dict) or metadata.get('schema')!=schema or metadata.get('design') not in designs:return None
    factors=metadata.get('factors')
    if not isinstance(factors,list) or not factors:return None
    indices=[]
    for descriptor in factors:
        if not isinstance(descriptor,dict):return None
        index=descriptor.get('column_index');kind=descriptor.get('kind')
        if type(index) is not int or not 0<=index<len(worksheet.columns) or index in indices:return None
        column=worksheet.columns[index]
        if descriptor.get('name')!=column.name or kind!=column.kind:return None
        indices.append(index)
    return indices,metadata


class BuildAnalyzeMixtureDialog(ProcedureDialog):
    def __init__(self,worksheet,parent=None):
        super().__init__(parent,'Analyze Mixture Design',worksheet,
            selectors=(
                {'key':'response_index','label':'Response:'},
                {'key':'component_indices','label':'Mixture components:','multiple':True,'minimum':2,'maximum':8}),
            fields=(
                {'key':'model','label':'Component model:','choices':['Linear','Quadratic','Special cubic'],'default':'Quadratic'},
                {'key':'total','label':'Total mixture amount:','numeric':True,'default':1},
                {'key':'confidence','label':'Confidence level (%):','numeric':True,'default':95},
                {'key':'show_graphs','label':'','boolean':True,'text':'Display residual plots','default':True},
                {'key':'title','label':'Title:','optional':True}),
            note='Select the component amounts for each run. Components must be nonnegative and sum to the fixed mixture total. Block and process-variable terms are not fitted.')
        known=_verified_factors(worksheet,'statcraft-special-design-v1',_MIXTURE_DESIGNS)
        if known:
            indices,metadata=known
            if 2<=len(indices)<=8 and all(worksheet.columns[index].kind=='number' for index in indices):
                self.controls['component_indices'].setText(format_variable_list(indices,worksheet))
                options=metadata.get('options',{})
                total=options.get('total',1) if isinstance(options,dict) else 1
                if type(total) in (int,float) and math.isfinite(total) and total>0:self.controls['total'].setText(str(total))

    def values(self):
        values=super().values()
        if values['response_index'] in values['component_indices']:raise ValueError('Choose separate response and component columns.')
        if values['total']<=0:raise ValueError('Total mixture amount must be positive.')
        if not 0<values['confidence']<100:raise ValueError('Confidence level must be between 0 and 100.')
        bounds=None
        known=_verified_factors(self.worksheet,'statcraft-special-design-v1',_MIXTURE_DESIGNS)
        if known and known[0]==values['component_indices']:
            descriptors=known[1]['factors'];candidate=[]
            for descriptor in descriptors:
                low=descriptor.get('low');high=descriptor.get('high')
                if type(low) not in (int,float) or type(high) not in (int,float) or not math.isfinite(low) or not math.isfinite(high) or low>high:break
                candidate.append({'low':float(low),'high':float(high)})
            if len(candidate)==len(descriptors):bounds=candidate
        return {'response_index':values['response_index'],'component_indices':values['component_indices'],
                'model':{'Linear':'linear','Quadratic':'quadratic','Special cubic':'special_cubic'}[values['model']],
                'total':values['total'],'options':{'confidence':values['confidence']/100,
                    'show_graphs':values['show_graphs'],'title':values['title'] or '','bounds':bounds}}

    def validate(self):
        self.parameters=None
        super().validate()


class BuildAnalyzeTaguchiDialog(ProcedureDialog):
    def __init__(self,worksheet,parent=None):
        super().__init__(parent,'Analyze Taguchi Design (Static)',worksheet,
            selectors=(
                {'key':'response_indices','label':'Response data are in:','multiple':True,'minimum':1,'maximum':20},
                {'key':'factor_indices','label':'Control factors:','multiple':True,'minimum':1,'maximum':8,'kinds':('number','text')}),
            fields=(
                {'key':'sn_type','label':'Signal-to-noise ratio:','choices':['Larger is better','Smaller is better','Nominal is best (mean and standard deviation)'],'default':'Larger is better'},
                {'key':'log_stdev','label':'','boolean':True,'text':'Use ln(s) for standard deviation output','default':False},
                {'key':'fit_models','label':'','boolean':True,'text':'Fit main-effects models','default':True},
                {'key':'show_graphs','label':'','boolean':True,'text':'Display main effects plots','default':True}),
            note='Each response column contains measurements under a different noise condition. Control factors identify the settings used in each run.')
        known=_verified_factors(worksheet,'statcraft-catalog-design-v1',{'taguchi'})
        if known and 1<=len(known[0])<=8 and all(worksheet.columns[index].kind in ('number','text') for index in known[0]):
            self.controls['factor_indices'].setText(format_variable_list(known[0],worksheet))

    def values(self):
        values=super().values()
        if set(values['response_indices'])&set(values['factor_indices']):raise ValueError('Choose separate response and control factor columns.')
        return {'response_indices':values['response_indices'],'factor_indices':values['factor_indices'],
                'options':{'sn_type':{'Larger is better':'larger','Smaller is better':'smaller','Nominal is best (mean and standard deviation)':'nominal'}[values['sn_type']],
                    'log_stdev':values['log_stdev'],'fit_models':values['fit_models'],'show_graphs':values['show_graphs']}}

    def validate(self):
        self.parameters=None
        super().validate()
