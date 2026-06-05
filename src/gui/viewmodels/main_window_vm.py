"""主窗口 ViewModel"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from ...core.models.eds import EDS


class DeviceVM(QObject):
    """单个设备的 ViewModel"""
    name_changed = Signal(str)

    def __init__(self, eds: EDS, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._eds = eds
        self._dirty = False

    @property
    def eds(self) -> EDS:
        return self._eds

    @property
    def name(self) -> str:
        return self._eds.di.ProductName or "未命名设备"

    @name.setter
    def name(self, value: str) -> None:
        self._eds.di.ProductName = value
        self.name_changed.emit(value)

    @property
    def dirty(self) -> bool:
        return self._dirty

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._dirty = value

    @property
    def filename(self) -> str:
        return self._eds.projectFilename or ""

    def __str__(self) -> str:
        name = self.name
        if self._dirty:
            name += " *"
        return name


class MainWindowVM(QObject):
    """主窗口 ViewModel"""
    device_added = Signal(object)
    device_removed = Signal(int)
    current_device_changed = Signal(object)
    status_message = Signal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._devices: list[DeviceVM] = []
        self._current_index = -1

    @property
    def devices(self) -> list[DeviceVM]:
        return self._devices

    @property
    def current_device(self) -> Optional[DeviceVM]:
        if 0 <= self._current_index < len(self._devices):
            return self._devices[self._current_index]
        return None

    @property
    def current_index(self) -> int:
        return self._current_index

    @current_index.setter
    def current_index(self, value: int) -> None:
        if value != self._current_index:
            self._current_index = value
            self.current_device_changed.emit(self.current_device)

    def new_device(self) -> DeviceVM:
        eds = EDS()
        eds.di.ProductName = f"新设备 {len(self._devices) + 1}"
        eds.projectFilename = ""
        vm = DeviceVM(eds, self)
        eds._on_data_dirty = lambda dirty, e: self._on_dirty(vm, dirty)
        self._devices.append(vm)
        self.device_added.emit(vm)
        self.current_index = len(self._devices) - 1
        self.status_message.emit(f"新建设备: {vm.name}")
        return vm

    def open_file(self, filepath: str) -> Optional[DeviceVM]:
        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
        eds = EDS()

        try:
            if ext in ("eds", "dcf"):
                from ...core.parsers.eds_parser import EDSParser
                EDSParser(eds).loadfile(filepath)
            elif ext in ("xdd", "xdc"):
                from ...core.parsers.xdd_handler import XDDHandler
                handler = XDDHandler()
                result = handler.read_xml(filepath)
                if result is None:
                    self.status_message.emit(f"无法加载: {filepath}")
                    return None
                eds = result
            else:
                self.status_message.emit(f"不支持的文件格式: .{ext}")
                return None
        except Exception as e:
            self.status_message.emit(f"加载失败: {e}")
            return None

        eds.projectFilename = filepath
        vm = DeviceVM(eds, self)
        eds._on_data_dirty = lambda dirty, e: self._on_dirty(vm, dirty)
        self._devices.append(vm)
        self.device_added.emit(vm)
        self.current_index = len(self._devices) - 1
        self.status_message.emit(f"已打开: {filepath}")
        return vm

    def save_file(self, filepath: str) -> bool:
        vm = self.current_device
        if vm is None:
            return False

        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
        try:
            if ext == "eds":
                vm.eds.Savefile(filepath)
            elif ext == "dcf":
                from ...core.models.info_section import Filetype
                vm.eds.Savefile(filepath, Filetype.FILE_DCF)
            elif ext in ("xdd", "xdc"):
                from ...core.parsers.xdd_handler import XDDHandler
                handler = XDDHandler()
                device_commissioning = (ext == "xdc")
                handler.write_xml(filepath, vm.eds, device_commissioning=device_commissioning, stripped=False)
            else:
                self.status_message.emit(f"不支持的保存格式: .{ext}")
                return False
        except Exception as e:
            self.status_message.emit(f"保存失败: {e}")
            return False

        vm.eds.projectFilename = filepath
        vm.dirty = False
        self.status_message.emit(f"已保存: {filepath}")
        return True

    def export_file(self, filepath: str, export_type: str = None) -> bool:
        vm = self.current_device
        if vm is None:
            return False

        from ...core.exporters.exporter_factory import Filetypes
        ext = "." + filepath.rsplit(".", 1)[-1] if "." in filepath else ""

        if export_type:
            exporter = Filetypes.find_by_description(export_type)
        else:
            matching = Filetypes.find_by_extension(ext)
            exporter = matching[0] if matching else None

        if exporter is None:
            self.status_message.emit(f"找不到导出器: {export_type or ext}")
            return False

        try:
            exporter.func(filepath, [vm.eds])
            self.status_message.emit(f"已导出: {filepath}")
            return True
        except Exception as e:
            self.status_message.emit(f"导出失败: {e}")
            return False

    def close_device(self, index: int) -> None:
        if 0 <= index < len(self._devices):
            self._devices.pop(index)
            self.device_removed.emit(index)
            if self._current_index >= len(self._devices):
                self._current_index = len(self._devices) - 1
            self.current_device_changed.emit(self.current_device)

    def _on_dirty(self, vm: DeviceVM, dirty: bool) -> None:
        vm.dirty = dirty
        if dirty:
            self.status_message.emit(f"数据已修改: {vm.name}")
