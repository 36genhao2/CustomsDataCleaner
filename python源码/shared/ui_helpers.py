from PyQt5.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
)

from .constants import (
    COLUMN_LABEL_DEFAULTS,
    QTY_UNIT_OPTIONS,
    MONEY_UNIT_OPTIONS,
    EXCHANGE_RATE_HINTS,
)


def build_column_mapping_group(title="列名映射（若列名不同请修改）"):
    """Build the column-name mapping QGroupBox.

    Returns (group_widget, col_edits_dict) where col_edits_dict maps
    label -> QLineEdit.
    """
    group = QGroupBox(title)
    grid = QGridLayout()
    col_edits = {}
    for i, (label, default) in enumerate(COLUMN_LABEL_DEFAULTS):
        grid.addWidget(QLabel(label), i, 0)
        edit = QLineEdit(default)
        col_edits[label] = edit
        grid.addWidget(edit, i, 1)
    group.setLayout(grid)
    return group, col_edits


def build_unit_conversion_group(rate_changed_callback):
    """Build the unit-conversion QGroupBox.

    Returns (group_widget, qty_combo, money_combo, rate_edit).
    """
    group = QGroupBox("单位转换")
    layout = QHBoxLayout()
    layout.addWidget(QLabel("数量单位:"))
    qty_combo = QComboBox()
    qty_combo.addItems(QTY_UNIT_OPTIONS)
    layout.addWidget(qty_combo)

    layout.addWidget(QLabel("金额单位:"))
    money_combo = QComboBox()
    money_combo.addItems(MONEY_UNIT_OPTIONS)
    money_combo.currentTextChanged.connect(rate_changed_callback)
    layout.addWidget(money_combo)

    layout.addWidget(QLabel("汇率:"))
    rate_edit = QLineEdit("0.14")
    rate_edit.setFixedWidth(70)
    layout.addWidget(rate_edit)

    group.setLayout(layout)
    return group, qty_combo, money_combo, rate_edit


def build_filter_group():
    """Build the product-code filter QGroupBox.

    Returns (group_widget, inc_edit, exc_edit).
    """
    group = QGroupBox("商品过滤（留空则不过滤）")
    layout = QHBoxLayout()
    layout.addWidget(QLabel("保留编码包含:"))
    inc_edit = QLineEdit()
    layout.addWidget(inc_edit)
    layout.addWidget(QLabel("排除编码包含:"))
    exc_edit = QLineEdit()
    layout.addWidget(exc_edit)
    group.setLayout(layout)
    return group, inc_edit, exc_edit


def update_rate_from_unit(money_combo, rate_edit):
    """Update the rate QLineEdit based on the current money unit selection."""
    unit = money_combo.currentText()
    rate_edit.setText(EXCHANGE_RATE_HINTS.get(unit, "1"))


def get_column_mappings(col_edits):
    """Extract stripped column name strings from the mapping edits dict."""
    return {label: edit.text().strip() for label, edit in col_edits.items()}


def parse_filter_list(text):
    """Split a pipe-separated filter string into a list of stripped tokens."""
    return [c.strip() for c in text.split('|') if c.strip()]
