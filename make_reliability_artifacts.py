"""Generate demo MPX project and screenshot artifacts for Reliability Distribution Analysis."""

import os
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QImage

from statcraft.model import Column, Worksheet
from statcraft.app import Presenter
from statcraft.reliability_chart import ReliabilityPlotWidget
from statcraft.verification_fonts import load_verification_fonts


def make_artifacts():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    load_verification_fonts(app)

    np.random.seed(101)
    # 60 failure/censored hours: Weibull shape=1.8, scale=200.0
    times = (np.random.weibull(1.8, 60) * 200.0 + 10.0).round(2).tolist()
    # Censored indicator: 1=Failed, 0=Censored (approx 25% censored)
    status = [0 if (i % 4 == 0) else 1 for i in range(60)]

    p = Presenter()
    p.worksheet = Worksheet("TurbineBlades", [
        Column("Hours", "number", times),
        Column("Status", "number", status),
    ])

    settings = {
        "variable_index": 0,
        "column_name": "Hours",
        "column_index": 0,
        "censor_index": 1,
        "censor_value": 0.0,
        "dist_name": "weibull",
        "confidence_level": 0.95,
    }
    entry = p.reliability_distribution(settings=settings)

    # Render Reliability Survival Plot to PNG
    plot_widget = ReliabilityPlotWidget(entry)
    plot_widget.resize(950, 650)
    img = QImage(QSize(950, 650), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.white)
    plot_widget.render(img)
    png_path = "outputs/StatCraft-reliability-distribution.png"
    img.save(png_path)
    print(f"Saved {png_path}")

    # Save MPX project
    mpx_path = "outputs/StatCraft-reliability-distribution-demo.mpx"
    p.save(mpx_path)
    print(f"Saved {mpx_path}")


if __name__ == '__main__':
    make_artifacts()
