"""内置组件注册表：组件名 → Component(render, schema, props_schema, check)。"""

from collections.abc import Callable
from dataclasses import dataclass

from . import block_diagram, capability_map, lane_roadmap, layered_arch, partitioned_arch, table


def _no_problems(data, box, props=None) -> list:
    return []


@dataclass(frozen=True)
class Component:
    render: Callable        # render(slide, style, box, data, props)
    schema: dict            # 组件接受的数据（JSON Schema）；校验器用它检查 example 和 deck 里被绑定的数据
    props_schema: dict      # layout 里 props 接受的选项（JSON Schema）
    check: Callable = _no_problems
    # check(data, box) -> [(路径, 消息)]：data 已通过 schema 后的语义规则（schema 表达不了的），路径相对 data；box 是元素的 (x, y, w, h)


COMPONENTS = {
    "layered-arch": Component(layered_arch.render, layered_arch.SCHEMA, layered_arch.PROPS_SCHEMA),
    "partitioned-arch": Component(partitioned_arch.render, partitioned_arch.SCHEMA, partitioned_arch.PROPS_SCHEMA,
                                  partitioned_arch.check),
    "lane-roadmap": Component(lane_roadmap.render, lane_roadmap.SCHEMA, lane_roadmap.PROPS_SCHEMA, lane_roadmap.check),
    "capability-map": Component(capability_map.render, capability_map.SCHEMA, capability_map.PROPS_SCHEMA, capability_map.check),
    "table": Component(table.render, table.SCHEMA, table.PROPS_SCHEMA, table.check),
    "block-diagram": Component(block_diagram.render, block_diagram.SCHEMA, block_diagram.PROPS_SCHEMA, block_diagram.check),
}
