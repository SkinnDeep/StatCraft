"""Smart 'Next Best Step' Statistical Guidance Chips for StatCraft.

Analyzes active statistical results and surfaces context-aware next actions
for quality engineers, Six Sigma practitioners, and researchers.
"""
from __future__ import annotations

from typing import Any, Dict, List
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


def get_smart_guidance_chips(entry: Dict[str, Any]) -> List[Dict[str, str]]:
    """Determine context-aware smart next steps based on result metrics."""
    result = entry.get("result", {})
    recipe = entry.get("recipe", {})
    action = recipe.get("action", "")
    analysis = result.get("analysis", action)

    chips: List[Dict[str, str]] = []

    # 1. Normality test failures
    p_norm = result.get("normality_p") or result.get("anderson_darling_p")
    if p_norm is not None and p_norm < 0.05:
        chips.append({
            "label": "⚡ Try Johnson Transformation",
            "action": "johnson_transformation",
            "description": "Transform non-normal data into standard normal distribution"
        })
        chips.append({
            "label": "📊 Nonparametric Capability",
            "action": "capability_nonparametric",
            "description": "Evaluate process capability without normality assumptions"
        })

    # 2. Significant ANOVA -> Tukey HSD post-hoc
    if ("anova" in analysis or action in ("oneway_anova", "twoway_anova")) and result.get("p_value", 1.0) < 0.05:
        chips.append({
            "label": "🔍 Tukey Multiple Comparisons",
            "action": "tukey_comparisons",
            "description": "Identify specific group pairs with statistically significant differences"
        })

    # 3. Regression -> Multicollinearity / Outliers
    if "regression" in analysis or action in ("multiple_regression", "linear_regression"):
        if result.get("unusual_observations"):
            chips.append({
                "label": "📈 4-in-1 Residual Diagnostics",
                "action": "residual_plots",
                "description": "Inspect outliers and high leverage observations"
            })
        if any(c.get("vif", 1.0) > 5.0 for c in result.get("coefficients", [])):
            chips.append({
                "label": "⚙️ Stepwise Variable Selection",
                "action": "stepwise_regression",
                "description": "Reduce multicollinearity by selecting optimal subset of predictors"
            })

    # 4. Capability Analysis -> What-If or Centering
    if "capability" in analysis or action in ("capability_analysis", "normal_capability"):
        cpk = result.get("cpk")
        if cpk is not None and cpk < 1.0:
            chips.append({
                "label": "⚡ Live What-If Tolerance Simulation",
                "action": "what_if_tolerance",
                "description": "Simulate capability gain from shifting process mean toward target"
            })

    # 5. Out of control SPC chart -> Cause and Effect
    if ("control_chart" in analysis or "spc" in analysis) and result.get("rule_violations"):
        chips.append({
            "label": "🐟 Cause-and-Effect (Fishbone)",
            "action": "fishbone_diagram",
            "description": "Brainstorm root causes for detected special cause alarms"
        })

    # 6. Predictive Analytics cross-model exploration
    if analysis in ("random_forest", "treenet_gbm", "mars_regression"):
        chips.append({
            "label": "🏆 Discover Best Model (AutoML)",
            "action": "discover_best_model",
            "description": "Benchmark CART, Random Forests, TreeNet, MARS, and Linear/Logistic side-by-side"
        })
    if analysis in ("multiple_regression", "linear_regression") and (result.get("r_sq") or 1.0) < 0.70:
        chips.append({
            "label": "🌲 Try Random Forests / MARS",
            "action": "random_forest",
            "description": "Capture non-linear curvature and interactions missed by linear regression"
        })

    return chips


class GuidanceChipsBar(QFrame):
    """Horizontal pill strip displaying actionable smart next steps."""
    actionTriggered = Signal(str, dict)

    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName("guidanceChipsBar")
        self.setStyleSheet("""
            #guidanceChipsBar {
                background: #F1F5F9;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 6px 12px;
                margin-top: 10px;
            }
        """)

        chips = get_smart_guidance_chips(entry)
        if not chips:
            self.setVisible(False)
            return

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        lbl = QLabel("Suggested Next Steps:")
        lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #475569;")
        layout.addWidget(lbl)

        for chip in chips:
            btn = QPushButton(chip["label"])
            btn.setToolTip(chip["description"])
            btn.setStyleSheet("""
                QPushButton {
                    background: #FFFFFF;
                    border: 1px solid #CBD5E1;
                    border-radius: 12px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    color: #0369A1;
                }
                QPushButton:hover {
                    background: #E0F2FE;
                    border-color: #38BDF8;
                }
            """)
            act = chip["action"]
            btn.clicked.connect(lambda checked=False, a=act: self.actionTriggered.emit(a, self.entry))
            layout.addWidget(btn)

        layout.addStretch()
