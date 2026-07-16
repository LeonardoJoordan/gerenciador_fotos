from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class RosterImportDialog(QDialog):
    def __init__(self, rows: list[dict], parent=None):
        super().__init__(parent)
        self.rows = rows
        self.setWindowTitle("Importar relação de militares")
        self.resize(900, 580)
        layout = QVBoxLayout(self)
        valid_count = sum(not row["erro"] for row in rows)
        invalid_count = len(rows) - valid_count
        summary = QLabel(
            f"{valid_count} cadastro(s) válido(s) · {invalid_count} linha(s) com problema",
            self,
        )
        summary.setObjectName("settings_hint")
        layout.addWidget(summary)

        table = QTableWidget(len(rows), 6, self)
        table.setHorizontalHeaderLabels(
            ["Linha", "Posto", "Nome", "Esquadrão", "Fração", "Situação"]
        )
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row_index, row in enumerate(rows):
            values = [
                row["linha"],
                row["posto_grad"],
                row["nome_guerra"],
                row["esquadrao"],
                row["fracao"] or "—",
                row["erro"] or "Pronto para importar",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if row["erro"]:
                    item.setForeground(QColor("#ff8c8c"))
                table.setItem(row_index, column, item)
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("Importar válidos")
        buttons.button(QDialogButtonBox.Ok).setEnabled(valid_count > 0)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def valid_rows(self) -> list[dict]:
        return [row for row in self.rows if not row["erro"]]
