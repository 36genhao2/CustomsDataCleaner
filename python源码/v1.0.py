import sys
import os

import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt

from shared.constants import QTY_FACTORS
from shared.csv_utils import read_csv_auto_encoding, save_csv_bom
from shared.cleaning import clean_single_file, rename_cleaned_columns
from shared.drop_area import DropArea
from shared.ui_helpers import (
    build_column_mapping_group,
    build_unit_conversion_group,
    build_filter_group,
    update_rate_from_unit,
    get_column_mappings,
    parse_filter_list,
)


class Cleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("海关数据清洗工具")
        self.setGeometry(300, 150, 900, 700)
        self.file_paths = []
        self.cleaned = {}
        self.merged = None
        self.initUI()

    def initUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.drop = DropArea(support_folders=False)
        self.drop.filesDropped.connect(self.addFiles)
        layout.addWidget(self.drop)

        btn_row = QHBoxLayout()
        self.addBtn = QPushButton("添加CSV")
        self.addBtn.clicked.connect(self.selectFiles)
        btn_row.addWidget(self.addBtn)
        self.clearBtn = QPushButton("清空列表")
        self.clearBtn.clicked.connect(self.clearFiles)
        btn_row.addWidget(self.clearBtn)
        self.fileLabel = QLabel("未选择文件")
        btn_row.addWidget(self.fileLabel)
        layout.addLayout(btn_row)

        map_group, self.cols = build_column_mapping_group()
        layout.addWidget(map_group)

        unit_group, self.qtyUnit, self.moneyUnit, self.rateEdit = \
            build_unit_conversion_group(self._onRateChanged)
        layout.addWidget(unit_group)

        filter_group, self.incEdit, self.excEdit = build_filter_group()
        layout.addWidget(filter_group)

        # 清洗选项
        clean_group = QGroupBox("清洗选项")
        opt_layout = QHBoxLayout()
        self.dedup = QCheckBox("去重")
        self.dedup.setChecked(True)
        opt_layout.addWidget(self.dedup)
        opt_layout.addWidget(QLabel("缺失值:"))
        self.missing = QComboBox()
        self.missing.addItems(["填充0", "删除缺失行"])
        opt_layout.addWidget(self.missing)
        self.mergeCheck = QCheckBox("合并所有文件")
        self.mergeCheck.setChecked(True)
        opt_layout.addWidget(self.mergeCheck)
        clean_group.setLayout(opt_layout)
        layout.addWidget(clean_group)

        self.processBtn = QPushButton("开始清洗并统计")
        self.processBtn.clicked.connect(self.runClean)
        self.processBtn.setEnabled(False)
        layout.addWidget(self.processBtn)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.stats = QTextEdit()
        self.stats.setReadOnly(True)
        layout.addWidget(QLabel("统计结果"))
        layout.addWidget(self.stats)

        save_row = QHBoxLayout()
        self.saveMergeBtn = QPushButton("保存合并数据")
        self.saveMergeBtn.clicked.connect(self.saveMerged)
        self.saveMergeBtn.setEnabled(False)
        save_row.addWidget(self.saveMergeBtn)
        self.saveSepBtn = QPushButton("分别保存每个文件")
        self.saveSepBtn.clicked.connect(self.saveSeparate)
        self.saveSepBtn.setEnabled(False)
        save_row.addWidget(self.saveSepBtn)
        layout.addLayout(save_row)

        self.statusBar().showMessage("就绪")
        update_rate_from_unit(self.moneyUnit, self.rateEdit)

    def _onRateChanged(self):
        update_rate_from_unit(self.moneyUnit, self.rateEdit)

    def selectFiles(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择CSV", "", "CSV (*.csv)")
        if paths:
            self.addFiles(paths)

    def addFiles(self, paths):
        self.file_paths.extend(paths)
        self.file_paths = list(dict.fromkeys(self.file_paths))
        self.fileLabel.setText(f"{len(self.file_paths)} 个文件")
        self.processBtn.setEnabled(True)

    def clearFiles(self):
        self.file_paths.clear()
        self.fileLabel.setText("未选择文件")
        self.processBtn.setEnabled(False)
        self.stats.clear()
        self.saveMergeBtn.setEnabled(False)
        self.saveSepBtn.setEnabled(False)

    def runClean(self):
        if not self.file_paths:
            QMessageBox.warning(self, "提示", "请先添加文件")
            return

        col_map = get_column_mappings(self.cols)
        col_date = col_map["日期"]
        col_code = col_map["商品编码"]
        col_name = col_map["商品名称"]
        col_partner = col_map["贸易伙伴"]
        col_qty = col_map["数量"]
        col_amt = col_map["金额"]

        qty_factor = QTY_FACTORS[self.qtyUnit.currentText()]
        qty_label = self.qtyUnit.currentText()
        rate = float(self.rateEdit.text())
        money_label = self.moneyUnit.currentText()
        inc = parse_filter_list(self.incEdit.text())
        exc = parse_filter_list(self.excEdit.text())
        dedup = self.dedup.isChecked()
        missing_opt = self.missing.currentText()

        self.processBtn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.file_paths))
        self.cleaned.clear()

        total_orig = 0
        total_clean = 0
        log = []

        for i, path in enumerate(self.file_paths):
            self.progress.setValue(i)
            QApplication.processEvents()
            fname = os.path.basename(path)
            try:
                df, _enc = read_csv_auto_encoding(path)
            except Exception as e:
                log.append(f"读取失败 {fname}: {e}")
                continue

            orig = len(df)
            total_orig += orig

            df = clean_single_file(
                df, col_qty, col_amt, qty_factor, rate, money_label,
                missing_opt, col_code, inc, exc, dedup,
            )
            if df is None:
                log.append(f"跳过 {fname}: 缺少数量或金额列")
                continue

            keep = [c for c in [col_date, col_code, col_name, col_partner] if c in df.columns]
            keep += ["数量_清洗后", "金额_清洗后"]
            df_clean = rename_cleaned_columns(df[keep].copy(), qty_label, money_label)

            self.cleaned[fname] = df_clean
            clean = len(df_clean)
            total_clean += clean
            log.append(f"{fname}: {orig} -> {clean}")

        # 合并与统计
        if self.mergeCheck.isChecked() and self.cleaned:
            self.merged = pd.concat(self.cleaned.values(), ignore_index=True)
            merge_stats = f"\n合并总计: 文件数={len(self.cleaned)}, 原始={total_orig}, 清洗后={total_clean}\n"
            qty_col = f"数量({qty_label})"
            amt_col = f"金额({money_label})"
            if qty_col in self.merged.columns:
                q = self.merged[qty_col]
                merge_stats += f"数量总计: {q.sum():,.2f} {qty_label}, 均值: {q.mean():,.2f}\n"
            if amt_col in self.merged.columns:
                a = self.merged[amt_col]
                merge_stats += f"金额总计: {a.sum():,.2f} {money_label}, 均值: {a.mean():,.2f}\n"
            if col_code in self.merged.columns and amt_col in self.merged.columns:
                merge_stats += "\n商品编码金额前10:\n"
                group = self.merged.groupby(col_code)[amt_col].sum().sort_values(ascending=False).head(10)
                for code, val in group.items():
                    merge_stats += f"  {code}: {val:,.2f} {money_label}\n"
            log.append(merge_stats)
            self.saveMergeBtn.setEnabled(True)
        else:
            self.merged = None
            self.saveMergeBtn.setEnabled(False)

        self.saveSepBtn.setEnabled(bool(self.cleaned))
        self.stats.setText("\n".join(log))
        self.statusBar().showMessage("清洗完成")
        self.processBtn.setEnabled(True)
        self.progress.setVisible(False)

    def saveMerged(self):
        if self.merged is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存合并数据", "merged.csv", "CSV (*.csv)")
        if path:
            save_csv_bom(self.merged, path)
            QMessageBox.information(self, "成功", f"已保存到 {path}")

    def saveSeparate(self):
        if not self.cleaned:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
        if folder:
            for name, df in self.cleaned.items():
                out = os.path.join(folder, os.path.splitext(name)[0] + "_cleaned.csv")
                save_csv_bom(df, out)
            QMessageBox.information(self, "成功", f"已保存 {len(self.cleaned)} 个文件")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Cleaner()
    win.show()
    sys.exit(app.exec_())
