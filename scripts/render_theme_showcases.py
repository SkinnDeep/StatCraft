import os
import sys
from pathlib import Path

if "QT_QPA_PLATFORM" in os.environ:
    del os.environ["QT_QPA_PLATFORM"]
os.environ["STATCRAFT_TESTING"] = "1"

root = Path(__file__).resolve().parent.parent
deps = root.parent / "statcraft-build-deps"
if deps.exists() and str(deps) not in sys.path:
    sys.path.insert(0, str(deps))
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize
from statcraft.modern_app import ModernWindow
from statcraft.model import Worksheet, Column
from statcraft.r_bridge import is_r_available

app = QApplication.instance() or QApplication([])

artifact_dir = Path(r"C:\Users\funny\.gemini\antigravity\brain\3cf39c38-17ed-4d7e-8ad6-672fcb3ec68a")
docs_img = root / "docs" / "images"

r_script = (
    "# --- StatCraft R Integration: Linear Modeling & Diagnostics ---\n"
    "# 'df' is automatically bound to the active StatCraft worksheet\n"
    "fit <- lm(Strength ~ Diameter, data=df)\n"
    "summary(fit)\n\n"
    "# Plot fitted line and confidence interval\n"
    "plot(df$Diameter, df$Strength, pch=19, col='#0284c7', cex=1.2,\n"
    "     main='Strength vs Diameter (OLS Model)',\n"
    "     xlab='Diameter (mm)', ylab='Tensile Strength (MPa)')\n"
    "abline(fit, col='#ef4444', lwd=2)\n"
    "grid(col='#cbd5e1', lty='dotted')\n\n"
    "# Push results back to a new StatCraft worksheet tab\n"
    "diagnostics <- data.frame(Fitted=fitted(fit), Residuals=resid(fit))\n"
    "statcraft_export(diagnostics, 'Model_Diagnostics')\n"
)

def setup_demo_window(dark: bool, mode: str):
    win = ModernWindow()
    win.resize(1380, 860)
    
    # Sample data
    import random
    rng = random.Random(42)
    diams = [round(rng.uniform(10.0, 30.0), 2) for _ in range(25)]
    strengths = [round(diams[i] * 6.84 + 412.35 + rng.gauss(0, 4.8), 2) for i in range(25)]
    
    ws = Worksheet("Tensile_Test", [
        Column("Diameter", kind="number", values=diams, metadata={"modeling_type": "continuous"}),
        Column("Strength", kind="number", values=strengths, metadata={"modeling_type": "continuous"}),
        Column("Batch", kind="text", values=["Batch A" if i % 2 == 0 else "Batch B" for i in range(25)], metadata={"modeling_type": "nominal"}),
    ])
    win.presenter.worksheet = ws
    win.refresh()
    
    win.set_dark_mode(dark)
    win.set_ui_mode(mode)
    
    if mode == "r" and win.r_workbench:
        win.r_workbench.editor.setPlainText(r_script)
        win.r_workbench.console_output.appendPlainText(
            "> summary(fit)\n\nCall:\nlm(formula = Strength ~ Diameter, data = df)\n\n"
            "Coefficients:\n            Estimate Std. Error t value Pr(>|t|)\n"
            "(Intercept)  412.352     14.281   28.87  < 2e-16 ***\n"
            "Diameter       6.841      1.354    5.05  3.7e-05 ***\n---\n"
            "Signif. codes:  0 '***' 0.001 '**' 0.01 '*' 0.05 '.' 0.1 ' ' 1\n\n"
            "Residual standard error: 4.821 on 23 degrees of freedom\n"
            "Multiple R-squared:  0.526,    Adjusted R-squared:  0.505\n"
            "F-statistic: 25.53 on 1 and 23 DF,  p-value: 3.73e-05\n"
        )
    
    win.show()
    app.processEvents()
    return win

# 1. R Workbench Light
win_r_light = setup_demo_window(dark=False, mode="r")
pix1 = win_r_light.grab()
pix1.save(str(artifact_dir / "r-workbench-light.png"))
pix1.save(str(docs_img / "r-workbench.png"))
win_r_light.close()
win_r_light.deleteLater()
app.processEvents()
print("Saved r-workbench-light.png and docs/images/r-workbench.png")

# 2. R Workbench Dark
win_r_dark = setup_demo_window(dark=True, mode="r")
pix2 = win_r_dark.grab()
pix2.save(str(artifact_dir / "r-workbench-dark.png"))
win_r_dark.close()
win_r_dark.deleteLater()
app.processEvents()
print("Saved r-workbench-dark.png")

# 3. Minitab Mode Dark
win_m_dark = setup_demo_window(dark=True, mode="minitab")
pix3 = win_m_dark.grab()
pix3.save(str(artifact_dir / "minitab-dark.png"))
win_m_dark.close()
win_m_dark.deleteLater()
app.processEvents()
print("Saved minitab-dark.png")

# 4. JMP Mode Dark
win_j_dark = setup_demo_window(dark=True, mode="jmp")
pix4 = win_j_dark.grab()
pix4.save(str(artifact_dir / "jmp-dark.png"))
win_j_dark.close()
win_j_dark.deleteLater()
app.processEvents()
print("Saved jmp-dark.png")

print("All screenshots successfully rendered.")
