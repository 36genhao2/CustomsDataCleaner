COLUMN_LABEL_DEFAULTS = [
    ("日期", "数据年月"),
    ("商品编码", "商品编码"),
    ("商品名称", "商品名称"),
    ("贸易伙伴", "贸易伙伴名称"),
    ("数量", "第一数量"),
    ("金额", "人民币"),
]

QTY_UNIT_OPTIONS = ["千克", "吨", "克", "磅"]

QTY_FACTORS = {"千克": 1, "吨": 0.001, "克": 1000, "磅": 2.20462}

MONEY_UNIT_OPTIONS = ["人民币", "美元", "欧元", "英镑"]

EXCHANGE_RATE_HINTS = {"美元": "0.14", "欧元": "0.13", "英镑": "0.11"}

MISSING_VALUE_OPTIONS = ["填充0", "删除缺失行"]

REDUNDANT_COLUMN_KEYWORDS = ["计量单位", "第二数量", "第二计量", "Unnamed"]

STYLE_DASHED = "border:2px dashed #aaa; padding:20px;"
STYLE_ACTIVE = "border:2px solid #2c8cff; padding:20px;"
