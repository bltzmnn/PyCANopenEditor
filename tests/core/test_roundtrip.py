"""Round-trip 和兼容性测试。

外部 EDS 样本通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入；未设置时
涉及样本 EDS 的测试会通过 `pytest.skip` 自动跳过。

仓库自带样本：
- `tests/core/test_data/minimal.eds` —— 用于 EDS 基础 round-trip
- `eds/minimal_project.xdd`（可选） —— 用于 XDD round-trip
"""
import os
import tempfile
import pytest

from src.core.models.eds import EDS
from src.core.models.info_section import Filetype
from src.core.models.datatypes import DataType, ObjectType, AccessType
from src.core.parsers.eds_parser import EDSParser, EDSWriter
from src.core.parsers.xdd_handler import XDDHandler


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
MINIMAL_XDD = os.path.join(REPO_ROOT, "eds", "minimal_project.xdd")


class TestEDSRoundTrip:
    """EDS round-trip 兼容性测试"""

    def test_minimal_eds_roundtrip(self, tmp_path):
        """使用 tests/core/test_data/minimal.eds 做 round-trip"""
        minimal_eds = os.path.join(os.path.dirname(__file__), "test_data", "minimal.eds")
        if not os.path.exists(minimal_eds):
            pytest.skip("minimal.eds not found")

        eds = EDS()
        EDSParser(eds).loadfile(minimal_eds)

        output = str(tmp_path / "rt.eds")
        eds.Savefile(output, Filetype.FILE_EDS)

        eds2 = EDS()
        EDSParser(eds2).loadfile(output)

        assert len(eds.ods) == len(eds2.ods)
        for idx in eds.ods:
            assert idx in eds2.ods, f"OD index {idx:#x} 丢失"
            assert eds.ods[idx].parameter_name == eds2.ods[idx].parameter_name
            assert eds.ods[idx].datatype == eds2.ods[idx].datatype

    def test_external_eds_files_roundtrip(self, test_eds_files):
        """使用外部 EDS 样本（PYCANOPEN_TEST_EDS_DIR）做 round-trip"""
        for path in test_eds_files:
            eds = EDS()
            EDSParser(eds).loadfile(path)

            with tempfile.NamedTemporaryFile(suffix='.eds', delete=False) as tmp:
                tmpfile = tmp.name
            try:
                eds.Savefile(tmpfile, Filetype.FILE_EDS)

                eds2 = EDS()
                EDSParser(eds2).loadfile(tmpfile)

                assert len(eds.ods) == len(eds2.ods), \
                    f"{os.path.basename(path)}: OD 数量不一致 {len(eds.ods)} != {len(eds2.ods)}"
            finally:
                os.unlink(tmpfile)

    def test_eds_roundtrip_preserves_device_info(self, tmp_path):
        """验证 EDS round-trip 保留 DeviceInfo"""
        minimal_eds = os.path.join(os.path.dirname(__file__), "test_data", "minimal.eds")
        if not os.path.exists(minimal_eds):
            pytest.skip("minimal.eds not found")

        eds = EDS()
        EDSParser(eds).loadfile(minimal_eds)

        output = str(tmp_path / "rt.eds")
        eds.Savefile(output, Filetype.FILE_EDS)

        eds2 = EDS()
        EDSParser(eds2).loadfile(output)

        assert eds2.di.VendorName == eds.di.VendorName
        assert eds2.di.ProductName == eds.di.ProductName
        assert eds2.di.VendorNumber == eds.di.VendorNumber

    def test_eds_roundtrip_preserves_subobjects(self, tmp_path):
        """验证 EDS round-trip 保留 sub-objects"""
        minimal_eds = os.path.join(os.path.dirname(__file__), "test_data", "minimal.eds")
        if not os.path.exists(minimal_eds):
            pytest.skip("minimal.eds not found")

        eds = EDS()
        EDSParser(eds).loadfile(minimal_eds)

        output = str(tmp_path / "rt.eds")
        eds.Savefile(output, Filetype.FILE_EDS)

        eds2 = EDS()
        EDSParser(eds2).loadfile(output)

        for idx in eds.ods:
            od1 = eds.ods[idx]
            od2 = eds2.ods[idx]
            assert len(od1.subobjects) == len(od2.subobjects), \
                f"Index {idx:#x} sub-objects 数量不一致"
            for sub_idx in od1.subobjects:
                assert sub_idx in od2.subobjects, \
                    f"Sub-index {idx:#x}:{sub_idx:#x} 丢失"
                assert od1.subobjects[sub_idx].datatype == od2.subobjects[sub_idx].datatype


class TestXDDRoundTrip:
    """XDD round-trip 测试"""

    def test_minimal_xdd_roundtrip(self, tmp_path):
        """XDD → 写 → 读 → 验证 OD 一致"""
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        output = str(tmp_path / "rt.xdd")
        handler.write_xml(output, eds)

        eds2 = handler.read_xml(output)
        assert eds2 is not None

        assert len(eds.ods) == len(eds2.ods)
        for idx in eds.ods:
            assert idx in eds2.ods, f"OD index {idx:#x} 丢失"
            assert eds.ods[idx].parameter_name == eds2.ods[idx].parameter_name

    def test_xdd_roundtrip_preserves_properties(self, tmp_path):
        """验证 XDD round-trip 保留自定义属性"""
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        output = str(tmp_path / "rt.xdd")
        handler.write_xml(output, eds)

        eds2 = handler.read_xml(output)

        if 0x1014 in eds.ods and 0x1014 in eds2.ods:
            assert eds.ods[0x1014].prop.CO_countLabel == eds2.ods[0x1014].prop.CO_countLabel
            assert eds.ods[0x1014].prop.CO_storageGroup == eds2.ods[0x1014].prop.CO_storageGroup

    def test_xdd_roundtrip_preserves_access_type(self, tmp_path):
        """验证 XDD round-trip 保留访问类型"""
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        output = str(tmp_path / "rt.xdd")
        handler.write_xml(output, eds)

        eds2 = handler.read_xml(output)

        for idx in eds.ods:
            if idx in eds2.ods:
                assert eds.ods[idx].accesstype == eds2.ods[idx].accesstype, \
                    f"Index {idx:#x} access type 不一致"

    def test_xdc_roundtrip(self, tmp_path):
        """XDC (含 actual value) round-trip"""
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        output = str(tmp_path / "rt.xdc")
        handler.write_xml(output, eds, device_commissioning=True)

        eds2 = handler.read_xml(output)
        assert eds2 is not None
        assert len(eds.ods) == len(eds2.ods)

    def test_xdd_stripped_roundtrip(self, tmp_path):
        """XDD stripped 模式 round-trip（禁用对象被跳过）"""
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        output = str(tmp_path / "stripped.xdd")
        handler.write_xml(output, eds, stripped=True)

        eds2 = handler.read_xml(output)
        assert eds2 is not None
        assert 0x1029 not in eds2.ods


class TestCrossFormatCompat:
    """跨格式兼容性验证"""

    def test_xdd_to_eds_to_xdd(self, tmp_path):
        """XDD → EDS → XDD round-trip（EDS 不保留 disabled 对象）"""
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        # XDD → EDS
        eds_file = str(tmp_path / "from_xdd.eds")
        eds.Savefile(eds_file, Filetype.FILE_EDS)

        # EDS → 重新加载
        eds2 = EDS()
        EDSParser(eds2).loadfile(eds_file)

        # EDS → XDD
        xdd_file = str(tmp_path / "from_eds.xdd")
        handler.write_xml(xdd_file, eds2)

        # XDD → 重新加载
        eds3 = handler.read_xml(xdd_file)
        assert eds3 is not None

        # EDS 不保留 CO_disabled 对象，所以只验证非 disabled 条目
        active_ods = {idx: od for idx, od in eds.ods.items() if not od.prop.CO_disabled}
        for idx in active_ods:
            assert idx in eds3.ods, f"OD index {idx:#x} (非 disabled) 丢失"
            assert active_ods[idx].parameter_name == eds3.ods[idx].parameter_name

    def test_eds_to_xdd_preserves_core_data(self, tmp_path):
        """EDS → XDD 保留核心数据"""
        minimal_eds = os.path.join(os.path.dirname(__file__), "test_data", "minimal.eds")
        if not os.path.exists(minimal_eds):
            pytest.skip("minimal.eds not found")

        eds = EDS()
        EDSParser(eds).loadfile(minimal_eds)

        handler = XDDHandler()
        xdd_file = str(tmp_path / "from_eds.xdd")
        handler.write_xml(xdd_file, eds)

        eds2 = handler.read_xml(xdd_file)
        assert eds2 is not None
        assert eds2.di.VendorName == eds.di.VendorName
        assert eds2.di.ProductName == eds.di.ProductName
        assert 0x1000 in eds2.ods


class TestProtobufCompat:
    """Protobuf 跨版本兼容性测试"""

    @pytest.fixture
    def _check_protobuf(self):
        try:
            from src.core.exporters.protobuf_handler import _PROTOBUF_AVAILABLE
            if not _PROTOBUF_AVAILABLE:
                pytest.skip("Protobuf 模块不可用")
        except ImportError:
            pytest.skip("Protobuf 模块不可用")

    def test_protobuf_in_memory_roundtrip(self, _check_protobuf):
        """EDS → protobuf → EDS 内存中 round-trip"""
        from src.core.exporters.protobuf_handler import _eds_to_proto, _proto_to_eds

        handler = XDDHandler()
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        device = _eds_to_proto(eds)
        eds2 = _proto_to_eds(device)

        assert len(eds.ods) == len(eds2.ods)
        for idx in sorted(eds.ods.keys()):
            assert idx in eds2.ods, f"OD {idx:#x} 丢失"
            assert eds.ods[idx].parameter_name == eds2.ods[idx].parameter_name

    def test_protobuf_binpb_file_roundtrip(self, _check_protobuf, tmp_path):
        """.binpb 文件写出再读回"""
        from src.core.exporters.protobuf_handler import _eds_to_proto, load_protobuf_binpb

        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")
        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        device = _eds_to_proto(eds)
        binpb_file = str(tmp_path / "device.binpb")
        with open(binpb_file, "wb") as f:
            f.write(device.SerializeToString())

        eds2 = load_protobuf_binpb(binpb_file)
        assert len(eds.ods) == len(eds2.ods)

    def test_protobuf_json_file_roundtrip(self, _check_protobuf, tmp_path):
        """.json 文件写出再读回"""
        from src.core.exporters.protobuf_handler import _eds_to_proto, load_protobuf_json
        from google.protobuf.json_format import MessageToJson

        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")
        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        device = _eds_to_proto(eds)
        json_file = str(tmp_path / "device.json")
        json_str = MessageToJson(device, preserving_proto_field_name=True)
        with open(json_file, "w") as f:
            f.write(json_str)

        eds2 = load_protobuf_json(json_file)
        assert len(eds.ods) == len(eds2.ods)

    def test_protobuf_preserves_device_info(self, _check_protobuf):
        """Protobuf round-trip 保留 DeviceInfo"""
        from src.core.exporters.protobuf_handler import _eds_to_proto, _proto_to_eds

        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")
        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        device = _eds_to_proto(eds)
        eds2 = _proto_to_eds(device)

        assert eds2.di.VendorName == eds.di.VendorName
        assert eds2.di.ProductName == eds.di.ProductName

    def test_protobuf_preserves_od_structure(self, _check_protobuf):
        """Protobuf round-trip 保留 OD 结构（objecttype + sub-objects）"""
        from src.core.exporters.protobuf_handler import _eds_to_proto, _proto_to_eds

        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")
        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        device = _eds_to_proto(eds)
        eds2 = _proto_to_eds(device)

        for idx in sorted(eds.ods.keys()):
            od1 = eds.ods[idx]
            od2 = eds2.ods[idx]
            assert od1.objecttype == od2.objecttype, \
                f"{idx:#x} objecttype: {od1.objecttype} != {od2.objecttype}"
            assert len(od1.subobjects) == len(od2.subobjects), \
                f"{idx:#x} sub count: {len(od1.subobjects)} != {len(od2.subobjects)}"

    def test_protobuf_preserves_custom_properties(self, _check_protobuf):
        """Protobuf round-trip 保留 CO_disabled / CO_countLabel / CO_storageGroup"""
        from src.core.exporters.protobuf_handler import _eds_to_proto, _proto_to_eds

        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")
        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        device = _eds_to_proto(eds)
        eds2 = _proto_to_eds(device)

        if 0x1014 in eds.ods and 0x1014 in eds2.ods:
            assert eds.ods[0x1014].prop.CO_countLabel == eds2.ods[0x1014].prop.CO_countLabel
            assert eds.ods[0x1014].prop.CO_storageGroup == eds2.ods[0x1014].prop.CO_storageGroup

        if 0x1029 in eds.ods and 0x1029 in eds2.ods:
            assert eds.ods[0x1029].prop.CO_disabled == eds2.ods[0x1029].prop.CO_disabled

    def test_protobuf_cli_export(self, _check_protobuf, tmp_path):
        """通过 CLI 导出 Protobuf 二进制文件"""
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")
        from src.cli.main import main

        out_file = str(tmp_path / "device.binpb")
        ret = main(["--type", "Protobuf Binary", "--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 0
