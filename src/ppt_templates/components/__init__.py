"""内置组件注册表：组件名 → Component(render, schema)。"""

from collections.abc import Callable
from dataclasses import dataclass

from . import block_diagram, layered_arch, table


@dataclass(frozen=True)
class Component:
    render: Callable  # render(slide, style, box, data, props)
    schema: dict      # 组件接受的数据（JSON Schema）；校验器用它检查模板的 example


COMPONENTS = {
    "layered-arch": Component(layered_arch.render, layered_arch.SCHEMA),
    "table": Component(table.render, table.SCHEMA),
    "block-diagram": Component(block_diagram.render, block_diagram.SCHEMA),
}
