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
