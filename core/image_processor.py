import os
import hashlib
import uuid
from PySide6.QtGui import QPixmap, QImageReader
from PySide6.QtGui import QTransform
from PySide6.QtCore import Qt

from core.app_paths import root_cache_dir

class ImageProcessor:
    def rotate_image_file(self, image_path: str, degrees: int = 90) -> None:
        """Gira uma imagem no disco usando substituição atômica do arquivo."""
        if not os.path.isfile(image_path):
            raise FileNotFoundError("A imagem que seria girada não existe mais.")
        normalized_degrees = degrees % 360
        if not normalized_degrees:
            return

        reader = QImageReader(image_path)
        reader.setAutoTransform(True)
        if not reader.canRead():
            raise ValueError("O formato desta imagem não permite rotação.")
        image_format = bytes(reader.format()).decode("ascii", "ignore")
        image = reader.read()
        if image.isNull():
            raise ValueError("Não foi possível carregar a imagem para rotação.")
        rotated = image.transformed(
            QTransform().rotate(normalized_degrees), Qt.SmoothTransformation
        )
        temporary_path = os.path.join(
            os.path.dirname(image_path), f".{uuid.uuid4().hex}.rotate.tmp"
        )
        try:
            quality = 95 if image_format.casefold() in {"jpg", "jpeg", "jfif"} else -1
            if not rotated.save(temporary_path, image_format, quality):
                raise ValueError("Não foi possível gravar a imagem rotacionada.")
            os.replace(temporary_path, image_path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    def get_cache_dir(self, root_path: str) -> str:
        """Usa o diretório de cache padrão do sistema operacional."""
        cache_path = root_cache_dir(root_path)
        os.makedirs(cache_path, exist_ok=True)
        return cache_path

    def get_thumbnail_path(
        self, root_path: str, original_file_path: str, size: int = 150
    ) -> str:
        """Gera um caminho único para a miniatura baseado no caminho relativo do arquivo original."""
        cache_dir = self.get_cache_dir(root_path)
        
        relative_path = os.path.normcase(
            os.path.relpath(os.path.abspath(original_file_path), os.path.abspath(root_path))
        )
        # A versão faz miniaturas antigas, criadas sem orientação EXIF, serem
        # naturalmente substituídas sem precisar apagar o cache do usuário.
        digest = hashlib.sha256(
            f"orientation-v3\0{relative_path}".encode("utf-8")
        ).hexdigest()
        return os.path.join(cache_dir, f"{digest}-{size}.jpg")

    def load_oriented_pixmap(self, image_path: str) -> QPixmap:
        """Carrega a imagem aplicando a orientação registrada pela câmera."""
        reader = QImageReader(image_path)
        reader.setAutoTransform(True)
        if not reader.canRead():
            return QPixmap()
        image = reader.read()
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

    def create_thumbnail(self, root_path: str, original_file_path: str, size: int = 150) -> str:
        """
        Gera uma miniatura otimizada da imagem original e salva no cache.
        Retorna o caminho para a miniatura gerada.
        """
        cached_path = self.get_cached_thumbnail(root_path, original_file_path, size)
        if cached_path:
            return cached_path
        thumb_path = self.get_thumbnail_path(root_path, original_file_path, size)
        try:
            source_mtime = os.path.getmtime(original_file_path)
        except OSError:
            return ""

        # QImageReader é extremamente rápido porque ele lê apenas o tamanho antes de carregar toda a imagem na RAM
        reader = QImageReader(original_file_path)
        reader.setAutoTransform(True)
        if not reader.canRead():
            return "" # Retorna vazio caso o arquivo não seja uma imagem válida

        # Calcula a proporção mantendo o aspecto da foto
        orig_size = reader.size()
        orig_width = orig_size.width()
        orig_height = orig_size.height()
        if orig_width <= 0 or orig_height <= 0:
            return ""

        if orig_width > orig_height:
            new_width = size
            new_height = int((orig_height * size) / orig_width)
        else:
            new_height = size
            new_width = int((orig_width * size) / orig_height)

        reader.setScaledSize(orig_size.scaled(new_width, new_height, Qt.KeepAspectRatio))
        image = reader.read()

        if not image.isNull():
            try:
                if os.path.getmtime(original_file_path) != source_mtime:
                    return ""
            except OSError:
                return ""
            temporary_path = f"{thumb_path}.{uuid.uuid4().hex}.tmp"
            try:
                if not image.save(temporary_path, "JPG", 80):
                    return ""
                if os.path.getmtime(original_file_path) != source_mtime:
                    return ""
                os.replace(temporary_path, thumb_path)
                return thumb_path
            except OSError:
                return ""
            finally:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)

        return ""

    def get_cached_thumbnail(
        self, root_path: str, original_file_path: str, size: int = 150
    ) -> str:
        """Retorna somente um cache válido, sem decodificar a imagem original."""
        if not os.path.isfile(original_file_path):
            return ""
        thumb_path = self.get_thumbnail_path(root_path, original_file_path, size)
        try:
            if (
                os.path.isfile(thumb_path)
                and os.path.getmtime(thumb_path) >= os.path.getmtime(original_file_path)
            ):
                return thumb_path
        except OSError:
            return ""
        return ""

    def invalidate_thumbnail(self, root_path: str, original_file_path: str) -> None:
        """Remove do cache a miniatura ligada a um caminho antigo."""
        if not root_path:
            return
        cache_dir = self.get_cache_dir(root_path)
        relative_path = os.path.normcase(
            os.path.relpath(os.path.abspath(original_file_path), os.path.abspath(root_path))
        )
        digest = hashlib.sha256(
            f"orientation-v3\0{relative_path}".encode("utf-8")
        ).hexdigest()
        for filename in os.listdir(cache_dir):
            if filename.startswith(f"{digest}-") and filename.endswith(".jpg"):
                try:
                    os.remove(os.path.join(cache_dir, filename))
                except OSError:
                    pass

    def refresh_thumbnail(self, root_path: str, original_file_path: str, size: int = 150) -> str:
        """Força a recriação de uma miniatura após uma edição."""
        self.invalidate_thumbnail(root_path, original_file_path)
        return self.create_thumbnail(root_path, original_file_path, size)
