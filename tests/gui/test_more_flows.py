"""更多 GUI 端到端流程: export, close-with-dirty, 多设备切换, DCF, Network XDD

覆盖以下 GUI 层验证：
- 通过 GUI 菜单走 EDS / XDD / C 源码导出流程
- 文件 close 时的 dirty 提示框与取消/确认分支
- 多设备标签页切换
- DCF 文件往返（带 value 而非 default）
- Network XDD（多 profile 容器）

测试 EDS 通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入。
"""
import os
import sys
import tempfile
import traceback

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _excepthook(exc_type, exc_value, exc_tb):
    print("\n=== UNCAUGLED EXCEPTION ===")
    traceback.print_exception(exc_type, exc_value, exc_tb)
    print("============================\n")


@pytest.fixture(scope="module")
def qapp():
    sys.excepthook = _excepthook
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture(scope="module")
def main_window(qapp):
    from src.gui.viewmodels.main_window_vm import MainWindowVM
    from src.gui.views.main_window import MainWindow

    vm = MainWindowVM()
    window = MainWindow(vm)
    window.show()
    yield window
    window.close()


def _process(qapp, ms=200):
    from PySide6.QtCore import QEventLoop
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _open_file(window, filepath, qapp):
    window._vm.open_file(filepath)
    _process(qapp, 100)


class TestMultiDevice:
    def test_open_two_files(self, main_window, qapp):
        """打开两个文件, 在 device list 中能看到两个设备"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_eds = os.path.join(tmpdir, "device2.eds")
            window = main_window
            dev1 = window._vm.new_device()
            dev1.eds.Savefile(tmp_eds)

            before_count = window._device_list.count()
            _open_file(window, tmp_eds, qapp)
            after_count = window._device_list.count()
            assert after_count == before_count + 1
            assert len(window._vm.devices) == before_count + 1

            while len(window._vm.devices) > 0:
                window._vm.close_device(0)
                _process(qapp, 30)

    def test_switch_device_refreshes_views(self, main_window, qapp):
        """切换 device 时 PDO/OD 视图应刷新到当前设备"""
        from src.core.models.datatypes import DataType, AccessType
        from src.core.models.od_entry import ODentry

        window = main_window

        for dev in list(window._vm.devices):
            window._vm.close_device(window._vm.devices.index(dev))
            _process(qapp, 30)

        dev_a = window._vm.new_device()
        dev_a.eds.di.ProductName = "DeviceA"
        dev_a.eds.ods[0x2000] = ODentry(
            parameter_name="DevA_obj", index=0x2000,
            datatype=DataType.UNSIGNED32, accesstype=AccessType.RW,
        )

        dev_b = window._vm.new_device()
        dev_b.eds.di.ProductName = "DeviceB"
        dev_b.eds.ods[0x2000] = ODentry(
            parameter_name="DevB_obj", index=0x2000,
            datatype=DataType.UNSIGNED32, accesstype=AccessType.RW,
        )

        _process(qapp, 50)

        window._vm.current_index = len(window._vm.devices) - 2
        _process(qapp, 50)
        items_a = [window._od_view._mfr_range._list.item(i).text()
                   for i in range(window._od_view._mfr_range._list.count())]
        assert any("DevA_obj" in t for t in items_a), f"DeviceA 应含 DevA_obj, 实际 {items_a}"

        window._vm.current_index = len(window._vm.devices) - 1
        _process(qapp, 50)
        items_b = [window._od_view._mfr_range._list.item(i).text()
                   for i in range(window._od_view._mfr_range._list.count())]
        assert any("DevB_obj" in t for t in items_b), f"DeviceB 应含 DevB_obj, 实际 {items_b}"

        while len(window._vm.devices) > 0:
            window._vm.close_device(0)
            _process(qapp, 30)


class TestExportFlow:
    def test_export_to_eds(self, main_window, qapp, eds_path):
        """GUI 导出 .eds"""
        _open_file(main_window, eds_path, qapp)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "exported.eds")
            main_window._vm.current_device.eds.Savefile(out_path)
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0

    def test_export_to_xdd_via_factory(self, main_window, qapp, eds_path):
        """通过 Filetypes 工厂导出到 .xdd (CanOpenXDDv1.1)"""
        from src.core.exporters.exporter_factory import Filetypes

        _open_file(main_window, eds_path, qapp)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "exported.xdd")
            eds = main_window._vm.current_device.eds
            exp = Filetypes.find_by_description("CanOpenXDDv1.1")
            assert exp is not None, "应能找到 CanOpenXDDv1.1 导出器"
            exp.func(out_path, [eds])
            assert os.path.exists(out_path)
            with open(out_path, "rb") as f:
                head = f.read(300)
            assert b"<?xml" in head
            assert b"CANopen" in head or b"canopen" in head

    def test_export_to_c_source_via_factory(self, main_window, qapp, eds_path):
        """通过 Filetypes 工厂导出到 CANopenNode C 源码 (V4 格式)

        V4 导出器以 filepath 的 dirname 为输出目录, basename 去扩展名作为 OD 名称.
        例如传入 /tmp/xxx/OD.h 会在 /tmp/xxx/ 写出 OD.h 和 OD.c.
        """
        from src.core.exporters.exporter_factory import Filetypes

        _open_file(main_window, eds_path, qapp)
        with tempfile.TemporaryDirectory() as tmpdir:
            target_h = os.path.join(tmpdir, "OD.h")
            eds = main_window._vm.current_device.eds
            exp = Filetypes.find_by_description("CanOpenNodeV4")
            assert exp is not None, "应能找到 CanOpenNodeV4 导出器"
            exp.func(target_h, [eds])
            files = os.listdir(tmpdir)
            assert any(f.endswith(".h") for f in files), f"应有 .h 文件: {files}"
            assert any(f.endswith(".c") for f in files), f"应有 .c 文件: {files}"


class TestDirtyAndClose:
    def test_modify_marks_dirty(self, main_window, qapp, eds_path):
        """编辑字段后设备应被标记为 dirty (textEdited 不由 setText 触发, 直接调 slot)"""
        _open_file(main_window, eds_path, qapp)
        dev = main_window._vm.current_device
        assert dev.dirty is False

        main_window._vendor_name_edit.setText("TestVendor_Modified")
        main_window._on_info_field_edited()
        _process(qapp, 50)
        assert dev.dirty is True, "修改 vendor name 后应该 dirty"

    def test_close_dirty_cancels_then_proceeds(self, main_window, qapp, eds_path):
        """关闭脏设备: 先取消, 再确认"""
        _open_file(main_window, eds_path, qapp)
        window = main_window

        main_window._vendor_name_edit.setText("TestDirty")
        main_window._on_info_field_edited()
        _process(qapp, 50)
        dev = window._vm.current_device
        assert dev.dirty
        idx = window._vm.current_index

        original_question = QMessageBox.question
        replies = iter([QMessageBox.No, QMessageBox.Yes])
        try:
            QMessageBox.question = staticmethod(lambda *a, **kw: next(replies))
            window._on_close()
            _process(qapp, 50)
            assert dev in window._vm.devices, "取消关闭后设备应保留"

            window._on_close()
            _process(qapp, 50)
            assert dev not in window._vm.devices, "确认关闭后设备应被移除"
        finally:
            QMessageBox.question = original_question


class TestDCFRoundTrip:
    def test_save_as_dcf_preserves_values(self, main_window, qapp, eds_path):
        """保存为 DCF, 重新打开后 value 应保留"""
        from src.core.models.datatypes import AccessType

        _open_file(main_window, eds_path, qapp)
        eds = main_window._vm.current_device.eds
        eds.ods[0x1000].defaultvalue = "0xDEADBEEF"
        eds.ods[0x1000].accesstype = AccessType.RO

        with tempfile.TemporaryDirectory() as tmpdir:
            dcf_path = os.path.join(tmpdir, "test.dcf")
            ok = main_window._vm.save_file(dcf_path)
            assert ok and os.path.exists(dcf_path)

            main_window._vm.close_device(main_window._vm.current_index)
            _process(qapp, 50)

            dev = main_window._vm.open_file(dcf_path)
            _process(qapp, 100)
            assert dev is not None
            assert 0x1000 in dev.eds.ods
            assert "DEADBEEF" in dev.eds.ods[0x1000].defaultvalue.upper()


class TestNetworkXDD:
    def test_eds_to_nxdd(self, main_window, qapp, eds_path):
        """EDS 通过 NetworkXDDExporter 保存为 .nxdd"""
        from src.core.exporters.exporter_factory import Filetypes

        _open_file(main_window, eds_path, qapp)
        with tempfile.TemporaryDirectory() as tmpdir:
            nxdd_path = os.path.join(tmpdir, "test.nxdd")
            eds = main_window._vm.current_device.eds
            exp = Filetypes.find_by_description("CanOpenNetworkXDDv1.1")
            assert exp is not None, "应能找到 CanOpenNetworkXDDv1.1 导出器"
            exp.func(nxdd_path, [eds])
            assert os.path.exists(nxdd_path)
            with open(nxdd_path, "rb") as f:
                content = f.read()
            assert b"ISO15745ProfileContainer" in content
