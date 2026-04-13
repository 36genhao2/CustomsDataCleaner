import sys
import os
import chardet
import pandas as pd
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

class DropArea(QLabel):
    filesDropped = pyqtSignal(list)
    folderDropped = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setText("拖拽文件或文件夹至此\n（支持多文件/文件夹）")
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
        urls = e.mimeData().urls()
        files = []
        folders = []
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path) and path.lower().endswith('.csv'):
                files.append(path)
            elif os.path.isdir(path):
                folders.append(path)
        if files:
            self.filesDropped.emit(files)
        for folder in folders:
            self.folderDropped.emit(folder)
        self.setStyleSheet("border:2px dashed #aaa; padding:20px;")

class CustomsCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("海关总署数据清洗工具")
        self.setGeometry(200, 100, 1200, 800)
        self.file_paths = []
        self.df = None
        self.sort_rows = []
        self.initUI()
    
    def initUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        self.drop = DropArea()
        self.drop.filesDropped.connect(self.addFiles)
        self.drop.folderDropped.connect(self.addFolder)
        layout.addWidget(self.drop)
        
        btn_row = QHBoxLayout()
        self.addFileBtn = QPushButton("添加CSV文件")
        self.addFileBtn.clicked.connect(self.selectFiles)
        btn_row.addWidget(self.addFileBtn)
        self.addFolderBtn = QPushButton("添加文件夹")
        self.addFolderBtn.clicked.connect(self.selectFolder)
        btn_row.addWidget(self.addFolderBtn)
        self.clearBtn = QPushButton("清空列表")
        self.clearBtn.clicked.connect(self.clearAll)
        btn_row.addWidget(self.clearBtn)
        self.fileLabel = QLabel("未选择文件")
        btn_row.addWidget(self.fileLabel)
        layout.addLayout(btn_row)
        
        map_group = QGroupBox("列名映射（根据实际CSV修改）")
        grid = QGridLayout()
        self.col_maps = {}
        labels = [("日期", "数据年月"), ("商品编码", "商品编码"), ("商品名称", "商品名称"),
                  ("贸易伙伴", "贸易伙伴名称"), ("数量", "第一数量"), ("金额", "人民币")]
        for i, (label, default) in enumerate(labels):
            grid.addWidget(QLabel(label), i, 0)
            self.col_maps[label] = QLineEdit(default)
            grid.addWidget(self.col_maps[label], i, 1)
        map_group.setLayout(grid)
        layout.addWidget(map_group)
        
        unit_group = QGroupBox("单位转换")
        unit_layout = QHBoxLayout()
        unit_layout.addWidget(QLabel("数量单位:"))
        self.qty_unit = QComboBox()
        self.qty_unit.addItems(["千克", "吨", "克", "磅"])
        unit_layout.addWidget(self.qty_unit)
        unit_layout.addWidget(QLabel("金额单位:"))
        self.money_unit = QComboBox()
        self.money_unit.addItems(["人民币", "美元", "欧元", "英镑"])
        self.money_unit.currentTextChanged.connect(self.updateRate)
        unit_layout.addWidget(self.money_unit)
        unit_layout.addWidget(QLabel("汇率:"))
        self.rate_edit = QLineEdit("0.14")
        self.rate_edit.setFixedWidth(70)
        unit_layout.addWidget(self.rate_edit)
        unit_group.setLayout(unit_layout)
        layout.addWidget(unit_group)
        
        dec_group = QGroupBox("小数位数")
        dec_layout = QHBoxLayout()
        dec_layout.addWidget(QLabel("数量:"))
        self.qty_dec = QSpinBox()
        self.qty_dec.setRange(0,6)
        self.qty_dec.setValue(2)
        dec_layout.addWidget(self.qty_dec)
        dec_layout.addWidget(QLabel("金额:"))
        self.amt_dec = QSpinBox()
        self.amt_dec.setRange(0,6)
        self.amt_dec.setValue(2)
        dec_layout.addWidget(self.amt_dec)
        dec_group.setLayout(dec_layout)
        layout.addWidget(dec_group)
        
        filter_group = QGroupBox("商品过滤（留空则不过滤）")
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("保留编码包含:"))
        self.inc_code = QLineEdit()
        filter_layout.addWidget(self.inc_code)
        filter_layout.addWidget(QLabel("排除编码包含:"))
        self.exc_code = QLineEdit()
        filter_layout.addWidget(self.exc_code)
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        clean_group = QGroupBox("清洗选项")
        clean_layout = QHBoxLayout()
        self.dedup_cb = QCheckBox("去重")
        self.dedup_cb.setChecked(True)
        clean_layout.addWidget(self.dedup_cb)
        clean_layout.addWidget(QLabel("缺失值:"))
        self.missing_cb = QComboBox()
        self.missing_cb.addItems(["填充0", "删除缺失行"])
        clean_layout.addWidget(self.missing_cb)
        clean_group.setLayout(clean_layout)
        layout.addWidget(clean_group)
        
        self.clean_btn = QPushButton("1. 清洗并合并所有文件")
        self.clean_btn.clicked.connect(self.cleanAndMerge)
        self.clean_btn.setEnabled(False)
        layout.addWidget(self.clean_btn)
        
        sort_group = QGroupBox("2. 多级排序（清洗后操作）")
        sort_layout = QVBoxLayout()
        self.sort_container = QWidget()
        self.sort_container_layout = QVBoxLayout(self.sort_container)
        self.sort_container_layout.setContentsMargins(0, 0, 0, 0)
        self.addSortRow()
        self.add_sort_btn = QPushButton("+ 添加排序条件（最多3级）")
        self.add_sort_btn.clicked.connect(self.addSortRow)
        sort_layout.addWidget(self.sort_container)
        sort_layout.addWidget(self.add_sort_btn)
        self.sort_btn = QPushButton("应用排序")
        self.sort_btn.clicked.connect(self.applyMultiSort)
        self.sort_btn.setEnabled(False)
        sort_layout.addWidget(self.sort_btn)
        sort_group.setLayout(sort_layout)
        layout.addWidget(sort_group)
        
        del_group = QGroupBox("删除列（多选）")
        del_layout = QHBoxLayout()
        self.del_cols = QListWidget()
        self.del_cols.setSelectionMode(QAbstractItemView.MultiSelection)
        self.del_cols.setMaximumHeight(80)
        del_layout.addWidget(self.del_cols)
        self.del_btn = QPushButton("删除选中列")
        self.del_btn.clicked.connect(self.deleteColumns)
        self.del_btn.setEnabled(False)
        del_layout.addWidget(self.del_btn)
        del_group.setLayout(del_layout)
        layout.addWidget(del_group)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        self.detail_view = QTextEdit()
        self.detail_view.setReadOnly(True)
        layout.addWidget(QLabel("清洗后明细（前100行）"))
        layout.addWidget(self.detail_view)
        
        self.save_detail = QPushButton("保存当前明细")
        self.save_detail.clicked.connect(self.saveDetail)
        self.save_detail.setEnabled(False)
        layout.addWidget(self.save_detail)
        
        self.statusBar().showMessage("就绪")
        self.updateRate()
    
    def updateRate(self):
        unit = self.money_unit.currentText()
        self.rate_edit.setText({"美元":"0.14","欧元":"0.13","英镑":"0.11"}.get(unit,"1"))
    
    def addSortRow(self):
        if len(self.sort_rows) >= 3:
            QMessageBox.information(self, "提示", "最多支持3级排序")
            return
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        level_label = QLabel(f"第{len(self.sort_rows)+1}排序:")
        col_combo = QComboBox()
        col_combo.setEditable(True)
        asc_check = QCheckBox("升序")
        asc_check.setChecked(True)
        remove_btn = QPushButton("移除")
        remove_btn.clicked.connect(lambda: self.removeSortRow(row_widget))
        row_layout.addWidget(level_label)
        row_layout.addWidget(col_combo)
        row_layout.addWidget(asc_check)
        row_layout.addWidget(remove_btn)
        self.sort_container_layout.addWidget(row_widget)
        self.sort_rows.append({
            'widget': row_widget,
            'combo': col_combo,
            'asc': asc_check
        })
        if self.df is not None:
            self.refreshSortCombos()
    
    def removeSortRow(self, widget):
        for i, row in enumerate(self.sort_rows):
            if row['widget'] is widget:
                widget.deleteLater()
                self.sort_rows.pop(i)
                for idx, r in enumerate(self.sort_rows):
                    r['widget'].layout().itemAt(0).widget().setText(f"第{idx+1}排序:")
                break
    
    def refreshSortCombos(self):
        if self.df is None:
            return
        cols = list(self.df.columns)
        for row in self.sort_rows:
            current = row['combo'].currentText()
            row['combo'].clear()
            row['combo'].addItems(cols)
            if current in cols:
                row['combo'].setCurrentText(current)
    
    def selectFiles(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择CSV文件", "", "CSV (*.csv)")
        if paths:
            self.addFiles(paths)
    
    def selectFolder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.addFolder(folder)
    
    def addFolder(self, folder):
        paths = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                if f.lower().endswith('.csv'):
                    paths.append(os.path.join(root, f))
        if paths:
            self.addFiles(paths)
            self.statusBar().showMessage(f"从文件夹添加了 {len(paths)} 个文件")
        else:
            QMessageBox.information(self, "提示", "文件夹中没有CSV文件")
    
    def addFiles(self, paths):
        for p in paths:
            if p not in self.file_paths:
                self.file_paths.append(p)
        self.fileLabel.setText(f"{len(self.file_paths)} 个文件")
        self.clean_btn.setEnabled(True)
    
    def clearAll(self):
        self.file_paths.clear()
        self.df = None
        self.fileLabel.setText("未选择文件")
        self.clean_btn.setEnabled(False)
        self.sort_btn.setEnabled(False)
        self.del_btn.setEnabled(False)
        self.save_detail.setEnabled(False)
        self.detail_view.clear()
        self.del_cols.clear()
        for row in self.sort_rows:
            row['widget'].deleteLater()
        self.sort_rows.clear()
        self.addSortRow()
        self.statusBar().showMessage("已清空")
    
    def cleanAndMerge(self):
        if not self.file_paths:
            QMessageBox.warning(self, "提示", "请先添加文件")
            return
        
        col_date = self.col_maps["日期"].text().strip()
        col_code = self.col_maps["商品编码"].text().strip()
        col_name = self.col_maps["商品名称"].text().strip()
        col_partner = self.col_maps["贸易伙伴"].text().strip()
        col_qty = self.col_maps["数量"].text().strip()
        col_amt = self.col_maps["金额"].text().strip()
        
        qty_factor = {"千克":1, "吨":0.001, "克":1000, "磅":2.20462}[self.qty_unit.currentText()]
        qty_label = self.qty_unit.currentText()
        rate = float(self.rate_edit.text())
        money_label = self.money_unit.currentText()
        qty_dec = self.qty_dec.value()
        amt_dec = self.amt_dec.value()
        inc_list = [c.strip() for c in self.inc_code.text().split('|') if c.strip()]
        exc_list = [c.strip() for c in self.exc_code.text().split('|') if c.strip()]
        dedup = self.dedup_cb.isChecked()
        missing_opt = self.missing_cb.currentText()
        
        self.clean_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(self.file_paths))
        
        all_dfs = []
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
            
            if col_qty not in df.columns or col_amt not in df.columns:
                log.append(f"跳过 {fname}: 缺少数量或金额列")
                continue
            
            df[col_qty] = df[col_qty].str.replace(',', '').astype(float)
            df["数量_清洗后"] = df[col_qty] * qty_factor
            df[col_amt] = df[col_amt].str.replace(',', '').str.strip('"').astype(float)
            df["金额_清洗后"] = df[col_amt] * rate if money_label != "人民币" else df[col_amt]
            df["数量_清洗后"] = df["数量_清洗后"].round(qty_dec)
            df["金额_清洗后"] = df["金额_清洗后"].round(amt_dec)
            
            if missing_opt == "填充0":
                df["数量_清洗后"] = df["数量_清洗后"].fillna(0)
                df["金额_清洗后"] = df["金额_清洗后"].fillna(0)
            else:
                df = df.dropna(subset=["数量_清洗后", "金额_清洗后"])
            
            if inc_list or exc_list:
                if col_code in df.columns:
                    mask = pd.Series([True]*len(df))
                    if inc_list:
                        mask &= df[col_code].astype(str).str.contains('|'.join(inc_list), na=False)
                    if exc_list:
                        mask &= ~df[col_code].astype(str).str.contains('|'.join(exc_list), na=False)
                    df = df[mask]
            
            if dedup:
                df = df.drop_duplicates()
            
            df.rename(columns={"数量_清洗后": f"数量({qty_label})", "金额_清洗后": f"金额({money_label})"}, inplace=True)
            all_dfs.append(df)
            clean = len(df)
            total_clean += clean
            log.append(f"{fname}: {orig} -> {clean}")
        
        self.progress.setValue(len(self.file_paths))
        
        if all_dfs:
            self.df = pd.concat(all_dfs, ignore_index=True)
            
            # 删除原始数量和金额列
            if col_qty in self.df.columns:
                self.df = self.df.drop(columns=[col_qty])
            if col_amt in self.df.columns:
                self.df = self.df.drop(columns=[col_amt])
            
            # 删除冗余列
            redundant_keywords = ['计量单位', '第二数量', '第二计量', 'Unnamed']
            cols_to_drop = []
            for col in self.df.columns:
                for kw in redundant_keywords:
                    if kw in col:
                        cols_to_drop.append(col)
                        break
            if cols_to_drop:
                self.df = self.df.drop(columns=cols_to_drop)
            
            # 默认按日期排序
            if col_date in self.df.columns:
                self.df['__sort_date'] = pd.to_datetime(self.df[col_date], format='%Y%m', errors='coerce')
                self.df = self.df.sort_values('__sort_date').reset_index(drop=True)
                self.df = self.df.drop(columns=['__sort_date'])
            
            self.detail_view.setText(self.df.head(100).to_string())
            stats = f"\n\n清洗完成！共处理 {len(all_dfs)} 个文件\n原始总行数: {total_orig}\n清洗后总行数: {total_clean}\n"
            self.detail_view.append(stats)
            
            self.del_cols.clear()
            for col in self.df.columns:
                self.del_cols.addItem(col)
            
            self.refreshSortCombos()
            self.sort_btn.setEnabled(True)
            self.del_btn.setEnabled(True)
            self.save_detail.setEnabled(True)
            self.statusBar().showMessage("清洗合并完成")
        else:
            QMessageBox.warning(self, "警告", "没有成功清洗任何文件")
        
        self.clean_btn.setEnabled(True)
        self.progress.setVisible(False)
    
    def applyMultiSort(self):
        if self.df is None:
            return
        sort_list = []
        for row in self.sort_rows:
            col = row['combo'].currentText()
            if col:
                sort_list.append((col, row['asc'].isChecked()))
        if not sort_list:
            QMessageBox.warning(self, "提示", "请至少设置一个排序列")
            return
        try:
            by = [col for col, asc in sort_list]
            ascending = [asc for col, asc in sort_list]
            self.df = self.df.sort_values(by=by, ascending=ascending).reset_index(drop=True)
            self.detail_view.setText(self.df.head(100).to_string())
            self.statusBar().showMessage(f"已按 {', '.join(by)} 排序")
        except Exception as e:
            QMessageBox.warning(self, "排序错误", str(e))
    
    def deleteColumns(self):
        if self.df is None:
            return
        selected = [item.text() for item in self.del_cols.selectedItems()]
        if not selected:
            QMessageBox.warning(self, "提示", "请选择要删除的列")
            return
        self.df = self.df.drop(columns=selected)
        self.del_cols.clear()
        for col in self.df.columns:
            self.del_cols.addItem(col)
        self.refreshSortCombos()
        self.detail_view.setText(self.df.head(100).to_string())
        self.statusBar().showMessage(f"已删除列: {', '.join(selected)}")
    
    def saveDetail(self):
        if self.df is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存当前明细", "cleaned_data.csv", "CSV (*.csv)")
        if path:
            self.df.to_csv(path, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, "成功", f"已保存到 {path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = CustomsCleaner()
    win.show()
    sys.exit(app.exec_())
