#!/usr/bin/env python3
"""
Markdown 实时预览编辑器
依赖: pip install PyQt6 markdown Pygments
"""
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont, QKeySequence, QPalette, QColor
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMainWindow,
    QMessageBox, QSplitter, QStatusBar, QTextEdit, QToolBar, QWidget,
)
import markdown


class MarkdownEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file: str = None
        self.dark_mode: bool = False
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Markdown Editor - 未命名")
        self.setGeometry(100, 100, 1200, 800)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.editor = QTextEdit()
        self.editor.setFont(QFont("Consolas, Menlo, monospace", 13))
        self.editor.setPlaceholderText("# 开始写 Markdown...")
        self.editor.setTabStopDistance(40)

        self._preview_timer = QTimer()
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(300)
        self._preview_timer.timeout.connect(self._update_preview)
        self.editor.textChanged.connect(lambda: self._preview_timer.start())

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("sans-serif", 12))

        splitter.addWidget(self.editor)
        splitter.addWidget(self.preview)
        splitter.setSizes([600, 600])
        self.setCentralWidget(splitter)

        self._create_toolbar()
        self._create_menus()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪")

    def _create_toolbar(self):
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        bold_action = QAction("B", self)
        bold_action.setToolTip("加粗 (Ctrl+B)")
        bold_action.setShortcut(QKeySequence("Ctrl+B"))
        bold_action.triggered.connect(lambda: self._wrap_selection("**", "**"))
        toolbar.addAction(bold_action)

        italic_action = QAction("I", self)
        italic_action.setToolTip("斜体 (Ctrl+I)")
        italic_action.triggered.connect(lambda: self._wrap_selection("*", "*"))
        toolbar.addAction(italic_action)

        code_action = QAction("`", self)
        code_action.setToolTip("行内代码")
        code_action.triggered.connect(lambda: self._wrap_selection("`", "`"))
        toolbar.addAction(code_action)

        toolbar.addSeparator()

        dark_action = QAction("🌙", self)
        dark_action.setToolTip("切换暗黑模式")
        dark_action.triggered.connect(self._toggle_dark_mode)
        toolbar.addAction(dark_action)

    def _create_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件(&F)")

        new_action = QAction("新建(&N)", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_file)
        file_menu.addAction(new_action)

        open_action = QAction("打开(&O)...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        save_action = QAction("保存(&S)", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_action = QAction("导出 HTML...", self)
        export_action.triggered.connect(self._export_html)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("退出(&Q)", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _update_preview(self):
        md_text = self.editor.toPlainText()
        if not md_text.strip():
            self.preview.setHtml("<p style='color:#888;'>预览区域</p>")
            return

        html = markdown.markdown(md_text, extensions=["fenced_code", "tables", "codehilite", "toc", "nl2br"])

        css = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.8;
        }
        code { background: #2c313a; padding: 2px 6px; border-radius: 4px; }
        pre { background: #2c313a; padding: 16px; border-radius: 8px; overflow-x: auto; }
        pre code { background: none; padding: 0; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f0f0f0; }
        blockquote { border-left: 4px solid #3498db; padding-left: 16px; color: #666; }
        """
        if self.dark_mode:
            css += """
            body { background: #1e1e1e; color: #d4d4d4; }
            th { background: #333; }
            th, td { border-color: #444; }
            """

        full_html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
        <style>{css}</style></head><body>{html}</body></html>"""
        self.preview.setHtml(full_html)

        char_count = len(md_text)
        line_count = md_text.count("\n") + 1
        self.status.showMessage(f"字数: {char_count} | 行数: {line_count}")

    def _wrap_selection(self, prefix: str, suffix: str):
        cursor = self.editor.textCursor()
        text = cursor.selectedText()
        cursor.insertText(f"{prefix}{text}{suffix}")

    def _toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
            palette.setColor(QPalette.ColorRole.WindowText, QColor("#d4d4d4"))
            palette.setColor(QPalette.ColorRole.Base, QColor("#252526"))
            palette.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))
            palette.setColor(QPalette.ColorRole.Button, QColor("#3c3c3c"))
            self.setPalette(palette)
        else:
            self.setPalette(QApplication.style().standardPalette())
        self._update_preview()

    def _new_file(self):
        if self._maybe_save():
            self.editor.clear()
            self.current_file = None
            self.setWindowTitle("Markdown Editor - 未命名")

    def _open_file(self):
        if not self._maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开 Markdown 文件", "", "Markdown Files (*.md *.markdown);;All Files (*)"
        )
        if path:
            content = Path(path).read_text(encoding="utf-8")
            self.editor.setPlainText(content)
            self.current_file = path
            self.setWindowTitle(f"Markdown Editor - {os.path.basename(path)}")
            self.status.showMessage(f"已打开: {path}")

    def _save_file(self):
        if self.current_file:
            Path(self.current_file).write_text(self.editor.toPlainText(), encoding="utf-8")
            self.status.showMessage(f"已保存: {self.current_file}", 3000)
            return True
        return self._save_file_as()

    def _save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 Markdown 文件", "", "Markdown Files (*.md);;All Files (*)"
        )
        if path:
            self.current_file = path
            return self._save_file()
        return False

    def _maybe_save(self) -> bool:
        if self.editor.document().isModified():
            ret = QMessageBox.question(
                self, "保存更改", "当前文档已修改，是否保存？",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if ret == QMessageBox.StandardButton.Save:
                return self._save_file()
            elif ret == QMessageBox.StandardButton.Cancel:
                return False
        return True

    def _export_html(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 HTML", "output.html", "HTML Files (*.html *.htm);;All Files (*)")
        if path:
            html = markdown.markdown(
                self.editor.toPlainText(),
                extensions=["fenced_code", "tables", "codehilite", "toc"],
            )
            full = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>Markdown Export</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:auto;padding:20px;line-height:1.8;}}
pre{{background:#f4f4f4;padding:16px;border-radius:8px;}}code{{background:#f4f4f4;padding:2px 6px;}}
table{{border-collapse:collapse;}}td,th{{border:1px solid #ddd;padding:8px;}}</style>
</head><body>{html}</body></html>"""
            Path(path).write_text(full, encoding="utf-8")
            self.status.showMessage(f"已导出: {path}", 3000)

    def closeEvent(self, event):
        if self._maybe_save():
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Markdown Editor")
    editor = MarkdownEditor()
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
