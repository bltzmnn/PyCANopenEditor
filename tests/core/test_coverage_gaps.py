"""补充测试覆盖：PDOHelper、ODentry 边界、EDS 辅助方法、ExporterFactory"""
import os
import tempfile

import pytest

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
from src.core.models.od_entry import ODentry, _get_base, _convert_to_uint16
from src.core.models.pdo_helper import PDOHelper, PDOMappingEntry, PDOSlot
from src.core.models.info_section import Filetype
from src.core.models.warnings import Warnings
from src.core.parsers.eds_parser import EDSParser, EDSWriter
from src.core.parsers.xdd_handler import XDDHandler
from src.core.exporters.exporter_factory import Filetypes, ExporterFlags


# ── PDOHelper 测试 ──────────────────────────────────────────────

class TestPDOHelper:
    """PDOHelper 单元测试"""

    def _make_eds_with_pdo(self) -> EDS:
        eds = EDS()

        # TX PDO 通信参数 (0x1800)
        od_1800 = ODentry(
            parameter_name="TPDO communication parameter",
            index=0x1800,
            objecttype=ObjectType.RECORD,
        )
        od_1800.subobjects[0] = ODentry(
            parameter_name="max sub-index", index=0x1800,
            datatype=DataType.UNSIGNED8, defaultvalue="0x05",
            accesstype=AccessType.RO, parent=od_1800,
        )
        od_1800.subobjects[1] = ODentry(
            parameter_name="COB-ID", index=0x1800,
            datatype=DataType.UNSIGNED32, defaultvalue="$NODEID+0x180",
            accesstype=AccessType.RW, parent=od_1800,
        )
        od_1800.subobjects[2] = ODentry(
            parameter_name="transmission type", index=0x1800,
            datatype=DataType.UNSIGNED8, defaultvalue="254",
            accesstype=AccessType.RW, parent=od_1800,
        )
        od_1800.subobjects[3] = ODentry(
            parameter_name="inhibit time", index=0x1800,
            datatype=DataType.UNSIGNED16, defaultvalue="100",
            accesstype=AccessType.RW, parent=od_1800,
        )
        od_1800.subobjects[5] = ODentry(
            parameter_name="event timer", index=0x1800,
            datatype=DataType.UNSIGNED16, defaultvalue="50",
            accesstype=AccessType.RW, parent=od_1800,
        )
        eds.ods[0x1800] = od_1800

        # TX PDO 映射 (0x1A00)
        od_1a00 = ODentry(
            parameter_name="TPDO mapping", index=0x1A00,
            objecttype=ObjectType.RECORD,
        )
        od_1a00.subobjects[0] = ODentry(
            parameter_name="Number of mapped objects", index=0x1A00,
            datatype=DataType.UNSIGNED8, defaultvalue="0x01",
            accesstype=AccessType.RO, parent=od_1a00,
        )
        od_1a00.subobjects[1] = ODentry(
            parameter_name="mapped object 1", index=0x1A00,
            datatype=DataType.UNSIGNED32, defaultvalue="0x10000020",
            accesstype=AccessType.RO, parent=od_1a00,
        )
        eds.ods[0x1A00] = od_1a00

        # RX PDO 通信参数 (0x1400)
        od_1400 = ODentry(
            parameter_name="RPDO communication parameter",
            index=0x1400,
            objecttype=ObjectType.RECORD,
        )
        od_1400.subobjects[0] = ODentry(
            parameter_name="max sub-index", index=0x1400,
            datatype=DataType.UNSIGNED8, defaultvalue="0x02",
            accesstype=AccessType.RO, parent=od_1400,
        )
        od_1400.subobjects[1] = ODentry(
            parameter_name="COB-ID", index=0x1400,
            datatype=DataType.UNSIGNED32, defaultvalue="0x00000200",
            accesstype=AccessType.RW, parent=od_1400,
        )
        od_1400.subobjects[2] = ODentry(
            parameter_name="transmission type", index=0x1400,
            datatype=DataType.UNSIGNED8, defaultvalue="255",
            accesstype=AccessType.RW, parent=od_1400,
        )
        eds.ods[0x1400] = od_1400

        # RX PDO 映射 (0x1600)
        od_1600 = ODentry(
            parameter_name="RPDO mapping", index=0x1600,
            objecttype=ObjectType.RECORD,
        )
        od_1600.subobjects[0] = ODentry(
            parameter_name="Number of mapped objects", index=0x1600,
            datatype=DataType.UNSIGNED8, defaultvalue="0x01",
            accesstype=AccessType.RO, parent=od_1600,
        )
        od_1600.subobjects[1] = ODentry(
            parameter_name="mapped object 1", index=0x1600,
            datatype=DataType.UNSIGNED32, defaultvalue="0x10000020",
            accesstype=AccessType.RW, parent=od_1600,
        )
        eds.ods[0x1600] = od_1600

        # 被映射的对象
        eds.ods[0x1000] = ODentry(
            parameter_name="Device type", index=0x1000,
            datatype=DataType.UNSIGNED32, defaultvalue="0x00000000",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.TPDO,
        )

        return eds

    def test_build_pdo_lists(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        assert len(helper.pdoslots) >= 2

    def test_txpdo_slot(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        assert len(tx_slots) >= 1
        slot = tx_slots[0]
        assert slot.ConfigurationIndex == 0x1800
        assert slot.MappingIndex == 0x1A00

    def test_rxpdo_slot(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        rx_slots = [s for s in helper.pdoslots if s.isRXPDO()]
        assert len(rx_slots) >= 1
        slot = rx_slots[0]
        assert slot.ConfigurationIndex == 0x1400
        assert slot.MappingIndex == 0x1600

    def test_pdo_cob_with_nodeid(self):
        eds = self._make_eds_with_pdo()
        eds.dc.NodeID = 10
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        slot = tx_slots[0]
        # $NODEID(10) + 0x180 = 10 + 384 = 394 = 0x18A
        assert slot.COB == 0x18A
        assert slot.nodeidpresent is True

    def test_pdo_cob_without_nodeid(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        slot = tx_slots[0]
        assert slot.COB == 0x180
        assert slot.nodeidpresent is True  # $NODEID is in defaultvalue

    def test_pdo_transmission_type(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        assert tx_slots[0].transmissiontype == 254

    def test_pdo_inhibit(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        assert tx_slots[0].inhibit == 100

    def test_pdo_event_timer(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        assert tx_slots[0].eventtimer == 50

    def test_pdo_mapping_parsed(self):
        eds = self._make_eds_with_pdo()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        assert len(tx_slots[0].Mapping) >= 1
        entry = tx_slots[0].Mapping[0]
        assert entry.width == 32
        assert entry.entry is not None
        assert entry.entry.index == 0x1000

    def test_pdo_disabled_skipped(self):
        eds = self._make_eds_with_pdo()
        eds.ods[0x1800].prop.CO_disabled = True
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        tx_slots = [s for s in helper.pdoslots if s.isTXPDO()]
        assert len(tx_slots) == 0

    def test_empty_eds(self):
        eds = EDS()
        helper = PDOHelper(eds)
        helper.build_PDOlists()
        assert len(helper.pdoslots) == 0

    def test_gettargetname(self):
        helper = PDOHelper(EDS())
        od = ODentry(parameter_name="Test", index=0x1000, parent=None)
        od._index = 0x1000
        name = helper.pdoslots.__class__  # just check method exists on PDOSlot
        slot = PDOSlot()
        name = slot.getTargetName(od)
        assert "0x1000" in name

    def test_gettargetname_dummy(self):
        slot = PDOSlot()
        od = ODentry(index=0x002)
        name = slot.getTargetName(od)
        assert "Dummy Int8" in name


# ── ODentry 边界情况 ──────────────────────────────────────────────

class TestODentryEdgeCases:
    """ODentry 方法的边界测试"""

    def test_add_sub_entry_to_var(self):
        od = ODentry(objecttype=ObjectType.VAR)
        result = od.AddSubEntry()
        assert result is None

    def test_add_sub_entry_to_record(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        sub = od.AddSubEntry()
        assert sub is not None
        assert 0 in od.subobjects  # sub-index 0 自动创建
        assert 1 in od.subobjects

    def test_add_sub_entry_to_array(self):
        od = ODentry(objecttype=ObjectType.ARRAY)
        sub = od.AddSubEntry()
        assert sub is not None
        assert len(od.subobjects) >= 2

    def test_add_sub_entry_increments_count(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        od.AddSubEntry()
        count_before = len(od.subobjects)
        od.AddSubEntry()
        assert len(od.subobjects) > count_before

    def test_remove_sub_entry_from_record(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        od.AddSubEntry()
        od.AddSubEntry()
        count_before = len(od.subobjects)
        # 删除 sub 1
        sub1 = od.subobjects.get(1)
        assert sub1 is not None
        result = sub1.RemoveSubEntry()
        assert result is True
        assert len(od.subobjects) < count_before

    def test_remove_sub_entry_from_var(self):
        od = ODentry(objecttype=ObjectType.VAR)
        result = od.RemoveSubEntry()
        assert result is False

    def test_getmaxsubindex(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        od.subobjects[0] = ODentry(
            parameter_name="max sub-index",
            datatype=DataType.UNSIGNED8,
            defaultvalue="0x03",
            parent=od,
        )
        assert od.Getmaxsubindex() == 3

    def test_getmaxsubindex_no_sub0(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        assert od.Getmaxsubindex() == 0

    def test_getmaxsubindex_array(self):
        od = ODentry(objecttype=ObjectType.ARRAY)
        od.subobjects[0] = ODentry(
            parameter_name="sub-index 0",
            datatype=DataType.UNSIGNED8,
            defaultvalue="0x05",
            parent=od,
        )
        assert od.Getmaxsubindex() == 5

    def test_containssubindex(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        od.subobjects[1] = ODentry(parameter_name="sub1", parent=od)
        assert od.Containssubindex(1) is True
        assert od.Containssubindex(2) is False

    def test_getsubobject(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        sub = ODentry(parameter_name="sub1", parent=od)
        od.subobjects[1] = sub
        assert od.Getsubobject(1) is sub
        assert od.Getsubobject(99) is None

    def test_nosubindexes(self):
        od = ODentry(objecttype=ObjectType.RECORD)
        od.subobjects[0] = ODentry(parameter_name="sub0", parent=od)
        od.subobjects[1] = ODentry(parameter_name="sub1", parent=od)
        assert od.Nosubindexes == 2

    def test_subindex_from_parent(self):
        parent = ODentry(index=0x1000, objecttype=ObjectType.RECORD)
        sub = ODentry(parameter_name="sub", parent=parent)
        parent.subobjects[3] = sub
        assert sub.Subindex == 3

    def test_clone_deep(self):
        od = ODentry(
            parameter_name="Original", index=0x2000,
            objecttype=ObjectType.RECORD,
            datatype=DataType.UNSIGNED32,
        )
        sub = ODentry(
            parameter_name="sub1", datatype=DataType.UNSIGNED16,
            defaultvalue="0x100", parent=od,
        )
        od.subobjects[1] = sub

        cloned = od.clone()
        assert cloned.parameter_name == "Original"
        assert cloned.index == 0x2000
        assert len(cloned.subobjects) == 1
        # 修改 clone 不影响原对象
        cloned.parameter_name = "Modified"
        cloned.subobjects[1].parameter_name = "Modified sub"
        assert od.parameter_name == "Original"
        assert od.subobjects[1].parameter_name == "sub1"

    def test_sizeof_string_types(self):
        od_v = ODentry(datatype=DataType.VISIBLE_STRING, defaultvalue="hello")
        assert od_v.sizeof_datatype() == 5 * 8

        od_o = ODentry(datatype=DataType.OCTET_STRING, defaultvalue="01 02 03")
        assert od_o.sizeof_datatype() == 3 * 8

        od_u = ODentry(datatype=DataType.UNICODE_STRING, defaultvalue="0041 0042")
        assert od_u.sizeof_datatype() == 16  # 默认 16 bits

    def test_lengthof_string_visible(self):
        od = ODentry(datatype=DataType.VISIBLE_STRING, defaultvalue="hello")
        assert od.lengthof_string == 5

    def test_lengthof_string_octet(self):
        od = ODentry(datatype=DataType.OCTET_STRING, defaultvalue="01 02 03")
        assert od.lengthof_string == 3

    def test_lengthof_string_empty(self):
        od = ODentry(datatype=DataType.VISIBLE_STRING, defaultvalue="")
        assert od.lengthof_string == 0

    def test_lengthof_string_none(self):
        od = ODentry(datatype=DataType.VISIBLE_STRING)
        assert od.lengthof_string == 0

    def test_format_octet_string(self):
        od = ODentry(datatype=DataType.OCTET_STRING)
        result = od.format_octet_string("01 02 03")
        assert result == "010203"

    def test_format_octet_string_non_octet(self):
        od = ODentry(datatype=DataType.UNSIGNED32)
        result = od.format_octet_string("0x1234")
        assert result == "0x1234"

    def test_objecttype_string(self):
        od_var = ODentry(objecttype=ObjectType.VAR)
        assert od_var.objecttype_string() == "VAR"
        od_arr = ODentry(objecttype=ObjectType.ARRAY)
        assert od_arr.objecttype_string() == "ARRAY"
        od_rec = ODentry(objecttype=ObjectType.RECORD)
        assert od_rec.objecttype_string() == "RECORD"

    def test_parameter_cname(self):
        od = ODentry(parameter_name="Error register")
        assert od.parameter_cname() == "Errorregister"

    def test_parameter_cname_hyphen(self):
        od = ODentry(parameter_name="COB-ID")
        assert "COB" in od.parameter_cname()

    def test_parameter_cname_empty(self):
        od = ODentry(parameter_name="")
        assert od.parameter_cname() == ""

    def test_set_access_sdo_ro(self):
        od = ODentry()
        od.set_access_sdo(AccessSDO.RO, AccessPDO.NO)
        assert od.accesstype == AccessType.RO

    def test_set_access_sdo_wo(self):
        od = ODentry()
        od.set_access_sdo(AccessSDO.WO, AccessPDO.NO)
        assert od.accesstype == AccessType.WO

    def test_set_access_sdo_rw_rpdo(self):
        od = ODentry()
        od.set_access_sdo(AccessSDO.RW, AccessPDO.R)
        assert od.accesstype == AccessType.RWW

    def test_set_access_sdo_rw_tpdo(self):
        od = ODentry()
        od.set_access_sdo(AccessSDO.RW, AccessPDO.T)
        assert od.accesstype == AccessType.RWR

    def test_set_access_sdo_rw_no_pdo(self):
        od = ODentry()
        od.set_access_sdo(AccessSDO.RW, AccessPDO.NO)
        assert od.accesstype == AccessType.RW

    def test_set_access_pdo_r(self):
        od = ODentry()
        od.set_access_pdo(AccessPDO.R)
        assert od.PDOtype == PDOMappingType.RPDO

    def test_set_access_pdo_t(self):
        od = ODentry()
        od.set_access_pdo(AccessPDO.T)
        assert od.PDOtype == PDOMappingType.TPDO

    def test_set_access_pdo_tr(self):
        od = ODentry()
        od.set_access_pdo(AccessPDO.TR)
        assert od.PDOtype == PDOMappingType.OPTIONAL

    def test_set_access_pdo_no(self):
        od = ODentry()
        od.set_access_pdo(AccessPDO.NO)
        assert od.PDOtype == PDOMappingType.NO

    def test_access_sdo_const(self):
        od = ODentry(accesstype=AccessType.CONST)
        assert od.access_sdo() == AccessSDO.RO

    def test_access_sdo_unknown(self):
        od = ODentry(accesstype=AccessType.UNKNOWN)
        assert od.access_sdo() == AccessSDO.NO

    def test_access_pdo_optional(self):
        od = ODentry(pdo_type=PDOMappingType.OPTIONAL)
        assert od.access_pdo() == AccessPDO.TR

    def test_access_pdo_default(self):
        od = ODentry(pdo_type=PDOMappingType.DEFAULT)
        assert od.access_pdo() == AccessPDO.TR

    def test_index_setter(self):
        od = ODentry(index=0x1000)
        od.index = 0x2000
        assert od.index == 0x2000

    def test_index_setter_with_parent(self):
        parent = ODentry(index=0x1000)
        child = ODentry(parent=parent)
        child.index = 0x2000  # 不应该改变，因为有 parent
        assert child.index == 0x1000


# ── EDS 辅助方法 ──────────────────────────────────────────────

class TestEDSHelpers:
    """EDS 类辅助方法测试"""

    def test_getnodeid_empty(self):
        eds = EDS()
        result, present = eds.GetNodeID("")
        assert result == 0
        assert present is False

    def test_getnodeid_hex(self):
        eds = EDS()
        result, present = eds.GetNodeID("0x180")
        assert result == 0x180
        assert present is False

    def test_getnodeid_decimal(self):
        eds = EDS()
        result, present = eds.GetNodeID("384")
        assert result == 384
        assert present is False

    def test_getnodeid_with_nodeid(self):
        eds = EDS()
        eds.dc.NodeID = 10
        result, present = eds.GetNodeID("$NODEID+0x180")
        assert result == 10 + 0x180
        assert present is True

    def test_getnodeid_nodeid_zero(self):
        eds = EDS()
        eds.dc.NodeID = 0
        result, present = eds.GetNodeID("$NODEID+0x180")
        # 当 NodeID=0 时，$NODEID 被移除，只剩 +0x180
        assert present is True

    def test_getnodeid_single_value_with_nodeid(self):
        eds = EDS()
        eds.dc.NodeID = 5
        result, present = eds.GetNodeID("$NODEID+0x100")
        assert result == 5 + 0x100
        assert present is True

    def test_getnodeid_invalid(self):
        eds = EDS()
        result, present = eds.GetNodeID("invalid")
        assert result == 0
        assert present is False

    def test_updatepdo_count(self):
        eds = EDS()
        eds.ods[0x1400] = ODentry(
            parameter_name="RPDO", index=0x1400,
            objecttype=ObjectType.RECORD,
        )
        eds.ods[0x1800] = ODentry(
            parameter_name="TPDO", index=0x1800,
            objecttype=ObjectType.RECORD,
        )
        eds.ods[0x1801] = ODentry(
            parameter_name="TPDO 2", index=0x1801,
            objecttype=ObjectType.RECORD,
        )
        eds.UpdatePDOcount()
        assert eds.di.NrOfRXPDO == 1
        assert eds.di.NrOfTXPDO == 2

    def test_updatepdo_count_disabled(self):
        eds = EDS()
        eds.ods[0x1800] = ODentry(
            parameter_name="TPDO", index=0x1800,
            objecttype=ObjectType.RECORD,
        )
        eds.ods[0x1800].prop.CO_disabled = True
        eds.UpdatePDOcount()
        assert eds.di.NrOfTXPDO == 0

    def test_verifypdo_mapping_valid(self):
        eds = EDS()
        eds.ods[0x1000] = ODentry(
            parameter_name="Device type", index=0x1000,
            datatype=DataType.UNSIGNED32,
        )
        od_map = ODentry(
            parameter_name="mapping", index=0x1A00,
            objecttype=ObjectType.RECORD,
        )
        od_map.subobjects[0] = ODentry(
            defaultvalue="0x01", parent=od_map,
        )
        od_map.subobjects[1] = ODentry(
            defaultvalue="0x10000020", parent=od_map,
        )
        eds.ods[0x1A00] = od_map
        errors = eds.VerifyPDOMapping()
        assert len(errors) == 0

    def test_verifypdo_mapping_missing(self):
        eds = EDS()
        od_map = ODentry(
            parameter_name="mapping", index=0x1A00,
            objecttype=ObjectType.RECORD,
        )
        od_map.subobjects[0] = ODentry(
            defaultvalue="0x01", parent=od_map,
        )
        od_map.subobjects[1] = ODentry(
            defaultvalue="0x99990020", parent=od_map,  # 引用不存在的 0x9999
        )
        eds.ods[0x1A00] = od_map
        errors = eds.VerifyPDOMapping()
        assert len(errors) == 1
        assert "missing OD entry" in errors[0]

    def test_getdatatype_var(self):
        eds = EDS()
        od = ODentry(datatype=DataType.UNSIGNED32, objecttype=ObjectType.VAR)
        assert eds.Getdatatype(od) == DataType.UNSIGNED32

    def test_getdatatype_array(self):
        eds = EDS()
        od = ODentry(
            index=0x2000,
            objecttype=ObjectType.ARRAY, datatype=DataType.UNSIGNED16,
        )
        sub1 = ODentry(
            datatype=DataType.UNSIGNED32, parent=od,
        )
        od.subobjects[1] = sub1
        eds.ods[0x2000] = od
        assert eds.Getdatatype(od) == DataType.UNSIGNED32

    def test_getdatatype_record_unknown(self):
        eds = EDS()
        od = ODentry(objecttype=ObjectType.RECORD)
        eds.ods[0x2000] = od
        assert eds.Getdatatype(od) == DataType.UNKNOWN

    def test_getnoenabled_objects(self):
        eds = EDS()
        eds.ods[0x1000] = ODentry(index=0x1000)
        eds.ods[0x1001] = ODentry(index=0x1001)
        eds.ods[0x1001].prop.CO_disabled = True
        assert eds.GetNoEnabledObjects() == 1

    def test_getnoenabled_with_subs(self):
        eds = EDS()
        od = ODentry(index=0x1018, objecttype=ObjectType.RECORD)
        od.subobjects[0] = ODentry(defaultvalue="0x02", parent=od)
        od.subobjects[1] = ODentry(parent=od)
        od.subobjects[2] = ODentry(parent=od)
        eds.ods[0x1018] = od
        # 包含 sub
        count = eds.GetNoEnabledObjects(includesub=True)
        assert count >= 3  # 1 parent + 2 subs

    def test_getobject_in_range(self):
        eds = EDS()
        # dummy_ods 在 0x002-0x007
        assert eds.Getobject(0x002) is not None
        assert eds.Getobject(0x007) is not None

    def test_trygetode_in_range(self):
        eds = EDS()
        assert eds.tryGetODEntry(0x002) is not None
        assert eds.tryGetODEntry(0x005) is not None

    def test_exporters(self):
        eds = EDS()
        exporters = eds.GetExporters()
        descriptions = [e.description for e in exporters]
        assert "Electronic Data Sheet" in descriptions
        assert "Device Configuration File" in descriptions


# ── ExporterFactory 测试 ──────────────────────────────────────────

class TestExporterFactory:
    """ExporterFactory 查找和匹配测试"""

    def test_find_by_extension_h(self):
        exporters = Filetypes.find_by_extension(".h")
        assert len(exporters) >= 1
        descriptions = [e.description for e in exporters]
        assert "CanOpenNodeV4" in descriptions

    def test_find_by_extension_xdd(self):
        exporters = Filetypes.find_by_extension(".xdd")
        assert len(exporters) >= 1

    def test_find_by_extension_nxdd(self):
        exporters = Filetypes.find_by_extension(".nxdd")
        assert len(exporters) >= 1

    def test_find_by_extension_html(self):
        exporters = Filetypes.find_by_extension(".html")
        assert len(exporters) >= 2  # Documentation HTML + Network PDO Report

    def test_find_by_extension_unknown(self):
        exporters = Filetypes.find_by_extension(".xyz")
        assert len(exporters) == 0

    def test_find_by_description(self):
        result = Filetypes.find_by_description("CanOpenNodeV4")
        assert result is not None
        assert result.description == "CanOpenNodeV4"

    def test_find_by_description_with_spaces(self):
        result = Filetypes.find_by_description("CanOpenNodeV4")
        assert result is not None

    def test_find_by_description_not_found(self):
        result = Filetypes.find_by_description("NonExistent")
        assert result is None

    def test_get_exporters_all(self):
        exporters = Filetypes.get_exporters()
        assert len(exporters) >= 8

    def test_get_exporters_with_flags(self):
        exporters = Filetypes.get_exporters(flags=ExporterFlags.CanOpenNode)
        assert len(exporters) >= 1
        for e in exporters:
            assert e.flags & ExporterFlags.CanOpenNode

    def test_get_exporters_documentation(self):
        exporters = Filetypes.get_exporters(flags=ExporterFlags.Documentation)
        assert len(exporters) >= 2

    def test_multiple_exporters_same_extension(self):
        # .html 对应多个导出器
        exporters = Filetypes.find_by_extension(".html")
        assert len(exporters) >= 2
        descriptions = [e.description for e in exporters]
        assert "Documentation HTML" in descriptions
        assert "Network PDO Report" in descriptions


# ── XDD Handler 额外测试 ──────────────────────────────────────────

class TestXDDHandlerExtra:
    """XDD Handler 额外测试"""

    def test_write_xdd_with_device_commissioning(self, tmp_path):
        eds = EDS()
        eds.di.VendorName = "TestVendor"
        eds.di.ProductName = "TestProduct"
        eds.dc.NodeID = 5
        eds.dc.NodeName = "TestNode"
        eds.dc.Baudrate = 500000

        od = ODentry(
            parameter_name="Device type", index=0x1000,
            datatype=DataType.UNSIGNED32, defaultvalue="0x00000000",
            accesstype=AccessType.RO,
        )
        eds.ods[0x1000] = od

        handler = XDDHandler()
        output = str(tmp_path / "test.xdc")
        handler.write_xml(output, eds, device_commissioning=True)

        eds2 = handler.read_xml(output)
        assert eds2 is not None
        assert eds2.dc.NodeID == 5
        assert eds2.dc.NodeName == "TestNode"
        assert eds2.dc.Baudrate == 500000

    def test_write_xdd_stripped_removes_disabled(self, tmp_path):
        eds = EDS()
        eds.di.ProductName = "Test"
        od = ODentry(
            parameter_name="Enabled", index=0x1000,
            datatype=DataType.UNSIGNED32, defaultvalue="0",
            accesstype=AccessType.RO,
        )
        eds.ods[0x1000] = od
        od_disabled = ODentry(
            parameter_name="Disabled", index=0x2000,
            datatype=DataType.UNSIGNED32, defaultvalue="0",
            accesstype=AccessType.RO,
        )
        od_disabled.prop.CO_disabled = True
        eds.ods[0x2000] = od_disabled

        handler = XDDHandler()
        output = str(tmp_path / "stripped.xdd")
        handler.write_xml(output, eds, stripped=True)

        eds2 = handler.read_xml(output)
        assert 0x1000 in eds2.ods
        assert 0x2000 not in eds2.ods

    def test_read_xdd_v10_format(self, tmp_path):
        """测试 XDD v1.0 格式解析"""
        xdd_content = """<?xml version="1.0" encoding="UTF-8"?>
<OpenEDSProject version="1.0">
  <ISO15745Profile>
    <ProfileBody>
      <DeviceIdentity>
        <vendorName>TestVendor</vendorName>
        <productName>TestProduct</productName>
      </DeviceIdentity>
      <CANopen>
        <CANopenObjectList>
          <CANopenObject index="1000" name="Device type" objectType="7">
            <CANopenSubObject subIndex="0" name="Device type" objectType="7"
              dataType="UNSIGNED32" access="read" defaultValue="0x00000000"/>
          </CANopenObject>
        </CANopenObjectList>
      </CANopen>
    </ProfileBody>
  </ISO15745Profile>
</OpenEDSProject>"""
        xdd_file = str(tmp_path / "test_v10.xdd")
        with open(xdd_file, "w") as f:
            f.write(xdd_content)

        handler = XDDHandler()
        eds = handler.read_xml(xdd_file)
        assert eds is not None
        assert eds.di.VendorName == "TestVendor"
        assert eds.di.ProductName == "TestProduct"

    def test_write_network_xdd(self, tmp_path):
        eds = EDS()
        eds.di.ProductName = "Device1"
        od = ODentry(
            parameter_name="Device type", index=0x1000,
            datatype=DataType.UNSIGNED32, defaultvalue="0",
            accesstype=AccessType.RO,
        )
        eds.ods[0x1000] = od

        handler = XDDHandler()
        output = str(tmp_path / "network.nxdd")
        handler.write_multi_xml(output, [eds, eds])

        devices = handler.read_multi_xml(output)
        assert len(devices) == 2
        assert devices[0].di.ProductName == "Device1"

    def test_network_xdd_preserves_nodeid(self, tmp_path):
        eds = EDS()
        eds.di.ProductName = "Device1"
        eds.dc.NodeID = 42
        eds.dc.NodeName = "Node42"
        eds.dc.Baudrate = 250000

        handler = XDDHandler()
        output = str(tmp_path / "network.nxdc")
        handler.write_multi_xml(output, [eds], device_commissioning=True)

        devices = handler.read_multi_xml(output)
        assert len(devices) == 1
        assert devices[0].dc.NodeID == 42
        assert devices[0].dc.NodeName == "Node42"


# ── NetworkPDOreport 测试 ──────────────────────────────────────────

class TestNetworkPDOreport:
    """Network PDO 报告导出器测试"""

    def test_export_produces_file(self, tmp_path):
        from src.core.exporters.network_pdo_report import NetworkPDOreport

        eds = EDS()
        eds.di.ProductName = "TestDevice"
        eds.dc.NodeID = 1

        od_1800 = ODentry(
            parameter_name="TPDO communication parameter",
            index=0x1800, objecttype=ObjectType.RECORD,
        )
        od_1800.subobjects[0] = ODentry(defaultvalue="0x05", parent=od_1800)
        od_1800.subobjects[1] = ODentry(
            defaultvalue="$NODEID+0x180", parent=od_1800,
        )
        od_1800.subobjects[2] = ODentry(defaultvalue="254", parent=od_1800)
        od_1800.subobjects[3] = ODentry(defaultvalue="0", parent=od_1800)
        od_1800.subobjects[5] = ODentry(defaultvalue="0", parent=od_1800)
        od_1800.subobjects[6] = ODentry(defaultvalue="0", parent=od_1800)
        eds.ods[0x1800] = od_1800

        od_1a00 = ODentry(
            parameter_name="TPDO mapping",
            index=0x1A00, objecttype=ObjectType.RECORD,
        )
        od_1a00.subobjects[0] = ODentry(defaultvalue="0x01", parent=od_1a00)
        od_1a00.subobjects[1] = ODentry(
            defaultvalue="0x10000020", parent=od_1a00,
        )
        eds.ods[0x1A00] = od_1a00

        eds.ods[0x1000] = ODentry(
            parameter_name="Device type", index=0x1000,
            datatype=DataType.UNSIGNED32, defaultvalue="0",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.TPDO,
        )

        exporter = NetworkPDOreport()
        output = str(tmp_path / "pdo_report.html")
        exporter._gen_net_pdo_doc(output, [eds])
        assert os.path.exists(output)

        with open(output) as f:
            content = f.read()
        assert "PDO Network Documentation" in content
        assert "TestDevice" in content

    def test_registered(self):
        exporters = Filetypes.find_by_extension(".html")
        descriptions = [e.description for e in exporters]
        assert "Network PDO Report" in descriptions


# ── 辅助函数测试 ──────────────────────────────────────────────

class TestHelperFunctions:
    """辅助函数测试"""

    def test_get_base_hex(self):
        assert _get_base("0x10") == 16
        assert _get_base("0X1F") == 16

    def test_get_base_octal(self):
        assert _get_base("010") == 8

    def test_get_base_decimal(self):
        assert _get_base("10") == 10

    def test_get_base_empty(self):
        assert _get_base("") == 10

    def test_get_base_none_like(self):
        assert _get_base("  ") == 10

    def test_convert_to_uint16(self):
        assert _convert_to_uint16("0x100") == 256
        assert _convert_to_uint16("256") == 256

    def test_convert_to_uint16_empty(self):
        assert _convert_to_uint16("") == 0


# ── EDS Save/Load 一致性 ──────────────────────────────────────────

class TestEDSSaveLoadConsistency:
    """EDS 保存/加载一致性测试"""

    def test_save_dcf_preserves_actual_value(self, tmp_path):
        eds = EDS()
        od = ODentry(
            parameter_name="Test", index=0x2000,
            datatype=DataType.UNSIGNED32, defaultvalue="0x12345678",
            accesstype=AccessType.RW,
        )
        od.actualvalue = "0xAABBCCDD"
        eds.ods[0x2000] = od

        output = str(tmp_path / "test.dcf")
        eds.Savefile(output, Filetype.FILE_DCF)

        eds2 = EDS()
        EDSParser(eds2).loadfile(output)
        assert eds2.ods[0x2000].actualvalue == "0xAABBCCDD"

    def test_save_eds_no_actual_value(self, tmp_path):
        eds = EDS()
        od = ODentry(
            parameter_name="Test", index=0x2000,
            datatype=DataType.UNSIGNED32, defaultvalue="0x12345678",
            accesstype=AccessType.RW,
        )
        od.actualvalue = "0xAABBCCDD"
        eds.ods[0x2000] = od

        output = str(tmp_path / "test.eds")
        eds.Savefile(output, Filetype.FILE_EDS)

        eds2 = EDS()
        EDSParser(eds2).loadfile(output)
        # EDS 不保存 actualvalue
        assert eds2.ods[0x2000].actualvalue == ""

    def test_save_preserves_disabled(self, tmp_path):
        eds = EDS()
        od = ODentry(
            parameter_name="DisabledObj", index=0x2000,
            datatype=DataType.UNSIGNED32, defaultvalue="0",
            accesstype=AccessType.RO,
        )
        od.prop.CO_disabled = True
        eds.ods[0x2000] = od

        output = str(tmp_path / "test.eds")
        eds.Savefile(output, Filetype.FILE_EDS)

        eds2 = EDS()
        EDSParser(eds2).loadfile(output)
        # EDS 不保存 disabled 对象
        assert 0x2000 not in eds2.ods

    def test_xdd_save_preserves_disabled(self, tmp_path):
        eds = EDS()
        od = ODentry(
            parameter_name="DisabledObj", index=0x2000,
            datatype=DataType.UNSIGNED32, defaultvalue="0",
            accesstype=AccessType.RO,
        )
        od.prop.CO_disabled = True
        eds.ods[0x2000] = od

        handler = XDDHandler()
        output = str(tmp_path / "test.xdd")
        handler.write_xml(output, eds)

        eds2 = handler.read_xml(output)
        assert 0x2000 in eds2.ods
        assert eds2.ods[0x2000].prop.CO_disabled is True


# ── PDOMappingEntry 测试 ──────────────────────────────────────────

class TestPDOMappingEntry:
    def test_entry_with_od(self):
        od = ODentry(datatype=DataType.UNSIGNED32)
        entry = PDOMappingEntry(entry=od)
        assert entry.width == 32

    def test_entry_explicit_width(self):
        entry = PDOMappingEntry(width=16)
        assert entry.width == 16

    def test_entry_with_od_explicit_width(self):
        od = ODentry(datatype=DataType.UNSIGNED32)
        entry = PDOMappingEntry(entry=od, width=64)
        assert entry.width == 64


# ── PDOSlot 边界测试 ──────────────────────────────────────────

class TestPDOSlotEdgeCases:
    def test_invalid_bit_set_clear(self):
        slot = PDOSlot()
        slot.invalid = True
        assert slot.invalid is True
        assert slot.COB & 0x80000000 != 0
        slot.invalid = False
        assert slot.invalid is False
        assert slot.COB & 0x80000000 == 0

    def test_configuration_index_invalid(self):
        slot = PDOSlot()
        with pytest.raises(ValueError):
            slot.ConfigurationIndex = 0x1000  # 不在 PDO 范围

    def test_configuration_index_zero(self):
        slot = PDOSlot()
        slot.ConfigurationIndex = 0x1800
        slot.ConfigurationIndex = 0
        assert slot.ConfigurationIndex == 0
        assert slot.MappingIndex == 0

    def test_insert_mapping_overflow_rejected(self):
        slot = PDOSlot()
        # 插入 32+32+32 = 96 bits，超过 64 位限制
        slot.insertMapping(0, PDOMappingEntry(width=32))
        slot.insertMapping(1, PDOMappingEntry(width=32))
        slot.insertMapping(2, PDOMappingEntry(width=32))
        assert len(slot.Mapping) == 2  # 第三个被拒绝

    def test_is_txpdo(self):
        slot = PDOSlot()
        slot.ConfigurationIndex = 0x1800
        assert slot.isTXPDO() is True
        assert slot.isRXPDO() is False

    def test_is_rxpdo(self):
        slot = PDOSlot()
        slot.ConfigurationIndex = 0x1400
        assert slot.isRXPDO() is True
        assert slot.isTXPDO() is False

    def test_mapping_index_calculation(self):
        slot = PDOSlot()
        slot.ConfigurationIndex = 0x1800
        assert slot.MappingIndex == 0x1A00
        slot.ConfigurationIndex = 0x1400
        assert slot.MappingIndex == 0x1600
        slot.ConfigurationIndex = 0x19FF
        assert slot.MappingIndex == 0x1BFF
