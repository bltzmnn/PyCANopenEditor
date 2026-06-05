"""对象字典视图，左侧 index range 列表 + 右侧 sub-object 表格 + 属性面板"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QTextEdit, QCheckBox, QMenu, QMessageBox,
    QInputDialog, QLabel,
)
from PySide6.QtCore import Qt, Signal

from ...core.models.datatypes import DataType, ObjectType, AccessType, PDOMappingType, AccessSDO, AccessPDO, AccessSRDO
from ...core.models.eds import EDS
from ..viewmodels.od_vm import ODViewModel, ODItemVM, SubObjectVM


# 数据类型下拉框选项
DATA_TYPE_NAMES = [dt.name for dt in DataType]
OBJECT_TYPE_NAMES = [ot.name for ot in ObjectType if ot != ObjectType.UNKNOWN]
ACCESS_TYPE_NAMES = [at.name for at in AccessType]
PDO_TYPE_NAMES = [pt.name for pt in PDOMappingType]


class ODIndexRangeWidget(QWidget):
    """OD Index 范围列表组件，显示某个 index 范围内的 OD 条目"""

    entry_selected = Signal(int)  # 选中条目的 index
    add_requested = Signal()
    delete_requested = Signal(int)

    def __init__(
        self,
        heading: str,
        min_index: int,
        max_index: int,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._heading = heading
        self._min_index = min_index
        self._max_index = max_index

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        heading_label = QLabel(f"<b>{heading}</b>")
        layout.addWidget(heading_label)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list)

        self._items: list[tuple[int, ODItemVM]] = []

    @property
    def min_index(self) -> int:
        return self._min_index

    @property
    def max_index(self) -> int:
        return self._max_index

    def refresh(self, vm: ODViewModel) -> None:
        """刷新列表内容"""
        self._list.clear()
        self._items.clear()

        vm.set_filter(self._min_index, self._max_index)
        items = vm.get_filtered_items()

        for item_vm in items:
            label = str(item_vm)
            list_item = QListWidgetItem(label)
            if item_vm.od.prop.CO_disabled:
                list_item.setForeground(Qt.GlobalColor.gray)
            self._list.addItem(list_item)
            self._items.append((item_vm.index, item_vm))

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._items):
            index, _ = self._items[row]
            self.entry_selected.emit(index)

    def _on_context_menu(self, pos) -> None:
        menu = QMenu(self)
        add_action = menu.addAction("添加...")
        delete_action = menu.addAction("删除...")

        current = self._list.currentRow()
        delete_action.setEnabled(current >= 0)

        action = menu.exec(self._list.mapToGlobal(pos))

        if action == add_action:
            self._on_add_index()
        elif action == delete_action and current >= 0:
            index, _ = self._items[current]
            self.delete_requested.emit(index)

    def _on_add_index(self) -> None:
        """添加新 OD 条目"""
        index_str, ok = QInputDialog.getText(
            self, "添加 OD 条目", "Index (十六进制，如 2000):"
        )
        if not ok or not index_str:
            return

        try:
            index = int(index_str, 16)
        except ValueError:
            QMessageBox.warning(self, "错误", "无效的十六进制值")
            return

        if not (self._min_index <= index <= self._max_index):
            QMessageBox.warning(self, "错误", f"Index 必须在 0x{self._min_index:04X} - 0x{self._max_index:04X} 范围内")
            return

        name, ok = QInputDialog.getText(
            self, "添加 OD 条目", "名称:"
        )
        if not ok or not name:
            name = f"NewObject_0x{index:04X}"

        obj_type_str, ok = QInputDialog.getItem(
            self, "添加 OD 条目", "对象类型:",
            OBJECT_TYPE_NAMES, 0, False,
        )
        if not ok:
            return

        obj_type = ObjectType[obj_type_str]
        self.add_requested.emit()
        # 将通过信号传递给 ViewModel
        self._pending_add = (index, name, obj_type)


class ODView(QWidget):
    """对象字典视图，包含左侧 index 范围列表和右侧 sub-object 编辑面板"""

    def __init__(self, vm: ODViewModel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._vm = vm
        self._updating_ui = False  # 防止循环更新

        layout = QHBoxLayout(self)

        # 左侧：index range 列表
        splitter = QSplitter(Qt.Horizontal)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._com_range = ODIndexRangeWidget("通信对象 (0x1000-0x1FFF)", 0x1000, 0x1FFF)
        self._mfr_range = ODIndexRangeWidget("制造商对象 (0x2000-0x5FFF)", 0x2000, 0x5FFF)
        self._dev_range = ODIndexRangeWidget("设备 Profile 对象 (0x6000+)", 0x6000, 0x9FFF)

        for range_widget in [self._com_range, self._mfr_range, self._dev_range]:
            range_widget.entry_selected.connect(self._on_entry_selected)
            range_widget.delete_requested.connect(self._on_delete_entry)
            left_layout.addWidget(range_widget)

        splitter.addWidget(left_widget)

        # 右侧：sub-object 表格 + 属性面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_splitter = QSplitter(Qt.Vertical)

        # Sub-object 表格
        self._sub_table = QTableWidget(0, 7)
        self._sub_table.setHorizontalHeaderLabels(["Sub", "名称", "数据类型", "SDO", "PDO", "默认值", "描述"])
        self._sub_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._sub_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._sub_table.currentCellChanged.connect(self._on_sub_cell_changed)
        self._sub_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._sub_table.customContextMenuRequested.connect(self._on_sub_context_menu)
        right_splitter.addWidget(self._sub_table)

        # 属性编辑面板
        prop_group = QGroupBox("属性编辑")
        prop_layout = QFormLayout(prop_group)

        self._index_label = QLineEdit()
        self._index_label.setReadOnly(True)
        self._subindex_label = QLineEdit()
        self._subindex_label.setReadOnly(True)

        index_layout = QHBoxLayout()
        index_layout.addWidget(self._index_label)
        index_layout.addWidget(QLabel("Sub"))
        index_layout.addWidget(self._subindex_label)
        prop_layout.addRow("Index:", index_layout)

        self._name_edit = QLineEdit()
        self._name_edit.textEdited.connect(self._on_name_edited)
        prop_layout.addRow("名称:", self._name_edit)

        self._datatype_combo = QComboBox()
        self._datatype_combo.addItems(DATA_TYPE_NAMES)
        self._datatype_combo.currentIndexChanged.connect(self._on_datatype_changed)
        prop_layout.addRow("数据类型:", self._datatype_combo)

        self._access_combo = QComboBox()
        self._access_combo.addItems(ACCESS_TYPE_NAMES)
        self._access_combo.currentIndexChanged.connect(self._on_access_changed)
        prop_layout.addRow("访问类型:", self._access_combo)

        self._pdo_combo = QComboBox()
        self._pdo_combo.addItems(PDO_TYPE_NAMES)
        self._pdo_combo.currentIndexChanged.connect(self._on_pdo_changed)
        prop_layout.addRow("PDO 映射:", self._pdo_combo)

        self._default_edit = QLineEdit()
        self._default_edit.textEdited.connect(self._on_default_edited)
        prop_layout.addRow("默认值:", self._default_edit)

        self._disabled_check = QCheckBox()
        self._disabled_check.stateChanged.connect(self._on_disabled_changed)
        prop_layout.addRow("禁用:", self._disabled_check)

        self._desc_edit = QTextEdit()
        self._desc_edit.setMaximumHeight(60)
        self._desc_edit.textChanged.connect(self._on_desc_changed)
        prop_layout.addRow("描述:", self._desc_edit)

        right_splitter.addWidget(prop_group)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)

        right_layout.addWidget(right_splitter)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def set_eds(self, eds: Optional[EDS]) -> None:
        """设置 EDS 数据并刷新视图"""
        self._vm.set_eds(eds)
        self._refresh_all_ranges()
        self._safe_clear_table()
        self._safe_clear_properties()

    def _safe_clear_table(self) -> None:
        try:
            self._sub_table.setRowCount(0)
        except RuntimeError:
            pass

    def _safe_clear_properties(self) -> None:
        try:
            self._clear_properties()
        except RuntimeError:
            pass

    def refresh(self) -> None:
        """刷新整个视图"""
        self._refresh_all_ranges()

    def _refresh_all_ranges(self) -> None:
        """刷新所有 index range 列表"""
        self._com_range.refresh(self._vm)
        self._mfr_range.refresh(self._vm)
        self._dev_range.refresh(self._vm)

    def _on_entry_selected(self, index: int) -> None:
        """选中 OD 条目"""
        self._vm.select_object(index)
        self._refresh_sub_table()
        self._update_properties()

    def _refresh_sub_table(self) -> None:
        """刷新 sub-object 表格"""
        self._sub_table.setRowCount(0)
        sub_vms = self._vm.get_subobjects()

        for i, sub_vm in enumerate(sub_vms):
            self._sub_table.insertRow(i)

            # Sub index
            sub_item = QTableWidgetItem(sub_vm.subindex_hex)
            sub_item.setFlags(sub_item.flags() & ~Qt.ItemIsEditable)
            self._sub_table.setItem(i, 0, sub_item)

            # 名称
            self._sub_table.setItem(i, 1, QTableWidgetItem(sub_vm.name))

            # 数据类型
            dt_item = QTableWidgetItem(sub_vm.data_type_name)
            self._sub_table.setItem(i, 2, dt_item)

            # SDO
            sdo = sub_vm.od.access_sdo()
            self._sub_table.setItem(i, 3, QTableWidgetItem(sdo.name))

            # PDO
            pdo = sub_vm.od.access_pdo()
            self._sub_table.setItem(i, 4, QTableWidgetItem(pdo.name))

            # 默认值
            self._sub_table.setItem(i, 5, QTableWidgetItem(sub_vm.default_value))

            # 描述
            self._sub_table.setItem(i, 6, QTableWidgetItem(sub_vm.description))

    def _on_sub_cell_changed(self, row: int, col: int, prev_row: int, prev_col: int) -> None:
        """sub-object 表格选中行变化"""
        if row < 0:
            return
        sub_vms = self._vm.get_subobjects()
        if row < len(sub_vms):
            sub_vm = sub_vms[row]
            self._vm.select_subobject(sub_vm.subindex)
            self._update_properties()

    def _update_properties(self) -> None:
        """更新属性面板"""
        self._updating_ui = True

        sub = self._vm.selected_subobject
        obj = self._vm.selected_object

        if obj:
            self._index_label.setText(obj.index_hex)
        else:
            self._index_label.clear()

        if sub:
            self._subindex_label.setText(sub.subindex_hex)
            self._name_edit.setText(sub.name)
            self._default_edit.setText(sub.default_value)
            self._desc_edit.setPlainText(sub.description)
            self._disabled_check.setChecked(sub.disabled)

            # 数据类型
            dt_idx = list(DataType).index(sub.data_type) if sub.data_type in DataType else 0
            self._datatype_combo.setCurrentIndex(dt_idx)

            # 访问类型
            at_idx = list(AccessType).index(sub.access_type) if sub.access_type in AccessType else 0
            self._access_combo.setCurrentIndex(at_idx)

            # PDO 类型
            pt_idx = list(PDOMappingType).index(sub.pdo_type) if sub.pdo_type in PDOMappingType else 0
            self._pdo_combo.setCurrentIndex(pt_idx)
        else:
            self._subindex_label.clear()
            self._name_edit.clear()
            self._default_edit.clear()
            self._desc_edit.clear()
            self._disabled_check.setChecked(False)
            self._datatype_combo.setCurrentIndex(0)
            self._access_combo.setCurrentIndex(0)
            self._pdo_combo.setCurrentIndex(0)

        self._updating_ui = False

    def _clear_properties(self) -> None:
        """清空属性面板"""
        self._updating_ui = True
        self._index_label.clear()
        self._subindex_label.clear()
        self._name_edit.clear()
        self._default_edit.clear()
        self._desc_edit.clear()
        self._disabled_check.setChecked(False)
        self._datatype_combo.setCurrentIndex(0)
        self._access_combo.setCurrentIndex(0)
        self._pdo_combo.setCurrentIndex(0)
        self._updating_ui = False

    def _on_name_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        self._vm.update_subobject(name=text)

    def _on_datatype_changed(self, index: int) -> None:
        if self._updating_ui or index < 0:
            return
        dt = list(DataType)[index]
        self._vm.update_subobject(data_type=dt)

    def _on_access_changed(self, index: int) -> None:
        if self._updating_ui or index < 0:
            return
        at = list(AccessType)[index]
        self._vm.update_subobject(access_type=at)

    def _on_pdo_changed(self, index: int) -> None:
        if self._updating_ui or index < 0:
            return
        pt = list(PDOMappingType)[index]
        self._vm.update_subobject(pdo_type=pt)

    def _on_default_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        self._vm.update_subobject(default_value=text)

    def _on_disabled_changed(self, state: int) -> None:
        if self._updating_ui:
            return
        self._vm.update_subobject(disabled=state == Qt.Checked)

    def _on_desc_changed(self) -> None:
        if self._updating_ui:
            return
        self._vm.update_subobject(description=self._desc_edit.toPlainText())

    def _on_sub_context_menu(self, pos) -> None:
        """sub-object 右键菜单"""
        menu = QMenu(self)
        add_action = menu.addAction("添加 sub-object")
        remove_action = menu.addAction("删除 sub-object")

        current_row = self._sub_table.currentRow()
        remove_action.setEnabled(current_row >= 0)

        action = menu.exec(self._sub_table.mapToGlobal(pos))

        if action == add_action:
            self._vm.add_subobject()
            self._refresh_sub_table()
        elif action == remove_action and current_row >= 0:
            sub_vms = self._vm.get_subobjects()
            if current_row < len(sub_vms):
                self._vm.delete_subobject(sub_vms[current_row].subindex)
                self._refresh_sub_table()

    def _on_delete_entry(self, index: int) -> None:
        """删除 OD 条目"""
        reply = QMessageBox.question(
            self, "删除",
            f"确认删除 0x{index:04X}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._vm.delete_od_entry(index)
            self._refresh_all_ranges()
            self._sub_table.setRowCount(0)
            self._clear_properties()
