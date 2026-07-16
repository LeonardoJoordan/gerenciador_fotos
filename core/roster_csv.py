import csv
import unicodedata


class RosterCsv:
    TEMPLATE_FILENAME = "modelo_cadastro_em_lote.csv"

    @staticmethod
    def _key(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value))
        return " ".join(
            "".join(char for char in normalized if not unicodedata.combining(char))
            .casefold()
            .replace("/", " ")
            .replace("_", " ")
            .split()
        )

    @classmethod
    def read(cls, path: str, config: dict) -> list[dict]:
        with open(path, "r", encoding="utf-8-sig", newline="") as csv_file:
            sample = csv_file.read(4096)
            csv_file.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,")
            except csv.Error:
                dialect = csv.excel
                dialect.delimiter = ";"
            reader = csv.DictReader(csv_file, dialect=dialect)
            if not reader.fieldnames:
                raise ValueError("O CSV não possui cabeçalho.")
            headers = {cls._key(header): header for header in reader.fieldnames}

            def header(*aliases):
                for alias in aliases:
                    if cls._key(alias) in headers:
                        return headers[cls._key(alias)]
                return None

            rank_header = header("Posto", "Posto/Graduação", "Posto Graduação")
            name_header = header("Nome", "Nome de Guerra")
            squadron_header = header("Esquadrão", "Esquadrao", "Unidade")
            section_header = header("Fração", "Fracao", "Setor")
            template_control_header = header("Controle do modelo")
            if not rank_header or not name_header or not squadron_header:
                raise ValueError(
                    "O CSV precisa das colunas Posto, Nome e Esquadrão. Fração é opcional."
                )

            abbreviations = config.get("abreviacoes", {})
            rank_lookup = cls._lookup(
                config.get("postos_graduacoes", []),
                abbreviations.get("postos_graduacoes", {}),
            )
            squadron_lookup = cls._lookup(
                config.get("esquadroes", {}).keys(),
                abbreviations.get("esquadroes", {}),
            )
            rows = []
            seen = set()
            for line_number, raw in enumerate(reader, start=2):
                raw_rank = str(raw.get(rank_header, "") or "").strip()
                name = str(raw.get(name_header, "") or "").strip()
                raw_squadron = str(raw.get(squadron_header, "") or "").strip()
                raw_section = (
                    str(raw.get(section_header, "") or "").strip()
                    if section_header
                    else ""
                )
                template_control = (
                    str(raw.get(template_control_header, "") or "").strip()
                    if template_control_header
                    else ""
                )
                # Os cadastros fictícios do modelo servem apenas como exemplo.
                if cls._key(template_control).startswith("exemplo"):
                    continue
                # As colunas de referência também não representam cadastros.
                if not any((raw_rank, name, raw_squadron, raw_section)):
                    continue
                errors = []
                rank = rank_lookup.get(cls._key(raw_rank), "")
                squadron = squadron_lookup.get(cls._key(raw_squadron), "")
                if not rank:
                    errors.append("posto não cadastrado")
                if not name:
                    errors.append("nome vazio")
                if not squadron:
                    errors.append("esquadrão não cadastrado")
                section = ""
                if squadron:
                    configured_sections = config.get("esquadroes", {}).get(squadron, [])
                    section_lookup = cls._lookup(
                        configured_sections,
                        abbreviations.get("fracoes", {}).get(squadron, {}),
                    )
                    section = section_lookup.get(cls._key(raw_section), "") if raw_section else ""
                    if configured_sections and not section:
                        errors.append("fração obrigatória ou não cadastrada")
                    if not configured_sections and raw_section:
                        errors.append("o esquadrão não possui frações")
                identity_key = (
                    cls._key(rank), cls._key(name), cls._key(squadron), cls._key(section)
                )
                if all(identity_key) and identity_key in seen:
                    errors.append("duplicado no CSV")
                seen.add(identity_key)
                rows.append(
                    {
                        "linha": line_number,
                        "posto_grad": rank or raw_rank,
                        "nome_guerra": name,
                        "esquadrao": squadron or raw_squadron,
                        "fracao": section or raw_section,
                        "erro": "; ".join(errors),
                    }
                )
            return rows

    @classmethod
    def write_template(cls, path: str, config: dict) -> str:
        """Cria um modelo CSV preenchível com referências da configuração atual."""
        if not path.casefold().endswith(".csv"):
            path += ".csv"

        ranks = list(config.get("postos_graduacoes", []))
        squadron_sections = config.get("esquadroes", {})
        squadrons = list(squadron_sections)
        if not ranks or not squadrons:
            raise ValueError(
                "Cadastre ao menos um posto/graduação e um esquadrão antes de exportar o modelo."
            )

        fictional_names = ["Almeida", "Barbosa", "Costa"]
        examples = []
        for index, name in enumerate(fictional_names):
            rank = ranks[index % len(ranks)]
            squadron = squadrons[index % len(squadrons)]
            sections = squadron_sections.get(squadron, [])
            section = sections[index % len(sections)] if sections else ""
            examples.append([rank, name, squadron, section, "EXEMPLO — NÃO IMPORTAR"])

        section_references = [
            (squadron, section)
            for squadron, sections in squadron_sections.items()
            for section in sections
        ]
        row_count = max(
            len(examples) + 10,
            len(ranks),
            len(squadrons),
            len(section_references),
        )

        with open(path, "w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.writer(csv_file, delimiter=";", quoting=csv.QUOTE_MINIMAL)
            writer.writerow(
                [
                    "Posto/Graduação",
                    "Nome de Guerra",
                    "Esquadrão",
                    "Fração",
                    "Controle do modelo",
                    "Postos/Graduações válidos",
                    "Esquadrões válidos",
                    "Esquadrão da fração",
                    "Frações válidas",
                ]
            )
            for index in range(row_count):
                example = examples[index] if index < len(examples) else ["", "", "", "", ""]
                if index == len(examples):
                    example[4] = "PREENCHA NOVOS CADASTROS DESTA LINHA PARA BAIXO"
                reference_squadron, reference_section = (
                    section_references[index]
                    if index < len(section_references)
                    else ("", "")
                )
                writer.writerow(
                    [
                        *example,
                        ranks[index] if index < len(ranks) else "",
                        squadrons[index] if index < len(squadrons) else "",
                        reference_squadron,
                        reference_section,
                    ]
                )
        return path

    @classmethod
    def _lookup(cls, values, abbreviations: dict) -> dict[str, str]:
        result = {}
        for value in values:
            result[cls._key(value)] = value
            abbreviation = str(abbreviations.get(value, "") or "").strip()
            if abbreviation:
                result[cls._key(abbreviation)] = value
        return result
