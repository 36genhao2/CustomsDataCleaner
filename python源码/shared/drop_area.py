import os

from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, pyqtSignal

from .constants import STYLE_DASHED, STYLE_ACTIVE


class DropArea(QLabel):
    """Drag-and-drop area that accepts CSV files and optionally folders."""

    filesDropped = pyqtSignal(list)
    folderDropped = pyqtSignal(str)

    def __init__(self, support_folders=False):
        super().__init__()
        self.setAcceptDrops(True)
        self._support_folders = support_folders
        if support_folders:
            self.setText("拖拽文件或文件夹至此\n（支持多文件/文件夹）")
        else:
            self.setText("拖拽CSV文件至此（支持多文件）")
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(STYLE_DASHED)
        self.setMinimumHeight(100)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
            self.setStyleSheet(STYLE_ACTIVE)

    def dragLeaveEvent(self, e):
        self.setStyleSheet(STYLE_DASHED)

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        files = []
        folders = []
        for url in urls:
            path = url.toLocalFile()
            if os.path.isfile(path) and path.lower().endswith('.csv'):
                files.append(path)
            elif self._support_folders and os.path.isdir(path):
                folders.append(path)
        if files:
            self.filesDropped.emit(files)
        for folder in folders:
            self.folderDropped.emit(folder)
        self.setStyleSheet(STYLE_DASHED)
