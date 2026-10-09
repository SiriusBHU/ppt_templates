"""内置组件注册表：组件名 → render(slide, style, box, data, props)。"""

from .layered_arch import render as _layered_arch

COMPONENTS = {"layered-arch": _layered_arch}
