from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSet,
    QChart,
    QChartView,
    QStackedBarSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.report_service import ReportService
from ui.widgets.filter_button_grid import FilterButtonGrid


class ReportDashboard(QWidget):
    TAB_OVERVIEW = 0
    TAB_MATRIX = 1
    TAB_GENERAL = 2
    VIEW_SQUADRONS = "squadrons"
    VIEW_RANKS = "ranks"
    VIEW_SQUADRON_RANKS = "squadron_ranks"

    requestOpenMember = Signal(object)
    requestAddPhoto = Signal(object)
    requestDeleteMember = Signal(object)
    requestExport = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.members: list[dict] = []
        self.config: dict = {}
        self.report = ReportService.build([], {})

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Relatórios de efetivo", self)
        title.setObjectName("section_title")
        export_button = QPushButton("Exportar visualização CSV", self)
        export_button.setObjectName("primary_btn")
        export_button.clicked.connect(self._request_export)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(export_button)
        layout.addLayout(header)

        self.report_tabs = QTabWidget(self)
        self.report_tabs.addTab(self._build_overview(), "Visão geral")
        self.report_tabs.addTab(self._build_matrix(), "Efetivo por posto")
        self.report_tabs.addTab(self._build_general_report(), "Relatório Geral")
        layout.addWidget(self.report_tabs, 1)

    def _request_export(self):
        self.requestExport.emit(self.export_context())

    def export_context(self) -> dict:
        current_tab = self.report_tabs.currentIndex()
        if current_tab == self.TAB_GENERAL:
            return {
                "view": "general",
                "squadron": self.general_squadron.currentText(),
                "photo_statuses": self.general_photo_filters.selected_values(),
            }
        if current_tab == self.TAB_MATRIX:
            return {"view": "matrix"}
        return {
            "view": "overview",
            "mode": self.chart_mode.currentData(),
            "squadron": self.chart_squadron.currentText(),
        }

    def _build_overview(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        cards = QGridLayout()
        self.total_value = self._metric_card(cards, 0, "Efetivo total")
        self.with_photo_value = self._metric_card(cards, 1, "Com foto")
        self.without_photo_value = self._metric_card(cards, 2, "Sem foto")
        self.coverage_value = self._metric_card(cards, 3, "Cobertura")
        layout.addLayout(cards)

        chart_filters = QHBoxLayout()
        chart_filters.addWidget(QLabel("Visualizar:", self))
        self.chart_mode = QComboBox(self)
        self.chart_mode.addItem("Efetivo geral por esquadrão", self.VIEW_SQUADRONS)
        self.chart_mode.addItem("Efetivo geral por posto/graduação", self.VIEW_RANKS)
        self.chart_mode.addItem("Um esquadrão por posto/graduação", self.VIEW_SQUADRON_RANKS)
        self.chart_mode.currentIndexChanged.connect(self._chart_selection_changed)
        chart_filters.addWidget(self.chart_mode)

        self.chart_squadron_label = QLabel("Esquadrão:", self)
        self.chart_squadron = QComboBox(self)
        self.chart_squadron.currentIndexChanged.connect(self._populate_chart)
        chart_filters.addWidget(self.chart_squadron_label)
        chart_filters.addWidget(self.chart_squadron)
        chart_filters.addStretch()
        layout.addLayout(chart_filters)

        self.chart_view = QChartView(self)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        layout.addWidget(self.chart_view, 1)
        self._update_chart_controls()
        return page

    def _metric_card(self, layout: QGridLayout, column: int, title: str) -> QLabel:
        card = QFrame(self)
        card.setObjectName("report_metric_card")
        card_layout = QVBoxLayout(card)
        label = QLabel(title, card)
        label.setObjectName("report_metric_title")
        value = QLabel("0", card)
        value.setObjectName("report_metric_value")
        value.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(label, 0, Qt.AlignCenter)
        card_layout.addWidget(value)
        layout.addWidget(card, 0, column)
        return value

    def _build_matrix(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        self.matrix_table = QTableWidget(self)
        self.matrix_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.matrix_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.matrix_table)
        return page

    def _build_general_report(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("Esquadrão:", self))
        self.general_squadron = QComboBox(self)
        self.general_squadron.currentTextChanged.connect(self._populate_general_report)
        filters.addWidget(self.general_squadron)
        filters.addSpacing(12)
        filters.addWidget(QLabel("Situação da foto:", self))
        self.general_photo_filters = FilterButtonGrid(
            columns=2,
            simple_toggle=True,
            parent=self,
        )
        self.general_photo_filters.set_options(
            ["Com foto", "Sem foto"],
            all_mode=True,
        )
        self.general_photo_filters.selectionChanged.connect(
            self._populate_general_report
        )
        filters.addWidget(self.general_photo_filters)
        filters.addStretch()
        self.general_count = QLabel("0 militares", self)
        filters.addWidget(self.general_count)
        layout.addLayout(filters)

        self.general_table = QTableWidget(self)
        self.general_table.setColumnCount(6)
        self.general_table.setHorizontalHeaderLabels(
            ["Posto/Graduação", "Nome", "Esquadrão", "Fração", "Fotos", "Ações"]
        )
        self.general_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.general_table.setAlternatingRowColors(True)
        header = self.general_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.general_table.setColumnWidth(5, 290)
        layout.addWidget(self.general_table)
        return page

    def refresh(self, members: list[dict], config: dict):
        self.members = list(members)
        self.config = config
        self.report = ReportService.build(self.members, config)
        self.total_value.setText(str(self.report["total"]))
        self.with_photo_value.setText(str(self.report["com_foto"]))
        self.without_photo_value.setText(str(self.report["sem_foto"]))
        self.coverage_value.setText(f'{self.report["cobertura"]:.1f}%')

        selected_squadron = self.chart_squadron.currentText()
        self.chart_squadron.blockSignals(True)
        self.chart_squadron.clear()
        self.chart_squadron.addItems(self.report["esquadroes"])
        selected_index = self.chart_squadron.findText(selected_squadron)
        self.chart_squadron.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.chart_squadron.blockSignals(False)
        self._update_chart_controls()
        self._populate_chart()
        self._populate_matrix()
        current = self.general_squadron.currentText()
        self.general_squadron.blockSignals(True)
        self.general_squadron.clear()
        self.general_squadron.addItem("Todos")
        self.general_squadron.addItems(self.report["esquadroes"])
        index = self.general_squadron.findText(current)
        self.general_squadron.setCurrentIndex(index if index >= 0 else 0)
        self.general_squadron.blockSignals(False)
        self._populate_general_report()

    def _chart_selection_changed(self):
        self._update_chart_controls()
        self._populate_chart()

    def _update_chart_controls(self):
        squadron_mode = self.chart_mode.currentData() == self.VIEW_SQUADRON_RANKS
        self.chart_squadron_label.setVisible(squadron_mode)
        self.chart_squadron.setVisible(squadron_mode)

    def _chart_data(self) -> tuple[str, list[str], dict]:
        mode = self.chart_mode.currentData()
        if mode == self.VIEW_RANKS:
            return (
                "Efetivo geral por posto/graduação",
                self.report["postos"],
                self.report["por_posto"],
            )
        if mode == self.VIEW_SQUADRON_RANKS:
            squadron = self.chart_squadron.currentText()
            return (
                f"Efetivo do {squadron} por posto/graduação" if squadron else "Efetivo por posto/graduação",
                self.report["postos"],
                self.report["por_esquadrao_posto"].get(squadron, {}),
            )
        return (
            "Efetivo geral por esquadrão",
            self.report["esquadroes"],
            self.report["por_esquadrao"],
        )

    def _populate_chart(self):
        title, ordered_categories, values_by_category = self._chart_data()
        # Mantém todas as categorias configuradas no eixo, inclusive as que estão
        # com efetivo zero, para que os gráficos preservem sempre o mesmo padrão.
        categories = list(ordered_categories)
        axis_labels = categories
        if self.chart_mode.currentData() in {self.VIEW_RANKS, self.VIEW_SQUADRON_RANKS}:
            rank_abbreviations = self.config.get("abreviacoes", {}).get(
                "postos_graduacoes", {}
            )
            axis_labels = [rank_abbreviations.get(rank, rank) for rank in categories]
        photographed = QBarSet("Com foto")
        pending = QBarSet("Sem foto")
        complete = QBarSet("Completo (100%)")
        photographed_values = []
        pending_values = []
        complete_values = []
        for item in categories:
            values = values_by_category[item]
            is_complete = values["total"] > 0 and values["sem_foto"] == 0
            photographed_values.append(0 if is_complete else values["com_foto"])
            pending_values.append(0 if is_complete else values["sem_foto"])
            complete_values.append(values["total"] if is_complete else 0)
        photographed.append(photographed_values)
        pending.append(pending_values)
        complete.append(complete_values)
        series = QStackedBarSeries()
        series.append(photographed)
        series.append(pending)
        series.append(complete)
        series.setLabelsVisible(True)
        series.setLabelsFormat("@value")
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(title)
        chart.setTheme(QChart.ChartThemeDark)
        photographed.setColor(QColor("#3a86ff"))
        pending.setColor(QColor("#FF5C00"))
        complete.setColor(QColor("#2eaf62"))
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        axis_x = QBarCategoryAxis()
        axis_x.append(axis_labels)
        if len(axis_labels) > 8:
            axis_x.setLabelsAngle(-35)
        axis_y = QValueAxis()
        maximum = max(
            (values_by_category[item]["total"] for item in categories),
            default=1,
        )
        axis_y.setRange(0, max(1, maximum))
        axis_y.setLabelFormat("%d")
        if maximum <= 10:
            axis_y.setTickCount(maximum + 1)
        else:
            upper_limit = ((maximum + 4) // 5) * 5
            axis_y.setRange(0, upper_limit)
            axis_y.setTickCount(6)
        chart.addAxis(axis_x, Qt.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
        self.chart_view.setChart(chart)

    def _populate_matrix(self):
        squadrons = self.report["esquadroes"]
        ranks = self.report["postos"]
        self.matrix_table.setRowCount(len(ranks) + 1)
        self.matrix_table.setColumnCount(len(squadrons) + 2)
        self.matrix_table.setHorizontalHeaderLabels(
            ["Posto/Graduação", *squadrons, "Total"]
        )
        for row, rank in enumerate(ranks):
            self.matrix_table.setItem(row, 0, QTableWidgetItem(rank))
            values = []
            for column, squadron in enumerate(squadrons, start=1):
                value = self.report["matriz"][rank][squadron]
                values.append(value)
                self.matrix_table.setItem(row, column, QTableWidgetItem(str(value)))
            self.matrix_table.setItem(row, len(squadrons) + 1, QTableWidgetItem(str(sum(values))))
        total_row = len(ranks)
        self.matrix_table.setItem(total_row, 0, QTableWidgetItem("Total"))
        for column, squadron in enumerate(squadrons, start=1):
            self.matrix_table.setItem(
                total_row,
                column,
                QTableWidgetItem(str(self.report["por_esquadrao"][squadron]["total"])),
            )
        self.matrix_table.setItem(total_row, len(squadrons) + 1, QTableWidgetItem(str(self.report["total"])))

    def _populate_general_report(self):
        selected_squadron = self.general_squadron.currentText()
        selected_statuses = set(self.general_photo_filters.selected_values())
        visible_members = [
            member
            for member in self.members
            if (
                selected_squadron in {"", "Todos"}
                or member["esquadrao"] == selected_squadron
            )
            and (
                "Com foto" if member.get("photo_count", 0) else "Sem foto"
            )
            in selected_statuses
        ]
        self.general_table.setRowCount(len(visible_members))
        count = len(visible_members)
        self.general_count.setText(
            "1 militar" if count == 1 else f"{count} militares"
        )
        for row, member in enumerate(visible_members):
            photo_count = member.get("photo_count", 0)
            for column, value in enumerate(
                [
                    member["posto_grad"],
                    member["nome_guerra"],
                    member["esquadrao"],
                    member["fracao"] or "—",
                    photo_count if photo_count else "Pendente",
                ]
            ):
                item = QTableWidgetItem(str(value))
                if column == 4:
                    item.setTextAlignment(Qt.AlignCenter)
                self.general_table.setItem(row, column, item)
            actions = QWidget(self.general_table)
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(4)
            open_button = QPushButton("Abrir", actions)
            add_button = QPushButton("Adicionar foto", actions)
            delete_button = QPushButton("Excluir", actions)
            delete_button.setObjectName("danger_btn")
            open_button.clicked.connect(
                lambda checked=False, item=member: self.requestOpenMember.emit(item)
            )
            add_button.clicked.connect(
                lambda checked=False, item=member: self.requestAddPhoto.emit(item)
            )
            delete_button.clicked.connect(
                lambda checked=False, item=member: self.requestDeleteMember.emit(item)
            )
            action_layout.addWidget(open_button)
            action_layout.addWidget(add_button)
            action_layout.addWidget(delete_button)
            self.general_table.setCellWidget(row, 5, actions)
        self.general_table.resizeRowsToContents()
