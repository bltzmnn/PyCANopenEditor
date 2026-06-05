"""主窗口 View"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar, QDockWidget,
    QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QTabWidget, QLabel, QPushButton, QLineEdit, QGroupBox,
    QFormLayout, QComboBox, QSplitter, QHeaderView,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon

from ..viewmodels.main_window_vm import MainWindowVM, DeviceVM
from ..viewmodels.od_vm import ODViewModel
from ..viewmodels.pdo_vm import PDOViewModel
from ..viewmodels.profile_vm import ProfileViewModel
from .od_view import ODView
from .pdo_view import PDOView
from .profile_view import ProfileDialog
from .module_view import ModuleView
from ...core.models.datatypes import DataType
from ...core.models.eds import EDS


class MainWindow(QMainWindow):
    """主窗口，对应 C# MainWindow.axaml"""

    def __init__(self, vm: MainWindowVM, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._vm = vm
        self.setWindowTitle("PyCANopenEditor")
        self.resize(1200, 800)

        # 创建 ViewModel
        self._od_vm = ODViewModel()
        self._pdo_vm = PDOViewModel()
        self._profile_vm = ProfileViewModel(self)

        self._setup_menu()
        self._setup_toolbar()
        self._setup_central()
        self._setup_statusbar()

        vm.device_added.connect(self._on_device_added)
        vm.device_removed.connect(self._on_device_removed)
        vm.current_device_changed.connect(self._on_current_changed)
        vm.status_message.connect(self._on_status)

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&文件")

        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self._on_new)
        file_menu.addAction(new_action)

        open_action = QAction("打开...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open)
        file_menu.addAction(open_action)

        save_action = QAction("保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save)
        file_menu.addAction(save_action)

        save_as_action = QAction("另存为...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._on_save_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        export_action = QAction("导出...", self)
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        insert_profile_action = QAction("导入 Profile...", self)
        insert_profile_action.triggered.connect(self._on_insert_profile)
        file_menu.addAction(insert_profile_action)

        file_menu.addSeparator()

        close_action = QAction("关闭", self)
        close_action.triggered.connect(self._on_close)
        file_menu.addAction(close_action)

        quit_action = QAction("退出", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        toolbar.addAction("新建", self._on_new)
        toolbar.addAction("打开", self._on_open)
        toolbar.addAction("保存", self._on_save)

    def _setup_central(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        self._device_list = QListWidget()
        self._device_list.setMaximumWidth(300)
        self._device_list.currentRowChanged.connect(self._on_list_row_changed)
        splitter.addWidget(self._device_list)

        self._device_tabs = QTabWidget()
        self._info_widget = QWidget()

        self._setup_info_widget()

        # OD 视图（使用 ODView 替换占位符）
        self._od_view = ODView(self._od_vm)

        # PDO 视图（使用 PDOView 替换占位符）
        self._pdo_view = PDOView(self._pdo_vm)

        # Module 视图
        self._module_view = ModuleView()

        self._device_tabs.addTab(self._info_widget, "设备信息")
        self._device_tabs.addTab(self._od_view, "对象字典")
        self._device_tabs.addTab(self._pdo_view, "PDO 映射")
        self._device_tabs.addTab(self._module_view, "Modules")
        splitter.addWidget(self._device_tabs)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

    def _setup_info_widget(self) -> None:
        layout = QFormLayout(self._info_widget)

        self._vendor_name_edit = QLineEdit()
        self._vendor_number_edit = QLineEdit()
        self._product_name_edit = QLineEdit()
        self._product_number_edit = QLineEdit()
        self._revision_number_edit = QLineEdit()
        self._granularity_edit = QLineEdit()

        layout.addRow("供应商名称:", self._vendor_name_edit)
        layout.addRow("供应商编号:", self._vendor_number_edit)
        layout.addRow("产品名称:", self._product_name_edit)
        layout.addRow("产品编号:", self._product_number_edit)
        layout.addRow("版本号:", self._revision_number_edit)
        layout.addRow("粒度:", self._granularity_edit)

        dc_group = QGroupBox("Device Commissioning")
        dc_layout = QFormLayout(dc_group)
        self._dc_node_id_edit = QLineEdit()
        self._dc_node_name_edit = QLineEdit()
        self._dc_baudrate_edit = QLineEdit()
        dc_layout.addRow("Node ID:", self._dc_node_id_edit)
        dc_layout.addRow("Node Name:", self._dc_node_name_edit)
        dc_layout.addRow("Baudrate:", self._dc_baudrate_edit)
        layout.addRow(dc_group)

        for edit in [
            self._vendor_name_edit, self._vendor_number_edit,
            self._product_name_edit, self._product_number_edit,
            self._revision_number_edit, self._granularity_edit,
            self._dc_node_id_edit, self._dc_node_name_edit,
            self._dc_baudrate_edit,
        ]:
            edit.textEdited.connect(self._on_info_field_edited)

    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("就绪")

    def _on_new(self) -> None:
        self._vm.new_device()

    def _on_open(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "",
            "EDS 文件 (*.eds);;DCF 文件 (*.dcf);;XDD 文件 (*.xdd *.xdc);;所有文件 (*)"
        )
        if filepath:
            self._vm.open_file(filepath)

    def _on_save(self) -> None:
        vm = self._vm.current_device
        if vm is None:
            return
        filepath = vm.filename
        if not filepath:
            self._on_save_as()
            return
        self._vm.save_file(filepath)

    def _on_save_as(self) -> None:
        vm = self._vm.current_device
        if vm is None:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "另存为", "",
            "EDS 文件 (*.eds);;DCF 文件 (*.dcf);;XDD 文件 (*.xdd *.xdc)"
        )
        if filepath:
            self._vm.save_file(filepath)

    def _on_export(self) -> None:
        vm = self._vm.current_device
        if vm is None:
            return

        from ...core.exporters.exporter_factory import Filetypes
        exporters = Filetypes.get_exporters()

        items = [f"{e.description} ({', '.join(e.filetypes)})" for e in exporters]
        from PySide6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(
            self, "导出", "选择导出格式:", items, 0, False
        )
        if not ok:
            return

        idx = items.index(choice)
        exporter = exporters[idx]

        ext = exporter.filetypes[0]
        filepath, _ = QFileDialog.getSaveFileName(
            self, f"导出 {exporter.description}", "", f"{exporter.description} (*{ext})"
        )
        if filepath:
            self._vm.export_file(filepath, exporter.description)

    def _on_insert_profile(self) -> None:
        dev_vm = self._vm.current_device
        if dev_vm is None:
            QMessageBox.information(self, "提示", "请先打开或新建一个设备")
            return

        import os
        profile_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "profiles"
        )

        dialog = ProfileDialog(
            self._profile_vm, dev_vm.eds, profile_dir, self
        )
        if dialog.exec() == QDialog.Accepted:
            self._od_view.set_eds(dev_vm.eds)
            self._pdo_view.set_eds(dev_vm.eds)
            self._statusbar.showMessage("Profile 导入完成", 5000)

    def _on_close(self) -> None:
        idx = self._vm.current_index
        if idx < 0:
            return
        vm = self._vm.current_device
        if vm and vm.dirty:
            reply = QMessageBox.question(
                self, "关闭", f"设备 '{vm.name}' 有未保存的修改，确认关闭?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        self._vm.close_device(idx)

    def _on_list_row_changed(self, row: int) -> None:
        self._vm.current_index = row

    def _on_device_added(self, vm: DeviceVM) -> None:
        item = QListWidgetItem(str(vm))
        self._device_list.addItem(item)

    def _on_device_removed(self, idx: int) -> None:
        if 0 <= idx < self._device_list.count():
            self._device_list.takeItem(idx)

    def _on_current_changed(self, vm: Optional[DeviceVM]) -> None:
        try:
            self._update_current_device(vm)
        except RuntimeError:
            # widget C++ 对象尚未就绪（构造期间信号触发），延迟到事件循环
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._update_current_device(vm))

    def _update_current_device(self, vm: Optional[DeviceVM]) -> None:
        if vm is None:
            self._clear_info_fields()
            self._od_view.set_eds(None)
            self._pdo_view.set_eds(None)
            self._module_view.set_eds(None)
            return

        eds = vm.eds
        self._vendor_name_edit.setText(eds.di.VendorName)
        self._vendor_number_edit.setText(eds.di.VendorNumber)
        self._product_name_edit.setText(eds.di.ProductName)
        self._product_number_edit.setText(eds.di.ProductNumber)
        self._revision_number_edit.setText(str(eds.di.RevisionNumber))
        self._granularity_edit.setText(str(eds.di.Granularity))

        self._dc_node_id_edit.setText(str(eds.dc.NodeID))
        self._dc_node_name_edit.setText(eds.dc.NodeName)
        self._dc_baudrate_edit.setText(str(eds.dc.Baudrate))

        self._od_view.set_eds(eds)
        self._pdo_view.set_eds(eds)
        self._module_view.set_eds(eds)

    def _on_info_field_edited(self) -> None:
        vm = self._vm.current_device
        if vm is None:
            return
        eds = vm.eds
        eds.di.VendorName = self._vendor_name_edit.text()
        eds.di.VendorNumber = self._vendor_number_edit.text()
        eds.di.ProductName = self._product_name_edit.text()
        eds.di.ProductNumber = self._product_number_edit.text()
        try:
            eds.di.RevisionNumber = int(self._revision_number_edit.text() or "0")
        except ValueError:
            pass
        try:
            eds.di.Granularity = int(self._granularity_edit.text() or "8")
        except ValueError:
            pass

        try:
            eds.dc.NodeID = int(self._dc_node_id_edit.text() or "0")
        except ValueError:
            pass
        eds.dc.NodeName = self._dc_node_name_edit.text()
        try:
            eds.dc.Baudrate = int(self._dc_baudrate_edit.text() or "0")
        except ValueError:
            pass

        eds.Dirty = True

    def _clear_info_fields(self) -> None:
        for edit in [
            self._vendor_name_edit, self._vendor_number_edit,
            self._product_name_edit, self._product_number_edit,
            self._revision_number_edit, self._granularity_edit,
            self._dc_node_id_edit, self._dc_node_name_edit,
            self._dc_baudrate_edit,
        ]:
            edit.clear()

    def _on_status(self, msg: str) -> None:
        self._statusbar.showMessage(msg, 5000)
