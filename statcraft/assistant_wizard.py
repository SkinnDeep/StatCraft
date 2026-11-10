"""Interactive Guided Analysis Assistant Wizard (Minitab Assistant Parity).

Provides a clean decision-tree workflow wizard that guides engineers and researchers
from their analytical question (data type, comparison count, normality/linearity)
to the optimal StatCraft procedure with key assumptions, alternatives, and one-click launch.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


# Track -> Options -> Recommendation Mapping
ASSISTANT_TRACKS: List[Dict[str, Any]] = [
    {
        "id": "graphical",
        "title": "1. Graphical Analysis",
        "subtitle": "Visualize distributions, relationships, or group comparisons",
        "questions": [
            ("goal", "What would you like to explore?", [
                ("distribution", "Distribution of a single continuous variable (Histogram / Boxplot)"),
                ("compare_groups", "Compare distributions across groups (Individual Value / Boxplot)"),
                ("relationship", "Relationship between two numeric X/Y variables (Scatter / Graph Builder)"),
                ("variation", "Sources of variation across multiple factors (Multi-Vari Chart)"),
            ]),
        ],
    },
    {
        "id": "hypothesis",
        "title": "2. Hypothesis Tests",
        "subtitle": "Test targets, group means/medians, variances, or proportions",
        "questions": [
            ("data_type", "What type of response data do you have?", [
                ("continuous", "Continuous measurement (e.g., length, temperature, weight)"),
                ("attribute", "Pass/Fail proportions or categorical counts"),
            ]),
            ("groups", "How many samples or groups are you comparing?", [
                ("one", "1 sample compared against a target / standard"),
                ("two_ind", "2 independent samples"),
                ("two_paired", "2 paired / before-and-after measurements"),
                ("three_plus", "3 or more independent groups"),
            ]),
            ("normal", "Are data approximately normal (or large sample >= 30)?", [
                ("yes", "Yes — parametric assumptions reasonable"),
                ("no", "No — heavily skewed / ordinal (use nonparametric)"),
            ]),
        ],
    },
    {
        "id": "predictive",
        "title": "3. Regression & Predictive ML",
        "subtitle": "Model Y = f(X), uncover drivers, or benchmark ML algorithms",
        "questions": [
            ("task", "What is your modeling objective?", [
                ("linear", "Interpretable linear equation with p-values & VIF"),
                ("binary", "Predict binary Yes/No outcome (Logistic Regression)"),
                ("nonlinear_trees", "Non-linear patterns / interactions with Decision Tree (CART)"),
                ("rf", "High-accuracy ensemble with OOB error (Random Forests®)"),
                ("treenet", "Top predictive accuracy boosting (TreeNet® GBM)"),
                ("mars", "Piecewise linear hinge splines (MARS® Regression)"),
                ("automl", "Benchmark all models & pick champion (Discover Best Model®)"),
            ]),
        ],
    },
    {
        "id": "spc",
        "title": "4. Control Charts (SPC)",
        "subtitle": "Monitor process stability over time & detect special causes",
        "questions": [
            ("data_type", "What kind of quality characteristic are you monitoring?", [
                ("continuous_ind", "Continuous individual measurements (subgroup size = 1)"),
                ("continuous_sub", "Continuous rational subgroups (size 2–8+ per sample)"),
                ("defective", "Pass/Fail proportion defective (P / NP chart)"),
                ("defects", "Defect counts per unit / area (C / U chart)"),
                ("small_shift", "Detect small sustained process shifts (< 1.5 sigma) via EWMA"),
                ("multivariate", "Monitor correlated variables simultaneously (Hotelling T²)"),
            ]),
        ],
    },
    {
        "id": "capability",
        "title": "5. Process Capability",
        "subtitle": "Assess Cp/Cpk, Pp/Ppk, Sigma Level & DPMO against specs",
        "questions": [
            ("dist", "What is your process data distribution?", [
                ("normal", "Continuous & normally distributed (Normal Capability)"),
                ("nonnormal", "Continuous & non-normal / skewed (Weibull / Box-Cox)"),
                ("attribute", "Pass/Fail or Defect counts (Binomial / Poisson Capability)"),
                ("six_sigma", "Full Six Sigma Process Report (Z-bench LT/ST & DPMO)"),
            ]),
        ],
    },
    {
        "id": "msa_doe",
        "title": "6. MSA & Design of Experiments",
        "subtitle": "Evaluate measurement repeatability or design multifactor experiments",
        "questions": [
            ("goal", "Which quality engineering study do you need?", [
                ("gage_rr", "Measure repeatability & reproducibility across parts & operators (Gage R&R)"),
                ("attr_agree", "Assess appraiser agreement on pass/fail classifications"),
                ("factorial_doe", "Screen factors & estimate interactions (2-Level Factorial DOE)"),
                ("balanced_anova", "Analyze balanced multi-factor fixed/random experiment"),
            ]),
        ],
    },
]


def recommend_analysis(track_id: str, choices: Dict[str, str]) -> Dict[str, Any]:
    """Resolve track & decision choices into an actionable recommendation dict."""
    if track_id == "graphical":
        g = choices.get("goal", "distribution")
        table = {
            "distribution": ("Graphical Summary & Histogram", "graphical_summary_dialog", (), "Displays histogram, Anderson-Darling normality test, boxplot, and 95% CIs.", "Requires numeric column.", "Use Bar Chart for categorical counts."),
            "compare_groups": ("Boxplot / Individual Value Plot", "graph", ("boxplot",), "Compares center, spread, and outliers cleanly across categories.", "Side-by-side numeric distributions.", "Use Contingency Table for categorical responses."),
            "relationship": ("Interactive Graph Builder (21 Plot Types)", "graph", ("builder",), "Explore scatterplots, fitted lines, wafer maps, heatmaps, and marginals.", "At least one numeric or categorical column.", "Use Fit Y by X for statistical p-values."),
            "variation": ("Multi-Vari Chart", "multivari_dialog", (), "Visualizes within-part, between-part, and temporal variance hierarchies.", "Continuous response + 2–4 factor columns.", "Use Fully Nested ANOVA for formal variance components."),
        }
        name, method, args, why, req, alt = table.get(g, table["distribution"])
    elif track_id == "hypothesis":
        dt = choices.get("data_type", "continuous")
        grp = choices.get("groups", "two_ind")
        norm = choices.get("normal", "yes") == "yes"
        if dt == "attribute":
            if grp == "one":
                name, method, args, why, req, alt = ("1 Proportion Test", "one_sample_proportion_dialog", (), "Tests single defect/event rate against a target proportion.", "Binary outcomes or summarized counts.", "Use 1-Sample Poisson for rates per unit.")
            elif grp in ("two_ind", "two_paired"):
                name, method, args, why, req, alt = ("2 Proportions Test", "two_sample_proportion_dialog", (), "Compares event rates between two independent populations.", "Counts and sample sizes per group.", "Use Chi-Square Association for >2 categories.")
            else:
                name, method, args, why, req, alt = ("Chi-Square Test for Association", "chi_square_association_dialog", (), "Tests independence across contingency tables with >=2 categories.", "Expected cell counts generally >= 5.", "Use Fisher's Exact / Monte Carlo for sparse cells.")
        else:
            if grp == "one":
                name, method, args, why, req, alt = (
                    ("1-Sample t-Test", "one_sample_t_dialog", (), "Tests whether population mean equals target when sigma is unknown.", "Approximate normality or N >= 20.", "1-Sample Wilcoxon / Sign Test.")
                    if norm else
                    ("1-Sample Sign / Wilcoxon Test", "one_sample_wilcoxon_dialog", (), "Nonparametric location test robust to skew and outliers.", "Continuous/ordinal symmetric data (Wilcoxon).", "Use 1-Sample Randomization Test.")
                )
            elif grp == "two_paired":
                name, method, args, why, req, alt = (
                    ("Paired t-Test", "paired_t_dialog", (), "Tests mean difference of matched before/after observations.", "Differences approximately normal.", "Paired Wilcoxon Signed-Rank Test.")
                    if norm else
                    ("Paired Wilcoxon Signed-Rank Test", "paired_wilcoxon_dialog", (), "Nonparametric paired median-difference test.", "Matched observation columns.", "1-Sample Randomization Test on differences.")
                )
            elif grp == "two_ind":
                name, method, args, why, req, alt = (
                    ("2-Sample t-Test", "two_sample_t_dialog", (), "Compares two independent group means using Welch's unpooled t.", "Independent samples; approximate normality.", "Mann-Whitney U Test.")
                    if norm else
                    ("Mann-Whitney U Test", "mann_whitney_dialog", (), "Nonparametric rank test comparing two independent sample medians.", "Two independent numeric samples.", "2-Sample Randomization Test.")
                )
            else:
                name, method, args, why, req, alt = (
                    ("One-Way ANOVA", "oneway_anova_dialog", (), "Compares 3+ group means with Welch/Tukey/Fisher options.", "Independent samples with roughly similar variance.", "Kruskal-Wallis Test.")
                    if norm else
                    ("Kruskal-Wallis Test", "kruskal_wallis_dialog", (), "Nonparametric rank ANOVA comparing 3+ independent groups.", "Numeric response + grouping factor.", "Mood's Median Test.")
                )
    elif track_id == "predictive":
        tk = choices.get("task", "linear")
        table = {
            "linear": ("Fit Multiple Regression Model", "multiple_regression", (), "Estimates interpretable slopes, t/p-values, VIFs, and R².", "Linear relationship with numeric response.", "Use MARS® or Random Forests® if curved."),
            "binary": ("Binary Logistic Regression", "fit_binary_logistic", (), "Models event log-odds, odds ratios, ROC-AUC, and deviance.", "Binary (2-class) outcome.", "Use Random Forests® or TreeNet® for non-linear boundaries."),
            "nonlinear_trees": ("CART® Decision Tree", "cart_tree_dialog", (), "Generates visual if-then decision rules and terminal node stats.", "Continuous or categorical Y + numeric/text X.", "Upgrade to Random Forests® for lower variance."),
            "rf": ("Random Forests®", "random_forest_dialog", (), "Ensemble bagging of trees with Out-of-Bag accuracy & predictor importance.", "Continuous or categorical Y; handles noisy features well.", "Compare with TreeNet® in Discover Best Model®."),
            "treenet": ("TreeNet® Gradient Boosting", "treenet_dialog", (), "Sequential boosted trees with shrinkage & holdout optimal tree count.", "Continuous or classification Y; top predictive accuracy.", "Check MARS® for explicit spline equations."),
            "mars": ("MARS® Multivariate Splines", "mars_dialog", (), "Fits piecewise linear hinge equations pruned by GCV.", "Continuous or binary Y with interactions/thresholds.", "Compare via Discover Best Model®."),
            "automl": ("Discover Best Model® AutoML", "discover_best_model_dialog", (), "Trains & ranks Linear/Logistic, CART, Random Forests, TreeNet & MARS on holdout data.", "At least ~15+ complete rows.", "Inspect winning model directly afterwards."),
        }
        name, method, args, why, req, alt = table.get(tk, table["linear"])
    elif track_id == "spc":
        dt = choices.get("data_type", "continuous_ind")
        table = {
            "continuous_ind": ("Individuals & Moving Range (I-MR) Chart", "imr_dialog", (), "Standard SPC chart for individual measurements (subgroup size = 1).", "Sequential numeric measurements.", "Use EWMA for small sustained shifts."),
            "continuous_sub": ("Xbar-R Subgroup Chart", "xbar_r_dialog", (), "Monitors subgroup mean and within-subgroup range (n = 2–8).", "Numeric data with subgroup column or constant size.", "Use Xbar-S when subgroup size > 8."),
            "defective": ("Attribute P Chart", "attribute_control_dialog", ("P",), "Tracks proportion defective when subgroup sizes vary.", "Defect counts + subgroup sample sizes.", "Use Laney P' if data are overdispersed."),
            "defects": ("Attribute U Chart", "attribute_control_dialog", ("U",), "Tracks defects per inspection unit.", "Defect counts + unit counts.", "Use C Chart when inspection size is constant."),
            "small_shift": ("EWMA Control Chart", "ewma_dialog", (), "Exponential weighting detects 0.5–1.5 sigma shifts faster than Shewhart.", "Sequential observations.", "Use CUSUM for tabular shift tracking."),
            "multivariate": ("Hotelling T² Control Chart", "tsquared_chart_dialog", (), "Monitors multiple correlated CTQs simultaneously.", "2+ correlated numeric columns.", "Follow up with I-MR on out-of-control contributors."),
        }
        name, method, args, why, req, alt = table.get(dt, table["continuous_ind"])
    elif track_id == "capability":
        dist = choices.get("dist", "normal")
        table = {
            "normal": ("Normal Capability Analysis", "capability", (), "Computes Cp, Cpk, Pp, Ppk, and expected PPM/DPMO.", "In-control normal continuous measurements + LSL/USL.", "Run Nonnormal or Six Sigma Report."),
            "nonnormal": ("Nonnormal Capability Analysis", "capability_nonnormal_dialog", (), "Fits Weibull/Gamma/Lognormal quantiles for skewed measurements.", "Positive or skewed continuous measurements + specs.", "Use Nonparametric Capability if no curve fits."),
            "attribute": ("Attribute Capability (Binomial)", "attribute_capability_dialog", ("binomial",), "Computes % defective, DPMO, and Z-bench for Pass/Fail data.", "Defect counts & sample sizes.", "Use Poisson Capability for defects per unit."),
            "six_sigma": ("Six Sigma Process Report", "six_sigma_process_dialog", (), "Executive Z-bench (LT/ST), sigma level, observed/expected DPMO & capability.", "Numeric measurement + at least one spec limit.", "Use Six Sigma RTY for multi-step rolled yield."),
        }
        name, method, args, why, req, alt = table.get(dist, table["normal"])
    else:  # msa_doe
        g = choices.get("goal", "gage_rr")
        table = {
            "gage_rr": ("Gage R&R Study (Crossed)", "gage_rr", (), "Decomposes %StudyVar into Repeatability, Reproducibility & Part-to-Part.", "Measurement + Part + Operator columns.", "Use Nested Gage R&R for destructive testing."),
            "attr_agree": ("Attribute Agreement Analysis", "attribute_agreement_dialog", (), "Computes Kappa & % agreement within/between appraisers vs standard.", "Appraiser ratings + Sample IDs.", "Use Attribute Gage (Analytic) for continuous reference bias."),
            "factorial_doe": ("Create 2-Level Factorial Design", "create_factorial", (), "Generates randomized full/fractional designs with center points & blocks.", "Define 2–8 experimental factors.", "Use Response Surface DOE for curvature optimization."),
            "balanced_anova": ("Balanced ANOVA", "balanced_anova_dialog", (), "Analyzes equal-cell multifactor designs with F-tests & interactions.", "Balanced response + factor columns.", "Use Mixed Effects (REML) for unbalanced random factors."),
        }
        name, method, args, why, req, alt = table.get(g, table["gage_rr"])

    return {
        "name": name,
        "method": method,
        "args": args,
        "why": why,
        "requirements": req,
        "alternative": alt,
    }


class GuidedAssistantDialog(QDialog):
    """Interactive Minitab-style Guided Analysis Assistant Wizard."""

    def __init__(self, parent: Optional[QWidget] = None, dark_mode: bool = False):
        super().__init__(parent)
        self.setWindowTitle("StatCraft Guided Analysis Assistant")
        self.resize(840, 560)
        self.chosen_method: Optional[str] = None
        self.chosen_args: Tuple[Any, ...] = ()
        self._current_track_idx = 0
        self._choices: Dict[str, str] = {}
        self._question_groups: List[QButtonGroup] = []

        self._apply_style(dark_mode)
        self._build_ui()
        self._select_track(0)

    def _apply_style(self, dark_mode: bool) -> None:
        if dark_mode:
            self.setStyleSheet("""
                QDialog { background-color: #18181b; color: #f4f4f5; font-family: 'Segoe UI', sans-serif; }
                QLabel { color: #f4f4f5; }
                QLabel#muted { color: #a1a1aa; font-size: 8.5pt; }
                QListWidget { background-color: #1f1f23; border: 1px solid #3f3f46; border-radius: 6px; padding: 4px; color: #e4e4e7; }
                QListWidget::item { padding: 8px 10px; border-radius: 4px; }
                QListWidget::item:selected { background-color: #0284c7; color: #ffffff; font-weight: 600; }
                QFrame#card { background-color: #1f1f23; border: 1px solid #3f3f46; border-radius: 8px; }
                QRadioButton { color: #e4e4e7; padding: 3px 0; }
                QPushButton#launchBtn { background-color: #0284c7; color: #ffffff; font-weight: 600; border: none; border-radius: 6px; padding: 8px 18px; }
                QPushButton#launchBtn:hover { background-color: #0369a1; }
            """)
        else:
            self.setStyleSheet("""
                QDialog { background-color: #f8fafc; color: #0f172a; font-family: 'Segoe UI', sans-serif; }
                QLabel#muted { color: #475569; font-size: 8.5pt; }
                QListWidget { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 4px; color: #0f172a; }
                QListWidget::item { padding: 8px 10px; border-radius: 4px; }
                QListWidget::item:selected { background-color: #0284c7; color: #ffffff; font-weight: 600; }
                QFrame#card { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 8px; }
                QPushButton#launchBtn { background-color: #0284c7; color: #ffffff; font-weight: 600; border: none; border-radius: 6px; padding: 8px 18px; }
                QPushButton#launchBtn:hover { background-color: #0369a1; }
            """)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(12)

        hdr = QLabel("<b>Guided Analysis Assistant</b> — Choose what you want to accomplish and answer a few quick questions:")
        root.addWidget(hdr)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.track_list = QListWidget()
        self.track_list.setMinimumWidth(230)
        for tr in ASSISTANT_TRACKS:
            item = QListWidgetItem(tr["title"])
            item.setToolTip(tr["subtitle"])
            self.track_list.addItem(item)
        self.track_list.currentRowChanged.connect(self._select_track)
        splitter.addWidget(self.track_list)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)

        self.track_subtitle = QLabel()
        self.track_subtitle.setObjectName("muted")
        self.track_subtitle.setWordWrap(True)
        right_layout.addWidget(self.track_subtitle)

        self.questions_box = QVBoxLayout()
        self.questions_box.setSpacing(8)
        right_layout.addLayout(self.questions_box)

        self.rec_card = QFrame()
        self.rec_card.setObjectName("card")
        rec_layout = QVBoxLayout(self.rec_card)
        rec_layout.setContentsMargins(14, 12, 14, 12)
        rec_layout.setSpacing(6)
        self.rec_title = QLabel()
        self.rec_title.setStyleSheet("font-size: 11pt; font-weight: 700; color: #0284c7;")
        self.rec_title.setWordWrap(True)
        self.rec_why = QLabel()
        self.rec_why.setWordWrap(True)
        self.rec_req = QLabel()
        self.rec_req.setObjectName("muted")
        self.rec_req.setWordWrap(True)
        self.rec_alt = QLabel()
        self.rec_alt.setObjectName("muted")
        self.rec_alt.setWordWrap(True)
        rec_layout.addWidget(self.rec_title)
        rec_layout.addWidget(self.rec_why)
        rec_layout.addWidget(self.rec_req)
        rec_layout.addWidget(self.rec_alt)
        right_layout.addWidget(self.rec_card)
        right_layout.addStretch(1)

        splitter.addWidget(right_panel)
        splitter.setSizes([250, 560])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        self.launch_btn = QPushButton("Open Recommended Tool →")
        self.launch_btn.setObjectName("launchBtn")
        self.launch_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        footer.addWidget(self.launch_btn)
        root.addLayout(footer)

    def _clear_questions(self) -> None:
        self._question_groups.clear()
        while self.questions_box.count():
            child = self.questions_box.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _select_track(self, row: int) -> None:
        if row < 0 or row >= len(ASSISTANT_TRACKS):
            return
        self._current_track_idx = row
        track = ASSISTANT_TRACKS[row]
        self.track_subtitle.setText(track["subtitle"])
        self._choices = {}
        self._clear_questions()

        for q_key, q_prompt, options in track["questions"]:
            card = QFrame()
            card.setObjectName("card")
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(12, 8, 12, 8)
            c_lay.setSpacing(4)
            lbl = QLabel(f"<b>{q_prompt}</b>")
            c_lay.addWidget(lbl)
            grp = QButtonGroup(card)
            self._question_groups.append(grp)
            for idx_opt, (opt_val, opt_label) in enumerate(options):
                rb = QRadioButton(opt_label)
                if idx_opt == 0:
                    rb.setChecked(True)
                    self._choices[q_key] = opt_val
                rb.toggled.connect(lambda checked, k=q_key, v=opt_val: self._on_option(k, v, checked))
                grp.addButton(rb)
                c_lay.addWidget(rb)
            self.questions_box.addWidget(card)

        self._update_recommendation()

    def _on_option(self, key: str, value: str, checked: bool) -> None:
        if checked:
            self._choices[key] = value
            self._update_recommendation()

    def _update_recommendation(self) -> None:
        track_id = ASSISTANT_TRACKS[self._current_track_idx]["id"]
        rec = recommend_analysis(track_id, self._choices)
        self.chosen_method = rec["method"]
        self.chosen_args = rec["args"]
        self.rec_title.setText(f"Recommended: {rec['name']}")
        self.rec_why.setText(f"<b>Why:</b> {rec['why']}")
        self.rec_req.setText(f"<b>Data Requirements:</b> {rec['requirements']}")
        self.rec_alt.setText(f"<b>Alternative:</b> {rec['alternative']}")
