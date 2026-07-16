import json
import os
import shutil
import re
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from PySide6.QtGui import QImageReader

from core.app_paths import root_config_dir


DEFAULT_CONFIG = {
    "esquadroes": {
        "Estado-Maior": [],
        "1º Esqd CC": [
            "Seção de Comando",
            "Sargenteação",
            "1º Pelotão",
            "2º Pelotão",
        ],
        "2º Esqd CC": ["Seção de Comando", "1º Pelotão"],
    },
    "postos_graduacoes": [
        "Coronel",
        "Tenente-Coronel",
        "Major",
        "Capitão",
        "Tenente",
        "Sargento",
        "Cabo",
        "Soldado",
    ],
    "abreviacoes": {
        "postos_graduacoes": {
            "Coronel": "Cel",
            "Tenente-Coronel": "Ten Cel",
            "Major": "Maj",
            "Capitão": "Cap",
            "Tenente": "Ten",
            "Sargento": "Sgt",
            "Cabo": "Cb",
            "Soldado": "Sd",
        },
        "esquadroes": {
            "Estado-Maior": "EM",
            "1º Esqd CC": "1º Esqd CC",
            "2º Esqd CC": "2º Esqd CC",
        },
        "fracoes": {
            "Estado-Maior": {},
            "1º Esqd CC": {
                "Seção de Comando": "Seç Cmdo",
                "Sargenteação": "Sgteação",
                "1º Pelotão": "1º Pel",
                "2º Pelotão": "2º Pel",
            },
            "2º Esqd CC": {
                "Seção de Comando": "Seç Cmdo",
                "1º Pelotão": "1º Pel",
            },
        },
    },
}


def _supported_photo_extensions() -> set[str]:
    available = {
        bytes(image_format).decode("ascii", "ignore").casefold()
        for image_format in QImageReader.supportedImageFormats()
    }
    aliases = {
        ".jpg": {"jpg", "jpeg"},
        ".jpeg": {"jpg", "jpeg"},
        ".jfif": {"jfif", "jpg", "jpeg"},
        ".png": {"png"},
        ".webp": {"webp"},
        ".bmp": {"bmp"},
        ".gif": {"gif"},
        ".tga": {"tga"},
        ".tif": {"tif", "tiff"},
        ".tiff": {"tif", "tiff"},
        ".heic": {"heic", "heif"},
        ".heif": {"heic", "heif"},
        ".avif": {"avif"},
    }
    supported = {
        extension
        for extension, format_names in aliases.items()
        if available.intersection(format_names)
    }
    return supported or {".jpg", ".jpeg", ".png"}


class FileManager:
    VALID_EXTENSIONS = _supported_photo_extensions()
    CONFIG_FILENAME = "config.json"
    MEMBER_MARKER = ".cadastro"

    def __init__(self, root_path: str = ""):
        self.root_path = os.path.abspath(root_path) if root_path else ""
        self.config: Dict[str, Any] = deepcopy(DEFAULT_CONFIG)

    @classmethod
    def image_dialog_filter(cls, include_all: bool = False) -> str:
        patterns = []
        for extension in sorted(cls.VALID_EXTENSIONS):
            patterns.extend((f"*{extension}", f"*{extension.upper()}"))
        image_filter = f"Imagens ({' '.join(patterns)})"
        return f"{image_filter};;Todos os arquivos (*)" if include_all else image_filter

    def set_root_path(self, path: str) -> Dict[str, Any]:
        self.root_path = os.path.abspath(path)
        return self.load_config()

    @property
    def config_path(self) -> str:
        if not self.root_path:
            raise ValueError("Diretório raiz de trabalho não definido.")
        return os.path.join(self.root_path, self.CONFIG_FILENAME)

    @property
    def external_config_path(self) -> str:
        """Local usado por versões que escondiam o JSON nos dados do aplicativo."""
        if not self.root_path:
            raise ValueError("Diretório raiz de trabalho não definido.")
        return os.path.join(root_config_dir(self.root_path), self.CONFIG_FILENAME)

    def load_config(self) -> Dict[str, Any]:
        """Lê a configuração da raiz ou cria uma configuração inicial."""
        if not self.root_path:
            raise ValueError("Diretório raiz de trabalho não definido.")
        os.makedirs(self.root_path, exist_ok=True)

        source_path = self.config_path
        migrating_external_config = False
        if not os.path.exists(source_path):
            if os.path.isfile(self.external_config_path):
                source_path = self.external_config_path
                migrating_external_config = True
            else:
                return self.save_config(self._infer_config_from_directory())

        try:
            with open(source_path, "r", encoding="utf-8") as config_file:
                loaded = json.load(config_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Não foi possível ler o config.json: {exc}") from exc

        normalized = self._normalize_config(loaded)
        # Migra configurações antigas adicionando o bloco de abreviações no próprio JSON.
        if migrating_external_config or normalized != loaded:
            saved = self.save_config(normalized)
            if migrating_external_config:
                try:
                    os.remove(self.external_config_path)
                except OSError:
                    pass
            return saved
        self.config = normalized
        return deepcopy(self.config)

    def _infer_config_from_directory(self) -> Dict[str, Any]:
        """Reconstrói o máximo possível da configuração usando somente o disco."""
        root = Path(self.root_path)
        squadrons: Dict[str, List[str]] = {}
        ranks: List[str] = []

        for squadron_dir in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
            if not squadron_dir.is_dir() or squadron_dir.name.startswith("."):
                continue
            sections = [
                child.name
                for child in sorted(squadron_dir.iterdir(), key=lambda path: path.name.casefold())
                if child.is_dir()
                and not child.name.startswith(".")
                and not self._directory_is_member(child)
            ]
            squadrons[squadron_dir.name] = sections
            for image_path in sorted(
                squadron_dir.rglob("*"), key=lambda path: str(path).casefold()
            ):
                if image_path.is_file() and image_path.suffix.lower() in self.VALID_EXTENSIONS:
                    identity = (
                        image_path.parent.name
                        if self._directory_is_member(image_path.parent)
                        else image_path.stem
                    )
                    rank = self._infer_rank_from_filename(identity)
                    if rank and rank not in ranks:
                        ranks.append(rank)

        # Também aproveita nomes de imagens soltas, embora não seja possível inferir sua unidade.
        for image_path in root.iterdir():
            if image_path.is_file() and image_path.suffix.lower() in self.VALID_EXTENSIONS:
                rank = self._infer_rank_from_filename(image_path.stem)
                if rank and rank not in ranks:
                    ranks.append(rank)

        if not squadrons and not ranks:
            return deepcopy(DEFAULT_CONFIG)

        if not ranks:
            ranks = deepcopy(DEFAULT_CONFIG["postos_graduacoes"])
        config = {"esquadroes": squadrons, "postos_graduacoes": ranks}
        return self._normalize_config(config)

    def _directory_is_member(self, directory: Path) -> bool:
        if not directory.is_dir():
            return False
        if (directory / self.MEMBER_MARKER).is_file():
            return True
        prefix = f"{directory.name}_".casefold()
        return any(
            child.is_file()
            and child.suffix.lower() in self.VALID_EXTENSIONS
            and child.stem.casefold().startswith(prefix)
            and child.stem[len(prefix):].isdigit()
            for child in directory.iterdir()
        )

    def _infer_rank_from_filename(self, stem: str) -> str:
        known_ranks = sorted(
            DEFAULT_CONFIG["postos_graduacoes"],
            key=lambda value: len(self._filename_part(value)),
            reverse=True,
        )
        for rank in known_ranks:
            prefix = f"{self._filename_part(rank)}_"
            if stem.casefold().startswith(prefix.casefold()):
                return rank
        for rank in known_ranks:
            legacy_prefix = f"{self._legacy_filename_part(rank)}_"
            if stem.casefold().startswith(legacy_prefix.casefold()):
                return rank
        if "_" in stem:
            # Sem o JSON, não há como distinguir com certeza posto composto de nome composto.
            return stem.split("_", 1)[0].replace("-", " ")
        return ""

    def save_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Valida e grava o JSON de forma atômica, preservando acentos."""
        normalized = self._normalize_config(config)
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        temporary_path = f"{self.config_path}.tmp"
        try:
            with open(temporary_path, "w", encoding="utf-8") as config_file:
                json.dump(normalized, config_file, ensure_ascii=False, indent=2)
                config_file.write("\n")
            os.replace(temporary_path, self.config_path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

        self.config = normalized
        return deepcopy(self.config)

    @staticmethod
    def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(config, dict):
            raise ValueError("A configuração precisa ser um objeto JSON.")

        raw_squadrons = config.get("esquadroes", {})
        raw_ranks = config.get("postos_graduacoes", [])
        if not isinstance(raw_squadrons, dict) or not isinstance(raw_ranks, list):
            raise ValueError("'esquadroes' deve ser um objeto e 'postos_graduacoes' uma lista.")

        squadrons: Dict[str, List[str]] = {}
        for raw_name, raw_sections in raw_squadrons.items():
            name = str(raw_name).strip()
            if not name:
                continue
            if not isinstance(raw_sections, list):
                raise ValueError(f"As frações de '{name}' precisam formar uma lista.")
            squadrons[name] = FileManager._unique_clean_strings(raw_sections)

        ranks = FileManager._unique_clean_strings(raw_ranks)
        raw_abbreviations = config.get("abreviacoes", {})
        if not isinstance(raw_abbreviations, dict):
            raw_abbreviations = {}
        raw_rank_abbreviations = raw_abbreviations.get("postos_graduacoes", {})
        raw_squadron_abbreviations = raw_abbreviations.get("esquadroes", {})
        raw_section_abbreviations = raw_abbreviations.get("fracoes", {})
        if not isinstance(raw_rank_abbreviations, dict):
            raw_rank_abbreviations = {}
        if not isinstance(raw_squadron_abbreviations, dict):
            raw_squadron_abbreviations = {}
        if not isinstance(raw_section_abbreviations, dict):
            raw_section_abbreviations = {}

        rank_abbreviations = {
            rank: str(raw_rank_abbreviations.get(rank, rank)).strip() or rank for rank in ranks
        }
        squadron_abbreviations = {
            squadron: str(raw_squadron_abbreviations.get(squadron, squadron)).strip() or squadron
            for squadron in squadrons
        }
        section_abbreviations: Dict[str, Dict[str, str]] = {}
        for squadron, sections in squadrons.items():
            configured = raw_section_abbreviations.get(squadron, {})
            if not isinstance(configured, dict):
                configured = {}
            section_abbreviations[squadron] = {
                section: str(configured.get(section, section)).strip() or section
                for section in sections
            }

        return {
            "esquadroes": squadrons,
            "postos_graduacoes": ranks,
            "abreviacoes": {
                "postos_graduacoes": rank_abbreviations,
                "esquadroes": squadron_abbreviations,
                "fracoes": section_abbreviations,
            },
        }

    @staticmethod
    def _unique_clean_strings(values: List[Any]) -> List[str]:
        result = []
        seen = set()
        for value in values:
            clean = str(value).strip()
            key = clean.casefold()
            if clean and key not in seen:
                seen.add(key)
                result.append(clean)
        return result

    def scan_directory(self) -> List[Dict[str, Any]]:
        if not self.root_path or not os.path.isdir(self.root_path):
            return []

        items = []
        grouped_members: Dict[str, Dict[str, Any]] = {}
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [
                directory
                for directory in dirs
                if directory != ".thumbnails" and not directory.startswith(".delete-")
            ]
            for directory in dirs:
                member_path = Path(root) / directory
                if not self._directory_is_member(member_path):
                    continue
                modern = self._parse_member_directory(str(member_path))
                if modern:
                    grouped_members.setdefault(
                        os.path.normcase(modern["member_path"]), modern
                    )
            for filename in files:
                if Path(filename).suffix.lower() not in self.VALID_EXTENSIONS:
                    continue
                file_path = os.path.join(root, filename)
                modern = self._parse_member_photo(file_path)
                if modern:
                    key = os.path.normcase(modern["member_path"])
                    member = grouped_members.setdefault(key, modern)
                    member["photos"].append(os.path.abspath(file_path))
                    continue
                item = self._parse_file_info(file_path)
                if item:
                    item.update({
                        "member_path": item["absolute_path"],
                        "photos": [item["absolute_path"]],
                        "photo_count": 1,
                        "has_photo": True,
                        "is_legacy": True,
                    })
                    items.append(item)

        for member in grouped_members.values():
            member["photos"].sort(key=self._photo_sort_key)
            member["photo_count"] = len(member["photos"])
            member["has_photo"] = bool(member["photos"])
            if member["photos"]:
                member["absolute_path"] = self._primary_photo(member["photos"])
                member["filename"] = os.path.basename(member["absolute_path"])
            else:
                member["absolute_path"] = ""
                member["filename"] = ""
            items.append(member)
        rank_order = {
            rank.casefold(): index
            for index, rank in enumerate(self.config.get("postos_graduacoes", []))
        }
        unknown_rank_position = len(rank_order)
        return sorted(
            items,
            key=lambda item: (
                rank_order.get(item["posto_grad"].casefold(), unknown_rank_position),
                item["posto_grad"].casefold(),
                item["nome_guerra"].casefold(),
                item["esquadrao"].casefold(),
                item["fracao"].casefold(),
            ),
        )

    def _parse_member_photo(self, file_path: str) -> Dict[str, Any] | None:
        """Reconhece o formato Unidade/Fração/Pessoa/Pessoa_01.ext."""
        rel_path = os.path.relpath(file_path, self.root_path)
        parts = Path(rel_path).parts
        if len(parts) < 3:
            return None
        member_folder = parts[-2]
        match = re.fullmatch(r"(.+)_([0-9]+)", Path(parts[-1]).stem)
        if not match or match.group(1).casefold() != member_folder.casefold():
            return None

        member = self._parse_member_directory(os.path.dirname(file_path))
        if not member:
            return None
        return member

    def _parse_member_directory(self, member_path: str) -> Dict[str, Any] | None:
        """Extrai um cadastro moderno, inclusive quando sua pasta ainda está vazia."""
        rel_path = os.path.relpath(member_path, self.root_path)
        parts = Path(rel_path).parts
        if len(parts) < 2:
            return None
        member_folder = parts[-1]
        posto_grad, nome_guerra = self._split_identity(member_folder)
        if posto_grad == "Indefinido":
            return None
        location = parts[:-1]
        esquadrao = location[0] if location else "Sem Categoria"
        fracao = location[1] if len(location) >= 2 else ""
        return {
            "absolute_path": "",
            "filename": "",
            "member_path": os.path.abspath(member_path),
            "photos": [],
            "photo_count": 0,
            "has_photo": False,
            "is_legacy": False,
            "esquadrao": esquadrao,
            "fracao": fracao,
            "posto_grad": posto_grad,
            "nome_guerra": nome_guerra,
        }

    @staticmethod
    def _photo_sort_key(path: str) -> tuple[int, str]:
        match = re.search(r"_([0-9]+)$", Path(path).stem)
        return (int(match.group(1)) if match else 10**9, path.casefold())

    @staticmethod
    def _primary_photo(photos: List[str]) -> str:
        for photo in photos:
            if re.search(r"_0*1$", Path(photo).stem):
                return photo
        return photos[0]

    def _parse_file_info(self, file_path: str) -> Dict[str, Any]:
        rel_path = os.path.relpath(file_path, self.root_path)
        parts = Path(rel_path).parts
        filename = parts[-1]

        if len(parts) >= 3:
            esquadrao, fracao = parts[0], parts[1]
        elif len(parts) == 2:
            esquadrao, fracao = parts[0], ""
        else:
            esquadrao, fracao = "Sem Categoria", ""

        stem = Path(filename).stem
        posto_grad, nome_guerra = self._split_identity(stem)
        return {
            "absolute_path": os.path.abspath(file_path),
            "filename": filename,
            "esquadrao": esquadrao,
            "fracao": fracao,
            "posto_grad": posto_grad,
            "nome_guerra": nome_guerra,
        }

    def _split_identity(self, stem: str) -> tuple[str, str]:
        ranks = self.config.get("postos_graduacoes", [])
        rank_token, separator, name_token = stem.partition("_")
        if separator and stem.count("_") == 1:
            # Formato atual: Posto-Composto_Nome-Composto.ext
            for rank in ranks:
                if self._filename_part(rank).casefold() == rank_token.casefold():
                    return rank, name_token.replace("-", " ").replace("_", " ")

        # Compatibilidade com o formato antigo, que também usava '_' dentro dos campos.
        legacy_ranks = sorted(ranks, key=lambda value: len(self._legacy_filename_part(value)), reverse=True)
        stem_folded = stem.casefold()
        for rank in legacy_ranks:
            prefix = f"{self._legacy_filename_part(rank)}_"
            if stem_folded.startswith(prefix.casefold()):
                return rank, stem[len(prefix):].replace("_", " ").replace("-", " ")

        if "_" in stem:
            rank, name = stem.split("_", 1)
            return rank.replace("-", " "), name.replace("_", " ").replace("-", " ")
        return "Indefinido", stem.replace("-", " ")

    def move_member(self, current_path: str, new_esquadrao: str, new_fracao: str = "") -> str:
        self._require_root()
        new_esquadrao = self._path_part(new_esquadrao, "Esquadrão")
        new_fracao = self._path_part(new_fracao, "Fração", allow_empty=True)
        filename = os.path.basename(current_path)
        dest_dir = os.path.join(self.root_path, new_esquadrao)
        if new_fracao:
            dest_dir = os.path.join(dest_dir, new_fracao)
        os.makedirs(dest_dir, exist_ok=True)
        destination = os.path.join(dest_dir, filename)

        if os.path.abspath(current_path) == os.path.abspath(destination):
            return destination
        self._ensure_destination_available(destination)
        shutil.move(current_path, destination)
        self._cleanup_empty_dirs(os.path.dirname(current_path))
        return destination

    def import_and_format_photo(
        self,
        source_path: str,
        posto_grad: str,
        nome_guerra: str,
        esquadrao: str,
        fracao: str = "",
    ) -> str:
        self._require_root()
        extension = Path(source_path).suffix.lower()
        if extension not in self.VALID_EXTENSIONS:
            raise ValueError("Formato de imagem não suportado neste computador.")
        if not os.path.isfile(source_path):
            raise FileNotFoundError("A imagem selecionada não existe.")

        identity = self._build_identity(posto_grad, nome_guerra)
        esquadrao = self._path_part(esquadrao, "Esquadrão")
        fracao = self._path_part(fracao, "Fração", allow_empty=True)
        dest_dir = os.path.join(self.root_path, esquadrao)
        if fracao:
            dest_dir = os.path.join(dest_dir, fracao)
        member_dir = os.path.join(dest_dir, identity)
        os.makedirs(member_dir, exist_ok=True)
        self._ensure_member_marker(member_dir)
        index = self._next_photo_index(member_dir)
        destination = os.path.join(member_dir, f"{identity}_{index:02d}{extension}")
        self._ensure_destination_available(destination)
        shutil.copy2(source_path, destination)
        return destination

    def create_member(
        self,
        posto_grad: str,
        nome_guerra: str,
        esquadrao: str,
        fracao: str = "",
    ) -> str:
        """Cria um cadastro portátil ainda sem fotografias."""
        self._require_root()
        identity = self._build_identity(posto_grad, nome_guerra)
        esquadrao = self._path_part(esquadrao, "Esquadrão")
        fracao = self._path_part(fracao, "Fração", allow_empty=True)
        destination_dir = os.path.join(self.root_path, esquadrao)
        if fracao:
            destination_dir = os.path.join(destination_dir, fracao)
        member_dir = os.path.join(destination_dir, identity)
        self._ensure_destination_available(member_dir)
        os.makedirs(member_dir)
        self._ensure_member_marker(member_dir)
        return member_dir

    def add_photos(self, member_path: str, source_paths: List[str]) -> List[str]:
        self._require_root()
        if not os.path.isdir(member_path):
            raise ValueError("O cadastro precisa ser convertido para o novo formato.")
        self._ensure_member_marker(member_path)
        identity = os.path.basename(member_path)
        next_index = self._next_photo_index(member_path)
        destinations = []
        for offset, source_path in enumerate(source_paths):
            extension = Path(source_path).suffix.lower()
            if extension not in self.VALID_EXTENSIONS or not os.path.isfile(source_path):
                raise ValueError(f"Imagem inválida: {source_path}")
            destination = os.path.join(
                member_path, f"{identity}_{next_index + offset:02d}{extension}"
            )
            self._ensure_destination_available(destination)
            destinations.append(destination)
        copied = []
        try:
            for source, destination in zip(source_paths, destinations):
                shutil.copy2(source, destination)
                copied.append(destination)
        except Exception:
            for destination in copied:
                if os.path.isfile(destination):
                    os.remove(destination)
            raise
        return destinations

    def convert_legacy_member(self, current_path: str) -> str:
        """Converte uma foto antiga após uma ação explícita do usuário."""
        self._require_root()
        if not os.path.isfile(current_path):
            raise FileNotFoundError("A foto antiga não existe mais.")
        identity = Path(current_path).stem
        member_dir = os.path.join(os.path.dirname(current_path), identity)
        self._ensure_destination_available(member_dir)
        os.makedirs(member_dir)
        destination = os.path.join(
            member_dir, f"{identity}_01{Path(current_path).suffix.lower()}"
        )
        try:
            shutil.move(current_path, destination)
            self._ensure_member_marker(member_dir)
        except Exception:
            if os.path.isdir(member_dir) and not os.listdir(member_dir):
                os.rmdir(member_dir)
            raise
        return member_dir

    def set_primary_photo(self, member_path: str, selected_path: str) -> str:
        self._require_root()
        if not os.path.isdir(member_path) or not os.path.isfile(selected_path):
            raise FileNotFoundError("A foto selecionada não existe mais.")
        photos = [
            os.path.join(member_path, name)
            for name in os.listdir(member_path)
            if Path(name).suffix.lower() in self.VALID_EXTENSIONS
        ]
        current = self._primary_photo(sorted(photos, key=self._photo_sort_key))
        if os.path.abspath(current) == os.path.abspath(selected_path):
            return selected_path
        selected_index = self._photo_index(selected_path)
        if selected_index is None:
            raise ValueError("O nome da foto selecionada não segue o padrão esperado.")
        identity = os.path.basename(member_path)
        temporary = os.path.join(member_path, f".{uuid.uuid4().hex}.tmp")
        selected_target = os.path.join(
            member_path, f"{identity}_01{Path(selected_path).suffix.lower()}"
        )
        old_primary_target = os.path.join(
            member_path, f"{identity}_{selected_index:02d}{Path(current).suffix.lower()}"
        )
        os.rename(selected_path, temporary)
        try:
            os.rename(current, old_primary_target)
            os.rename(temporary, selected_target)
        except Exception:
            if os.path.exists(old_primary_target) and not os.path.exists(current):
                os.rename(old_primary_target, current)
            if os.path.exists(temporary) and not os.path.exists(selected_path):
                os.rename(temporary, selected_path)
            raise
        return selected_target

    def delete_photos(self, member_path: str, selected_paths: List[str]) -> None:
        """Exclui fotos selecionadas e promove outra principal quando necessário."""
        self._require_root()
        selected = list(dict.fromkeys(os.path.abspath(path) for path in selected_paths))
        if not selected:
            return

        member_path = os.path.abspath(member_path)
        if os.path.isfile(member_path):
            if selected != [member_path]:
                raise ValueError("A seleção não pertence ao cadastro informado.")
            self._delete_with_staging([(member_path, os.path.basename(member_path))])
            return
        if not os.path.isdir(member_path):
            raise FileNotFoundError("O cadastro não existe mais.")

        photos = [
            os.path.abspath(os.path.join(member_path, name))
            for name in os.listdir(member_path)
            if Path(name).suffix.lower() in self.VALID_EXTENSIONS
        ]
        available = set(photos)
        if any(path not in available for path in selected):
            raise ValueError("Uma ou mais fotos não pertencem a este cadastro.")

        primary = self._primary_photo(sorted(photos, key=self._photo_sort_key))
        remaining = [photo for photo in photos if photo not in set(selected)]
        stage_dir = os.path.join(
            os.path.dirname(member_path), f".delete-{uuid.uuid4().hex}"
        )
        os.makedirs(stage_dir)
        staged: list[tuple[str, str]] = []
        promoted: tuple[str, str] | None = None
        try:
            for photo in selected:
                staged_path = os.path.join(stage_dir, os.path.basename(photo))
                shutil.move(photo, staged_path)
                staged.append((photo, staged_path))

            if primary in selected and remaining:
                candidate = sorted(remaining, key=self._photo_sort_key)[0]
                identity = os.path.basename(member_path)
                new_primary = os.path.join(
                    member_path, f"{identity}_01{Path(candidate).suffix.lower()}"
                )
                if os.path.abspath(candidate) != os.path.abspath(new_primary):
                    self._ensure_destination_available(new_primary)
                    os.rename(candidate, new_primary)
                    promoted = (candidate, new_primary)
        except Exception:
            if promoted and os.path.exists(promoted[1]):
                os.rename(promoted[1], promoted[0])
            for original, staged_path in reversed(staged):
                if os.path.exists(staged_path):
                    shutil.move(staged_path, original)
            if os.path.isdir(stage_dir) and not os.listdir(stage_dir):
                os.rmdir(stage_dir)
            raise

        shutil.rmtree(stage_dir)
        if not remaining and os.path.isdir(member_path):
            self._ensure_member_marker(member_path)

    def delete_member(self, member_path: str) -> None:
        """Exclui permanentemente um cadastro moderno ou uma foto legada."""
        self._require_root()
        member_path = os.path.abspath(member_path)
        root = os.path.abspath(self.root_path)
        if (
            member_path == root
            or os.path.commonpath([root, member_path]) != root
        ):
            raise ValueError("O cadastro informado não pertence à pasta raiz.")
        if not os.path.exists(member_path):
            raise FileNotFoundError("O cadastro não existe mais.")
        if not (os.path.isdir(member_path) or os.path.isfile(member_path)):
            raise ValueError("O caminho informado não é um cadastro válido.")

        parent = os.path.dirname(member_path)
        staged_path = os.path.join(parent, f".delete-{uuid.uuid4().hex}")
        shutil.move(member_path, staged_path)
        try:
            if os.path.isdir(staged_path):
                shutil.rmtree(staged_path)
            else:
                os.remove(staged_path)
        except Exception:
            if os.path.exists(staged_path) and not os.path.exists(member_path):
                shutil.move(staged_path, member_path)
            raise
        self._cleanup_empty_dirs(parent)

    def _delete_with_staging(self, files: List[tuple[str, str]]) -> None:
        parent = os.path.dirname(files[0][0])
        stage_dir = os.path.join(parent, f".delete-{uuid.uuid4().hex}")
        os.makedirs(stage_dir)
        staged = []
        try:
            for original, name in files:
                staged_path = os.path.join(stage_dir, name)
                shutil.move(original, staged_path)
                staged.append((original, staged_path))
        except Exception:
            for original, staged_path in reversed(staged):
                if os.path.exists(staged_path):
                    shutil.move(staged_path, original)
            if os.path.isdir(stage_dir) and not os.listdir(stage_dir):
                os.rmdir(stage_dir)
            raise
        shutil.rmtree(stage_dir)

    def rename_member(self, current_path: str, posto_grad: str, nome_guerra: str) -> str:
        """Altera posto/nome no arquivo físico, mantendo extensão e diretório."""
        self._require_root()
        if not os.path.isfile(current_path):
            raise FileNotFoundError("A foto que seria renomeada não existe mais.")
        filename = self._build_filename(posto_grad, nome_guerra, Path(current_path).suffix.lower())
        destination = os.path.join(os.path.dirname(current_path), filename)
        if os.path.abspath(current_path) == os.path.abspath(destination):
            return destination
        self._ensure_destination_available(destination)
        os.rename(current_path, destination)
        return destination

    def update_member(
        self,
        current_path: str,
        posto_grad: str,
        nome_guerra: str,
        esquadrao: str,
        fracao: str = "",
    ) -> str:
        """Atualiza identificação e localização com uma única movimentação no disco."""
        self._require_root()
        if os.path.isdir(current_path):
            return self._update_member_directory(
                current_path, posto_grad, nome_guerra, esquadrao, fracao
            )
        if not os.path.isfile(current_path):
            raise FileNotFoundError("A foto que seria editada não existe mais.")

        filename = self._build_filename(
            posto_grad, nome_guerra, Path(current_path).suffix.lower()
        )
        esquadrao = self._path_part(esquadrao, "Esquadrão")
        fracao = self._path_part(fracao, "Fração", allow_empty=True)
        destination_dir = os.path.join(self.root_path, esquadrao)
        if fracao:
            destination_dir = os.path.join(destination_dir, fracao)
        destination = os.path.join(destination_dir, filename)

        if os.path.abspath(current_path) == os.path.abspath(destination):
            return destination
        self._ensure_destination_available(destination)
        os.makedirs(destination_dir, exist_ok=True)
        shutil.move(current_path, destination)
        self._cleanup_empty_dirs(os.path.dirname(current_path))
        return destination

    def _update_member_directory(
        self, current_path: str, posto_grad: str, nome_guerra: str,
        esquadrao: str, fracao: str = ""
    ) -> str:
        identity = self._build_identity(posto_grad, nome_guerra)
        esquadrao = self._path_part(esquadrao, "Esquadrão")
        fracao = self._path_part(fracao, "Fração", allow_empty=True)
        destination_dir = os.path.join(self.root_path, esquadrao)
        if fracao:
            destination_dir = os.path.join(destination_dir, fracao)
        destination = os.path.join(destination_dir, identity)
        if os.path.abspath(current_path) != os.path.abspath(destination):
            self._ensure_destination_available(destination)

        photos = sorted(
            [
                os.path.join(current_path, name) for name in os.listdir(current_path)
                if Path(name).suffix.lower() in self.VALID_EXTENSIONS
            ],
            key=self._photo_sort_key,
        )
        targets = []
        for fallback, photo in enumerate(photos, 1):
            index = self._photo_index(photo) or fallback
            targets.append(f"{identity}_{index:02d}{Path(photo).suffix.lower()}")
        if len(set(name.casefold() for name in targets)) != len(targets):
            raise FileExistsError("Há fotos com numeração duplicada neste cadastro.")

        operations = []
        completed_targets = []
        try:
            for photo, target_name in zip(photos, targets):
                temporary = os.path.join(current_path, f".{uuid.uuid4().hex}.tmp")
                os.rename(photo, temporary)
                operations.append((temporary, photo, os.path.join(current_path, target_name)))
            for temporary, _, target in operations:
                os.rename(temporary, target)
                completed_targets.append(target)
            if os.path.abspath(current_path) != os.path.abspath(destination):
                os.makedirs(destination_dir, exist_ok=True)
                shutil.move(current_path, destination)
                self._cleanup_empty_dirs(os.path.dirname(current_path))
            return destination
        except Exception:
            # Restaura os nomes originais caso uma etapa local falhe.
            for temporary, original, target in reversed(operations):
                if target in completed_targets and os.path.exists(target):
                    os.rename(target, original)
                if os.path.exists(temporary) and not os.path.exists(original):
                    os.rename(temporary, original)
            raise

    def _build_filename(self, rank: str, name: str, extension: str) -> str:
        return f"{self._build_identity(rank, name)}{extension}"

    def _build_identity(self, rank: str, name: str) -> str:
        safe_rank = self._filename_part(rank)
        safe_name = self._filename_part(name)
        if not safe_rank or not safe_name:
            raise ValueError("Posto/Graduação e Nome de Guerra são obrigatórios.")
        return f"{safe_rank}_{safe_name}"

    def _next_photo_index(self, member_dir: str) -> int:
        indexes = [
            self._photo_index(os.path.join(member_dir, name))
            for name in os.listdir(member_dir)
            if Path(name).suffix.lower() in self.VALID_EXTENSIONS
        ]
        return max((index for index in indexes if index is not None), default=0) + 1

    @staticmethod
    def _photo_index(path: str) -> int | None:
        match = re.search(r"_([0-9]+)$", Path(path).stem)
        return int(match.group(1)) if match else None

    @staticmethod
    def _filename_part(value: str) -> str:
        clean = " ".join(str(value).strip().split())
        for character in '<>:"/\\|?*':
            clean = clean.replace(character, "-")
        return clean.replace("_", "-").replace(" ", "-")

    @staticmethod
    def _legacy_filename_part(value: str) -> str:
        clean = " ".join(str(value).strip().split())
        for character in '<>:"/\\|?*':
            clean = clean.replace(character, "-")
        return clean.replace(" ", "_")

    @staticmethod
    def _path_part(value: str, label: str, allow_empty: bool = False) -> str:
        clean = " ".join(str(value).strip().split())
        if not clean and allow_empty:
            return ""
        if not clean:
            raise ValueError(f"{label} é obrigatório.")
        if clean in {".", ".."} or any(char in clean for char in "/\\"):
            raise ValueError(f"{label} contém caracteres inválidos.")
        return clean

    @classmethod
    def _ensure_member_marker(cls, member_path: str) -> None:
        marker_path = os.path.join(member_path, cls.MEMBER_MARKER)
        Path(marker_path).touch(exist_ok=True)

    @staticmethod
    def _ensure_destination_available(destination: str) -> None:
        if os.path.exists(destination):
            raise FileExistsError(f"Já existe uma foto com este destino: {destination}")

    def _require_root(self) -> None:
        if not self.root_path:
            raise ValueError("Diretório raiz de trabalho não definido.")

    def _cleanup_empty_dirs(self, path: str) -> None:
        root = os.path.abspath(self.root_path)
        current = os.path.abspath(path)
        while current != root and os.path.commonpath([root, current]) == root:
            if not os.path.isdir(current) or os.listdir(current):
                break
            os.rmdir(current)
            current = os.path.dirname(current)
