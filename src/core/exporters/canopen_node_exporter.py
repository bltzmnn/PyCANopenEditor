"""CANopenNode Legacy (V1-3) C 源码导出器，对应 C# CanOpenNodeExporter"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from ..models.datatypes import (
    AccessType,
    DataType,
    ObjectType,
    PDOMappingType,
)
from ..models.eds import EDS
from ..models.od_entry import ODentry, _convert_to_byte
from ..models.warnings import Warnings, WarningClass
from .exporter_factory import ExporterDescriptor, ExporterFlags, IFileExporter


_ACCEPTABLE_CANOPEN_NAMES: dict[int, str] = {
    0x101800: "identity",
    0x140000: "RPDOCommunicationParameter",
    0x160000: "RPDOMappingParameter",
    0x180000: "TPDOCommunicationParameter",
    0x1A0000: "TPDOMappingParameter",
    0x100500: "COB_ID_SYNCMessage",
    0x101801: "vendorID",
    0x101802: "productCode",
    0x101803: "revisionNumber",
    0x101804: "serialNumber",
    0x120000: "SDOServerParameter",
    0x120001: "COB_IDClientToServer",
    0x120002: "COB_IDServerToClient",
    0x128000: "SDOClientParameter",
    0x128001: "COB_IDClientToServer",
    0x128002: "COB_IDServerToClient",
    0x102900: "errorBehavior",
}

_SPECIAL_ARRAY_RANGES = [
    (0x1301, 0x1340),
    (0x1381, 0x13C0),
    (0x1200, 0x127F),
    (0x1280, 0x12FF),
    (0x1400, 0x15FF),
    (0x1600, 0x17FF),
    (0x1800, 0x19FF),
    (0x1A00, 0x1BFF),
]


def make_cname(name: str, entry: ODentry) -> str:
    if not name:
        return ""

    tokens = [t for t in re.split(r"[\W]+", name.replace("-", "_")) if t]
    if not tokens:
        return ""

    output = ""
    prev = " "
    for tok in tokens:
        first = tok[0]
        if prev.isupper() and first.isupper():
            output += "_"
        if len(tok) > 1 and first.isalpha():
            output += first.upper() + tok[1:]
        else:
            output += tok
        prev = tok[-1]

    if len(output) > 1:
        if output[1].islower():
            output = output[0].lower() + output[1:]
    else:
        output = output.lower()

    key = (entry.index << 8) + entry.Subindex

    if 0x1200 <= entry.index < 0x1280:
        key = (0x1200 << 8) + entry.Subindex
    elif 0x1280 <= entry.index < 0x1300:
        key = (0x1280 << 8) + entry.Subindex
    elif 0x1400 <= entry.index < 0x1600:
        key = (0x1400 << 8) + entry.Subindex
    elif 0x1600 <= entry.index < 0x1800:
        key = (0x1600 << 8) + entry.Subindex
    elif 0x1800 <= entry.index < 0x1A00:
        key = (0x1800 << 8) + entry.Subindex
    elif 0x1A00 <= entry.index < 0x1C00:
        key = (0x1A00 << 8) + entry.Subindex

    if key in _ACCEPTABLE_CANOPEN_NAMES and not (entry.parent is not None and entry.Subindex == 0):
        new_name = _ACCEPTABLE_CANOPEN_NAMES[key]
        if output != new_name:
            Warnings.add_warning(
                f"Warning: index 0x{entry.index:04X}/{entry.Subindex:02X} "
                f"correcting name for CanOpenNode compatibility from {output} to {new_name}",
                WarningClass.WARNING_RENAME,
            )
        output = new_name

    return output


def _parse_default_value(defaultvalue: str) -> tuple[int, int]:
    if not defaultvalue:
        return 0, 10
    defaultvalue = defaultvalue.strip()
    nobase = 10
    if "$NODEID" in defaultvalue.upper():
        defaultvalue = defaultvalue.upper().replace("$NODEID", "").replace("+", "").strip()
        if not defaultvalue:
            return 0, 10
    if re.match(r"^0[xX][0-9a-fA-FL]+$", defaultvalue):
        nobase = 16
        defaultvalue = defaultvalue.replace("L", "")
    elif re.match(r"^0[0-7]+", defaultvalue):
        nobase = 8
    return int(defaultvalue, nobase), nobase


def format_value_with_datatype(defaultvalue: str, dt: DataType, fixstring: bool = False) -> str:
    try:
        nobase = 10
        if not defaultvalue:
            if dt in (DataType.VISIBLE_STRING, DataType.OCTET_STRING, DataType.UNKNOWN, DataType.UNICODE_STRING):
                if fixstring:
                    return "'X'"
                return ""
            defaultvalue = "0"

        nodeid_replace = False
        if "$NODEID" in defaultvalue.upper():
            defaultvalue = defaultvalue.upper().replace("$NODEID", "").replace("+", "").strip()
            nodeid_replace = True

        if re.match(r"^0[xX][0-9a-fA-FL]+$", defaultvalue):
            nobase = 16
            defaultvalue = defaultvalue.replace("L", "")

        if re.match(r"^0[0-7]+", defaultvalue):
            nobase = 8

        if dt in (DataType.UNSIGNED24, DataType.UNSIGNED32):
            return f"0x{int(defaultvalue, nobase):04X}L"
        if dt in (DataType.INTEGER24, DataType.INTEGER32):
            return f"0x{int(defaultvalue, nobase) & 0xFFFFFFFF:04X}L"
        if dt in (DataType.REAL32, DataType.REAL64):
            return defaultvalue
        if dt == DataType.UNICODE_STRING:
            return f"'{defaultvalue}'"
        if dt == DataType.VISIBLE_STRING:
            chars = list(defaultvalue)
            parts = [f"'{c}'" for c in chars]
            return "{" + ", ".join(parts) + "}"
        if dt == DataType.OCTET_STRING:
            bits = defaultvalue.split()
            parts = [f"0x{int(b, 16):02X}" for b in bits]
            return "{" + ", ".join(parts) + "}"
        if dt == DataType.INTEGER8:
            return f"0x{int(defaultvalue, nobase) & 0xFF:01X}"
        if dt == DataType.INTEGER16:
            return f"0x{int(defaultvalue, nobase) & 0xFFFF:02X}"
        if dt == DataType.UNSIGNED8:
            return f"0x{int(defaultvalue, nobase) & 0xFF:01X}L"
        if dt == DataType.UNSIGNED16:
            return f"0x{int(defaultvalue, nobase) & 0xFFFF:02X}"
        if dt == DataType.INTEGER64:
            return f"0x{int(defaultvalue, nobase) & 0xFFFFFFFFFFFFFFFF:08X}L"
        if dt == DataType.UNSIGNED64:
            return f"0x{int(defaultvalue, nobase) & 0xFFFFFFFFFFFFFFFF:08X}L"
        if dt in (DataType.TIME_DIFFERENCE, DataType.TIME_OF_DAY):
            return f"{{{int(defaultvalue, nobase)}}}"

        return f"{int(defaultvalue, nobase):X}"
    except Exception:
        Warnings.add_warning(
            f"Error converting value {defaultvalue} to type {dt.name}",
            WarningClass.WARNING_BUILD,
        )
        return ""


def get_flags(od: ODentry) -> int:
    flags = 0
    mapping = 0

    if od.objecttype == ObjectType.RECORD:
        return 0

    storage = od.prop.CO_storageGroup if od.parent is None else od.parent.prop.CO_storageGroup
    storage = storage.upper()
    if storage == "ROM":
        flags = 0x01
    elif storage == "RAM":
        flags = 0x02
    else:
        flags = 0x03

    if od.accesstype in (AccessType.RO, AccessType.RW, AccessType.RWR, AccessType.RWW, AccessType.CONST):
        flags |= 0x04
        if od.accesstype != AccessType.RWW:
            mapping |= 0x20

    if od.accesstype in (AccessType.WO, AccessType.RW, AccessType.RWR, AccessType.RWW):
        flags |= 0x08
        if od.accesstype != AccessType.RWR:
            mapping |= 0x10

    if od.index == 0x1003:
        flags |= 0x08

    if od.PDOtype == PDOMappingType.RPDO:
        mapping |= 0x10
    elif od.PDOtype == PDOMappingType.TPDO:
        mapping |= 0x20
    elif od.PDOtype in (PDOMappingType.OPTIONAL, PDOMappingType.DEFAULT):
        mapping |= 0x30

    if od.PDOMapping:
        flags |= mapping

    if od.prop.CO_flagsPDO:
        flags |= 0x40
    if od.parent is not None and od.parent.prop.CO_flagsPDO:
        flags |= 0x40

    data_size = math.ceil(od.sizeof_datatype() / 8.0) if od.sizeof_datatype() > 0 else 0
    if data_size > 1:
        if od.datatype not in (DataType.VISIBLE_STRING, DataType.OCTET_STRING):
            flags |= 0x80

    return flags


class CanOpenNodeExporter(IFileExporter):
    """CANopenNode Legacy (V1-3) 导出器"""

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "CanOpenNode",
                [".h", ".c"],
                ExporterFlags.CanOpenNode,
                lambda filepath, eds_list: CanOpenNodeExporter()._export(filepath, eds_list[0]),
            )
        ]

    def _export(self, filepath: str, eds: EDS) -> None:
        folderpath = os.path.dirname(filepath) or "."
        filename = os.path.splitext(os.path.basename(filepath))[0] or "CO_OD"
        self._eds = eds
        self._enabled_count = eds.GetNoEnabledObjects()
        self._au: dict[str, int] = {}
        self._openings: list[int] = []
        self._closings: list[int] = []
        self._max_rx_mapping_size = 0
        self._max_tx_mapping_size = 0
        self._max_rx_mapping_od: Optional[ODentry] = None
        self._max_tx_mapping_od: Optional[ODentry] = None
        self._no_tx_pdos = 0
        self._no_rx_pdos = 0
        self._no_sdo_clients = 0
        self._no_sdo_servers = 0
        self._no_sync = 0
        self._no_emcy = 0
        self._no_time = 0
        self._no_gfc = 0
        self._no_srdo = 0

        self._count_pdos()
        self._fix_compat_entry()
        self._prewalk_arrays()

        self._export_h(folderpath, filename)
        self._export_c(folderpath, filename)

    def _object_active(self, index: int) -> bool:
        if index in self._eds.ods:
            return not self._eds.ods[index].prop.CO_disabled
        return False

    def _count_pdos(self) -> None:
        check = 0
        if self._object_active(0x1005):
            check += 1
        if self._object_active(0x1006):
            check += 1
        if self._object_active(0x1007):
            check += 1
        if self._object_active(0x1019):
            check += 1
        self._no_sync = 1 if check == 4 else 0
        if check != 4:
            Warnings.add_warning(
                "BUILD WARNING, required objects for SYNC are not present 0x1005,0x1006,0x1007,0x1019",
                WarningClass.WARNING_BUILD,
            )

        check = 0
        if self._object_active(0x1003):
            check += 1
        if self._object_active(0x1014):
            check += 1
        if self._object_active(0x1015):
            check += 1
        self._no_emcy = 1 if check == 3 else 0
        if check != 3:
            Warnings.add_warning(
                "BUILD WARNING, required objects for EMCY are not present 0x1003,0x1014,0x1015",
                WarningClass.WARNING_BUILD,
            )

        self._no_time = 1 if self._object_active(0x1012) else 0

        check = 0
        if self._object_active(0x1F80):
            check += 1
        if self._object_active(0x1029):
            check += 1
        if self._object_active(0x1017):
            check += 1
        if self._object_active(0x1001):
            check += 1
        if check != 4:
            Warnings.add_warning(
                "BUILD WARNING, required objects for NMT Client are not present 0x1f80,0x1029,0x1017,0x1001",
                WarningClass.WARNING_BUILD,
            )

        for index in self._eds.ods:
            od = self._eds.ods[index]
            if od.prop.CO_disabled:
                continue
            if 0x1400 <= index < 0x1600:
                self._no_rx_pdos += 1
            if 0x1800 <= index < 0x1A00:
                self._no_tx_pdos += 1
            if (index & 0xFF80) == 0x1200:
                self._no_sdo_servers += 1
            if (index & 0xFF80) == 0x1280:
                self._no_sdo_clients += 1
            if index == 0x1300:
                self._no_gfc = 1
            if 0x1301 <= index <= 0x1340:
                self._no_srdo += 1

    def _fix_compat_entry(self) -> None:
        for idx in range(0x1800, 0x1900):
            if self._object_active(idx):
                od = self._eds.ods[idx]
                if not od.Containssubindex(0x04):
                    compat = ODentry(
                        parameter_name="compatibility entry",
                        index=idx,
                        datatype=DataType.UNSIGNED8,
                        defaultvalue="0",
                        accesstype=AccessType.RO,
                        pdo_type=PDOMappingType.NO,
                        parent=od,
                    )
                    od.subobjects[0x04] = compat

    def _special_array_search(self, start: int, end: int) -> None:
        lowest = 0xFFFF
        highest = 0x0000
        for idx, od in self._eds.ods.items():
            if od.prop.CO_disabled:
                continue
            if start <= idx <= end:
                if idx > highest:
                    highest = idx
                if idx < lowest:
                    lowest = idx
        if lowest != 0xFFFF and highest != 0x0000:
            self._openings.append(lowest)
            self._closings.append(highest)

    def _arrayspecial(self, index: int, is_open: bool) -> bool:
        if is_open:
            return index in self._openings
        return index in self._closings

    def _prewalk_arrays(self) -> None:
        for od in self._eds.ods.values():
            if od.prop.CO_disabled:
                continue
            name = make_cname(od.parameter_name, od)
            self._au[name] = self._au.get(name, 0) + 1

        for start, end in _SPECIAL_ARRAY_RANGES:
            self._special_array_search(start, end)

        for name, count in self._au.items():
            if count > 1:
                lowest = 0xFFFF
                highest = 0x0000
                for idx, od in self._eds.ods.items():
                    n = make_cname(od.parameter_name, od)
                    if n == name:
                        if idx > highest:
                            highest = idx
                        if idx < lowest:
                            lowest = idx
                if lowest not in self._openings:
                    self._openings.append(lowest)
                    self._closings.append(highest)

        self._max_rx_mapping_size = 0
        self._max_tx_mapping_size = 0
        self._max_rx_mapping_od = None
        self._max_tx_mapping_od = None

        for x in range(0x1600, 0x1800):
            if self._object_active(x):
                maxcount = _convert_to_byte(self._eds.ods[x].subobjects[0].defaultvalue)
                if maxcount > self._max_rx_mapping_size:
                    self._max_rx_mapping_size = maxcount
                    self._max_rx_mapping_od = self._eds.ods[x]

        for x in range(0x1A00, 0x1C00):
            if self._object_active(x):
                maxcount = _convert_to_byte(self._eds.ods[x].subobjects[0].defaultvalue)
                if maxcount > self._max_tx_mapping_size:
                    self._max_tx_mapping_size = maxcount
                    self._max_tx_mapping_od = self._eds.ods[x]

    def _print_h_bylocation(self, location: str) -> str:
        lines = []
        for od in self._eds.ods.values():
            if od.prop.CO_disabled or od.prop.CO_storageGroup != location:
                continue
            lines.append(self._print_h_entry(od))
        return "".join(lines)

    def _print_h_entry(self, od: ODentry) -> str:
        lines = []
        name = make_cname(od.parameter_name, od)

        if od.Nosubindexes == 0:
            special_array_length = ""
            if od.datatype in (DataType.VISIBLE_STRING, DataType.OCTET_STRING, DataType.UNICODE_STRING):
                if od.lengthof_string == 0:
                    Warnings.add_warning(
                        f" Object 0x{od.index:04X}/{od.Subindex:02X} A string must have a default value "
                        f"to set the required datasize for canopen node, i have set this to [1] byte to prevent compile errors",
                        WarningClass.WARNING_STRING,
                    )
                    special_array_length = "[1]"
                else:
                    special_array_length = f"[{od.lengthof_string}]"
            lines.append(f"/*{od.index:04X}      */ {od.datatype.name:<14} {name}{special_array_length};\n")
        else:
            t = self._eds.Getdatatype(od)
            if od.objecttype == ObjectType.RECORD:
                objecttype_words = f"OD_{make_cname(od.parameter_name, od)}_t"
            else:
                objecttype_words = t.name

            cname = make_cname(od.parameter_name, od)
            if self._au.get(cname, 0) > 1:
                if not hasattr(self, '_lastname'):
                    self._lastname = ""
                if self._lastname == name:
                    return ""
                self._lastname = name
                lines.append(f"/*{od.index:04X}      */ {objecttype_words:<15} {cname}[{self._au[cname]}];\n")
            else:
                if od.objecttype == ObjectType.RECORD:
                    if self._arrayspecial(od.index, True):
                        lines.append(f"/*{od.index:04X}      */ {objecttype_words:<15} {cname}[1];\n")
                    else:
                        lines.append(f"/*{od.index:04X}      */ {objecttype_words:<15} {cname};\n")
                else:
                    special_array_length = ""
                    if od.datatype in (DataType.VISIBLE_STRING, DataType.OCTET_STRING, DataType.UNICODE_STRING):
                        max_len = 0
                        for sub in od.subobjects.values():
                            if sub.lengthof_string > max_len:
                                max_len = sub.lengthof_string
                        if max_len == 0:
                            Warnings.add_warning(
                                f" Object children of 0x{od.index:04X} A string must have a default value "
                                f"to set the required datasize for canopen node, i have set this to [1] byte to prevent compile errors",
                                WarningClass.WARNING_STRING,
                            )
                            max_len = 1
                        special_array_length = f"[{max_len}]"
                    lines.append(f"/*{od.index:04X}      */ {objecttype_words:<15} {cname}[{od.Nosubindexes - 1}]{special_array_length};\n")

        return "".join(lines)

    def _export_h(self, folderpath: str, filename: str) -> None:
        if not filename:
            filename = "CO_OD"
        filepath = os.path.join(folderpath, filename + ".h")
        eds = self._eds

        self._lastname = ""

        with open(filepath, "w", newline="\n") as f:
            f.write("// clang-format off\n")
            f.write(
                "/*******************************************************************************\n"
                "    CANopen Object Dictionary definition for CANopenNode v1 to v2\n"
                "\n"
                "    This file was automatically generated by CANopenEditor (Python)\n"
                "\n"
                "    https://github.com/CANopenNode/CANopenNode\n"
                "    https://github.com/CANopenNode/CANopenEditor\n"
                "\n"
                "    DON'T EDIT THIS FILE MANUALLY !!!!\n"
                "*******************************************************************************/\n"
            )

            f.write("#ifndef CO_OD_H_\n")
            f.write("#define CO_OD_H_\n\n")

            f.write(
                "/*******************************************************************************\n"
                "   CANopen DATA TYPES\n"
                "*******************************************************************************/\n"
                "   typedef bool_t       BOOLEAN;\n"
                "   typedef uint8_t      UNSIGNED8;\n"
                "   typedef uint16_t     UNSIGNED16;\n"
                "   typedef uint32_t     UNSIGNED32;\n"
                "   typedef uint64_t     UNSIGNED64;\n"
                "   typedef int8_t       INTEGER8;\n"
                "   typedef int16_t      INTEGER16;\n"
                "   typedef int32_t      INTEGER32;\n"
                "   typedef int64_t      INTEGER64;\n"
                "   typedef float32_t    REAL32;\n"
                "   typedef float64_t    REAL64;\n"
                "   typedef char         VISIBLE_STRING;\n"
                "   typedef uint8_t      OCTET_STRING;\n"
                "\n"
                "   #ifdef DOMAIN\n"
                "   #undef DOMAIN\n"
                "   #endif\n"
                "\n"
                "   typedef domain_t     DOMAIN;\n"
                "\n\n"
            )

            f.write("/*******************************************************************************\n")
            f.write("   FILE INFO:\n")
            f.write(f"      FileName:     {os.path.basename(eds.projectFilename)}\n")
            f.write(f"      FileVersion:  {eds.fi.FileVersion}\n")
            f.write(f"      CreationTime: {eds.fi.CreationTime}\n")
            f.write(f"      CreationDate: {eds.fi.CreationDate}\n")
            f.write(f"      CreatedBy:    {eds.fi.CreatedBy}\n")
            f.write("*******************************************************************************/\n\n\n")

            f.write("/*******************************************************************************\n")
            f.write("   DEVICE INFO:\n")
            f.write(f"      VendorName:     {eds.di.VendorName}\n")
            f.write(f"      VendorNumber:   {eds.di.VendorNumber}\n")
            f.write(f"      ProductName:    {eds.di.ProductName}\n")
            f.write(f"      ProductNumber:  {eds.di.ProductNumber}\n")
            f.write("*******************************************************************************/\n\n\n")

            f.write(
                "/*******************************************************************************\n"
                "   FEATURES\n"
                "*******************************************************************************/\n"
            )
            f.write(f"  #define CO_NO_SYNC                     {self._no_sync}   //Associated objects: 1005-1007\n")
            f.write(f"  #define CO_NO_EMERGENCY                {self._no_emcy}   //Associated objects: 1014, 1015\n")
            f.write(f"  #define CO_NO_TIME                     {self._no_time}   //Associated objects: 1012, 1013\n")
            f.write(f"  #define CO_NO_SDO_SERVER               {self._no_sdo_servers}   //Associated objects: 1200-127F\n")
            f.write(f"  #define CO_NO_SDO_CLIENT               {self._no_sdo_clients}   //Associated objects: 1280-12FF\n")
            f.write(f"  #define CO_NO_GFC                      {self._no_gfc}   //Associated objects: 1300\n")
            f.write(f"  #define CO_NO_SRDO                     {self._no_srdo}   //Associated objects: 1301-1341, 1381-13C0\n")

            lss_server = 1 if eds.di.LSS_Supported else 0
            lss_client = 1 if eds.di.LSS_Master else 0
            ng_slave = 1 if eds.di.NG_Slave else 0
            f.write(f"  #define CO_NO_LSS_SERVER               {lss_server}   //LSS Slave\n")
            f.write(f"  #define CO_NO_LSS_CLIENT               {lss_client}   //LSS Master\n")
            f.write(f"  #define CO_NODE_GUARDING_SLAVE         {ng_slave}   //NG Slave\n")
            f.write(f"  #define CO_NODE_GUARDING_MASTER        {eds.di.NrOfNG_MonitoredNodes}   //NG Master\n")
            f.write(f"  #define CO_NO_RPDO                     {self._no_rx_pdos}   //Associated objects: 14xx, 16xx\n")
            f.write(f"  #define CO_NO_TPDO                     {self._no_tx_pdos}   //Associated objects: 18xx, 1Axx\n")

            is_master = False
            if self._object_active(0x1F80):
                master = self._eds.ods[0x1F80]
                meh = format_value_with_datatype(master.defaultvalue, master.datatype)
                meh = meh.replace("L", "")
                try:
                    nmt_startup = int(meh, 16)
                    if nmt_startup & 0x01:
                        is_master = True
                except ValueError:
                    pass

            f.write(f"  #define CO_NO_NMT_MASTER               {1 if is_master else 0}\n")
            f.write("  #define CO_NO_TRACE                    0\n\n\n")

            f.write(
                "/*******************************************************************************\n"
                "   OBJECT DICTIONARY\n"
                "*******************************************************************************/\n"
            )
            f.write(f"   #define CO_OD_NoOfElements             {self._enabled_count}\n\n\n")

            f.write(
                "/*******************************************************************************\n"
                "   TYPE DEFINITIONS FOR RECORDS\n"
                "*******************************************************************************/\n"
            )

            eds.CO_storageGroups.append("ROM")
            eds.CO_storageGroups.append("EEPROM")

            struct_name_list: list[str] = []
            for idx, od in self._eds.ods.items():
                eds.CO_storageGroups.append(od.prop.CO_storageGroup)
                if od.objecttype != ObjectType.RECORD:
                    continue
                structname = f"OD_{make_cname(od.parameter_name, od)}_t"
                if structname in struct_name_list:
                    continue
                struct_name_list.append(structname)

                record_od = od
                if 0x1600 <= idx < 0x1800:
                    record_od = self._max_rx_mapping_od
                if 0x1A00 <= idx < 0x1C00:
                    record_od = self._max_tx_mapping_od
                if record_od is None:
                    continue

                struct_member_list: list[str] = []
                f.write(f"/*{idx:04X}      */ typedef struct {{\n")
                for sub_idx, sub_od in record_od.subobjects.items():
                    param_arr_len = ""
                    proposedname = make_cname(sub_od.parameter_name, sub_od)
                    suffix = 1
                    while proposedname in struct_member_list:
                        Warnings.add_warning(
                            f"STRUCT WARNING; in 0x{sub_od.index:04X}/{sub_od.Subindex:02X} "
                            f"Duplicate struct entry name, it has been auto numbered",
                            WarningClass.WARNING_STRUCT,
                        )
                        proposedname = make_cname(sub_od.parameter_name, sub_od) + str(suffix)
                        suffix += 1
                    struct_member_list.append(proposedname)
                    if sub_od.datatype in (DataType.VISIBLE_STRING, DataType.OCTET_STRING):
                        param_arr_len = f"[{sub_od.lengthof_string}]"
                    f.write(f"               {sub_od.datatype.name:<15}{proposedname}{param_arr_len};\n")
                f.write(f"               }}              {structname};\n\n")

            f.write(
                "\n"
                "/*******************************************************************************\n"
                "   TYPE DEFINITIONS FOR OBJECT DICTIONARY INDEXES\n"
                "\n"
                "   some of those are redundant with CO_SDO.h CO_ObjDicId_t <Common CiA301 object\n"
                "   dictionary entries>\n"
                "*******************************************************************************/\n"
            )

            for idx, od in self._eds.ods.items():
                if od.prop.CO_disabled:
                    continue
                t = self._eds.Getdatatype(od)
                cname = make_cname(od.parameter_name, od)

                if od.objecttype in (ObjectType.ARRAY, ObjectType.RECORD):
                    f.write(f"/*{od.index:04X} */\n")
                    f.write(f"        #define {f'OD_{od.index:04X}_{cname}':<51} 0x{od.index:04X}\n\n")
                    f.write(f"        #define {f'OD_{od.index:04X}_0_{cname}_maxSubIndex':<51} 0\n")

                    odsi_list: list[str] = []
                    odsi_out = ""
                    for sub_idx, sub in od.subobjects.items():
                        if sub_idx == 0:
                            continue
                        odsi = f"OD_{od.index:04X}_{sub_idx}_{cname}_{make_cname(sub.parameter_name, sub)}"
                        if odsi in odsi_list:
                            continue
                        odsi_list.append(odsi)
                        odsi_out += f"        #define {odsi:<51} {sub_idx}\n"
                    f.write(odsi_out)
                    f.write("\n")
                else:
                    f.write(f"/*{od.index:04X} */\n")
                    f.write(f"        #define {f'OD_{od.index:04X}_{cname}':<51} 0x{od.index:04X}\n\n")

            f.write(
                "/*******************************************************************************\n"
                "   STRUCTURES FOR VARIABLES IN DIFFERENT MEMORY LOCATIONS\n"
                "*******************************************************************************\n"
                "#define  CO_OD_FIRST_LAST_WORD     0x55 //Any value from 0x01 to 0xFE. If changed, EEPROM will be reinitialized.\n"
            )

            for location in eds.CO_storageGroups:
                if location == "Unused":
                    continue
                f.write(f"/***** Structure for {location} variables ********************************************/\n")
                f.write(f"struct sCO_OD_{location}{{\n")
                f.write("               UNSIGNED32     FirstWord;\n\n")
                f.write(self._print_h_bylocation(location))
                f.write("\n               UNSIGNED32     LastWord;\n};\n")

            f.write("/***** Declaration of Object Dictionary variables *****************************/\n")
            for location in eds.CO_storageGroups:
                if location == "Unused":
                    continue
                f.write(f"extern struct sCO_OD_{location} CO_OD_{location};\n\n")

            f.write(
                "/*******************************************************************************\n"
                "   ALIASES FOR OBJECT DICTIONARY VARIABLES\n"
                "*******************************************************************************/\n"
            )

            constructed_rec_types: list[str] = []
            for idx, od in self._eds.ods.items():
                if od.prop.CO_disabled:
                    continue
                loc = "CO_OD_" + od.prop.CO_storageGroup
                t = self._eds.Getdatatype(od)
                cname = make_cname(od.parameter_name, od)

                if od.objecttype == ObjectType.VAR or od.objecttype not in (ObjectType.ARRAY, ObjectType.RECORD):
                    f.write(f"/*{od.index:04X}, Data Type: {t.name} */\n")
                    f.write(f"        #define {f'OD_{cname}_idx':<51} 0x{od.index:04X}\n")
                    f.write(f"        #define {f'OD_{cname}':<51} {loc}.{cname}\n")
                    if od.datatype in (DataType.OCTET_STRING, DataType.VISIBLE_STRING):
                        f.write(f"        #define {f'ODL_{cname}_stringLength':<51} {od.lengthof_string}\n")
                    f.write("\n")

                elif od.objecttype == ObjectType.ARRAY:
                    dt = od.datatype
                    f.write(f"/*{od.index:04X}, Data Type: {t.name}, Array[{od.Nosubindexes - 1}] */\n")
                    f.write(f"        #define {f'OD_{cname}_idx':<51} 0x{od.index:04X}\n")
                    f.write(f"        #define {f'OD_{cname}':<51} {loc}.{cname}\n")
                    f.write(f"        #define {f'ODL_{cname}_arrayLength':<51} {od.Nosubindexes - 1}\n")

                    oda_list: list[str] = []
                    oda_out = ""
                    for sub_idx, sub in od.subobjects.items():
                        if sub_idx == 0:
                            continue
                        oda = f"ODA_{cname}_{make_cname(sub.parameter_name, sub)}"
                        if oda in oda_list:
                            continue
                        oda_list.append(oda)
                        oda_out += f"        #define {oda:<51} {sub_idx - 1}\n"
                    f.write(oda_out)
                    f.write("\n")

                elif od.objecttype == ObjectType.RECORD:
                    rectype = make_cname(od.parameter_name, od)
                    if rectype not in constructed_rec_types:
                        f.write(f"/*{od.index:04X}, Data Type: {rectype}_t */\n")
                        f.write(f"        #define {f'OD_{rectype}_idx':<51} 0x{od.index:04X}\n")
                        f.write(f"        #define {f'OD_{rectype}':<51} {loc}.{rectype}\n")
                        constructed_rec_types.append(rectype)
                        f.write("\n")

            f.write("#endif\n")
            f.write("// clang-format on\n")

    def _export_c(self, folderpath: str, filename: str) -> None:
        if not filename:
            filename = "CO_OD"
        filepath = os.path.join(folderpath, filename + ".c")
        eds = self._eds

        with open(filepath, "w", newline="\n") as f:
            f.write("// clang-format off\n")
            f.write(
                "/*******************************************************************************\n"
                "    CANopen Object Dictionary definition for CANopenNode v1 to v2\n"
                "\n"
                "    This file was automatically generated by CANopenEditor (Python)\n"
                "\n"
                "    https://github.com/CANopenNode/CANopenNode\n"
                "    https://github.com/CANopenNode/CANopenEditor\n"
                "\n"
                "    DON'T EDIT THIS FILE MANUALLY !!!!\n"
                "*******************************************************************************/\n"
            )
            f.write(
                '// For CANopenNode V2 users, C macro `CO_VERSION_MAJOR=2` has to be added to project options\n'
                '#ifndef CO_VERSION_MAJOR\n'
                ' #include "CO_driver.h"\n'
                f' #include "{filename}.h"\n'
                ' #include "CO_SDO.h"\n'
                '#elif CO_VERSION_MAJOR < 4\n'
                ' #include "301/CO_driver.h"\n'
                f' #include "{filename}.h"\n'
                ' #include "301/CO_SDOserver.h"\n'
                '#else\n'
                ' #error This Object dictionary is not compatible with CANopenNode v4.0 and up!\n'
                '#endif\n\n'
                '/*******************************************************************************\n'
                '   DEFINITION AND INITIALIZATION OF OBJECT DICTIONARY VARIABLES\n'
                '*******************************************************************************/\n\n'
            )

            for location in eds.CO_storageGroups:
                if location == "Unused":
                    continue
                f.write(f"/***** Definition for {location} variables *******************************************/\n")
                f.write(f"struct sCO_OD_{location} CO_OD_{location} = {{\n")
                f.write("           CO_OD_FIRST_LAST_WORD,\n\n")
                f.write(self._export_od_def_array(location))
                f.write("\n           CO_OD_FIRST_LAST_WORD,\n};\n\n")

            f.write(
                "\n\n"
                "/*******************************************************************************\n"
                "   STRUCTURES FOR RECORD TYPE OBJECTS\n"
                "*******************************************************************************/\n\n"
            )
            f.write(self._export_record_types())

            f.write(
                "/*******************************************************************************\n"
                "   OBJECT DICTIONARY\n"
                "*******************************************************************************/\n"
                "const CO_OD_entry_t CO_OD[CO_OD_NoOfElements] = {\n"
            )
            f.write(self._write_od())
            f.write("};\n")
            f.write("// clang-format on\n")

    def _write_od(self) -> str:
        lines = []
        for idx, od in self._eds.ods.items():
            if od.prop.CO_disabled:
                continue
            lines.append(self._write_od_line(od))
        return "".join(lines)

    def _write_od_line(self, od: ODentry) -> str:
        loc = "CO_OD_" + od.prop.CO_storageGroup
        flags = get_flags(od)
        data_size = 0 if od.objecttype == ObjectType.RECORD else math.ceil(od.sizeof_datatype() / 8.0)

        array = ""
        if od.objecttype == ObjectType.ARRAY and od.Nosubindexes > 0:
            array = "[0]"

        arrayspecialcase = False
        arrayspecialcasecount = 0

        if self._arrayspecial(od.index, True):
            arrayspecialcase = True
            arrayspecialcasecount = 0

        if arrayspecialcase:
            array = f"[{arrayspecialcasecount}]"
            arrayspecialcasecount += 1

        nosubindexs = od.Nosubindexes
        if od.objecttype in (ObjectType.ARRAY, ObjectType.RECORD):
            if nosubindexs > 0:
                nosubindexs -= 1

        if od.objecttype == ObjectType.ARRAY:
            maxsub = od.Getmaxsubindex()
            if maxsub != nosubindexs:
                if od.index != 0x1003 and od.index != 0x1011:
                    Warnings.add_warning(
                        f"Subindex discrepancy on object 0x{od.index:04X} "
                        f"arraysize: {nosubindexs} vs max sub-index: {maxsub}"
                    )
                if od.index != 0x1003:
                    nosubindexs = maxsub

        if od.objecttype == ObjectType.RECORD:
            pdata = f"&OD_record{od.index:04X}"
        else:
            pdata = f"&{loc}.{make_cname(od.parameter_name, od)}{array}"

        if (od.objecttype in (ObjectType.VAR, ObjectType.ARRAY)) and od.datatype == DataType.DOMAIN:
            pdata = "0"

        result = f"{{0x{od.index:04X}, 0x{nosubindexs:02X}, 0x{flags:02X}, {data_size:2d}, (void*){pdata}}},\n"

        if self._arrayspecial(od.index, False):
            arrayspecialcase = False

        return result

    def _export_record_types(self) -> str:
        lines = []
        arrayopen = False
        arrayindex = 0

        for idx, od in self._eds.ods.items():
            if od.objecttype != ObjectType.RECORD:
                continue
            if od.prop.CO_disabled:
                continue

            count = len(od.subobjects)

            lines.append(f"/*0x{od.index:04X}*/ const CO_OD_entryRecord_t OD_record{od.index:04X}[{count}] = {{\n")

            arrayaccess = ""
            if self._arrayspecial(od.index, True) or arrayopen:
                arrayaccess = f"[{arrayindex}]"
                arrayindex += 1
                arrayopen = True

            for sub_idx, sub in od.subobjects.items():
                lines.append(self._export_one_record_type(sub, arrayaccess))

            if self._arrayspecial(od.index, False):
                arrayindex = 0
                arrayopen = False

            lines.append("};\n\n")

        return "".join(lines)

    def _export_one_record_type(self, sub: ODentry, arrayaccess: str) -> str:
        if sub is None or sub.parent is None:
            return ""

        cname = make_cname(sub.parent.parameter_name, sub.parent)
        subcname = make_cname(sub.parameter_name, sub)
        data_size = math.ceil(sub.sizeof_datatype() / 8.0) if sub.sizeof_datatype() > 0 else 0
        flags = get_flags(sub)

        if sub.datatype != DataType.DOMAIN:
            loc = "CO_OD_" + sub.parent.prop.CO_storageGroup
            return f"           {{(void*)&{loc}.{cname}{arrayaccess}.{subcname}, 0x{flags:02X}, 0x{data_size:X} }},\n"
        else:
            return f"           {{(void*)0, 0x{flags:02X}, 0x{data_size:X} }},\n"

    def _export_od_def_array(self, location: str) -> str:
        lines = []
        for idx, od in self._eds.ods.items():
            if od.prop.CO_disabled or od.prop.CO_storageGroup != location:
                continue

            if od.Nosubindexes == 0:
                lines.append(f"/*{od.index:04X}*/ {format_value_with_datatype(od.defaultvalue, od.datatype, True)},\n")
            else:
                if self._arrayspecial(od.index, True):
                    lines.append(f"/*{od.index:04X}*/ {{")
                else:
                    lines.append(f"/*{od.index:04X}*/ {{")

                parts = []
                for sub_idx, sub in od.subobjects.items():
                    dt = sub.datatype
                    if od.objecttype == ObjectType.ARRAY and sub_idx == 0:
                        continue
                    parts.append(format_value_with_datatype(sub.defaultvalue, dt, True))
                lines.append(", ".join(parts))

                if self._arrayspecial(od.index, False):
                    lines.append("}},\n")
                else:
                    lines.append("},\n")

        return "".join(lines)
