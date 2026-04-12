import sys, os, chardet
import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent


class DropArea(QLabel):
    filesDropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setText("拖拽CSV文件至此（支持多文件）")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border:2px dashed #aaa; padding:20px;")
        self.setMinimumHeight(100)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
            self.setStyleSheet("border:2px solid #2c8cff; padding:20px;")

    def dragLeaveEvent(self, e):
        self.setStyleSheet("border:2px dashed #aaa; padding:20px;")

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile().endswith('.csv')]
        if paths:
            self.filesDropped.emit(paths)
        self.setStyleSheet("border:2px dashed #aaa; padding:20px;")


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

        self.drop = DropArea()
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

        # 列映射（精简为一行一个）
        map_group = QGroupBox("列名映射（若列名不同请修改）")
        grid = QGridLayout()
        row = 0
        self.cols = {}
        for label, default in [("日期", "数据年月"), ("商品编码", "商品编码"), ("商品名称", "商品名称"),
                               ("贸易伙伴", "贸易伙伴名称"), ("数量", "第一数量"), ("金额", "人民币")]:
            grid.addWidget(QLabel(label), row, 0)
            self.cols[label] = QLineEdit(default)
            grid.addWidget(self.cols[label], row, 1)
            row += 1
        map_group.setLayout(grid)
        layout.addWidget(map_group)

        # 单位转换
        unit_group = QGroupBox("单位转换")
        unit_layout = QHBoxLayout()
        unit_layout.addWidget(QLabel("数量单位:"))
        self.qtyUnit = QComboBox()
        self.qtyUnit.addItems(["千克", "吨", "克", "磅"])
        unit_layout.addWidget(self.qtyUnit)
        unit_layout.addWidget(QLabel("金额单位:"))
        self.moneyUnit = QComboBox()
        self.moneyUnit.addItems(["人民币", "美元", "欧元", "英镑"])
        self.moneyUnit.currentTextChanged.connect(self.setRateHint)
        unit_layout.addWidget(self.moneyUnit)
        unit_layout.addWidget(QLabel("汇率:"))
        self.rateEdit = QLineEdit("0.14")
        self.rateEdit.setFixedWidth(70)
        unit_layout.addWidget(self.rateEdit)
        unit_group.setLayout(unit_layout)
        layout.addWidget(unit_group)

        # 过滤
        filter_group = QGroupBox("商品过滤（留空则不过滤）")
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("保留编码包含:"))
        self.incEdit = QLineEdit()
        filter_layout.addWidget(self.incEdit)
        filter_layout.addWidget(QLabel("排除编码包含:"))
        self.excEdit = QLineEdit()
        filter_layout.addWidget(self.excEdit)
        filter_group.setLayout(filter_layout)
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
        self.setRateHint()

    def setRateHint(self):
        unit = self.moneyUnit.currentText()
        self.rateEdit.setText({"美元": "0.14", "欧元": "0.13", "英镑": "0.11"}.get(unit, "1"))

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

        # 获取映射
        col_date = self.cols["日期"].text().strip()
        col_code = self.cols["商品编码"].text().strip()
        col_name = self.cols["商品名称"].text().strip()
        col_partner = self.cols["贸易伙伴"].text().strip()
        col_qty = self.cols["数量"].text().strip()
        col_amt = self.cols["金额"].text().strip()

        qty_factor = {"千克": 1, "吨": 0.001, "克": 1000, "磅": 2.20462}[self.qtyUnit.currentText()]
        qty_label = self.qtyUnit.currentText()
        rate = float(self.rateEdit.text())
        money_label = self.moneyUnit.currentText()
        inc = [c.strip() for c in self.incEdit.text().split('|') if c.strip()]
        exc = [c.strip() for c in self.excEdit.text().split('|') if c.strip()]
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
                with open(path, 'rb') as f:
                    enc = chardet.detect(f.read(50000))['encoding'] or 'gbk'
                df = pd.read_csv(path, dtype=str, encoding=enc)
            except Exception as e:
                log.append(f"读取失败 {fname}: {e}")
                continue

            orig = len(df)
            total_orig += orig

            # 检查必要列
            if col_qty not in df.columns or col_amt not in df.columns:
                log.append(f"跳过 {fname}: 缺少数量或金额列")
                continue

            # 清洗
            df[col_qty] = df[col_qty].str.replace(',', '').astype(float)
            df[col_amt] = df[col_amt].str.replace(',', '').str.strip('"').astype(float)
            df["数量_清洗后"] = df[col_qty] * qty_factor
            df["金额_清洗后"] = df[col_amt] * rate if money_label != "人民币" else df[col_amt]

            if missing_opt == "填充0":
                df["数量_清洗后"] = df["数量_清洗后"].fillna(0)
                df["金额_清洗后"] = df["金额_清洗后"].fillna(0)
            else:
                df = df.dropna(subset=["数量_清洗后", "金额_清洗后"])

            # 过滤
            if inc or exc:
                if col_code in df.columns:
                    mask = pd.Series([True] * len(df))
                    if inc:
                        mask &= df[col_code].astype(str).str.contains('|'.join(inc), na=False)
                    if exc:
                        mask &= ~df[col_code].astype(str).str.contains('|'.join(exc), na=False)
                    df = df[mask]

            if dedup:
                df = df.drop_duplicates()

            # 保留列
            keep = [c for c in [col_date, col_code, col_name, col_partner] if c in df.columns]
            keep += ["数量_清洗后", "金额_清洗后"]
            df_clean = df[keep].copy()
            df_clean.rename(columns={"数量_清洗后": f"数量({qty_label})", "金额_清洗后": f"金额({money_label})"},
                            inplace=True)

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
            # 商品分组
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
            self.merged.to_csv(path, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, "成功", f"已保存到 {path}")

    def saveSeparate(self):
        if not self.cleaned:
            return
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹")
        if folder:
            for name, df in self.cleaned.items():
                out = os.path.join(folder, os.path.splitext(name)[0] + "_cleaned.csv")
                df.to_csv(out, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, "成功", f"已保存 {len(self.cleaned)} 个文件")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = Cleaner()
    win.show()
    sys.exit(app.exec_())
