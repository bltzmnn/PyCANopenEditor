"""XDD/XDC XML 文件处理器，对应 C# CanOpenXDD_1_1.cs 和 CanOpenXDD.cs"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from lxml import etree

from ..models.datatypes import (
    AccessPDO,
    AccessSDO,
    AccessSRDO,
    AccessType,
    DataType,
    ObjectType,
    PDOMappingType,
)
from ..models.eds import EDS
from ..models.info_section import (
    Comments,
    DeviceCommissioning,
    DeviceInfo,
    DummyUsage,
    FileInfo,
    Filetype,
    MandatoryObjects,
    Module,
    OptionalObjects,
)
from ..models.od_entry import CustomProperties, ODentry
from ..models.warnings import Warnings

NS_V11 = "http://www.canopen.org/xml/1.1"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"

XDD_ACCESS_MAP = {
    "noAccess": AccessType.UNKNOWN,
    "const": AccessType.CONST,
    "read": AccessType.RO,
    "readWrite": AccessType.RW,
    "readWriteInput": AccessType.RWR,
    "readWriteOutput": AccessType.RWW,
    "write": AccessType.WO,
}

XDD_DATA_TYPE_MAP = {
    "BOOLEAN": DataType.BOOLEAN,
    "INTEGER8": DataType.INTEGER8,
    "INTEGER16": DataType.INTEGER16,
    "INTEGER32": DataType.INTEGER32,
    "INTEGER64": DataType.INTEGER64,
    "UNSIGNED8": DataType.UNSIGNED8,
    "UNSIGNED16": DataType.UNSIGNED16,
    "UNSIGNED32": DataType.UNSIGNED32,
    "UNSIGNED64": DataType.UNSIGNED64,
    "REAL32": DataType.REAL32,
    "REAL64": DataType.REAL64,
    "VISIBLE_STRING": DataType.VISIBLE_STRING,
    "OCTET_STRING": DataType.OCTET_STRING,
    "UNICODE_STRING": DataType.UNICODE_STRING,
    "TIME_OF_DAY": DataType.TIME_OF_DAY,
    "TIME_DIFFERENCE": DataType.TIME_DIFFERENCE,
    "DOMAIN": DataType.DOMAIN,
    "INTEGER24": DataType.INTEGER24,
    "INTEGER40": DataType.INTEGER40,
    "INTEGER48": DataType.INTEGER48,
    "INTEGER56": DataType.INTEGER56,
    "UNSIGNED24": DataType.UNSIGNED24,
    "UNSIGNED40": DataType.UNSIGNED40,
    "UNSIGNED48": DataType.UNSIGNED48,
    "UNSIGNED56": DataType.UNSIGNED56,
    "USINT": DataType.UNSIGNED8,
    "UINT": DataType.UNSIGNED16,
    "UDINT": DataType.UNSIGNED32,
    "ULINT": DataType.UNSIGNED64,
    "SINT": DataType.INTEGER8,
    "INT": DataType.INTEGER16,
    "DINT": DataType.INTEGER32,
    "LINT": DataType.INTEGER64,
    "STRING": DataType.VISIBLE_STRING,
    "WSTRING": DataType.UNICODE_STRING,
    "BYTE": DataType.UNSIGNED8,
    "WORD": DataType.UNSIGNED16,
    "DWORD": DataType.UNSIGNED32,
    "LWORD": DataType.UNSIGNED64,
}

PDO_MAPPING_MAP = {
    "no": PDOMappingType.NO,
    "TPDO": PDOMappingType.TPDO,
    "RPDO": PDOMappingType.RPDO,
    "optional": PDOMappingType.OPTIONAL,
    "default": PDOMappingType.DEFAULT,
}


class XDDHandler:
    """XDD/XDC 文件处理器，对应 C# CanOpenXDD_1_1"""

    def read_xml(self, filename: str) -> Optional[EDS]:
        try:
            tree = etree.parse(filename)
            root = tree.getroot()
        except Exception:
            return None

        ns = _detect_namespace(root)
        if ns:
            return self._parse_v11(root, ns, filename)
        else:
            return self._parse_v10(root, filename)

    def write_xml(self, filename: str, eds: EDS,
                  device_commissioning: bool = False, stripped: bool = False) -> None:
        container = self._build_profile_container(eds, filename, device_commissioning, stripped)
        tree = etree.ElementTree(container)
        with open(filename, "wb") as f:
            tree.write(f, xml_declaration=True, encoding="utf-8", pretty_print=True)

    def read_multi_xml(self, filename: str) -> list[EDS]:
        """读取多设备 Network XDD/XDC 文件，对应 C# ReadMultiXML"""
        try:
            tree = etree.parse(filename)
            root = tree.getroot()
        except Exception:
            return []

        results: list[EDS] = []

        # Network XDD 根元素是 CanOpenProject（v1.1）或 OpenEDSProject（v1.0）
        # 每个子 ISO15745ProfileContainer 是一个设备
        for container in root.iter():
            tag = _local_tag(container.tag)
            if tag == "ISO15745ProfileContainer":
                ns = _detect_namespace(container)
                if ns:
                    eds = self._parse_v11(container, ns, filename)
                else:
                    eds = self._parse_v10(container, filename)
                if eds is not None:
                    results.append(eds)

        # 如果根元素本身就是 ISO15745ProfileContainer，则作为单设备处理
        root_tag = _local_tag(root.tag)
        if root_tag == "ISO15745ProfileContainer" and not results:
            ns = _detect_namespace(root)
            if ns:
                eds = self._parse_v11(root, ns, filename)
            else:
                eds = self._parse_v10(root, filename)
            if eds is not None:
                results.append(eds)

        return results

    def write_multi_xml(self, filename: str, edss: list[EDS],
                        device_commissioning: bool = False) -> None:
        """写入多设备 Network XDD/XDC 文件，对应 C# WriteMultiXML"""
        ns = NS_V11
        q = f"{{{ns}}}"

        root = etree.Element(f"{q}CanOpenProject", nsmap={None: ns})
        root.set("version", "1.1")

        for eds in edss:
            container = self._build_profile_container(eds, filename, device_commissioning, False)
            root.append(container)

        tree = etree.ElementTree(root)
        with open(filename, "wb") as f:
            tree.write(f, xml_declaration=True, encoding="utf-8", pretty_print=True)

    def _build_profile_container(self, eds: EDS, filename: str,
                                  device_commissioning: bool = False,
                                  stripped: bool = False) -> etree._Element:
        """构建单个设备的 ISO15745ProfileContainer XML 元素"""
        ns = NS_V11
        q = f"{{{ns}}}"

        root = etree.Element(f"{q}ISO15745ProfileContainer", nsmap={None: ns})

        profile = etree.SubElement(root, f"{q}ISO15745Profile")
        header = etree.SubElement(profile, f"{q}ProfileHeader")
        _add_text(header, f"{q}ProfileIdentification", "CANopen device profile")
        _add_text(header, f"{q}ProfileRevision", "1.1")
        _add_text(header, f"{q}ProfileClassID", "Device")

        iso_ref = etree.SubElement(header, f"{q}ISO15745Reference")
        _add_text(iso_ref, f"{q}ISO15745Part", "1")
        _add_text(iso_ref, f"{q}ISO15745Edition", "1")
        _add_text(iso_ref, f"{q}ProfileTechnology", "CANopen")

        body = etree.SubElement(profile, f"{q}ProfileBody")
        body.set(f"{{{NS_XSI}}}type", f"{{{ns}}}ProfileBody_Device_CANopen")
        body.set("formatName", "CANopen")
        body.set("formatVersion", "1.0")

        if eds.fi.FileName:
            body.set("fileName", eds.fi.FileName)
        else:
            body.set("fileName", os.path.basename(filename))

        self._write_device_identity(body, eds, q, stripped)
        self._write_application_process(body, eds, q, stripped, device_commissioning)

        profile2 = etree.SubElement(root, f"{q}ISO15745Profile")
        header2 = etree.SubElement(profile2, f"{q}ProfileHeader")
        _add_text(header2, f"{q}ProfileIdentification", "CANopen communication network profile")
        _add_text(header2, f"{q}ProfileRevision", "1.1")
        _add_text(header2, f"{q}ProfileClassID", "CommunicationNetwork")

        iso_ref2 = etree.SubElement(header2, f"{q}ISO15745Reference")
        _add_text(iso_ref2, f"{q}ISO15745Part", "1")
        _add_text(iso_ref2, f"{q}ISO15745Edition", "1")
        _add_text(iso_ref2, f"{q}ProfileTechnology", "CANopen")

        body2 = etree.SubElement(profile2, f"{q}ProfileBody")
        body2.set(f"{{{NS_XSI}}}type", f"{{{ns}}}ProfileBody_CommunicationNetwork_CANopen")
        body2.set("formatName", "CANopen")
        body2.set("formatVersion", "1.0")

        self._write_communication_network(body2, eds, q, stripped, device_commissioning)

        return root

    def _parse_v11(self, root: etree._Element, ns: str, filename: str) -> EDS:
        eds = EDS()
        eds.projectFilename = filename
        eds.xddfilename_1_1 = filename

        q = f"{{{ns}}}"

        device_body = None
        comm_body = None

        for profile in root.iter():
            tag = _local_tag(profile.tag)
            if tag != "ProfileBody":
                continue
            xsi_type = profile.get(f"{{{NS_XSI}}}type", "")
            if "Device" in xsi_type:
                device_body = profile
            elif "CommunicationNetwork" in xsi_type:
                comm_body = profile

        # Parse communication network first (contains CANopenObjectList)
        if comm_body is not None:
            self._parse_comm_network_profile(eds, comm_body)

        # Parse device profile (contains parameterList with data types and properties)
        if device_body is not None:
            self._parse_device_profile(eds, device_body, q)

        return eds

    def _parse_v10(self, root: etree._Element, filename: str) -> EDS:
        eds = EDS()
        eds.projectFilename = filename
        eds.xddfilename_1_0 = filename
        Warnings.add_warning("XDD v1.0 parsing is best-effort")

        for elem in root.iter():
            tag = _local_tag(elem.tag)
            if tag == "DeviceIdentity":
                self._parse_device_identity_v10(eds, elem)
            elif tag == "CANopenObject":
                self._parse_canopen_object(eds, elem, None)

        return eds

    def _parse_device_profile(self, eds: EDS, body: etree._Element, q: str) -> None:
        fi_attr = {
            "fileName": "FileName",
            "fileCreator": "CreatedBy",
            "fileVersion": "FileVersion",
        }
        for xml_attr, field in fi_attr.items():
            val = body.get(xml_attr)
            if val:
                setattr(eds.fi, field, val)

        for di in body.iter():
            if _local_tag(di.tag) != "DeviceIdentity":
                continue
            vn = _find_child_ns(di, "vendorName", q)
            if vn is not None and vn.text:
                eds.di.VendorName = vn.text.strip()
            vi = _find_child_ns(di, "vendorID", q)
            if vi is not None and vi.text:
                eds.di.VendorNumber = vi.text.strip()
            pn = _find_child_ns(di, "productName", q)
            if pn is not None and pn.text:
                eds.di.ProductName = pn.text.strip()
            pi = _find_child_ns(di, "productID", q)
            if pi is not None and pi.text:
                eds.di.ProductNumber = pi.text.strip()
            break

        param_list = _find_child_deep_ns(body, "parameterList", q)
        uid_map: dict[str, tuple] = {}
        if param_list is not None:
            for param in param_list.iter():
                if _local_tag(param.tag) != "parameter":
                    continue
                uid = param.get("uniqueID", "")
                access_str = param.get("access", "")
                access_type = XDD_ACCESS_MAP.get(access_str, AccessType.UNKNOWN)

                description = ""
                desc_elem = _find_child_ns(param, "description", q)
                if desc_elem is not None and desc_elem.text:
                    description = desc_elem.text.strip()

                label = ""
                label_elem = _find_child_ns(param, "label", q)
                if label_elem is not None and label_elem.text:
                    label = label_elem.text.strip()

                data_type = self._parse_data_type_ns(param, q)
                default_value = ""
                dv_elem = _find_child_ns(param, "defaultValue", q)
                if dv_elem is not None:
                    default_value = dv_elem.get("value", "")

                props = self._parse_properties_ns(param, q)

                uid_map[uid] = (data_type, access_type, default_value, description, label, props)

        obj_list = _find_child_deep(body, "CANopenObjectList")
        if obj_list is not None:
            for obj in obj_list.iter("CANopenObject"):
                self._parse_canopen_object(eds, obj)

        # Merge parameterList data into OD entries from CANopenObjectList
        for uid, info in uid_map.items():
            data_type, access_type, default_value, description, label, props = info
            od = _find_od_by_uid(eds, uid)
            if od is not None:
                if data_type != DataType.UNKNOWN:
                    od.datatype = data_type
                if access_type != AccessType.UNKNOWN:
                    od.accesstype = access_type
                if default_value:
                    od.defaultvalue = default_value
                if description:
                    od.Description = description
                od.prop = props

    def _parse_comm_network_profile(self, eds: EDS, body: etree._Element) -> None:
        net_mgmt = _find_child_deep(body, "CANopenNetworkManagement")
        if net_mgmt is not None:
            dc_elem = _find_child(net_mgmt, "deviceCommissioning")
            if dc_elem is not None:
                try:
                    eds.dc.NodeID = int(dc_elem.get("NodeID", "0"))
                except (TypeError, ValueError):
                    pass
                if dc_elem.get("nodeName"):
                    eds.dc.NodeName = dc_elem.get("nodeName")
                if dc_elem.get("actualBaudRate"):
                    try:
                        eds.dc.Baudrate = int(dc_elem.get("actualBaudRate"))
                    except (TypeError, ValueError):
                        pass
                if dc_elem.get("networkNumber"):
                    try:
                        eds.dc.NetNumber = int(dc_elem.get("networkNumber"))
                    except (TypeError, ValueError):
                        pass
                if dc_elem.get("networkName"):
                    eds.dc.NetworkName = dc_elem.get("networkName")
                mgr = dc_elem.get("CANopenManager")
                if mgr is not None:
                    eds.dc.CANopenManager = mgr.lower() == "true"

        obj_list = _find_child_deep(body, "CANopenObjectList")
        if obj_list is not None:
            for obj in obj_list.iter():
                if _local_tag(obj.tag) != "CANopenObject":
                    continue
                self._parse_canopen_object(eds, obj)

        dummy = _find_child_deep(body, "dummyUsage")
        if dummy is not None:
            for d in dummy.iter():
                if _local_tag(d.tag) != "dummy":
                    continue
                entry = d.get("entry", "")
                if "=" in entry:
                    key, val = entry.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key.startswith("Dummy") and len(key) == 8:
                        try:
                            idx = int(key[-3:])
                            attr = f"Dummy{idx:04d}"
                            if hasattr(eds.du, attr):
                                setattr(eds.du, attr, val == "1")
                        except ValueError:
                            pass

    def _parse_canopen_object(self, eds: EDS, obj: etree._Element) -> None:
        idx_str = obj.get("index", "")
        try:
            idx = int(idx_str, 16)
        except ValueError:
            try:
                idx = int(idx_str)
            except ValueError:
                return

        name = obj.get("name", "")
        obj_type_str = obj.get("objectType", "7")
        try:
            obj_type = ObjectType(int(obj_type_str))
        except (ValueError, KeyError):
            obj_type = ObjectType.VAR

        pdo_str = obj.get("PDOmapping", "no")
        pdo_type = PDO_MAPPING_MAP.get(pdo_str, PDOMappingType.NO)
        uid = obj.get("uniqueIDRef", obj.get("uniqueID", ""))

        od = ODentry(parameter_name=name, index=idx, objecttype=obj_type)
        od.uniqueID = uid
        od.PDOtype = pdo_type

        for sub in obj.iter():
            if _local_tag(sub.tag) != "CANopenSubObject":
                continue
            if sub is obj:
                continue
            self._parse_canopen_sub_object(eds, od, sub)

        eds.ods[idx] = od

    def _parse_canopen_sub_object(self, eds: EDS, parent: ODentry, sub: etree._Element) -> None:
        sub_idx_str = sub.get("subIndex", "0")
        try:
            sub_idx = int(sub_idx_str, 16)
        except ValueError:
            try:
                sub_idx = int(sub_idx_str)
            except ValueError:
                return

        name = sub.get("name", "")
        obj_type_str = sub.get("objectType", "7")
        try:
            obj_type = ObjectType(int(obj_type_str))
        except (ValueError, KeyError):
            obj_type = ObjectType.VAR

        pdo_str = sub.get("PDOmapping", "no")
        pdo_type = PDO_MAPPING_MAP.get(pdo_str, PDOMappingType.NO)
        uid = sub.get("uniqueIDRef", sub.get("uniqueID", ""))

        data_type = DataType.UNKNOWN
        dt_str = sub.get("dataType", "")
        if dt_str:
            try:
                data_type = DataType(int(dt_str, 16))
            except ValueError:
                data_type = XDD_DATA_TYPE_MAP.get(dt_str, DataType.UNKNOWN)

        access_str = sub.get("access", "")
        access_type = XDD_ACCESS_MAP.get(access_str, AccessType.UNKNOWN)

        default_value = ""
        dv_elem = _find_child(sub, "defaultValue")
        if dv_elem is not None:
            default_value = dv_elem.get("value", "")

        actual_value = ""
        av_elem = _find_child(sub, "actualValue")
        if av_elem is not None:
            actual_value = av_elem.get("value", "")

        low_limit = ""
        ll_elem = _find_child(sub, "lowLimit")
        if ll_elem is not None:
            low_limit = ll_elem.get("value", ll_elem.text or "")

        high_limit = ""
        hl_elem = _find_child(sub, "highLimit")
        if hl_elem is not None:
            high_limit = hl_elem.get("value", hl_elem.text or "")

        props = self._parse_properties(sub)

        sub_od = ODentry(
            parameter_name=name,
            index=parent.index,
            objecttype=obj_type,
            datatype=data_type,
            defaultvalue=default_value,
            accesstype=access_type,
            pdo_type=pdo_type,
            parent=parent,
        )
        sub_od.actualvalue = actual_value
        sub_od.LowLimit = low_limit
        sub_od.HighLimit = high_limit
        sub_od.uniqueID = uid
        sub_od.prop = props

        parent.subobjects[sub_idx] = sub_od

    def _parse_data_type(self, param: etree._Element) -> DataType:
        for child in param:
            tag = _local_tag(child.tag)
            if tag == "dataTypeIDRef":
                continue
            if tag in XDD_DATA_TYPE_MAP:
                return XDD_DATA_TYPE_MAP[tag]
            if tag in ("array", "record", "struct"):
                return DataType.UNKNOWN
        return DataType.UNKNOWN

    def _parse_data_type_ns(self, param: etree._Element, q: str) -> DataType:
        for child in param:
            tag = _local_tag(child.tag)
            if tag == "dataTypeIDRef":
                continue
            if tag in XDD_DATA_TYPE_MAP:
                return XDD_DATA_TYPE_MAP[tag]
            if tag in ("array", "record", "struct"):
                return DataType.UNKNOWN
        return DataType.UNKNOWN

    def _parse_properties(self, elem: etree._Element) -> CustomProperties:
        props = CustomProperties()
        for prop in elem.iter("property"):
            name = prop.get("name", "")
            value = prop.get("value", "")
            self._apply_property(props, name, value)
        return props

    def _parse_properties_ns(self, elem: etree._Element, q: str) -> CustomProperties:
        props = CustomProperties()
        for prop in elem.iter():
            if _local_tag(prop.tag) != "property":
                continue
            name = prop.get("name", "")
            value = prop.get("value", "")
            self._apply_property(props, name, value)
        return props

    def _apply_property(self, props: CustomProperties, name: str, value: str) -> None:
        if name == "CO_disabled":
            props.CO_disabled = value.lower() in ("true", "1")
        elif name == "CO_countLabel":
            props.CO_countLabel = value
        elif name == "CO_storageGroup":
            props.CO_storageGroup = value
        elif name == "CO_flagsPDO":
            props.CO_flagsPDO = value.lower() in ("true", "1")
        elif name == "CO_accessSRDO":
            try:
                props.CO_accessSRDO = AccessSRDO[value.upper()]
            except (KeyError, ValueError):
                props.CO_accessSRDO = AccessSRDO.NO
        elif name == "CO_stringLengthMin":
            try:
                props.CO_stringLengthMin = int(value)
            except ValueError:
                props.CO_stringLengthMin = 0

    def _parse_device_identity_v10(self, eds: EDS, elem: etree._Element) -> None:
        for child in elem:
            tag = _local_tag(child.tag)
            if tag == "vendorName" and child.text:
                eds.di.VendorName = child.text
            elif tag == "vendorID" and child.text:
                eds.di.VendorNumber = child.text
            elif tag == "productName" and child.text:
                eds.di.ProductName = child.text
            elif tag == "productID" and child.text:
                eds.di.ProductNumber = child.text

    def _write_device_identity(self, body: etree._Element, eds: EDS, q: str, stripped: bool) -> None:
        di_elem = etree.SubElement(body, f"{q}DeviceIdentity")
        _add_text(di_elem, f"{q}vendorName", eds.di.VendorName)
        _add_text(di_elem, f"{q}vendorID", eds.di.VendorNumber)
        _add_text(di_elem, f"{q}productName", eds.di.ProductName)
        _add_text(di_elem, f"{q}productID", eds.di.ProductNumber)

    def _write_application_process(self, body: etree._Element, eds: EDS, q: str,
                                    stripped: bool, device_commissioning: bool) -> None:
        ap = etree.SubElement(body, f"{q}ApplicationProcess")

        param_list = etree.SubElement(ap, f"{q}parameterList")

        for idx in sorted(eds.ods.keys()):
            od = eds.ods[idx]
            if stripped and od.prop.CO_disabled:
                continue

            uid = od.uniqueID or f"UID_OBJ_{idx:04X}"
            param = etree.SubElement(param_list, f"{q}parameter")
            param.set("uniqueID", uid)

            if od.accesstype != AccessType.UNKNOWN:
                access_key = _access_type_to_xdd(od.accesstype)
                param.set("access", access_key)

            if od.Description:
                desc = etree.SubElement(param, f"{q}description")
                desc.set("lang", "en")
                desc.text = od.Description

            self._write_data_type_element(param, od.datatype, q)

            if od.defaultvalue:
                dv = etree.SubElement(param, f"{q}defaultValue")
                dv.set("value", od.defaultvalue)

            self._write_properties(param, od.prop, q, stripped)

            for sub_idx in sorted(od.subobjects.keys()):
                sub = od.subobjects[sub_idx]
                sub_uid = sub.uniqueID or f"UID_SUB_{idx:04X}{sub_idx:02X}"
                sub_param = etree.SubElement(param_list, f"{q}parameter")
                sub_param.set("uniqueID", sub_uid)

                if sub.accesstype != AccessType.UNKNOWN:
                    access_key = _access_type_to_xdd(sub.accesstype)
                    sub_param.set("access", access_key)

                if sub.parameter_name:
                    label = etree.SubElement(sub_param, f"{q}label")
                    label.set("lang", "en")
                    label.text = sub.parameter_name

                self._write_data_type_element(sub_param, sub.datatype, q)

                if sub.defaultvalue:
                    dv = etree.SubElement(sub_param, f"{q}defaultValue")
                    dv.set("value", sub.defaultvalue)

                if device_commissioning and sub.actualvalue:
                    av = etree.SubElement(sub_param, f"{q}actualValue")
                    av.set("value", sub.actualvalue)

                self._write_properties(sub_param, sub.prop, q, stripped)

    def _write_communication_network(self, body: etree._Element, eds: EDS, q: str,
                                       stripped: bool, device_commissioning: bool = False) -> None:
        if device_commissioning:
            net_mgmt = etree.SubElement(body, f"{q}CANopenNetworkManagement")
            dc_elem = etree.SubElement(net_mgmt, f"{q}deviceCommissioning")
            dc_elem.set("NodeID", str(int(eds.dc.NodeID or 0)))
            if eds.dc.NodeName:
                dc_elem.set("nodeName", eds.dc.NodeName)
            if eds.dc.Baudrate:
                dc_elem.set("actualBaudRate", str(int(eds.dc.Baudrate)))
            if eds.dc.NetNumber:
                dc_elem.set("networkNumber", str(int(eds.dc.NetNumber)))
            if eds.dc.NetworkName:
                dc_elem.set("networkName", eds.dc.NetworkName)
            if eds.dc.CANopenManager:
                dc_elem.set("CANopenManager", "true")

        al = etree.SubElement(body, "ApplicationLayers")
        obj_list = etree.SubElement(al, f"{q}CANopenObjectList")

        for idx in sorted(eds.ods.keys()):
            od = eds.ods[idx]
            if stripped and od.prop.CO_disabled:
                continue

            uid = od.uniqueID or f"UID_OBJ_{idx:04X}"
            obj = etree.SubElement(obj_list, "CANopenObject")
            obj.set("index", f"{idx:04X}")
            obj.set("name", od.parameter_name)
            obj.set("objectType", str(int(od.objecttype)))

            pdo_val = _pdo_type_to_xdd(od.PDOtype)
            if pdo_val != "no":
                obj.set("PDOmapping", pdo_val)

            obj.set("uniqueIDRef", uid)

            if od.subobjects:
                obj.set("subNumber", str(len(od.subobjects)))
                for sub_idx in sorted(od.subobjects.keys()):
                    sub = od.subobjects[sub_idx]
                    sub_uid = sub.uniqueID or f"UID_SUB_{idx:04X}{sub_idx:02X}"
                    sub_obj = etree.SubElement(obj, "CANopenSubObject")
                    sub_obj.set("subIndex", f"{sub_idx:02X}")
                    sub_obj.set("name", sub.parameter_name)
                    sub_obj.set("objectType", str(int(sub.objecttype)))
                    sub_pdo = _pdo_type_to_xdd(sub.PDOtype)
                    sub_obj.set("PDOmapping", sub_pdo)
                    sub_obj.set("uniqueIDRef", sub_uid)

        dummy = etree.SubElement(al, f"{q}dummyUsage")
        for i in range(1, 8):
            attr = f"Dummy{i:04d}"
            val = getattr(eds.du, attr, False)
            d = etree.SubElement(dummy, f"{q}dummy")
            d.set("entry", f"{attr}={'1' if val else '0'}")

    def _write_data_type_element(self, parent: etree._Element, dt: DataType, q: str) -> None:
        for name, value in XDD_DATA_TYPE_MAP.items():
            if value == dt:
                etree.SubElement(parent, name)
                return
        etree.SubElement(parent, "UNSIGNED32")

    def _write_properties(self, parent: etree._Element, props: CustomProperties, q: str, stripped: bool) -> None:
        if stripped:
            return
        if props.CO_disabled:
            p = etree.SubElement(parent, f"{q}property")
            p.set("name", "CO_disabled")
            p.set("value", "true")
        if props.CO_countLabel:
            p = etree.SubElement(parent, f"{q}property")
            p.set("name", "CO_countLabel")
            p.set("value", props.CO_countLabel)
        if props.CO_storageGroup != "RAM":
            p = etree.SubElement(parent, f"{q}property")
            p.set("name", "CO_storageGroup")
            p.set("value", props.CO_storageGroup)
        if props.CO_flagsPDO:
            p = etree.SubElement(parent, f"{q}property")
            p.set("name", "CO_flagsPDO")
            p.set("value", "true")


def _detect_namespace(root: etree._Element) -> Optional[str]:
    for key, val in root.nsmap.items():
        if val and "canopen.org/xml/1.1" in val:
            return val
    return None


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_child(parent: etree._Element, local_name: str) -> Optional[etree._Element]:
    for child in parent:
        if _local_tag(child.tag) == local_name:
            return child
    return None


def _find_child_deep(parent: etree._Element, local_name: str) -> Optional[etree._Element]:
    for elem in parent.iter():
        if _local_tag(elem.tag) == local_name:
            return elem
    return None


def _find_od_by_uid(eds: EDS, uid: str) -> Optional[ODentry]:
    for idx, od in eds.ods.items():
        if od.uniqueID == uid:
            return od
        for sub_idx, sub in od.subobjects.items():
            if sub.uniqueID == uid:
                return sub
    return None


def _find_child_ns(parent: etree._Element, local_name: str, q: str) -> Optional[etree._Element]:
    ns_child = parent.find(f"{q}{local_name}")
    if ns_child is not None:
        return ns_child
    return _find_child(parent, local_name)


def _find_child_deep_ns(parent: etree._Element, local_name: str, q: str) -> Optional[etree._Element]:
    for elem in parent.iter():
        if _local_tag(elem.tag) == local_name:
            return elem
    return None


def _add_text(parent: etree._Element, tag: str, text: str) -> None:
    child = etree.SubElement(parent, tag)
    child.text = text or ""


def _access_type_to_xdd(at: AccessType) -> str:
    mapping = {
        AccessType.CONST: "const",
        AccessType.RO: "read",
        AccessType.RW: "readWrite",
        AccessType.RWR: "readWriteInput",
        AccessType.RWW: "readWriteOutput",
        AccessType.WO: "write",
    }
    return mapping.get(at, "noAccess")


def _pdo_type_to_xdd(pt: PDOMappingType) -> str:
    mapping = {
        PDOMappingType.NO: "no",
        PDOMappingType.TPDO: "TPDO",
        PDOMappingType.RPDO: "RPDO",
        PDOMappingType.OPTIONAL: "optional",
        PDOMappingType.DEFAULT: "default",
    }
    return mapping.get(pt, "no")