"""Generate demonstration artifacts for Preview 58: Capability Analysis (Normal Distribution)."""
import os, sys, json
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'work/statcraft'))
sys.path.insert(0, str(root / 'work/statcraft-build-deps'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize, QBuffer, QIODevice
from PySide6.QtGui import QImage
from statcraft.model import Column, Worksheet
from statcraft.app import Presenter, format_entry
from statcraft.capability_dialogs import CapabilityDialog, CapabilityOptionsDialog, CapabilityEstimateDialog
from statcraft.capability_chart import CapabilityPlotWidget
from statcraft.office_export import OfficeSnapshot, export_docx, export_pptx

app = QApplication.instance() or QApplication(sys.argv)

np.random.seed(42)
true_mu = 74.001
true_sigma = 0.009
data = np.random.normal(loc=true_mu, scale=true_sigma, size=125).tolist()
subgroup_ids = np.repeat(np.arange(1, 26), 5).tolist()

out_dir = root / 'outputs'
out_dir.mkdir(parents=True, exist_ok=True)

p = Presenter()
p.worksheet = Worksheet("PistonRings", [
    Column("Diameter", "number", data),
    Column("Subgroup", "number", subgroup_ids),
])

settings = {
    "single_column": True,
    "column_name": "Diameter",
    "subgroup_spec": "5",
    "lsl": 73.95,
    "usl": 74.05,
    "options": {
        "target": 74.00,
        "tolerance_k": 6.0,
        "confidence_level": 95.0,
        "ci_type": "two_sided",
        "display_cstat": True,
        "display_zbench": True,
        "perform_ppm": True,
        "within_method": "pooled_sd",
        "unbias_within": True,
        "unbias_overall": False,
        "include_ccpk": True
    }
}

entry = p.normal_capability(settings=settings)
assert entry is not None

# Save MPX
demo_mpx_path = out_dir / "StatCraft-capability-analysis-normal-demo.mpx"
p.save(demo_mpx_path)
print(f"Created {demo_mpx_path}")

# Format report
report_text = format_entry(entry)
rep_path = out_dir / "StatCraft-capability-analysis-normal-report.txt"
rep_path.write_text(report_text, encoding="utf-8")
print(f"Created {rep_path}")

# Render Capability Plot
chart_widget = CapabilityPlotWidget(entry)
chart_widget.resize(800, 600)
chart_img = QImage(QSize(800, 600), QImage.Format.Format_ARGB32_Premultiplied)
chart_img.fill(Qt.GlobalColor.white)
chart_widget.render(chart_img)

plot_path = out_dir / "StatCraft-capability-analysis-normal-plot-preview-58.png"
chart_img.save(str(plot_path), "PNG")
chart_img.save(str(out_dir / "StatCraft-capability-analysis-normal-plot.png"), "PNG")
print(f"Created {plot_path}")

# Render Dialog Screenshot
dlg = CapabilityDialog(p.worksheet)
dlg.rb_single_col.setChecked(True)
dlg.edit_single_col.setText("Diameter")
dlg.edit_sub_size.setText("5")
dlg.edit_lsl.setText("73.95")
dlg.edit_usl.setText("74.05")
dlg.resize(560, 420)
dlg_img = QImage(QSize(560, 420), QImage.Format.Format_ARGB32_Premultiplied)
dlg_img.fill(Qt.GlobalColor.white)
dlg.render(dlg_img)

dlg_path = out_dir / "StatCraft-capability-dialog-preview-58.png"
dlg_img.save(str(dlg_path), "PNG")
dlg_img.save(str(out_dir / "StatCraft-capability-dialog.png"), "PNG")
print(f"Created {dlg_path}")

# Export Office documents
buf = QBuffer()
buf.open(QIODevice.OpenModeFlag.WriteOnly)
chart_img.save(buf, "PNG")
png_bytes = bytes(buf.data())

snapshot = OfficeSnapshot(entry["title"], report_text, png_bytes)
docx_path = out_dir / "StatCraft-capability-analysis-normal-example.docx"
pptx_path = out_dir / "StatCraft-capability-analysis-normal-example.pptx"
export_docx(str(docx_path), snapshot)
export_pptx(str(pptx_path), snapshot)
print(f"Created {docx_path} and {pptx_path}")

print("Preview 58 demo artifacts successfully generated!")
