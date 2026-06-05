"""PDO 视图，显示 TX/RX PDO 列表、通信参数和映射可视化"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QLineEdit, QCheckBox, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox, QMenu, QInputDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from ...core.models.eds import EDS
from ...core.models.pdo_helper import PDOMappingEntry
from ..viewmodels.pdo_vm import PDOViewModel, PDOSlotVM


class PDOView(QWidget):
    """PDO 映射视图"""

    def __init__(self, vm: PDOViewModel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._vm = vm
        self._updating_ui = False

        layout = QVBoxLayout(self)

        top_splitter = QSplitter(Qt.Horizontal)

        # 左侧：TX 和 RX PDO 列表 + 按钮
        pdo_list_widget = QWidget()
        pdo_list_layout = QVBoxLayout(pdo_list_widget)
        pdo_list_layout.setContentsMargins(0, 0, 0, 0)

        pdo_list_layout.addWidget(QLabel("<b>TX PDO (0x1800-0x19FF)</b>"))
        self._tx_list = QListWidget()
        self._tx_list.currentRowChanged.connect(self._on_tx_selected)
        pdo_list_layout.addWidget(self._tx_list)

        tx_btn_layout = QHBoxLayout()
        self._add_tx_btn = QPushButton("+ TX PDO")
        self._add_tx_btn.clicked.connect(self._on_add_tx)
        self._del_tx_btn = QPushButton("- TX PDO")
        self._del_tx_btn.clicked.connect(self._on_del_tx)
        tx_btn_layout.addWidget(self._add_tx_btn)
        tx_btn_layout.addWidget(self._del_tx_btn)
        pdo_list_layout.addLayout(tx_btn_layout)

        pdo_list_layout.addWidget(QLabel("<b>RX PDO (0x1400-0x15FF)</b>"))
        self._rx_list = QListWidget()
        self._rx_list.currentRowChanged.connect(self._on_rx_selected)
        pdo_list_layout.addWidget(self._rx_list)

        rx_btn_layout = QHBoxLayout()
        self._add_rx_btn = QPushButton("+ RX PDO")
        self._add_rx_btn.clicked.connect(self._on_add_rx)
        self._del_rx_btn = QPushButton("- RX PDO")
        self._del_rx_btn.clicked.connect(self._on_del_rx)
        rx_btn_layout.addWidget(self._add_rx_btn)
        rx_btn_layout.addWidget(self._del_rx_btn)
        pdo_list_layout.addLayout(rx_btn_layout)

        top_splitter.addWidget(pdo_list_widget)

        # 右侧：通信参数 + 映射表格
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        comm_group = QGroupBox("通信参数")
        comm_layout = QFormLayout(comm_group)

        self._comm_index_edit = QLineEdit()
        self._comm_index_edit.setReadOnly(True)
        comm_layout.addRow("通信 Index:", self._comm_index_edit)

        self._mapping_index_edit = QLineEdit()
        self._mapping_index_edit.setReadOnly(True)
        comm_layout.addRow("映射 Index:", self._mapping_index_edit)

        self._cob_edit = QLineEdit()
        self._cob_edit.textEdited.connect(self._on_cob_edited)
        comm_layout.addRow("COB-ID:", self._cob_edit)

        self._type_edit = QLineEdit()
        self._type_edit.textEdited.connect(self._on_type_edited)
        comm_layout.addRow("传输类型:", self._type_edit)

        self._inhibit_edit = QLineEdit()
        self._inhibit_edit.textEdited.connect(self._on_inhibit_edited)
        comm_layout.addRow("Inhibit:", self._inhibit_edit)

        self._event_timer_edit = QLineEdit()
        self._event_timer_edit.textEdited.connect(self._on_event_timer_edited)
        comm_layout.addRow("Event Timer:", self._event_timer_edit)

        self._sync_start_edit = QLineEdit()
        self._sync_start_edit.textEdited.connect(self._on_sync_start_edited)
        comm_layout.addRow("Sync Start:", self._sync_start_edit)

        self._invalid_check = QCheckBox()
        self._invalid_check.stateChanged.connect(self._on_invalid_changed)
        comm_layout.addRow("Invalid:", self._invalid_check)

        self._nodeid_label = QLabel()
        comm_layout.addRow("NodeID:", self._nodeid_label)

        right_layout.addWidget(comm_group)

        mapping_group = QGroupBox("PDO 映射")
        mapping_layout = QVBoxLayout(mapping_group)

        self._mapping_table = QTableWidget(0, 4)
        self._mapping_table.setHorizontalHeaderLabels(["映射对象", "Index", "Sub", "Bits"])
        self._mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._mapping_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._mapping_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._mapping_table.customContextMenuRequested.connect(self._on_mapping_context_menu)
        mapping_layout.addWidget(self._mapping_table)

        self._total_bits_label = QLabel("总位数: 0 / 64")
        mapping_layout.addWidget(self._total_bits_label)

        self._bits_label = QLabel()
        self._bits_label.setMinimumHeight(20)
        mapping_layout.addWidget(self._bits_label)

        right_layout.addWidget(mapping_group)

        top_splitter.addWidget(right_widget)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 3)

        layout.addWidget(top_splitter)

    def set_eds(self, eds: Optional[EDS]) -> None:
        self._vm.set_eds(eds)
        self._refresh_pdo_lists()
        try:
            self._clear_comm_params()
            self._mapping_table.setRowCount(0)
        except RuntimeError:
            pass

    def refresh(self) -> None:
        self._vm.rebuild()
        self._refresh_pdo_lists()

    def _refresh_pdo_lists(self) -> None:
        self._tx_list.clear()
        self._rx_list.clear()

        for slot_vm in self._vm.get_tx_slots():
            item = QListWidgetItem(str(slot_vm))
            if slot_vm.invalid:
                item.setForeground(QBrush(QColor("gray")))
            self._tx_list.addItem(item)

        for slot_vm in self._vm.get_rx_slots():
            item = QListWidgetItem(str(slot_vm))
            if slot_vm.invalid:
                item.setForeground(QBrush(QColor("gray")))
            self._rx_list.addItem(item)

    def _on_tx_selected(self, row: int) -> None:
        if row < 0:
            return
        self._rx_list.blockSignals(True)
        self._rx_list.clearSelection()
        self._rx_list.blockSignals(False)

        tx_slots = self._vm.get_tx_slots()
        if row < len(tx_slots):
            self._vm.select_pdo(row)
            self._update_comm_params()
            self._update_mapping_table()

    def _on_rx_selected(self, row: int) -> None:
        if row < 0:
            return
        self._tx_list.blockSignals(True)
        self._tx_list.clearSelection()
        self._tx_list.blockSignals(False)

        rx_slots = self._vm.get_rx_slots()
        tx_count = len(self._vm.get_tx_slots())
        self._vm.select_pdo(tx_count + row)
        self._update_comm_params()
        self._update_mapping_table()

    def _update_comm_params(self) -> None:
        self._updating_ui = True

        slot_vm = self._vm.selected_pdo
        if slot_vm:
            self._comm_index_edit.setText(slot_vm.config_index_hex)
            self._mapping_index_edit.setText(slot_vm.mapping_index_hex)
            self._cob_edit.setText(slot_vm.cob_hex)
            self._type_edit.setText(str(slot_vm.transmission_type))
            self._inhibit_edit.setText(str(slot_vm.inhibit))
            self._event_timer_edit.setText(str(slot_vm.event_timer))
            self._sync_start_edit.setText(str(slot_vm.sync_start))
            self._invalid_check.setChecked(slot_vm.invalid)
            self._nodeid_label.setText("是" if slot_vm.nodeid_present else "否")
        else:
            self._clear_comm_params()

        self._updating_ui = False

    def _clear_comm_params(self) -> None:
        self._updating_ui = True
        self._comm_index_edit.clear()
        self._mapping_index_edit.clear()
        self._cob_edit.clear()
        self._type_edit.clear()
        self._inhibit_edit.clear()
        self._event_timer_edit.clear()
        self._sync_start_edit.clear()
        self._invalid_check.setChecked(False)
        self._nodeid_label.clear()
        self._updating_ui = False

    def _update_mapping_table(self) -> None:
        self._mapping_table.setRowCount(0)

        slot_vm = self._vm.selected_pdo
        if slot_vm is None:
            self._total_bits_label.setText("总位数: 0 / 64")
            self._bits_label.clear()
            return

        entries = slot_vm.get_mapping_entries()
        total_bits = 0

        for i, entry in enumerate(entries):
            self._mapping_table.insertRow(i)

            desc = self._vm.get_mapping_description(entry)
            self._mapping_table.setItem(i, 0, QTableWidgetItem(desc))

            if entry.entry:
                idx_text = f"0x{entry.entry.index:04X}"
            else:
                idx_text = "-"
            self._mapping_table.setItem(i, 1, QTableWidgetItem(idx_text))

            if entry.entry:
                sub_text = f"0x{entry.entry.Subindex:02X}"
            else:
                sub_text = "-"
            self._mapping_table.setItem(i, 2, QTableWidgetItem(sub_text))

            self._mapping_table.setItem(i, 3, QTableWidgetItem(str(entry.width)))

            total_bits += entry.width

        over = " ⚠️ 超过 64 位!" if total_bits > 64 else ""
        self._total_bits_label.setText(f"总位数: {total_bits} / 64{over}")
        self._update_bits_visual(total_bits)

    def _update_bits_visual(self, total_bits: int) -> None:
        if total_bits <= 0:
            self._bits_label.clear()
            return

        parts = []
        for byte_idx in range(8):
            start = byte_idx * 8
            end = min(start + 8, total_bits)
            if start >= total_bits:
                break
            parts.append(f"B{byte_idx}:{start}-{end}")

        self._bits_label.setText(" | ".join(parts))

    # 添加/删除 PDO
    def _on_add_tx(self) -> None:
        idx = self._vm.find_next_pdo_index(rx=False)
        if idx is None:
            QMessageBox.warning(self, "错误", "没有可用的 TX PDO index（0x1800-0x19FF 已满）")
            return
        if self._vm.add_pdo(rx=False, index=idx):
            self._refresh_pdo_lists()

    def _on_add_rx(self) -> None:
        idx = self._vm.find_next_pdo_index(rx=True)
        if idx is None:
            QMessageBox.warning(self, "错误", "没有可用的 RX PDO index（0x1400-0x15FF 已满）")
            return
        if self._vm.add_pdo(rx=True, index=idx):
            self._refresh_pdo_lists()

    def _on_del_tx(self) -> None:
        row = self._tx_list.currentRow()
        if row < 0:
            return
        tx_slots = self._vm.get_tx_slots()
        if row >= len(tx_slots):
            return
        config_idx = tx_slots[row].config_index
        reply = QMessageBox.question(
            self, "删除 PDO",
            f"确认删除 TX PDO 0x{config_idx:04X}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._vm.delete_pdo(config_idx)
            self._refresh_pdo_lists()
            self._clear_comm_params()
            self._mapping_table.setRowCount(0)

    def _on_del_rx(self) -> None:
        row = self._rx_list.currentRow()
        if row < 0:
            return
        rx_slots = self._vm.get_rx_slots()
        if row >= len(rx_slots):
            return
        config_idx = rx_slots[row].config_index
        reply = QMessageBox.question(
            self, "删除 PDO",
            f"确认删除 RX PDO 0x{config_idx:04X}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._vm.delete_pdo(config_idx)
            self._refresh_pdo_lists()
            self._clear_comm_params()
            self._mapping_table.setRowCount(0)

    # 映射右键菜单
    def _on_mapping_context_menu(self, pos) -> None:
        menu = QMenu(self)
        add_action = menu.addAction("添加映射...")
        delete_action = menu.addAction("删除此映射")

        current_row = self._mapping_table.currentRow()
        delete_action.setEnabled(current_row >= 0)

        action = menu.exec(self._mapping_table.mapToGlobal(pos))

        if action == add_action:
            self._on_add_mapping()
        elif action == delete_action and current_row >= 0:
            self._on_delete_mapping(current_row)

    def _on_add_mapping(self) -> None:
        """添加映射条目，让用户选择 OD 对象"""
        mappable = self._vm.get_mappable_objects()
        if not mappable:
            QMessageBox.information(self, "提示", "没有可映射的 OD 对象（需要设置 PDO 映射类型）")
            return

        items = [f"0x{idx:04X}/{sub:02X} {name} ({bits} bits)" for idx, sub, name, bits in mappable]
        choice, ok = QInputDialog.getItem(
            self, "添加映射", "选择 OD 对象:", items, 0, False
        )
        if not ok:
            return

        idx = items.index(choice)
        od_index, sub_index, _, bits = mappable[idx]

        if self._vm.add_mapping(od_index, sub_index, bits):
            self._update_mapping_table()
        else:
            QMessageBox.warning(self, "错误", "映射失败（可能超过 64 位限制或映射已满）")

    def _on_delete_mapping(self, row: int) -> None:
        """删除映射条目（row 是 0-based 表格行，映射 ordinal 是 row+1）"""
        if self._vm.delete_mapping(row + 1):
            self._update_mapping_table()

    # 通信参数编辑回调
    def _on_cob_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        try:
            cob = int(text, 16)
            self._vm.update_comm_param(cob=cob)
        except ValueError:
            pass

    def _on_type_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        try:
            self._vm.update_comm_param(transmission_type=int(text))
        except ValueError:
            pass

    def _on_inhibit_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        try:
            self._vm.update_comm_param(inhibit=int(text))
        except ValueError:
            pass

    def _on_event_timer_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        try:
            self._vm.update_comm_param(event_timer=int(text))
        except ValueError:
            pass

    def _on_sync_start_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        try:
            self._vm.update_comm_param(sync_start=int(text))
        except ValueError:
            pass

    def _on_invalid_changed(self, state: int) -> None:
        if self._updating_ui:
            return
        self._vm.update_comm_param(invalid=(state == Qt.Checked))
