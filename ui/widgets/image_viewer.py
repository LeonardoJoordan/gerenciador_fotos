import os

from PySide6.QtCore import QEvent, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QImageReader, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

from core.image_loader_worker import ImageLoadWorker


class ImageGraphicsView(QGraphicsView):
    zoomRequested = Signal(float)
    viewportResized = Signal()

    def wheelEvent(self, event):
        if event.angleDelta().y():
            self.zoomRequested.emit(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.viewportResized.emit()


class ImageViewerDialog(QDialog):
    """Visualizador sob demanda para as fotos de um único cadastro."""

    def __init__(
        self,
        photo_paths: list[str],
        initial_index: int,
        thumbnail_paths: dict[str, str],
        worker_pool,
        parent=None,
    ):
        super().__init__(parent)
        self.photo_paths = list(photo_paths)
        self.current_index = max(0, min(initial_index, len(self.photo_paths) - 1))
        self.thumbnail_paths = dict(thumbnail_paths)
        self.worker_pool = worker_pool
        self._request_sequence = 0
        self._active_request = 0
        self._workers: dict[int, ImageLoadWorker] = {}
        self._fit_mode = True
        self._loaded_full_resolution = False
        self._full_resolution_loading = False
        self._full_resolution_request_id = 0
        self._full_load_behavior = "actual"
        self._zoom_multiplier = 1.0
        self._initial_load_pending = bool(self.photo_paths)
        self._expanded = False
        self._host_window = self._find_host_window()

        self.setWindowTitle("Visualizar imagem")
        self.setModal(True)
        self.setObjectName("image_viewer_dialog")
        self._build_ui()
        self._apply_photo_geometry()
        self._show_current_photo(request_image=False)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self.previous_button = self._tool_button(
            "←", "Foto anterior", self.show_previous
        )
        self.next_button = self._tool_button(
            "→", "Próxima foto", self.show_next
        )
        self.counter_label = QLabel(self)
        self.counter_label.setObjectName("image_viewer_counter")
        self.status_label = QLabel(self)
        self.status_label.setObjectName("image_viewer_status")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumWidth(0)
        self.status_label.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred
        )
        toolbar.addWidget(self.previous_button)
        toolbar.addWidget(self.next_button)
        toolbar.addWidget(self.counter_label)
        toolbar.addWidget(self.status_label, 1)

        self.expand_button = self._tool_button(
            "□", "Expandir visualização", self.toggle_expanded
        )
        self.close_button = self._tool_button(
            "×", "Fechar", self.accept
        )
        toolbar.addWidget(self.expand_button)
        toolbar.addWidget(self.close_button)
        layout.addLayout(toolbar)

        image_controls = QHBoxLayout()
        image_controls.addStretch()
        self.zoom_out_button = self._text_tool_button(
            "−", "Reduzir", lambda: self._zoom(1 / 1.25)
        )
        self.zoom_in_button = self._text_tool_button(
            "+", "Ampliar", lambda: self._zoom(1.25)
        )
        self.fit_button = QPushButton("Ajustar", self)
        self.fit_button.setToolTip("Ajustar a imagem à janela")
        self.fit_button.clicked.connect(self.fit_to_window)
        self.actual_size_button = QPushButton("1:1", self)
        self.actual_size_button.setToolTip("Exibir em tamanho real")
        self.actual_size_button.clicked.connect(self.show_actual_size)
        image_controls.addWidget(self.zoom_out_button)
        image_controls.addWidget(self.zoom_in_button)
        image_controls.addWidget(self.fit_button)
        image_controls.addWidget(self.actual_size_button)
        image_controls.addStretch()
        layout.addLayout(image_controls)

        self.scene = QGraphicsScene(self)
        self.pixmap_item = QGraphicsPixmapItem()
        self.scene.addItem(self.pixmap_item)
        self.view = ImageGraphicsView(self.scene, self)
        self.view.setObjectName("image_viewer_view")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setBackgroundBrush(Qt.black)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.view.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.view.zoomRequested.connect(self._zoom)
        self.view.viewportResized.connect(self._refit_after_resize)
        layout.addWidget(self.view, 1)

    def _tool_button(self, text: str, tooltip: str, callback) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("image_viewer_tool")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(34, 32)
        button.clicked.connect(callback)
        return button

    def _text_tool_button(self, text: str, tooltip: str, callback) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("image_viewer_tool")
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFixedSize(34, 32)
        button.clicked.connect(callback)
        return button

    def _find_host_window(self):
        widget = self.parentWidget()
        while widget is not None:
            if isinstance(widget, QMainWindow):
                return widget
            widget = widget.parentWidget()

        for window in QApplication.topLevelWidgets():
            if isinstance(window, QMainWindow) and window.isVisible():
                return window

        parent = self.parentWidget()
        return parent.window() if parent is not None else None

    def _host_geometry(self) -> QRect:
        if self._host_window is not None:
            return QRect(self._host_window.frameGeometry())
        return QRect(self.screen().availableGeometry())

    def _center_on_host(self):
        frame = self.frameGeometry()
        frame.moveCenter(self._host_geometry().center())
        self.move(frame.topLeft())

    def _photo_aspect_ratio(self) -> float:
        if not self.current_path:
            return 4 / 3

        thumbnail = QPixmap(self.thumbnail_paths.get(self.current_path, ""))
        if not thumbnail.isNull() and thumbnail.height() > 0:
            return thumbnail.width() / thumbnail.height()

        reader = QImageReader(self.current_path)
        image_size = reader.size()
        if image_size.isValid() and image_size.height() > 0:
            return image_size.width() / image_size.height()
        return 4 / 3

    def _apply_photo_geometry(self):
        host_geometry = self._host_geometry()
        height = max(1, round(host_geometry.height() * 0.8))

        # Margens e barras de controle não fazem parte da área útil da foto.
        image_height = max(1, height - 106)
        width = round((image_height * self._photo_aspect_ratio()) + 24)
        maximum_width = max(1, round(host_geometry.width() * 0.95))
        width = min(max(width, min(360, maximum_width)), maximum_width)

        self.setMinimumSize(min(360, width), min(320, height))
        self.resize(width, height)
        self._center_on_host()

    def _apply_expanded_geometry(self):
        host_geometry = self._host_geometry()
        margin = min(16, host_geometry.width() // 20, host_geometry.height() // 20)
        width = max(1, host_geometry.width() - (margin * 2))
        height = max(1, host_geometry.height() - (margin * 2))
        self.resize(width, height)
        self._center_on_host()

    def toggle_expanded(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.expand_button.setText("❐")
            self.expand_button.setToolTip("Restaurar tamanho")
            self._apply_expanded_geometry()
        else:
            self.expand_button.setText("□")
            self.expand_button.setToolTip("Expandir visualização")
            self._apply_photo_geometry()

    @property
    def current_path(self) -> str:
        return self.photo_paths[self.current_index] if self.photo_paths else ""

    def _show_current_photo(self, request_image: bool = True):
        if not self.photo_paths:
            self.status_label.setText("Nenhuma imagem disponível")
            self._set_controls_enabled(False)
            return
        self._loaded_full_resolution = False
        self._full_resolution_loading = False
        self._full_resolution_request_id = 0
        self._full_load_behavior = "actual"
        self._zoom_multiplier = 1.0
        self._fit_mode = True
        self.previous_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < len(self.photo_paths) - 1)
        self.counter_label.setText(
            f"{self.current_index + 1} de {len(self.photo_paths)}"
        )
        self.setWindowTitle(os.path.basename(self.current_path))
        self._show_thumbnail()
        if request_image:
            self._request_image(
                full_resolution=True,
                full_behavior="fit",
            )
        else:
            self.status_label.setText("Carregando imagem original...")

    def _show_thumbnail(self):
        thumbnail = QPixmap(self.thumbnail_paths.get(self.current_path, ""))
        if thumbnail.isNull():
            self.pixmap_item.setPixmap(QPixmap())
            return
        self.pixmap_item.setPixmap(thumbnail)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        self.fit_to_window()

    def _request_image(
        self,
        full_resolution: bool,
        full_behavior: str = "actual",
    ):
        if full_resolution:
            self._full_load_behavior = full_behavior
            if self._full_resolution_loading:
                return
            self._full_resolution_loading = True

        self._request_sequence += 1
        request_id = self._request_sequence
        self._active_request = request_id
        if full_resolution:
            self._full_resolution_request_id = request_id
        self.status_label.setText(
            "Carregando resolução completa..."
            if full_resolution
            else "Carregando imagem..."
        )
        target_size = None
        if not full_resolution:
            viewport_size = self.view.viewport().size()
            scale = max(1.0, self.devicePixelRatioF())
            target_size = QSize(
                max(1, int(max(viewport_size.width(), self.width() - 40) * scale)),
                max(1, int(max(viewport_size.height(), self.height() - 100) * scale)),
            )
        worker = ImageLoadWorker(
            request_id,
            self.current_path,
            target_size,
            "full" if full_resolution else "fit",
        )
        worker.signals.finished.connect(self._image_loaded)
        worker.signals.failed.connect(self._image_failed)
        self._workers[request_id] = worker
        self.worker_pool.start(worker)

    def _image_loaded(
        self,
        request_id: int,
        image_path: str,
        image: QImage,
        mode: str,
    ):
        self._workers.pop(request_id, None)
        if mode == "full" and request_id == self._full_resolution_request_id:
            self._full_resolution_loading = False
            self._full_resolution_request_id = 0
        if (
            request_id != self._active_request
            or os.path.abspath(image_path) != os.path.abspath(self.current_path)
        ):
            return
        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            self._image_failed(request_id, image_path, "Imagem indisponível.")
            return
        self.pixmap_item.setPixmap(pixmap)
        self.scene.setSceneRect(self.pixmap_item.boundingRect())
        full_resolution = mode == "full"
        self._loaded_full_resolution = full_resolution
        self.status_label.setText("")
        if full_resolution:
            if self._full_load_behavior == "zoom":
                self._apply_zoom_multiplier()
            elif self._full_load_behavior == "fit":
                self.fit_to_window()
            else:
                self._apply_actual_size()
        else:
            self.fit_to_window()

    def _image_failed(
        self,
        request_id: int,
        image_path: str,
        message: str,
        mode: str = "",
    ):
        self._workers.pop(request_id, None)
        if mode == "full" and request_id == self._full_resolution_request_id:
            self._full_resolution_loading = False
            self._full_resolution_request_id = 0
        if request_id != self._active_request:
            return
        self.status_label.setText(message or "Não foi possível carregar a imagem.")

    def show_previous(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current_photo()

    def show_next(self):
        if self.current_index < len(self.photo_paths) - 1:
            self.current_index += 1
            self._show_current_photo()

    def fit_to_window(self):
        if self.pixmap_item.pixmap().isNull():
            return
        self._zoom_multiplier = 1.0
        if self._full_resolution_loading:
            self._full_load_behavior = "fit"
        self._fit_mode = True
        self.view.resetTransform()
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)

    def show_actual_size(self):
        if self.pixmap_item.pixmap().isNull():
            return
        if self._loaded_full_resolution:
            self._apply_actual_size()
        else:
            self._request_image(
                full_resolution=True,
                full_behavior="actual",
            )

    def _apply_actual_size(self):
        self._fit_mode = False
        self.view.resetTransform()
        self.view.centerOn(self.pixmap_item)

    def _apply_zoom_multiplier(self):
        self.view.resetTransform()
        self.view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self.view.scale(self._zoom_multiplier, self._zoom_multiplier)
        self._fit_mode = False

    def _zoom(self, factor: float):
        if self.pixmap_item.pixmap().isNull():
            return
        current_scale = self.view.transform().m11()
        target_scale = current_scale * factor
        if target_scale < 0.03 or target_scale > 20:
            return
        self._fit_mode = False
        self._zoom_multiplier *= factor
        self.view.scale(factor, factor)
        if not self._loaded_full_resolution and self._zoom_multiplier > 1.0:
            self._request_image(
                full_resolution=True,
                full_behavior="zoom",
            )

    def _refit_after_resize(self):
        if self._fit_mode:
            self.fit_to_window()

    def _set_controls_enabled(self, enabled: bool):
        for control in (
            self.previous_button,
            self.next_button,
            self.zoom_out_button,
            self.zoom_in_button,
            self.fit_button,
            self.actual_size_button,
        ):
            control.setEnabled(enabled)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Left:
            self.show_previous()
            return
        if event.key() == Qt.Key_Right:
            self.show_next()
            return
        if event.key() in {Qt.Key_Plus, Qt.Key_Equal}:
            self._zoom(1.25)
            return
        if event.key() == Qt.Key_Minus:
            self._zoom(1 / 1.25)
            return
        if event.key() == Qt.Key_0:
            self.fit_to_window()
            return
        if event.key() == Qt.Key_F11:
            self.toggle_expanded()
            return
        super().keyPressEvent(event)

    def showEvent(self, event: QEvent):
        super().showEvent(event)
        QTimer.singleShot(0, self._finish_initial_layout)

    def _finish_initial_layout(self):
        if self._expanded:
            self._apply_expanded_geometry()
        else:
            self._apply_photo_geometry()

        if self._initial_load_pending:
            self._initial_load_pending = False
            self._request_image(
                full_resolution=True,
                full_behavior="fit",
            )

    def closeEvent(self, event: QEvent):
        self._active_request = -1
        super().closeEvent(event)
