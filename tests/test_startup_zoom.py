import unittest
from PySide6.QtCore import QEventLoop,QTimer,Qt
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QPushButton
from PySide6.QtTest import QTest
from statcraft.startup import start_window,dispose_startup,splash_pixmap
from statcraft.output_zoom import OutputZoomView
from statcraft.verification_fonts import load_verification_fonts


def pump(milliseconds):
    loop=QEventLoop();QTimer.singleShot(milliseconds,loop.quit);loop.exec()


class StartupZoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);load_verification_fonts(cls.app)
        cls.app.setQuitOnLastWindowClosed(False)

    def tearDown(self):
        dispose_startup(self.app)

    def test_startup_shows_splash_then_maximizes_and_loads_one_literal_path(self):
        class Window(QMainWindow):
            def load_path(self,path):self.loaded=str(path)
        state=start_window(self.app,Window,['C:/sample data/quiz1.mpx'],minimum_ms=60)
        self.assertTrue(state['splash'].isVisible());self.assertIsNone(state['window'])
        pump(150)
        self.assertTrue(state['ready']);self.assertTrue(state['window'].isMaximized())
        self.assertEqual(state['window'].loaded.replace('\\','/'),'C:/sample data/quiz1.mpx')
        self.assertFalse(state['splash'].isVisible())

    def test_dismissed_splash_still_reveals_main_window(self):
        state=start_window(self.app,QMainWindow,minimum_ms=40);state['splash'].hide();pump(100)
        self.assertTrue(state['window'].isMaximized());self.assertTrue(state['window'].isVisible())

    def test_original_splash_renders(self):
        image=splash_pixmap();self.assertEqual((image.width(),image.height()),(560,280));self.assertFalse(image.isNull())

    def make_view(self):
        root=QWidget();layout=QVBoxLayout(root);button=QPushButton('Editable graph object');layout.addWidget(button)
        view=OutputZoomView(root);view.resize(700,450);view.show();self.app.processEvents()
        self.addCleanup(view.close);self.addCleanup(view.deleteLater)
        return view,button

    def test_zoom_scales_view_and_preserves_source_size_and_font(self):
        view,button=self.make_view();size=view.content.size();font=button.font()
        view.set_zoom(200);self.app.processEvents()
        self.assertEqual(view.transform().m11(),2);self.assertEqual(view.content.size(),size)
        self.assertEqual(button.font(),font);self.assertGreater(view.horizontalScrollBar().maximum(),0)
        view.set_zoom(100);self.assertEqual(view.transform().m11(),1)

    def test_scaled_output_clicks_reach_the_correct_widget(self):
        view,button=self.make_view();view.set_zoom(150);self.app.processEvents();clicked=[]
        button.clicked.connect(lambda:clicked.append(True))
        scene=view.proxy.mapToScene(button.mapTo(view.content,button.rect().center()))
        position=view.mapFromScene(scene)
        view.ensureVisible(scene.x()-10,scene.y()-10,20,20)
        position=view.mapFromScene(scene)
        QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,position)
        self.assertEqual(clicked,[True])

    def test_fit_and_explicit_zoom_limits(self):
        view,_=self.make_view();view.set_zoom(900);self.assertEqual(view.percent,500)
        view.set_zoom(0);self.assertEqual(view.percent,10)
        view.fit_window();self.assertTrue(view.fit_mode);self.assertGreater(view.percent,0)
        view.set_zoom(100);self.assertFalse(view.fit_mode)
