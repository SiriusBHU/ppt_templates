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
