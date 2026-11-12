"""Interactive output scaling; source widget/export coordinates stay at 100%."""
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget


class OutputZoomView(QGraphicsView):
    def __init__(self, widget, parent=None):
        super().__init__(parent)
        self.content=widget;self.percent=100;self.fit_mode=False
        scene=QGraphicsScene(self);self.setScene(scene);self.proxy=scene.addWidget(widget)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setStyleSheet('QGraphicsView { border: none; background: #e6e6e6; }')
        self._resizing=False
        self.resize_content()

    def resize_content(self):
        if self._resizing:return
        self._resizing=True
        hint=self.content.minimumSizeHint()
        width=max(320,self.width()-2,self.content.minimumWidth(),hint.width())
        height=max(180,self.height()-2,self.content.minimumHeight(),hint.height())
        self.proxy.resize(width,height)
        self.scene().setSceneRect(self.proxy.boundingRect())
        if self.fit_mode:self.fit_window()
        self._resizing=False

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'proxy'):self.resize_content()

    def set_zoom(self,percent):
        self.fit_mode=False;self.percent=max(10,min(500,int(percent)))
        self.resetTransform();self.scale(self.percent/100,self.percent/100)

    def fit_window(self):
        self.fit_mode=True
        self.fitInView(self.proxy.boundingRect(),Qt.AspectRatioMode.KeepAspectRatio)
        self.percent=max(10,min(500,round(self.transform().m11()*100)))

    def wheelEvent(self, event):
        if hasattr(self, 'content') and self.content is not None:
            target_chart = None
            if hasattr(self.content, '_has_3d_panel') and self.content._has_3d_panel():
                target_chart = self.content
            elif hasattr(self.content, '_interactive_3d') and self.content._interactive_3d:
                target_chart = self.content
            else:
                for child in self.content.findChildren(QWidget):
                    if (hasattr(child, '_has_3d_panel') and child._has_3d_panel()) or (hasattr(child, '_interactive_3d') and child._interactive_3d):
                        target_chart = child
                        break
            if target_chart is None and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                scene_pt = self.mapToScene(event.position().toPoint())
                for child in ([self.content] + list(self.content.findChildren(QWidget))):
                    if hasattr(child, '_has_2d_zoomable_panel') and child._has_2d_zoomable_panel():
                        local_pt = QPointF(child.mapFrom(self.content, scene_pt.toPoint()))
                        if hasattr(child, '_zoom2d_panel_at') and child._zoom2d_panel_at(local_pt) is not None:
                            steps = event.angleDelta().y() / 120.0
                            if steps and child._apply_2d_wheel_zoom(local_pt, steps):
                                event.accept()
                                return
                            break
            if target_chart is not None:
                target_chart.wheelEvent(event)
                if event.isAccepted():
                    return
        super().wheelEvent(event)

