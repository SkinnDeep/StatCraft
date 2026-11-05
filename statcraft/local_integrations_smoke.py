"""Exercise local integrations in a packaged build without modifying user settings."""
import json
from pathlib import Path
from statistics import median
from time import monotonic, perf_counter, sleep
import traceback


def verify(report_path, fixture_dir):
    from PySide6.QtCore import QSettings, QThreadPool, QTimer, Qt
    from PySide6.QtWidgets import QApplication
    from .app import Presenter
    from .graph_frame import GraphFrame
    from .jmp_reader import load_jmp
    from .model import Column, Worksheet
    from .modern_app import ModernWindow
    from .r_bridge import get_r_help_text, reset_r_session
    from .recipes import columns, run

    path = Path(report_path).resolve()
    fixtures = Path(fixture_dir).resolve()
    app = QApplication([])
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                      str(path.parent / "verification-settings"))
    report = {}
    window = None

    def drain(condition, timeout=12):
        deadline = monotonic() + timeout
        while not condition():
            if monotonic() > deadline:
                raise RuntimeError("Timed out waiting for the desktop workflow.")
            app.processEvents()
            sleep(.01)
        app.processEvents()

    def submit(code):
        bench.repl_input.setText(code)
        bench._run_repl()
        drain(lambda: bench._cancel is None)
        assert bench.con_status_lbl.text().startswith("Ready"), bench.console_output.toPlainText()

    try:
        presenter = Presenter()
        presenter.worksheet = Worksheet("R source", [Column("X", values=[1, 2, 3, 4])])
        window = ModernWindow(presenter)
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        window.resize(1320, 860)
        window.show()
        window.set_ui_mode("r")
        bench = window.r_workbench
        submit("marker <- sum(df[['X']]); cat(marker)")
        assert "\n10" in bench.console_output.toPlainText()
        durations = []
        for _ in range(5):
            started = perf_counter()
            submit("cat(42)")
            durations.append((perf_counter() - started) * 1000)
            assert bench.console_output.toPlainText().endswith("\n42")
        report["r_warm_ui_median_ms"] = round(median(durations))
        responsive = []
        bench._execute_r("Sys.sleep(10)")
        QTimer.singleShot(80, lambda: responsive.append(True))
        drain(lambda: bool(responsive), timeout=2)
        assert bench._cancel is not None
        bench.stop_execution()
        drain(lambda: bench._cancel is None, timeout=3)
        assert bench.con_status_lbl.text() == "Stopped"
        submit('cat("Fresh workspace")')
        submit('plot(1:4); hist(1:4)')
        assert len(bench.plot_gallery.plot_history) == 2
        assert all(Path(p).stat().st_size > 1000 for p in bench.plot_gallery.plot_history)
        bench.editor.setPlainText("plot(1:4)\nhist(1:4)\n")
        window.grab().save(str(path.with_suffix(".r.png")))
        submit('sample <- data.frame(Amount=c(0, NA, 2), Text=c("NA", "", NA)); '
               'statcraft_export(sample, "R output")')
        assert presenter.worksheet.name == "R output"
        assert presenter.worksheet.columns[0].values == [0.0, None, 2.0]
        assert presenter.worksheet.columns[1].values == ["NA", "", None]
        submit("View(sample)")
        assert "Fitting Linear Models" in get_r_help_text("lm")
        report["r_workbench"] = ["responsive during execution", "stop and restart",
                                  "two plots", "typed worksheet export", "object viewer", "help"]
        results = {file.name: load_jmp(file) for file in fixtures.glob("*.jmp")}
        assert len(results) >= 17
        assert results["byteintegers_notcompressed.jmp"].columns[1].values[:3] == [32767, None, 0]
        assert results["date.jmp"].columns[0].kind == "date"
        assert results["compressed.jmp"].row_count == 10000
        assert results["rowstate.jmp"].columns[2].values == ["•", "▲", "ꙮ"]
        window.set_ui_mode("jmp")
        window.load_path(str(fixtures / "example1.jmp"))
        assert presenter.worksheet.columns[0].values[:3] == [1, 2, 3]
        for entry in (presenter.jmp_distribution([0, 1]), presenter.fit_y_by_x(1, 0),
                      presenter.control_chart_builder([0]), presenter.process_screening([0, 1])):
            window.show_result(entry)
            app.processEvents()
            frame = window._active_graph_frame
            assert isinstance(frame, GraphFrame) and frame.entry is entry, entry["title"]
            assert not frame.capture().isNull(), entry["title"]
        report["jmp_binary_fixtures"] = len(results)
        report["jmp_analysis"] = ["Distribution", "Fit Y by X", "Control Chart Builder", "Process Screening"]
        window.set_ui_mode("minitab")
        presenter.worksheet = Worksheet("Lag sample", [
            Column("First", values=[0, 0, 0, 1, 0, 0, 0, 0, 0, 0]),
            Column("Second", values=[0, 0, 0, 0, 0, 1, 0, 0, 0, 0]),
        ])
        window.refresh()
        entry = presenter.execute_session_command("CCF 4 C1 C2")
        recipe = entry["recipe"]
        assert columns(recipe) == [0, 1]
        peak = max(entry["result"]["lags"], key=lambda row: row["correlation"])
        assert peak["lag"] == 2
        window.show_result(run(presenter, recipe))
        app.processEvents()
        assert isinstance(window._active_graph_frame, GraphFrame)
        result = presenter.cross_correlation(0, 1, 4, title="Lead/lag check", store_ccf=True)
        assert result["title"] == "Lead/lag check"
        assert presenter.worksheet.columns[-1].name == "CCF"
        assert len(presenter.worksheet.columns[-1].values) == 9
        presenter.undo()
        assert len(presenter.worksheet.columns) == 2
        river = fixtures.parent / "ccf-river-sediment.mwx"
        if river.is_file():
            reference = Presenter()
            reference.load(river)
            rows = reference.cross_correlation(0, 1)["result"]["lags"]
            native_peak = max(rows, key=lambda row: row["correlation"])
            assert len(rows) == 27 and native_peak["lag"] == -2
            assert abs(native_peak["correlation"] - .919857) < .0000005
            report["published_example_peak"] = native_peak
        report["cross_correlation_peak"] = peak
        report["passed"] = True
    except Exception:
        report["traceback"] = traceback.format_exc()
    finally:
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if window:
            window.presenter.dirty = window.presenter._results_dirty = False
            window.close()
        reset_r_session()
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()
    return 0 if report.get("passed") else 1
