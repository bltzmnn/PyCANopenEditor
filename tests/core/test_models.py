"""数据模型单元测试"""
import pytest

from src.core.models.datatypes import (
    AccessPDO,
    AccessSDO,
    AccessSRDO,
    AccessType,
    DataType,
    ObjectType,
    PDOMappingType,
    DATA_TYPE_SIZE_BITS,
)
from src.core.models.eds import EDS
from src.core.models.info_section import (
    Comments,
    DeviceCommissioning,
    DeviceInfo,
    DummyUsage,
    FileInfo,
    MandatoryObjects,
    Module,
    OptionalObjects,
)
from src.core.models.od_entry import CustomProperties, ODentry
from src.core.models.pdo_helper import PDOHelper, PDOMappingEntry, PDOSlot
from src.core.models.warnings import WarningClass, Warnings


class TestDataType:
    def test_values_match_csharp(self):
        assert DataType.UNKNOWN == 0
        assert DataType.BOOLEAN == 1
        assert DataType.INTEGER8 == 2
        assert DataType.UNSIGNED32 == 7
        assert DataType.VISIBLE_STRING == 9
        assert DataType.PDO_COMMUNICATION_PARAMETER == 0x20
        assert DataType.PDO_MAPPING == 0x21
        assert DataType.UNSIGNED64 == 0x1B

    def test_size_bits_lookup(self):
        assert DATA_TYPE_SIZE_BITS[DataType.BOOLEAN] == 1
        assert DATA_TYPE_SIZE_BITS[DataType.UNSIGNED8] == 8
        assert DATA_TYPE_SIZE_BITS[DataType.UNSIGNED16] == 16
        assert DATA_TYPE_SIZE_BITS[DataType.UNSIGNED32] == 32
        assert DATA_TYPE_SIZE_BITS[DataType.UNSIGNED64] == 64
        assert DATA_TYPE_SIZE_BITS[DataType.REAL32] == 32
        assert DATA_TYPE_SIZE_BITS[DataType.REAL64] == 64


class TestObjectType:
    def test_values_match_csharp(self):
        assert ObjectType.UNKNOWN == -1
        assert ObjectType.NULL == 0
        assert ObjectType.VAR == 7
        assert ObjectType.ARRAY == 8
        assert ObjectType.RECORD == 9


class TestAccessType:
    def test_values_match_csharp(self):
        assert AccessType.RW == 0
        assert AccessType.RO == 1
        assert AccessType.WO == 2
        assert AccessType.RWR == 3
        assert AccessType.RWW == 4
        assert AccessType.CONST == 5
        assert AccessType.UNKNOWN == 6


class TestODentry:
    def test_var_constructor(self):
        od = ODentry(
            parameter_name="Test Object",
            index=0x1000,
            datatype=DataType.UNSIGNED32,
            defaultvalue="0x0",
            accesstype=AccessType.RW,
            pdo_type=PDOMappingType.NO,
        )
        assert od.parameter_name == "Test Object"
        assert od.index == 0x1000
        assert od.datatype == DataType.UNSIGNED32
        assert od.objecttype == ObjectType.VAR
        assert od.accesstype == AccessType.RW
        assert od.Nosubindexes == 0

    def test_index_from_parent(self):
        parent = ODentry(index=0x1000)
        child = ODentry(parent=parent)
        assert child.index == 0x1000

    def test_subindex(self):
        parent = ODentry(index=0x1000, objecttype=ObjectType.RECORD)
        sub = ODentry(parameter_name="sub", parent=parent)
        parent.addsubobject(1, sub)
        assert sub.Subindex == 1

    def test_access_sdo(self):
        od_ro = ODentry(accesstype=AccessType.RO)
        assert od_ro.access_sdo() == AccessSDO.RO
        od_rw = ODentry(accesstype=AccessType.RW)
        assert od_rw.access_sdo() == AccessSDO.RW
        od_wo = ODentry(accesstype=AccessType.WO)
        assert od_wo.access_sdo() == AccessSDO.WO

    def test_access_pdo(self):
        od_t = ODentry(pdo_type=PDOMappingType.TPDO)
        assert od_t.access_pdo() == AccessPDO.T
        od_r = ODentry(pdo_type=PDOMappingType.RPDO)
        assert od_r.access_pdo() == AccessPDO.R

    def test_sizeof_datatype(self):
        od = ODentry(datatype=DataType.UNSIGNED32)
        assert od.sizeof_datatype() == 32
        od8 = ODentry(datatype=DataType.UNSIGNED8)
        assert od8.sizeof_datatype() == 8
        od_bool = ODentry(datatype=DataType.BOOLEAN)
        assert od_bool.sizeof_datatype() == 1

    def test_clone(self):
        od = ODentry(
            parameter_name="Original",
            index=0x2000,
            datatype=DataType.UNSIGNED16,
            defaultvalue="0x100",
            accesstype=AccessType.RW,
        )
        cloned = od.clone()
        assert cloned.parameter_name == "Original"
        assert cloned.index == 0x2000
        assert cloned.datatype == DataType.UNSIGNED16
        cloned.parameter_name = "Modified"
        assert od.parameter_name == "Original"

    def test_parameter_cname(self):
        od = ODentry(parameter_name="Error register")
        assert od.parameter_cname() == "Errorregister"
        od2 = ODentry(parameter_name="rx-pdo")
        assert od2.parameter_cname() == "rx_pdo"


class TestCustomProperties:
    def test_defaults(self):
        cp = CustomProperties()
        assert cp.CO_disabled is False
        assert cp.CO_countLabel == ""
        assert cp.CO_storageGroup == "RAM"
        assert cp.CO_flagsPDO is False
        assert cp.CO_accessSRDO == AccessSRDO.NO
        assert cp.CO_stringLengthMin == 0

    def test_clone(self):
        cp = CustomProperties(CO_disabled=True, CO_countLabel="TPDO")
        cloned = cp.clone()
        assert cloned.CO_disabled is True
        assert cloned.CO_countLabel == "TPDO"
        cloned.CO_disabled = False
        assert cp.CO_disabled is True


class TestEDS:
    def test_init(self):
        eds = EDS()
        assert isinstance(eds.fi, FileInfo)
        assert isinstance(eds.di, DeviceInfo)
        assert isinstance(eds.du, DummyUsage)
        assert isinstance(eds.dc, DeviceCommissioning)
        assert isinstance(eds.md, MandatoryObjects)
        assert isinstance(eds.oo, OptionalObjects)
        assert isinstance(eds.c, Comments)
        assert eds.fi.EDSVersionMajor == 4
        assert eds.fi.EDSVersionMinor == 0
        assert len(eds.dummy_ods) == 6

    def test_dummy_ods(self):
        eds = EDS()
        assert eds.dummy_ods[0x002].parameter_name == "Dummy Int8"
        assert eds.dummy_ods[0x007].parameter_name == "Dummy UInt32"

    def test_getobject(self):
        eds = EDS()
        od = ODentry(parameter_name="Test", index=0x1000, datatype=DataType.UNSIGNED16)
        eds.ods[0x1000] = od
        assert eds.Getobject(0x1000) is od
        assert eds.Getobject(0x002) is eds.dummy_ods[0x002]
        assert eds.Getobject(0x9999) is None

    def test_try_get_od_entry(self):
        eds = EDS()
        od = ODentry(index=0x1000)
        eds.ods[0x1000] = od
        assert eds.tryGetODEntry(0x1000) is od
        assert eds.tryGetODEntry(0x002) is eds.dummy_ods[0x002]
        assert eds.tryGetODEntry(0x9999) is None

    def test_dirty_flag(self):
        eds = EDS()
        assert eds.Dirty is False
        eds.Dirty = True
        assert eds.Dirty is True


class TestPDOSlot:
    def test_configuration_index_txpdo(self):
        slot = PDOSlot()
        slot.ConfigurationIndex = 0x1800
        assert slot.MappingIndex == 0x1A00
        assert slot.isTXPDO() is True
        assert slot.isRXPDO() is False

    def test_configuration_index_rxpdo(self):
        slot = PDOSlot()
        slot.ConfigurationIndex = 0x1400
        assert slot.MappingIndex == 0x1600
        assert slot.isRXPDO() is True
        assert slot.isTXPDO() is False

    def test_invalid_bit(self):
        slot = PDOSlot()
        slot.COB = 0x181
        assert slot.invalid is False
        slot.invalid = True
        assert slot.invalid is True
        assert slot.COB & 0x80000000 != 0

    def test_insert_mapping(self):
        slot = PDOSlot()
        entry = PDOMappingEntry(width=32)
        slot.insertMapping(0, entry)
        assert len(slot.Mapping) == 1

    def test_insert_mapping_overflow(self):
        slot = PDOSlot()
        slot.insertMapping(0, PDOMappingEntry(width=32))
        slot.insertMapping(1, PDOMappingEntry(width=16))
        assert len(slot.Mapping) == 2
        slot.insertMapping(2, PDOMappingEntry(width=32))
        assert len(slot.Mapping) == 2


class TestWarnings:
    def setup_method(self):
        Warnings.warning_list.clear()
        Warnings.warning_mask = 0xFFFF

    def test_add_warning(self):
        Warnings.add_warning("test warning")
        assert len(Warnings.warning_list) == 1
        assert Warnings.warning_list[0] == "test warning"

    def test_warning_mask(self):
        Warnings.warning_mask = 0x00
        Warnings.add_warning("should be filtered", WarningClass.WARNING_GENERIC)
        assert len(Warnings.warning_list) == 0

    def test_clear(self):
        Warnings.add_warning("test")
        Warnings.clear()
        assert len(Warnings.warning_list) == 0


class TestInfoSection:
    def test_fileinfo_parse(self):
        fi = FileInfo()
        fi.parse({
            "FileName": "test.eds",
            "FileVersion": "1",
            "FileRevision": "1",
            "EDSVersion": "4.0",
            "Description": "Test file",
        })
        assert fi.FileName == "test.eds"
        assert fi.FileVersion == "1"
        assert fi.FileRevision == 1
        assert fi.EDSVersion == "4.0"

    def test_deviceinfo_parse(self):
        di = DeviceInfo()
        di.parse({
            "VendorName": "TestVendor",
            "ProductName": "TestProduct",
            "VendorNumber": "0x123",
            "BaudRate_10": "1",
            "BaudRate_1000": "0",
        })
        assert di.VendorName == "TestVendor"
        assert di.ProductName == "TestProduct"
        assert di.BaudRate_10 is True
        assert di.BaudRate_1000 is False

    def test_module_init(self):
        m = Module(moduleindex=1)
        assert m.mi is not None
        assert m.mc is not None
        assert m.moduleindex == 1