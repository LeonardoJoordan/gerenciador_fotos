import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.flow_layout import FlowLayout


class GalleryPhoto(QFrame):
    requestPrimary = Signal(str)
    requestRotate = Signal(str, int)
    selectionChanged = Signal(str, bool)

    def __init__(self, photo_path: str, thumb_path: str, primary: bool, parent=None):
        super().__init__(parent)
        self.photo_path = photo_path
        self.setObjectName("gallery_photo")
        self.setFixedSize(270, 320)

        layout = QVBoxLayout(self)
        preview = QLabel(self)
        preview.setFixedSize(248, 185)
        preview.setAlignment(Qt.AlignCenter)
        preview.setStyleSheet("background-color: #121212; border-radius: 4px;")
        pixmap = QPixmap(thumb_path)
        if not pixmap.isNull():
            preview.setPixmap(
                pixmap.scaled(preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            preview.setText("Imagem indisponível")
        preview.setToolTip(photo_path)
        layout.addWidget(preview, 0, Qt.AlignHCenter)

        status = QLabel("Foto principal" if primary else os.path.basename(photo_path), self)
        status.setObjectName("primary_photo_label" if primary else "photo_filename_label")
        status.setAlignment(Qt.AlignCenter)
        status.setToolTip(os.path.basename(photo_path))
        layout.addWidget(status)

        rotation_controls = QHBoxLayout()
        select_box = QCheckBox("Selecionar", self)
        select_box.toggled.connect(
            lambda checked: self._selection_changed(checked)
        )
        rotate_left = QPushButton("↶", self)
        rotate_left.setObjectName("rotate_image_btn")
        rotate_left.setFixedSize(32, 28)
        rotate_left.setToolTip("Girar 90° para a esquerda")
        rotate_left.clicked.connect(
            lambda: self.requestRotate.emit(self.photo_path, -90)
        )
        rotate_right = QPushButton("↷", self)
        rotate_right.setObjectName("rotate_image_btn")
        rotate_right.setFixedSize(32, 28)
        rotate_right.setToolTip("Girar 90° para a direita")
        rotate_right.clicked.connect(
            lambda: self.requestRotate.emit(self.photo_path, 90)
        )
        primary_button = QPushButton("Definir principal", self)
        primary_button.setObjectName("gallery_action_btn")
        primary_button.setMinimumWidth(116)
        primary_button.setEnabled(not primary)
        primary_button.clicked.connect(lambda: self.requestPrimary.emit(self.photo_path))
        rotation_controls.addWidget(select_box)
        rotation_controls.addStretch()
        rotation_controls.addWidget(rotate_left)
        rotation_controls.addWidget(rotate_right)
        layout.addLayout(rotation_controls)
        layout.addWidget(primary_button)

    def _selection_changed(self, checked: bool):
        self.setProperty("selected", checked)
        self.style().unpolish(self)
        self.style().polish(self)
        self.selectionChanged.emit(self.photo_path, checked)


class MemberGalleryDialog(QDialog):
    requestAdd = Signal(object)
    requestPrimary = Signal(object, str)
    requestRotate = Signal(object, str, int)
    requestExport = Signal(object)
    requestDelete = Signal(object, object)

    def __init__(self, member: dict, thumbnail_paths: dict[str, str], parent=None):
        super().__init__(parent)
        self.member = member
        self.selected_paths: set[str] = set()
        self.setObjectName("member_gallery_dialog")
        self.setWindowTitle(
            f"Galeria — {member['posto_grad']} {member['nome_guerra']}"
        )
        self.resize(820, 620)
        self.setMinimumSize(620, 450)

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel(
            f"{member['posto_grad']} {member['nome_guerra']} · "
            f"{member['photo_count']} foto(s)",
            self,
        )
        self.title.setObjectName("section_title")
        add_button = QPushButton("Adicionar fotos", self)
        add_button.setObjectName("primary_btn")
        add_button.clicked.connect(self._request_add)
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(add_button)
        layout.addLayout(header)

        if member.get("is_legacy"):
            hint = QLabel(
                "Cadastro no formato antigo. Ao adicionar fotos, ele será convertido "
                "para uma pasta individual.",
                self,
            )
            hint.setObjectName("settings_hint")
            hint.setWordWrap(True)
            layout.addWidget(hint)

        self.selection_bar = QFrame(self)
        self.selection_bar.setObjectName("gallery_selection_bar")
        selection_layout = QHBoxLayout(self.selection_bar)
        selection_layout.setContentsMargins(10, 7, 10, 7)
        self.selection_count = QLabel("", self.selection_bar)
        self.export_button = QPushButton("Exportar cópia", self.selection_bar)
        self.export_button.clicked.connect(self._request_export)
        self.delete_button = QPushButton("Excluir imagem", self.selection_bar)
        self.delete_button.setObjectName("danger_btn")
        self.delete_button.clicked.connect(self._request_delete)
        selection_layout.addStretch()
        selection_layout.addWidget(self.selection_count)
        selection_layout.addWidget(self.export_button)
        selection_layout.addWidget(self.delete_button)
        selection_layout.addStretch()
        self.selection_bar.setVisible(False)
        layout.addWidget(self.selection_bar)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.container = QWidget(scroll)
        self.container.setObjectName("gallery_container")
        self.flow = FlowLayout(self.container, margin=8, h_spacing=14, v_spacing=14)
        self.container.setLayout(self.flow)
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)
        self._populate_photos(thumbnail_paths)

        close_button = QPushButton("Fechar", self)
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, 0, Qt.AlignRight)

    def _request_add(self):
        self.requestAdd.emit(self.member)

    def _request_primary(self, photo_path: str):
        self.requestPrimary.emit(self.member, photo_path)

    def refresh_member(self, member: dict, thumbnail_paths: dict[str, str]):
        """Atualiza a galeria aberta após uma alteração nos arquivos."""
        self.member = member
        self.selected_paths.clear()
        self.selection_bar.setVisible(False)
        self.title.setText(
            f"{member['posto_grad']} {member['nome_guerra']} · "
            f"{member['photo_count']} foto(s)"
        )
        self._populate_photos(thumbnail_paths)

    def _populate_photos(self, thumbnail_paths: dict[str, str]):
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        primary_path = os.path.abspath(self.member["absolute_path"])
        for photo in self.member["photos"]:
            card = GalleryPhoto(
                photo,
                thumbnail_paths.get(photo, ""),
                os.path.abspath(photo) == primary_path,
                self.container,
            )
            card.requestPrimary.connect(self._request_primary)
            card.requestRotate.connect(self._request_rotate)
            card.selectionChanged.connect(self._update_selection)
            self.flow.addWidget(card)

    def _update_selection(self, photo_path: str, checked: bool):
        if checked:
            self.selected_paths.add(photo_path)
        else:
            self.selected_paths.discard(photo_path)
        count = len(self.selected_paths)
        self.selection_count.setText(
            f"{count} imagem selecionada" if count == 1 else f"{count} imagens selecionadas"
        )
        self.export_button.setText(
            "Exportar cópia" if count == 1 else "Exportar cópias"
        )
        self.delete_button.setText(
            "Excluir imagem" if count == 1 else "Excluir imagens"
        )
        self.selection_bar.setVisible(count > 0)

    def _request_rotate(self, photo_path: str, degrees: int):
        self.requestRotate.emit(self.member, photo_path, degrees)

    def _request_export(self):
        if self.selected_paths:
            self.requestExport.emit(sorted(self.selected_paths))

    def _request_delete(self):
        if self.selected_paths:
            self.requestDelete.emit(self.member, sorted(self.selected_paths))
