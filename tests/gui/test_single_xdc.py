"""补充测试: 单设备 XDC 往返 commissioning

测试 EDS 通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入；未设置时跳过。
"""
import os
import sys
import tempfile

import pytest
from PySide6.QtWidgets import QApplication


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_single_xdc_round_trip_preserves_dc(qapp, eds_path):
    """单设备 XDC 文件往返应保留 NodeID/NodeName/Baudrate"""
    from src.core.exporters.exporter_factory import Filetypes
    from src.core.parsers.xdd_handler import XDDHandler

    exp = Filetypes.find_by_description("CanOpenXDCv1.1")
    assert exp is not None

    with tempfile.TemporaryDirectory() as tmpdir:
        from src.core.parsers.eds_parser import EDSParser
        from src.core.models.eds import EDS
        eds = EDS()
        EDSParser(eds).loadfile(eds_path)
        eds.dc.NodeID = 0x07
        eds.dc.NodeName = "my_node"
        eds.dc.Baudrate = 250000

        xdc = os.path.join(tmpdir, "single.xdc")
        exp.func(xdc, [eds])
        assert os.path.exists(xdc)

        loaded = XDDHandler().read_xml(xdc)
        assert loaded is not None
        assert loaded.dc.NodeID == 0x07, f"NodeID 应保留 0x07, 实际 {loaded.dc.NodeID:#x}"
        assert loaded.dc.NodeName == "my_node"
        assert loaded.dc.Baudrate == 250000
        print(f"单设备 XDC 往返 OK: NodeID={loaded.dc.NodeID:#x}, Baudrate={loaded.dc.Baudrate}")
