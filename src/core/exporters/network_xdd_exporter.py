"""Network XDD/XDC 导出器，对应 C# CanOpenXDD_1_1 的 Network 导出"""
from __future__ import annotations

from ..models.eds import EDS
from ..parsers.xdd_handler import XDDHandler
from .exporter_factory import ExporterDescriptor, ExporterFlags, IFileExporter


class NetworkXDDExporter(IFileExporter):

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "CanOpen Network XDD v1.1",
                [".nxdd"],
                ExporterFlags.MultipleNodeSupport,
                lambda filepath, eds_list: NetworkXDDExporter()._export_nxdd(filepath, eds_list),
            ),
            ExporterDescriptor(
                "CanOpen Network XDC v1.1",
                [".nxdc"],
                ExporterFlags.MultipleNodeSupport,
                lambda filepath, eds_list: NetworkXDDExporter()._export_nxdc(filepath, eds_list),
            ),
        ]

    def _export_nxdd(self, filepath: str, eds_list: list[EDS]) -> None:
        handler = XDDHandler()
        handler.write_multi_xml(filepath, eds_list, device_commissioning=False)

    def _export_nxdc(self, filepath: str, eds_list: list[EDS]) -> None:
        handler = XDDHandler()
        handler.write_multi_xml(filepath, eds_list, device_commissioning=True)
