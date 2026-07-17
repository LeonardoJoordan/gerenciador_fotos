import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ui.widgets.selection_button_grid import SelectionButtonGrid
from ui.widgets.tag_widget import TagWidget
from ui.widgets.clickable_image_label import ClickableImageLabel


class MemberEditDialog(QDialog):
    """Edição completa usando os mesmos seletores rápidos do cadastro."""

    def __init__(self, member: dict, config: dict, parent=None):
        super().__init__(parent)
        self.member = member
        self.config = config
        self.structure = config.get("esquadroes", {})
        self.abbreviations = config.get("abreviacoes", {})
        self._initial_section = member["fracao"]
        self.delete_requested = False

        self.setWindowTitle("Editar cadastro")
        self.setMinimumWidth(570)
        self.resize(640, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        layout.addWidget(self._label("Posto/Graduação"))
        self.rank_buttons = SelectionButtonGrid(
            columns=3, label_formatter=self._rank_label, parent=self
        )
        ranks = list(config.get("postos_graduacoes", []))
        if member["posto_grad"] not in ranks:
            ranks.append(member["posto_grad"])
        self.rank_buttons.set_options(ranks, member["posto_grad"])
        layout.addWidget(self.rank_buttons)

        layout.addWidget(self._label("Nome de Guerra"))
        self.name_input = QLineEdit(member["nome_guerra"], self)
        self.name_input.selectAll()
        layout.addWidget(self.name_input)

        layout.addWidget(self._label("Esquadrão/Fábrica"))
        self.squadron_buttons = SelectionButtonGrid(
            columns=3, label_formatter=self._squadron_label, parent=self
        )
        squadrons = list(self.structure)
        if member["esquadrao"] not in squadrons:
            squadrons.append(member["esquadrao"])
        self.squadron_buttons.set_options(squadrons, member["esquadrao"])
        self.squadron_buttons.selectionChanged.connect(self._update_sections)
        layout.addWidget(self.squadron_buttons)

        self.section_label = self._label("Fração/Setor")
        layout.addWidget(self.section_label)
        self.section_buttons = SelectionButtonGrid(
            columns=3,
            label_formatter=self._section_label,
            empty_text="Este esquadrão não possui frações",
            parent=self,
        )
        layout.addWidget(self.section_buttons)
        self._update_sections(self.squadron_buttons.currentText())
        layout.addStretch()

        footer = QHBoxLayout()
        delete_button = QPushButton("Excluir cadastro", self)
        delete_button.setObjectName("danger_btn")
        delete_button.clicked.connect(self._request_delete)
        footer.addWidget(delete_button)
        footer.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("form_label")
        return label

    def _rank_label(self, value: str) -> str:
        return self.abbreviations.get("postos_graduacoes", {}).get(value, value)

    def _squadron_label(self, value: str) -> str:
        return self.abbreviations.get("esquadroes", {}).get(value, value)

    def _section_label(self, value: str) -> str:
        squadron = self.squadron_buttons.currentText()
        return self.abbreviations.get("fracoes", {}).get(squadron, {}).get(value, value)

    def _update_sections(self, squadron: str):
        sections = self.structure.get(squadron, [])
        previous = self._initial_section or self.section_buttons.currentText()
        self._initial_section = ""
        self.section_buttons.set_options(sections, previous)
        self.section_label.setVisible(bool(sections))
        self.section_buttons.setVisible(True)

    def _accept_if_valid(self):
        if not self.rank_buttons.currentText() or not self.name_input.text().strip():
            QMessageBox.warning(self, "Cadastro incompleto", "Informe o posto e o nome.")
            return
        if not self.squadron_buttons.currentText():
            QMessageBox.warning(self, "Cadastro incompleto", "Selecione um esquadrão.")
            return
        self.accept()

    def _request_delete(self):
        self.delete_requested = True
        self.reject()

    def values(self) -> tuple[str, str, str, str]:
        return (
            self.rank_buttons.currentText(),
            self.name_input.text().strip(),
            self.squadron_buttons.currentText(),
            self.section_buttons.currentText(),
        )


class PhotoCard(QFrame):
    requestMove = Signal(str, str, str)
    requestEdit = Signal(str, str, str, str, str)
    requestGallery = Signal(object)
    requestAddPhotos = Signal(object, object)
    requestDelete = Signal(object)
    requestPhotoUpdate = Signal(object, bool)
    requestPreview = Signal(object, str)

    def __init__(self, member_data: dict, thumb_path: str, config: dict, parent=None):
        super().__init__(parent)
        self.data = member_data
        self.thumb_path = thumb_path
        self.config = config
        self.structure = config.get("esquadroes", {})
        self.setObjectName("photo_card")
        self.setProperty("withoutPhoto", self.data.get("photo_count", 0) == 0)
        self.setAcceptDrops(True)
        self.setFixedSize(200, 375)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(7)

        self.img_label = ClickableImageLabel(self)
        self.img_label.setFixedSize(180, 170)
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("background-color: #121212; border-radius: 4px;")
        if self.thumb_path and os.path.exists(self.thumb_path):
            pixmap = QPixmap(self.thumb_path)
            self.img_label.setPixmap(
                pixmap.scaled(self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        elif self.data.get("photo_count", 0) > 0:
            self.img_label.setText("Carregando miniatura…")
        else:
            self.img_label.setText("Foto pendente\n\nArraste uma imagem aqui")
        if self.data.get("photo_count", 0) > 0:
            self.img_label.setCursor(Qt.PointingHandCursor)
            self.img_label.setToolTip("Abrir imagem ampliada")
            self.img_label.clicked.connect(
                lambda: self.requestPreview.emit(
                    self.data, self.data["absolute_path"]
                )
            )

        self.name_label = QLabel(
            f"{self.data['posto_grad']} {self.data['nome_guerra']}", self
        )
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setObjectName("card_name")

        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(4)
        squadrons = list(self.structure)
        if self.data["esquadrao"] not in squadrons:
            squadrons.append(self.data["esquadrao"])
        sections = list(self.structure.get(self.data["esquadrao"], []))
        if self.data["fracao"] and self.data["fracao"] not in sections:
            sections.append(self.data["fracao"])

        self.esq_tag = TagWidget(
            "esquadrao",
            self.data["esquadrao"],
            squadrons,
            self,
            label_formatter=self._squadron_label,
        )
        self.esq_tag.tagChanged.connect(self._on_tag_changed)
        tags_layout.addWidget(self.esq_tag, 1)
        self.fracao_tag = None
        if self.data["fracao"]:
            self.fracao_tag = TagWidget(
                "fracao",
                self.data["fracao"],
                sections,
                self,
                label_formatter=self._section_label,
            )
            self.fracao_tag.setEnabled(bool(sections))
            self.fracao_tag.tagChanged.connect(self._on_tag_changed)
            tags_layout.addWidget(self.fracao_tag, 1)
        else:
            self.esq_tag.set_expanded(True)

        edit_button = QPushButton("Editar", self)
        edit_button.setObjectName("card_edit_btn")
        edit_button.clicked.connect(self._edit_member)

        count = self.data.get("photo_count", 0)
        self.update_toggle = QPushButton("", self)
        self.update_toggle.setObjectName("photo_update_toggle")
        self.update_toggle.setCheckable(True)
        self.update_toggle.setChecked(
            count > 0 and self.data.get("update_recommended", False)
        )
        self.update_toggle.setEnabled(count > 0)
        self.update_toggle.setFixedSize(28, 26)
        self.update_toggle.setCursor(Qt.PointingHandCursor)
        self.update_toggle.setAccessibleName("Marcar para atualizar foto")
        self.update_toggle.setToolTip(
            "Marcar como “Atualizar”: indica que este militar deve renovar a foto."
            if count > 0
            else "Cadastros sem foto já possuem o status “Pendente”."
        )
        self.update_toggle.clicked.connect(
            lambda checked: self.requestPhotoUpdate.emit(self.data, checked)
        )

        photo_count = QLabel(
            "Sem fotos" if count == 0 else f"{count} foto(s)", self
        )
        photo_count.setObjectName("photo_count_label")
        photo_count.setAlignment(Qt.AlignCenter)
        gallery_button = QPushButton("Adicionar foto" if count == 0 else "Galeria", self)
        gallery_button.setObjectName("card_edit_btn")
        gallery_button.clicked.connect(lambda: self.requestGallery.emit(self.data))

        actions = QHBoxLayout()
        actions.addWidget(gallery_button)
        actions.addWidget(edit_button)

        layout.addWidget(self.img_label, 0, Qt.AlignHCenter)
        layout.addWidget(self.name_label)
        layout.addWidget(self.update_toggle, 0, Qt.AlignHCenter)
        layout.addWidget(photo_count)
        layout.addLayout(tags_layout)
        layout.addLayout(actions)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.requestAddPhotos.emit(self.data, paths)
            event.acceptProposedAction()

    def _squadron_label(self, squadron: str) -> str:
        return (
            self.config.get("abreviacoes", {})
            .get("esquadroes", {})
            .get(squadron, squadron)
        )

    def _section_label(self, section: str) -> str:
        abbreviations = self.config.get("abreviacoes", {}).get("fracoes", {})
        squadron = self.data["esquadrao"]
        abbreviation = abbreviations.get(squadron, {}).get(section, "").strip()
        return abbreviation or section

    def set_thumbnail(self, photo_path: str, thumbnail_path: str):
        """Atualiza a imagem quando o worker terminar, já na thread da interface."""
        if os.path.abspath(photo_path) != os.path.abspath(self.data["absolute_path"]):
            return
        pixmap = QPixmap(thumbnail_path)
        if pixmap.isNull():
            self.img_label.setText("Sem Foto")
            return
        self.img_label.setText("")
        self.img_label.setPixmap(
            pixmap.scaled(self.img_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def set_update_recommended(self, recommended: bool):
        self.data["update_recommended"] = recommended
        self.update_toggle.blockSignals(True)
        self.update_toggle.setChecked(recommended)
        self.update_toggle.blockSignals(False)

    def _on_tag_changed(self, tag_type: str, new_value: str):
        squadron = self.data["esquadrao"]
        section = self.data["fracao"]
        if tag_type == "esquadrao":
            squadron = new_value
            available_sections = self.structure.get(squadron, [])
            section = section if section in available_sections else (
                available_sections[0] if available_sections else ""
            )
        else:
            section = new_value
        self.requestMove.emit(self.data["member_path"], squadron, section)

    def _edit_member(self):
        dialog = MemberEditDialog(self.data, self.config, self)
        result = dialog.exec()
        if dialog.delete_requested:
            self.requestDelete.emit(self.data)
        elif result == QDialog.Accepted:
            rank, name, squadron, section = dialog.values()
            original = (
                self.data["posto_grad"],
                self.data["nome_guerra"],
                self.data["esquadrao"],
                self.data["fracao"],
            )
            if (rank, name, squadron, section) != original:
                self.requestEdit.emit(
                    self.data["member_path"], rank, name, squadron, section
                )
