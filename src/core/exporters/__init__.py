"""导出器包"""
from .exporter_factory import ExporterDescriptor, ExporterFlags, Filetypes, IFileExporter
from .canopen_node_exporter_v4 import CanOpenNodeExporterV4
from .documentation_gen_markup import DocumentationGenMarkup
from .documentation_gen_html import DocumentationGenHtml
from .network_pdo_report import NetworkPDOreport
from .network_xdd_exporter import NetworkXDDExporter
from .xdd_exporter import XDDExporter

Filetypes.register(CanOpenNodeExporterV4)
Filetypes.register(DocumentationGenMarkup)
Filetypes.register(DocumentationGenHtml)
Filetypes.register(NetworkPDOreport)
Filetypes.register(NetworkXDDExporter)
Filetypes.register(XDDExporter)

try:
    from .protobuf_handler import ProtobufExporter, ProtobufJsonExporter
    Filetypes.register(ProtobufExporter)
    Filetypes.register(ProtobufJsonExporter)
    _PROTOBUF_AVAILABLE = True
except Exception:
    _PROTOBUF_AVAILABLE = False

__all__ = [
    "ExporterDescriptor",
    "ExporterFlags",
    "Filetypes",
    "IFileExporter",
    "CanOpenNodeExporterV4",
    "DocumentationGenMarkup",
    "DocumentationGenHtml",
    "NetworkPDOreport",
    "NetworkXDDExporter",
    "XDDExporter",
]
