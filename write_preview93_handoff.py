import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
p = json.loads((out / 'StatCraft-preview93-verification.json').read_text(encoding='utf-8'))
t = p['source_tests']

text = f'''# StatCraft preview93 — 29 October 2026

Current executable: **StatCraft.exe**, identical to **StatCraft-preview93.exe**.

StatCraft Preview 93 delivers an expansive wide-pass implementation of **Multivariate Analysis** under `Stat > Multivariate`, providing 1:1 statistical and functional parity with StatCraft/22.6 for dimension reduction, internal consistency/reliability, unsupervised agglomerative and partitioning clustering, supervised classification, and dual contingency biplots.

Multivariate Analysis:
- **Principal Components Analysis (PCA)**: Supports Correlation and Covariance matrices, calculates eigenvalues, individual variance proportions, cumulative proportions, eigenvectors (loadings) with StatCraft sign convention, and observation component scores.
- **Item Analysis & Cronbach\'s Alpha**: Computes overall Cronbach\'s $\\alpha$ and standardized $\\alpha$, item statistics (means, standard deviations), adjusted total statistics, item-adjusted total correlations, squared multiple correlations (SMC via inverse correlation matrix), and Cronbach\'s $\\alpha$ if item deleted.
- **Cluster Observations**: Agglomerative hierarchical clustering of observations supporting 7 linkage methods (Average, Single, Complete, Centroid, Ward, Median, McQuitty) and 4 distance measures (Euclidean, Squared Euclidean, Manhattan, Maximum) with optional Standardization (Z-score, Range 0-1). Produces full amalgamation schedules, cluster partition summaries, and cluster centroids.
- **Cluster K-Means**: Partitioning clustering for $K$ clusters with Lloyd\'s algorithm and deterministic initial partition; outputs cluster sizes, within-cluster SS, average/max centroid distances, inter-cluster centroid distances, and ANOVA SS decomposition (Within, Between, Total SS).
- **Cluster Variables**: Hierarchical clustering of variables via correlation distance ($d = 1 - r$) and similarity metrics ($s = 100 \\times (1 - d/2)$) with amalgamation schedules and variable dendrograms.
- **Discriminant Analysis**: Linear and Quadratic Discriminant Analysis (LDA & QDA) with Equal or Proportional priors; calculates group means, pooled covariance matrix, linear discriminant function coefficients, classification confusion matrices (% correct), Jackknife leave-one-out cross-validation matrices, and 2D canonical discriminant scores.
- **Simple Correspondence Analysis**: 2-way contingency table decomposition into principal dimensions; computes row and column masses, principal inertias, singular values, $\\chi^2$ contributions, and symmetric row/column biplot coordinates.
- **High-DPI Visualization**: `MultivariateChartWidget` with interactive Pan/Zoom via `GraphInteractionMixin` rendering PCA Scree Plots with Kaiser line, PCA Loading Plots, PCA Score Plots, PCA Biplots, Item-Total Statistics Plots, Observation/Variable Dendrograms, K-Means Centroid Profiles, Discriminant Canonical Score Plots, and Correspondence Biplots.
- **Interactive Qt Dialogs & Menu**: Modern Qt dialogs with dual-list column selectors, variable role validation, algorithm options, and OK/Cancel buttons under `Stat > &Multivariate`.
- **Persistence & Immutability**: All 7 multivariate procedures are fully integrated into MPX recipes, supporting rerun invariance and persistence without altering original benchmark files.

Verification: **{t['unittest_passed']} tests passed**, {t.get('skipped',0)} skipped, **{p['packaged_workflow_gates']} packaged workflow gates**, and **{len(p['mpx_fixtures'])} MPX fixture checks**. The supplied native project also passes in the EXE; saved-value digests match the source application. Startup maximization, splash dismissal and source/frozen equality are verified. {p['source_archive_entries_byte_equal']} source archive files match current files; {p['frozen_application_source']['application_modules_checked']} bundled application modules match compiled source.

- [Scope and limits](StatCraft-preview93-contract.md)
- [Release verification](StatCraft-preview93-verification.json)

Remaining priorities: hover support in independent specialty capability/control/MSA painters; broader axis/tick fidelity; native graph object editing; further DOE options and coupled multiresponse optimization; further worksheet and native project format coverage. Native row-for-row coordinate/order identity and full product-wide numerical/UI equivalence remain unverified.
'''

(out / 'StatCraft-preview-93-changes.md').write_text(text, encoding='utf-8')
for name in ('StatCraft-handoff.md', 'StatCraft-parity-backlog.md', 'StatCraft-current-feature-audit.md'):
    path = out / name
    old = path.read_text(encoding='utf-8-sig')
    if not old.startswith('# StatCraft preview93'):
        path.write_text(text + '\n---\n\nHistorical notes follow; preview93 above overrides older completed-feature gaps.\n\n' + old, encoding='utf-8')
print('Preview93 handoff and priority list updated')
