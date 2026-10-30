"""Scalar tables for binary logistic fits and probability predictions."""
from .prediction_report import _display, _equation_lines


def _equation(result):
    event = str(result['event']) if result.get('event') is not None else 'Event'
    return _equation_lines('logit(P('+str(result.get('response_name', 'Response'))+' = '+event+'))', result.get('coefficients', []))


def sections(result):
    if result.get('analysis') == 'logistic_prediction':
        return prediction_sections(result)
    r = result
    o = dict(method=True, response_information=True, model_summary=True,
             coefficients=True, odds_ratios=True, equation=True,
             diagnostics='unusual', confidence=.95) | r.get('options', {})
    level = format(100*o['confidence'], '.7g')+'%'
    tables = []
    if o['model_summary']:
        tables.append(('Model Summary', ['Deviance', 'AIC', 'BIC', 'ROC AUC', 'N', 'N*'],
                       [[r.get(k) for k in ('deviance', 'aic', 'bic', 'auc', 'n', 'missing')]]))
        tables.append(('Likelihood Ratio Test', ['Source', 'DF', 'Chi-Square', 'P-Value'],
                       [['Model', r.get('model_lr_df'), r.get('model_lr'), r.get('model_lr_p')]]))
        tables.append(('Goodness-of-Fit', ['Test', 'DF', 'Chi-Square', 'P-Value'], [
            ['Deviance', r.get('df_error'), r.get('deviance'), r.get('deviance_p')],
            ['Pearson', r.get('df_error'), r.get('pearson_chi_square'), r.get('pearson_p')]]))
    if o['coefficients']:
        tables.append(('Coefficients', ['Term', 'Coef', 'SE Coef', 'Z-Value', 'P-Value', level+' Wald Lower', level+' Wald Upper'],
                       [[a.get(k) for k in ('name', 'estimate', 'standard_error', 'z', 'p_value', 'ci_low', 'ci_high')] for a in r.get('coefficients', [])]))
    if o['odds_ratios']:
        rows = [[a.get(k) for k in ('name', 'odds_ratio', 'or_low', 'or_high')]
                for a in r.get('coefficients', []) if str(a.get('name', '')).casefold() not in ('constant', 'intercept', '(intercept)')]
        if rows:
            tables.append(('Odds Ratios', ['Term', 'Odds Ratio', level+' Wald Lower', level+' Wald Upper'], rows))
    if o['equation'] and r.get('coefficients'):
        tables.append(('Regression Equation', ['Equation (source model coding)'], [[line] for line in _equation(r)]))
    if o['response_information']:
        event = r['event'] if r.get('event') is not None else 'Event'
        non_event = r['non_event'] if r.get('non_event') is not None else 'Non-event'
        tables.append(('Response Information', ['Response', 'Value', 'Count'], [
            [r.get('response_name'), event, r.get('events')],
            [r.get('response_name'), non_event, r.get('non_events')]]))
        tables.append(('Event', ['Event modeled'], [[event]]))
    if o['diagnostics'] != 'none':
        rows = [a for a in r.get('diagnostics', []) if o['diagnostics']=='all' or a.get('flag')]
        if rows:
            tables.append(('Fits and Diagnostics'+(' for Unusual Observations' if o['diagnostics']=='unusual' else ''),
                ['Obs', 'Events', 'Trials', 'Probability', 'Deviance Resid', 'Pearson Resid', 'Std Resid', 'Leverage', ''],
                [[a.get(k) for k in ('row', 'response', 'trials', 'probability', 'deviance_residual', 'pearson_residual', 'standardized_residual', 'leverage', 'flag')] for a in rows]))
    if o['method']:
        rows = [['Link', 'Logit'], ['Estimation', 'Maximum likelihood'], ['Confidence level', level],
                ['Intervals', 'Wald'], ['Factor coding', 'Reference contrasts'],
                ['Missing data', 'Omit incomplete model rows'], ['Log likelihood', r.get('log_likelihood')],
                ['Null log likelihood', r.get('null_log_likelihood')], ['BIC sample size (total trials)', r.get('bic_sample_size')],
                ['Iterations', r.get('iterations')]]
        for item in r.get('coding_information', []):
            if item.get('kind') == 'factor':
                rows.append([str(item.get('name', 'Factor'))+' reference', item.get('reference', (item.get('levels') or [None])[-1])])
        tables.append(('Method', ['Setting', 'Value'], rows))
    return tables


def prediction_sections(result):
    r = result
    o = dict(confidence=.95, side='two_sided', intervals='confidence', show_table=True, show_equation=True) | r.get('options', {})
    tables = []
    if o['show_table']:
        headers = ['Row', 'Probability', 'SE Probability']
        keys = ['row', 'probability', 'se_probability']
        level = format(100*o['confidence'], '.7g')+'%'
        if o['intervals'] != 'none':
            if o['side'] in ('two_sided', 'lower'):
                headers.append(level+' CI Lower'); keys.append('ci_low')
            if o['side'] in ('two_sided', 'upper'):
                headers.append(level+' CI Upper'); keys.append('ci_high')
        headers += ['X', 'Status']
        tables.append(('Probability Predictions', headers, [[a.get(k) for k in keys]+[
            'X' if a.get('extrapolated') else '', 'Missing predictor settings' if a.get('status')=='missing' else '' if a.get('status') in ('converged', 'ok') else a.get('status', '')] for a in r.get('rows', [])]))
        names = list(r.get('predictor_names', []))
        tables.append(('New Predictor Values', ['Row']+names, [[a.get('row')]+list(a.get('inputs', []))[:len(names)]+[None]*max(0, len(names)-len(a.get('inputs', []))) for a in r.get('rows', [])]))
    if o['show_equation'] and r.get('coefficients'):
        tables.append(('Regression Equation', ['Equation (source model coding)'], [[line] for line in _equation(r)]))
    tables.append(('Method', ['Setting', 'Value'], [['Source model', r.get('model_title', 'Binary Logistic Regression')],
        ['Response', r.get('response_name')], ['Event modeled', r['event'] if r.get('event') is not None else 'Event'],
        ['Model data', 'Refit the source model using the current worksheet data'],
        ['Confidence level', format(100*o['confidence'], '.7g')+'%'],
        ['Intervals', 'None' if o['intervals']=='none' else 'Pointwise Wald probability confidence intervals (logit scale)'],
        ['Bounds', {'two_sided': 'Two-sided', 'lower': 'Lower bound', 'upper': 'Upper bound'}[o['side']]],
        ['Usable prediction rows', r.get('used')], ['Rows missing settings', r.get('missing')]]))
    return tables


def text_report(result):
    lines = []
    for title, headers, rows in sections(result):
        data = [[_display(v) for v in row] for row in rows]
        widths = [max(len(h), max((len(row[i]) for row in data), default=0)) for i, h in enumerate(headers)]
        lines += [title, '  '.join(h.ljust(w) for h, w in zip(headers, widths))]
        lines += ['  '.join(v.ljust(w) for v, w in zip(row, widths)) for row in data]
        lines.append('')
    if result.get('analysis') == 'logistic_prediction':
        if result.get('options', {}).get('show_table', True):
            lines.append('*: missing or undefined value. X: continuous setting outside the observed predictor range.')
    elif result.get('options', {}).get('diagnostics', 'unusual') != 'none':
        lines.append('R: |standardized residual| > 2. X: leverage > 3p/n; p includes the intercept.')
    if result.get('methodnotes'):
        lines.append(str(result['methodnotes']))
    lines.extend(str(a) for a in result.get('warnings', []))
    return '\n'.join(lines)


prediction_text_report = text_report
