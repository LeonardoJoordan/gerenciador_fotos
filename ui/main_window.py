import os
import shutil
import weakref
from pathlib import Path

from PySide6.QtCore import QSettings, QThreadPool, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.file_manager import FileManager
from core.image_processor import ImageProcessor
from core.report_service import ReportService
from core.roster_csv import RosterCsv
from core.thumbnail_worker import ThumbnailWorker
from ui.styles import STYLE_SHEET
from ui.widgets.filter_button_grid import FilterButtonGrid, GroupedFilterButtonGrid
from ui.widgets.flow_layout import FlowLayout
from ui.widgets.photo_card import PhotoCard
from ui.widgets.report_dashboard import ReportDashboard
from ui.widgets.roster_import_dialog import RosterImportDialog
from ui.widgets.member_gallery import MemberGalleryDialog
from ui.widgets.selection_button_grid import SelectionButtonGrid


LEGACY_SETTINGS_APPLICATION = "Gerenciador Semântico de Fotos"


class DropArea(QFrame):
    filesDropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop_area")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(105)
        layout = QVBoxLayout(self)
        label = QLabel("Arraste uma imagem aqui\nou clique para selecionar", self)
        label.setAlignment(Qt.AlignCenter)
        label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(label)

    @staticmethod
    def _valid_image(path: str) -> bool:
        return os.path.isfile(path) and os.path.splitext(path)[1].lower() in FileManager.VALID_EXTENSIONS

    def dragEnterEvent(self, event: QDragEnterEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if any(self._valid_image(path) for path in paths):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        valid_paths = [path for path in paths if self._valid_image(path)]
        if valid_paths:
            self.filesDropped.emit(valid_paths)
            event.acceptProposedAction()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gerenciador de Fotos de Pessoal")
        self.setStyleSheet(STYLE_SHEET)

        self.file_manager = FileManager()
        self.image_processor = ImageProcessor()
        self.root_directory = ""
        self.config = {
            "esquadroes": {},
            "postos_graduacoes": [],
            "abreviacoes": {"postos_graduacoes": {}, "esquadroes": {}, "fracoes": {}},
        }
        self.members_data = []
        self.import_source_path = ""
        self.import_rotation = 0
        self.thumbnail_pool = QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(4)
        self._thumbnail_jobs = {}
        self._thumbnail_targets = {}
        self.init_ui()
        self.restore_last_root_directory()

    def init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(14, 12, 14, 14)

        root_bar = QHBoxLayout()
        self.btn_select_dir = QPushButton("Selecionar Pasta Raiz", self)
        self.btn_select_dir.setObjectName("primary_btn")
        self.btn_select_dir.clicked.connect(self.select_root_directory)
        self.lbl_dir_status = QLabel("Nenhuma pasta selecionada", self)
        self.lbl_dir_status.setObjectName("directory_status")
        self.lbl_dir_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root_bar.addWidget(self.btn_select_dir)
        root_bar.addWidget(self.lbl_dir_status, 1)
        root_layout.addLayout(root_bar)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_import_tab(), "Importação Rápida")
        self.tabs.addTab(self._build_gallery_tab(), "Galeria e Filtros")
        self.tabs.addTab(self._build_reports_tab(), "Relatórios")
        self.tabs.addTab(self._build_settings_tab(), "Configurações")
        self.tabs.setEnabled(False)
        root_layout.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------ Importação
    def _build_import_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(28)

        left = QVBoxLayout()
        preview_header = QHBoxLayout()
        preview_header.addWidget(self._title("Foto selecionada"))
        preview_header.addStretch()
        self.btn_rotate_import_counterclockwise = QPushButton("↶", self)
        self.btn_rotate_import_counterclockwise.setObjectName("rotate_image_btn")
        self.btn_rotate_import_counterclockwise.setFixedSize(34, 30)
        self.btn_rotate_import_counterclockwise.setToolTip(
            "Girar 90° para a esquerda"
        )
        self.btn_rotate_import_counterclockwise.setEnabled(False)
        self.btn_rotate_import_counterclockwise.clicked.connect(
            lambda: self.rotate_import_preview(-90)
        )
        self.btn_rotate_import_clockwise = QPushButton("↷", self)
        self.btn_rotate_import_clockwise.setObjectName("rotate_image_btn")
        self.btn_rotate_import_clockwise.setFixedSize(34, 30)
        self.btn_rotate_import_clockwise.setToolTip("Girar 90° para a direita")
        self.btn_rotate_import_clockwise.setEnabled(False)
        self.btn_rotate_import_clockwise.clicked.connect(
            lambda: self.rotate_import_preview(90)
        )
        preview_header.addWidget(self.btn_rotate_import_counterclockwise)
        preview_header.addWidget(self.btn_rotate_import_clockwise)
        left.addLayout(preview_header)
        self.import_preview = QLabel("Nenhuma imagem selecionada", self)
        self.import_preview.setObjectName("import_preview")
        self.import_preview.setAlignment(Qt.AlignCenter)
        self.import_preview.setMinimumSize(360, 360)
        left.addWidget(self.import_preview, 1)
        self.drop_area = DropArea(self)
        self.drop_area.clicked.connect(self.select_import_file)
        self.drop_area.filesDropped.connect(lambda paths: self.set_import_source(paths[0]))
        left.addWidget(self.drop_area)

        right_panel = QFrame(self)
        right_panel.setObjectName("form_panel")
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(24, 24, 24, 24)
        right.addWidget(self._title("Cadastro do militar"))
        form = QVBoxLayout()
        form.setSpacing(9)
        self.import_rank_buttons = SelectionButtonGrid(
            columns=3,
            label_formatter=self._rank_button_label,
            empty_text="Cadastre postos na aba Configurações",
            parent=self,
        )
        self.import_name_input = QLineEdit(self)
        self.import_name_input.setPlaceholderText("Ex.: Antunes")
        self.import_squadron_buttons = SelectionButtonGrid(
            columns=3,
            label_formatter=self._squadron_button_label,
            empty_text="Cadastre esquadrões na aba Configurações",
            parent=self,
        )
        self.import_section_buttons = SelectionButtonGrid(
            columns=3,
            label_formatter=self._section_button_label,
            empty_text="Este esquadrão não possui frações",
            parent=self,
        )
        self.import_squadron_buttons.selectionChanged.connect(self.update_import_sections)
        form.addWidget(self._form_label("Posto/Graduação"))
        form.addWidget(self.import_rank_buttons)
        form.addWidget(self._form_label("Nome de Guerra"))
        form.addWidget(self.import_name_input)
        form.addWidget(self._form_label("Esquadrão/Fábrica"))
        form.addWidget(self.import_squadron_buttons)
        self.import_section_label = self._form_label("Fração do esquadrão")
        form.addWidget(self.import_section_label)
        form.addWidget(self.import_section_buttons)
        right.addLayout(form)
        right.addStretch()
        batch_registration_button = QPushButton("Cadastrar em lote", self)
        batch_registration_button.clicked.connect(self.open_batch_registration)
        right.addWidget(batch_registration_button)
        self.btn_save_import = QPushButton("Salvar", self)
        self.btn_save_import.setObjectName("primary_btn")
        self.btn_save_import.clicked.connect(self.save_import)
        right.addWidget(self.btn_save_import)

        layout.addLayout(left, 3)
        layout.addWidget(right_panel, 2)
        return tab

    def open_batch_registration(self):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Cadastrar em lote")
        dialog.setIcon(QMessageBox.Information)
        dialog.setText("Como deseja realizar o cadastro em lote?")
        dialog.setInformativeText(
            "Exporte o modelo baseado na estrutura atual, preencha-o e depois volte "
            "para importar a relação pronta."
        )
        import_button = dialog.addButton(
            "Importar relação preenchida", QMessageBox.ActionRole
        )
        template_button = dialog.addButton("Exportar modelo CSV", QMessageBox.ActionRole)
        dialog.addButton("Cancelar", QMessageBox.RejectRole)
        dialog.exec()

        if dialog.clickedButton() is import_button:
            self.import_roster_csv()
        elif dialog.clickedButton() is template_button:
            self.export_roster_template()

    def export_roster_template(self):
        suggested_path = os.path.join(
            self.root_directory, RosterCsv.TEMPLATE_FILENAME
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar modelo de cadastro em lote",
            suggested_path,
            "Relações CSV (*.csv)",
        )
        if not path:
            return
        try:
            written_path = RosterCsv.write_template(path, self.config)
        except Exception as exc:
            self._show_error("Não foi possível exportar o modelo", exc)
            return
        QMessageBox.information(
            self,
            "Modelo exportado",
            f"O modelo de cadastro em lote foi salvo em:\n{written_path}",
        )

    def import_roster_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar relação", "", "Relações CSV (*.csv)"
        )
        if not path:
            return
        try:
            rows = RosterCsv.read(path, self.config)
        except Exception as exc:
            self._show_error("CSV inválido", exc)
            return
        dialog = RosterImportDialog(rows, self)
        if dialog.exec() != QDialog.Accepted:
            return

        existing = {
            (
                member["posto_grad"].casefold(),
                member["nome_guerra"].casefold(),
                member["esquadrao"].casefold(),
                member["fracao"].casefold(),
            )
            for member in self.members_data
        }
        created = 0
        skipped = 0
        for row in dialog.valid_rows():
            values = {
                key: row[key]
                for key in ("posto_grad", "nome_guerra", "esquadrao", "fracao")
            }
            key = tuple(values[field].casefold() for field in values)
            if key in existing:
                skipped += 1
                continue
            try:
                self.file_manager.create_member(**values)
                existing.add(key)
                created += 1
            except FileExistsError:
                skipped += 1
        self.reload_data()
        QMessageBox.information(
            self,
            "Relação importada",
            f"{created} cadastro(s) criado(s).\n{skipped} duplicado(s) ignorado(s).",
        )

    def select_import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar foto", "", FileManager.image_dialog_filter()
        )
        if path:
            self.set_import_source(path)

    def set_import_source(self, path: str):
        pixmap = self.image_processor.load_oriented_pixmap(path)
        if pixmap.isNull():
            QMessageBox.warning(self, "Imagem inválida", "O arquivo não pôde ser lido como imagem.")
            return
        self.import_source_path = path
        self.import_rotation = 0
        self.btn_rotate_import_counterclockwise.setEnabled(True)
        self.btn_rotate_import_clockwise.setEnabled(True)
        self._update_import_preview()

    def rotate_import_preview(self, degrees: int = 90):
        if not self.import_source_path:
            return
        self.import_rotation = (self.import_rotation + degrees) % 360
        self._update_import_preview()

    def _update_import_preview(self):
        pixmap = self.image_processor.load_oriented_pixmap(self.import_source_path)
        if self.import_rotation:
            pixmap = pixmap.transformed(
                QTransform().rotate(self.import_rotation), Qt.SmoothTransformation
            )
        self.import_preview.setPixmap(
            pixmap.scaled(self.import_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.import_preview.setToolTip(self.import_source_path)

    def update_import_sections(self, squadron: str):
        sections = self.config.get("esquadroes", {}).get(squadron, [])
        self.import_section_buttons.set_options(sections)

    def save_import(self):
        values = {
            "posto_grad": self.import_rank_buttons.currentText().strip(),
            "nome_guerra": self.import_name_input.text().strip(),
            "esquadrao": self.import_squadron_buttons.currentText().strip(),
            "fracao": self.import_section_buttons.currentText().strip(),
        }
        if not all(values[key] for key in ("posto_grad", "nome_guerra", "esquadrao")):
            QMessageBox.warning(self, "Cadastro incompleto", "Preencha posto, nome e esquadrão.")
            return
        existing = next(
            (
                member for member in self.members_data
                if member["posto_grad"].casefold() == values["posto_grad"].casefold()
                and member["nome_guerra"].casefold() == values["nome_guerra"].casefold()
                and member["esquadrao"].casefold() == values["esquadrao"].casefold()
                and member["fracao"].casefold() == values["fracao"].casefold()
            ),
            None,
        )
        if existing:
            if not self.import_source_path:
                QMessageBox.warning(
                    self,
                    "Cadastro já existente",
                    "Este militar já está cadastrado nesta unidade.",
                )
                return
            answer = QMessageBox.question(
                self,
                "Funcionário já cadastrado",
                "Este funcionário já possui foto(s). Deseja adicionar esta imagem "
                "à galeria existente?",
            )
            if answer != QMessageBox.Yes:
                return
        destination = ""
        try:
            if not self.import_source_path:
                self.file_manager.create_member(**values)
            elif existing:
                member_path = existing["member_path"]
                if existing.get("is_legacy"):
                    self.image_processor.invalidate_thumbnail(
                        self.root_directory, existing["absolute_path"]
                    )
                    member_path = self.file_manager.convert_legacy_member(member_path)
                destination = self.file_manager.add_photos(
                    member_path, [self.import_source_path]
                )[0]
            else:
                destination = self.file_manager.import_and_format_photo(
                    self.import_source_path, **values
                )
            if destination and self.import_rotation:
                self.image_processor.rotate_image_file(destination, self.import_rotation)
        except Exception as exc:
            if destination and os.path.isfile(destination):
                self.image_processor.invalidate_thumbnail(
                    self.root_directory, destination
                )
                os.remove(destination)
                member_dir = os.path.dirname(destination)
                if os.path.isdir(member_dir) and not os.listdir(member_dir):
                    os.rmdir(member_dir)
            self._show_error("Erro na importação", exc)
            return
        self.clear_import_form()
        self.reload_data()
        QMessageBox.information(
            self,
            "Cadastro salvo",
            "A foto foi importada e organizada com sucesso."
            if destination
            else "O cadastro sem foto foi criado com sucesso.",
        )

    def clear_import_form(self):
        self.import_source_path = ""
        self.import_rotation = 0
        self.btn_rotate_import_counterclockwise.setEnabled(False)
        self.btn_rotate_import_clockwise.setEnabled(False)
        self.import_preview.clear()
        self.import_preview.setText("Nenhuma imagem selecionada")
        self.import_preview.setToolTip("")
        self.import_name_input.clear()
        self.import_rank_buttons.setCurrentIndex(0)
        self.import_name_input.setFocus()

    # --------------------------------------------------------------------- Galeria
    def _build_gallery_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame(self)
        sidebar.setObjectName("sidebar")
        filters = QVBoxLayout(sidebar)
        filters.setContentsMargins(16, 20, 16, 20)
        filters.setSpacing(11)
        filters.addWidget(self._title("Filtros dinâmicos"))

        self.btn_all_photo_status = self._filter_toggle_button()
        filters.addLayout(
            self._filter_header("Situação da foto", self.btn_all_photo_status)
        )
        self.filter_photo_buttons = FilterButtonGrid(columns=2, parent=self)
        filters.addWidget(self.filter_photo_buttons)

        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Buscar pelo nome...")
        filters.addWidget(QLabel("Busca rápida", self))
        filters.addWidget(self.search_input)

        self.btn_all_ranks = self._filter_toggle_button()
        filters.addLayout(self._filter_header("Posto/Graduação", self.btn_all_ranks))
        self.filter_rank_buttons = FilterButtonGrid(
            columns=3,
            label_formatter=self._rank_button_label,
            empty_text="Nenhum posto configurado",
            parent=self,
        )
        filters.addWidget(self.filter_rank_buttons)

        self.btn_all_squadrons = self._filter_toggle_button()
        filters.addLayout(self._filter_header("Esquadrão", self.btn_all_squadrons))
        self.filter_squadron_buttons = FilterButtonGrid(
            columns=3,
            label_formatter=self._squadron_button_label,
            empty_text="Nenhum esquadrão configurado",
            parent=self,
        )
        filters.addWidget(self.filter_squadron_buttons)

        self.btn_all_sections = self._filter_toggle_button()
        self.filter_section_header = QWidget(self)
        section_header_layout = self._filter_header("Fração/Setor", self.btn_all_sections)
        self.filter_section_header.setLayout(section_header_layout)
        filters.addWidget(self.filter_section_header)
        self.filter_section_buttons = GroupedFilterButtonGrid(
            columns=2,
            group_formatter=self._squadron_button_label,
            label_formatter=self._filter_section_button_label,
            empty_text="Sem frações configuradas",
            parent=self,
        )
        filters.addWidget(self.filter_section_buttons)

        unknown_separator = QFrame(self)
        unknown_separator.setFrameShape(QFrame.HLine)
        unknown_separator.setObjectName("filter_separator")
        filters.addWidget(unknown_separator)
        self.filter_unrecognized_button = QPushButton("Não reconhecidos", self)
        self.filter_unrecognized_button.setObjectName("unrecognized_filter_button")
        self.filter_unrecognized_button.setCheckable(True)
        self.filter_unrecognized_button.setToolTip(
            "Mostra fotos com posto, esquadrão ou fração fora do config.json"
        )
        self.filter_unrecognized_button.toggled.connect(self._on_unrecognized_filter_toggled)
        filters.addWidget(self.filter_unrecognized_button)
        filters.addStretch()

        self.search_input.textChanged.connect(self.populate_gallery)
        self.filter_photo_buttons.selectionChanged.connect(
            self._on_photo_filters_changed
        )
        self.filter_rank_buttons.selectionChanged.connect(self._on_rank_filters_changed)
        self.filter_squadron_buttons.selectionChanged.connect(self._on_squadron_filters_changed)
        self.filter_section_buttons.selectionChanged.connect(self._on_section_filters_changed)
        self.btn_all_ranks.clicked.connect(self._toggle_all_ranks)
        self.btn_all_photo_status.clicked.connect(self._toggle_all_photo_status)
        self.btn_all_squadrons.clicked.connect(self._toggle_all_squadrons)
        self.btn_all_sections.clicked.connect(self._toggle_all_sections)

        content = QFrame(self)
        content.setObjectName("main_content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        self.lbl_section = self._title("Militares")
        content_layout.addWidget(self.lbl_section)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.grid_container = QWidget(self)
        self.grid_container.setObjectName("content_container")
        self.flow_layout = FlowLayout(self.grid_container, margin=5, h_spacing=15, v_spacing=15)
        self.grid_container.setLayout(self.flow_layout)
        self.scroll_area.setWidget(self.grid_container)
        content_layout.addWidget(self.scroll_area)

        filter_scroll = QScrollArea(self)
        filter_scroll.setObjectName("filter_scroll")
        filter_scroll.setWidgetResizable(True)
        filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        filter_scroll.setWidget(sidebar)
        filter_scroll.setMinimumWidth(380)
        filter_scroll.setMaximumWidth(430)
        layout.addWidget(filter_scroll)
        layout.addWidget(content, 1)
        return tab

    def refresh_filter_options(self):
        first_photo_load = self.filter_photo_buttons.count() == 0
        first_rank_load = self.filter_rank_buttons.count() == 0
        first_squadron_load = self.filter_squadron_buttons.count() == 0
        first_section_load = self.filter_section_buttons.count() == 0
        rank_selection = self.filter_rank_buttons.selected_values()
        squadron_selection = self.filter_squadron_buttons.selected_values()
        rank_all = self.filter_rank_buttons.all_selected()
        squadron_all = self.filter_squadron_buttons.all_selected()
        photo_selection = self.filter_photo_buttons.selected_values()
        photo_all = self.filter_photo_buttons.all_selected()

        configured_ranks = self.config.get("postos_graduacoes", [])
        configured_squadrons = self.config.get("esquadroes", {}).keys()
        self.filter_photo_buttons.set_options(
            ["Com foto", "Sem foto"],
            photo_selection,
            all_mode=photo_all or first_photo_load,
        )
        self.filter_rank_buttons.set_options(
            configured_ranks,
            rank_selection,
            all_mode=rank_all or first_rank_load,
        )
        self.filter_squadron_buttons.set_options(
            configured_squadrons,
            squadron_selection,
            all_mode=squadron_all or first_squadron_load,
        )
        self._refresh_fraction_filters(force_all=first_section_load)
        unrecognized_count = sum(
            self._member_is_unrecognized(member) for member in self.members_data
        )
        self.filter_unrecognized_button.setText(
            f"Não reconhecidos ({unrecognized_count})"
        )
        self.filter_unrecognized_button.setEnabled(unrecognized_count > 0)
        if not unrecognized_count:
            self.filter_unrecognized_button.setChecked(False)
        self._update_filter_toggle_labels()

    def _on_rank_filters_changed(self):
        self.filter_unrecognized_button.setChecked(False)
        if (
            self.filter_rank_buttons.selected_values()
            and not self.filter_photo_buttons.selected_values()
        ):
            self.filter_photo_buttons.select_all(emit=False)
        if (
            self.filter_rank_buttons.selected_values()
            and not self.filter_squadron_buttons.selected_values()
        ):
            self.filter_squadron_buttons.select_all(emit=False)
            self._refresh_fraction_filters(force_all=True)
        self._update_filter_toggle_labels()
        self.populate_gallery()

    def _on_photo_filters_changed(self):
        self.filter_unrecognized_button.setChecked(False)
        self._update_filter_toggle_labels()
        self.populate_gallery()

    def _on_squadron_filters_changed(self):
        self.filter_unrecognized_button.setChecked(False)
        fractions_were_all = self.filter_section_buttons.all_selected()
        self._refresh_fraction_filters(force_all=fractions_were_all)
        self._update_filter_toggle_labels()
        self.populate_gallery()

    def _on_section_filters_changed(self):
        self.filter_unrecognized_button.setChecked(False)
        self._update_filter_toggle_labels()
        self.populate_gallery()

    def _on_unrecognized_filter_toggled(self, checked: bool):
        if checked:
            self.filter_photo_buttons.clear_selection(emit=False)
            self.filter_rank_buttons.clear_selection(emit=False)
            self.filter_squadron_buttons.clear_selection(emit=False)
            self.filter_section_buttons.clear_selection(emit=False)
            self._refresh_fraction_filters()
            self._update_filter_toggle_labels()
        self.populate_gallery()

    def _toggle_all_ranks(self):
        if self.filter_rank_buttons.all_selected():
            self.filter_rank_buttons.clear_selection()
        else:
            self.filter_rank_buttons.select_all()

    def _toggle_all_photo_status(self):
        if self.filter_photo_buttons.all_selected():
            self.filter_photo_buttons.clear_selection()
        else:
            self.filter_photo_buttons.select_all()

    def _toggle_all_squadrons(self):
        if self.filter_squadron_buttons.all_selected():
            self.filter_squadron_buttons.clear_selection()
        else:
            self.filter_squadron_buttons.select_all()

    def _toggle_all_sections(self):
        if self.filter_section_buttons.all_selected():
            self.filter_section_buttons.clear_selection()
        else:
            self.filter_section_buttons.select_all()

    def _refresh_fraction_filters(self, force_all: bool = False):
        selected_squadrons = self.filter_squadron_buttons.selected_values()
        previous = set(self.filter_section_buttons.selected_values())
        previous_squadrons = getattr(self, "_fraction_filter_squadrons", set())
        current_squadrons = set(selected_squadrons)
        newly_selected = current_squadrons - previous_squadrons
        structure = self.config.get("esquadroes", {})
        groups = {
            squadron: list(structure.get(squadron, []))
            for squadron in selected_squadrons
            if structure.get(squadron, [])
        }
        if not force_all:
            for squadron in newly_selected:
                previous.update(
                    (squadron, section)
                    for section in groups.get(squadron, [])
                )
        self.filter_section_buttons.set_groups(
            groups,
            previous,
            all_mode=force_all and any(groups.values()),
        )
        self._fraction_filter_squadrons = current_squadrons
        has_fractions = any(groups.values())
        self.filter_section_header.setVisible(has_fractions)
        self.filter_section_buttons.setVisible(bool(selected_squadrons))

    def _update_filter_toggle_labels(self):
        self._set_filter_toggle_label(
            self.btn_all_photo_status, self.filter_photo_buttons
        )
        self._set_filter_toggle_label(self.btn_all_ranks, self.filter_rank_buttons)
        self._set_filter_toggle_label(self.btn_all_squadrons, self.filter_squadron_buttons)
        self._set_filter_toggle_label(self.btn_all_sections, self.filter_section_buttons)

    def populate_gallery(self):
        if not hasattr(self, "flow_layout"):
            return
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        term = self.search_input.text().strip().casefold()
        ranks = set(self.filter_rank_buttons.selected_values())
        squadrons = set(self.filter_squadron_buttons.selected_values())
        sections = set(self.filter_section_buttons.selected_values())
        photo_statuses = set(self.filter_photo_buttons.selected_values())
        configured_structure = self.config.get("esquadroes", {})
        show_unrecognized = self.filter_unrecognized_button.isChecked()
        shown = 0
        for member in self.members_data:
            searchable = f"{member['posto_grad']} {member['nome_guerra']}".casefold()
            if term and term not in searchable:
                continue
            if show_unrecognized:
                if not self._member_is_unrecognized(member):
                    continue
            else:
                member_status = "Com foto" if member.get("photo_count", 0) else "Sem foto"
                if member_status not in photo_statuses:
                    continue
                if not ranks or member["posto_grad"] not in ranks:
                    continue
                if not squadrons or member["esquadrao"] not in squadrons:
                    continue
                configured_sections = configured_structure.get(member["esquadrao"], [])
                if member["fracao"] in configured_sections:
                    if (member["esquadrao"], member["fracao"]) not in sections:
                        continue
                elif configured_sections and not set(configured_sections).issubset(
                    {
                        section
                        for squadron, section in sections
                        if squadron == member["esquadrao"]
                    }
                ):
                    # Fração legada: aparece ao mostrar todas as frações do esquadrão,
                    # mas não contamina a lista de filtros nem o config.json.
                    continue

            thumb_path = self.image_processor.get_cached_thumbnail(
                self.root_directory, member["absolute_path"]
            )
            card = PhotoCard(
                member,
                thumb_path,
                self.config,
                self,
            )
            card.requestMove.connect(self.handle_member_move)
            card.requestEdit.connect(self.handle_member_edit)
            card.requestGallery.connect(self.open_member_gallery)
            card.requestAddPhotos.connect(self.handle_card_add_photos)
            card.requestDelete.connect(self.handle_member_delete)
            card.requestPhotoUpdate.connect(self.handle_photo_update_recommended)
            self.flow_layout.addWidget(card)
            if member["absolute_path"] and not thumb_path:
                self._queue_thumbnail(member["absolute_path"], 150, card)
            shown += 1
        self.lbl_section.setText(f"Militares ({shown})")

    def _member_is_unrecognized(self, member: dict) -> bool:
        ranks = self.config.get("postos_graduacoes", [])
        structure = self.config.get("esquadroes", {})
        squadron = member["esquadrao"]
        if member["posto_grad"] not in ranks or squadron not in structure:
            return True
        return bool(member["fracao"] and member["fracao"] not in structure[squadron])

    def handle_member_move(self, current_path: str, squadron: str, section: str):
        try:
            self._invalidate_member_thumbnails(current_path)
            self.file_manager.move_member(current_path, squadron, section)
            self.reload_data()
        except Exception as exc:
            self._show_error("Erro ao mover arquivo", exc)
            self.reload_data()

    def handle_member_edit(
        self,
        current_path: str,
        rank: str,
        name: str,
        squadron: str,
        section: str,
    ):
        try:
            self._invalidate_member_thumbnails(current_path)
            self.file_manager.update_member(
                current_path, rank, name, squadron, section
            )
            self.reload_data()
        except Exception as exc:
            self._show_error("Erro ao editar cadastro", exc)
            self.reload_data()

    def handle_photo_update_recommended(self, member: dict, recommended: bool):
        try:
            self.file_manager.set_photo_update_recommended(
                member["member_path"], recommended
            )
            self.reload_data()
        except Exception as exc:
            self._show_error("Erro ao atualizar situação da foto", exc)
            self.reload_data()

    def open_member_gallery(self, member: dict):
        thumbnail_paths = {
            photo: self.image_processor.get_cached_thumbnail(
                self.root_directory, photo, 210
            )
            for photo in member["photos"]
        }
        dialog = MemberGalleryDialog(member, thumbnail_paths, self)
        self._queue_gallery_thumbnails(dialog)
        dialog.requestAdd.connect(self.handle_gallery_add)
        dialog.requestPrimary.connect(self.handle_set_primary)
        dialog.requestRotate.connect(self.handle_rotate_gallery_photo)
        dialog.requestExport.connect(self.handle_export_photos)
        dialog.requestDelete.connect(self.handle_delete_photos)
        dialog.exec()

    def handle_card_add_photos(self, member: dict, paths: list[str]):
        valid_paths = [
            path
            for path in paths
            if os.path.isfile(path)
            and Path(path).suffix.lower() in FileManager.VALID_EXTENSIONS
        ]
        if not valid_paths:
            QMessageBox.warning(self, "Imagem inválida", "Nenhuma imagem suportada foi solta.")
            return
        try:
            member_path = member["member_path"]
            if member.get("is_legacy"):
                self.image_processor.invalidate_thumbnail(
                    self.root_directory, member["absolute_path"]
                )
                member_path = self.file_manager.convert_legacy_member(member_path)
            self.file_manager.add_photos(member_path, valid_paths)
            self.reload_data()
        except Exception as exc:
            self._show_error("Erro ao adicionar fotos", exc)
            self.reload_data()

    def _build_reports_tab(self) -> QWidget:
        self.report_dashboard = ReportDashboard(self)
        self.report_dashboard.requestOpenMember.connect(self.open_member_gallery)
        self.report_dashboard.requestAddPhoto.connect(self.handle_report_add_photo)
        self.report_dashboard.requestDeleteMember.connect(
            self.handle_member_delete
        )
        self.report_dashboard.requestExport.connect(self.export_reports)
        return self.report_dashboard

    def handle_report_add_photo(self, member: dict):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar fotos", "", FileManager.image_dialog_filter()
        )
        if paths:
            self.handle_card_add_photos(member, paths)

    def handle_member_delete(self, member: dict):
        photo_count = member.get("photo_count", 0)
        identity = f"{member['posto_grad']} {member['nome_guerra']}"
        if photo_count == 1:
            details = (
                f"O cadastro de {identity} e sua foto serão excluídos "
                "permanentemente."
            )
        elif photo_count > 1:
            details = (
                f"O cadastro de {identity} e suas {photo_count} fotos serão "
                "excluídos permanentemente."
            )
        else:
            details = f"O cadastro sem foto de {identity} será excluído permanentemente."
        answer = QMessageBox.question(
            self,
            "Confirmar exclusão",
            f"{details}\n\nEsta ação não pode ser desfeita. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            for photo in member.get("photos", []):
                self.image_processor.invalidate_thumbnail(
                    self.root_directory, photo
                )
            self.file_manager.delete_member(member["member_path"])
            self.reload_data()
            QMessageBox.information(
                self,
                "Cadastro excluído",
                f"O cadastro de {identity} foi excluído.",
            )
        except Exception as exc:
            self._show_error("Erro ao excluir cadastro", exc)
            self.reload_data()

    def export_reports(self, context: dict):
        suggested_filename = ReportService.export_filename(context)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar visualização do relatório",
            suggested_filename,
            "Relatórios CSV (*.csv)",
        )
        if not path:
            return
        try:
            written = ReportService.export_view(
                path, self.members_data, self.config, context
            )
            QMessageBox.information(
                self,
                "Relatório exportado",
                f"A visualização atual foi salva em:\n{written}",
            )
        except Exception as exc:
            self._show_error("Erro ao exportar relatório", exc)

    def handle_gallery_add(self, member: dict):
        dialog = self.sender()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Adicionar fotos", "", FileManager.image_dialog_filter()
        )
        if not paths:
            return
        member_path = member["member_path"]
        try:
            if member.get("is_legacy"):
                answer = QMessageBox.question(
                    self,
                    "Converter cadastro antigo",
                    "Para adicionar novas fotos, o cadastro antigo será movido para "
                    "uma pasta individual. Deseja continuar?",
                )
                if answer != QMessageBox.Yes:
                    return
                self.image_processor.invalidate_thumbnail(
                    self.root_directory, member["absolute_path"]
                )
                member_path = self.file_manager.convert_legacy_member(member_path)
            elif not os.path.isdir(member_path):
                # Permite adicionar novamente após excluir todas as fotos sem
                # precisar fechar e reabrir a galeria.
                os.makedirs(member_path, exist_ok=True)
            destinations = self.file_manager.add_photos(member_path, paths)
            self.reload_data()
            self._refresh_gallery_dialog(dialog, member_path)
            QMessageBox.information(
                self,
                "Fotos adicionadas",
                f"{len(destinations)} foto(s) adicionada(s) à galeria.",
            )
        except Exception as exc:
            self._show_error("Erro ao adicionar fotos", exc)
            self.reload_data()

    def handle_set_primary(self, member: dict, photo_path: str):
        dialog = self.sender()
        try:
            for photo in member["photos"]:
                self.image_processor.invalidate_thumbnail(self.root_directory, photo)
            self.file_manager.set_primary_photo(member["member_path"], photo_path)
            self.reload_data()
            self._refresh_gallery_dialog(dialog, member["member_path"])
        except Exception as exc:
            self._show_error("Erro ao definir foto principal", exc)
            self.reload_data()

    def handle_rotate_gallery_photo(
        self, member: dict, photo_path: str, degrees: int
    ):
        dialog = self.sender()
        try:
            self.image_processor.invalidate_thumbnail(self.root_directory, photo_path)
            self.image_processor.rotate_image_file(photo_path, degrees)
            self.reload_data()
            self._refresh_gallery_dialog(dialog, member["member_path"])
        except Exception as exc:
            self._show_error("Erro ao girar imagem", exc)
            self.reload_data()

    def handle_export_photos(self, photo_paths: list[str]):
        if not photo_paths:
            return
        try:
            if len(photo_paths) == 1:
                photo_path = photo_paths[0]
                destination, _ = QFileDialog.getSaveFileName(
                    self,
                    "Exportar cópia da foto",
                    os.path.basename(photo_path),
                    FileManager.image_dialog_filter(include_all=True),
                )
                if not destination:
                    return
                if not Path(destination).suffix:
                    destination += Path(photo_path).suffix
                if os.path.abspath(destination) == os.path.abspath(photo_path):
                    raise ValueError("Escolha um destino diferente do arquivo original.")
                shutil.copy2(photo_path, destination)
                exported = 1
            else:
                directory = QFileDialog.getExistingDirectory(
                    self, "Selecionar pasta para exportar as cópias"
                )
                if not directory:
                    return
                destinations = [
                    os.path.join(directory, os.path.basename(photo))
                    for photo in photo_paths
                ]
                if any(
                    os.path.abspath(source) == os.path.abspath(destination)
                    for source, destination in zip(photo_paths, destinations)
                ):
                    raise ValueError("Escolha uma pasta diferente da pasta das fotos originais.")
                existing = [path for path in destinations if os.path.exists(path)]
                if existing:
                    answer = QMessageBox.question(
                        self,
                        "Substituir arquivos existentes",
                        f"{len(existing)} arquivo(s) já existe(m) no destino. "
                        "Deseja substituí-lo(s)?",
                    )
                    if answer != QMessageBox.Yes:
                        return
                for source, destination in zip(photo_paths, destinations):
                    shutil.copy2(source, destination)
                exported = len(photo_paths)
            QMessageBox.information(
                self,
                "Cópia exportada" if exported == 1 else "Cópias exportadas",
                "A imagem foi copiada para o destino escolhido."
                if exported == 1
                else f"{exported} imagens foram copiadas para o destino escolhido.",
            )
        except Exception as exc:
            self._show_error("Erro ao exportar imagens", exc)

    def handle_delete_photos(self, member: dict, photo_paths: list[str]):
        dialog = self.sender()
        count = len(photo_paths)
        if not count:
            return
        deleting_all = count == member.get("photo_count", len(member["photos"]))
        message = (
            f"Excluir permanentemente {count} imagem?"
            if count == 1
            else f"Excluir permanentemente {count} imagens?"
        )
        message += "\n\nEsta ação não pode ser desfeita."
        if deleting_all:
            message += (
                "\nComo todas as fotos foram selecionadas, o cadastro deixará "
                "de aparecer na galeria."
            )
        answer = QMessageBox.question(
            self,
            "Confirmar exclusão",
            message,
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            for photo in member["photos"]:
                self.image_processor.invalidate_thumbnail(self.root_directory, photo)
            self.file_manager.delete_photos(member["member_path"], photo_paths)
            self.reload_data()
            self._refresh_gallery_dialog(
                dialog, member["member_path"], empty_member=member
            )
            QMessageBox.information(
                self,
                "Imagem excluída" if count == 1 else "Imagens excluídas",
                "A imagem foi excluída."
                if count == 1
                else f"{count} imagens foram excluídas.",
            )
        except Exception as exc:
            self._show_error("Erro ao excluir imagens", exc)
            self.reload_data()

    def _refresh_gallery_dialog(
        self,
        dialog,
        member_path: str,
        empty_member: dict | None = None,
    ):
        if not isinstance(dialog, MemberGalleryDialog):
            return
        normalized_path = os.path.abspath(member_path)
        updated_member = next(
            (
                item for item in self.members_data
                if os.path.abspath(item["member_path"]) == normalized_path
            ),
            None,
        )
        if updated_member:
            thumbnail_paths = {
                photo: self.image_processor.get_cached_thumbnail(
                    self.root_directory, photo, 210
                )
                for photo in updated_member["photos"]
            }
            dialog.refresh_member(updated_member, thumbnail_paths)
            self._queue_gallery_thumbnails(dialog)
        elif empty_member is not None:
            empty = dict(empty_member)
            empty.update(
                {
                    "absolute_path": "",
                    "filename": "",
                    "member_path": member_path,
                    "photos": [],
                    "photo_count": 0,
                    "is_legacy": False,
                }
            )
            dialog.refresh_member(empty, {})

    def _invalidate_member_thumbnails(self, member_path: str):
        member_path = os.path.abspath(member_path)
        for member in self.members_data:
            if os.path.abspath(member["member_path"]) == member_path:
                for photo in member["photos"]:
                    self.image_processor.invalidate_thumbnail(self.root_directory, photo)
                return

    def _queue_gallery_thumbnails(self, dialog: MemberGalleryDialog):
        for photo, card in dialog.photo_cards.items():
            if not self.image_processor.get_cached_thumbnail(
                self.root_directory, photo, 210
            ):
                self._queue_thumbnail(photo, 210, card)

    def _queue_thumbnail(self, photo_path: str, size: int, target: QWidget):
        cached = self.image_processor.get_cached_thumbnail(
            self.root_directory, photo_path, size
        )
        if cached:
            target.set_thumbnail(photo_path, cached)
            return

        key = (
            os.path.realpath(self.root_directory),
            os.path.realpath(photo_path),
            size,
        )
        self._thumbnail_targets.setdefault(key, []).append(weakref.ref(target))
        if key in self._thumbnail_jobs:
            return
        worker = ThumbnailWorker(
            key, self.root_directory, photo_path, size
        )
        self._thumbnail_jobs[key] = worker
        worker.signals.finished.connect(self._thumbnail_finished)
        self.thumbnail_pool.start(worker)

    def _thumbnail_finished(self, key, photo_path: str, thumbnail_path: str):
        self._thumbnail_jobs.pop(key, None)
        targets = self._thumbnail_targets.pop(key, [])
        for target_ref in targets:
            target = target_ref()
            if target is None:
                continue
            try:
                target.set_thumbnail(photo_path, thumbnail_path)
            except RuntimeError:
                # O card pode ter sido destruído por uma troca rápida de filtro.
                pass

    # --------------------------------------------------------------- Configurações
    def _build_settings_tab(self) -> QWidget:
        tab = QWidget(self)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(20, 20, 20, 20)
        reorder_hint = QLabel(
            "Arraste os itens para reorganizar. A ordem será usada nos botões do cadastro.",
            self,
        )
        reorder_hint.setObjectName("settings_hint")
        outer.addWidget(reorder_hint)
        splitter = QSplitter(Qt.Horizontal, self)

        ranks_group = QGroupBox("Postos / Graduações", self)
        ranks_layout = QVBoxLayout(ranks_group)
        self.config_ranks_list = QListWidget(self)
        self._enable_list_reordering(self.config_ranks_list)
        self.config_rank_input = QLineEdit(self)
        self.config_rank_input.setPlaceholderText("Novo posto ou graduação")
        self.config_rank_abbreviation_input = QLineEdit(self)
        self.config_rank_abbreviation_input.setPlaceholderText(
            "Abreviação opcional (ex.: Sd EV)"
        )
        add_rank = QPushButton("Adicionar", self)
        edit_rank = QPushButton("Editar selecionado", self)
        remove_rank = QPushButton("Remover selecionado", self)
        add_rank.clicked.connect(self.add_config_rank)
        edit_rank.clicked.connect(
            lambda: self.edit_config_entry(self.config_ranks_list, "posto ou graduação")
        )
        remove_rank.clicked.connect(lambda: self._remove_selected(self.config_ranks_list))
        ranks_layout.addWidget(self.config_ranks_list)
        ranks_layout.addWidget(self.config_rank_input)
        ranks_layout.addWidget(self.config_rank_abbreviation_input)
        ranks_layout.addWidget(add_rank)
        ranks_layout.addWidget(edit_rank)
        ranks_layout.addWidget(remove_rank)

        squadrons_group = QGroupBox("Esquadrões", self)
        squadrons_layout = QVBoxLayout(squadrons_group)
        self.config_squadrons_list = QListWidget(self)
        self._enable_list_reordering(self.config_squadrons_list)
        self.config_squadron_input = QLineEdit(self)
        self.config_squadron_input.setPlaceholderText("Novo esquadrão")
        self.config_squadron_abbreviation_input = QLineEdit(self)
        self.config_squadron_abbreviation_input.setPlaceholderText(
            "Abreviação opcional (ex.: EM)"
        )
        add_squadron = QPushButton("Adicionar", self)
        edit_squadron = QPushButton("Editar selecionado", self)
        remove_squadron = QPushButton("Remover selecionado", self)
        add_squadron.clicked.connect(self.add_config_squadron)
        edit_squadron.clicked.connect(
            lambda: self.edit_config_entry(self.config_squadrons_list, "esquadrão")
        )
        remove_squadron.clicked.connect(self.remove_config_squadron)
        self.config_squadrons_list.currentItemChanged.connect(self.show_config_sections)
        squadrons_layout.addWidget(self.config_squadrons_list)
        squadrons_layout.addWidget(self.config_squadron_input)
        squadrons_layout.addWidget(self.config_squadron_abbreviation_input)
        squadrons_layout.addWidget(add_squadron)
        squadrons_layout.addWidget(edit_squadron)
        squadrons_layout.addWidget(remove_squadron)

        sections_group = QGroupBox("Frações do esquadrão", self)
        sections_layout = QVBoxLayout(sections_group)
        self.config_sections_list = QListWidget(self)
        self._enable_list_reordering(self.config_sections_list)
        self.config_section_input = QLineEdit(self)
        self.config_section_input.setPlaceholderText("Nova fração do esquadrão selecionado")
        self.config_section_abbreviation_input = QLineEdit(self)
        self.config_section_abbreviation_input.setPlaceholderText(
            "Abreviação opcional (ex.: 1º Pel)"
        )
        add_section = QPushButton("Adicionar", self)
        edit_section = QPushButton("Editar selecionada", self)
        remove_section = QPushButton("Remover selecionada", self)
        add_section.clicked.connect(self.add_config_section)
        edit_section.clicked.connect(
            lambda: self.edit_config_entry(self.config_sections_list, "fração")
        )
        remove_section.clicked.connect(lambda: self._remove_selected(self.config_sections_list))
        sections_layout.addWidget(self.config_sections_list)
        sections_layout.addWidget(self.config_section_input)
        sections_layout.addWidget(self.config_section_abbreviation_input)
        sections_layout.addWidget(add_section)
        sections_layout.addWidget(edit_section)
        sections_layout.addWidget(remove_section)

        splitter.addWidget(ranks_group)
        splitter.addWidget(squadrons_group)
        splitter.addWidget(sections_group)
        splitter.setSizes([300, 300, 360])
        outer.addWidget(splitter, 1)
        save_button = QPushButton("Salvar Estrutura", self)
        save_button.setObjectName("primary_btn")
        save_button.clicked.connect(self.save_structure)
        outer.addWidget(save_button, 0, Qt.AlignRight)
        return tab

    def populate_settings(self):
        self._editing_squadron = ""
        self.config_ranks_list.clear()
        abbreviations = self.config.get("abreviacoes", {})
        rank_abbreviations = abbreviations.get("postos_graduacoes", {})
        for rank in self.config.get("postos_graduacoes", []):
            self._add_config_item(
                self.config_ranks_list, rank, rank_abbreviations.get(rank, rank)
            )
        self.config_squadrons_list.clear()
        squadron_abbreviations = abbreviations.get("esquadroes", {})
        for squadron in self.config.get("esquadroes", {}):
            self._add_config_item(
                self.config_squadrons_list,
                squadron,
                squadron_abbreviations.get(squadron, squadron),
            )
        if self.config_squadrons_list.count():
            self.config_squadrons_list.setCurrentRow(0)
        else:
            self.config_sections_list.clear()

    def show_config_sections(self, current: QListWidgetItem | None, previous=None):
        # Antes de trocar, as alterações da lista anterior já são registradas no rascunho.
        self._store_visible_sections()
        squadron = self._config_item_name(current) if current else ""
        self._editing_squadron = squadron
        self.config_sections_list.clear()
        section_abbreviations = (
            self.config.get("abreviacoes", {}).get("fracoes", {}).get(squadron, {})
        )
        for section in self.config.get("esquadroes", {}).get(squadron, []):
            self._add_config_item(
                self.config_sections_list,
                section,
                section_abbreviations.get(section, section),
            )

    def add_config_rank(self):
        self._add_named_entry(
            self.config_ranks_list,
            self.config_rank_input,
            self.config_rank_abbreviation_input,
            "posto ou graduação",
        )

    def add_config_squadron(self):
        name = self.config_squadron_input.text().strip()
        abbreviation = self.config_squadron_abbreviation_input.text().strip() or name
        if not self._validate_named_entry(
            self.config_squadrons_list, name, abbreviation, "esquadrão"
        ):
            return
        self._store_visible_sections()
        self.config["esquadroes"][name] = []
        abbreviations = self.config.setdefault("abreviacoes", {})
        abbreviations.setdefault("esquadroes", {})[name] = abbreviation
        abbreviations.setdefault("fracoes", {})[name] = {}
        self._add_config_item(self.config_squadrons_list, name, abbreviation)
        self.config_squadrons_list.setCurrentRow(self.config_squadrons_list.count() - 1)
        self.config_squadron_input.clear()
        self.config_squadron_abbreviation_input.clear()

    def remove_config_squadron(self):
        item = self.config_squadrons_list.currentItem()
        if not item:
            return
        name = self._config_item_name(item)
        answer = QMessageBox.question(
            self,
            "Remover esquadrão",
            f"Remover '{name}' da configuração? As fotos no disco não serão apagadas.",
        )
        if answer != QMessageBox.Yes:
            return
        self.config["esquadroes"].pop(name, None)
        abbreviations = self.config.get("abreviacoes", {})
        abbreviations.get("esquadroes", {}).pop(name, None)
        abbreviations.get("fracoes", {}).pop(name, None)
        row = self.config_squadrons_list.row(item)
        self.config_squadrons_list.takeItem(row)

    def add_config_section(self):
        if not self.config_squadrons_list.currentItem():
            QMessageBox.warning(self, "Esquadrão obrigatório", "Selecione ou crie um esquadrão.")
            return
        self._add_named_entry(
            self.config_sections_list,
            self.config_section_input,
            self.config_section_abbreviation_input,
            "fração ou setor",
        )

    def edit_config_entry(self, widget: QListWidget, label: str):
        item = widget.currentItem()
        if not item:
            QMessageBox.warning(self, "Seleção obrigatória", f"Selecione um {label}.")
            return
        data = item.data(Qt.UserRole)
        old_name = data.get("nome", item.text()) if isinstance(data, dict) else item.text()
        old_abbreviation = data.get("abreviacao", old_name) if isinstance(data, dict) else old_name

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Editar {label}")
        dialog.setMinimumWidth(360)
        form = QFormLayout(dialog)
        name_input = QLineEdit(old_name, dialog)
        abbreviation_input = QLineEdit(old_abbreviation, dialog)
        form.addRow("Nome completo:", name_input)
        form.addRow("Abreviação:", abbreviation_input)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return

        new_name = name_input.text().strip()
        new_abbreviation = abbreviation_input.text().strip() or new_name
        if not new_name:
            QMessageBox.warning(
                self, "Dados incompletos", "Informe o nome completo."
            )
            return
        for row in range(widget.count()):
            other = widget.item(row)
            if other is not item and self._config_item_name(other).casefold() == new_name.casefold():
                QMessageBox.warning(self, "Item duplicado", f"'{new_name}' já está cadastrado.")
                return

        if widget is self.config_squadrons_list:
            self._store_visible_sections()
            sections = self.config["esquadroes"].pop(old_name, [])
            abbreviations = self.config.setdefault("abreviacoes", {})
            abbreviations.setdefault("esquadroes", {}).pop(old_name, None)
            section_abbreviations = abbreviations.setdefault("fracoes", {}).pop(old_name, {})
            self.config["esquadroes"][new_name] = sections
            abbreviations["esquadroes"][new_name] = new_abbreviation
            abbreviations["fracoes"][new_name] = section_abbreviations
            self._editing_squadron = new_name

        item.setText(f"{new_name}  —  {new_abbreviation}")
        item.setData(Qt.UserRole, {"nome": new_name, "abreviacao": new_abbreviation})
        item.setToolTip(f"Nome completo: {new_name}\nAbreviação: {new_abbreviation}")

    def save_structure(self):
        self._store_visible_sections()
        rank_entries = self._config_list_entries(self.config_ranks_list)
        squadron_entries = self._config_list_entries(self.config_squadrons_list)
        draft = {
            "postos_graduacoes": [entry["nome"] for entry in rank_entries],
            "esquadroes": {
                entry["nome"]: self.config["esquadroes"].get(entry["nome"], [])
                for entry in squadron_entries
            },
            "abreviacoes": {
                "postos_graduacoes": {
                    entry["nome"]: entry["abreviacao"] for entry in rank_entries
                },
                "esquadroes": {
                    entry["nome"]: entry["abreviacao"] for entry in squadron_entries
                },
                "fracoes": {
                    entry["nome"]: self.config.get("abreviacoes", {})
                    .get("fracoes", {})
                    .get(entry["nome"], {})
                    for entry in squadron_entries
                },
            },
        }
        try:
            self.config = self.file_manager.save_config(draft)
        except Exception as exc:
            self._show_error("Erro ao salvar configuração", exc)
            return
        self.refresh_config_dependent_ui()
        self.refresh_filter_options()
        self.populate_gallery()
        self.report_dashboard.refresh(self.members_data, self.config)
        QMessageBox.information(self, "Estrutura salva", "O config.json foi atualizado.")

    def _store_visible_sections(self):
        squadron = getattr(self, "_editing_squadron", "")
        if squadron in self.config.get("esquadroes", {}):
            entries = self._config_list_entries(self.config_sections_list)
            self.config["esquadroes"][squadron] = [entry["nome"] for entry in entries]
            self.config.setdefault("abreviacoes", {}).setdefault("fracoes", {})[
                squadron
            ] = {entry["nome"]: entry["abreviacao"] for entry in entries}

    # ----------------------------------------------------------------- Ciclo geral
    def select_root_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Selecionar Diretório de Fotos")
        if not directory:
            return
        self.activate_root_directory(directory, show_errors=True)

    def activate_root_directory(self, directory: str, show_errors: bool = True) -> bool:
        """Ativa uma raiz manualmente ou restaurada das preferências da aplicação."""
        try:
            config = self.file_manager.set_root_path(directory)
        except Exception as exc:
            if show_errors:
                self._show_error("Pasta raiz inválida", exc)
            else:
                self.lbl_dir_status.setText("A última pasta não pôde ser reaberta.")
            return False
        self.root_directory = directory
        self.config = config
        self.lbl_dir_status.setText(directory)
        self.tabs.setEnabled(True)
        self.populate_settings()
        self.refresh_config_dependent_ui()
        self.reload_data()
        settings = QSettings()
        settings.setValue("last_root_directory", directory)
        settings.sync()
        return True

    def restore_last_root_directory(self):
        settings = QSettings()
        directory = str(settings.value("last_root_directory", "") or "")
        if not directory:
            legacy_settings = QSettings("ComSoc", LEGACY_SETTINGS_APPLICATION)
            directory = str(
                legacy_settings.value("last_root_directory", "") or ""
            )
            if directory:
                settings.setValue("last_root_directory", directory)
                settings.sync()
        if directory and os.path.isdir(directory):
            self.activate_root_directory(directory, show_errors=False)
        elif directory:
            settings.remove("last_root_directory")
            settings.sync()
            self.lbl_dir_status.setText("A última pasta não existe mais. Selecione outra pasta.")

    def reload_data(self):
        if not self.root_directory:
            return
        self.members_data = self.file_manager.scan_directory()
        self.refresh_filter_options()
        self.populate_gallery()
        self.report_dashboard.refresh(self.members_data, self.config)

    def refresh_config_dependent_ui(self):
        self.import_rank_buttons.set_options(
            self.config.get("postos_graduacoes", []),
            self.import_rank_buttons.currentText(),
        )
        self.import_squadron_buttons.set_options(
            self.config.get("esquadroes", {}).keys(),
            self.import_squadron_buttons.currentText(),
        )
        self.update_import_sections(self.import_squadron_buttons.currentText())

    @staticmethod
    def _title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("section_title")
        return label

    @staticmethod
    def _form_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("form_label")
        return label

    @staticmethod
    def _filter_toggle_button() -> QPushButton:
        button = QPushButton("Mostrar todos")
        button.setObjectName("filter_toggle_button")
        return button

    @staticmethod
    def _filter_header(text: str, button: QPushButton) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 0)
        label = QLabel(text)
        label.setObjectName("filter_group_label")
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(button)
        return layout

    @staticmethod
    def _set_filter_toggle_label(button: QPushButton, grid: FilterButtonGrid) -> None:
        button.setText("Ocultar todos" if grid.all_selected() else "Mostrar todos")
        button.setEnabled(grid.count() > 0)

    def _rank_button_label(self, rank: str) -> str:
        return (
            self.config.get("abreviacoes", {})
            .get("postos_graduacoes", {})
            .get(rank, rank)
        )

    def _squadron_button_label(self, squadron: str) -> str:
        return (
            self.config.get("abreviacoes", {}).get("esquadroes", {}).get(squadron, squadron)
        )

    def _section_button_label(self, section: str) -> str:
        squadron = self.import_squadron_buttons.currentText()
        return (
            self.config.get("abreviacoes", {})
            .get("fracoes", {})
            .get(squadron, {})
            .get(section, section)
        )

    def _filter_section_button_label(self, squadron: str, section: str) -> str:
        abbreviations = self.config.get("abreviacoes", {}).get("fracoes", {})
        return abbreviations.get(squadron, {}).get(section, section) or section

    @staticmethod
    def _add_config_item(widget: QListWidget, name: str, abbreviation: str) -> None:
        item = QListWidgetItem(f"{name}  —  {abbreviation}", widget)
        item.setData(Qt.UserRole, {"nome": name, "abreviacao": abbreviation})
        item.setToolTip(f"Nome completo: {name}\nAbreviação: {abbreviation}")

    @staticmethod
    def _enable_list_reordering(widget: QListWidget) -> None:
        widget.setDragEnabled(True)
        widget.setAcceptDrops(True)
        widget.setDropIndicatorShown(True)
        widget.setDragDropMode(QAbstractItemView.InternalMove)
        widget.setDefaultDropAction(Qt.MoveAction)

    @staticmethod
    def _config_item_name(item: QListWidgetItem | None) -> str:
        if not item:
            return ""
        data = item.data(Qt.UserRole)
        return data.get("nome", "") if isinstance(data, dict) else item.text()

    @staticmethod
    def _config_list_entries(widget: QListWidget) -> list[dict[str, str]]:
        entries = []
        for row in range(widget.count()):
            item = widget.item(row)
            data = item.data(Qt.UserRole)
            if isinstance(data, dict):
                entries.append(
                    {"nome": str(data["nome"]), "abreviacao": str(data["abreviacao"])}
                )
            else:
                entries.append({"nome": item.text(), "abreviacao": item.text()})
        return entries

    @staticmethod
    def _list_contains(widget: QListWidget, text: str) -> bool:
        folded = text.casefold()
        return any(
            MainWindow._config_item_name(widget.item(row)).casefold() == folded
            for row in range(widget.count())
        )

    def _validate_named_entry(
        self, widget: QListWidget, name: str, abbreviation: str, label: str
    ) -> bool:
        if not name:
            QMessageBox.warning(
                self,
                "Dados incompletos",
                f"Informe o nome completo do {label}.",
            )
            return False
        if self._list_contains(widget, name):
            QMessageBox.warning(self, "Item duplicado", f"'{name}' já está cadastrado.")
            return False
        return True

    def _add_named_entry(
        self,
        widget: QListWidget,
        name_input: QLineEdit,
        abbreviation_input: QLineEdit,
        label: str,
    ) -> None:
        name = name_input.text().strip()
        abbreviation = abbreviation_input.text().strip() or name
        if not self._validate_named_entry(widget, name, abbreviation, label):
            return
        self._add_config_item(widget, name, abbreviation)
        name_input.clear()
        abbreviation_input.clear()

    @staticmethod
    def _remove_selected(widget: QListWidget):
        for item in widget.selectedItems():
            widget.takeItem(widget.row(item))

    def _show_error(self, title: str, error: Exception):
        QMessageBox.critical(self, title, f"{error}")
