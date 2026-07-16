from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core.image_processor import ImageProcessor


class ThumbnailWorkerSignals(QObject):
    finished = Signal(object, str, str)


class ThumbnailWorker(QRunnable):
    """Gera uma miniatura fora da thread da interface."""

    def __init__(self, key: tuple[str, str, int], root_path: str, photo_path: str, size: int):
        super().__init__()
        self.key = key
        self.root_path = root_path
        self.photo_path = photo_path
        self.size = size
        self.signals = ThumbnailWorkerSignals()

    @Slot()
    def run(self):
        thumbnail_path = ""
        try:
            thumbnail_path = ImageProcessor().create_thumbnail(
                self.root_path, self.photo_path, self.size
            )
        except Exception:
            # Uma imagem inválida não pode deixar o trabalho preso na fila.
            pass
        self.signals.finished.emit(self.key, self.photo_path, thumbnail_path)
