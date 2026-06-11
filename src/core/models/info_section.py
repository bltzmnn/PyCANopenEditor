"""CANopen EDS/DCF 信息段模型，对应 C# 的 InfoSection 及其子类"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .od_entry import _get_base


class Filetype(Enum):
    FILE_EDS = "eds"
    FILE_DCF = "dcf"


@dataclass
class InfoSection:
    edssection: str = ""
    infoheader: str = ""
    _section: dict[str, str] = field(default_factory=dict)

    def get_field(self, name: str, varname: str, target_type: type = str) -> bool:
        for key, value in self._section.items():
            if key.lower() == name.lower():
                try:
                    if target_type == str:
                        setattr(self, varname, value)
                    elif target_type == int:
                        setattr(self, varname, int(value, _get_base(value)))
                    elif target_type == bool:
                        setattr(self, varname, value == "1")
                    else:
                        setattr(self, varname, target_type(value))
                    return True
                except (ValueError, OverflowError):
                    return False
        return False

    def parse(self, section: dict[str, str]) -> None:
        self._section = section


@dataclass
class FileInfo(InfoSection):
    FileName: str = ""
    FileVersion: str = ""
    FileRevision: int = 0
    LastEDS: str = ""
    EDSVersionMajor: int = 0
    EDSVersionMinor: int = 0
    EDSVersion: str = ""
    Description: str = ""
    CreationTime: str = ""
    CreationDate: str = ""
    CreatedBy: str = ""
    ModificationTime: str = ""
    ModificationDate: str = ""
    ModifiedBy: str = ""
    exportFolder: str = ""
    CreationDateTime: str = ""
    ModificationDateTime: str = ""

    def __post_init__(self):
        self.infoheader = "CAN OPEN FileInfo"
        self.edssection = "FileInfo"

    def parse(self, section: dict[str, str]) -> None:
        self._section = section
        self.get_field("FileName", "FileName", str)
        self.get_field("FileVersion", "FileVersion", str)
        self.get_field("FileRevision", "FileRevision", int)
        self.get_field("LastEDS", "LastEDS", str)
        self.get_field("EDSVersion", "EDSVersion", str)
        self.get_field("Description", "Description", str)
        self.get_field("CreationTime", "CreationTime", str)
        self.get_field("CreationDate", "CreationDate", str)
        self.get_field("CreatedBy", "CreatedBy", str)
        self.get_field("ModificationTime", "ModificationTime", str)
        self.get_field("ModificationDate", "ModificationDate", str)
        self.get_field("ModifiedBy", "ModifiedBy", str)


@dataclass
class DeviceInfo(InfoSection):
    VendorName: str = ""
    VendorNumber: str = ""
    ProductName: str = ""
    ProductNumber: str = ""
    RevisionNumber: int = 0
    BaudRate_10: bool = False
    BaudRate_20: bool = False
    BaudRate_50: bool = False
    BaudRate_125: bool = False
    BaudRate_250: bool = False
    BaudRate_500: bool = False
    BaudRate_800: bool = False
    BaudRate_1000: bool = False
    BaudRate_auto: bool = False
    SimpleBootUpMaster: bool = False
    SimpleBootUpSlave: bool = False
    Granularity: int = 8
    DynamicChannelsSupported: bool = False
    CompactPDO: int = 0
    GroupMessaging: bool = False
    NrOfRXPDO: int = 0
    NrOfTXPDO: int = 0
    LSS_Supported: bool = False
    LSS_Master: bool = False
    NG_Slave: bool = False
    NG_Master: bool = False
    NrOfNG_MonitoredNodes: int = 0

    def __post_init__(self):
        self.infoheader = "CAN OPEN DeviceInfo"
        self.edssection = "DeviceInfo"

    def parse(self, section: dict[str, str]) -> None:
        self._section = section
        self.get_field("VendorName", "VendorName", str)
        self.get_field("VendorNumber", "VendorNumber", str)
        self.get_field("ProductName", "ProductName", str)
        self.get_field("ProductNumber", "ProductNumber", str)
        self.get_field("RevisionNumber", "RevisionNumber", int)
        for br in ["10", "20", "50", "125", "250", "500", "800", "1000"]:
            self.get_field(f"BaudRate_{br}", f"BaudRate_{br}", bool)
        self.get_field("SimpleBootUpMaster", "SimpleBootUpMaster", bool)
        self.get_field("SimpleBootUpSlave", "SimpleBootUpSlave", bool)
        self.get_field("Granularity", "Granularity", int)
        self.get_field("DynamicChannelsSupported", "DynamicChannelsSupported", bool)
        self.get_field("CompactPDO", "CompactPDO", int)
        self.get_field("GroupMessaging", "GroupMessaging", bool)
        self.get_field("NrOfRXPDO", "NrOfRXPDO", int)
        self.get_field("NrOfTXPDO", "NrOfTXPDO", int)
        self.get_field("LSS_Supported", "LSS_Supported", bool)


@dataclass
class DeviceCommissioning(InfoSection):
    NodeID: int = 0
    NodeName: str = ""
    Baudrate: int = 0
    NetNumber: int = 0
    NetworkName: str = ""
    CANopenManager: bool = False
    LSS_SerialNumber: int = 0

    def __post_init__(self):
        self.infoheader = "CAN OPEN DeviceCommissioning"
        self.edssection = "DeviceComissioning"

    def parse(self, section: dict[str, str]) -> None:
        self._section = section
        self.get_field("NodeID", "NodeID", int)
        self.get_field("NodeName", "NodeName", str)
        self.get_field("Baudrate", "Baudrate", int)
        self.get_field("NetNumber", "NetNumber", int)
        self.get_field("NetworkName", "NetworkName", str)
        self.get_field("CANopenManager", "CANopenManager", bool)
        self.get_field("LSS_SerialNumber", "LSS_SerialNumber", int)


@dataclass
class DummyUsage(InfoSection):
    Dummy0001: bool = False
    Dummy0002: bool = False
    Dummy0003: bool = False
    Dummy0004: bool = False
    Dummy0005: bool = False
    Dummy0006: bool = False
    Dummy0007: bool = False

    def __post_init__(self):
        self.infoheader = "CAN OPEN Dummy Usage"
        self.edssection = "DummyUsage"

    def parse(self, section: dict[str, str]) -> None:
        self._section = section
        for i in range(1, 8):
            self.get_field(f"Dummy000{i}", f"Dummy000{i}", bool)


@dataclass
class SupportedObjects:
    objectlist: dict[int, int] = field(default_factory=dict)
    infoheader: str = "Supported Objects"
    edssection: str = ""
    countmsg: str = "SupportedObjects"


@dataclass
class MandatoryObjects(SupportedObjects):
    def __post_init__(self):
        self.infoheader = "Mandatory Objects"
        self.edssection = "MandatoryObjects"


@dataclass
class OptionalObjects(SupportedObjects):
    def __post_init__(self):
        self.infoheader = "Optional Objects"
        self.edssection = "OptionalObjects"


@dataclass
class ManufacturerObjects(SupportedObjects):
    def __post_init__(self):
        self.infoheader = "Manufacturer Objects"
        self.edssection = "ManufacturerObjects"


@dataclass
class TypeDefinitions(SupportedObjects):
    def __post_init__(self):
        self.infoheader = "Type Definitions"
        self.edssection = "TypeDefinitions"


@dataclass
class Comments:
    comments: list[str] = field(default_factory=list)
    infoheader: str = "Comments"
    edssection: str = "Comments"


@dataclass
class SupportedModules(InfoSection):
    NrOfEntries: int = 0

    def __post_init__(self):
        self.infoheader = "CAN OPEN Supported Modules"
        self.edssection = "SupportedModules"


@dataclass
class ConnectedModules:
    connectedmodulelist: dict[int, int] = field(default_factory=dict)
    infoheader: str = "CAN OPEN Connected Modules"
    edssection: str = "ConnectedModules"
    countmsg: str = "NrOfEntries"

    @property
    def NrOfEntries(self) -> int:
        return len(self.connectedmodulelist)


@dataclass
class ModuleInfo(InfoSection):
    ProductName: str = ""
    ProductVersion: int = 0
    ProductRevision: int = 0
    OrderCode: str = ""
    _moduleindex: int = 0

    def __post_init__(self):
        self.infoheader = f"CAN OPEN Module Info {self._moduleindex}"
        self.edssection = f"M{self._moduleindex}ModuleInfo"

    def parse(self, section: dict[str, str]) -> None:
        self._section = section
        self.get_field("ProductName", "ProductName", str)
        self.get_field("ProductVersion", "ProductVersion", int)
        self.get_field("ProductRevision", "ProductRevision", int)
        self.get_field("OrderCode", "OrderCode", str)


@dataclass
class ModuleComments(Comments):
    _moduleindex: int = 0

    def __post_init__(self):
        self.infoheader = f"CAN OPEN Module Comments {self._moduleindex}"
        self.edssection = f"M{self._moduleindex}Comments"


@dataclass
class ModuleSubExtends(SupportedObjects):
    _moduleindex: int = 0

    def __post_init__(self):
        self.infoheader = f"CAN OPEN ModuleSubExtends {self._moduleindex}"
        self.edssection = f"M{self._moduleindex}SubExtends"


@dataclass
class MxFixedObjects(SupportedObjects):
    connectedmodulelist: dict[int, int] = field(default_factory=dict)
    _moduleindex: int = 0

    @property
    def NrOfEntries(self) -> int:
        return len(self.connectedmodulelist)

    def __post_init__(self):
        self.infoheader = "CAN OPEN Module Fixed Objects"
        self.edssection = f"M{self._moduleindex}FixedObjects"
        self.countmsg = "NrOfEntries"


@dataclass
class Module:
    mi: Optional[ModuleInfo] = None
    mc: Optional[ModuleComments] = None
    mse: Optional[ModuleSubExtends] = None
    mxfo: Optional[MxFixedObjects] = None
    modulefixedobjects: dict[int, object] = field(default_factory=dict)
    modulesubext: dict[int, object] = field(default_factory=dict)
    moduleindex: int = 0

    def __post_init__(self):
        self.mi = ModuleInfo(_moduleindex=self.moduleindex)
        self.mc = ModuleComments(_moduleindex=self.moduleindex)
        self.mse = ModuleSubExtends(_moduleindex=self.moduleindex)
        self.mxfo = MxFixedObjects(_moduleindex=self.moduleindex)