import json
import unittest
import sys
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path

root = Path(__file__).resolve().parent
deps = root.parent / 'statcraft-build-deps'
if str(deps) not in sys.path:
    sys.path.insert(0, str(deps))
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
suite = unittest.defaultTestLoader.discover(str(root / 'tests'))
result = unittest.TextTestRunner(verbosity=1).run(suite)
(root.parent / 'preview-v2-test-result.json').write_text(json.dumps({
    'unittest_passed': result.testsRun - len(result.errors) - len(result.failures) - len(result.skipped),
    'skipped': len(result.skipped), 'skip_reasons': [reason for _, reason in result.skipped],
    'tests_run': result.testsRun, 'errors': len(result.errors),
    'failed': len(result.failures), 'native_full_parity': False,
}, indent=2), encoding='utf-8')
# Dispose Qt before Python module globals: test classes retain app/dialog
# wrappers, which otherwise tear down in an unstable order on Windows.
if 'PySide6.QtWidgets' in sys.modules:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    app=QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        app.processEvents()
        import shiboken6
        shiboken6.delete(app)
raise SystemExit(0 if result.wasSuccessful() else 1)
