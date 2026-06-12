"""EDS/DCF 文件解析器和生成器，对应 C# CanOpenEDS.cs"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional

from ..models.datatypes import AccessType, DataType, ObjectType, PDOMappingType
from ..models.eds import EDS
from ..models.info_section import (
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
    ModuleComments,
    ModuleInfo,
    ModuleSubExtends,
    MxFixedObjects,
    OptionalObjects,
    SupportedModules,
    TypeDefinitions,
)
from ..models.od_entry import ODentry, _get_base
from ..models.warnings import Warnings


class EDSParser:
    """EDS/DCF 文件解析器"""

    def __init__(self, eds: EDS):
        self.eds = eds

    def loadfile(self, filename: str) -> None:
        self.eds.projectFilename = filename
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".eds":
            self.eds.edsfilename = filename
        elif ext == ".dcf":
            self.eds.dcffilename = filename

        with open(filename, "r", encoding="utf-8", errors="replace") as f:
            for lineno, line in enumerate(f, 1):
                self._parseline(line, lineno)

        self._parse_all_sections()

    def _parseline(self, linex: str, lineno: int) -> None:
        if not linex:
            return

        line = linex.strip()
        if not line:
            return

        custom_extension = False
        raw_line = line
        if line.startswith(";"):
            custom_extension = True
            line = line.lstrip(";").strip()
            if not line:
                return

        section_match = re.match(r"^\[([a-zA-Z0-9]+)\]", line)
        if section_match:
            section_name = section_match.group(1)
            if section_name not in self.eds.eds:
                self.eds.eds[section_name] = {}
                self.eds.sectionlinenos[section_name] = lineno
            else:
                Warnings.add_warning(f"EDS Error on Line {lineno}: Duplicate section [{section_name}]")
            self.eds.sectionname = section_name
            return

        kv_match = re.match(r"^([a-zA-Z0-9_]+)[ ]*=[ ]*(.*)", line)
        if kv_match:
            key = kv_match.group(1)
            value = kv_match.group(2).rstrip(" \t\n\r")

            section_name = self.eds.sectionname
            if section_name not in self.eds.eds:
                self.eds.eds[section_name] = {}

            if not custom_extension:
                if key in self.eds.eds[section_name]:
                    Warnings.add_warning(
                        f'EDS Error on Line {lineno}: Duplicate key "{key}" value "{value}" in section [{section_name}]'
                    )
                else:
                    self.eds.eds[section_name][key] = value
            else:
                if key in ("StorageLocation", "TPDODetectCos"):
                    if key in self.eds.eds[section_name]:
                        Warnings.add_warning(
                            f'EDS Error on Line {lineno}: Duplicate custom key "{key}" value "{value}" in section [{section_name}]'
                        )
                    else:
                        self.eds.eds[section_name][key] = value

    def _parse_all_sections(self) -> None:
        if "DeviceInfo" in self.eds.eds:
            self.eds.di = DeviceInfo()
            self.eds.di.parse(self.eds.eds["DeviceInfo"])

        for section_name, section_data in self.eds.eds.items():
            try:
                self._parse_eds_entry(section_name, section_data)
            except Exception:
                Warnings.add_warning(f"Error parsing section [{section_name}]")

        if "FileInfo" in self.eds.eds:
            self.eds.fi = FileInfo()
            self.eds.fi.parse(self.eds.eds["FileInfo"])
            self._parse_fileinfo_datetime()

        if "DummyUsage" in self.eds.eds:
            self.eds.du = DummyUsage()
            self.eds.du.parse(self.eds.eds["DummyUsage"])

        self.eds.md = MandatoryObjects()
        if "MandatoryObjects" in self.eds.eds:
            self._parse_supported_objects(self.eds.md, self.eds.eds["MandatoryObjects"])

        self.eds.oo = OptionalObjects()
        if "OptionalObjects" in self.eds.eds:
            self._parse_supported_objects(self.eds.oo, self.eds.eds["OptionalObjects"])

        self.eds.mo = ManufacturerObjects()
        if "ManufacturerObjects" in self.eds.eds:
            self._parse_supported_objects(self.eds.mo, self.eds.eds["ManufacturerObjects"])

        self.eds.td = TypeDefinitions()
        if "TypeDefinitions" in self.eds.eds:
            self._parse_supported_objects(self.eds.td, self.eds.eds["TypeDefinitions"])

        self.eds.dc = DeviceCommissioning()
        str_section = ""
        if "DeviceCommissioning" in self.eds.eds:
            str_section = "DeviceCommissioning"
        elif "DeviceComissioning" in self.eds.eds:
            str_section = "DeviceComissioning"
        if str_section:
            self.eds.dc = DeviceCommissioning()
            self.eds.dc.parse(self.eds.eds[str_section])
            self.eds.edsfilename = self.eds.fi.LastEDS

        self.eds.c = Comments()
        if "Comments" in self.eds.eds:
            self._parse_comments(self.eds.c, self.eds.eds["Comments"])

        if "SupportedModules" in self.eds.eds:
            self.eds.sm = SupportedModules()
            self.eds.sm.parse(self.eds.eds["SupportedModules"])
            self._parse_modules()

            if self.eds.di.CompactPDO != 0:
                for idx in range(0x1400, 0x1600):
                    self._apply_compact_pdo(idx)
                for idx in range(0x1800, 0x1A00):
                    self._apply_compact_pdo(idx)

            self._apply_implicit_pdo()

    def _parse_fileinfo_datetime(self) -> None:
        fi_data = self.eds.eds.get("FileInfo", {})
        try:
            if "CreationTime" in fi_data and "CreationDate" in fi_data:
                self.eds.fi.CreationDateTime = _format_csharp_datetime(
                    fi_data["CreationDate"].strip(), fi_data["CreationTime"].strip()
                )
            if "ModificationTime" in fi_data and "ModificationDate" in fi_data:
                self.eds.fi.ModificationDateTime = _format_csharp_datetime(
                    fi_data["ModificationDate"].strip(), fi_data["ModificationTime"].strip()
                )
        except (ValueError, KeyError):
            pass

    def _parse_eds_entry(self, section: str, data: dict[str, str]) -> None:
        pat = r"^(M[0-9a-fA-F]+(Fixed|SubExt))?([a-fA-F0-9]+)(sub)?([0-9a-fA-F]*)$"
        m = re.match(pat, section, re.IGNORECASE)
        if not m:
            return

        target = self.eds.ods

        mod_match = re.match(r"^M([0-9a-fA-F]+)(Fixed|SubExt)([0-9a-fA-F]+)", section, re.IGNORECASE)
        if mod_match:
            try:
                mod_index = int(mod_match.group(1))
            except ValueError:
                mod_index = 0
            if mod_index not in self.eds.modules:
                self.eds.modules[mod_index] = Module(moduleindex=mod_index)
            if mod_match.group(2).lower() == "subext":
                target = self.eds.modules[mod_index].modulesubext
            else:
                target = self.eds.modules[mod_index].modulefixedobjects

        od_index = 0
        try:
            od_index = int(m.group(3), 16)
        except ValueError:
            return

        od = ODentry(index=od_index)

        if "ParameterName" not in data:
            return
        od.parameter_name = data["ParameterName"]

        if "ObjectType" in data:
            try:
                od.objecttype = ObjectType(int(data["ObjectType"], _get_base(data["ObjectType"])))
            except (ValueError, KeyError):
                od.objecttype = ObjectType.VAR
        else:
            od.objecttype = ObjectType.VAR

        if "CompactSubObj" in data:
            try:
                od.CompactSubObj = int(data["CompactSubObj"], _get_base(data["CompactSubObj"]))
            except ValueError:
                pass

        if "ObjFlags" in data:
            try:
                od.ObjFlags = int(data["ObjFlags"], _get_base(data["ObjFlags"]))
            except ValueError:
                od.ObjFlags = 0
        else:
            od.ObjFlags = 0

        if "StorageLocation" in data:
            od.prop.CO_storageGroup = data["StorageLocation"]

        if "TPDODetectCos" in data:
            val = data["TPDODetectCos"].lower()
            od.prop.CO_flagsPDO = val in ("1", "true")

        if "Count" in data:
            count_val = data["Count"]
            count_match = re.match(r"\s*([0-9a-fA-F]+)\s*;\s*([0-9a-fA-F]+)", count_val, re.IGNORECASE)
            if count_match:
                try:
                    od.count = int(count_match.group(2), _get_base(count_match.group(2)))
                except ValueError:
                    pass
            else:
                try:
                    od.count = int(count_val, _get_base(count_val))
                except ValueError:
                    pass

        if "ObjExtend" in data:
            try:
                od.ObjExtend = int(data["ObjExtend"])
            except ValueError:
                pass

        if od.objecttype == ObjectType.VAR:
            if "ParameterValue" in data:
                od.actualvalue = data["ParameterValue"]
            if "HighLimit" in data:
                od.HighLimit = data["HighLimit"]
            if "LowLimit" in data:
                od.LowLimit = data["LowLimit"]
            if "Denotation" in data:
                od.denotation = data["Denotation"]

            sub_index = m.group(5)
            if sub_index:
                try:
                    sub_idx = int(sub_index, 16)
                    if od_index in target:
                        od.parent = target[od_index]
                        target[od_index].subobjects[sub_idx] = od
                except ValueError:
                    pass

            if "DataType" in data:
                try:
                    od.datatype = DataType(int(data["DataType"], _get_base(data["DataType"])))
                except ValueError:
                    od.datatype = DataType.UNKNOWN

            if "AccessType" in data:
                access_str = data["AccessType"].lower()
                try:
                    od.accesstype = AccessType[access_str.upper()]
                    if access_str == "const":
                        od.accesstype = AccessType.CONST
                except (KeyError, ValueError):
                    od.accesstype = AccessType.UNKNOWN

            if "DefaultValue" in data:
                od.defaultvalue = data["DefaultValue"]

            od.PDOtype = PDOMappingType.NO
            if "PDOMapping" in data:
                try:
                    pdo_val = int(data["PDOMapping"], _get_base(data["PDOMapping"]))
                    if pdo_val == 1:
                        od.PDOtype = PDOMappingType.OPTIONAL
                except ValueError:
                    pass

        elif od.objecttype in (ObjectType.RECORD, ObjectType.ARRAY, ObjectType.DEFSTRUCT):
            if od.CompactSubObj != 0:
                if "DataType" in data:
                    try:
                        od.datatype = DataType(int(data["DataType"], _get_base(data["DataType"])))
                    except ValueError:
                        pass
                if "AccessType" in data:
                    try:
                        od.accesstype = AccessType[data["AccessType"].upper()]
                    except (KeyError, ValueError):
                        pass

                if od.CompactSubObj >= 0xFE:
                    od.CompactSubObj = 0xFE

                subi = ODentry(
                    parameter_name="NrOfObjects",
                    datatype=DataType.UNSIGNED8,
                    defaultvalue=f"0x{od.CompactSubObj:02x}",
                    accesstype=AccessType.RO,
                    pdo_type=PDOMappingType.NO,
                    parent=od,
                )
                od.subobjects[0] = subi

                for x in range(1, od.CompactSubObj + 1):
                    pname = f"{od.parameter_name}{x:02x}"
                    sub = ODentry(
                        parameter_name=pname,
                        datatype=od.datatype,
                        defaultvalue=od.defaultvalue,
                        accesstype=od.accesstype,
                        pdo_type=od.PDOtype,
                        parent=od,
                    )
                    if "HighLimit" in data:
                        sub.HighLimit = data["HighLimit"]
                    if "LowLimit" in data:
                        sub.LowLimit = data["LowLimit"]
                    od.subobjects[x] = sub
            else:
                if "SubNumber" not in data:
                    pass

        elif od.objecttype == ObjectType.DOMAIN:
            od.datatype = DataType.DOMAIN
            od.accesstype = AccessType.RW
            if "DefaultValue" in data:
                od.defaultvalue = data["DefaultValue"]

        if not m.group(5):
            target[od_index] = od

    def _parse_supported_objects(self, obj, data: dict[str, str]) -> None:
        obj.objectlist = {}
        for key, value in data.items():
            if key.lower() in ("supportedobjects", "nrofentries"):
                continue
            try:
                count = int(key, _get_base(key))
                target = int(value, _get_base(value))
                obj.objectlist[count] = target
            except ValueError:
                pass

    def _parse_comments(self, comments: Comments, data: dict[str, str]) -> None:
        comments.comments = []
        for key, value in data.items():
            if key == "Lines":
                continue
            comments.comments.append(value)

    def _parse_modules(self) -> None:
        for section_name in self.eds.eds:
            m = re.match(r"M([0-9]+)ModuleInfo", section_name, re.IGNORECASE)
            if m:
                mod_index = int(m.group(1))
                if mod_index not in self.eds.modules:
                    self.eds.modules[mod_index] = Module(moduleindex=mod_index)
                mi = ModuleInfo(_moduleindex=mod_index)
                mi.parse(self.eds.eds[section_name])
                self.eds.modules[mod_index].mi = mi

            m = re.match(r"M([0-9]+)Comments", section_name, re.IGNORECASE)
            if m:
                mod_index = int(m.group(1))
                if mod_index not in self.eds.modules:
                    self.eds.modules[mod_index] = Module(moduleindex=mod_index)
                mc = ModuleComments(_moduleindex=mod_index)
                self._parse_comments(mc, self.eds.eds[section_name])
                self.eds.modules[mod_index].mc = mc

            m = re.match(r"M([0-9]+)SubExtends", section_name, re.IGNORECASE)
            if m:
                mod_index = int(m.group(1))
                if mod_index not in self.eds.modules:
                    self.eds.modules[mod_index] = Module(moduleindex=mod_index)
                mse = ModuleSubExtends(_moduleindex=mod_index)
                self._parse_supported_objects(mse, self.eds.eds[section_name])
                self.eds.modules[mod_index].mse = mse

            m = re.match(r"M([0-9]+)FixedObjects", section_name, re.IGNORECASE)
            if m:
                mod_index = int(m.group(1))
                if mod_index not in self.eds.modules:
                    self.eds.modules[mod_index] = Module(moduleindex=mod_index)
                mxf = MxFixedObjects(_moduleindex=mod_index)
                self._parse_supported_objects(mxf, self.eds.eds[section_name])
                self.eds.modules[mod_index].mxfo = mxf

        if "ConnectedModules" in self.eds.eds:
            self.eds.cm = ConnectedModules()
            self._parse_supported_objects(self.eds.cm, self.eds.eds["ConnectedModules"])
            for k, v in self.eds.cm.objectlist.items():
                self.eds.cm.connectedmodulelist[v] = k

    def _apply_compact_pdo(self, index: int) -> None:
        if index not in self.eds.ods:
            return
        od = self.eds.ods[index]

        if not od.Containssubindex(1) and (self.eds.di.CompactPDO & 0x01) == 0:
            if index < 0x1800:
                cob_default = "$NODEID+0x200"
            else:
                cob_default = "$NODEID+0x180"
            sub = ODentry(
                parameter_name="COB-ID", datatype=DataType.UNSIGNED32,
                defaultvalue=cob_default, accesstype=AccessType.RW,
                pdo_type=PDOMappingType.NO, parent=od,
            )
            od.subobjects[1] = sub

        if not od.Containssubindex(2) and (self.eds.di.CompactPDO & 0x02) == 0:
            sub = ODentry(
                parameter_name="Type", datatype=DataType.UNSIGNED8,
                defaultvalue="0xff", accesstype=AccessType.RW,
                pdo_type=PDOMappingType.NO, parent=od,
            )
            od.subobjects[2] = sub

        if not od.Containssubindex(3) and (self.eds.di.CompactPDO & 0x04) == 0:
            sub = ODentry(
                parameter_name="Inhibit time", datatype=DataType.UNSIGNED16,
                defaultvalue="0", accesstype=AccessType.RW,
                pdo_type=PDOMappingType.NO, parent=od,
            )
            od.subobjects[3] = sub

        if index < 0x1800:
            return

        if not od.Containssubindex(4) and (self.eds.di.CompactPDO & 0x08) == 0:
            sub = ODentry(
                parameter_name="Compatibility entry", datatype=DataType.UNSIGNED8,
                defaultvalue="0", accesstype=AccessType.RO,
                pdo_type=PDOMappingType.NO, parent=od,
            )
            od.subobjects[4] = sub

        if not od.Containssubindex(5) and (self.eds.di.CompactPDO & 0x10) == 0:
            sub = ODentry(
                parameter_name="Event Timer", datatype=DataType.UNSIGNED16,
                defaultvalue="0", accesstype=AccessType.RW,
                pdo_type=PDOMappingType.NO, parent=od,
            )
            od.subobjects[5] = sub

    def _apply_implicit_pdo(self) -> None:
        total_rx = self.eds.di.NrOfRXPDO
        total_tx = self.eds.di.NrOfTXPDO
        self.eds.UpdatePDOcount()
        explicit_rx = self.eds.di.NrOfRXPDO
        explicit_tx = self.eds.di.NrOfTXPDO
        implicit_rx = total_rx - explicit_rx
        implicit_tx = total_tx - explicit_tx

        for idx in range(0x1400, 0x1600):
            if implicit_rx <= 0:
                break
            if idx not in self.eds.ods:
                self._create_rxpdo(idx)
                implicit_rx -= 1

        for idx in range(0x1800, 0x1A00):
            if implicit_tx <= 0:
                break
            if idx not in self.eds.ods:
                self._create_txpdo(idx)
                implicit_tx -= 1

        self.eds.UpdatePDOcount()

    def _create_rxpdo(self, index: int) -> bool:
        return self._create_pdo(rx=True, index=index)

    def _create_txpdo(self, index: int) -> bool:
        return self._create_pdo(rx=False, index=index)

    def _create_pdo(self, rx: bool, index: int) -> bool:
        if rx and not (0x1400 <= index < 0x1600):
            return False
        if not rx and not (0x1800 <= index < 0x1A00):
            return False
        if index in self.eds.ods:
            return False
        if (index + 0x200) in self.eds.ods:
            return False

        if rx:
            com_name = "RPDO communication parameter"
            map_name = "RPDO mapping parameter"
            cob_default = "$NODEID+0x200"
            max_sub = "2"
        else:
            com_name = "TPDO communication parameter"
            map_name = "TPDO mapping parameter"
            cob_default = "$NODEID+0x180"
            max_sub = "6"

        od_comparam = ODentry(parameter_name=com_name, index=index, objecttype=ObjectType.RECORD)
        od_comparam.prop.CO_storageGroup = "ROM"
        od_comparam.accesstype = AccessType.RO
        od_comparam.PDOtype = PDOMappingType.NO

        sub = ODentry(parameter_name="max sub-index", datatype=DataType.UNSIGNED8,
                       defaultvalue=max_sub, accesstype=AccessType.RO, parent=od_comparam)
        od_comparam.subobjects[0] = sub

        sub = ODentry(parameter_name="COB-ID used by " + ("RPDO" if rx else "TPDO"),
                       datatype=DataType.UNSIGNED32, defaultvalue=cob_default,
                       accesstype=AccessType.RW, parent=od_comparam)
        od_comparam.subobjects[1] = sub

        sub = ODentry(parameter_name="transmission type", datatype=DataType.UNSIGNED8,
                       defaultvalue="254", accesstype=AccessType.RW, parent=od_comparam)
        od_comparam.subobjects[2] = sub

        if not rx:
            sub = ODentry(parameter_name="inhibit time", datatype=DataType.UNSIGNED16,
                           defaultvalue="0", accesstype=AccessType.RW, parent=od_comparam)
            od_comparam.subobjects[3] = sub
            sub = ODentry(parameter_name="event timer", datatype=DataType.UNSIGNED16,
                           defaultvalue="0", accesstype=AccessType.RW, parent=od_comparam)
            od_comparam.subobjects[5] = sub
            sub = ODentry(parameter_name="SYNC start value", datatype=DataType.UNSIGNED8,
                           defaultvalue="0", accesstype=AccessType.RW, parent=od_comparam)
            od_comparam.subobjects[6] = sub

        map_idx = index + 0x200
        od_mapping = ODentry(parameter_name=map_name, index=map_idx, objecttype=ObjectType.RECORD)
        od_mapping.prop.CO_storageGroup = "ROM"
        od_mapping.accesstype = AccessType.RW
        od_mapping.PDOtype = PDOMappingType.NO

        sub = ODentry(parameter_name="Number of mapped objects", datatype=DataType.UNSIGNED8,
                       defaultvalue="0", accesstype=AccessType.RO, parent=od_mapping)
        od_mapping.subobjects[0] = sub

        for p in range(1, 9):
            sub = ODentry(parameter_name=f"mapped object {p}", datatype=DataType.UNSIGNED32,
                           defaultvalue="0x00000000", accesstype=AccessType.RO, parent=od_mapping)
            od_mapping.subobjects[p] = sub

        self.eds.ods[index] = od_comparam
        self.eds.ods[map_idx] = od_mapping
        return True


class EDSWriter:
    """EDS/DCF 文件生成器"""

    def __init__(self, eds: EDS):
        self.eds = eds

    def savefile(self, filename: str, ft: Filetype = Filetype.FILE_EDS) -> None:
        if ft == Filetype.FILE_EDS:
            self.eds.edsfilename = filename
        elif ft == Filetype.FILE_DCF:
            self.eds.dcffilename = filename
            self.eds.fi.LastEDS = self.eds.edsfilename

        self.eds.UpdatePDOcount()

        self.eds.fi.FileName = os.path.basename(filename)
        self.eds.fi.EDSVersion = "4.0"
        self.eds.fi.EDSVersionMajor = 4
        self.eds.fi.EDSVersionMinor = 0

        lines: list[str] = []

        self._write_info_section(lines, self.eds.fi, ft)
        self._write_info_section(lines, self.eds.di, ft)
        self._write_info_section(lines, self.eds.du, ft)
        self._write_comments(lines, self.eds.c)

        if ft == Filetype.FILE_DCF:
            self._write_info_section(lines, self.eds.dc, ft)

        md_list, oo_list, mo_list = self._regenerate_object_lists()

        self._write_supported_objects(lines, self.eds.md, md_list)
        self._write_od_entries(lines, md_list, ft)
        self._write_supported_objects(lines, self.eds.oo, oo_list)
        self._write_od_entries(lines, oo_list, ft)
        self._write_supported_objects(lines, self.eds.mo, mo_list)
        self._write_od_entries(lines, mo_list, ft)

        if self.eds.sm.NrOfEntries > 0:
            self._write_modules(lines, ft)

        if ft == Filetype.FILE_DCF and self.eds.cm.NrOfEntries > 0:
            self._write_connected_modules(lines)

        with open(filename, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))

    def _regenerate_object_lists(self) -> tuple[list[int], list[int], list[int]]:
        md_list: list[int] = []
        oo_list: list[int] = []
        mo_list: list[int] = []

        for idx in sorted(self.eds.ods.keys()):
            od = self.eds.ods[idx]
            if od.prop.CO_disabled:
                continue
            if idx in (0x1000, 0x1001, 0x1018):
                md_list.append(idx)
            elif 0x2000 <= idx < 0x6000:
                mo_list.append(idx)
            else:
                oo_list.append(idx)

        self.eds.md.objectlist = {i + 1: v for i, v in enumerate(md_list)}
        self.eds.oo.objectlist = {i + 1: v for i, v in enumerate(oo_list)}
        self.eds.mo.objectlist = {i + 1: v for i, v in enumerate(mo_list)}

        return md_list, oo_list, mo_list

    def _write_info_section(self, lines: list[str], section, ft: Filetype) -> None:
        lines.append(f"[{section.edssection}]")
        eds_fields = _get_eds_fields(section, ft)
        for name, value in eds_fields:
            if isinstance(value, bool):
                lines.append(f"{name}={1 if value else 0}")
            else:
                lines.append(f"{name}={value}")
        lines.append("")

    def _write_supported_objects(self, lines: list[str], obj, index_list: list[int]) -> None:
        lines.append(f"[{obj.edssection}]")
        lines.append(f"{obj.countmsg}={len(index_list)}")
        for i, idx in enumerate(index_list, 1):
            lines.append(f"{i}=0x{idx:04X}")
        lines.append("")

    def _write_od_entries(self, lines: list[str], index_list: list[int], ft: Filetype) -> None:
        for idx in index_list:
            if idx not in self.eds.ods:
                continue
            od = self.eds.ods[idx]
            self._write_od_entry(lines, od, ft)
            for sub_idx in sorted(od.subobjects.keys()):
                self._write_od_entry(lines, od.subobjects[sub_idx], ft)

    def _write_od_entry(self, lines: list[str], od: ODentry, ft: Filetype,
                        odt: str = "NORMAL", module: int = 0) -> None:
        fixed_header = ""
        if odt == "FIXED":
            fixed_header = f"M{module}Fixed"
        elif odt == "SUBEXT":
            fixed_header = f"M{module}SubExt"

        if od.parent is not None:
            lines.append(f"[{fixed_header}{od.index:X}sub{od.Subindex:X}]")
        else:
            lines.append(f"[{fixed_header}{od.index:X}]")

        lines.append(f"ParameterName={od.parameter_name}")

        if ft == Filetype.FILE_DCF:
            lines.append(f"Denotation={od.denotation}")

        lines.append(f"ObjectType=0x{od.objecttype:X}")
        lines.append(f";StorageLocation={od.prop.CO_storageGroup}")

        if od.objecttype in (ObjectType.ARRAY, ObjectType.RECORD):
            lines.append(f"SubNumber=0x{od.Nosubindexes:X}")

        if od.objecttype == ObjectType.VAR:
            dt = od.datatype
            if dt == DataType.UNKNOWN and od.parent is not None:
                dt = od.parent.datatype
            lines.append(f"DataType=0x{dt:04X}")
            lines.append(f"AccessType={od.accesstype.name.lower()}")

            if od.HighLimit:
                lines.append(f"HighLimit={od.format_octet_string(od.HighLimit)}")
            if od.LowLimit:
                lines.append(f"LowLimit={od.format_octet_string(od.LowLimit)}")

            lines.append(f"DefaultValue={od.format_octet_string(od.defaultvalue)}")

            if ft == Filetype.FILE_DCF:
                lines.append(f"ParameterValue={od.format_octet_string(od.actualvalue)}")

            lines.append(f"PDOMapping={1 if od.PDOMapping else 0}")

            if od.prop.CO_flagsPDO:
                lines.append(";TPDODetectCos=1")

        if odt == "SUBEXT":
            lines.append(f"Count={od.count}")
            lines.append(f"ObjExtend={od.ObjExtend}")

        if od.ObjFlags != 0:
            lines.append(f"ObjFlags={od.ObjFlags}")

        lines.append("")

    def _write_comments(self, lines: list[str], comments: Comments) -> None:
        lines.append(f"[{comments.edssection}]")
        lines.append(f"Lines={len(comments.comments)}")
        for i, s in enumerate(comments.comments, 1):
            lines.append(f"Line{i}={s}")
        lines.append("")

    def _write_modules(self, lines: list[str], ft: Filetype) -> None:
        self._write_info_section(lines, self.eds.sm, ft)

        for mod_id in sorted(self.eds.modules.keys()):
            mod = self.eds.modules[mod_id]
            if mod.mi:
                self._write_info_section(lines, mod.mi, ft)
            if mod.mc:
                self._write_comments(lines, mod.mc)
            if mod.mse:
                self._write_supported_objects(lines, mod.mse, list(mod.modulesubext.keys()))

            for od_idx in sorted(mod.modulesubext.keys()):
                od = mod.modulesubext[od_idx]
                self._write_od_entry(lines, od, ft, odt="SUBEXT", module=mod_id)

            if mod.mxfo:
                self._write_supported_objects(lines, mod.mxfo, list(mod.modulefixedobjects.keys()))

            for od_idx in sorted(mod.modulefixedobjects.keys()):
                od = mod.modulefixedobjects[od_idx]
                self._write_od_entry(lines, od, ft, odt="SUBEXT", module=mod_id)
                for sub_idx in sorted(od.subobjects.keys()):
                    self._write_od_entry(lines, od.subobjects[sub_idx], ft, odt="FIXED", module=mod_id)

    def _write_connected_modules(self, lines: list[str]) -> None:
        lines.append(f"[{self.eds.cm.edssection}]")
        lines.append(f"{self.eds.cm.countmsg}={self.eds.cm.NrOfEntries}")
        for i, (k, v) in enumerate(self.eds.cm.connectedmodulelist.items(), 1):
            lines.append(f"{i}=0x{k:04X}")
        lines.append("")


def _get_eds_fields(section, ft: Filetype) -> list[tuple[str, object]]:
    eds_fields = []
    dcf_only_fields = set()

    if isinstance(section, DeviceCommissioning):
        dcf_only_fields = set()
        for name in ["NodeID", "NodeName", "Baudrate", "NetNumber", "NetworkName", "CANopenManager", "LSS_SerialNumber"]:
            dcf_only_fields.add(name)

    for attr_name in dir(section):
        if attr_name.startswith("_"):
            continue
        if attr_name in ("edssection", "infoheader", "parse", "get_field", "objectlist", "countmsg"):
            continue
        try:
            value = getattr(section, attr_name)
        except AttributeError:
            continue

        if callable(value):
            continue

        if attr_name in dcf_only_fields and ft != Filetype.FILE_DCF:
            continue

        if attr_name == "exportFolder":
            continue

        eds_fields.append((attr_name, value))

    return eds_fields


def _format_csharp_datetime(date_str: str, time_str: str) -> str:
    """将 EDS 日期时间格式化为 C# 风格: '2024/1/1 12:00:00'"""
    from datetime import datetime
    date_str = date_str.strip()
    time_str = time_str.strip()

    for fmt in ("%m-%d-%Y", "%m/%d/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
    else:
        return f"{date_str} {time_str}"

    for tfmt in ("%I:%M%p", "%I:%M:%S%p", "%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(time_str.upper(), tfmt)
            return f"{d.year}/{d.month}/{d.day} {t.strftime('%H:%M:%S')}"
        except ValueError:
            continue

    return f"{d.year}/{d.month}/{d.day} {time_str}"