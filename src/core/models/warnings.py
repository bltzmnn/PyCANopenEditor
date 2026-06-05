"""警告系统，对应 C# Warnings"""
from enum import IntFlag


class WarningClass(IntFlag):
    WARNING_GENERIC = 0x01
    WARNING_RENAME = 0x02
    WARNING_BUILD = 0x04
    WARNING_STRING = 0x08
    WARNING_STRUCT = 0x10


class Warnings:
    warning_list: list[str] = []
    warning_mask: int = 0xFFFF

    @classmethod
    def add_warning(cls, warning: str, c: WarningClass = WarningClass.WARNING_GENERIC) -> None:
        if c & cls.warning_mask:
            cls.warning_list.append(warning)

    @classmethod
    def clear(cls) -> None:
        cls.warning_list.clear()