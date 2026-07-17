import csv
import os
from collections import Counter
from typing import Any


class ReportService:
    """Agrega o efetivo e exporta relatórios sem manter estado paralelo."""

    STATUS_CURRENT = "Em dia"
    STATUS_PENDING = "Pendente"
    STATUS_UPDATE = "Atualizar"
    PHOTO_STATUSES = (STATUS_CURRENT, STATUS_PENDING, STATUS_UPDATE)

    @staticmethod
    def ordered_values(configured, actual) -> list[str]:
        return list(dict.fromkeys([*configured, *actual]))

    @classmethod
    def member_status(cls, member: dict) -> str:
        if member.get("photo_count", 0) == 0:
            return cls.STATUS_PENDING
        if member.get("update_recommended", False):
            return cls.STATUS_UPDATE
        return cls.STATUS_CURRENT

    @classmethod
    def _aggregate_statuses(cls, members: list[dict]) -> dict[str, Any]:
        counts = Counter(cls.member_status(member) for member in members)
        return cls._aggregate_counts(counts, len(members))

    @classmethod
    def _aggregate_counts(cls, counts: Counter, total: int) -> dict[str, Any]:
        current = counts[cls.STATUS_CURRENT]
        pending = counts[cls.STATUS_PENDING]
        update = counts[cls.STATUS_UPDATE]
        return {
            "total": total,
            "em_dia": current,
            "pendente": pending,
            "atualizar": update,
            "regularidade": (current / total * 100) if total else 0.0,
            # Chaves mantidas para compatibilidade com exportações antigas.
            "com_foto": current + update,
            "sem_foto": pending,
            "cobertura": (current / total * 100) if total else 0.0,
        }

    @classmethod
    def build(cls, members: list[dict], config: dict) -> dict[str, Any]:
        squadrons = cls.ordered_values(
            config.get("esquadroes", {}).keys(),
            (member["esquadrao"] for member in members),
        )
        ranks = cls.ordered_values(
            config.get("postos_graduacoes", []),
            (member["posto_grad"] for member in members),
        )
        total_statuses = Counter()
        squadron_statuses = {squadron: Counter() for squadron in squadrons}
        squadron_totals = Counter()
        rank_statuses = {rank: Counter() for rank in ranks}
        rank_totals = Counter()
        squadron_rank_statuses = {
            squadron: {rank: Counter() for rank in ranks} for squadron in squadrons
        }
        squadron_rank_totals = Counter()
        counts = Counter()
        pending = []

        for member in members:
            status = cls.member_status(member)
            squadron = member["esquadrao"]
            rank = member["posto_grad"]
            total_statuses[status] += 1
            squadron_statuses.setdefault(squadron, Counter())[status] += 1
            squadron_totals[squadron] += 1
            rank_statuses.setdefault(rank, Counter())[status] += 1
            rank_totals[rank] += 1
            squadron_rank_statuses.setdefault(squadron, {}).setdefault(
                rank, Counter()
            )[status] += 1
            squadron_rank_totals[(squadron, rank)] += 1
            counts[(rank, squadron)] += 1
            if status == cls.STATUS_PENDING:
                pending.append(member)

        totals = cls._aggregate_counts(total_statuses, len(members))
        by_squadron = {
            squadron: cls._aggregate_counts(
                squadron_statuses.get(squadron, Counter()), squadron_totals[squadron]
            )
            for squadron in squadrons
        }
        by_rank = {
            rank: cls._aggregate_counts(rank_statuses.get(rank, Counter()), rank_totals[rank])
            for rank in ranks
        }
        by_squadron_rank = {
            squadron: {
                rank: cls._aggregate_counts(
                    squadron_rank_statuses.get(squadron, {}).get(rank, Counter()),
                    squadron_rank_totals[(squadron, rank)],
                )
                for rank in ranks
            }
            for squadron in squadrons
        }
        matrix = {
            rank: {squadron: counts[(rank, squadron)] for squadron in squadrons}
            for rank in ranks
        }
        return {
            **totals,
            "esquadroes": squadrons,
            "postos": ranks,
            "por_esquadrao": by_squadron,
            "por_posto": by_rank,
            "por_esquadrao_posto": by_squadron_rank,
            "matriz": matrix,
            "pendentes": pending,
        }

    @classmethod
    def export_all(cls, directory: str, members: list[dict], config: dict) -> list[str]:
        report = cls.build(members, config)
        os.makedirs(directory, exist_ok=True)
        written = []

        squad_rows = [
            [
                squadron,
                values["total"],
                values["em_dia"],
                values["pendente"],
                values["atualizar"],
                f'{values["regularidade"]:.1f}',
            ]
            for squadron, values in report["por_esquadrao"].items()
        ]
        written.append(
            cls._write_csv(
                directory,
                "efetivo_por_esquadrao.csv",
                [
                    "Esquadrão",
                    "Total",
                    "Em dia",
                    "Pendente",
                    "Atualizar",
                    "Regularidade (%)",
                ],
                squad_rows,
            )
        )

        matrix_header = ["Posto/Graduação", *report["esquadroes"], "Total"]
        matrix_rows = []
        for rank in report["postos"]:
            values = [report["matriz"][rank][squadron] for squadron in report["esquadroes"]]
            matrix_rows.append([rank, *values, sum(values)])
        written.append(
            cls._write_csv(
                directory, "efetivo_por_posto.csv", matrix_header, matrix_rows
            )
        )

        detail_header = [
            "Posto/Graduação",
            "Nome de Guerra",
            "Esquadrão",
            "Fração",
            "Situação",
            "Quantidade de fotos",
            "Pasta do cadastro",
        ]
        detail_rows = [
            [
                member["posto_grad"],
                member["nome_guerra"],
                member["esquadrao"],
                member["fracao"],
                cls.member_status(member),
                member.get("photo_count", 0),
                member["member_path"],
            ]
            for member in members
        ]
        written.append(
            cls._write_csv(directory, "relacao_completa.csv", detail_header, detail_rows)
        )
        pending_rows = [
            row
            for member, row in zip(members, detail_rows)
            if cls.member_status(member) == cls.STATUS_PENDING
        ]
        written.append(
            cls._write_csv(directory, "pendencias_de_foto.csv", detail_header, pending_rows)
        )
        return written

    @classmethod
    def export_view(
        cls,
        path: str,
        members: list[dict],
        config: dict,
        context: dict,
    ) -> str:
        """Exporta somente os dados representados pela visualização ativa."""
        if not path.casefold().endswith(".csv"):
            path += ".csv"
        report = cls.build(members, config)
        view = context.get("view", "overview")

        if view in {"general", "pending"}:
            selected_squadron = context.get("squadron", "Todos")
            selected_statuses = set(
                context.get("photo_statuses", cls.PHOTO_STATUSES)
                if view == "general"
                else [cls.STATUS_PENDING]
            )
            visible_members = [
                member
                for member in members
                if selected_squadron in {"", "Todos"}
                or member["esquadrao"] == selected_squadron
            ]
            visible_members = [
                member
                for member in visible_members
                if cls.member_status(member) in selected_statuses
            ]
            header = [
                "Posto/Graduação",
                "Nome de Guerra",
                "Esquadrão",
                "Fração",
                "Fotos",
                "Status",
            ]
            rows = [
                [
                    member["posto_grad"],
                    member["nome_guerra"],
                    member["esquadrao"],
                    member["fracao"],
                    member.get("photo_count", 0),
                    cls.member_status(member),
                ]
                for member in visible_members
            ]
        elif view == "matrix":
            header = ["Posto/Graduação", *report["esquadroes"], "Total"]
            rows = []
            for rank in report["postos"]:
                values = [
                    report["matriz"][rank][squadron]
                    for squadron in report["esquadroes"]
                ]
                rows.append([rank, *values, sum(values)])
            rows.append(
                [
                    "Total",
                    *[
                        report["por_esquadrao"][squadron]["total"]
                        for squadron in report["esquadroes"]
                    ],
                    report["total"],
                ]
            )
        else:
            mode = context.get("mode", "squadrons")
            if mode == "ranks":
                header, rows = cls._status_rows(
                    "Posto/Graduação", report["postos"], report["por_posto"]
                )
            elif mode == "squadron_ranks":
                selected_squadron = context.get("squadron", "")
                values = report["por_esquadrao_posto"].get(selected_squadron, {})
                status_header, status_rows = cls._status_rows(
                    "Posto/Graduação", report["postos"], values
                )
                header = ["Esquadrão", *status_header]
                rows = [[selected_squadron, *row] for row in status_rows]
            else:
                header, rows = cls._status_rows(
                    "Esquadrão",
                    report["esquadroes"],
                    report["por_esquadrao"],
                )

        directory = os.path.dirname(os.path.abspath(path))
        filename = os.path.basename(path)
        return cls._write_csv(directory, filename, header, rows)

    @staticmethod
    def export_filename(context: dict) -> str:
        if context.get("view") == "general":
            return "relatorio_geral.csv"
        if context.get("view") == "pending":
            return "pendencias_de_foto.csv"
        if context.get("view") == "matrix":
            return "efetivo_por_posto.csv"
        mode = context.get("mode", "squadrons")
        if mode == "ranks":
            return "efetivo_geral_por_posto.csv"
        if mode == "squadron_ranks":
            return "efetivo_do_esquadrao_por_posto.csv"
        return "efetivo_geral_por_esquadrao.csv"

    @staticmethod
    def _status_rows(label: str, categories: list[str], values: dict) -> tuple[list, list]:
        header = [
            label,
            "Total",
            "Em dia",
            "Pendente",
            "Atualizar",
            "Regularidade (%)",
        ]
        rows = []
        for category in categories:
            category_values = values.get(
                category,
                {
                    "total": 0,
                    "em_dia": 0,
                    "pendente": 0,
                    "atualizar": 0,
                    "regularidade": 0.0,
                },
            )
            rows.append(
                [
                    category,
                    category_values["total"],
                    category_values["em_dia"],
                    category_values["pendente"],
                    category_values["atualizar"],
                    f'{category_values["regularidade"]:.1f}',
                ]
            )
        return header, rows

    @staticmethod
    def _write_csv(directory: str, filename: str, header: list, rows: list) -> str:
        path = os.path.join(directory, filename)
        with open(path, "w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            writer.writerow(header)
            writer.writerows(rows)
        return path
