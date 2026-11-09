# StatCraft

<div align="center">

<img src="StatCraft.png" width="128" height="128" alt="StatCraft Logo" />

### Modern, High-Performance Statistical Analysis & Quality Engineering Software
**A powerful desktop alternative to Minitab with native MPX file compatibility, universal R code translation (Tidyverse, ggplot2, Base R), interactive 3D CAD response surfaces, and complete offline privacy.**

[![Version](https://img.shields.io/badge/version-114.0.0-blue.svg)](https://github.com/SkinnDeep/StatCraft/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/SkinnDeep/StatCraft)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-green.svg)](https://www.qt.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Download Release (v114.0.0)](https://github.com/SkinnDeep/StatCraft/releases/tag/v114.0.0) •
[Documentation](#capabilities--features) •
[Installation Guide](#installation--setup) •
[Roadmap](#cross-platform-roadmap)

</div>

---

## Overview

**StatCraft** is a modern, standalone desktop statistical software suite engineered for quality engineers, data scientists, researchers, and manufacturing specialists. It provides an authentic, high-speed alternative to legacy tools like Minitab, featuring direct compatibility with standard **MPX** and **MWX** project files, publication-ready graphics with balanced aspect ratios, interactive 3D CAD response surface navigation, and an intelligent **Universal R Code Translator**.

StatCraft operates **100% offline** with zero cloud telemetry, ensuring your proprietary formulas, manufacturing measurements, and research data remain entirely private on your local machine.

---

## Key Highlights

### 1. Universal R Code Translator (Tidyverse, ggplot2 & Base R)
Every analysis and dataset in StatCraft can be instantly translated into standalone, fully executable R code with smart statistical calculation engines:
- **Multi-Engine Code Generation**: Toggle effortlessly between **Tidyverse** (`dplyr`, `ggplot2`, `vroom`, `readxl`), **Base R** (`lm()`, `aov()`, `hist()`, `pairs()`), and High-Performance File Readers.
- **Real Statistical Computations**: Generated R scripts perform real calculations—computing model formulas, ANOVA, PRESS, Predicted R-squared, Anderson-Darling tests, and outlier diagnostics rather than merely pasting static numbers.
- **Publication Plots Out-of-the-Box**: Automatically generates normal distribution curve overlays for histograms, fitted lines with 95% confidence bands, and 4-in-1 residual diagnostic plots.
- **IDE Ready**: One-click copy or direct export to **Positron**, **RStudio**, or **VS Code**. Column names with special characters and units (`Strength (N)`) are preserved cleanly with `check.names = FALSE`.

### 2. Minitab 22 Regression Parity
StatCraft delivers identical statistical reporting and diagnostic rigor to Minitab 22:
- **Standard Regression Equation**: Displays cleanly formatted linear equations (e.g. `Strength = 520.14 + 1.482 Temp - 0.312 Pressure`).
- **Complete Model Summary**: Reports standard error $S$, $R^2$, adjusted $R^2_{adj}$, and **Predicted R-squared ($R^2_{pred}$)** computed via the **PRESS** (Prediction Error Sum of Squares) statistic.
- **Fits and Diagnostics for Unusual Observations**: Automatically detects and flags:
  - **`R`**: Large standardized residuals ($|e_{std}| > 2.0$).
  - **`X`**: Unusual X / high leverage observations ($h_{ii} > 3p/n$).
  - **`RX`**: Observations exhibiting both extreme leverage and large residual error.
- **4-in-1 Residual Diagnostic Plots**: Integrated 2x2 multi-panel diagnostic dashboard featuring:
  1. *Normal Probability Plot of Residuals* with theoretical normal reference line.
  2. *Versus Fits* with zero reference line and $\pm 2.0$ residual thresholds.
  3. *Histogram of Residuals* with normal distribution fit curve overlay.
  4. *Versus Order* showing observation run order vs residuals.

### 3. Publication-Grade Graphics & Balanced Aspect Ratios
- **Centered, Responsive Sizing**: Charts and diagnostic plots are centered and bounded at optimal 16:10 / 4:3 ratios (up to 1,040px max width), preventing unnatural widescreen distortion on 1080p, 1440p, and 4K ultra-wide monitors.
- **High-DPI Anti-Aliasing**: Crisp vector rendering with customizable palettes, annotations, and clean typography.
- **Interactive Graph Brushing**: Select points or histogram bars to immediately highlight matching rows in the active worksheet grid.

### 4. Interactive CAD 3D Flyaround & Surface Inspection
- **OnShape CAD Navigation**: Smooth turntable 3D orbit (right-drag), camera panning (middle-drag / Ctrl+right-drag), and zoom (scroll wheel).
- **Interactive 3D ViewCube**: Orient the model instantly to `TOP`, `FRONT`, `RIGHT`, `LEFT`, `BACK`, `BOTTOM`, or canonical `[ISO]` isometric view.
- **Automated Optimum Detection**: Visual beacons identify global maximums ($\Delta$) and minimums ($\nabla$) with interactive hover cards displaying coordinates and fitted response $\hat{Y}$.
- **160+ FPS Performance**: Adaptive mesh rendering ensures butter-smooth interaction even on complex quadratic surfaces.

### 5. Dynamic Prediction Profilers & Response Optimization
- **Interactive Factor Crosshairs**: Drag factor sliders in real time to explore multi-variable prediction traces, 2D contour projections, and desirability curves.
- **Derringer-Suich Multi-Response Optimizer**: Maximize composite desirability $D$ across conflicting targets, minimums, and maximums.

---

## Capabilities & Features

### 1. Basic Statistics & Distribution Analysis
- **Descriptive Statistics**: Multi-column aligned tables ($N, N^*, \text{Mean}, \text{SE Mean}, \text{StDev}, \text{Min}, Q_1, \text{Median}, Q_3, \text{Max}, \text{IQR}$).
- **Graphical Summary**: 4-in-1 dashboard with histogram, normal fit curve, boxplot, 95% confidence intervals, and Anderson-Darling normality test ($A^2, p\text{-value}, \text{skewness}, \text{kurtosis}$).
- **Hypothesis Testing**:
  - 1-Sample Z and 1-Sample t tests & confidence intervals.
  - 2-Sample t (independent samples with equal or unequal variances).
  - Paired t (paired differences).
  - 1-Sample Poisson Rate & 2-Sample Poisson Rate.
  - 1 Proportion & 2 Proportions tests.
  - 1 Variance & 2 Variances (Bonett, Levene, and F-test).
- **Correlation & Outlier Detection**:
  - Pearson correlation and covariance matrices.
  - Grubbs' and Dixon's tests for outlier identification.

### 2. Advanced Regression & Linear Models
- **Multiple Linear Regression (OLS)**: Full Minitab 22 parity with PRESS, Predicted R-squared, Unusual Observations ($R, X, RX$), and publication 4-in-1 residual plots.
- **Stepwise & Best Subsets Regression**: Automated model selection via Stepwise, Forward, Backward, Forward/Backward AIC, and Forward/Backward BIC; Mallows' $C_p$, $R^2_{adj}$, and PRESS.
- **Poisson Regression**: Log-link generalized linear models (GLM) for event counts with continuous and categorical predictors, exposure/offset terms, deviance/Pearson goodness-of-fit, and relative rate ratios with 95% CIs.
- **Binary, Ordinal & Nominal Logistic Regression**:
  * Binary Logistic with logit link, odds ratios, and classification tables.
  * Ordinal Logistic proportional odds cumulative logit model with threshold cutpoints and Somers' $D$, Gamma, Kendall's $\tau_a$.
  * Nominal Logistic generalized logit multinomial model with baseline reference event.
- **Nonlinear Regression**: Levenberg-Marquardt optimizer with built-in growth catalog (Asymptotic, Michaelis-Menten, Logistic, Gompertz, Power) and user-defined formulas.
- **Orthogonal Regression (Deming)**: Fits linear models when both response and predictor contain measurement error; configurable error variance ratio $\delta$, jackknife standard errors, and slope $= 1$ hypothesis testing.
- **Partial Least Squares (PLS)**: NIPALS and SIMPLS cross-validated PLS regression with leave-one-out cross-validation PRESS, predicted $R^2$, and Variable Importance in Projection (VIP) scores.
- **Stability Study (ICH Q1E)**: Pharmaceutical shelf life expiration determination across manufacturing batches with ANCOVA slope and intercept poolability tests and 95% one-sided confidence bands.
- **Analysis of Variance (ANOVA)**: One-Way (Tukey, Fisher LSD, Dunnett, Hsu MCB, Games-Howell), Two-Way, Balanced ANOVA, Fully Nested ANOVA, and General Linear Model (GLM).
- **Analysis of Means (ANOM)**: One-Way and Two-Way ANOM for Normal, Binomial, and Poisson data with decision limits.
- **Test for Equal Variances**: Bartlett's test, Levene's test, and Multiple Comparisons confidence intervals.

### 3. Statistical Process Control (SPC) & Six Sigma Quality
- **Variables Control Charts for Subgroups**: Xbar-R, Xbar-S, I-MR-R/S (Between/Within), Xbar, R, and S charts with Nelson Rules 1–8 signal detection.
- **Variables Control Charts for Individuals**: I-MR (Individual-Moving Range) and Z-MR charts.
- **Attributes Control Charts**: P, NP, U, and C charts, plus Laney P' and Laney U' overdispersion charts.
- **Time-Weighted & Rare Event Charts**: EWMA, CUSUM, Moving Average, G Chart, and T Chart.
- **Process Capability Analysis**:
  * Normal Capability ($C_p, C_{pk}, P_p, P_{pk}, C_{pm}$, and expected PPM).
  * Between/Within Capability ($C_p, C_{pk}$, StDev Between/Within).
  * Nonnormal Capability (Weibull, Lognormal, Exponential, Gamma, Box-Cox, Johnson).
  * Multiple Variables Capability (Normal and Nonnormal).
  * Binomial and Poisson Attribute Capability.
- **Capability Sixpack**: Full 6-panel diagnostics dashboard across Normal, Between/Within, and Nonnormal distributions.
- **Tolerance Intervals**: Normal and Nonnormal tolerance intervals for parts with confidence/coverage bounds.
- **Acceptance Sampling**: Acceptance Sampling by Attributes and Acceptance Sampling by Variables (AQL, RQL, OC Curves).
- **Measurement Systems Analysis (MSA)**:
  * Gage R&R (Crossed, Nested, and Expanded ANOVA models with up to 10 factors and $ndc$).
  * Type 1 Gage Study ($C_g, C_{gk}$, run charts).
  * Gage Linearity and Bias Study.
  * Evaluating the Measurement Process (EMP / Wheeler).
  * Attribute Agreement Analysis (Fleiss' kappa, Kendall's concordance, Cohen's kappa).
- **Cause-and-Effect (Fishbone / Ishikawa) Diagram**: Standard 6M industrial categories, custom branch labels, empty branch suppression, and interactive vector diagram with hover HUD inspection.
- **Johnson Transformation**: Transform nonnormal process data into a standard normal distribution using the optimal Johnson curve system ($S_B, S_L, S_U$).
- **Individual Distribution Identification**: Evaluate data against 16 continuous distributions and transformations with Anderson-Darling tests, calibrated p-values, LRT, and 4-in-1 probability plots.
- **Pareto Charts**: Defect frequency bars, cumulative percentage curves, and 80/20 reference markers.

### 4. Reliability & Survival Analysis
- **Distribution Analysis (Right & Arbitrary Censoring)**: Parametric (Weibull, Lognormal, Exponential, Normal, Loglogistic) and Nonparametric (Kaplan-Meier / Turnbull) estimation with delta-method percentile standard errors.
- **Accelerated Life Testing (ALT)**: Arrhenius, Power, and Exponential acceleration models for temperature and stress extrapolation.
- **Probit Analysis**: Bioassay and dose-response modeling with Probit, Logit, Weibull, and Gompertz links; LD10/LD50/LD90 lethal doses with Fieller's fiducial confidence limits.
- **Repairable Systems Analysis**:
  * Nonparametric Growth Curve: Mean Cumulative Function (MCF) via Nelson / Lawless-Nadeau estimator with pointwise confidence limits.
  * Parametric Growth Curve: Crow-AMSAA / Power Law NHPP modeling, MIL-HDBK-189 & Laplace trend tests, instantaneous failure rates, and MTBF horizons.
- **Regression with Life Data**: Parametric Accelerated Failure Time (AFT) survival regression with right censoring, log-likelihood optimization, and quantile predictions.

### 5. Multivariate Analysis & Categorical Tables
- **Principal Component Analysis (PCA)**: Scree plots, eigenvalues, eigenvectors, and score/loading biplots.
- **Factor Analysis**: Principal components extraction with orthogonal rotations (Varimax with Kaiser normalization, Quartimax, Equamax), communalities, variance explained, and Thomson factor score coefficients.
- **Multiple Correspondence Analysis (MCA)**: Indicator matrix and Burt contingency table decomposition for multi-way categorical data.
- **Item Analysis & Cronbach's Alpha**: Survey reliability assessment with item-deleted statistics.
- **Cluster Analysis**: Hierarchical clustering of observations, variables, and K-Means partitioning.
- **Discriminant Analysis**: Linear (LDA) and quadratic (QDA) classification with cross-validation summary.

### 6. Time Series Analysis
- **Trend Analysis & Decomposition**: Linear, quadratic, exponential growth, and S-curve trends; additive and multiplicative seasonal decomposition.
- **Smoothing Methods**: Moving Average, Single Exponential Smoothing, Double Exponential Smoothing (Holt's method), and Winters' 3-Parameter Additive/Multiplicative Smoothing.
- **ARIMA Modeling**: Full seasonal autoregressive integrated moving average $(p, d, q) \times (P, D, Q)_s$ forecasting.
- **Correlation**: Autocorrelation (ACF), Partial Autocorrelation (PACF), and Cross-Correlation (CCF).

### 7. Design of Experiments (DOE)
- **Factorial Designs**: 2-Level Full and Fractional factorials ($2^{k-p}$), General Full Factorials, Plackett-Burman screening designs.
- **Response Surface Methodology (RSM)**: Central Composite Designs (CCD) and Box-Behnken designs with full quadratic regression and 3D CAD visualization.
- **Mixture Designs**: Simplex Centroid, Simplex Lattice, Extreme Vertices designs with Scheffé canonical polynomials.
- **Taguchi Robust Designs**: Orthogonal arrays ($L_4$ to $L_{36}$) with S/N ratios (Larger-is-better, Smaller-is-better, Nominal-is-best).
- **Definitive Screening Designs (DSD)**: Main effects unconfounded with two-factor interactions.

### 8. Native File Compatibility & Data Prep
- **MPX / MWX Compatibility**: Read, edit, and save native Minitab project and worksheet containers with column types, formatting, and formulas preserved.
- **Office Export**: Export worksheets and high-resolution reports to Microsoft Excel (`.xlsx`), Word (`.docx`), PowerPoint (`.pptx`), and PDF.
- **Data Calculator & Transformations**: Formula evaluation, pattern generation, stacking/unstacking, transposing, sorting, and standardization.

---

## Installation & Setup

### Option 1: Modern Windows Installer (Recommended)
Download **`StatCraft-Setup.exe`** from the [Latest Releases](https://github.com/SkinnDeep/StatCraft/releases):
1. Run `StatCraft-Setup.exe`.
2. Follow the setup wizard (no administrator elevation required).
3. Shortcuts are created in the Start Menu and Desktop.
4. Updates can be checked anytime via **`Help > Check for Updates…`**.

*Silent / Enterprise Deployment:*
```powershell
StatCraft-Setup.exe --silent --dir "C:\Program Files\StatCraft"
```

### Option 2: Standalone Portable Binary
Download **`StatCraft.exe`**. No installation required—simply double-click and run.

### Option 3: Run from Source
StatCraft runs on Python 3.10+:

```bash
# 1. Clone the repository
git clone https://github.com/SkinnDeep/StatCraft.git
cd statcraft

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install PySide6 numpy scipy

# 4. Launch StatCraft
python launch_modern.py
```

---

## Cross-Platform Roadmap

StatCraft is built on the cross-platform Qt6 (PySide6) framework:

| Platform | Current Status | Release Artifact |
|---|---|---|
| **Windows x64** | **Available (v114.0.0)** | `StatCraft-Setup.exe`, `StatCraft.exe` |
| **macOS (Apple Silicon & Intel)** | *In Preparation* | `.dmg` installer & standalone `.app` bundle |
| **Linux (x86_64)** | *In Preparation* | `AppImage` & `.deb` package |

Source execution is fully functional on macOS and Linux by running `python launch_modern.py`.

---

## Testing & Quality Assurance

StatCraft maintains rigorous test suites covering calculations, numerical invariants, and visual components (2,214+ automated tests):

```bash
# Run the complete test suite
python -m unittest discover tests
```

---

## Contributing & License

Contributions, feature requests, and issue reports are welcome! Please open an issue or pull request on GitHub.

Distributed under the **MIT License**. See `LICENSE` for details.
