"""Readable attribute capability output without internal model or array dumps."""
import math


def _fmt(value):
    if value is None:return '*'
    if isinstance(value,(float,int)) and math.isfinite(value):return f'{value:.6g}'
    return str(value)


def generate_attribute_capability_report(result):
    title=result.get('title') or result.get('method','').title()+' Capability Analysis'
    lines=[title, '='*len(title), '', 'Data',
           '  Count variable: '+str(result.get('count_name','')),
           '  Sample size: '+str(result.get('size_name','Constant')),
           f"  Samples analyzed: {result.get('n_samples',0)}",
           f"  Rows omitted: {len(result.get('omitted_rows',[]))}", '', 'Summary Statistics']
    def stat(label,value):lines.append(f'  {label:<30} {_fmt(value)}')
    stat('Total count',result.get('total_count'));stat('Total sample size',result.get('total_size'))
    level=result.get('confidence',95)
    suffix={'lower':'lower bound','upper':'upper bound'}.get(result.get('interval_type'),'CI')
    if result.get('method')=='binomial':
        stat('% Defective',result.get('percent_defective'));stat('PPM Defective',result.get('ppm_defective'))
        ci=result.get('percent_ci') or [None,None]
        lines.append(f'  {level:g}% {suffix} for % Defective: '+' to '.join(_fmt(v) for v in ci))
        stat('Process Z',result.get('process_z_label') or result.get('process_z'))
        zci=result.get('process_z_ci_labels') or result.get('process_z_ci')
        if zci:lines.append('  Process Z interval: '+' to '.join(_fmt(v) for v in zci))
        stat('Target % Defective',None if result.get('target') is None else 100*result['target'])
    else:
        for label,key in [('Mean defects per sample','mean_defects'),('Mean DPU','mean_dpu'),('Minimum DPU','min_dpu'),('Maximum DPU','max_dpu')]:stat(label,result.get(key))
        lines.append(f'  {level:g}% {suffix} for Mean DPU: '+' to '.join(_fmt(v) for v in result.get('rate_ci',[None,None])))
        stat('Target DPU',result.get('target'))
    if result.get('historical_rate') is not None:
        stat('Historical process rate',result['historical_rate'])
        lines.append('  Control limits use the historical rate; summary estimates use observed data.')
    lines.extend(['', 'Stability', f"  Points beyond 3-sigma limits: {len(result.get('violations',[]))}"])
    for note in result.get('notes',[]):lines.append('  '+str(note))
    return '\n'.join(lines)
