"""HTML 文档导出器，对应 C# DocumentationGenHtml"""
from __future__ import annotations

import os
from typing import Optional

from ..models.datatypes import DataType, ObjectType
from ..models.eds import EDS
from ..models.od_entry import ODentry
from .exporter_factory import ExporterDescriptor, ExporterFlags, IFileExporter


class DocumentationGenHtml(IFileExporter):
    """HTML 文档导出器"""

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "Documentation HTML",
                [".html"],
                ExporterFlags.Documentation,
                lambda filepath, eds_list: DocumentationGenHtml()._gen_html_doc(filepath, eds_list[0]),
            )
        ]

    def _gen_html_doc(self, filepath: str, eds: EDS) -> None:
        with open(filepath, "w", newline="\n") as f:
            f.write("<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                    "<link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\" /></head><body>")

            f.write(f"<h1> {eds.di.ProductName} Documentation </h1>")

            f.write("<h2>Device Information</h2>")
            f.write("<table id=\"deviceinfo\">")
            self._write_table_header(f, "Product name", eds.di.ProductName)
            self._write_table_header(f, "Product number", eds.di.ProductNumber)
            self._write_table_header(f, "Revision number", str(eds.di.RevisionNumber))
            self._write_table_header(f, "Vendor name", eds.di.VendorName)
            f.write("</table>")

            f.write("<h2>Mandatory objects</h2>")
            for od in eds.ods.values():
                if od.prop.CO_disabled:
                    continue
                if od.index in (0x1000, 0x1001, 0x1018):
                    self._write_od_entry_html(f, od)

            f.write("<h2>Optional objects</h2>")
            for od in eds.ods.values():
                if od.prop.CO_disabled:
                    continue
                if (0x1001 < od.index < 0x2000 and od.index != 0x1018) or od.index >= 0x6000:
                    self._write_od_entry_html(f, od)

            f.write("<h2>Manufacturer specific objects</h2>")
            for od in eds.ods.values():
                if od.prop.CO_disabled:
                    continue
                if 0x2000 <= od.index < 0x6000:
                    self._write_od_entry_html(f, od)

            f.write("</body></html>")

    def _write_od_entry_html(self, f, od: ODentry) -> None:
        if od.parent is None:
            f.write("<hr/>")
            f.write(f"<h3>0x{od.index:04x} - {od.parameter_name}</h3>")
        else:
            f.write(f"<h3>0x{od.index:04x} sub 0x{od.Subindex:02x} - {od.parameter_name}</h3>")

        f.write("<table id=\"odentry\">")
        self._write_table_header(f, "Parameter", "Value")

        obj_type = od.objecttype
        if obj_type == ObjectType.UNKNOWN and od.parent is not None:
            obj_type = od.parent.objecttype

        data_type = od.datatype
        if data_type == DataType.UNKNOWN and od.parent is not None:
            data_type = od.parent.datatype

        self._write_table_row(f, "Object Type", obj_type.name)
        self._write_table_row(f, "Data Type", data_type.name)
        self._write_table_row(f, "Default Value", od.defaultvalue)
        self._write_table_row(f, "Location", od.prop.CO_storageGroup)
        self._write_table_row(f, "Access type", od.accesstype.name)
        self._write_table_row(f, "PDO mapping", str(od.PDOMapping))
        self._write_table_row(f, "No Sub index", str(od.Nosubindexes))

        f.write("</table>")

        if od.Description:
            f.write(f"<pre>{od.Description}</pre>")

        for sub_od in od.subobjects.values():
            self._write_od_entry_html(f, sub_od)

    def _write_table_row(self, f, a: str, b: object) -> None:
        f.write(f"<tr><td>{a}</td><td>{str(b) if b else ''}</td></tr>")

    def _write_table_header(self, f, a: str, b: object) -> None:
        f.write(f"<tr><th>{a}</th><th>{str(b) if b else ''}</th></tr>")