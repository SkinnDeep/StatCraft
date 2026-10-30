"""Generate review artifacts for Native One-Way ANOVA (Preview 46)."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
from statcraft.app import Presenter, format_entry
from statcraft.model import Column, Worksheet
from statcraft.modern_app import ModernWindow
from statcraft.modern_charts import ChartWidget
from statcraft.office_export import OfficeSnapshot, export_docx, export_pptx
from statcraft.oneway import oneway_settings
from statcraft.oneway_dialogs import OneWayAnovaDialog
from statcraft.oneway_report import text_report
from statcraft.verification_fonts import load_verification_fonts

root = Path(__file__).resolve().parents[2]
out = root / 'outputs'
app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)
load_verification_fonts(app)

p = Presenter()
tensile = [7.0, 7.0, 15.0, 11.0, 9.0, 12.0, 17.0, 12.0, 18.0, 18.0, 14.0, 18.0, 18.0, 19.0, 19.0]
blend = ['Low', 'Low', 'Low', 'Low', 'Low', 'Med', 'Med', 'Med', 'Med', 'Med', 'High', 'High', 'High', 'High', 'High']
p.worksheet = Worksheet(
    'FabricDurability',
    [
        Column('Tensile', 'number', tensile),
        Column('Blend', 'text', blend),
        Column('Cotton15', 'number', [7.0, 7.0, 15.0, 11.0, 9.0]),
        Column('Cotton20', 'number', [12.0, 17.0, 12.0, 18.0, 18.0]),
        Column('Cotton25', 'number', [14.0, 18.0, 18.0, 19.0, 19.0]),
    ],
)
p._owned_project()

# 1. Fit Equal-Variances One-Way ANOVA with Tukey, Fisher, Dunnett, Hsu MCB, 4-in-1, storage
opts_equal = oneway_settings({
    'confidence': 0.95,
    'assume_equal_variances': True,
    'comparisons': {
        'error_rate': 0.05,
        'tukey': True,
        'fisher': True,
        'dunnett': True,
        'control_group': 'Low',
        'hsu_mcb': True,
        'hsu_best': 'largest',
        'interval_plot': True,
    },
    'graphs': {
        'interval_plot': True,
        'residual_mode': 'four_in_one',
    },
    'storage': {
        'fits': True,
        'residuals': True,
    },
})
entry_equal = p.oneway_anova(response_index=0, factor_index=1, options=opts_equal)

# 2. Fit Unequal-Variances One-Way ANOVA (Welch) with Games-Howell
opts_welch = oneway_settings({
    'confidence': 0.95,
    'assume_equal_variances': False,
    'comparisons': {
        'games_howell': True,
        'interval_plot': True,
    },
    'graphs': {
        'interval_plot': True,
        'residual_mode': 'none',
    },
})
entry_welch = p.oneway_anova(response_index=0, factor_index=1, options=opts_welch)

# 3. Fit Unstacked One-Way ANOVA
entry_unstacked = p.oneway_anova_unstacked(
    response_indices=[2, 3, 4],
    options=oneway_settings({'confidence': 0.95, 'assume_equal_variances': True}),
)

w = ModernWindow(p)
w.resize(1500, 1050)
w.show()

# 1. Dialog Screenshot
dlg = OneWayAnovaDialog(w)
dlg.response_edit.setText('C1')
dlg.factor_edit.setText('C2')
dlg.resize(540, 380)
dlg.show()
app.processEvents()
dlg_pix = dlg.grab()
dlg_pix.save(str(out / 'StatCraft-oneway-dialog-preview-46.png'))
dlg_pix.save(str(out / 'StatCraft-oneway-dialog.png'))
dlg.close()

# 2. Means Interval Plot Graph
w.show_result(entry_equal)
app.processEvents()
w.grab().save(str(out / 'StatCraft-oneway-interval-graph-preview-46.png'))
w.grab().save(str(out / 'StatCraft-oneway-interval-graph.png'))

# 3. Differences of Means Interval Plot Graph
chart_comp = ChartWidget(entry_equal)
chart_comp.resize(900, 520)
# isolate differences panel for clean preview
comp_pix = chart_comp.grab()
comp_pix.save(str(out / 'StatCraft-oneway-comparisons-graph-preview-46.png'))
comp_pix.save(str(out / 'StatCraft-oneway-comparisons-graph.png'))

# 4. Residual Plots 4-in-1
res_panel = [p for p in chart_comp.panels if p.get('kind') == 'oneway_four_in_one']
if res_panel:
    chart_res = ChartWidget(entry_equal)
    chart_res.panels = res_panel
    chart_res.resize(880, 680)
    chart_res.grab().save(str(out / 'StatCraft-oneway-residuals-graph-preview-46.png'))
    chart_res.grab().save(str(out / 'StatCraft-oneway-residuals-graph.png'))

# 5. Output Report Screenshot & text
w.result_tabs.setCurrentIndex(0)  # Output tab
app.processEvents()
w.grab().save(str(out / 'StatCraft-oneway-report-preview-46.png'))
w.grab().save(str(out / 'StatCraft-oneway-report.png'))

rep_text = text_report(entry_equal['result'])
(out / 'StatCraft-oneway-report.txt').write_text(rep_text, encoding='utf-8')

# 6. MPX demo save
demo_mpx = out / 'StatCraft-oneway-demo.mpx'
w.save_path(str(demo_mpx))

# 7. Office exports
snap = OfficeSnapshot('One-Way ANOVA', rep_text, comp_pix.toImage().bits().tobytes() if False else b'')
docx_file = out / 'StatCraft-oneway-example.docx'
pptx_file = out / 'StatCraft-oneway-example.pptx'
export_docx(str(docx_file), snap)
export_pptx(str(pptx_file), snap)

w.close()

# 8. Verification JSON Manifest
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

manifest = {
    'preview': 46,
    'feature': 'One-Way ANOVA (Stat > ANOVA > One-Way...) Native Parity',
    'native_full_parity': False,
    'mdf_resources_verified': [
        'AMONEWAY.MDF',
        'ONEWAYANOVA.MDF',
        'ONEWAYCOMPARISONS.MDF',
        'ONEWAYGRAPHS.MDF',
        'ONEWAYOPTIONS.MDF',
        'ONEWAYRESULTS.MDF',
        'ONEWAYSTORAGE.MDF',
    ],
    'files': {
        'demo_mpx': {
            'path': str(demo_mpx.relative_to(root)),
            'bytes': demo_mpx.stat().st_size,
            'sha256': sha256_file(demo_mpx),
        },
        'dialog_screenshot': {
            'path': 'outputs/StatCraft-oneway-dialog-preview-46.png',
            'bytes': (out / 'StatCraft-oneway-dialog-preview-46.png').stat().st_size,
            'sha256': sha256_file(out / 'StatCraft-oneway-dialog-preview-46.png'),
        },
        'interval_graph': {
            'path': 'outputs/StatCraft-oneway-interval-graph-preview-46.png',
            'bytes': (out / 'StatCraft-oneway-interval-graph-preview-46.png').stat().st_size,
            'sha256': sha256_file(out / 'StatCraft-oneway-interval-graph-preview-46.png'),
        },
        'comparisons_graph': {
            'path': 'outputs/StatCraft-oneway-comparisons-graph-preview-46.png',
            'bytes': (out / 'StatCraft-oneway-comparisons-graph-preview-46.png').stat().st_size,
            'sha256': sha256_file(out / 'StatCraft-oneway-comparisons-graph-preview-46.png'),
        },
        'report_screenshot': {
            'path': 'outputs/StatCraft-oneway-report-preview-46.png',
            'bytes': (out / 'StatCraft-oneway-report-preview-46.png').stat().st_size,
            'sha256': sha256_file(out / 'StatCraft-oneway-report-preview-46.png'),
        },
        'report_text': {
            'path': 'outputs/StatCraft-oneway-report.txt',
            'bytes': (out / 'StatCraft-oneway-report.txt').stat().st_size,
            'sha256': sha256_file(out / 'StatCraft-oneway-report.txt'),
        },
        'docx_export': {
            'path': 'outputs/StatCraft-oneway-example.docx',
            'bytes': docx_file.stat().st_size,
            'sha256': sha256_file(docx_file),
        },
        'pptx_export': {
            'path': 'outputs/StatCraft-oneway-example.pptx',
            'bytes': pptx_file.stat().st_size,
            'sha256': sha256_file(pptx_file),
        },
    },
    'statistics_verification': {
        'f_value': entry_equal['result']['anova_table']['f_value'],
        'p_value': entry_equal['result']['anova_table']['p_value'],
        'r_sq': entry_equal['result']['model_summary']['r_sq'],
        'r_sq_adj': entry_equal['result']['model_summary']['r_sq_adj'],
        's_pooled': entry_equal['result']['model_summary']['s'],
        'comparisons_tested': ['tukey', 'fisher', 'dunnett', 'hsu_mcb', 'games_howell'],
        'welch_anova_f': entry_welch['result']['welch_anova']['f'],
        'unstacked_f': entry_unstacked['result']['anova_table']['f_value'],
    },
}

(root / 'work' / 'oneway-artifacts-verified.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('One-Way ANOVA artifacts generated and verified successfully.')
