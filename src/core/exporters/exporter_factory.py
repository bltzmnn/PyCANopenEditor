"""导出器描述符和注册工厂，对应 C# ExporterDescriptor/IFileExporter/Filetypes"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntFlag
from typing import Callable, List

from ..models.eds import EDS


class ExporterFlags(IntFlag):
    MultipleNodeSupport = 1
    Documentation = 2
    CanOpenNode = 3


ExportFunc = Callable[[str, List[EDS]], None]


@dataclass
class ExporterDescriptor:
    description: str
    filetypes: list[str]
    flags: ExporterFlags
    func: ExportFunc


class IFileExporter:
    """导出器接口，对应 C# IFileExporter"""

    def get_exporters(self) -> list[ExporterDescriptor]:
        raise NotImplementedError


class Filetypes:
    """导出器注册表，对应 C# Filetypes"""

    _exporter_classes: list[type] = []

    @classmethod
    def register(cls, exporter_class: type) -> None:
        if exporter_class not in cls._exporter_classes:
            cls._exporter_classes.append(exporter_class)

    @classmethod
    def get_exporters(cls, flags: ExporterFlags = 0) -> list[ExporterDescriptor]:
        exporters: list[ExporterDescriptor] = []
        for exporter_class in cls._exporter_classes:
            try:
                instance = exporter_class()
                for exp in instance.get_exporters():
                    if (exp.flags & flags) or flags == 0:
                        exporters.append(exp)
            except Exception:
                continue
        return exporters

    @classmethod
    def find_by_extension(cls, extension: str) -> list[ExporterDescriptor]:
        all_exporters = cls.get_exporters()
        return [e for e in all_exporters if extension in e.filetypes]

    @classmethod
    def find_by_description(cls, description: str) -> ExporterDescriptor | None:
        all_exporters = cls.get_exporters()
        for e in all_exporters:
            if e.description.replace(" ", "") == description.replace(" ", ""):
                return e
        return None