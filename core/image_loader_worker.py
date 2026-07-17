from PySide6.QtCore import QObject, QRunnable, QSize, Qt, Signal, Slot
from PySide6.QtGui import QImageReader


class ImageLoadSignals(QObject):
    finished = Signal(int, str, object, str)
    failed = Signal(int, str, str, str)


class ImageLoadWorker(QRunnable):
    """Decodifica uma imagem sem bloquear a thread da interface."""

    def __init__(
        self,
        request_id: int,
        image_path: str,
        target_size: QSize | None = None,
        mode: str = "fit",
    ):
        super().__init__()
        self.request_id = request_id
        self.image_path = image_path
        self.target_size = QSize(target_size) if target_size else None
        self.mode = mode
        self.signals = ImageLoadSignals()

    @Slot()
    def run(self):
        try:
            reader = QImageReader(self.image_path)
            reader.setAutoTransform(True)
            if not reader.canRead():
                raise ValueError("O arquivo não pôde ser lido como imagem.")
            if self.target_size and self.target_size.isValid():
                original_size = reader.size()
                if original_size.isValid():
                    reader.setScaledSize(
                        original_size.scaled(self.target_size, Qt.KeepAspectRatio)
                    )
            image = reader.read()
            if image.isNull():
                raise ValueError("Não foi possível decodificar a imagem.")
        except Exception as exc:
            try:
                self.signals.failed.emit(
                    self.request_id,
                    self.image_path,
                    str(exc),
                    self.mode,
                )
            except RuntimeError:
                pass
            return

        try:
            self.signals.finished.emit(
                self.request_id,
                self.image_path,
                image,
                self.mode,
            )
        except RuntimeError:
            pass
