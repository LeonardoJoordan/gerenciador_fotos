import hashlib
import os

from PySide6.QtCore import QStandardPaths


def root_key(root_path: str) -> str:
    """Identificador estável para separar os dados de cada pasta de fotos."""
    normalized = os.path.normcase(os.path.realpath(os.path.abspath(root_path)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def root_config_dir(root_path: str) -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
    if not base:
        raise OSError("O sistema não informou um diretório de configuração válido.")
    return os.path.join(base, "photo-roots", root_key(root_path))


def root_cache_dir(root_path: str) -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
    if not base:
        raise OSError("O sistema não informou um diretório de cache válido.")
    return os.path.join(base, "photo-roots", root_key(root_path), "thumbnails")
