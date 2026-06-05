"""CANopen 数据类型枚 CiA 301"""
from enum import IntEnum


class DataType(IntEnum):
    UNKNOWN = 0
    BOOLEAN = 1
    INTEGER8 = 2
    INTEGER16 = 3
    INTEGER32 = 4
    UNSIGNED8 = 5
    UNSIGNED16 = 6
    UNSIGNED32 = 7
    REAL32 = 8
    VISIBLE_STRING = 9
    OCTET_STRING = 0x0A
    UNICODE_STRING = 0x0B
    TIME_OF_DAY = 0x0C
    TIME_DIFFERENCE = 0x0D
    DOMAIN = 0x0F
    INTEGER24 = 0x10
    REAL64 = 0x11
    INTEGER40 = 0x12
    INTEGER48 = 0x13
    INTEGER56 = 0x14
    INTEGER64 = 0x15
    UNSIGNED24 = 0x16
    UNSIGNED40 = 0x18
    UNSIGNED48 = 0x19
    UNSIGNED56 = 0x1A
    UNSIGNED64 = 0x1B
    PDO_COMMUNICATION_PARAMETER = 0x20
    PDO_MAPPING = 0x21
    SDO_PARAMETER = 0x22
    IDENTITY = 0x23


class ObjectType(IntEnum):
    UNKNOWN = -1
    NULL = 0
    DOMAIN = 2
    DEFTYPE = 5
    DEFSTRUCT = 6
    VAR = 7
    ARRAY = 8
    RECORD = 9


class PDOMappingType(IntEnum):
    NO = 0
    OPTIONAL = 1
    RPDO = 2
    TPDO = 3
    DEFAULT = 4


class AccessType(IntEnum):
    RW = 0
    RO = 1
    WO = 2
    RWR = 3
    RWW = 4
    CONST = 5
    UNKNOWN = 6


class AccessSDO(IntEnum):
    NO = 0
    RO = 1
    WO = 2
    RW = 3


class AccessPDO(IntEnum):
    NO = 0
    T = 1
    R = 2
    TR = 3


class AccessSRDO(IntEnum):
    NO = 0
    TX = 1
    RX = 2
    TRX = 3


DATA_TYPE_SIZE_BITS = {
    DataType.BOOLEAN: 1,
    DataType.UNSIGNED8: 8,
    DataType.INTEGER8: 8,
    DataType.UNSIGNED16: 16,
    DataType.INTEGER16: 16,
    DataType.UNSIGNED24: 24,
    DataType.INTEGER24: 24,
    DataType.UNSIGNED32: 32,
    DataType.INTEGER32: 32,
    DataType.REAL32: 32,
    DataType.UNSIGNED40: 40,
    DataType.INTEGER40: 40,
    DataType.UNSIGNED48: 48,
    DataType.INTEGER48: 48,
    DataType.TIME_OF_DAY: 48,
    DataType.TIME_DIFFERENCE: 48,
    DataType.UNSIGNED56: 56,
    DataType.INTEGER56: 56,
    DataType.UNSIGNED64: 64,
    DataType.INTEGER64: 64,
    DataType.REAL64: 64,
}