"""PDO 辅助类，对应 C# PDOHelper"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from .datatypes import AccessPDO, AccessType, ObjectType, PDOMappingType

if TYPE_CHECKING:
    from .eds import EDS
    from .od_entry import ODentry


@dataclass
class PDOMappingEntry:
    entry: Optional[ODentry] = None
    width: int = 0

    def __post_init__(self):
        if self.entry is not None and self.width == 0:
            self.width = self.entry.sizeof_datatype()


class PDOSlot:
    """PDO 槽位，对应 C# PDOSlot"""

    def __init__(self):
        self._configuration_index: int = 0
        self._mapping_index: int = 0
        self.nodeidpresent: bool = False
        self.mappingAccessType: AccessType = AccessType.UNKNOWN
        self.configAccessType: AccessType = AccessType.UNKNOWN
        self.mappingloc: str = "PERSIST_COMM"
        self.configloc: str = "PERSIST_COMM"
        self.COB: int = 0
        self.Mapping: list[PDOMappingEntry] = []
        self.inhibit: int = 0
        self.eventtimer: int = 0
        self.syncstart: int = 0
        self.transmissiontype: int = 254
        self.DescriptionComm: str = ""
        self.DescriptionMap: str = ""

    @property
    def ConfigurationIndex(self) -> int:
        return self._configuration_index

    @ConfigurationIndex.setter
    def ConfigurationIndex(self, value: int) -> None:
        if value == 0:
            self._configuration_index = 0
            self._mapping_index = 0
            return
        if (0x1400 <= value < 0x1600) or (0x1800 <= value < 0x1A00):
            self._configuration_index = value
            self._mapping_index = value + 0x200
        else:
            raise ValueError(f"Configuration Index must be between 0x1400 and 0x19FF, got 0x{value:04X}")

    @property
    def MappingIndex(self) -> int:
        return self._mapping_index

    @property
    def invalid(self) -> bool:
        return (self.COB & 0x80000000) != 0

    @invalid.setter
    def invalid(self, value: bool) -> None:
        if value:
            self.COB |= 0x80000000
        else:
            self.COB &= 0x7FFFFFFF

    def isTXPDO(self) -> bool:
        return self._configuration_index >= 0x1800

    def isRXPDO(self) -> bool:
        return self._configuration_index < 0x1800

    def insertMapping(self, ordinal: int, entry: PDOMappingEntry) -> None:
        total_size = sum(e.width for e in self.Mapping)
        if total_size + entry.width > 64:
            return
        self.Mapping.insert(ordinal, entry)

    def getTargetName(self, od: ODentry) -> str:
        if 0x002 <= od.index <= 0x007:
            dummy_names = {
                0x002: "0x0002/00/Dummy Int8",
                0x003: "0x0003/00/Dummy Int16",
                0x004: "0x0004/00/Dummy Int32",
                0x005: "0x0005/00/Dummy UInt8",
                0x006: "0x0006/00/Dummy UInt16",
                0x007: "0x0007/00/Dummy UInt32",
            }
            return dummy_names.get(od.index, "")
        return f"0x{od.index:04X}/{od.Subindex:02X}/{od.parameter_name}"


class PDOHelper:
    """PDO 辅助类，对应 C# PDOHelper"""

    def __init__(self, eds: EDS):
        self.eds = eds
        self.pdoslots: list[PDOSlot] = []

    def build_PDOlists(self) -> None:
        self.pdoslots.clear()
        self._build_PDOlist(0x1800)
        self._build_PDOlist(0x1400)

    def _build_PDOlist(self, start_idx: int) -> None:
        for idx in range(start_idx, start_idx + 0x01FF):
            od = self.eds.ods.get(idx)
            if od is None:
                continue
            if od.prop.CO_disabled:
                continue

            slot = PDOSlot()
            slot.ConfigurationIndex = idx

            if od.Getsubobject(1) is not None:
                cob_str = od.Getsubobject(1).defaultvalue
                if cob_str:
                    cob_val, nodeid_present = self.eds.GetNodeID(cob_str)
                    slot.COB = cob_val
                    slot.nodeidpresent = nodeid_present

            if od.Getsubobject(2) is not None:
                try:
                    slot.transmissiontype = int(od.Getsubobject(2).defaultvalue, 0)
                except (ValueError, TypeError):
                    pass

            if od.Getsubobject(3) is not None:
                try:
                    slot.inhibit = int(od.Getsubobject(3).defaultvalue, 0)
                except (ValueError, TypeError):
                    pass

            if od.Getsubobject(5) is not None:
                try:
                    slot.eventtimer = int(od.Getsubobject(5).defaultvalue, 0)
                except (ValueError, TypeError):
                    pass

            mapping_od = self.eds.ods.get(slot.MappingIndex)
            if mapping_od is not None:
                for sub_idx in range(1, len(mapping_od.subobjects)):
                    sub = mapping_od.subobjects.get(sub_idx)
                    if sub is None:
                        continue
                    try:
                        map_val = int(sub.defaultvalue, 0)
                        map_idx = (map_val >> 16) & 0xFFFF
                        map_sub = (map_val >> 8) & 0xFF
                        map_width = map_val & 0xFF

                        mapped_od = self.eds.Getobject(map_idx)
                        if mapped_od is not None and map_sub > 0:
                            mapped_od = mapped_od.Getsubobject(map_sub) or mapped_od

                        slot.Mapping.append(PDOMappingEntry(entry=mapped_od, width=map_width))
                    except (ValueError, TypeError):
                        slot.Mapping.append(PDOMappingEntry(width=0))

            self.pdoslots.append(slot)