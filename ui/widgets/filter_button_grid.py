from collections.abc import Callable, Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FilterButtonGrid(QWidget):
    """Grade de filtros com seleção múltipla e um modo explícito de 'todos'."""

    selectionChanged = Signal()

    def __init__(
        self,
        columns: int = 3,
        label_formatter: Callable[[str], str] | None = None,
        empty_text: str = "Nenhuma opção disponível",
        parent=None,
    ):
        super().__init__(parent)
        self.columns = max(1, columns)
        self.label_formatter = label_formatter or (lambda value: value)
        self.empty_text = empty_text
        self._values: list[str] = []
        self._buttons: dict[str, QPushButton] = {}
        self._all_mode = False

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)

    def set_options(
        self,
        values: Iterable[str],
        selected_values: Iterable[str] | None = None,
        all_mode: bool = False,
    ) -> None:
        previous = set(self.selected_values()) if selected_values is None else set(selected_values)
        self._clear()
        self._values = list(dict.fromkeys(str(value) for value in values if str(value).strip()))

        if not self._values:
            placeholder = QLabel(self.empty_text, self)
            placeholder.setObjectName("filter_empty_label")
            self.grid.addWidget(placeholder, 0, 0, 1, self.columns)
            self.setEnabled(False)
            return

        self.setEnabled(True)
        selected = set(self._values) if all_mode else previous.intersection(self._values)
        for index, value in enumerate(self._values):
            button = QPushButton(self.label_formatter(value), self)
            button.setObjectName("filter_button")
            button.setCheckable(True)
            button.setChecked(value in selected)
            button.setToolTip(value)
            button.clicked.connect(lambda checked=False, item=value: self._button_clicked(item))
            self._buttons[value] = button
            self.grid.addWidget(button, index // self.columns, index % self.columns)

        self._all_mode = bool(self._values) and all_mode
        for column in range(self.columns):
            self.grid.setColumnStretch(column, 1)

    def selected_values(self) -> list[str]:
        return [value for value in self._values if self._buttons[value].isChecked()]

    def select_all(self, emit: bool = True) -> None:
        for button in self._buttons.values():
            button.setChecked(True)
        self._all_mode = bool(self._buttons)
        if emit:
            self.selectionChanged.emit()

    def clear_selection(self, emit: bool = True) -> None:
        for button in self._buttons.values():
            button.setChecked(False)
        self._all_mode = False
        if emit:
            self.selectionChanged.emit()

    def all_selected(self) -> bool:
        return bool(self._buttons) and all(button.isChecked() for button in self._buttons.values())

    def count(self) -> int:
        return len(self._buttons)

    def _button_clicked(self, value: str) -> None:
        # Quando 'todos' estava ativo, um clique passa a significar 'somente este'.
        if self._all_mode:
            for item, button in self._buttons.items():
                button.setChecked(item == value)
            self._all_mode = False
        else:
            self._all_mode = self.all_selected()
        self.selectionChanged.emit()

    def _clear(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._values = []
        self._buttons = {}
        self._all_mode = False


class GroupedFilterButtonGrid(QWidget):
    """Grade de filtros que mantém as opções separadas por esquadrão."""

    selectionChanged = Signal()

    def __init__(
        self,
        columns: int = 3,
        group_formatter: Callable[[str], str] | None = None,
        label_formatter: Callable[[str, str], str] | None = None,
        empty_text: str = "Sem frações configuradas",
        parent=None,
    ):
        super().__init__(parent)
        self.columns = max(1, columns)
        self.group_formatter = group_formatter or (lambda value: value)
        self.label_formatter = label_formatter or (lambda group, value: value)
        self.empty_text = empty_text
        self._buttons: dict[tuple[str, str], QPushButton] = {}
        self._all_mode = False
        self.groups_layout = QVBoxLayout(self)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_layout.setSpacing(7)

    def set_groups(
        self,
        groups: dict[str, list[str]],
        selected_values=None,
        all_mode: bool = False,
    ) -> None:
        previous = set(self.selected_values()) if selected_values is None else set(selected_values)
        self._clear()
        show_group_headers = len(groups) > 1
        for group, raw_values in groups.items():
            values = list(dict.fromkeys(str(value) for value in raw_values if str(value).strip()))
            if show_group_headers:
                self.groups_layout.addLayout(self._group_header(self.group_formatter(group)))
            if not values:
                empty = QLabel(self.empty_text, self)
                empty.setObjectName("filter_empty_label")
                self.groups_layout.addWidget(empty)
                continue
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(6)
            grid.setVerticalSpacing(6)
            for index, value in enumerate(values):
                key = (group, value)
                button = QPushButton(self.label_formatter(group, value), self)
                button.setObjectName("filter_button")
                button.setCheckable(True)
                button.setChecked(all_mode or key in previous)
                button.setToolTip(value)
                button.clicked.connect(
                    lambda checked=False, item=key: self._button_clicked(item)
                )
                self._buttons[key] = button
                grid.addWidget(button, index // self.columns, index % self.columns)
            for column in range(self.columns):
                grid.setColumnStretch(column, 1)
            self.groups_layout.addLayout(grid)
        self._all_mode = bool(self._buttons) and all_mode
        self.setEnabled(bool(groups))

    def selected_values(self) -> list[tuple[str, str]]:
        return [key for key, button in self._buttons.items() if button.isChecked()]

    def select_all(self, emit: bool = True) -> None:
        for button in self._buttons.values():
            button.setChecked(True)
        self._all_mode = bool(self._buttons)
        if emit:
            self.selectionChanged.emit()

    def clear_selection(self, emit: bool = True) -> None:
        for button in self._buttons.values():
            button.setChecked(False)
        self._all_mode = False
        if emit:
            self.selectionChanged.emit()

    def all_selected(self) -> bool:
        return bool(self._buttons) and all(
            button.isChecked() for button in self._buttons.values()
        )

    def count(self) -> int:
        return len(self._buttons)

    def _button_clicked(self, key: tuple[str, str]) -> None:
        if self._all_mode:
            for item, button in self._buttons.items():
                button.setChecked(item == key)
            self._all_mode = False
        else:
            self._all_mode = self.all_selected()
        self.selectionChanged.emit()

    def _group_header(self, text: str) -> QHBoxLayout:
        header = QHBoxLayout()
        header.setContentsMargins(3, 3, 3, 0)
        left = QFrame(self)
        left.setFrameShape(QFrame.HLine)
        left.setObjectName("fraction_group_line")
        label = QLabel(text, self)
        label.setObjectName("fraction_group_label")
        right = QFrame(self)
        right.setFrameShape(QFrame.HLine)
        right.setObjectName("fraction_group_line")
        header.addWidget(left, 1)
        header.addWidget(label)
        header.addWidget(right, 1)
        return header

    def _clear(self) -> None:
        self._clear_layout(self.groups_layout)
        self._buttons = {}
        self._all_mode = False

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
