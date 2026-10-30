"""Generate demo MPX project and screenshot artifacts for Shewhart Extended Limits & Warning Bands."""

import os
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage

from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.modern_charts import ChartWidget
from statcraft.imr_chart import IMRChartWidget
from statcraft.verification_fonts import load_verification_fonts


def make_artifacts():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    load_verification_fonts(app)

    np.random.seed(99)
    # Generate 25 subgroups of size 5
    n_sub = 25
    sg_sz = 5
    total = n_sub * sg_sz
    vals = np.random.normal(100.0, 4.0, total).tolist()
    # Introduce mean excursion around subgroup 18
    for i in range(17 * sg_sz, 18 * sg_sz):
        vals[i] += 8.5

    subgroups = []
    for g in range(1, n_sub + 1):
        subgroups.extend([g] * sg_sz)

    p = Presenter()
    p.worksheet = Worksheet("ExtendedLimits", [
        Column("Diameter", "number", vals),
        Column("Subgroup", "number", subgroups),
    ])

    # 1. Fit Xbar-R chart with multi-k and warning limits
    opts_xr = {
        'chart_type': 'xbar_r',
        'warning_limits': True,
        'warning_k': 2.0,
        'display_zones': True,
        'k_sigma': '1 2 3',
    }
    entry_xr = p.subgroup_control_chart(
        chart_type='xbar_r',
        stacked=True,
        response_index=0,
        factor_index=1,
        options=opts_xr
    )

    # Render Xbar-R chart to PNG
    chart_xr = ChartWidget(entry_xr)
    chart_xr.resize(1000, 700)
    img_xr = QImage(QSize(1000, 700), QImage.Format.Format_ARGB32_Premultiplied)
    img_xr.fill(Qt.GlobalColor.white)
    chart_xr.render(img_xr)
    xr_png_path = "outputs/StatCraft-xbar-r-extended-limits.png"
    img_xr.save(xr_png_path)
    print(f"Saved {xr_png_path}")

    # 2. Fit I-MR chart with warning limits
    settings_imr = {
        'variables': [0],
        'options': {
            'warning_limits': True,
            'warning_k': 2.0,
            'display_zones': True,
            'k_sigma': 3.0,
        }
    }
    entry_imr = p.imr_chart(settings=settings_imr)

    # Render I-MR chart to PNG
    chart_imr = IMRChartWidget(entry_imr)
    chart_imr.resize(1000, 700)
    img_imr = QImage(QSize(1000, 700), QImage.Format.Format_ARGB32_Premultiplied)
    img_imr.fill(Qt.GlobalColor.white)
    chart_imr.render(img_imr)
    imr_png_path = "outputs/StatCraft-imr-extended-limits.png"
    img_imr.save(imr_png_path)
    print(f"Saved {imr_png_path}")

    # 3. Save MPX project
    mpx_path = "outputs/StatCraft-shewhart-extended-limits-demo.mpx"
    p.save(mpx_path)
    print(f"Saved {mpx_path}")


if __name__ == '__main__':
    make_artifacts()
