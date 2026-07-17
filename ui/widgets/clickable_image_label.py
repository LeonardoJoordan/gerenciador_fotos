from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel


class ClickableImageLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
