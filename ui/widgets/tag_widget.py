from collections.abc import Callable

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QSizePolicy
from PySide6.QtCore import Signal, Qt

class TagWidget(QWidget):
    # Sinal emitido quando a tag é alterada pelo usuário: (tipo_da_tag, novo_valor)
    tagChanged = Signal(str, str)

    def __init__(
        self,
        tag_type: str,
        current_value: str,
        available_options: list,
        parent=None,
        label_formatter: Callable[[str], str] | None = None,
    ):
        super().__init__(parent)
        self.tag_type = tag_type # "esquadrao" ou "fracao"
        self.current_value = current_value
        self.options = available_options
        self.label_formatter = label_formatter or (lambda value: value)

        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Label estática que se comporta como um botão/tag visual
        self.label = QLabel(self._label_text(self.current_value), self)
        self.label.setObjectName("tag_lbl")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setCursor(Qt.PointingHandCursor)
        self._update_tooltip()
        self.label.setMaximumWidth(88)
        
        # Monitora o clique na label para trocar pelo ComboBox
        self.label.mousePressEvent = self._on_label_clicked

        # ComboBox que fica oculto até o usuário clicar na label
        self.combo = QComboBox(self)
        self.combo.setVisible(False)
        self.combo.setEditable(True)
        self.combo.lineEdit().setReadOnly(True)
        self.combo.lineEdit().setAlignment(Qt.AlignCenter)
        self.combo.lineEdit().setStyleSheet(
            "background: transparent; border: none; padding: 0;"
        )
        self.combo.addItems(self.options)
        self._center_combo_items()
        
        # Define o index atual para o valor correspondente
        index = self.combo.findText(self.current_value)
        if index >= 0:
            self.combo.setCurrentIndex(index)

        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        # Se o usuário tirar o foco do combobox sem selecionar, ele volta a ser label
        self.combo.focusOutEvent = lambda event: self._switch_to_label()

        layout.addWidget(self.label)
        layout.addWidget(self.combo)

    def _on_label_clicked(self, event):
        if event.button() == Qt.LeftButton and self.options and self.isEnabled():
            self.label.setVisible(False)
            self.combo.setVisible(True)
            self.combo.setFocus()
            self.combo.showPopup() # Abre a lista automaticamente ao clicar

    def _on_combo_changed(self, index):
        new_value = self.combo.itemText(index)
        if new_value != self.current_value:
            self.current_value = new_value
            self.label.setText(self._label_text(new_value))
            self._update_tooltip()
            self.tagChanged.emit(self.tag_type, new_value)
        self._switch_to_label()

    def _switch_to_label(self):
        self.combo.setVisible(False)
        self.label.setVisible(True)

    def update_options(self, new_options: list):
        """Atualiza a lista de opções caso novos esquadrões/frações sejam criados."""
        self.options = new_options
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(self.options)
        self._center_combo_items()
        index = self.combo.findText(self.current_value)
        if index >= 0:
            self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)

    def set_expanded(self, expanded: bool = True):
        """Permite que uma tag única use toda a largura disponível no card."""
        policy = QSizePolicy.Expanding if expanded else QSizePolicy.Preferred
        self.label.setSizePolicy(policy, QSizePolicy.Preferred)
        self.combo.setSizePolicy(policy, QSizePolicy.Fixed)
        self.label.setMaximumWidth(167 if expanded else 88)

    def _center_combo_items(self):
        for index in range(self.combo.count()):
            self.combo.setItemData(index, Qt.AlignCenter, Qt.TextAlignmentRole)

    def _label_text(self, value: str) -> str:
        return self.label_formatter(value) if value else "Sem fração"

    def _update_tooltip(self):
        self.label.setToolTip(
            f"{self.current_value}\nClique para alterar o/a {self.tag_type}"
        )
