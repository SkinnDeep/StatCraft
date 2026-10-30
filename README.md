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

### 6. File Compatibility & Export
- **MPX File Compatibility**:
  - Directly open, edit, and navigate `.mpx` and `.mwx` project containers.
  - Preserves native variable bindings, column formatting, and metadata across edits.
- **Office & Presentation Export**:
  - Export worksheets and reports to Microsoft Excel (`.xlsx`), Word (`.docx`), and PowerPoint (`.pptx`).
  - High-resolution PDF generation and print preview.

---

## Installation & Setup

### Option 1: Lightweight Web Installer (Recommended)
Download **`StatCraft-Setup-v104.0.0-Windows-x64.exe`** from the [Latest Releases](https://github.com/SkinnDeep/StatCraft/releases):
1. Run `StatCraft-Setup-v104.0.0-Windows-x64.exe`.
2. Follow the modern setup wizard to install StatCraft to your user directory (no administrator elevation required). The installer automatically downloads and verifies the application package directly from GitHub releases.
3. StatCraft creates Desktop and Start Menu shortcuts, registers in Windows **Add/Remove Programs**, and configures background update checks.
4. Future updates can be checked and applied anytime via **`Help > Check for Updates…`**.

> [!NOTE]
> **Windows Defender SmartScreen Notice:**
> Because StatCraft is an independent open-source release (and does not use a commercial \$500/year enterprise certificate), Windows Defender SmartScreen may show a prompt saying *"Windows protected your PC"* on your first download.
> - Simply click **"More info"** &rarr; **"Run anyway"**.
> - This is standard for newly released open-source software on GitHub. As downloads and clean telemetry accumulate with Microsoft, this prompt clears automatically.

*Silent / Automated Deployment:*
```powershell
StatCraft-Setup-v104.0.0-Windows-x64.exe --silent --dir "$env:LOCALAPPDATA\StatCraft"
```

### Option 2: Standalone Portable Binary
Download **`StatCraft-v104.0.0-Windows-x64.exe`**. No installation required—simply double-click and run directly anywhere.

### Uninstallation
StatCraft integrates cleanly with standard Windows application management:
- Go to **Windows Settings &rarr; Apps &rarr; Installed apps**, find **StatCraft**, and click **Uninstall**.
- Or run `StatCraft-Uninstall.exe` in `%LOCALAPPDATA%\StatCraft`.
- Shortcuts, registry keys, and program files are removed completely without leaving clutter behind.

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

## Automated Releases & Publishing

Releases are fully automated with zero manual browser uploads required:

### Method 1: Cloud Automation (GitHub Actions)
Pushing any version tag automatically triggers GitHub Actions to build both the standalone application and web setup installer, create the release on GitHub, and attach the binaries:
```bash
git tag v105.0.0
git push origin v105.0.0
```
You can also trigger a release build on demand from the **Actions** tab on GitHub by selecting **Build & Publish Release** &rarr; **Run workflow**.

### Method 2: Local 1-Click Publisher
To package, Authenticode code-sign, and publish directly from your terminal:
```powershell
# Build, sign, and upload release automatically
.\publish_release.ps1

# Or skip rebuild and upload existing output binaries immediately
.\publish_release.ps1 -SkipBuild
```

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
