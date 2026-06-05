"""EDS/DCF 解析器和生成器测试"""
import os
import pytest

from src.core.models.eds import EDS
from src.core.models.info_section import Filetype
from src.core.models.datatypes import DataType, ObjectType, AccessType, PDOMappingType
from src.core.parsers.eds_parser import EDSParser, EDSWriter


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")
MINIMAL_EDS = os.path.join(TEST_DATA_DIR, "minimal.eds")


class TestEDSParser:
    def test_load_minimal_eds(self):
        eds = EDS()
        parser = EDSParser(eds)
        parser.loadfile(MINIMAL_EDS)

        assert eds.fi.FileName == "minimal.eds"
        assert eds.fi.EDSVersion == "4.0"
        assert eds.di.VendorName == "TestVendor"
        assert eds.di.ProductName == "TestProduct"
        assert eds.di.BaudRate_10 is True
        assert eds.di.BaudRate_1000 is True

    def test_load_od_entries(self):
        eds = EDS()
        parser = EDSParser(eds)
        parser.loadfile(MINIMAL_EDS)

        assert 0x1000 in eds.ods
        assert eds.ods[0x1000].parameter_name == "Device type"
        assert eds.ods[0x1000].datatype == DataType.UNSIGNED32
        assert eds.ods[0x1000].objecttype == ObjectType.VAR
        assert eds.ods[0x1000].accesstype == AccessType.RO

    def test_load_record_entry(self):
        eds = EDS()
        parser = EDSParser(eds)
        parser.loadfile(MINIMAL_EDS)

        assert 0x1018 in eds.ods
        od = eds.ods[0x1018]
        assert od.parameter_name == "Identity"
        assert od.objecttype == ObjectType.RECORD
        assert len(od.subobjects) == 4
        assert od.subobjects[1].parameter_name == "Vendor-ID"
        assert od.subobjects[1].datatype == DataType.UNSIGNED32

    def test_dummy_usage(self):
        eds = EDS()
        parser = EDSParser(eds)
        parser.loadfile(MINIMAL_EDS)

        assert eds.du.Dummy0001 is False
        assert eds.du.Dummy0007 is False

    def test_comments(self):
        eds = EDS()
        parser = EDSParser(eds)
        parser.loadfile(MINIMAL_EDS)

        assert len(eds.c.comments) == 1
        assert eds.c.comments[0] == "Test EDS file"


class TestEDSWriter:
    def test_save_and_reload_roundtrip(self, tmp_path):
        eds = EDS()
        parser = EDSParser(eds)
        parser.loadfile(MINIMAL_EDS)

        output_file = str(tmp_path / "output.eds")
        writer = EDSWriter(eds)
        writer.savefile(output_file, Filetype.FILE_EDS)

        assert os.path.exists(output_file)

        eds2 = EDS()
        parser2 = EDSParser(eds2)
        parser2.loadfile(output_file)

        assert eds2.fi.FileName == "output.eds"
        assert eds2.di.VendorName == "TestVendor"
        assert eds2.di.ProductName == "TestProduct"
        assert 0x1000 in eds2.ods
        assert eds2.ods[0x1000].parameter_name == "Device type"
        assert eds2.ods[0x1000].datatype == DataType.UNSIGNED32

    def test_dcf_output(self, tmp_path):
        eds = EDS()
        parser = EDSParser(eds)
        parser.loadfile(MINIMAL_EDS)

        output_file = str(tmp_path / "output.dcf")
        writer = EDSWriter(eds)
        writer.savefile(output_file, Filetype.FILE_DCF)

        assert os.path.exists(output_file)

        eds2 = EDS()
        parser2 = EDSParser(eds2)
        parser2.loadfile(output_file)

        assert eds2.di.VendorName == "TestVendor"
        assert eds2.ods[0x1000].parameter_name == "Device type"


class TestEDSParserSpaceTolerance:
    def test_key_value_spaces(self):
        content = """[FileInfo]
FileName = test.eds
FileVersion = 1
EDSVersion=4.0

[DeviceInfo]
VendorName = TestVendor
ProductName = TestProduct
"""
        eds = EDS()
        parser = EDSParser(eds)

        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".eds", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            parser.loadfile(f.name)
            os.unlink(f.name)

        assert eds.fi.FileName == "test.eds"
        assert eds.di.VendorName == "TestVendor"
        assert eds.di.ProductName == "TestProduct"


class TestModuleParsing:
    def test_module_info_section(self):
        content = """[FileInfo]
FileName=test.eds
FileVersion=1
EDSVersion=4.0

[DeviceInfo]
VendorName=TestVendor
ProductName=TestProduct

[SupportedModules]
NrOfEntries=1

[M1ModuleInfo]
ProductName=Module1
ProductVersion=1
ProductRevision=1

[M1Comments]
Lines=0

[M1SubExtends]
SupportedObjects=0
"""
        eds = EDS()
        parser = EDSParser(eds)

        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".eds", delete=False, encoding="utf-8") as f:
            f.write(content)
            f.flush()
            parser.loadfile(f.name)
            os.unlink(f.name)

        assert 1 in eds.modules
        assert eds.modules[1].mi.ProductName == "Module1"