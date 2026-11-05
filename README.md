# StatCraft

<div align="center">

<img src="StatCraft.png" width="128" height="128" alt="StatCraft Logo" />

### Modern, High-Performance Statistical Analysis & Quality Engineering Software
**A powerful desktop alternative to Minitab with native MPX file compatibility, interactive CAD 3D response surfaces, and enterprise-grade reliability.**

[![Version](https://img.shields.io/badge/version-104.0.0-blue.svg)](https://github.com/SkinnDeep/StatCraft/releases)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/SkinnDeep/StatCraft)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt6-green.svg)](https://www.qt.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[Download Release (v104.0.0)](https://github.com/SkinnDeep/StatCraft/releases/tag/v104.0.0) •
[Documentation](#capabilities--features) •
[Installation Guide](#installation--setup) •
[Roadmap](#cross-platform-roadmap)

</div>

---

## Overview

**StatCraft** is a modern, standalone desktop statistical analysis suite built for engineers, data scientists, quality professionals, and researchers. It provides a complete alternative to legacy proprietary tools like Minitab, featuring direct compatibility with standard **MPX** project and worksheet files, sub-millisecond calculation speeds, and an innovative CAD-grade interactive 3D visualization engine.

Whether you need quick descriptive statistics, hypothesis testing, Six Sigma control charts, complex Design of Experiments (DOE), or response surface optimization, StatCraft delivers authentic, production-ready results in an intuitive interface.

---

## Highlight: Interactive CAD 3D Flyaround & Surface Inspection

StatCraft features a custom, high-speed 3D viewport for Response Surface Methodology (RSM) and 3D scatter/surface visualization:

- 🔄 **OnShape CAD Navigation**:
  - **Turntable Orbit**: Right-click drag rotates the model smoothly in 3D camera space.
  - **Screen Pan**: Middle-click drag (Scroll wheel press) or `Ctrl + Right-drag` pans the camera.
  - **Zoom**: Smooth mouse wheel scroll scaling centered on the cursor.
- 🧊 **Interactive 3D ViewCube**:
  - Live orientation cube positioned in the top-right corner, rotating synchronously with the model.
  - Click any face (`TOP`, `FRONT`, `RIGHT`, `LEFT`, `BACK`, `BOTTOM`), edge, or corner to snap immediately to canonical viewpoints.
  - Includes a one-click `[ISO]` isometric reset button.
- 🎯 **Automated Peak & Minimum Detection**:
  - Visual beacon pinheads and drop stems identify global maximums ($\Delta$) and minimums ($\nabla$).
  - One-click inspection callout cards displaying fitted response $\hat{Y}$, factor coordinates, and active hold settings.
- ⚡ **160+ FPS Performance**:
  - Adaptive mesh decimation during rapid orbit and pan ensures buttery smooth interaction without UI stutter.
  - Non-occluding transparent reference frame preserves full view of surfaces from any angle.

---

## Capabilities & Features

### 1. Basic Statistics
- **Display Descriptive Statistics**: Aligned multi-column tables ($N, N^*, \text{Mean}, \text{SE Mean}, \text{StDev}, \text{Min}, Q_1, \text{Median}, Q_3, \text{Max}$).
- **Graphical Summary**: 4-in-1 diagnostic dashboard featuring histogram with normal fit, boxplot, confidence intervals, and Anderson-Darling normality test ($A^2, p\text{-value}, \text{skewness}, \text{kurtosis}$).
- **Hypothesis Testing**:
  - 1-Sample Z and 1-Sample t tests & confidence intervals.
  - 2-Sample t (independent samples with equal or unequal variances).
  - Paired t (within-subject paired differences).
  - 1-Sample Poisson Rate & 2-Sample Poisson Rate.
  - 1 Proportion & 2 Proportions tests.
  - 1 Variance & 2 Variances (Bonett, Levene, and F-test).
- **Association & Correlation**:
  - Pearson correlation matrix and covariance matrix (pairwise or listwise deletion).
  - Outlier detection via Grubbs' and Dixon's tests.
  - Stem-and-Leaf display with depth columns and leaf unit headers.

### 2. Analysis of Variance (ANOVA)
- **One-Way ANOVA**:
  - Stacked and unstacked data layouts.
  - Multiple comparisons: Tukey, Fisher LSD, Dunnett (with control group), Hsu MCB (best), and Games-Howell.
  - High-DPI means interval plots and differences of means charts.
- **Two-Way ANOVA**:
  - Full factorial ($A, B, A \times B$) and additive models.
  - Complete ANOVA table with Sums of Squares, Mean Squares, $F$-values, $p$-values, $S$, $R^2$, and $R^2_{adj}$.
  - Side-by-side **Main Effects Plots** and **Interaction Plots**.
- **General Linear Model (GLM)**:
  - Supports continuous covariates, categorical factors, custom interaction terms, and model diagnostics.
- **Test for Equal Variances**:
  - Bartlett's test, Levene's test, and Multiple Comparisons confidence intervals.

### 3. Statistical Process Control (SPC) & Quality Tools
- **Variables Control Charts for Subgroups**: Xbar-R, Xbar-S, Xbar, R, S charts with Nelson Test 1–8 signal detection.
- **Variables Control Charts for Individuals**: I-MR (Individual-Moving Range) charts.
- **Attributes Control Charts**: P, NP, U, and C charts with variable subgroup sample size weighting.
- **Time-Weighted Charts**: EWMA and CUSUM charts.
- **Process Capability Analysis**:
  - Normal Capability ($C_p, C_{pk}, P_p, P_{pk}, C_{pm}$, and expected PPM).
  - Non-Normal Capability (Weibull, Lognormal, Exponential, Gamma).
  - Capability Sixpack dashboard.
- **Measurement Systems Analysis (MSA)**:
  - Gage R&R (Crossed & Nested ANOVA methods, Study Variation %, Tolerance %).
  - Type 1 Gage Study ($C_g, C_{gk}$, run charts).
  - Gage Linearity and Bias Study.
  - Attribute Agreement Analysis (Fleiss' kappa, Kendall's concordance).
- **Pareto Charts**:
  - Defect frequency bars, cumulative percentage curves, and 80/20 reference markers.

### 4. Design of Experiments (DOE)
- **Factorial Designs**:
  - 2-Level Full and Fractional factorials ($2^{k-p}$), General Full Factorials, Plackett-Burman screening designs.
  - Aliasing resolution analysis, design catalogs, and center point replication.
- **Response Surface Methodology (RSM)**:
  - Central Composite Designs (CCD - circumscribed, inscribed, face-centered) and Box-Behnken designs.
  - Full quadratic regression fitting with blocking factors.
  - Response Optimizer (desirability functions $d(y)$ and composite $D$).
  - 2D Contour Maps with bilinear probing and 3D Surface Plots.
- **Mixture Designs**:
  - Simplex Centroid, Simplex Lattice, Extreme Vertices designs.
  - Scheffé canonical polynomial modeling (linear, quadratic, special cubic).
  - Process variable interactions.
- **Taguchi Robust Designs**:
  - Orthogonal arrays ($L_4$ to $L_{36}$), Signal-to-Noise (S/N) ratios (Larger-is-better, Smaller-is-better, Nominal-is-best), and Dynamic Taguchi analysis.

### 5. Data Manipulation & Calculator
- **Mathematical Calculator**:
  - Direct arithmetic, trigonometric, exponential, and statistical column transformations.
  - Column formula assignment with dynamic recomputation on data edits.
- **Make Patterned Data**:
  - Simple numeric sequences with step and repetition parameters.
  - Arbitrary numeric lists with repeat-each and repeat-sequence multipliers.
  - Discrete text factor sequences.
- **Random Data Generation**:
  - Normal, Uniform, Exponential, Poisson, and Binomial pseudorandom generators.
- **Data Preparation**:
  - Stack / Unstack columns, Transpose, Sort, Rank, Standardize (Z-score, range, scale).
  - Worksheet merging and splitting.

### 6. StatCraft Connect (Cross-Modal Analytical Workflow)
- **Unified Tri-Modal Analysis**:
  - Seamlessly move between **Minitab-style statistical dialogs**, **JMP-style interactive visual analysis**, and the integrated **R Workbench**.
  - Contextual **Open in Interactive Explorer** launches dynamic bivariate fits and prediction profilers directly from regression output without manual re-entry.
  - Contextual **Open in R** generates robust, formatted R scripts (`lm()`, ANOVA, and diagnostic plotting) with complete variable and parameter fidelity.
- **Durable Observation & Analysis Identities**:
  - Observation rows retain permanent UUIDs across sorting, filtering, and reordering.
  - Column renames, moves, and insertions preserve model bindings automatically.
  - Omitted/missing rows are strictly preserved as `None` when syncing predictions back from external scripts.
- **Bi-Directional Worksheet Synchronization**:
  - Automatically exports and imports model predictions (`FITS_...`) and residuals (`RESI_...`) aligned directly by observation identity.
  - Stale detection alerts users when source worksheet data is altered after model fitting.
- **Linked Graph Brushing & Named Selections**:
  - Brushing observations on interactive charts highlights corresponding worksheet rows in real time.
  - Save brushed subsets as named selections or push directly into R as `df_subset` for immediate deep-dive exploration.

### 7. File Compatibility & Export
- **MPX File Compatibility**:
  - Directly open, edit, and navigate `.mpx` and `.mwx` project containers.
  - Preserves native variable bindings, column formatting, and metadata across edits.
- **Office & Presentation Export**:
  - Export worksheets and reports to Microsoft Excel (`.xlsx`), Word (`.docx`), and PowerPoint (`.pptx`).
  - High-resolution PDF generation and print preview.

---

## Installation & Setup

### Option 1: Modern Windows Installer (Recommended)
Download **`StatCraft-Setup.exe`** from the [Latest Releases](https://github.com/SkinnDeep/StatCraft/releases):
1. Run `StatCraft-Setup-v104.0.0-Windows-x64.exe`.
2. Follow the 4-step wizard to install StatCraft to your user directory (no administrator elevation required).
3. StatCraft creates Desktop and Start Menu shortcuts and configures background update checks.
4. Future updates can be checked and installed anytime via **`Help > Check for Updates…`**.

*Silent / Enterprise Deployment:*
```powershell
StatCraft-Setup.exe --silent --dir "C:\Program Files\StatCraft"
```

### Option 2: Standalone Portable Binary
Download **`StatCraft-v104.0.0-Windows-x64.exe`**. No installation required—simply double-click and run.

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

StatCraft is built on the cross-platform Qt6 (PySide6) framework. Official pre-compiled releases are structured as follows:

| Platform | Current Status | Release Artifact |
|---|---|---|
| **Windows x64** | **Available (v104.0.0)** | `StatCraft-Setup.exe`, `StatCraft.exe` |
| **macOS (Apple Silicon & Intel)** | *In Preparation* | `.dmg` installer & standalone `.app` bundle |
| **Linux (x86_64)** | *In Preparation* | `AppImage` & `.deb` package |

Source execution is already fully functional on macOS and Linux by running `python launch_modern.py`.

---

## Testing & Quality Assurance

StatCraft maintains rigorous test suites covering calculations, numerical invariants, and visual components:

```bash
# Run the complete test suite
python -m unittest discover tests
```

---

## Contributing & License

Contributions, feature requests, and issue reports are welcome! Please open an issue or pull request on GitHub.

Distributed under the **MIT License**. See `LICENSE` for details.
