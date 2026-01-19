"""
History Window for LocalWhisper

Displays transcription history with search and export capabilities.
"""

from typing import Optional, List
from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
    QGroupBox,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from localwhisper.core.history_manager import HistoryManager, HistoryEntry


class HistoryWindow(QDialog):
    """
    History viewer dialog.

    Shows past transcriptions with search, delete, and export functionality.
    """

    # Signals
    entry_selected = pyqtSignal(HistoryEntry)

    def __init__(
        self,
        history_manager: HistoryManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._history = history_manager
        self._current_entries: List[HistoryEntry] = []

        self._setup_ui()
        self._load_history()

    def _setup_ui(self) -> None:
        """Set up the history UI."""
        self.setWindowTitle("Transcription History")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Statistics bar
        stats = self._history.get_statistics()
        stats_label = QLabel(
            f"Total: {stats['total_entries']} entries | "
            f"Duration: {stats['total_duration_formatted']} | "
            f"Today: {stats['entries_today']}"
        )
        stats_label.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        layout.addWidget(stats_label)

        # Search bar
        search_layout = QHBoxLayout()

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search transcriptions...")
        self._search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_edit)

        self._clear_search_btn = QPushButton("Clear")
        self._clear_search_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self._clear_search_btn)

        layout.addLayout(search_layout)

        # History table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Time", "Text", "Duration", "Confidence"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)

        # Column sizing
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.cellDoubleClicked.connect(self._on_double_click)

        layout.addWidget(self._table)

        # Preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self._preview_text = QLabel()
        self._preview_text.setWordWrap(True)
        self._preview_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._preview_text.setMinimumHeight(60)
        self._preview_text.setStyleSheet(
            "background: #1F2937; padding: 8px; border-radius: 4px;"
        )
        preview_layout.addWidget(self._preview_text)

        layout.addWidget(preview_group)

        # Button row
        button_layout = QHBoxLayout()

        self._export_btn = QPushButton("Export...")
        self._export_btn.clicked.connect(self._export_history)
        button_layout.addWidget(self._export_btn)

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_selected)
        button_layout.addWidget(self._delete_btn)

        button_layout.addStretch()

        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._copy_selected)
        button_layout.addWidget(self._copy_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self._close_btn)

        layout.addLayout(button_layout)

    def _load_history(self, search_query: str = "") -> None:
        """Load history into the table."""
        if search_query:
            entries = self._history.search(search_query)
        else:
            entries = self._history.get_recent(limit=500)

        self._current_entries = entries
        self._table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            # Time
            time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M")
            self._table.setItem(row, 0, QTableWidgetItem(time_str))

            # Text (truncated)
            text = entry.text[:100] + "..." if len(entry.text) > 100 else entry.text
            text = text.replace("\n", " ")
            self._table.setItem(row, 1, QTableWidgetItem(text))

            # Duration
            duration_str = f"{entry.duration:.1f}s"
            self._table.setItem(row, 2, QTableWidgetItem(duration_str))

            # Confidence
            confidence_str = f"{entry.confidence * 100:.0f}%"
            self._table.setItem(row, 3, QTableWidgetItem(confidence_str))

        self._preview_text.setText("")
        self._delete_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)

    def _on_search(self, text: str) -> None:
        """Handle search text change."""
        self._load_history(text.strip())

    def _clear_search(self) -> None:
        """Clear the search and reload."""
        self._search_edit.clear()
        self._load_history()

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        selected = self._table.selectedItems()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self._current_entries):
                entry = self._current_entries[row]
                self._preview_text.setText(entry.text)
                self._delete_btn.setEnabled(True)
                self._copy_btn.setEnabled(True)
                return

        self._preview_text.setText("")
        self._delete_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)

    def _on_double_click(self, row: int, col: int) -> None:
        """Handle double-click on row."""
        if 0 <= row < len(self._current_entries):
            entry = self._current_entries[row]
            self.entry_selected.emit(entry)

    def _get_selected_entry(self) -> Optional[HistoryEntry]:
        """Get the currently selected entry."""
        selected = self._table.selectedItems()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self._current_entries):
                return self._current_entries[row]
        return None

    def _delete_selected(self) -> None:
        """Delete the selected entry."""
        entry = self._get_selected_entry()
        if not entry or entry.id is None:
            return

        reply = QMessageBox.question(
            self,
            "Delete Entry",
            "Are you sure you want to delete this transcription?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._history.delete_entry(entry.id)
            self._load_history(self._search_edit.text())

    def _copy_selected(self) -> None:
        """Copy selected text to clipboard."""
        entry = self._get_selected_entry()
        if entry:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(entry.text)

    def _export_history(self) -> None:
        """Export history to file."""
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export History",
            "transcription_history",
            "JSON (*.json);;Text (*.txt);;CSV (*.csv)",
        )

        if not file_path:
            return

        from pathlib import Path
        path = Path(file_path)

        try:
            if "json" in selected_filter.lower() or path.suffix == ".json":
                count = self._history.export_to_json(path)
            elif "csv" in selected_filter.lower() or path.suffix == ".csv":
                count = self._history.export_to_csv(path)
            else:
                count = self._history.export_to_txt(path)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {count} entries to:\n{file_path}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export history:\n{str(e)}",
            )

    def refresh(self) -> None:
        """Refresh the history display."""
        self._load_history(self._search_edit.text())
