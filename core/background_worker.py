import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class BackgroundJobSignals(QObject):
    finished = Signal(int, object)
    failed = Signal(int, object)


class BackgroundJob(QRunnable):
    """Executa uma função fora da thread da interface e devolve o resultado por sinal."""

    def __init__(self, job_id: int, callback: Callable[[], Any]):
        super().__init__()
        self.job_id = job_id
        self.callback = callback
        self.signals = BackgroundJobSignals()

    @Slot()
    def run(self):
        try:
            self.signals.finished.emit(self.job_id, self.callback())
        except Exception as exc:
            self.signals.failed.emit(
                self.job_id,
                {
                    "exception": exc,
                    "traceback": traceback.format_exc(),
                },
            )
