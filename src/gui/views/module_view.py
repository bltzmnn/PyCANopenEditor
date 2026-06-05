"""Module 视图，对应 C# ModuleInfo.cs"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.models.eds import EDS
from ..viewmodels.module_vm import ModuleViewModel


class ModuleView(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._vm = ModuleViewModel()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Supported Modules:"))
        self._nr_label = QLineEdit("0")
        self._nr_label.setReadOnly(True)
        self._nr_label.setMaximumWidth(60)
        top_row.addWidget(self._nr_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_group = QGroupBox("Modules")
        left_layout = QVBoxLayout(left_group)
        self._module_list = QListWidget()
        self._module_list.currentRowChanged.connect(self._on_module_selected)
        left_layout.addWidget(self._module_list)
        splitter.addWidget(left_group)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        extends_group = QGroupBox("Sub-Extends (OD References)")
        extends_layout = QVBoxLayout(extends_group)
        self._extends_table = QTableWidget(0, 2)
        self._extends_table.setHorizontalHeaderLabels(["Index", "Name"])
        self._extends_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._extends_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._extends_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        extends_layout.addWidget(self._extends_table)
        right_layout.addWidget(extends_group)

        comments_group = QGroupBox("Module Comments")
        comments_layout = QVBoxLayout(comments_group)
        self._comments_text = QTextEdit()
        self._comments_text.setReadOnly(True)
        comments_layout.addWidget(self._comments_text)
        right_layout.addWidget(comments_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([250, 500])

        layout.addWidget(splitter)

    def set_eds(self, eds: Optional[EDS]) -> None:
        self._vm.set_eds(eds)
        try:
            self._refresh()
        except RuntimeError:
            pass

    def _refresh(self) -> None:
        self._nr_label.setText(str(self._vm.nr_supported))

        self._module_list.clear()
        for mod in self._vm.modules:
            connected_mark = " [Connected]" if mod.is_connected else ""
            text = f"Module {mod.module_index}: {mod.product_name}{connected_mark}"
            item = QListWidgetItem(text)
            if mod.is_connected:
                item.setBackground(Qt.GlobalColor.darkGreen)
                item.setForeground(Qt.GlobalColor.white)
            self._module_list.addItem(item)

        self._clear_details()

    def _on_module_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._vm.modules):
            self._clear_details()
            return

        mod = self._vm.modules[row]
        self._vm.select_module(mod.module_index)
        self._refresh_details()

    def _refresh_details(self) -> None:
        self._extends_table.setRowCount(len(self._vm.sub_extends))
        for i, ext in enumerate(self._vm.sub_extends):
            idx_item = QTableWidgetItem(f"0x{ext.od_index:04X}")
            name_item = QTableWidgetItem(ext.od_name)
            if not ext.is_found:
                idx_item.setForeground(Qt.GlobalColor.red)
                name_item.setForeground(Qt.GlobalColor.red)
            self._extends_table.setItem(i, 0, idx_item)
            self._extends_table.setItem(i, 1, name_item)

        self._comments_text.setPlainText("\n".join(self._vm.module_comments))

    def _clear_details(self) -> None:
        self._extends_table.setRowCount(0)
        self._comments_text.clear()
