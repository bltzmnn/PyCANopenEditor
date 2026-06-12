"""CANopenNode V4 导出器单元测试"""
import os
import tempfile

import pytest

from src.core.exporters.canopen_node_exporter_v4 import (
    CanOpenNodeExporterV4,
    DataProperties,
    get_attributes,
    get_data_properties,
    make_cname_v4,
)
from src.core.models.datatypes import (
    AccessPDO,
    AccessSDO,
    AccessSRDO,
    AccessType,
    DataType,
    ObjectType,
    PDOMappingType,
)
from src.core.models.eds import EDS
from src.core.models.od_entry import ODentry


class TestMakeCnameV4:
    def test_simple_name(self):
        assert make_cname_v4("Device type") == "deviceType"

    def test_empty_name(self):
        assert make_cname_v4("") == ""

    def test_starts_with_digit(self):
        result = make_cname_v4("1000 device")
        assert result.startswith("_")

    def test_single_char(self):
        assert make_cname_v4("x") == "x"

    def test_camel_case(self):
        result = make_cname_v4("vendor ID")
        assert "vendor" in result


class TestGetDataProperties:
    def test_unsigned8(self):
        data = get_data_properties(DataType.UNSIGNED8, "0x05", 0, "1000")
        assert data.c_type == "uint8_t"
        assert data.length == 1
        assert data.c_value == "0x05"

    def test_unsigned16(self):
        data = get_data_properties(DataType.UNSIGNED16, "0x1234", 0, "1000")
        assert data.c_type == "uint16_t"
        assert data.length == 2
        assert data.c_value == "0x1234"

    def test_unsigned32(self):
        data = get_data_properties(DataType.UNSIGNED32, "0x12345678", 0, "1000")
        assert data.c_type == "uint32_t"
        assert data.length == 4
        assert data.c_value == "0x12345678"

    def test_boolean_true(self):
        data = get_data_properties(DataType.BOOLEAN, "1", 0, "1000")
        assert data.c_type == "bool_t"
        assert data.c_value == "true"

    def test_boolean_false(self):
        data = get_data_properties(DataType.BOOLEAN, "0", 0, "1000")
        assert data.c_value == "false"

    def test_integer8(self):
        data = get_data_properties(DataType.INTEGER8, "-1", 0, "1000")
        assert data.c_type == "int8_t"
        assert data.length == 1

    def test_domain(self):
        data = get_data_properties(DataType.DOMAIN, "", 0, "1000")
        assert data.c_type == "not specified"
        assert data.c_value is None

    def test_visible_string(self):
        data = get_data_properties(DataType.VISIBLE_STRING, "Hi", 0, "1000")
        assert data.c_type == "char"
        assert data.c_type_string is True
        assert "'H'" in data.c_value
        assert "'i'" in data.c_value

    def test_octet_string(self):
        data = get_data_properties(DataType.OCTET_STRING, "01 02", 0, "1000")
        assert data.c_type == "uint8_t"
        assert "0x01" in data.c_value

    def test_unsigned24(self):
        data = get_data_properties(DataType.UNSIGNED24, "0x123456", 0, "1000")
        assert data.length == 3
        assert data.c_type == "uint8_t"
        assert data.c_type_array == "[3]"

    def test_empty_default(self):
        data = get_data_properties(DataType.UNSIGNED8, "", 0, "1000")
        assert data.c_value is None


class TestGetAttributes:
    def test_read_only(self):
        od = ODentry(accesstype=AccessType.RO)
        attr = get_attributes(od, False, False)
        assert "ODA_SDO_R" in attr

    def test_write_only(self):
        od = ODentry(accesstype=AccessType.WO)
        attr = get_attributes(od, False, False)
        assert "ODA_SDO_W" in attr

    def test_read_write(self):
        od = ODentry(accesstype=AccessType.RW)
        attr = get_attributes(od, False, False)
        assert "ODA_SDO_RW" in attr

    def test_multibyte(self):
        od = ODentry(accesstype=AccessType.RO)
        attr = get_attributes(od, True, False)
        assert "ODA_MB" in attr

    def test_string(self):
        od = ODentry(accesstype=AccessType.RO)
        attr = get_attributes(od, False, True)
        assert "ODA_STR" in attr


def _make_minimal_eds() -> EDS:
    eds = EDS()
    eds.projectFilename = "test.eds"
    eds.fi.FileVersion = "1"
    eds.fi.CreationTime = "10:00AM"
    eds.fi.CreationDate = "01-01-2024"
    eds.fi.CreatedBy = "TestUser"
    eds.fi.ModificationTime = "11:00AM"
    eds.fi.ModificationDate = "01-02-2024"
    eds.fi.ModifiedBy = "TestUser2"
    eds.fi.CreationDateTime = "10:00AM 01-01-2024"
    eds.fi.ModificationDateTime = "11:00AM 01-02-2024"
    eds.fi.Description = "Test device"
    eds.di.VendorName = "TestVendor"
    eds.di.VendorNumber = "0x1234"
    eds.di.ProductName = "TestProduct"
    eds.di.ProductNumber = "0x5678"

    od_1000 = ODentry(
        parameter_name="Device type",
        index=0x1000,
        datatype=DataType.UNSIGNED32,
        defaultvalue="0x00000000",
        accesstype=AccessType.RO,
    )
    od_1000.prop.CO_storageGroup = "ROM"
    eds.ods[0x1000] = od_1000

    od_1001 = ODentry(
        parameter_name="Error register",
        index=0x1001,
        datatype=DataType.UNSIGNED8,
        defaultvalue="0x00",
        accesstype=AccessType.RO,
    )
    od_1001.prop.CO_storageGroup = "RAM"
    eds.ods[0x1001] = od_1001

    od_1018 = ODentry(
        parameter_name="Identity object",
        index=0x1018,
        objecttype=ObjectType.RECORD,
    )
    od_1018.prop.CO_storageGroup = "ROM"
    sub0 = ODentry(
        parameter_name="Number of entries",
        index=0x1018,
        datatype=DataType.UNSIGNED8,
        defaultvalue="0x04",
        accesstype=AccessType.RO,
        parent=od_1018,
    )
    sub1 = ODentry(
        parameter_name="Vendor-ID",
        index=0x1018,
        datatype=DataType.UNSIGNED32,
        defaultvalue="0x00000000",
        accesstype=AccessType.RO,
        parent=od_1018,
    )
    sub2 = ODentry(
        parameter_name="Product code",
        index=0x1018,
        datatype=DataType.UNSIGNED32,
        defaultvalue="0x00000000",
        accesstype=AccessType.RO,
        parent=od_1018,
    )
    sub3 = ODentry(
        parameter_name="Revision number",
        index=0x1018,
        datatype=DataType.UNSIGNED32,
        defaultvalue="0x00000000",
        accesstype=AccessType.RO,
        parent=od_1018,
    )
    sub4 = ODentry(
        parameter_name="Serial number",
        index=0x1018,
        datatype=DataType.UNSIGNED32,
        defaultvalue="0x00000000",
        accesstype=AccessType.RO,
        parent=od_1018,
    )
    od_1018.subobjects = {0: sub0, 1: sub1, 2: sub2, 3: sub3, 4: sub4}
    eds.ods[0x1018] = od_1018

    return eds


class TestV4Exporter:
    def test_export_produces_files(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            assert os.path.exists(os.path.join(tmpdir, "OD.h"))
            assert os.path.exists(os.path.join(tmpdir, "OD.c"))

    def test_h_file_contains_header_guard(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            with open(os.path.join(tmpdir, "OD.h")) as f:
                content = f.read()
            assert "#ifndef OD_H" in content
            assert "#define OD_H" in content

    def test_h_file_contains_storage_declarations(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            with open(os.path.join(tmpdir, "OD.h")) as f:
                content = f.read()
            assert "OD_ROM_t" in content
            assert "OD_RAM_t" in content

    def test_h_file_contains_entry_shortcuts(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            with open(os.path.join(tmpdir, "OD.h")) as f:
                content = f.read()
            assert "OD_ENTRY_H1000" in content

    def test_c_file_contains_version_check(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            with open(os.path.join(tmpdir, "OD.c")) as f:
                content = f.read()
            assert "CO_VERSION_MAJOR" in content

    def test_c_file_contains_od_definition(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            with open(os.path.join(tmpdir, "OD.c")) as f:
                content = f.read()
            assert "OD_DEFINITION" in content
            assert "ODList" in content

    def test_c_file_contains_objects(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            with open(os.path.join(tmpdir, "OD.c")) as f:
                content = f.read()
            assert "ODObjs" in content
            assert "OD_obj_var_t" in content

    def test_v4_h_file_contains_config_structure(self):
        eds = _make_minimal_eds()
        exporter = CanOpenNodeExporterV4()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "OD")
            exporter._export(filepath, eds)
            with open(os.path.join(tmpdir, "OD.h")) as f:
                content = f.read()
            assert "OD_INIT_CONFIG" in content


class TestExporterRegistration:
    def test_v4_registered(self):
        from src.core.exporters.exporter_factory import Filetypes
        exporters = Filetypes.find_by_extension(".h")
        descriptions = [e.description for e in exporters]
        assert "CanOpenNodeV4" in descriptions

    def test_find_by_description(self):
        from src.core.exporters.exporter_factory import Filetypes
        result = Filetypes.find_by_description("CanOpenNodeV4")
        assert result is not None
        assert result.description == "CanOpenNodeV4"
