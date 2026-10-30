"""Generate demo MPX project and screenshot artifacts for Nonnormal Capability Analysis."""

import os
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage

from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.capability_nonnormal_chart import NonnormalCapabilityPlotWidget
from statcraft.verification_fonts import load_verification_fonts


def make_artifacts():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    load_verification_fonts(app)

    np.random.seed(123)
    # 100 positive values from Weibull distribution (shape=1.75, scale=15.0)
    weibull_data = (np.random.weibull(1.75, 100) * 15.0 + 1.0).round(3).tolist()

    p = Presenter()
    p.worksheet = Worksheet("NonnormalLifespan", [
        Column("Lifespan", "number", weibull_data),
    ])

    # 1. Nonnormal Capability with Weibull distribution
    settings_weibull = {
        "variable_index": 0,
        "column_name": "Lifespan",
        "column_index": 0,
        "dist_or_transform": "weibull",
        "lsl": 2.5,
        "usl": 35.0,
        "target": 15.0,
        "naming_convention": "aiag_vda",
        "tolerance_k": 6.0,
    }
    entry_weibull = p.capability_nonnormal(settings=settings_weibull)

    # Render Nonnormal Capability Plot to PNG
    plot_widget = NonnormalCapabilityPlotWidget(entry_weibull)
    plot_widget.resize(950, 650)
    img = QImage(QSize(950, 650), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    plot_widget.render(img)
    png_path = "outputs/StatCraft-capability-nonnormal.png"
    img.save(png_path)
    print(f"Saved {png_path}")

    # 2. Save MPX project
    mpx_path = "outputs/StatCraft-capability-nonnormal-demo.mpx"
    p.save(mpx_path)
    print(f"Saved {mpx_path}")


if __name__ == '__main__':
    make_artifacts()
