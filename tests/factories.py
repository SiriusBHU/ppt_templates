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


def arch_template():
    """system.solution-arch：分区架构图（partitioned-arch 组件）；左分区每层最多 2 个模块、右分区最多 3 个，另有 1 个共享层。"""
    modules = {"type": "array", "minItems": 1, "maxItems": 4, "items": {
        "type": "object", "required": ["name"],
        "properties": {"name": {"type": "string", "maxLength": 8}, "highlight": {"type": "boolean", "default": False}}}}
    layers = {"type": "array", "minItems": 1, "maxItems": 4, "items": {
        "type": "object", "required": ["name", "modules"],
        "properties": {"name": {"type": "string", "maxLength": 6}, "modules": modules}}}
    template = {
        "id": "system.solution-arch",
        "name": "分区架构图",
        "roles": ["solution"],
        "when_to_use": "测试用：分区架构图",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "arch"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "arch": {
                    "type": "object",
                    "required": ["partitions"],
                    "properties": {
                        "partitions": {"type": "array", "minItems": 2, "maxItems": 3, "items": {
                            "type": "object", "required": ["name", "layers"],
                            "properties": {"name": {"type": "string", "maxLength": 26}, "layers": layers}}},
                        "shared": {"type": "array", "maxItems": 2, "items": {
                            "type": "object", "required": ["name", "modules"],
                            "properties": {"name": {"type": "string", "maxLength": 6}, "modules": modules}}},
                    },
                },
            },
        },
        "layout": [{"type": "component", "component": "partitioned-arch", "box": [0, 0, 664, 452], "bind": "arch",
                    "props": {"legend": "重点模块"}}],
    }
    example = {
        "title": "推理集群架构",
        "arch": {
            "partitions": [
                {"name": "Tool Use (via CPU)", "layers": [
                    {"name": "工具层", "modules": [{"name": "代码沙箱"}, {"name": "搜索服务"}]}]},
                {"name": "Agent Reasoning (via NPU)", "layers": [
                    {"name": "推理层", "modules": [{"name": "Prefill"}, {"name": "Decode"}, {"name": "稀疏注意力", "highlight": True}]}]},
            ],
            "shared": [{"name": "内存池", "modules": [{"name": "HBM 池"}, {"name": "CXL 池", "highlight": True}]}],
        },
    }
    return template, example


def roadmap_template():
    """product.roadmap-lanes：泳道路线图（lane-roadmap 组件）；4 列、2 条泳道（第 1 条有高亮条目和备注）、2 个时代。"""
    template = {
        "id": "product.roadmap-lanes",
        "name": "泳道路线图",
        "roles": ["roadmap"],
        "when_to_use": "测试用：泳道路线图",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "roadmap"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "roadmap": {
                    "type": "object",
                    "required": ["periods", "lanes"],
                    "properties": {
                        "periods": {"type": "array", "minItems": 3, "maxItems": 6, "uniqueItems": True,
                                    "items": {"type": "string", "maxLength": 8}},
                        "lanes": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                            "type": "object", "required": ["name", "items"],
                            "properties": {
                                "name": {"type": "string", "maxLength": 6},
                                "items": {"type": "array", "minItems": 1, "maxItems": 6, "items": {
                                    "type": "object", "required": ["name", "from"],
                                    "properties": {
                                        "name": {"type": "string", "maxLength": 10},
                                        "from": {"type": "string"}, "to": {"type": "string"},
                                        "notes": {"type": "array", "maxItems": 3, "items": {"type": "string", "maxLength": 12}},
                                        "highlight": {"type": "boolean", "default": False}}}}}}},
                        "eras": {"type": "array", "maxItems": 4, "items": {
                            "type": "object", "required": ["name", "from"],
                            "properties": {"name": {"type": "string", "maxLength": 13}, "note": {"type": "string", "maxLength": 10},
                                           "from": {"type": "string"}, "to": {"type": "string"},
                                           "highlight": {"type": "boolean", "default": False}}}},
                    },
                },
            },
        },
        "layout": [{"type": "component", "component": "lane-roadmap", "box": [0, 0, 1216, 560], "bind": "roadmap",
                    "props": {"legend": "本次重点"}}],
    }
    example = {
        "title": "产品路线图",
        "roadmap": {
            "periods": ["2026", "2027", "2028", "2029"],
            "lanes": [
                {"name": "智算", "items": [
                    {"name": "芯片甲", "from": "2026"},
                    {"name": "芯片乙", "from": "2027", "to": "2028", "highlight": True, "notes": ["IP已确定", "SoC待评审"]}]},
                {"name": "存储", "items": [{"name": "控制器", "from": "2026", "to": "2029"}]},
            ],
            "eras": [
                {"name": "旧时代", "from": "2026", "to": "2027"},
                {"name": "新时代", "note": "多智能体", "from": "2028", "to": "2029", "highlight": True},
            ],
        },
    }
    return template, example


def image_template(**image):
    """common.overview-photo：一张图（image 元素，box 400×400）；image 里的键覆盖 image 元素的字段。"""
    template = {
        "id": "common.overview-photo",
        "name": "单图页",
        "roles": ["overview"],
        "when_to_use": "测试用：单张图片",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "photo": {"type": "string", "maxLength": 200},
            },
        },
        "layout": [{"type": "image", "box": [0, 0, 400, 400], "bind": "photo", "placeholder": "放一张示意图", **image}],
    }
    return template, {"title": "单图"}


def rows_template():
    """common.overview-rows：嵌套 grid——外层每行一个领域（标签 + 内层 grid 最多 4 张卡片），行高固定 100。"""
    template = {
        "id": "common.overview-rows",
        "name": "分行卡片",
        "roles": ["overview"],
        "when_to_use": "测试用：grid 里套 grid",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "rows"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "rows": {"type": "array", "minItems": 1, "maxItems": 3, "items": {
                    "type": "object",
                    "required": ["label", "cards"],
                    "properties": {
                        "label": {"type": "string", "maxLength": 6},
                        "cards": {"type": "array", "minItems": 1, "maxItems": 4, "items": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {"name": {"type": "string", "maxLength": 6},
                                           "pic": {"type": "string", "maxLength": 200}}}},
                    },
                }},
            },
        },
        "layout": [{
            "type": "grid", "box": [0, 0, 1000, 320], "bind": "rows", "columns": 1, "gap": 10, "row_height": 100,
            "item": [
                {"type": "text", "box": [0, 0, 100, "100%"], "bind": "label", "style": "body_strong"},
                {"type": "grid", "box": [110, 0, "100%-110", "100%"], "bind": "cards", "columns": 4, "gap": 8, "item": [
                    {"type": "shape", "box": [0, 0, "100%", "100%"], "fill": "surface"},
                    {"type": "text", "box": [4, 4, "100%-8", 20], "bind": "name", "style": "body"},
                    {"type": "text", "box": [4, 30, 20, 20], "bind": "#", "style": "body"},
                    {"type": "image", "box": [4, 54, "100%-8", 40], "bind": "pic", "placeholder": "配图"},
                ]},
            ],
        }],
    }
    example = {"title": "分行", "rows": [
        {"label": "行一", "cards": [{"name": "甲"}]},
        {"label": "行二", "cards": [{"name": "乙"}, {"name": "丙"}, {"name": "丁"}]},
    ]}
    return template, example
