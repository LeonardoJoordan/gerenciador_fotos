# Cores e estilizações baseadas em um visual Dark/Moderno limpo
STYLE_SHEET = """
QMainWindow {
    background-color: #121212;
}

QWidget {
    color: #e5e7eb;
    font-size: 13px;
}

QWidget#content_container, QWidget#gallery_container,
QDialog#member_gallery_dialog {
    background-color: #121212;
}

QTabWidget::pane {
    border: 1px solid #2d2d2d;
    background-color: #121212;
}

QTabBar::tab {
    background-color: #1e1e1e;
    color: #aeb4be;
    border: 1px solid #2d2d2d;
    padding: 10px 18px;
    min-width: 145px;
}

QTabBar::tab:selected {
    color: #ffffff;
    background-color: #252525;
    border-bottom: 2px solid #3a86ff;
}

/* Painel Lateral de Filtros */
QFrame#sidebar {
    background-color: #1e1e1e;
    border-right: 1px solid #2d2d2d;
    min-width: 350px;
    max-width: 410px;
}

QScrollArea#filter_scroll {
    background-color: #1e1e1e;
    border-right: 1px solid #2d2d2d;
}

/* Área Principal de Exibição */
QFrame#main_content {
    background-color: #121212;
}

QFrame#form_panel, QGroupBox {
    background-color: #1e1e1e;
    border: 1px solid #2d2d2d;
    border-radius: 7px;
}

QGroupBox {
    margin-top: 10px;
    padding-top: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QFrame#drop_area {
    background-color: #1e1e1e;
    border: 2px dashed #4b5563;
    border-radius: 8px;
}

QFrame#drop_area:hover {
    border-color: #3a86ff;
    background-color: #202837;
}

QLabel#import_preview {
    background-color: #0d0d0d;
    color: #777777;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
}

QLabel#directory_status {
    color: #9ca3af;
    padding-left: 8px;
}

QLabel#settings_hint {
    color: #9ca3af;
    background-color: #1b2330;
    border: 1px solid #30415a;
    border-radius: 5px;
    padding: 8px 10px;
}

/* Títulos */
QLabel#section_title {
    color: #ffffff;
    font-size: 16px;
    font-weight: bold;
    margin-bottom: 10px;
}

QLabel#sidebar_title {
    color: #e0e0e0;
    font-size: 14px;
    font-weight: bold;
    padding: 5px;
}

QLabel#card_name {
    color: #ffffff;
    font-weight: bold;
    font-size: 12px;
}

QLabel#photo_count_label, QLabel#photo_filename_label {
    color: #9ca3af;
    font-size: 11px;
}

QLabel#primary_photo_label {
    color: #79b0ff;
    font-size: 11px;
    font-weight: bold;
}

QLabel#form_label {
    color: #d5d9e0;
    font-size: 12px;
    font-weight: bold;
    margin-top: 4px;
}

QLabel#filter_group_label {
    color: #e5e7eb;
    font-size: 12px;
    font-weight: bold;
}

QLabel#fraction_group_label {
    color: #78a9ff;
    font-size: 10px;
    padding: 0 5px;
}

QFrame#fraction_group_line {
    color: #343a43;
}

QLabel#filter_empty_label {
    color: #737b86;
    padding: 7px;
}

QLabel#selection_empty_label {
    color: #7f8792;
    background-color: #191919;
    border: 1px dashed #3b3b3b;
    border-radius: 4px;
    padding: 9px;
}

/* Inputs de Texto e Busca */
QLineEdit {
    background-color: #2d2d2d;
    color: #ffffff;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 13px;
}

QLineEdit:focus {
    border: 1px solid #3a86ff;
}

/* Botões */
QPushButton {
    background-color: #2d2d2d;
    color: #ffffff;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #3d3d3d;
}

QPushButton:pressed {
    background-color: #1e1e1e;
}

/* Botão de Destaque (Ações primárias como Importar) */
QPushButton#primary_btn {
    background-color: #3a86ff;
    color: #ffffff;
    border: none;
}

QPushButton#primary_btn:hover {
    background-color: #4895ef;
}

QPushButton#primary_btn:pressed {
    background-color: #2a75e6;
}

QPushButton#card_edit_btn {
    padding: 5px 8px;
    font-size: 11px;
    font-weight: normal;
}

QPushButton#gallery_action_btn {
    padding: 6px 3px;
    font-size: 11px;
}

QPushButton#gallery_action_btn:disabled {
    background-color: #3a3a3a;
    color: #858b94;
    border: 1px solid #4a4a4a;
}

QPushButton#rotate_image_btn {
    padding: 2px;
    font-size: 18px;
    font-weight: bold;
}

QPushButton#selection_button {
    background-color: #292929;
    border: 1px solid #404040;
    padding: 7px 5px;
    min-width: 68px;
    font-size: 12px;
}

QPushButton#selection_button:hover {
    background-color: #363d49;
    border-color: #57708f;
}

QPushButton#selection_button:checked {
    background-color: #3a86ff;
    color: #ffffff;
    border: 1px solid #6ca5ff;
}

QPushButton#filter_button {
    background-color: #292929;
    border: 1px solid #404040;
    padding: 6px 4px;
    min-width: 66px;
    font-size: 11px;
}

QPushButton#filter_button:hover {
    background-color: #363d49;
    border-color: #57708f;
}

QPushButton#filter_button:checked {
    background-color: #3a86ff;
    color: #ffffff;
    border-color: #6ca5ff;
}

QPushButton#filter_toggle_button {
    background-color: transparent;
    color: #78a9ff;
    border: none;
    padding: 3px 4px;
    font-size: 10px;
    font-weight: normal;
}

QPushButton#filter_toggle_button:hover {
    color: #a9c8ff;
    text-decoration: underline;
}

QFrame#filter_separator {
    color: #343a43;
    margin-top: 7px;
}

QPushButton#unrecognized_filter_button {
    background-color: #332a1f;
    color: #f1bd73;
    border: 1px solid #68502e;
}

QPushButton#unrecognized_filter_button:hover {
    background-color: #443522;
}

QPushButton#unrecognized_filter_button:checked {
    background-color: #b66a15;
    color: #ffffff;
    border-color: #e19137;
}

/* ScrollArea (Lista de cards) */
QScrollArea {
    border: none;
    background-color: transparent;
}

/* Card Individual do Militar/Funcionário */
QFrame#photo_card {
    background-color: #1e1e1e;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
}

QFrame#photo_card:hover {
    border: 1px solid #3a86ff;
}

QFrame#photo_card[withoutPhoto="true"] {
    border: 1px dashed #b66a15;
}

QFrame#report_metric_card {
    background-color: #1e1e1e;
    border: 1px solid #343434;
    border-radius: 8px;
    min-height: 92px;
}

QLabel#report_metric_title {
    color: #9ca3af;
    font-size: 12px;
}

QLabel#report_metric_value {
    color: #ffffff;
    font-size: 25px;
    font-weight: bold;
}

QTableWidget {
    background-color: #171717;
    alternate-background-color: #1d1d1d;
    color: #ffffff;
    border: 1px solid #343434;
    gridline-color: #343434;
    selection-background-color: #3a86ff;
}

QHeaderView::section {
    background-color: #252525;
    color: #e5e7eb;
    border: none;
    border-right: 1px solid #3a3a3a;
    border-bottom: 1px solid #3a3a3a;
    padding: 7px;
    font-weight: bold;
}

QFrame#gallery_photo {
    background-color: #1e1e1e;
    border: 1px solid #343434;
    border-radius: 7px;
}

QFrame#gallery_photo[selected="true"] {
    border: 2px solid #3a86ff;
    background-color: #202837;
}

QFrame#gallery_selection_bar {
    background-color: #1b2330;
    border: 1px solid #30415a;
    border-radius: 6px;
}

QPushButton#danger_btn {
    background-color: #7f1d1d;
    border-color: #a83232;
}

QPushButton#danger_btn:hover {
    background-color: #a52828;
}

QCheckBox {
    color: #d5d9e0;
    spacing: 5px;
}

/* Tags de Esquadrão e Seção dentro do Card */
QLabel#tag_lbl {
    background-color: #2d2d2d;
    color: #b0b0b0;
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
}

QLabel#tag_lbl:hover {
    background-color: #3d3d3d;
    color: #ffffff;
}

/* Combobox Customizado (Usado para trocar a Tag rápida) */
QComboBox {
    background-color: #2d2d2d;
    color: #ffffff;
    border: 1px solid #3d3d3d;
    border-radius: 4px;
    padding: 4px 8px;
}

QComboBox::drop-down {
    border: none;
}

QListView {
    background-color: #1e1e1e;
    color: #ffffff;
    border: 1px solid #2d2d2d;
    selection-background-color: #3a86ff;
}

QListWidget {
    background-color: #171717;
    color: #ffffff;
    border: 1px solid #343434;
    border-radius: 4px;
    padding: 4px;
}

QListWidget::item {
    padding: 6px;
}

QListWidget::item:selected {
    background-color: #3a86ff;
}
"""
