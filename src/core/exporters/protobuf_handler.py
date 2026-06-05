"""Protobuf 序列化/反序列化处理器"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

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
from ..models.od_entry import ODentry
from .exporter_factory import ExporterDescriptor, ExporterFlags, IFileExporter

try:
    from ..proto.CanOpen_pb2 import (
        CanOpenDevice,
        CanOpen_DeviceCommissioning,
        CanOpen_DeviceInfo,
        CanOpen_FileInfo,
        OdObject,
        OdSubObject,
    )
    _PROTOBUF_AVAILABLE = True
except ImportError:
    _PROTOBUF_AVAILABLE = False


_DATATYPE_TO_PROTO = {
    DataType.UNKNOWN: OdSubObject.DataType.UNSPECIFIED,
    DataType.BOOLEAN: OdSubObject.DataType.BOOLEAN,
    DataType.INTEGER8: OdSubObject.DataType.INTEGER8,
    DataType.INTEGER16: OdSubObject.DataType.INTEGER16,
    DataType.INTEGER32: OdSubObject.DataType.INTEGER32,
    DataType.UNSIGNED8: OdSubObject.DataType.UNSIGNED8,
    DataType.UNSIGNED16: OdSubObject.DataType.UNSIGNED16,
    DataType.UNSIGNED32: OdSubObject.DataType.UNSIGNED32,
    DataType.REAL32: OdSubObject.DataType.REAL32,
    DataType.VISIBLE_STRING: OdSubObject.DataType.VISIBLE_STRING,
    DataType.OCTET_STRING: OdSubObject.DataType.OCTET_STRING,
    DataType.UNICODE_STRING: OdSubObject.DataType.UNICODE_STRING,
    DataType.TIME_OF_DAY: OdSubObject.DataType.TIME_OF_DAY,
    DataType.TIME_DIFFERENCE: OdSubObject.DataType.TIME_DIFFERENCE,
    DataType.DOMAIN: OdSubObject.DataType.DOMAIN,
    DataType.INTEGER24: OdSubObject.DataType.INTEGER24,
    DataType.REAL64: OdSubObject.DataType.REAL64,
    DataType.INTEGER40: OdSubObject.DataType.INTEGER40,
    DataType.INTEGER48: OdSubObject.DataType.INTEGER48,
    DataType.INTEGER56: OdSubObject.DataType.INTEGER56,
    DataType.INTEGER64: OdSubObject.DataType.INTEGER64,
    DataType.UNSIGNED24: OdSubObject.DataType.UNSIGNED24,
    DataType.UNSIGNED40: OdSubObject.DataType.UNSIGNED40,
    DataType.UNSIGNED48: OdSubObject.DataType.UNSIGNED48,
    DataType.UNSIGNED56: OdSubObject.DataType.UNSIGNED56,
    DataType.UNSIGNED64: OdSubObject.DataType.UNSIGNED64,
}

_PROTO_TO_DATATYPE = {v: k for k, v in _DATATYPE_TO_PROTO.items()}

_ACCESS_SDO_TO_PROTO = {
    AccessSDO.NO: OdSubObject.AccessSDO.ACCESS_SDO_NO,
    AccessSDO.RO: OdSubObject.AccessSDO.ACCESS_SDO_RO,
    AccessSDO.WO: OdSubObject.AccessSDO.ACCESS_SDO_WO,
    AccessSDO.RW: OdSubObject.AccessSDO.ACCESS_SDO_RW,
}

_PROTO_TO_ACCESS_SDO = {v: k for k, v in _ACCESS_SDO_TO_PROTO.items()}

_ACCESS_PDO_TO_PROTO = {
    AccessPDO.NO: OdSubObject.AccessPDO.ACCESS_PDO_NO,
    AccessPDO.T: OdSubObject.AccessPDO.ACCESS_PDO_T,
    AccessPDO.R: OdSubObject.AccessPDO.ACCESS_PDO_R,
    AccessPDO.TR: OdSubObject.AccessPDO.ACCESS_PDO_TR,
}

_PROTO_TO_ACCESS_PDO = {v: k for k, v in _ACCESS_PDO_TO_PROTO.items()}

_ACCESS_SRDO_TO_PROTO = {
    AccessSRDO.NO: OdSubObject.AccessSRDO.ACCESS_SRDO_NO,
    AccessSRDO.TX: OdSubObject.AccessSRDO.ACCESS_SRDO_TX,
    AccessSRDO.RX: OdSubObject.AccessSRDO.ACCESS_SRDO_RX,
    AccessSRDO.TRX: OdSubObject.AccessSRDO.ACCESS_SRDO_TRX,
}

_PROTO_TO_ACCESS_SRDO = {v: k for k, v in _ACCESS_SRDO_TO_PROTO.items()}

_OBJ_TYPE_TO_PROTO = {
    ObjectType.VAR: OdObject.ObjectType.OBJECT_TYPE_VAR,
    ObjectType.ARRAY: OdObject.ObjectType.OBJECT_TYPE_ARRAY,
    ObjectType.RECORD: OdObject.ObjectType.OBJECT_TYPE_RECORD,
}

_PROTO_TO_OBJ_TYPE = {v: k for k, v in _OBJ_TYPE_TO_PROTO.items()}


def _eds_to_proto(eds: EDS) -> CanOpenDevice:
    device = CanOpenDevice()

    fi = device.fileInfo
    fi.fileVersion = eds.fi.FileVersion
    fi.description = eds.fi.Description
    fi.createdBy = eds.fi.CreatedBy
    fi.modifiedBy = eds.fi.ModifiedBy

    di = device.deviceInfo
    di.vendorName = eds.di.VendorName
    di.productName = eds.di.ProductName
    di.baudRate10 = eds.di.BaudRate_10
    di.baudRate20 = eds.di.BaudRate_20
    di.baudRate50 = eds.di.BaudRate_50
    di.baudRate125 = eds.di.BaudRate_125
    di.baudRate250 = eds.di.BaudRate_250
    di.baudRate500 = eds.di.BaudRate_500
    di.baudRate800 = eds.di.BaudRate_800
    di.baudRate1000 = eds.di.BaudRate_1000
    di.baudRateAuto = eds.di.BaudRate_auto
    di.lssSlave = eds.di.LSS_Supported
    di.lssMaster = eds.di.LSS_Master

    dc = device.deviceCommissioning
    dc.nodeId = eds.dc.NodeID
    dc.nodeName = eds.dc.NodeName
    dc.baudrate = eds.dc.Baudrate

    for idx, od in eds.ods.items():
        key = f"0x{idx:04X}"
        obj = device.objects[key]
        obj.disabled = od.prop.CO_disabled
        obj.name = od.parameter_name
        obj.alias = od.denotation
        obj.description = od.Description
        obj.objectType = _OBJ_TYPE_TO_PROTO.get(od.objecttype, OdObject.ObjectType.OBJECT_TYPE_UNSPECIFIED)
        obj.countLabel = od.prop.CO_countLabel
        obj.storageGroup = od.prop.CO_storageGroup
        obj.flagsPDO = od.prop.CO_flagsPDO

        if od.objecttype == ObjectType.VAR:
            sub_key = "0x00"
            sub = obj.subObjects[sub_key]
            _fill_sub_object(sub, od)
        else:
            for sub_idx, sub_od in od.subobjects.items():
                sub_key = f"0x{sub_idx:02X}"
                sub = obj.subObjects[sub_key]
                _fill_sub_object(sub, sub_od)

    return device


def _fill_sub_object(sub: OdSubObject, od: ODentry) -> None:
    sub.name = od.parameter_name
    sub.dataType = _DATATYPE_TO_PROTO.get(od.datatype, OdSubObject.DataType.UNSPECIFIED)
    sub.sdo = _ACCESS_SDO_TO_PROTO.get(od.access_sdo(), OdSubObject.AccessSDO.ACCESS_SDO_NO)
    sub.pdo = _ACCESS_PDO_TO_PROTO.get(od.access_pdo(), OdSubObject.AccessPDO.ACCESS_PDO_NO)
    sub.srdo = _ACCESS_SRDO_TO_PROTO.get(od.prop.CO_accessSRDO, OdSubObject.AccessSRDO.ACCESS_SRDO_NO)
    sub.defaultValue = od.defaultvalue
    sub.actualValue = od.actualvalue
    sub.lowLimit = od.LowLimit
    sub.highLimit = od.HighLimit
    sub.stringLengthMin = od.prop.CO_stringLengthMin


def _proto_to_eds(device: CanOpenDevice) -> EDS:
    eds = EDS()

    fi = device.fileInfo
    eds.fi.FileVersion = fi.fileVersion
    eds.fi.Description = fi.description
    eds.fi.CreatedBy = fi.createdBy
    eds.fi.ModifiedBy = fi.modifiedBy

    di = device.deviceInfo
    eds.di.VendorName = di.vendorName
    eds.di.ProductName = di.productName
    eds.di.BaudRate_10 = di.baudRate10
    eds.di.BaudRate_20 = di.baudRate20
    eds.di.BaudRate_50 = di.baudRate50
    eds.di.BaudRate_125 = di.baudRate125
    eds.di.BaudRate_250 = di.baudRate250
    eds.di.BaudRate_500 = di.baudRate500
    eds.di.BaudRate_800 = di.baudRate800
    eds.di.BaudRate_1000 = di.baudRate1000
    eds.di.BaudRate_auto = di.baudRateAuto
    eds.di.LSS_Supported = di.lssSlave
    eds.di.LSS_Master = di.lssMaster

    dc = device.deviceCommissioning
    eds.dc.NodeID = dc.nodeId
    eds.dc.NodeName = dc.nodeName
    eds.dc.Baudrate = dc.baudrate

    for key in sorted(device.objects.keys()):
        obj = device.objects[key]
        try:
            idx = int(key, 16)
        except ValueError:
            continue

        obj_type = _PROTO_TO_OBJ_TYPE.get(obj.objectType, ObjectType.VAR)

        od = ODentry(
            parameter_name=obj.name,
            index=idx,
            objecttype=obj_type,
        )
        od.denotation = obj.alias
        od.Description = obj.description
        od.prop.CO_disabled = obj.disabled
        od.prop.CO_countLabel = obj.countLabel
        od.prop.CO_storageGroup = obj.storageGroup or "RAM"
        od.prop.CO_flagsPDO = obj.flagsPDO

        if obj_type == ObjectType.VAR:
            for sub_key in obj.subObjects:
                sub_obj = obj.subObjects[sub_key]
                _fill_od_from_sub(od, sub_obj)
        else:
            for sub_key in sorted(obj.subObjects.keys()):
                sub_obj = obj.subObjects[sub_key]
                try:
                    sub_idx = int(sub_key, 16)
                except ValueError:
                    continue
                sub_od = ODentry(
                    parameter_name=sub_obj.name,
                    index=idx,
                    parent=od,
                )
                _fill_od_from_sub(sub_od, sub_obj)
                od.subobjects[sub_idx] = sub_od

        eds.ods[idx] = od

    return eds


def _fill_od_from_sub(od: ODentry, sub: OdSubObject) -> None:
    od.datatype = _PROTO_TO_DATATYPE.get(sub.dataType, DataType.UNKNOWN)
    od.defaultvalue = sub.defaultValue
    od.actualvalue = sub.actualValue
    od.LowLimit = sub.lowLimit
    od.HighLimit = sub.highLimit
    od.prop.CO_stringLengthMin = sub.stringLengthMin

    access_sdo = _PROTO_TO_ACCESS_SDO.get(sub.sdo, AccessSDO.NO)
    access_pdo = _PROTO_TO_ACCESS_PDO.get(sub.pdo, AccessPDO.NO)
    access_srdo = _PROTO_TO_ACCESS_SRDO.get(sub.srdo, AccessSRDO.NO)

    od.set_access_sdo(access_sdo, access_pdo)
    od.prop.CO_accessSRDO = access_srdo


class ProtobufExporter(IFileExporter):
    """Protobuf 二进制序列化导出器"""

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "Protobuf Binary",
                [".binpb"],
                ExporterFlags.CanOpenNode,
                lambda filepath, eds_list: ProtobufExporter()._export_binpb(filepath, eds_list[0]),
            )
        ]

    def _export_binpb(self, filepath: str, eds: EDS) -> None:
        if not _PROTOBUF_AVAILABLE:
            raise RuntimeError("Protobuf 模块未安装，请先运行构建生成 CanOpen_pb2.py")
        device = _eds_to_proto(eds)
        with open(filepath, "wb") as f:
            f.write(device.SerializeToString())


class ProtobufJsonExporter(IFileExporter):
    """Protobuf JSON 序列化导出器"""

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "Protobuf JSON",
                [".json"],
                ExporterFlags.CanOpenNode,
                lambda filepath, eds_list: ProtobufJsonExporter()._export_json(filepath, eds_list[0]),
            )
        ]

    def _export_json(self, filepath: str, eds: EDS) -> None:
        if not _PROTOBUF_AVAILABLE:
            raise RuntimeError("Protobuf 模块未安装，请先运行构建生成 CanOpen_pb2.py")
        device = _eds_to_proto(eds)
        from google.protobuf.json_format import MessageToJson
        json_str = MessageToJson(device, preserving_proto_field_name=True)
        with open(filepath, "w", newline="\n") as f:
            f.write(json_str)


def load_protobuf_binpb(filepath: str) -> EDS:
    """从 .binpb 文件加载设备数据"""
    if not _PROTOBUF_AVAILABLE:
        raise RuntimeError("Protobuf 模块未安装")
    device = CanOpenDevice()
    with open(filepath, "rb") as f:
        device.ParseFromString(f.read())
    return _proto_to_eds(device)


def load_protobuf_json(filepath: str) -> EDS:
    """从 .json 文件加载设备数据"""
    if not _PROTOBUF_AVAILABLE:
        raise RuntimeError("Protobuf 模块未安装")
    device = CanOpenDevice()
    from google.protobuf.json_format import Parse
    with open(filepath) as f:
        Parse(f.read(), device)
    return _proto_to_eds(device)
