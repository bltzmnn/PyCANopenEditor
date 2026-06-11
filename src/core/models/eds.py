"""CANopen 设备描述顶层类"""
from __future__ import annotations

from typing import Callable, Optional

from .datatypes import AccessType, DataType, ObjectType, PDOMappingType
from .info_section import (
    Comments,
    ConnectedModules,
    DeviceCommissioning,
    DeviceInfo,
    DummyUsage,
    FileInfo,
    Filetype,
    MandatoryObjects,
    ManufacturerObjects,
    Module,
    OptionalObjects,
    SupportedModules,
    TypeDefinitions,
)
from .od_entry import ODentry, _convert_to_uint16, _get_base


class COStorageGroups(list):
    def __init__(self):
        super().__init__()
        self.append("RAM")

    def append(self, item: str) -> None:
        if item not in self:
            super().append(item)


class EDS:
    """CANopen 设备描述顶层类"""

    def __init__(self):
        self.projectFilename: str = ""
        self.xddfilename_1_1: str = ""
        self.xddfilenameStripped: str = ""
        self.edsfilename: str = ""
        self.dcffilename: str = ""
        self.ODfilename: str = ""
        self.ODfileVersion: str = ""
        self.mdfilename: str = ""
        self.xmlfilename: str = ""
        self.xddfilename_1_0: str = ""

        self._dirty: bool = False
        self.eds: dict[str, dict[str, str]] = {}
        self.sectionlinenos: dict[str, int] = {}
        self.ods: dict[int, ODentry] = {}
        self.dummy_ods: dict[int, ODentry] = {}
        self.CO_storageGroups = COStorageGroups()

        self.fi = FileInfo()
        self.di = DeviceInfo()
        self.du = DummyUsage()
        self.md = MandatoryObjects()
        self.oo = OptionalObjects()
        self.mo = ManufacturerObjects()
        self.dc = DeviceCommissioning()
        self.c = Comments()
        self.sm = SupportedModules()
        self.cm = ConnectedModules()
        self.td = TypeDefinitions()
        self.modules: dict[int, Module] = {}

        self.fi.EDSVersionMajor = 4
        self.fi.EDSVersionMinor = 0
        self.fi.FileVersion = "1"
        self.fi.FileRevision = 1

        self._init_dummy_ods()

        self.sectionname: str = ""
        self.NodeID: int = 0
        self._on_data_dirty: Optional[Callable] = None

    def _init_dummy_ods(self) -> None:
        self.dummy_ods[0x002] = ODentry(
            parameter_name="Dummy Int8", index=0x002,
            datatype=DataType.INTEGER8, defaultvalue="0",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.OPTIONAL,
        )
        self.dummy_ods[0x003] = ODentry(
            parameter_name="Dummy Int16", index=0x003,
            datatype=DataType.INTEGER16, defaultvalue="0",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.OPTIONAL,
        )
        self.dummy_ods[0x004] = ODentry(
            parameter_name="Dummy Int32", index=0x004,
            datatype=DataType.INTEGER32, defaultvalue="0",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.OPTIONAL,
        )
        self.dummy_ods[0x005] = ODentry(
            parameter_name="Dummy UInt8", index=0x005,
            datatype=DataType.UNSIGNED8, defaultvalue="0",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.OPTIONAL,
        )
        self.dummy_ods[0x006] = ODentry(
            parameter_name="Dummy UInt16", index=0x006,
            datatype=DataType.UNSIGNED16, defaultvalue="0",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.OPTIONAL,
        )
        self.dummy_ods[0x007] = ODentry(
            parameter_name="Dummy UInt32", index=0x007,
            datatype=DataType.UNSIGNED32, defaultvalue="0",
            accesstype=AccessType.RO, pdo_type=PDOMappingType.OPTIONAL,
        )

    @property
    def Dirty(self) -> bool:
        return self._dirty

    @Dirty.setter
    def Dirty(self, value: bool) -> None:
        self._dirty = value
        if self._on_data_dirty:
            self._on_data_dirty(value, self)

    def Getobject(self, no: int) -> Optional[ODentry]:
        if 0x002 <= no <= 0x007:
            return self.dummy_ods.get(no)
        return self.ods.get(no)

    def tryGetODEntry(self, index: int) -> Optional[ODentry]:
        if index in self.ods:
            return self.ods[index]
        if index in self.dummy_ods:
            return self.dummy_ods[index]
        return None

    def GetNoEnabledObjects(self, includesub: bool = False) -> int:
        count = 0
        for od in self.ods.values():
            if not od.prop.CO_disabled:
                count += 1
                if includesub:
                    for sub in od.subobjects.values():
                        if not sub.prop.CO_disabled:
                            count += 1
        return count

    def UpdatePDOcount(self) -> None:
        self.di.NrOfRXPDO = 0
        self.di.NrOfTXPDO = 0
        for idx, od in self.ods.items():
            if not od.prop.CO_disabled:
                if 0x1400 <= idx < 0x1600:
                    self.di.NrOfRXPDO += 1
                elif 0x1800 <= idx < 0x1A00:
                    self.di.NrOfTXPDO += 1

    def GetNodeID(self, input_str: str) -> tuple[int, bool]:
        if not input_str:
            return 0, False

        input_str = input_str.upper()
        nodeid_present = "$NODEID" in input_str

        try:
            if self.dc.NodeID == 0:
                input_str = input_str.replace("$NODEID", "").replace("+", "").replace(" ", "")
                return int(input_str.strip(), _get_base(input_str)), nodeid_present

            input_str = input_str.replace("$NODEID", str(self.dc.NodeID))
            bits = [b.strip() for b in input_str.split("+")]
            if len(bits) == 1:
                return int(bits[0], _get_base(bits[0])), nodeid_present
            if len(bits) == 2:
                return int(bits[0], _get_base(bits[0])) + int(bits[1], _get_base(bits[1])), nodeid_present
        except Exception:
            pass

        return 0, nodeid_present

    def Getdatatype(self, od: ODentry) -> DataType:
        if od.objecttype == ObjectType.VAR:
            return od.datatype
        if od.objecttype == ObjectType.ARRAY:
            sub2 = self.ods.get(od.index)
            if sub2:
                t = sub2.datatype
                if sub2.Getsubobject(1) is not None:
                    t = sub2.Getsubobject(1).datatype
                    if t == DataType.UNKNOWN:
                        t = sub2.datatype
                return t
        return DataType.UNKNOWN

    def VerifyPDOMapping(self) -> list[str]:
        mapping_errors: list[str] = []
        for index_pdo, od_pdo in self.ods.items():
            if not ((0x1600 <= index_pdo < 0x1800) or (0x1A00 <= index_pdo < 0x1C00)):
                continue
            pdo = "RPDO" if index_pdo < 0x1800 else "TPDO"
            for sub_idx in range(1, len(od_pdo.subobjects)):
                sub_od = od_pdo.subobjects.get(sub_idx)
                if not sub_od:
                    continue
                try:
                    map_val = int(sub_od.defaultvalue, 0)
                except (ValueError, TypeError):
                    continue
                map_idx = (map_val >> 16) & 0xFFFF
                map_sub = (map_val >> 8) & 0xFF
                if map_idx < 0x1000:
                    continue
                if map_idx not in self.ods:
                    mapping_errors.append(f"{pdo} 0x{index_pdo:04X},0x{sub_idx:02X}: missing OD entry 0x{map_idx:04X},0x{map_sub:02X}")
        return mapping_errors

    def Loadfile(self, filename: str) -> None:
        from ..parsers.eds_parser import EDSParser
        parser = EDSParser(self)
        parser.loadfile(filename)

    def Savefile(self, filename: str, ft: Filetype = Filetype.FILE_EDS) -> None:
        from ..parsers.eds_parser import EDSWriter
        writer = EDSWriter(self)
        writer.savefile(filename, ft)

    def GetExporters(self) -> list:
        from ..exporters.exporter_factory import ExporterDescriptor
        return [
            ExporterDescriptor(
                "Electronic Data Sheet", [".eds"], 0,
                lambda filepath, eds_list: eds_list[0].Savefile(filepath, Filetype.FILE_EDS),
            ),
            ExporterDescriptor(
                "Device Configuration File", [".dcf"], 0,
                lambda filepath, eds_list: eds_list[0].Savefile(filepath, Filetype.FILE_DCF),
            ),
        ]