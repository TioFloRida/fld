import sys
import os
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLineEdit, QPushButton, QLabel,
    QFileDialog, QSplitter, QMessageBox, QStatusBar
)

from pyside6_scintilla import ScintillaEdit


class LoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(245, 247, 250, 160);")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.label = QLabel("Loading file…\nPlease wait")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(
            "color:#2b2f38;"
            "font-size:16px;"
            "font-weight:600;"
            "background-color: rgba(255, 255, 255, 235);"
            "border: 1px solid #d7dbe0;"
            "border-radius: 10px;"
            "padding: 20px 28px;"
        )
        layout.addWidget(self.label)
        self.hide()

    def show_over(self, target: QWidget):
        self.setParent(target)
        self.setGeometry(0, 0, target.width(), target.height())
        self.raise_()
        self.show()
        QApplication.processEvents()


class FileLoaderThread(QThread):
    finished = Signal(str, str)
    error = Signal(str, str)

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.finished.emit(self.path, content)
        except Exception as e:
            self.error.emit(self.path, str(e))


class ScintillaEditor(ScintillaEdit):
    INDIC_ALL = 8
    INDIC_CURRENT = 9
    INDIC_UNDERLINE = 10

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setReadOnly(True)

        # Give the editor a visible border (was previously being lost
        # because the container layout has zero margins and no widget
        # in the chain was drawing a frame).
        self.setObjectName("scintillaEditor")
        self.setStyleSheet(
            "#scintillaEditor { border: 1px solid #a0a0a0; }"
        )

        # Narrower line-number margin (less empty space on the right)
        try:
            self.setMarginTypeN(0, 1)
            self.setMarginWidthN(0, 40)   # was 56 – tighter
        except Exception:
            pass

        try:
            self.styleSetFont(32, "Consolas")
            self.styleSetSize(32, 11)
            self.styleSetFore(32, 0x202020)
            self.styleSetBack(32, 0xFFFFFF)

            self.styleSetFont(33, "Consolas")
            self.styleSetSize(33, 10)
            self.styleSetFore(33, 0x666666)
            self.styleSetBack(33, 0xF5F5F5)
        except Exception:
            pass

        # Line (caret line) highlight and text-selection colors,
        # matching a GitHub-style light-blue accent.
        # Scintilla colours are packed as 0xBBGGRR.
        # Caret line background: #ddf4ff -> 0xFFF4DD
        # Selected text background: rgb(166, 216, 255) -> #A6D8FF -> 0xFFD8A6
        caret_line_bg = 0xFFF4DD
        selection_bg = 0xFFD8A6

        try:
            self.setCaretLineVisible(True)
            self.setCaretLineBack(caret_line_bg)
        except Exception:
            pass

        for method_name in ("setSelBack", "setSelectionBackground", "setSelBackground"):
            fn = getattr(self, method_name, None)
            if callable(fn):
                try:
                    fn(True, selection_bg)
                    break
                except TypeError:
                    try:
                        fn(selection_bg)
                        break
                    except Exception:
                        pass
                except Exception:
                    pass

        self._setup_indicators()

        self._search_positions: list[int] = []
        self._current_match = -1
        self._query = ""
        self._full_text = ""

    def _setup_indicators(self):
        # Former deep-orange palette (BGR)
        style_box = 16
        colour_all = 0x4A9EFF       # deeper light orange
        colour_current = 0x0066FF   # deep bright orange
        colour_underline = 0xE8731A

        for method_name in ("indicSetStyle", "indicatorSetStyle", "setIndicStyle"):
            fn = getattr(self, method_name, None)
            if callable(fn):
                try:
                    fn(self.INDIC_ALL, style_box)
                    fn(self.INDIC_CURRENT, style_box)
                    fn(self.INDIC_UNDERLINE, 0)
                    break
                except Exception:
                    pass

        for method_name in (
            "indicSetForeground", "indicatorSetForeground",
            "setIndicForeground", "indicSetFore"
        ):
            fn = getattr(self, method_name, None)
            if callable(fn):
                try:
                    fn(self.INDIC_ALL, colour_all)
                    fn(self.INDIC_CURRENT, colour_current)
                    fn(self.INDIC_UNDERLINE, colour_underline)
                    break
                except Exception:
                    pass

        for method_name in ("indicSetUnder", "indicatorSetUnder", "setIndicUnder"):
            fn = getattr(self, method_name, None)
            if callable(fn):
                try:
                    fn(self.INDIC_ALL, True)
                    fn(self.INDIC_CURRENT, True)
                    fn(self.INDIC_UNDERLINE, True)
                    break
                except Exception:
                    pass

        for method_name in ("indicSetAlpha", "indicatorSetAlpha", "setIndicAlpha"):
            fn = getattr(self, method_name, None)
            if callable(fn):
                try:
                    fn(self.INDIC_ALL, 80)
                    fn(self.INDIC_CURRENT, 120)
                    break
                except Exception:
                    pass

    def _indicator_fill(self, indicator: int, start: int, length: int):
        for set_cur in ("setIndicatorCurrent", "setIndicCurrent", "indicSetCurrent"):
            fn = getattr(self, set_cur, None)
            if callable(fn):
                try:
                    fn(indicator)
                    break
                except Exception:
                    pass
        for fill in ("indicatorFillRange", "indicFillRange", "fillIndicatorRange"):
            fn = getattr(self, fill, None)
            if callable(fn):
                try:
                    fn(start, length)
                    return True
                except Exception:
                    pass
        return False

    def _indicator_clear_all(self, indicator: int):
        length = len(self._full_text)
        if length <= 0:
            return
        for set_cur in ("setIndicatorCurrent", "setIndicCurrent", "indicSetCurrent"):
            fn = getattr(self, set_cur, None)
            if callable(fn):
                try:
                    fn(indicator)
                    break
                except Exception:
                    pass
        for clear in ("indicatorClearRange", "indicClearRange", "clearIndicatorRange"):
            fn = getattr(self, clear, None)
            if callable(fn):
                try:
                    fn(0, length)
                    return
                except Exception:
                    pass

    def set_text_content(self, text: str):
        # Full reset of search state for the new document
        self.clear_search()

        self._full_text = text or ""
        self.setReadOnly(False)
        self.setText(self._full_text)
        self.setReadOnly(True)

        try:
            self.styleSetFore(33, 0x666666)
            self.styleSetBack(33, 0xF5F5F5)
            self.setMarginWidthN(0, 40)
        except Exception:
            pass

        self._apply_start_of_new_line_underline()

    def _apply_start_of_new_line_underline(self):
        if not self._full_text:
            return
        self._indicator_clear_all(self.INDIC_UNDERLINE)
        pos = 0
        for line in self._full_text.splitlines(keepends=True):
            if line.startswith("StartOfNewLine"):
                self._indicator_fill(self.INDIC_UNDERLINE, pos, len(line))
            pos += len(line)

    def clear_search(self):
        """Reset every search-related field and visual indicator."""
        self._search_positions = []
        self._current_match = -1
        self._query = ""
        self._indicator_clear_all(self.INDIC_ALL)
        self._indicator_clear_all(self.INDIC_CURRENT)
        try:
            pos = 0
            if hasattr(self, "currentPos"):
                pos = self.currentPos()
            self.setSel(pos, pos)
        except Exception:
            pass

    def find_all(self, query: str) -> list[int]:
        self.clear_search()
        if not query or not self._full_text:
            return []

        self._query = query
        positions = []
        start = 0
        while True:
            idx = self._full_text.find(query, start)
            if idx == -1:
                break
            positions.append(idx)
            start = idx + max(len(query), 1)

        self._search_positions = positions
        qlen = len(query)
        for p in positions:
            self._indicator_fill(self.INDIC_ALL, p, qlen)
        return positions

    def goto_match(self, index: int):
        if not self._search_positions:
            return
        index %= len(self._search_positions)
        self._current_match = index
        pos = self._search_positions[index]
        qlen = len(self._query)
        end = pos + qlen

        self._indicator_clear_all(self.INDIC_CURRENT)
        self._indicator_fill(self.INDIC_CURRENT, pos, qlen)

        try:
            self.setSel(pos, end)
        except Exception:
            pass
        try:
            self.gotoPos(pos)
        except Exception:
            pass
        try:
            self.scrollCaret()
        except Exception:
            pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Viewer (Scintilla) – Two Columns")
        self.resize(1100, 700)

        self.current_folder = os.getcwd()
        self._last_query = ""
        self._loader_thread = None

        self._build_ui()
        self._load_folder(self.current_folder)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Horizontal)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 0, 0)

        folder_row = QHBoxLayout()
        btn = QPushButton("Choose Folder…")
        btn.clicked.connect(self.choose_folder)
        folder_row.addWidget(btn)
        folder_row.addStretch(1)
        left_l.addLayout(folder_row)

        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_file_selected)
        left_l.addWidget(self.file_list)

        splitter.addWidget(left)

        right = QWidget()
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type text → Enter / Next / Prev")
        self.search_edit.returnPressed.connect(self.find_next)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.setMaximumWidth(320)
        search_row.addWidget(self.search_edit)

        self.btn_prev = QPushButton("◀ Prev")
        self.btn_prev.clicked.connect(self.find_prev)
        self.btn_next = QPushButton("Next ▶")
        self.btn_next.clicked.connect(self.find_next)
        search_row.addWidget(self.btn_prev)
        search_row.addWidget(self.btn_next)

        self.match_label = QLabel("")
        self.match_label.setMinimumWidth(90)
        search_row.addWidget(self.match_label)

        # Directory label lives to the right of the "Next" button, right-aligned
        self.folder_label = QLabel(self.current_folder)
        self.folder_label.setWordWrap(True)
        self.folder_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.folder_label.setStyleSheet("color:#555;")
        search_row.addWidget(self.folder_label, 1)

        right_l.addLayout(search_row)

        self.editor_container = QWidget()
        editor_layout = QVBoxLayout(self.editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        self.editor = ScintillaEditor()
        editor_layout.addWidget(self.editor)

        self.loading_overlay = LoadingOverlay(self.editor_container)
        right_l.addWidget(self.editor_container)

        splitter.addWidget(right)
        splitter.setSizes([210, 890])
        layout.addWidget(splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        QAction("Find Next", self, shortcut=QKeySequence.FindNext, triggered=self.find_next)
        QAction("Find Previous", self, shortcut=QKeySequence.FindPrevious, triggered=self.find_prev)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.loading_overlay.isVisible():
            self.loading_overlay.setGeometry(
                0, 0, self.editor_container.width(), self.editor_container.height()
            )

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", self.current_folder)
        if folder:
            self.current_folder = folder
            self.folder_label.setText(folder)
            self._load_folder(folder)

    def _load_folder(self, folder):
        self.file_list.clear()
        self.editor.set_text_content("")
        self.editor.clear_search()
        self.match_label.clear()
        self._last_query = ""          # force search rebuild on next file

        try:
            for name in sorted(os.listdir(folder), key=str.lower):
                full = os.path.join(folder, name)
                if os.path.isfile(full):
                    item = QListWidgetItem(name)
                    item.setData(Qt.UserRole, full)
                    self.file_list.addItem(item)

            count = self.file_list.count()
            self.status.showMessage(f"{count} files")

            if count > 0:
                self.file_list.setCurrentRow(0)
                self.on_file_selected(self.file_list.item(0))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cannot read folder:\n{e}")

    def on_file_selected(self, item: QListWidgetItem):
        path = item.data(Qt.UserRole)

        if self._loader_thread and self._loader_thread.isRunning():
            self._loader_thread.quit()
            self._loader_thread.wait(500)

        # Reset search state immediately so old positions are never reused
        self.editor.clear_search()
        self.match_label.clear()
        self._last_query = ""

        self.loading_overlay.show_over(self.editor_container)
        self.file_list.setEnabled(False)
        self.status.showMessage(f"Loading: {os.path.basename(path)} …")

        self._loader_thread = FileLoaderThread(path, self)
        self._loader_thread.finished.connect(self._on_file_loaded)
        self._loader_thread.error.connect(self._on_file_error)
        self._loader_thread.start()

    def _on_file_loaded(self, path: str, content: str):
        self.loading_overlay.label.setText("Preparing display…\nPlease wait")
        QApplication.processEvents()
        try:
            # set_text_content already calls clear_search()
            self.editor.set_text_content(content)
            self.status.showMessage(f"Loaded: {path}")

            self.match_label.clear()
            self._last_query = ""

            # Re-run search against the NEW file if the box still has text
            if self.search_edit.text().strip():
                self._perform_search(jump_to_first=True)
        finally:
            self.loading_overlay.hide()
            self.file_list.setEnabled(True)
            self._loader_thread = None

    def _on_file_error(self, path: str, message: str):
        self.loading_overlay.hide()
        self.file_list.setEnabled(True)
        self._loader_thread = None
        QMessageBox.warning(self, "Cannot open file", f"{path}\n\n{message}")
        self.status.showMessage("Failed to load file")

    def _on_search_text_changed(self, text: str):
        if not text.strip():
            self.editor.clear_search()
            self.match_label.clear()
            self._last_query = ""

    def _perform_search(self, jump_to_first: bool = False):
        query = self.search_edit.text()
        if not query:
            self.editor.clear_search()
            self.match_label.clear()
            return

        positions = self.editor.find_all(query)
        self._last_query = query

        if not positions:
            self.match_label.setText("No matches")
            return

        current = 0 if jump_to_first else max(0, self.editor._current_match)
        current = min(current, len(positions) - 1)
        self.editor.goto_match(current)
        self.match_label.setText(f"{current + 1} / {len(positions)}")

    def find_next(self):
        query = self.search_edit.text()
        if not query:
            return
        if query != self._last_query or not self.editor._search_positions:
            self._perform_search(jump_to_first=True)
        else:
            self.editor.goto_match(self.editor._current_match + 1)
            n = len(self.editor._search_positions)
            self.match_label.setText(f"{self.editor._current_match + 1} / {n}")

    def find_prev(self):
        query = self.search_edit.text()
        if not query:
            return
        if query != self._last_query or not self.editor._search_positions:
            self._perform_search(jump_to_first=True)
        else:
            self.editor.goto_match(self.editor._current_match - 1)
            n = len(self.editor._search_positions)
            self.match_label.setText(f"{self.editor._current_match + 1} / {n}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
