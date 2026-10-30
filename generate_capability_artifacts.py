"""Generate demonstration artifacts for Preview 58: Capability Analysis (Normal Distribution)."""
import os, sys, json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'work/statcraft'))
sys.path.insert(0, str(root / 'work/statcraft-build-deps'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import numpy as np
from PySide6.QtWidgets import QApplication
from statcraft.mpx_io import MPXWorkbook
from statcraft.capability_engine import run_normal_capability
from statcraft.capability_report import format_normal_capability_report
from statcraft.capability_chart import CapabilityPlotWidget
from statcraft.capability_dialogs import CapabilityDialog
from statcraft.export_office import export_analysis_to_docx, export_analysis_to_pptx

app = QApplication.instance() or QApplication(sys.argv)

# Generate realistic baseline manufacturing dataset (e.g., Piston Ring Diameters, target 74.0, LSL 73.95, USL 74.05)
# 25 subgroups of size 5 = 125 observations
np.random.seed(42)
true_mu = 74.001
true_sigma = 0.009
data = np.random.normal(loc=true_mu, scale=true_sigma, size=125)
subgroup_ids = np.repeat(np.arange(1, 26), 5)

out = root / 'outputs'

# 1. Create MPX
wb = MPXWorkbook()
ws = wb.add_worksheet("Piston Rings")
ws.add_column("Diameter", list(data))
ws.add_column("Subgroup", list(subgroup_ids))
demo_mpx_path = out / "StatCraft-capability-analysis-normal-demo.mpx"
wb.save(str(demo_mpx_path))
print(f"Created {demo_mpx_path}")

# 2. Run Capability Analysis
settings = {
    'data_mode': 'single_column',
    'column_name': 'Diameter',
    'column_data': list(data),
    'subgroup_type': 'size',
    'subgroup_size': 5,
    'lsl': 73.95,
    'usl': 74.05,
    'target': 74.00,
    'k_sigma': 6.0,
    'alpha': 0.05,
    'within_method': 'pooled_sd',
    'unbias_within': True,
    'unbias_overall': False,
    'perform_ppm': True,
    'display_cstat': True,
    'display_zbench': True,
    'ci_type': 'two_sided'
}

res = run_normal_capability(settings)

# 3. Report text
report_txt = format_normal_capability_report(res)
rep_path = out / "StatCraft-capability-analysis-normal-report.txt"
rep_path.write_text(report_txt, encoding='utf-8')
print(f"Created {rep_path}")

# 4. Capability Plot screenshot
chart_widget = CapabilityPlotWidget(res)
chart_widget.resize(800, 600)
chart_pix = chart_widget.grab()
plot_path = out / "StatCraft-capability-analysis-normal-plot-preview-58.png"
chart_pix.save(str(plot_path), "PNG")
print(f"Created {plot_path}")

# 5. Dialog screenshot
dlg = CapabilityDialog()
dlg.populate_columns(["Diameter", "Subgroup"])
dlg.single_col_radio.setChecked(True)
dlg.single_col_combo.setCurrentText("Diameter")
dlg.subgroup_size_radio.setChecked(True)
dlg.subgroup_size_edit.setText("5")
dlg.lsl_edit.setText("73.95")
dlg.usl_edit.setText("74.05")
dlg.resize(550, 420)
dlg_pix = dlg.grab()
dlg_path = out / "StatCraft-capability-dialog-preview-58.png"
dlg_pix.save(str(dlg_path), "PNG")
print(f"Created {dlg_path}")

# 6. Docx & Pptx export
docx_path = out / "StatCraft-capability-analysis-normal-example.docx"
pptx_path = out / "StatCraft-capability-analysis-normal-example.pptx"

class MockResult:
    def __init__(self, title, text, pixmap):
        self.title = title
        self.text = text
        self.pixmap = pixmap

mock_res = MockResult("Process Capability Report for Diameter", report_txt, chart_pix)
export_analysis_to_docx([mock_res], str(docx_path))
export_analysis_to_pptx([mock_res], str(pptx_path))
print(f"Created {docx_path} and {pptx_path}")

print("All capability artifacts generated successfully.")
