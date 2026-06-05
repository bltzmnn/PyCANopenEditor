"""补充高价值路径: Network XDD 往返, DCF 直接打开, Unicode 字段值

Network XDD 是多设备容器格式（nxdd/nxdc），需要验证：
- 打开后能解析出多个 device
- 修改任意 device 后能保存回 nxdd
- 重新打开后所有 device 都还在

测试 EDS 通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入。
"""
import os
import sys
import tempfile

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def qapp():
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


class TestNetworkXDDRoundTrip:
    def test_two_eds_to_nxdd_and_back(self, main_window, qapp):
        """两个 EDS 合并保存为 nxdd, 重新打开后两个 device 都保留"""
        from src.core.exporters.exporter_factory import Filetypes

        with tempfile.TemporaryDirectory() as tmpdir:
            edsa = os.path.join(tmpdir, "a.eds")
            edsb = os.path.join(tmpdir, "b.eds")
            main_window._vm.new_device()
            main_window._vm.current_device.eds.di.ProductName = "DeviceA"
            main_window._vm.current_device.eds.Savefile(edsa)
            main_window._vm.new_device()
            main_window._vm.current_device.eds.di.ProductName = "DeviceB"
            main_window._vm.current_device.eds.Savefile(edsb)

            nxdd = os.path.join(tmpdir, "net.nxdd")
            eds_a = main_window._vm.devices[0].eds
            eds_b = main_window._vm.devices[1].eds
            exp = Filetypes.find_by_description("CanOpen Network XDD v1.1")
            assert exp is not None
            exp.func(nxdd, [eds_a, eds_b])
            assert os.path.exists(nxdd)

            while len(main_window._vm.devices) > 0:
                main_window._vm.close_device(0)
                _process(qapp, 30)

            from src.core.parsers.xdd_handler import XDDHandler
            handler = XDDHandler()
            result = handler.read_multi_xml(nxdd)
            assert result is not None
            assert len(result) == 2, f"应有 2 个 device, 实际 {len(result)}"
            names = sorted(d.di.ProductName for d in result)
            assert names == ["DeviceA", "DeviceB"], f"设备名应保留: {names}"

    def test_nxdd_with_dc_preserves_nodeid(self, main_window, qapp):
        """保存为 nxdc (含 commissioning) 后 NodeID 应保留"""
        from src.core.exporters.exporter_factory import Filetypes
        from src.core.models.datatypes import AccessType

        with tempfile.TemporaryDirectory() as tmpdir:
            main_window._vm.new_device()
            dev = main_window._vm.current_device
            dev.eds.di.ProductName = "Commissioned"
            dev.eds.dc.NodeID = 0x42
            dev.eds.dc.NodeName = "node66"
            dev.eds.dc.Baudrate = 500000

            nxdc = os.path.join(tmpdir, "net.nxdc")
            exp = Filetypes.find_by_description("CanOpen Network XDC v1.1")
            assert exp is not None
            exp.func(nxdc, [dev.eds])
            assert os.path.exists(nxdc)

            from src.core.parsers.xdd_handler import XDDHandler
            result = XDDHandler().read_multi_xml(nxdc)
            assert result is not None and len(result) == 1
            loaded = result[0]
            assert loaded.dc.NodeID == 0x42, f"NodeID 应保留 0x42, 实际 {loaded.dc.NodeID:#x}"
            assert loaded.dc.NodeName == "node66"
            assert loaded.dc.Baudrate == 500000

            main_window._vm.close_device(0)
            _process(qapp, 30)


class TestDCFDirectOpen:
    def test_open_existing_dcf(self, main_window, qapp, eds_path):
        """DCF 文件应该能直接通过 open_file 打开"""
        from src.core.models.datatypes import AccessType

        with tempfile.TemporaryDirectory() as tmpdir:
            _open_file(main_window, eds_path, qapp)
            eds = main_window._vm.current_device.eds
            eds.ods[0x1000].defaultvalue = "0xCAFEBABE"
            eds.ods[0x1000].accesstype = AccessType.RO

            dcf_path = os.path.join(tmpdir, "test.dcf")
            main_window._vm.save_file(dcf_path)
            assert os.path.exists(dcf_path)

            main_window._vm.close_device(0)
            _process(qapp, 30)

            dev = main_window._vm.open_file(dcf_path)
            _process(qapp, 100)
            assert dev is not None
            assert "CAFEBABE" in dev.eds.ods[0x1000].defaultvalue.upper()
            ok = f"DCF 直接打开成功, 0x1000 value={dev.eds.ods[0x1000].defaultvalue}"
            print(ok)


class TestUnicodeFieldValues:
    def test_unicode_vendor_name(self, main_window, qapp, eds_path):
        """Unicode 字符（中/英/特殊符号）应能正确往返"""
        with tempfile.TemporaryDirectory() as tmpdir:
            _open_file(main_window, eds_path, qapp)
            dev = main_window._vm.current_device

            unicode_name = "供应商 Inc. — 2024"
            main_window._vendor_name_edit.setText(unicode_name)
            main_window._on_info_field_edited()
            _process(qapp, 50)

            assert dev.eds.di.VendorName == unicode_name

            eds_path = os.path.join(tmpdir, "unicode.eds")
            dev.eds.Savefile(eds_path)
            main_window._vm.close_device(0)
            _process(qapp, 30)

            dev2 = main_window._vm.open_file(eds_path)
            _process(qapp, 100)
            assert dev2.eds.di.VendorName == unicode_name, (
                f"Unicode vendor name 往返失败: 期望 {unicode_name!r}, 实际 {dev2.eds.di.VendorName!r}"
            )

    def test_unicode_in_od_name(self, main_window, qapp, eds_path):
        """OD 条目名称含 Unicode 应能正确往返"""
        with tempfile.TemporaryDirectory() as tmpdir:
            _open_file(main_window, eds_path, qapp)
            dev = main_window._vm.current_device

            from src.core.models.datatypes import DataType, AccessType, ObjectType
            dev.eds.ods[0x5F10] = dev.eds.ods.get(0x5F10) and dev.eds.ods[0x5F10] or type(
                dev.eds.ods[0x1000]
            )(
                parameter_name="温度传感器",
                index=0x5F10,
                datatype=DataType.UNSIGNED32,
                accesstype=AccessType.RW,
            )
            assert dev.eds.ods[0x5F10].parameter_name == "温度传感器"

            eds_path = os.path.join(tmpdir, "unicode_od.eds")
            dev.eds.Savefile(eds_path)
            main_window._vm.close_device(0)
            _process(qapp, 30)

            dev2 = main_window._vm.open_file(eds_path)
            _process(qapp, 100)
            assert 0x5F10 in dev2.eds.ods
            assert dev2.eds.ods[0x5F10].parameter_name == "温度传感器"
