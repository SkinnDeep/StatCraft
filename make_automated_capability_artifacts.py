"""Generate demo MPX project and screenshot artifacts for Nonparametric and Automated Capability Analysis."""

import os
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage

from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.capability_automated_chart import NonparametricCapabilityPlotWidget
from statcraft.verification_fonts import load_verification_fonts


def make_artifacts():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    load_verification_fonts(app)

    np.random.seed(202)
    # 80 skewed positive values
    skewed = (np.random.weibull(1.7, 80) * 18.0 + 3.0).round(2).tolist()

    p = Presenter()
    p.worksheet = Worksheet("NonparamAuto", [
        Column("BreakingLoad", "number", skewed),
    ])

    # 1. Nonparametric Capability
    settings_nonp = {
        "variable_index": 0,
        "column_name": "BreakingLoad",
        "column_index": 0,
        "lsl": 4.0,
        "usl": 45.0,
        "target": 20.0,
        "naming_convention": "aiag_vda",
        "tolerance_k": 6.0,
    }
    entry_nonp = p.capability_nonparametric(settings=settings_nonp)

    plot_widget = NonparametricCapabilityPlotWidget(entry_nonp)
    plot_widget.resize(950, 650)
    img = QImage(QSize(950, 650), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    plot_widget.render(img)
    png_path = "outputs/StatCraft-capability-nonparametric.png"
    img.save(png_path)
    print(f"Saved {png_path}")

    # 2. Automated Capability Analysis (Tournament)
    settings_auto = {
        "variable_index": 0,
        "column_name": "BreakingLoad",
        "column_index": 0,
        "lsl": 4.0,
        "usl": 45.0,
        "target": 20.0,
        "naming_convention": "classical",
        "tolerance_k": 6.0,
    }
    entry_auto = p.capability_automated(settings=settings_auto)

    plot_auto = NonparametricCapabilityPlotWidget(entry_auto)
    plot_auto.resize(950, 650)
    img_auto = QImage(QSize(950, 650), QImage.Format.Format_ARGB32_Premultiplied)
    img_auto.fill(Qt.GlobalColor.white)
    plot_auto.render(img_auto)
    png_auto_path = "outputs/StatCraft-capability-automated.png"
    img_auto.save(png_auto_path)
    print(f"Saved {png_auto_path}")

    # Save MPX project
    mpx_path = "outputs/StatCraft-capability-automated-demo.mpx"
    p.save(mpx_path)
    print(f"Saved {mpx_path}")


if __name__ == '__main__':
    make_artifacts()
