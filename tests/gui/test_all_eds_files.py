"""遍历外部 EDS 样本做解析与多格式往返测试。

EDS 样本通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入：fixture 会扫描
该目录下所有 `.eds` 文件并逐个跑解析、EDS 往返、XDD 导出和
CANopenNode C 源码导出。未设置环境变量时测试自动跳过。
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


def _load(path):
    from src.core.parsers.eds_parser import EDSParser
    from src.core.models.eds import EDS
    eds = EDS()
    EDSParser(eds).loadfile(path)
    return eds


def _get_exporter(description):
    from src.core.exporters.exporter_factory import Filetypes
    return Filetypes.find_by_description(description)


def test_parse_all_eds_files(test_eds_files):
    """所有外部 EDS 样本都能成功解析。"""
    for path in test_eds_files:
        eds = _load(path)
        fname = os.path.basename(path)
        assert eds is not None
        assert len(eds.ods) > 0, f"{fname}: 至少应有 1 个 OD 条目"
        assert eds.di.ProductName or eds.di.VendorName, (
            f"{fname}: 至少应有一个产品/厂商名"
        )


def test_eds_round_trip_all_files(test_eds_files, qapp):
    """所有外部 EDS 样本 EDS 往返：核心字段保留。"""
    for path in test_eds_files:
        eds = _load(path)
        fname = os.path.basename(path)
        original_product = eds.di.ProductName
        original_vendor = eds.di.VendorName
        original_od_count = len(eds.ods)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "rt.eds")
            eds.Savefile(out_path)
            assert os.path.exists(out_path)

            eds2 = _load(out_path)
            assert eds2.di.ProductName == original_product, (
                f"{fname}: ProductName 丢失: {original_product!r} -> {eds2.di.ProductName!r}"
            )
            assert eds2.di.VendorName == original_vendor, (
                f"{fname}: VendorName 丢失: {original_vendor!r} -> {eds2.di.VendorName!r}"
            )
            assert len(eds2.ods) == original_od_count, (
                f"{fname}: OD 数量变化: {original_od_count} -> {len(eds2.ods)}"
            )


def test_xdd_export_all_files(test_eds_files):
    """所有外部 EDS 样本都能导出为 XDD。"""
    exp = _get_exporter("CanOpenXDDv1.1")
    assert exp is not None

    for path in test_eds_files:
        eds = _load(path)
        fname = os.path.basename(path)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "rt.xdd")
            exp.func(out_path, [eds])
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 1000, f"{fname}: 导出 XDD 太小，可能不完整"

            from src.core.parsers.xdd_handler import XDDHandler
            loaded = XDDHandler().read_xml(out_path)
            assert loaded is not None
            assert loaded.di.ProductName == eds.di.ProductName, (
                f"{fname}: XDD 往返 ProductName 不匹配"
            )
            assert len(loaded.ods) == len(eds.ods), (
                f"{fname}: XDD 往返 OD 数量不匹配: {len(eds.ods)} -> {len(loaded.ods)}"
            )


def test_canopennode_c_export_all_files(test_eds_files):
    """所有外部 EDS 样本都能导出为 CANopenNode C 源码。"""
    exp = _get_exporter("CanOpenNodeV4")
    assert exp is not None

    for path in test_eds_files:
        eds = _load(path)
        fname = os.path.basename(path)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "OD.h")
            exp.func(out_path, [eds])
            assert os.path.exists(out_path)

            with open(out_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            assert "OD_" in content or "CO_OD" in content, (
                f"{fname}: C 导出文件不含 OD_/CO_OD 关键字"
            )
            assert eds.di.ProductName in content or eds.di.ProductNumber in content, (
                f"{fname}: C 导出文件不含设备标识: {eds.di.ProductName!r}"
            )
