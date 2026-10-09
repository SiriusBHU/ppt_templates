"""测试用的模板。每个函数返回 (template, example)。"""


def deck_of(template_id: str, data: dict) -> dict:
    return {"style": "default", "pages": [{"template": template_id, "data": data}]}


def mini_template(**overrides):
    """common.summary-note：一句话总结页；overrides 覆盖 template 顶层字段。"""
    template = {
        "id": "common.summary-note",
        "name": "一句话总结",
        "roles": ["summary"],
        "when_to_use": "用一句话总结全文",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "note"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "note": {"type": "string", "maxLength": 60},
            },
        },
        "layout": [{"type": "text", "box": [0, 0, 1216, 80], "bind": "note", "style": "emphasis"}],
    }
    template.update(overrides)
    return template, {"title": "总结", "note": "一句话说清楚结论"}


def bullets_template():
    """common.summary-points：要点列表（bullets 元素）。"""
    template = {
        "id": "common.summary-points",
        "name": "要点总结",
        "roles": ["summary"],
        "when_to_use": "测试用：要点列表",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "points"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "points": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "required": ["text"],
                        "properties": {
                            "text": {"type": "string", "maxLength": 40},
                            "level": {"type": "integer", "minimum": 0, "maximum": 2, "default": 0},
                        },
                    },
                },
            },
        },
        "layout": [{"type": "bullets", "box": [0, 0, 800, 400], "bind": "points", "style": "body"}],
    }
    example = {
        "title": "要点总结",
        "points": [
            {"text": "检查点写入不再阻塞训练"},
            {"text": "先写本地 NVMe，再异步下刷", "level": 1},
            {"text": "恢复时间缩短70%"},
        ],
    }
    return template, example


def table_template():
    """common.overview-table：对比表格（table 组件），高亮推荐列。"""
    template = {
        "id": "common.overview-table",
        "name": "对比表格",
        "roles": ["overview"],
        "when_to_use": "测试用：对比表格",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "matrix"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "matrix": {
                    "type": "object",
                    "required": ["columns", "rows"],
                    "properties": {
                        "columns": {"type": "array", "minItems": 2, "maxItems": 5,
                                    "items": {"type": "string", "maxLength": 8}},
                        "rows": {"type": "array", "minItems": 1, "maxItems": 8,
                                 "items": {"type": "array", "items": {"type": "string", "maxLength": 16}}},
                        "highlight_column": {"type": "integer", "minimum": 0},
                    },
                },
            },
        },
        "layout": [{"type": "component", "component": "table", "box": [0, 0, 1216, 360],
                    "bind": "matrix", "props": {"first_column_width": 200}}],
    }
    example = {
        "title": "存储介质选型",
        "matrix": {
            "columns": ["指标", "SATA SSD", "NVMe SSD", "CXL 内存"],
            "rows": [["带宽", "0.5 GB/s", "7 GB/s", "64 GB/s"],
                     ["延迟", "100 μs", "20 μs", "0.3 μs"],
                     ["单价", "低", "中", "高"]],
            "highlight_column": 2,
        },
    }
    return template, example


def diagram_template():
    """system.solution-flow：数据流框图（block-diagram 组件）。"""
    template = {
        "id": "system.solution-flow",
        "name": "数据流框图",
        "roles": ["solution"],
        "when_to_use": "测试用：数据流框图",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "flow"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "flow": {
                    "type": "object",
                    "required": ["nodes"],
                    "properties": {
                        "nodes": {
                            "type": "array", "minItems": 2, "maxItems": 12,
                            "items": {
                                "type": "object",
                                "required": ["id", "name", "pos"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string", "maxLength": 10},
                                    "pos": {"type": "array", "minItems": 2, "maxItems": 2,
                                            "items": {"type": "integer", "minimum": 0}},
                                    "highlight": {"type": "boolean", "default": False},
                                },
                            },
                        },
                        "edges": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["from", "to"],
                                "properties": {"from": {"type": "string"}, "to": {"type": "string"},
                                               "label": {"type": "string", "maxLength": 8}},
                            },
                        },
                    },
                },
            },
        },
        "layout": [{"type": "component", "component": "block-diagram", "box": [0, 0, 1216, 400], "bind": "flow"}],
    }
    example = {
        "title": "检查点写入路径",
        "flow": {
            "nodes": [
                {"id": "gpu", "name": "训练进程", "pos": [0, 0]},
                {"id": "nvme", "name": "本地 NVMe", "pos": [0, 1], "highlight": True},
                {"id": "store", "name": "存储集群", "pos": [0, 2]},
                {"id": "meta", "name": "元数据服务", "pos": [1, 2]},
            ],
            "edges": [
                {"from": "gpu", "to": "nvme", "label": "同步写"},
                {"from": "nvme", "to": "store", "label": "异步下刷"},
                {"from": "store", "to": "meta"},
            ],
        },
    }
    return template, example


def cards_template(**grid):
    """common.summary-cards：字符串数组排成网格（grid 元素）；grid 里的键覆盖 grid 元素的字段。"""
    template = {
        "id": "common.summary-cards",
        "name": "要点卡片",
        "roles": ["summary"],
        "when_to_use": "测试用：卡片网格",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "cards"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "cards": {"type": "array", "minItems": 1, "maxItems": 6, "items": {"type": "string", "maxLength": 10}},
            },
        },
        "layout": [{"type": "grid", "box": [0, 0, 1200, 400], "bind": "cards", "columns": 4, "gap": 20,
                    "item": [{"type": "text", "box": [0, 0, "100%", "100%"], "bind": ".", "style": "body"}], **grid}],
    }
    return template, {"title": "卡片", "cards": ["甲", "乙"]}
