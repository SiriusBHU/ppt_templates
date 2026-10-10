"""image 元素的图片路径：相对 deck 所在目录解析，检查扩展名、文件是否存在、能否读取，可选限定在某个目录之内。"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .errors import PptError

EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")


@dataclass(frozen=True)
class ImageSource:
    base: Path                    # 相对路径的起点：deck 文件所在目录（模板预览用模板目录）
    confine: Path | None = None   # 给定则解析后的真实路径必须在这个目录之内（MCP 只允许仓库内的图片）

    def resolve(self, value: str) -> Path:
        """图片的真实路径；扩展名不支持、不在 confine 之内、文件不存在或读不出图片时抛 PptError（中文消息）。"""
        shown = f"图片 {value}"
        if Path(value).suffix.lower() not in EXTENSIONS:
            raise PptError(f"{shown} 的格式不支持，只能用 {' / '.join(e.lstrip('.') for e in EXTENSIONS)}")
        try:
            path = (self.base / value).resolve()
            if self.confine is not None and not path.is_relative_to(self.confine.resolve()):
                raise PptError(f"{shown} 不在允许的目录内（只能引用 {self.confine} 之内的文件）")
            if not path.is_file():
                raise PptError(f"{shown} 不存在（相对路径从 {self.base} 起算）")
            if path.suffix.lower() not in EXTENSIONS:  # 符号链接指向了别的文件
                raise PptError(f"{shown} 实际指向 {path.name}，格式不支持")
            with Image.open(path):  # 只读文件头
                pass
        except PptError:
            raise
        except (OSError, ValueError) as e:  # 含 PIL.UnidentifiedImageError、路径里有 NUL
            raise PptError(f"{shown} 无法读取：{e}") from e
        return path
