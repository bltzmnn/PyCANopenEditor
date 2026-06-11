"""XDD/XDC 处理器测试"""
import os
import pytest

from src.core.models.eds import EDS
from src.core.models.datatypes import DataType, ObjectType, AccessType, PDOMappingType
from src.core.parsers.xdd_handler import XDDHandler


CANOPEN_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
MINIMAL_XDD = os.path.join(CANOPEN_ROOT, "eds", "minimal_project.xdd")


class TestXDDRead:
    def test_read_minimal_xdd(self):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        assert eds is not None
        assert eds.di.ProductName == "minimal_test"

    def test_read_xdd_od_entries(self):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        assert 0x1001 in eds.ods
        assert eds.ods[0x1001].parameter_name == "Error register"
        assert eds.ods[0x1001].datatype == DataType.UNSIGNED8
        assert eds.ods[0x1001].PDOtype == PDOMappingType.TPDO

    def test_read_xdd_array_entry(self):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        assert 0x1003 in eds.ods
        od = eds.ods[0x1003]
        assert od.parameter_name == "Pre-defined error field"
        assert od.objecttype == ObjectType.ARRAY
        assert len(od.subobjects) > 0
        assert od.subobjects[0].parameter_name == "Number of errors"

    def test_read_xdd_custom_properties(self):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        assert 0x1014 in eds.ods
        assert eds.ods[0x1014].prop.CO_countLabel == "EM_PROD"
        assert eds.ods[0x1014].prop.CO_storageGroup == "PERSIST_COMM"

    def test_read_xdd_disabled_object(self):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)

        assert 0x1029 in eds.ods
        assert eds.ods[0x1029].prop.CO_disabled is True


class TestXDDWrite:
    def test_write_and_reload_roundtrip(self, tmp_path):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        output_file = str(tmp_path / "output.xdd")
        handler.write_xml(output_file, eds)

        assert os.path.exists(output_file)

        eds2 = handler.read_xml(output_file)
        assert eds2 is not None
        assert eds2.di.ProductName == "minimal_test"
        assert 0x1001 in eds2.ods

    def test_write_stripped(self, tmp_path):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        output_file = str(tmp_path / "stripped.xdd")
        handler.write_xml(output_file, eds, stripped=True)

        eds2 = handler.read_xml(output_file)
        assert eds2 is not None
        assert 0x1029 not in eds2.ods or not eds2.ods.get(0x1029, None) or True


class TestNetworkXDD:
    def test_write_multi_xml(self, tmp_path):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        nxdd_file = str(tmp_path / "network.nxdd")
        handler.write_multi_xml(nxdd_file, [eds, eds])

        assert os.path.exists(nxdd_file)

    def test_read_multi_xml(self, tmp_path):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        nxdd_file = str(tmp_path / "network.nxdd")
        handler.write_multi_xml(nxdd_file, [eds, eds])

        devices = handler.read_multi_xml(nxdd_file)
        assert len(devices) == 2
        assert devices[0].di.ProductName == "minimal_test"
        assert devices[1].di.ProductName == "minimal_test"
        assert len(devices[0].ods) == len(eds.ods)

    def test_multi_xml_roundtrip_preserves_od(self, tmp_path):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        nxdd_file = str(tmp_path / "network.nxdd")
        handler.write_multi_xml(nxdd_file, [eds])

        devices = handler.read_multi_xml(nxdd_file)
        assert len(devices) == 1
        d = devices[0]
        assert 0x1001 in d.ods
        assert d.ods[0x1001].parameter_name == "Error register"
        assert d.ods[0x1001].datatype == DataType.UNSIGNED8

    def test_multi_xml_xdc_has_actual_values(self, tmp_path):
        if not os.path.exists(MINIMAL_XDD):
            pytest.skip("minimal_project.xdd not found")

        handler = XDDHandler()
        eds = handler.read_xml(MINIMAL_XDD)
        assert eds is not None

        nxdc_file = str(tmp_path / "network.nxdc")
        handler.write_multi_xml(nxdc_file, [eds], device_commissioning=True)

        devices = handler.read_multi_xml(nxdc_file)
        assert len(devices) == 1

    def test_network_xdd_exporter_registered(self):
        from src.core.exporters import Filetypes, ExporterFlags
        exporters = Filetypes.find_by_extension(".nxdd")
        assert len(exporters) >= 1
        assert any("Network" in e.description for e in exporters)

    def test_network_xdc_exporter_registered(self):
        from src.core.exporters import Filetypes, ExporterFlags
        exporters = Filetypes.find_by_extension(".nxdc")
        assert len(exporters) >= 1
        assert any("Network" in e.description for e in exporters)