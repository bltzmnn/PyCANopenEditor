"""XDD/XDC 单文件导出器，对应 C# CanOpenXDD_1_1.GetExporters()"""
from __future__ import annotations

from ..models.eds import EDS
from ..parsers.xdd_handler import XDDHandler
from .exporter_factory import ExporterDescriptor, ExporterFlags, IFileExporter


class XDDExporter(IFileExporter):

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "CanOpenXDDv1.1",
                [".xdd"],
                ExporterFlags(0),
                lambda filepath, eds_list: XDDExporter()._export_xdd(filepath, eds_list[0]),
            ),
            ExporterDescriptor(
                "CanOpenXDDv1.1stripped",
                [".xdd"],
                ExporterFlags(0),
                lambda filepath, eds_list: XDDExporter()._export_xdd_stripped(filepath, eds_list[0]),
            ),
            ExporterDescriptor(
                "CanOpenXDCv1.1",
                [".xdc"],
                ExporterFlags(0),
                lambda filepath, eds_list: XDDExporter()._export_xdc(filepath, eds_list[0]),
            ),
        ]

    def _export_xdd(self, filepath: str, eds: EDS) -> None:
        handler = XDDHandler()
        handler.write_xml(filepath, eds, device_commissioning=False, stripped=False)

    def _export_xdd_stripped(self, filepath: str, eds: EDS) -> None:
        handler = XDDHandler()
        handler.write_xml(filepath, eds, device_commissioning=False, stripped=True)

    def _export_xdc(self, filepath: str, eds: EDS) -> None:
        handler = XDDHandler()
        handler.write_xml(filepath, eds, device_commissioning=True, stripped=False)