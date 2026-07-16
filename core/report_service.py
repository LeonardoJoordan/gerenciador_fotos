import csv
import os
from collections import Counter
from typing import Any


class ReportService:
    """Agrega o efetivo e exporta relatórios sem manter estado paralelo."""

    @staticmethod
    def ordered_values(configured, actual) -> list[str]:
        return list(dict.fromkeys([*configured, *actual]))

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
        with_photo = sum(member.get("photo_count", 0) > 0 for member in members)
        without_photo = len(members) - with_photo

        by_squadron = {}
        for squadron in squadrons:
            squad_members = [m for m in members if m["esquadrao"] == squadron]
            photographed = sum(m.get("photo_count", 0) > 0 for m in squad_members)
            total = len(squad_members)
            by_squadron[squadron] = {
                "total": total,
                "com_foto": photographed,
                "sem_foto": total - photographed,
                "cobertura": (photographed / total * 100) if total else 0.0,
            }

        by_rank = {}
        by_squadron_rank = {}
        for rank in ranks:
            rank_members = [m for m in members if m["posto_grad"] == rank]
            photographed = sum(m.get("photo_count", 0) > 0 for m in rank_members)
            total = len(rank_members)
            by_rank[rank] = {
                "total": total,
                "com_foto": photographed,
                "sem_foto": total - photographed,
            }

        for squadron in squadrons:
            by_squadron_rank[squadron] = {}
            for rank in ranks:
                rank_members = [
                    member
                    for member in members
                    if member["esquadrao"] == squadron
                    and member["posto_grad"] == rank
                ]
                photographed = sum(
                    member.get("photo_count", 0) > 0 for member in rank_members
                )
                total = len(rank_members)
                by_squadron_rank[squadron][rank] = {
                    "total": total,
                    "com_foto": photographed,
                    "sem_foto": total - photographed,
                }

        counts = Counter(
            (member["posto_grad"], member["esquadrao"]) for member in members
        )
        matrix = {
            rank: {squadron: counts[(rank, squadron)] for squadron in squadrons}
            for rank in ranks
        }
        pending = [member for member in members if member.get("photo_count", 0) == 0]
        return {
            "total": len(members),
            "com_foto": with_photo,
            "sem_foto": without_photo,
            "cobertura": (with_photo / len(members) * 100) if members else 0.0,
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
                values["com_foto"],
                values["sem_foto"],
                f'{values["cobertura"]:.1f}',
            ]
            for squadron, values in report["por_esquadrao"].items()
        ]
        written.append(
            cls._write_csv(
                directory,
                "efetivo_por_esquadrao.csv",
                ["Esquadrão", "Total", "Com foto", "Sem foto", "Cobertura (%)"],
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
                "Com foto" if member.get("photo_count", 0) else "Sem foto",
                member.get("photo_count", 0),
                member["member_path"],
            ]
            for member in members
        ]
        written.append(
            cls._write_csv(directory, "relacao_completa.csv", detail_header, detail_rows)
        )
        pending_rows = [row for member, row in zip(members, detail_rows) if not member.get("photo_count", 0)]
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
                context.get("photo_statuses", ["Com foto", "Sem foto"])
                if view == "general"
                else ["Sem foto"]
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
                if ("Com foto" if member.get("photo_count", 0) else "Sem foto")
                in selected_statuses
            ]
            header = [
                "Posto/Graduação",
                "Nome de Guerra",
                "Esquadrão",
                "Fração",
                "Fotos",
            ]
            rows = [
                [
                    member["posto_grad"],
                    member["nome_guerra"],
                    member["esquadrao"],
                    member["fracao"],
                    member.get("photo_count", 0) or "Pendente",
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
        header = [label, "Total", "Com foto", "Sem foto", "Cobertura (%)"]
        rows = []
        for category in categories:
            category_values = values.get(
                category, {"total": 0, "com_foto": 0, "sem_foto": 0}
            )
            total = category_values["total"]
            coverage = (
                category_values.get("cobertura")
                if "cobertura" in category_values
                else (category_values["com_foto"] / total * 100 if total else 0.0)
            )
            rows.append(
                [
                    category,
                    total,
                    category_values["com_foto"],
                    category_values["sem_foto"],
                    f"{coverage:.1f}",
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
