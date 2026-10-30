"""ROC and observation diagnostics using the existing QPainter chart panels."""
import math

MAX_PLOT_OBSERVATIONS = 20000


def prepare(chart, result):
    chart.panels = []
    chart.panel_columns = 2
    chart.note = ''
    if result.get('options', {}).get('graphs', 'none') != 'four':
        return
    probabilities = list(result['probabilities'])
    residuals = list(result['residuals'])
    pearson = list(result['pearson_residuals'])
    rows = list(result['row_indices'])
    n = len(rows)
    if not n or any(len(a)!=n for a in (probabilities, residuals, pearson)):
        raise ValueError('Logistic diagnostic plots require aligned complete model rows.')
    if n > MAX_PLOT_OBSERVATIONS:
        raise ValueError('Logistic graph display supports at most 20,000 observations. The complete numerical report remains available.')
    if any(type(a) not in (int, float) or not math.isfinite(a) for a in probabilities+residuals+pearson):
        raise ValueError('Logistic graph values must be finite numbers.')
    if any(not 0 <= a <= 1 for a in probabilities):
        raise ValueError('Fitted event probabilities must be between zero and one.')
    if any(type(a) is not int or a < 0 for a in rows) or len(set(rows)) != n or rows != sorted(rows):
        raise ValueError('Logistic source row indices must be distinct nonnegative worksheet rows in order.')
    roc = result['roc_curve']
    if not isinstance(roc, list) or not 2 <= len(roc) <= n+1:
        raise ValueError('Logistic ROC data must contain 2 to N+1 points.')
    xs = [a['false_positive_rate'] for a in roc]
    ys = [a['sensitivity'] for a in roc]
    if any(type(a) not in (int, float) or not math.isfinite(a) or not 0 <= a <= 1 for a in xs+ys):
        raise ValueError('ROC coordinates must be finite probabilities.')
    if xs != sorted(xs) or ys != sorted(ys):
        raise ValueError('ROC coordinates must increase monotonically.')
    one_based = [a+1 for a in rows]
    auc = result.get('auc')
    if type(auc) not in (int, float) or not math.isfinite(auc) or not 0 <= auc <= 1:
        raise ValueError('ROC area must be a finite probability.')
    panels = [dict(kind='line', title='ROC Curve (AUC = '+format(auc, '.4f')+')', x=xs, y=ys,
        xlabel='False Positive Rate', ylabel='Sensitivity', lines=[('Chance', xs, '#999999')]),
        dict(kind='line', title='Fitted Event Probabilities', x=one_based, y=probabilities,
             xlabel='Observation Order', ylabel='Event Probability', lines=[], row_indices=one_based),
        dict(kind='scatter', title='Deviance Residuals Versus Fits', x=probabilities, y=residuals,
             xlabel='Fitted Event Probability', ylabel='Deviance Residual', zero=True, row_indices=one_based),
        dict(kind='scatter', title='Pearson Residuals Versus Order', x=one_based, y=pearson,
             xlabel='Observation Order', ylabel='Pearson Residual', zero=True, row_indices=one_based)]
    for panel in panels:
        chart._bounds(panel['x'])
        chart._bounds(panel['y']+([0.] if panel.get('zero') else []))
    chart.panels = panels
    chart.note = 'Event: '+(str(result['event']) if result.get('event') is not None else 'Event')+' · ROC chance line: sensitivity = false positive rate · Diagnostic points retain worksheet row links.'
