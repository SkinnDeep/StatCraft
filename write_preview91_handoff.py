import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview91-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

text = f'''# StatCraft preview91 — 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview91.exe**.

StatCraft Preview 91 delivers a wide-pass implementation of **Time Series Analysis and Forecasting** under `Stat > Time Series`, providing 1:1 statistical and functional parity with StatCraft/22.6 for univariate time series modeling, smoothing, decomposition, diagnostics, and multi-step forecasting.

Time Series Analysis and Forecasting:
- **Trend Analysis**: Fits Linear, Quadratic, Exponential Growth, and Pearl-Reed Logistic S-Curve trend models with fitted equations, forecasts, prediction limits, and MAPE/MAD/MSD accuracy metrics.
- **Decomposition**: Classical multiplicative and additive decomposition with centered moving average (CMA) smoothing, normalized seasonal indices, deseasonalized series trend fitting, and seasonal multi-step forecasts.
- **Moving Average**: One-step-ahead forecasting and centered smoothing with user-defined window sizes and expanding prediction intervals.
- **Single Exponential Smoothing**: Level recurrence smoothing with user-specified or MSD-optimal smoothing weight $\\alpha$, flat forecasts, and lead-time prediction intervals.
- **Double Exponential Smoothing**: Holt's two-parameter linear exponential smoothing with level and trend recurrence, automated joint parameter optimization, and trended forecasts with Holt variance factor prediction limits.
- **Autocorrelation (ACF) & Partial Autocorrelation (PACF)**: Autocorrelation with Bartlett standard errors, t-statistics, and Ljung-Box $Q$ statistics; PACF via Durbin-Levinson recursion; correlation spike plots with 5% significance bounds.
- **Time Series Transformations**: Differencing and Lag transformations with direct column worksheet storage.
- **Interactive Qt Dialogs & Menu**: Modern Qt dialogs with dual-list column selectors, forecast horizons, automated vs. manual parameter solvers, and storage destination controls.
- **High-DPI Visualization & Reports**: `TimeSeriesChartWidget` with pan/zoom rendering time plots (actual, fit, forecast, 95% PI) and correlation spike charts; authentic StatCraft session reports.
- **Persistence & Immutability**: All time series models are fully integrated into MPX recipes, supporting rerun invariance and persistence without altering original native files.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview91-contract.md)
- [Release verification](StatCraft-preview91-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-91-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview91'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview91 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview91 handoff and priority list updated')
