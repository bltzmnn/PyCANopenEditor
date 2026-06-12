"""CANopenNode V4 C 源码导出器，对应 C# CanOpenNodeExporter_V4"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from ..models.datatypes import (
    AccessPDO,
    AccessSDO,
    AccessSRDO,
    DataType,
    ObjectType,
)
from ..models.eds import EDS
from ..models.od_entry import ODentry
from ..models.warnings import Warnings, WarningClass
from .exporter_factory import ExporterDescriptor, ExporterFlags, IFileExporter


def make_cname_v4(name: str) -> str:
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

    if output[0].isdigit():
        output = "_" + output
    elif len(output) > 1:
        if output[0].isalpha() and output[1].islower():
            output = output[0].lower() + output[1:]
    else:
        output = output.lower()

    return output


@dataclass
class DataProperties:
    c_type: str = "not specified"
    c_type_array: str = ""
    c_type_array0: str = ""
    c_type_multibyte: bool = False
    c_type_string: bool = False
    length: int = 0
    c_value: Optional[str] = None


def get_data_properties(
    data_type: DataType, defaultvalue: str, string_length: int, index_h: str
) -> DataProperties:
    data = DataProperties()
    nobase = 10
    value_defined = True

    if not defaultvalue:
        value_defined = False
    elif data_type not in (DataType.VISIBLE_STRING, DataType.UNICODE_STRING, DataType.OCTET_STRING):
        defaultvalue = defaultvalue.strip()
        if "$NODEID" in defaultvalue.upper():
            defaultvalue = defaultvalue.upper().replace("$NODEID", "").replace("+", "").strip()
            if not defaultvalue:
                defaultvalue = "0"

        if re.match(r"^0[xX][0-9a-fA-FUL]+$", defaultvalue):
            nobase = 16
            defaultvalue = defaultvalue.replace("U", "").replace("L", "")
        elif re.match(r"^0[0-7]+", defaultvalue):
            nobase = 8

    try:
        signed_number = False
        unsigned_number = False

        if data_type == DataType.BOOLEAN:
            data.length = 1
            data.c_type = "bool_t"
            if value_defined:
                data.c_value = "false" if defaultvalue.lower() in ("false", "0") else "true"

        elif data_type == DataType.INTEGER8:
            data.length = 1
            data.c_type = "int8_t"
            if value_defined:
                data.c_value = str(int(defaultvalue, nobase))

        elif data_type == DataType.INTEGER16:
            data.length = 2
            data.c_type = "int16_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = str(int(defaultvalue, nobase))

        elif data_type == DataType.INTEGER32:
            data.length = 4
            data.c_type = "int32_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = str(int(defaultvalue, nobase))

        elif data_type == DataType.INTEGER64:
            data.length = 8
            data.c_type = "int64_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = str(int(defaultvalue, nobase))

        elif data_type == DataType.UNSIGNED8:
            data.length = 1
            data.c_type = "uint8_t"
            if value_defined:
                data.c_value = f"0x{int(defaultvalue, nobase):02X}"

        elif data_type == DataType.UNSIGNED16:
            data.length = 2
            data.c_type = "uint16_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = f"0x{int(defaultvalue, nobase):04X}"

        elif data_type == DataType.UNSIGNED32:
            data.length = 4
            data.c_type = "uint32_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = f"0x{int(defaultvalue, nobase):08X}"

        elif data_type == DataType.UNSIGNED64:
            data.length = 8
            data.c_type = "uint64_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = f"0x{int(defaultvalue, nobase):016X}"

        elif data_type == DataType.REAL32:
            data.length = 4
            data.c_type = "float32_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = defaultvalue

        elif data_type == DataType.REAL64:
            data.length = 8
            data.c_type = "float64_t"
            data.c_type_multibyte = True
            if value_defined:
                data.c_value = defaultvalue

        elif data_type == DataType.DOMAIN:
            pass

        elif data_type == DataType.VISIBLE_STRING:
            data.c_type_string = True
            if value_defined or string_length > 0:
                chars = []
                length = 0
                if value_defined:
                    for b in defaultvalue.encode("utf-8"):
                        if b == ord("'"):
                            chars.append("'\\''")
                        elif 0x20 <= b < 0x7F:
                            chars.append(f"'{chr(b)}'")
                        elif b <= 0x7F:
                            chars.append(f"0x{b:02X}")
                        else:
                            chars.append(f"(char)0x{b:02X}")
                        length += 1
                for _ in range(length, string_length):
                    chars.append("0")
                chars.append("0")
                data.length = length
                data.c_type = "char"
                data.c_type_array = f"[{length + 1}]"
                data.c_type_array0 = "[0]"
                data.c_value = "{" + ", ".join(chars) + "}"

        elif data_type == DataType.OCTET_STRING:
            defaultvalue = defaultvalue.strip() if defaultvalue else ""
            if not defaultvalue:
                value_defined = False
            if value_defined or string_length > 0:
                bytes_list = []
                length = 0
                if value_defined:
                    hex_str = defaultvalue.replace(" ", "")
                    if len(hex_str) % 2 == 0:
                        for i in range(0, len(hex_str), 2):
                            try:
                                bytes_list.append(f"0x{int(hex_str[i:i+2], 16):02X}")
                                length += 1
                            except ValueError:
                                length = 0
                                bytes_list = []
                                break
                for _ in range(length, string_length):
                    bytes_list.append("0x00")
                data.length = length
                data.c_type = "uint8_t"
                data.c_type_array = f"[{length}]"
                data.c_type_array0 = "[0]"
                if length > 0:
                    data.c_value = "{" + ", ".join(bytes_list) + "}"
                else:
                    data.c_value = None

        elif data_type == DataType.UNICODE_STRING:
            data.c_type_string = True
            if value_defined or string_length > 0:
                words = []
                length = 0
                if value_defined:
                    encoded = defaultvalue.encode("utf-16-le")
                    for i in range(0, len(encoded), 2):
                        val = encoded[i] | (encoded[i + 1] << 8)
                        words.append(f"0x{val:04X}")
                        length += 1
                for _ in range(length, string_length):
                    words.append("0x0000")
                words.append("0x0000")
                data.length = length * 2
                data.c_type = "uint16_t"
                data.c_type_array = f"[{length + 1}]"
                data.c_type_array0 = "[0]"
                data.c_value = "{" + ", ".join(words) + "}"

        elif data_type == DataType.INTEGER24:
            data.length = 3
            signed_number = True
        elif data_type == DataType.INTEGER40:
            data.length = 5
            signed_number = True
        elif data_type == DataType.INTEGER48:
            data.length = 6
            signed_number = True
        elif data_type == DataType.INTEGER56:
            data.length = 7
            signed_number = True
        elif data_type == DataType.UNSIGNED24:
            data.length = 3
            unsigned_number = True
        elif data_type == DataType.UNSIGNED40:
            data.length = 5
            unsigned_number = True
        elif data_type in (DataType.UNSIGNED48, DataType.TIME_OF_DAY, DataType.TIME_DIFFERENCE):
            data.length = 6
            unsigned_number = True
        elif data_type == DataType.UNSIGNED56:
            data.length = 7
            unsigned_number = True

        else:
            Warnings.add_warning(
                f"Error in 0x{index_h}: Unknown dataType: {data_type}",
                WarningClass.WARNING_BUILD,
            )

        if value_defined and (signed_number or unsigned_number):
            value = int(defaultvalue, nobase)
            if signed_number and value < 0:
                value = value & 0xFFFFFFFFFFFFFFFF
            bytes_list = []
            for _ in range(data.length):
                bytes_list.append(f"0x{value & 0xFF:02X}")
                value >>= 8
            if value > 0:
                Warnings.add_warning(
                    f"Error in 0x{index_h}: Overflow error in default value {defaultvalue} of type {data_type}",
                    WarningClass.WARNING_BUILD,
                )
            else:
                data.c_type = "uint8_t"
                data.c_type_array = f"[{data.length}]"
                data.c_type_array0 = "[0]"
                data.c_value = "{" + ", ".join(bytes_list) + "}"

    except Exception:
        Warnings.add_warning(
            f"Error in 0x{index_h}: Error converting default value {defaultvalue} to type {data_type}",
            WarningClass.WARNING_BUILD,
        )

    return data


def get_attributes(od: ODentry, c_type_multibyte: bool, c_type_string: bool) -> str:
    attributes = []

    access_sdo = od.access_sdo()
    if access_sdo == AccessSDO.RO:
        attributes.append("ODA_SDO_R")
    elif access_sdo == AccessSDO.WO:
        attributes.append("ODA_SDO_W")
    elif access_sdo == AccessSDO.RW:
        attributes.append("ODA_SDO_RW")

    access_pdo = od.access_pdo()
    if access_pdo == AccessPDO.R:
        attributes.append("ODA_RPDO")
    elif access_pdo == AccessPDO.T:
        attributes.append("ODA_TPDO")
    elif access_pdo == AccessPDO.TR:
        attributes.append("ODA_TRPDO")

    access_srdo = od.prop.CO_accessSRDO
    if access_srdo == AccessSRDO.RX:
        attributes.append("ODA_RSRDO")
    elif access_srdo == AccessSRDO.TX:
        attributes.append("ODA_TSRDO")
    elif access_srdo == AccessSRDO.TRX:
        attributes.append("ODA_TRSRDO")

    if c_type_multibyte:
        attributes.append("ODA_MB")
    if c_type_string:
        attributes.append("ODA_STR")

    if not attributes:
        attributes.append("0")

    return " | ".join(attributes)


class CanOpenNodeExporterV4(IFileExporter):
    """CANopenNode V4 导出器"""

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "CanOpenNodeV4",
                [".h", ".c"],
                ExporterFlags.CanOpenNode,
                lambda filepath, eds_list: CanOpenNodeExporterV4()._export(filepath, eds_list[0]),
            )
        ]

    def _export(self, filepath: str, eds: EDS) -> None:
        folderpath = os.path.dirname(filepath) or "."
        filename = os.path.splitext(os.path.basename(filepath))[0] or "OD"
        self._odname = filename
        self._eds = eds

        self._prepare()

        self._export_h(folderpath, filename)
        self._export_c(folderpath, filename)

    def _prepare(self) -> None:
        self._od_storage_groups: list[str] = []
        self._od_storage_t: dict[str, list[str]] = {}
        self._od_storage: dict[str, list[str]] = {}
        self._od_objs_t: list[str] = []
        self._od_objs: list[str] = []
        self._od_list: list[str] = []
        self._od_defines: list[str] = []
        self._od_defines_long: list[str] = []
        self._od_cnt: dict[str, int] = {}
        self._od_arr_size: dict[str, int] = {}

        mapping_errors = self._eds.VerifyPDOMapping()
        if mapping_errors:
            Warnings.add_warning(
                f"Errors in PDO mappings:\r\n    " + "\r\n    ".join(mapping_errors),
                WarningClass.WARNING_BUILD,
            )

        for od in self._eds.ods.values():
            if od.prop.CO_disabled:
                continue

            index_h = f"{od.index:04X}"
            c_name = make_cname_v4(od.parameter_name)
            var_name = f"{index_h}_{c_name}"

            if od.prop.CO_storageGroup not in self._od_storage_groups:
                self._od_storage_groups.append(od.prop.CO_storageGroup)
                self._od_storage_t[od.prop.CO_storageGroup] = []
                self._od_storage[od.prop.CO_storageGroup] = []

            od_object_type = ""
            sub_entries_count = 0

            if od.objecttype == ObjectType.VAR:
                od_object_type = "VAR"
                sub_entries_count = self._prepare_var(od, index_h, var_name, od.prop.CO_storageGroup)
            elif od.objecttype == ObjectType.ARRAY:
                od_object_type = "ARR"
                sub_entries_count = self._prepare_arr(od, index_h, var_name, od.prop.CO_storageGroup)
            elif od.objecttype == ObjectType.RECORD:
                od_object_type = "REC"
                sub_entries_count = self._prepare_rec(od, index_h, var_name, od.prop.CO_storageGroup)

            if sub_entries_count < 1:
                continue

            self._od_defines.append(f"#define {self._odname}_ENTRY_H{index_h} &{self._odname}->list[{len(self._od_list)}]")
            self._od_defines_long.append(
                f"#define {self._odname}_ENTRY_H{var_name} &{self._odname}->list[{len(self._od_list)}]"
            )

            self._od_list.append(
                f"{{0x{index_h}, 0x{sub_entries_count:02X}, ODT_{od_object_type}, "
                f"&{self._odname}Objs.o_{var_name}, NULL}}"
            )

            self._verify_count_label(od, 0x1000, 0x1000, "NMT")
            self._verify_count_label(od, 0x1001, 0x1001, "EM")
            self._verify_count_label(od, 0x1005, 0x1005, "SYNC")
            self._verify_count_label(od, 0x1006, 0x1006, "SYNC_PROD")
            self._verify_count_label(od, 0x1010, 0x1010, "STORAGE")
            self._verify_count_label(od, 0x1012, 0x1012, "TIME")
            self._verify_count_label(od, 0x1014, 0x1014, "EM_PROD")
            self._verify_count_label(od, 0x1016, 0x1016, "HB_CONS")
            self._verify_count_label(od, 0x1017, 0x1017, "HB_PROD")
            self._verify_count_label(od, 0x1200, 0x127F, "SDO_SRV")
            self._verify_count_label(od, 0x1280, 0x12FF, "SDO_CLI")
            self._verify_count_label(od, 0x1300, 0x1300, "GFC")
            self._verify_count_label(od, 0x1301, 0x1340, "SRDO")
            self._verify_count_label(od, 0x1400, 0x15FF, "RPDO")
            self._verify_count_label(od, 0x1800, 0x19FF, "TPDO")

            if od.prop.CO_countLabel:
                if od.prop.CO_countLabel in self._od_cnt:
                    self._od_cnt[od.prop.CO_countLabel] += 1
                else:
                    self._od_cnt[od.prop.CO_countLabel] = 1

    def _verify_count_label(self, od: ODentry, index_l: int, index_h: int, count_label: str) -> None:
        if index_l <= od.index <= index_h:
            if od.prop.CO_countLabel != count_label:
                od.prop.CO_countLabel = count_label

    def _prepare_var(self, od: ODentry, index_h: str, var_name: str, group: str) -> int:
        data = get_data_properties(
            od.datatype, od.defaultvalue, od.prop.CO_stringLengthMin, index_h
        )
        attr = get_attributes(od, data.c_type_multibyte, data.c_type_string)

        data_ptr = "NULL"
        if data.c_value is not None:
            self._od_storage_t[group].append(f"{data.c_type} x{var_name}{data.c_type_array};")
            self._od_storage[group].append(f".x{var_name} = {data.c_value}")
            data_ptr = f"&{self._odname}_{group}.x{var_name}{data.c_type_array0}"

        self._od_objs_t.append(f"OD_obj_var_t o_{var_name};")
        self._od_objs.append(f"    .o_{var_name} = {{")
        self._od_objs.append(f"        .dataOrig = {data_ptr},")
        self._od_objs.append(f"        .attribute = {attr},")
        self._od_objs.append(f"        .dataLength = {data.length}")
        self._od_objs.append("    },")

        return 1

    def _prepare_arr(self, od: ODentry, index_h: str, var_name: str, group: str) -> int:
        sub_entries_count = len(od.subobjects)
        if sub_entries_count < 2:
            Warnings.add_warning(
                f"Error in 0x{index_h}: ARRAY must have minimum two sub entries, not {sub_entries_count}!",
                WarningClass.WARNING_BUILD,
            )
            return 0

        self._od_arr_size[index_h] = sub_entries_count - 1

        c_value0 = ""
        data_elem = DataProperties()
        attr_elem0 = ""
        attr_elem = ""
        od_storage_values: list[str] = []
        i = 0

        for sub in od.subobjects.values():
            data_type = sub.datatype if sub.datatype != DataType.UNKNOWN else od.datatype
            data = get_data_properties(data_type, sub.defaultvalue, sub.prop.CO_stringLengthMin, index_h)
            attr = get_attributes(sub, data.c_type_multibyte, data.c_type_string)

            if sub.Subindex != i:
                Warnings.add_warning(
                    f"Error in 0x{index_h}: SubIndexes in ARRAY must be in sequence!",
                    WarningClass.WARNING_BUILD,
                )

            if i == 0:
                if data.c_type != "uint8_t" or data.length != 1:
                    Warnings.add_warning(
                        f"Error in 0x{index_h}: Data type in ARRAY in subIndex 0 must be UNSIGNED8, not {sub.datatype}!",
                        WarningClass.WARNING_BUILD,
                    )
                c_value0 = data.c_value or ""
                attr_elem0 = attr
            else:
                if i == 1:
                    data_elem = data
                    attr_elem = attr
                else:
                    if data.c_type != data_elem.c_type or data.length != data_elem.length:
                        Warnings.add_warning(
                            f"Error in 0x{index_h}: Data type of elements in ARRAY must be equal!",
                            WarningClass.WARNING_BUILD,
                        )
                    if (data.c_value is None) != (data_elem.c_value is None):
                        Warnings.add_warning(
                            f"Error in 0x{index_h}: Default value must be defined on all ARRAY elements "
                            "or must be undefined on all ARRAY elements!",
                            WarningClass.WARNING_BUILD,
                        )
                    if attr != attr_elem:
                        Warnings.add_warning(
                            f"Error in 0x{index_h}: Attributes of elements in ARRAY must be equal",
                            WarningClass.WARNING_BUILD,
                        )
                od_storage_values.append(data.c_value or "0")

            i += 1

        data_ptr0 = "NULL"
        data_ptr = "NULL"
        if c_value0:
            self._od_storage_t[group].append(f"uint8_t x{var_name}_sub0;")
            self._od_storage[group].append(f".x{var_name}_sub0 = {c_value0}")
            data_ptr0 = f"&{self._odname}_{group}.x{var_name}_sub0"

        if data_elem.c_value is not None:
            self._od_storage_t[group].append(
                f"{data_elem.c_type} x{var_name}[{self._odname}_CNT_ARR_{index_h}]{data_elem.c_type_array};"
            )
            self._od_storage[group].append(f".x{var_name} = {{{', '.join(od_storage_values)}}}")
            data_ptr = f"&{self._odname}_{group}.x{var_name}[0]{data_elem.c_type_array0}"

        data_element_sizeof = (
            "0"
            if data_elem.c_type == "not specified" and data_elem.length == 0
            else f"sizeof({data_elem.c_type}{data_elem.c_type_array})"
        )

        self._od_objs_t.append(f"OD_obj_array_t o_{var_name};")
        self._od_objs.append(f"    .o_{var_name} = {{")
        self._od_objs.append(f"        .dataOrig0 = {data_ptr0},")
        self._od_objs.append(f"        .dataOrig = {data_ptr},")
        self._od_objs.append(f"        .attribute0 = {attr_elem0},")
        self._od_objs.append(f"        .attribute = {attr_elem},")
        self._od_objs.append(f"        .dataElementLength = {data_elem.length},")
        self._od_objs.append(f"        .dataElementSizeof = {data_element_sizeof}")
        self._od_objs.append("    },")

        return sub_entries_count

    def _prepare_rec(self, od: ODentry, index_h: str, var_name: str, group: str) -> int:
        sub_entries_count = len(od.subobjects)
        if sub_entries_count < 2:
            Warnings.add_warning(
                f"Error in 0x{index_h}: RECORD must have minimum two sub entries, not {sub_entries_count}!",
                WarningClass.WARNING_BUILD,
            )
            return 0

        sub_od_storage_t: list[str] = []
        sub_od_storage: list[str] = []

        self._od_objs_t.append(f"OD_obj_record_t o_{var_name}[{sub_entries_count}];")
        self._od_objs.append(f"    .o_{var_name} = {{")

        for sub in od.subobjects.values():
            data = get_data_properties(
                sub.datatype, sub.defaultvalue, sub.prop.CO_stringLengthMin, index_h
            )
            attr = get_attributes(sub, data.c_type_multibyte, data.c_type_string)

            if sub.Subindex == 0 and (data.c_type != "uint8_t" or data.length != 1):
                Warnings.add_warning(
                    f"Error in 0x{index_h}: Data type in RECORD, subIndex 0 must be UNSIGNED8, not {sub.datatype}!",
                    WarningClass.WARNING_BUILD,
                )

            sub_c_name = make_cname_v4(sub.parameter_name)
            data_ptr = "NULL"
            if data.c_value is not None:
                sub_od_storage_t.append(f"{data.c_type} {sub_c_name}{data.c_type_array};")
                sub_od_storage.append(f".{sub_c_name} = {data.c_value}")
                data_ptr = f"&{self._odname}_{group}.x{var_name}.{sub_c_name}{data.c_type_array0}"

            self._od_objs.append("        {")
            self._od_objs.append(f"            .dataOrig = {data_ptr},")
            self._od_objs.append(f"            .subIndex = {sub.Subindex},")
            self._od_objs.append(f"            .attribute = {attr},")
            self._od_objs.append(f"            .dataLength = {data.length}")
            self._od_objs.append("        },")

        if self._od_objs:
            last = self._od_objs[-1]
            self._od_objs[-1] = last.rstrip(",")

        self._od_objs.append("    },")

        if sub_od_storage_t:
            self._od_storage_t[group].append(
                f"struct {{\n        " + "\n        ".join(sub_od_storage_t) + f"\n    }} x{var_name};"
            )
            self._od_storage[group].append(
                f".x{var_name} = {{\n        " + ",\n        ".join(sub_od_storage) + "\n    }"
            )

        return sub_entries_count

    def _export_h(self, folderpath: str, filename: str) -> None:
        if not filename:
            filename = "OD"
        filepath = os.path.join(folderpath, filename + ".h")
        eds = self._eds

        with open(filepath, "w", newline="\n") as f:
            f.write(
                f"/*******************************************************************************\n"
                f"    CANopen Object Dictionary definition for CANopenNode V4\n"
                f"\n"
                f"    This file was automatically generated by CANopenEditor (Python)\n"
                f"\n"
                f"    https://github.com/CANopenNode/CANopenNode\n"
                f"    https://github.com/CANopenNode/CANopenEditor\n"
                f"\n"
                f"    DON'T EDIT THIS FILE MANUALLY !!!!\n"
                f"********************************************************************************\n"
                f"\n"
                f"    File info:\n"
                f"        File Names:   {filename}.h; {filename}.c\n"
                f"        Project File: {os.path.basename(eds.projectFilename)}\n"
                f"        File Version: {eds.fi.FileVersion}\n"
                f"\n"
                f"        Created:      {eds.fi.CreationDateTime}\n"
                f"        Created By:   {eds.fi.CreatedBy}\n"
                f"        Modified:     {eds.fi.ModificationDateTime}\n"
                f"        Modified By:  {eds.fi.ModifiedBy}\n"
                f"\n"
                f"    Device Info:\n"
                f"        Vendor Name:  {eds.di.VendorName}\n"
                f"        Vendor ID:    {eds.di.VendorNumber}\n"
                f"        Product Name: {eds.di.ProductName}\n"
                f"        Product ID:   {eds.di.ProductNumber}\n"
                f"\n"
                f"        Description:  {eds.fi.Description}\n"
                f"*******************************************************************************/\n"
            )

            f.write(f"\n#ifndef {self._odname}_H\n")
            f.write(f"#define {self._odname}_H\n")
            f.write("/*******************************************************************************\n")
            f.write("    Counters of OD objects\n")
            f.write("*******************************************************************************/\n")

            for label, count in self._od_cnt.items():
                f.write(f"#define {self._odname}_CNT_{label} {count}\n")

            f.write("\n\n/*******************************************************************************\n")
            f.write("    Sizes of OD arrays\n")
            f.write("*******************************************************************************/\n")
            for index_h, size in self._od_arr_size.items():
                f.write(f"#define {self._odname}_CNT_ARR_{index_h} {size}\n")
            if "1016" not in self._od_arr_size:
                f.write(f"#ifndef {self._odname}_CNT_ARR_1016\n")
                f.write(f"#define {self._odname}_CNT_ARR_1016 0\n")
                f.write(f"#endif\n")

            f.write("\n\n/*******************************************************************************\n")
            f.write("    OD data declaration of all groups\n")
            f.write("*******************************************************************************/\n")
            for group in self._od_storage_groups:
                if self._od_storage_t:
                    f.write("typedef struct {\n")
                    f.write(f"    " + "\n    ".join(self._od_storage_t[group]) + "\n")
                    f.write(f"}} {self._odname}_{group}_t;\n\n")

            for group in self._od_storage_groups:
                if self._od_storage_t:
                    f.write(f"#ifndef {self._odname}_ATTR_{group}\n")
                    f.write(f"#define {self._odname}_ATTR_{group}\n")
                    f.write("#endif\n")
                    f.write(f"extern {self._odname}_ATTR_{group} {self._odname}_{group}_t {self._odname}_{group};\n\n")

            f.write(f"#ifndef {self._odname}_ATTR_OD\n")
            f.write(f"#define {self._odname}_ATTR_OD\n")
            f.write("#endif\n")
            f.write(f"extern {self._odname}_ATTR_OD OD_t *{self._odname};\n")

            f.write("\n\n/*******************************************************************************\n")
            f.write("    Object dictionary entries - shortcuts\n")
            f.write("*******************************************************************************/\n")
            f.write("\n".join(self._od_defines))
            f.write("\n")
            for idx_h in ["1016"]:
                if f"_ENTRY_H{idx_h}" not in "".join(self._od_defines):
                    f.write(f"#ifndef {self._odname}_ENTRY_H{idx_h}\n")
                    f.write(f"#define {self._odname}_ENTRY_H{idx_h} NULL\n")
                    f.write(f"#endif\n")

            f.write("\n\n/*******************************************************************************\n")
            f.write("    Object dictionary entries - shortcuts with names\n")
            f.write("*******************************************************************************/\n")
            f.write("\n".join(self._od_defines_long))

            f.write(f"\n\n/*******************************************************************************\n")
            f.write("    OD config structure\n")
            f.write("*******************************************************************************/\n")
            f.write("#ifdef CO_MULTIPLE_OD\n")
            f.write(f"#define {self._odname}_INIT_CONFIG(config) {{\\\n")

            def _entry_or_null(idx: int) -> str:
                if idx in self._eds.ods:
                    return f"{self._odname}_ENTRY_H{idx:04X}"
                return "NULL"

            def _cnt_or_zero(label: str) -> str:
                if label in self._od_cnt:
                    return f"{self._odname}_CNT_{label}"
                return "0"

            def _cnt_arr_or_zero(idx: int) -> str:
                index_h = f"{idx:04X}"
                if index_h in self._od_arr_size:
                    return f"{self._odname}_CNT_ARR_{index_h}"
                return "0"

            f.write(f"    (config).CNT_NMT = {_cnt_or_zero('NMT')};\\\n")
            f.write(f"    (config).ENTRY_H1017 = {_entry_or_null(0x1017)};\\\n")
            f.write(f"    (config).CNT_HB_CONS = {_cnt_or_zero('HB_CONS')};\\\n")
            f.write(f"    (config).CNT_ARR_1016 = {_cnt_arr_or_zero(0x1016)};\\\n")
            f.write(f"    (config).ENTRY_H1016 = {_entry_or_null(0x1016)};\\\n")
            f.write(f"    (config).CNT_EM = {_cnt_or_zero('EM')};\\\n")
            f.write(f"    (config).ENTRY_H1001 = {_entry_or_null(0x1001)};\\\n")
            f.write(f"    (config).ENTRY_H1014 = {_entry_or_null(0x1014)};\\\n")
            f.write(f"    (config).ENTRY_H1015 = {_entry_or_null(0x1015)};\\\n")
            f.write(f"    (config).CNT_ARR_1003 = {_cnt_arr_or_zero(0x1003)};\\\n")
            f.write(f"    (config).ENTRY_H1003 = {_entry_or_null(0x1003)};\\\n")
            f.write(f"    (config).CNT_SDO_SRV = {_cnt_or_zero('SDO_SRV')};\\\n")
            f.write(f"    (config).ENTRY_H1200 = {_entry_or_null(0x1200)};\\\n")
            f.write(f"    (config).CNT_SDO_CLI = {_cnt_or_zero('SDO_CLI')};\\\n")
            f.write(f"    (config).ENTRY_H1280 = {_entry_or_null(0x1280)};\\\n")
            f.write(f"    (config).CNT_TIME = {_cnt_or_zero('TIME')};\\\n")
            f.write(f"    (config).ENTRY_H1012 = {_entry_or_null(0x1012)};\\\n")
            f.write(f"    (config).CNT_SYNC = {_cnt_or_zero('SYNC')};\\\n")
            f.write(f"    (config).ENTRY_H1005 = {_entry_or_null(0x1005)};\\\n")
            f.write(f"    (config).ENTRY_H1006 = {_entry_or_null(0x1006)};\\\n")
            f.write(f"    (config).ENTRY_H1007 = {_entry_or_null(0x1007)};\\\n")
            f.write(f"    (config).ENTRY_H1019 = {_entry_or_null(0x1019)};\\\n")
            f.write(f"    (config).CNT_RPDO = {_cnt_or_zero('RPDO')};\\\n")
            f.write(f"    (config).ENTRY_H1400 = {_entry_or_null(0x1400)};\\\n")
            f.write(f"    (config).ENTRY_H1600 = {_entry_or_null(0x1600)};\\\n")
            f.write(f"    (config).CNT_TPDO = {_cnt_or_zero('TPDO')};\\\n")
            f.write(f"    (config).ENTRY_H1800 = {_entry_or_null(0x1800)};\\\n")
            f.write(f"    (config).ENTRY_H1A00 = {_entry_or_null(0x1A00)};\\\n")
            f.write(f"    (config).CNT_LEDS = 0;\\\n")
            f.write(f"    (config).CNT_GFC = {_cnt_or_zero('GFC')};\\\n")
            f.write(f"    (config).ENTRY_H1300 = {_entry_or_null(0x1300)};\\\n")
            f.write(f"    (config).CNT_SRDO = {_cnt_or_zero('SRDO')};\\\n")
            f.write(f"    (config).ENTRY_H1301 = {_entry_or_null(0x1301)};\\\n")
            f.write(f"    (config).ENTRY_H1381 = {_entry_or_null(0x1381)};\\\n")
            f.write(f"    (config).ENTRY_H13FE = {_entry_or_null(0x13FE)};\\\n")
            f.write(f"    (config).ENTRY_H13FF = {_entry_or_null(0x13FF)};\\\n")
            f.write(f"    (config).CNT_LSS_SLV = 0;\\\n")
            f.write(f"    (config).CNT_LSS_MST = 0;\\\n")
            f.write(f"    (config).CNT_GTWA = 0;\\\n")
            f.write(f"    (config).CNT_TRACE = 0;\\\n")
            f.write("}\n")
            f.write("#endif\n")

            f.write(f"\n#endif /* {self._odname}_H */\n")

    def _export_c(self, folderpath: str, filename: str) -> None:
        if not filename:
            filename = "OD"
        filepath = os.path.join(folderpath, filename + ".c")

        with open(filepath, "w", newline="\n") as f:
            f.write(
                f"/*******************************************************************************\n"
                f"    CANopen Object Dictionary definition for CANopenNode V4\n"
                f"\n"
                f"    This file was automatically generated by CANopenEditor (Python)\n"
                f"\n"
                f"    https://github.com/CANopenNode/CANopenNode\n"
                f"    https://github.com/CANopenNode/CANopenEditor\n"
                f"\n"
                f"    DON'T EDIT THIS FILE MANUALLY, UNLESS YOU KNOW WHAT YOU ARE DOING !!!!\n"
                f"*******************************************************************************/\n"
                f"\n"
                f"#define OD_DEFINITION\n"
                f'#include "301/CO_ODinterface.h"\n'
                f'#include "{filename}.h"\n'
                f"\n"
                f"#if CO_VERSION_MAJOR < 4\n"
                f"#error This Object dictionary is compatible with CANopenNode V4.0 and above!\n"
                f"#endif\n"
            )

            f.write("\n/*******************************************************************************\n")
            f.write("    OD data initialization of all groups\n")
            f.write("*******************************************************************************/\n")
            for group in self._od_storage_groups:
                if self._od_storage:
                    f.write(f"{self._odname}_ATTR_{group} {self._odname}_{group}_t {self._odname}_{group} = {{\n")
                    f.write(f"    " + ",\n    ".join(self._od_storage[group]) + "\n")
                    f.write("};\n\n")

            if self._od_objs:
                last = self._od_objs[-1]
                self._od_objs[-1] = last.rstrip(",")

            f.write("\n/*******************************************************************************\n")
            f.write("    All OD objects (constant definitions)\n")
            f.write("*******************************************************************************/\n")
            f.write("typedef struct {\n")
            f.write(f"    " + "\n    ".join(self._od_objs_t) + "\n")
            f.write(f"}} {self._odname}Objs_t;\n\n")
            f.write(f"static CO_PROGMEM {self._odname}Objs_t {self._odname}Objs = {{\n")
            f.write("\n".join(self._od_objs))
            f.write("\n};\n")

            f.write(f"\n/*******************************************************************************\n")
            f.write("    Object dictionary\n")
            f.write("*******************************************************************************/\n")
            f.write(f"static {self._odname}_ATTR_OD OD_entry_t {self._odname}List[] = {{\n")
            f.write(f"    " + ",\n    ".join(self._od_list) + ",\n")
            f.write("    {0x0000, 0x00, 0, NULL, NULL}\n")
            f.write("};\n\n")
            f.write(f"static OD_t _{self._odname} = {{\n")
            f.write(f"    (sizeof({self._odname}List) / sizeof({self._odname}List[0])) - 1,\n")
            f.write(f"    &{self._odname}List[0]\n")
            f.write("};\n\n")
            f.write(f"OD_t *{self._odname} = &_{self._odname};\n")
