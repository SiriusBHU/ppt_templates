"""内置组件注册表：组件名 → Component(render, schema)。"""

from collections.abc import Callable
from dataclasses import dataclass

from . import layered_arch


@dataclass(frozen=True)
class Component:
    render: Callable  # render(slide, style, box, data, props)
    schema: dict      # 组件接受的数据（JSON Schema）；校验器用它检查模板的 example


COMPONENTS = {
    "layered-arch": Component(layered_arch.render, layered_arch.SCHEMA),
}
