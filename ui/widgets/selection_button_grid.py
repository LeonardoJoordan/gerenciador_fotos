from collections.abc import Callable, Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QGridLayout, QLabel, QPushButton, QWidget


class SelectionButtonGrid(QWidget):
    """Grade exclusiva: apresenta várias opções, mas mantém apenas uma marcada."""

    selectionChanged = Signal(str)

    def __init__(
        self,
        columns: int = 3,
        label_formatter: Callable[[str], str] | None = None,
        empty_text: str = "Nenhuma opção configurada",
        parent=None,
    ):
        super().__init__(parent)
        self.columns = max(1, columns)
        self.label_formatter = label_formatter or (lambda value: value)
        self.empty_text = empty_text
        self._values: list[str] = []
        self._buttons: list[QPushButton] = []
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(7)
        self.grid.setVerticalSpacing(7)

    def set_options(self, values: Iterable[str], selected: str = "") -> None:
        """Reconstrói a grade e tenta preservar a seleção informada."""
        previous = selected or self.currentText()
        self._clear()
        self._values = [str(value) for value in values if str(value).strip()]

        if not self._values:
            placeholder = QLabel(self.empty_text, self)
            placeholder.setObjectName("selection_empty_label")
            self.grid.addWidget(placeholder, 0, 0, 1, self.columns)
            self.setEnabled(False)
            return

        self.setEnabled(True)
        for index, value in enumerate(self._values):
            button = QPushButton(self.label_formatter(value), self)
            button.setObjectName("selection_button")
            button.setCheckable(True)
            button.setProperty("selection_value", value)
            button.setToolTip(value)
            button.clicked.connect(lambda checked=False, item=value: self._select(item))
            self._button_group.addButton(button)
            self._buttons.append(button)
            self.grid.addWidget(button, index // self.columns, index % self.columns)

        selected_index = self._values.index(previous) if previous in self._values else 0
        self._buttons[selected_index].setChecked(True)

        # Mantém todas as colunas com a mesma largura, inclusive na última linha incompleta.
        for column in range(self.columns):
            self.grid.setColumnStretch(column, 1)

    def currentText(self) -> str:
        checked = self._button_group.checkedButton()
        return str(checked.property("selection_value")) if checked else ""

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def count(self) -> int:
        return len(self._buttons)

    def _select(self, value: str) -> None:
        self.selectionChanged.emit(value)

    def _clear(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._button_group.deleteLater()
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self._buttons = []
        self._values = []
