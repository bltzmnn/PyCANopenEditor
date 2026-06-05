"""Profile 视图，Profile 列表对话框 + 合并预览 + 冲突解决"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit, QCheckBox, QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from ...core.models.eds import EDS
from ..viewmodels.profile_vm import ProfileViewModel, ProfileInfo, MergeEntry


class ProfileDialog(QDialog):
    """Profile 导入对话框"""

    def __init__(
        self,
        vm: ProfileViewModel,
        target_eds: Optional[EDS],
        profile_dir: str,
        parent=None,
    ):
        super().__init__(parent)
        self._vm = vm
        self._profile_dir = profile_dir

        self.setWindowTitle("导入 Profile")
        self.resize(900, 600)

        vm.set_target(target_eds)

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧：Profile 列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_layout.addWidget(QLabel("<b>可用的 Profile</b>"))

        self._profile_list = QListWidget()
        self._profile_list.currentRowChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self._profile_list)

        open_btn = QPushButton("打开 Profile 文件...")
        open_btn.clicked.connect(self._on_open_profile)
        left_layout.addWidget(open_btn)

        splitter.addWidget(left_widget)

        # 右侧：合并预览
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 偏移设置
        offset_layout = QHBoxLayout()
        offset_layout.addWidget(QLabel("Index 偏移:"))
        self._offset_edit = QLineEdit("0")
        self._offset_edit.setMaximumWidth(100)
        self._offset_edit.textEdited.connect(self._on_offset_changed)
        offset_layout.addWidget(self._offset_edit)

        self._preview_btn = QPushButton("预览")
        self._preview_btn.clicked.connect(self._on_preview)
        offset_layout.addWidget(self._preview_btn)

        self._conflict_label = QLabel()
        offset_layout.addWidget(self._conflict_label)

        offset_layout.addStretch()
        right_layout.addLayout(offset_layout)

        # 合并表格
        self._merge_table = QTableWidget(0, 4)
        self._merge_table.setHorizontalHeaderLabels(["导入", "Index", "名称", "冲突"])
        self._merge_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self._merge_table)

        # 操作按钮
        btn_layout = QHBoxLayout()

        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self._on_select_all)
        btn_layout.addWidget(select_all_btn)

        deselect_conflicts_btn = QPushButton("取消选择冲突项")
        deselect_conflicts_btn.clicked.connect(self._on_deselect_conflicts)
        btn_layout.addWidget(deselect_conflicts_btn)

        btn_layout.addStretch()

        self._import_btn = QPushButton("导入")
        self._import_btn.clicked.connect(self._on_import)
        self._import_btn.setEnabled(False)
        btn_layout.addWidget(self._import_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        right_layout.addLayout(btn_layout)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        # 扫描 profile 目录
        self._vm.scan_profiles(self._profile_dir)
        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        self._profile_list.clear()
        for info in self._vm.profiles:
            label = info.filename
            if info.error:
                label += f" [错误: {info.error}]"
            item = QListWidgetItem(label)
            if info.error:
                item.setForeground(QBrush(QColor("red")))
            self._profile_list.addItem(item)

    def _on_profile_selected(self, row: int) -> None:
        if 0 <= row < len(self._vm.profiles):
            profile = self._vm.profiles[row]
            self._vm.select_profile(profile)
            self._on_preview()

    def _on_open_profile(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开 Profile 文件", "",
            "XPD 文件 (*.xpd);;XDD 文件 (*.xdd *.xdc);;所有文件 (*)"
        )
        if not filepath:
            return

        filename = os.path.basename(filepath)
        info = ProfileInfo(filepath=filepath, filename=filename)

        try:
            from ...core.parsers.xdd_handler import XDDHandler
            handler = XDDHandler()
            result = handler.read_xml(filepath)
            if result is not None:
                info.eds = result
            else:
                info.error = "无法解析文件"
        except Exception as e:
            info.error = str(e)

        self._vm.select_profile(info)
        self._on_preview()

    def _on_offset_changed(self) -> None:
        pass

    def _on_preview(self) -> None:
        try:
            text = self._offset_edit.text() or "0"
            offset = int(text, 0)
        except ValueError:
            offset = 0

        entries = self._vm.preview_merge(offset)
        self._refresh_merge_table(entries)
        self._import_btn.setEnabled(len(entries) > 0)

    def _refresh_merge_table(self, entries: list[MergeEntry]) -> None:
        self._merge_table.setRowCount(0)

        conflicts = 0
        for i, entry in enumerate(entries):
            self._merge_table.insertRow(i)

            # 导入复选框
            check = QCheckBox()
            check.setChecked(entry.insert)
            check.stateChanged.connect(lambda state, idx=entry.index: self._on_toggle_entry(idx, state))
            self._merge_table.setCellWidget(i, 0, check)

            # Index
            self._merge_table.setItem(i, 1, QTableWidgetItem(f"0x{entry.index:04X}"))

            # 名称
            self._merge_table.setItem(i, 2, QTableWidgetItem(entry.name))

            # 冲突
            conflict_text = "⚠️ 冲突" if entry.collision else ""
            conflict_item = QTableWidgetItem(conflict_text)
            if entry.collision:
                conflict_item.setForeground(QBrush(QColor("red")))
                conflicts += 1
            self._merge_table.setItem(i, 3, conflict_item)

        self._conflict_label.setText(f"冲突: {conflicts} | 导入: {self._vm.get_insert_count()}")

    def _on_toggle_entry(self, index: int, state: int) -> None:
        self._vm.toggle_entry(index, state == Qt.Checked)
        self._conflict_label.setText(
            f"冲突: {self._vm.get_conflict_count()} | 导入: {self._vm.get_insert_count()}"
        )

    def _on_select_all(self) -> None:
        for entry in self._vm.merge_entries:
            entry.insert = True
        self._refresh_merge_table(self._vm.merge_entries)

    def _on_deselect_conflicts(self) -> None:
        for entry in self._vm.merge_entries:
            if entry.collision:
                entry.insert = False
        self._refresh_merge_table(self._vm.merge_entries)

    def _on_import(self) -> None:
        conflicts = self._vm.get_conflict_count()
        if conflicts > 0:
            reply = QMessageBox.question(
                self, "导入确认",
                f"有 {conflicts} 个冲突项将被跳过，继续?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        if self._vm.execute_merge(skip_collisions=True):
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "导入失败")
