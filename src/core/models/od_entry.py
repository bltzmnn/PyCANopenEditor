"""CANopen 对象字典条目模型"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Optional

from .datatypes import (
    AccessPDO,
    AccessSDO,
    AccessSRDO,
    AccessType,
    DataType,
    DATA_TYPE_SIZE_BITS,
    ObjectType,
    PDOMappingType,
)


@dataclass
class CustomProperties:
    CO_disabled: bool = False
    CO_countLabel: str = ""
    CO_storageGroup: str = "RAM"
    CO_flagsPDO: bool = False
    CO_accessSRDO: AccessSRDO = AccessSRDO.NO
    CO_stringLengthMin: int = 0

    def clone(self) -> CustomProperties:
        return CustomProperties(
            CO_disabled=self.CO_disabled,
            CO_countLabel=self.CO_countLabel,
            CO_storageGroup=self.CO_storageGroup,
            CO_flagsPDO=self.CO_flagsPDO,
            CO_accessSRDO=self.CO_accessSRDO,
            CO_stringLengthMin=self.CO_stringLengthMin,
        )


class ODentry:
    """对象字典条目，对应 C# 的 ODentry"""

    def __init__(
        self,
        parameter_name: str = "",
        index: int = 0,
        datatype: DataType = DataType.UNKNOWN,
        defaultvalue: str = "",
        accesstype: AccessType = AccessType.UNKNOWN,
        pdo_type: PDOMappingType = PDOMappingType.NO,
        parent: Optional[ODentry] = None,
        objecttype: ObjectType = ObjectType.UNKNOWN,
    ):
        self._index: int = index
        self.parameter_name: str = parameter_name
        self.denotation: str = ""
        self.objecttype: ObjectType = objecttype if objecttype != ObjectType.UNKNOWN else ObjectType.VAR
        self.datatype: DataType = datatype
        self.accesstype: AccessType = accesstype
        self.defaultvalue: str = defaultvalue
        self.LowLimit: str = ""
        self.HighLimit: str = ""
        self.actualvalue: str = ""
        self.ObjFlags: int = 0
        self.CompactSubObj: int = 0
        self.count: int = 0
        self.ObjExtend: int = 0
        self.PDOtype: PDOMappingType = pdo_type
        self.Label: str = ""
        self.Description: str = ""
        self.subobjects: dict[int, ODentry] = {}
        self.parent: Optional[ODentry] = parent
        self.prop: CustomProperties = CustomProperties()
        self.uniqueID: str = ""
        self.Odtype: str = "NORMAL"

    @property
    def index(self) -> int:
        if self.parent is not None:
            return self.parent.index
        return self._index

    @index.setter
    def index(self, value: int) -> None:
        if self.parent is None:
            self._index = value

    @property
    def PDOMapping(self) -> bool:
        return self.PDOtype != PDOMappingType.NO

    @property
    def Nosubindexes(self) -> int:
        return len(self.subobjects)

    @property
    def Subindex(self) -> int:
        if self.parent is not None:
            for k, v in self.parent.subobjects.items():
                if v is self:
                    return k
        return 0

    def access_sdo(self) -> AccessSDO:
        acc_type = self.accesstype
        if acc_type == AccessType.UNKNOWN and self.parent is not None and self.parent.objecttype == ObjectType.ARRAY:
            acc_type = self.parent.accesstype
        if acc_type in (AccessType.RO, AccessType.CONST):
            return AccessSDO.RO
        elif acc_type == AccessType.WO:
            return AccessSDO.WO
        elif acc_type in (AccessType.RW, AccessType.RWR, AccessType.RWW):
            return AccessSDO.RW
        return AccessSDO.NO

    def set_access_sdo(self, access_sdo: AccessSDO, access_pdo: AccessPDO) -> None:
        if access_sdo == AccessSDO.RO:
            self.accesstype = AccessType.RO
        elif access_sdo == AccessSDO.WO:
            self.accesstype = AccessType.WO
        elif access_sdo == AccessSDO.RW:
            if access_pdo == AccessPDO.R:
                self.accesstype = AccessType.RWW
            elif access_pdo == AccessPDO.T:
                self.accesstype = AccessType.RWR
            else:
                self.accesstype = AccessType.RW
        else:
            self.accesstype = AccessType.UNKNOWN

    def access_pdo(self) -> AccessPDO:
        acc_type = self.accesstype
        if acc_type == AccessType.UNKNOWN and self.parent is not None and self.parent.objecttype == ObjectType.ARRAY:
            acc_type = self.parent.accesstype
        if self.PDOtype == PDOMappingType.RPDO or acc_type == AccessType.RWW:
            return AccessPDO.R
        elif self.PDOtype == PDOMappingType.TPDO or acc_type == AccessType.RWR:
            return AccessPDO.T
        elif self.PDOtype in (PDOMappingType.OPTIONAL, PDOMappingType.DEFAULT):
            return AccessPDO.TR
        return AccessPDO.NO

    def set_access_pdo(self, access_pdo: AccessPDO) -> None:
        if access_pdo == AccessPDO.R:
            self.PDOtype = PDOMappingType.RPDO
        elif access_pdo == AccessPDO.T:
            self.PDOtype = PDOMappingType.TPDO
        elif access_pdo == AccessPDO.TR:
            self.PDOtype = PDOMappingType.OPTIONAL
        else:
            self.PDOtype = PDOMappingType.NO

    def sizeof_datatype(self) -> int:
        dt = self.datatype
        if dt == DataType.UNKNOWN and self.parent is not None:
            dt = self.parent.datatype
        if dt in (DataType.VISIBLE_STRING, DataType.OCTET_STRING):
            return self.lengthof_string * 8
        if dt == DataType.UNICODE_STRING:
            return 16
        return DATA_TYPE_SIZE_BITS.get(dt, 0)

    @property
    def lengthof_string(self) -> int:
        val = self.defaultvalue
        if not val:
            return 0
        if self.datatype == DataType.VISIBLE_STRING:
            return len(_unescape_visible_string(val))
        elif self.datatype == DataType.OCTET_STRING:
            return len(re.sub(r"\s", "", val)) // 2
        elif self.datatype == DataType.UNICODE_STRING:
            return len(re.sub(r"\s", "", val)) // 4
        return 0

    def objecttype_string(self) -> str:
        if self.objecttype in ObjectType:
            return self.objecttype.name
        return ObjectType.VAR.name

    def format_octet_string(self, value: str) -> str:
        dt = self.datatype
        if dt == DataType.UNKNOWN and self.parent is not None:
            dt = self.parent.datatype
        if dt == DataType.OCTET_STRING:
            return value.replace(" ", "")
        return value

    def parameter_cname(self) -> str:
        cname = self.parameter_name.replace("-", "_")
        cname = re.sub(r"([A-Z]) ([A-Z])", r"\1_\2", cname)
        cname = cname.replace(" ", "")
        return cname

    def clone(self, new_parent: Optional[ODentry] = None) -> ODentry:
        new_od = ODentry()
        new_od.parent = new_parent
        new_od._index = self._index
        new_od.parameter_name = self.parameter_name
        new_od.denotation = self.denotation
        new_od.objecttype = self.objecttype
        new_od.datatype = self.datatype
        new_od.accesstype = self.accesstype
        new_od.PDOtype = self.PDOtype
        new_od.defaultvalue = self.defaultvalue
        new_od.LowLimit = self.LowLimit
        new_od.HighLimit = self.HighLimit
        new_od.actualvalue = self.actualvalue
        new_od.Label = self.Label
        new_od.Description = self.Description
        new_od.prop = self.prop.clone()
        new_od.subobjects = {}
        for k, v in self.subobjects.items():
            new_od.subobjects[k] = v.clone(new_od)
        return new_od

    def addsubobject(self, subindex: int, sub: ODentry) -> None:
        sub.parent = self
        self.subobjects[subindex] = sub

    def Getsubobject(self, no: int) -> Optional[ODentry]:
        return self.subobjects.get(no)

    def Containssubindex(self, no: int) -> bool:
        return no in self.subobjects

    def Getmaxsubindex(self) -> int:
        if self.objecttype in (ObjectType.ARRAY, ObjectType.RECORD):
            if self.Containssubindex(0):
                val = self.subobjects[0].defaultvalue
                return _convert_to_byte(val)
        return 0

    def AddSubEntry(self) -> Optional[ODentry]:
        base_object = self.parent if self.parent else self

        if base_object.objecttype == ObjectType.VAR:
            return None

        if not base_object.subobjects and base_object.objecttype in (ObjectType.ARRAY, ObjectType.RECORD):
            base_object.subobjects[0] = ODentry(
                parameter_name="Highest sub-index supported",
                accesstype=AccessType.RO,
                objecttype=ObjectType.VAR,
                datatype=DataType.UNSIGNED8,
                defaultvalue="0x01",
                parent=base_object,
            )

        last_sub_od = list(base_object.subobjects.values())[-1] if base_object.subobjects else None
        original_od = None
        max_sub_index = 1
        last_sub_index = 1

        if last_sub_od is None or last_sub_od.Subindex < 1:
            new_od = ODentry(
                parameter_name="item",
                objecttype=ObjectType.VAR,
                datatype=DataType.UNSIGNED32,
                parent=base_object,
            )
        else:
            original_od = (self.parent and self.Subindex > 0) and self or last_sub_od
            new_od = original_od.clone(original_od.parent)
            max_sub_index = _convert_to_uint16(base_object.subobjects[0].defaultvalue) if 0 in base_object.subobjects else 1
            last_sub_index = last_sub_od.Subindex

        new_sub_objects: dict[int, ODentry] = {}
        new_sub_index = 0
        for sub_od in base_object.subobjects.values():
            if sub_od.Subindex > new_sub_index:
                new_sub_index = sub_od.Subindex
            new_sub_objects[new_sub_index] = sub_od
            new_sub_index += 1
            if last_sub_od is sub_od:
                new_sub_objects[new_sub_index] = new_od
                prev_name = new_sub_objects[new_sub_index - 1].parameter_name
                new_od.parameter_name = _increment_number_at_end(prev_name, 1)

        if original_od is None:
            new_sub_objects[new_sub_index] = new_od
            new_sub_index += 1

        base_object.subobjects = new_sub_objects

        if max_sub_index > 0 and max_sub_index == last_sub_index and base_object.subobjects:
            base_object.subobjects[0].defaultvalue = f"0x{new_sub_index - 1:02X}"

        return new_od

    def RemoveSubEntry(self, renumber: bool = True) -> bool:
        if self.parent is not None and self.parent.objecttype in (ObjectType.ARRAY, ObjectType.RECORD):
            max_sub_index = _convert_to_uint16(self.parent.subobjects[0].defaultvalue) if 0 in self.parent.subobjects else 0
            last_sub_index = list(self.parent.subobjects.values())[-1].Subindex if self.parent.subobjects else 0

            del self.parent.subobjects[self.Subindex]

            if renumber:
                new_sub_objects: dict[int, ODentry] = {}
                sub_index = 0
                for sub_od in self.parent.subobjects.values():
                    new_sub_objects[sub_index] = sub_od
                    sub_index += 1
                self.parent.subobjects = new_sub_objects

            if max_sub_index > 0 and max_sub_index == last_sub_index and self.parent.subobjects:
                self.parent.subobjects[0].defaultvalue = f"0x{list(self.parent.subobjects.values())[-1].Subindex:02X}"

            return True
        return False

    def __repr__(self) -> str:
        if self.subobjects:
            return f"{self.index:04X}[{len(self.subobjects)}] : {self.parameter_name} : {self.datatype}"
        return f"{self.index:04X}/{self.Subindex:02X} : {self.parameter_name} : {self.datatype}"


def _unescape_visible_string(s: str) -> str:
    result = []
    i = 0
    while i < len(s):
        if s[i] == "$" and i + 2 < len(s):
            try:
                result.append(chr(int(s[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        result.append(s[i])
        i += 1
    return "".join(result)


def _increment_number_at_end(input_str: str, increment: int) -> str:
    m = re.search(r"(\d+)$", input_str)
    if m:
        number = int(m.group(1)) + increment
        return re.sub(r"\d+$", str(number), input_str)
    return input_str


def _convert_to_byte(value: str) -> int:
    if not value:
        return 0
    return int(value, _get_base(value))


def _convert_to_uint16(value: str) -> int:
    if not value:
        return 0
    return int(value, _get_base(value))


def _convert_to_uint32(value: str) -> int:
    if not value:
        return 0
    return int(value, _get_base(value))


def _get_base(value: str) -> int:
    if not value:
        return 10
    if re.match(r"^\s*0[xX][0-9a-fA-F]+\s*$", value):
        return 16
    if re.match(r"^0[0-7]+", value):
        return 8
    return 10