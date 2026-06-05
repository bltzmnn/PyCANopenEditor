"""文档导出器、CLI 和新功能测试"""
import os
import tempfile

import pytest

from src.core.models.datatypes import AccessType, DataType, ObjectType, PDOMappingType
from src.core.models.eds import EDS
from src.core.models.od_entry import ODentry
from src.core.exporters.documentation_gen_markup import DocumentationGenMarkup
from src.core.exporters.documentation_gen_html import DocumentationGenHtml
from src.core.exporters.exporter_factory import Filetypes


def _make_test_eds() -> EDS:
    eds = EDS()
    eds.projectFilename = "test.eds"
    eds.fi.FileVersion = "1"
    eds.fi.Description = "Test device"
    eds.di.VendorName = "TestVendor"
    eds.di.ProductName = "TestProduct"
    eds.di.ProductNumber = "0x1234"
    eds.di.BaudRate_1000 = True

    od = ODentry(
        parameter_name="Device type",
        index=0x1000,
        datatype=DataType.UNSIGNED32,
        defaultvalue="0x00000000",
        accesstype=AccessType.RO,
    )
    od.prop.CO_storageGroup = "ROM"
    eds.ods[0x1000] = od

    od2 = ODentry(
        parameter_name="Error register",
        index=0x1001,
        datatype=DataType.UNSIGNED8,
        defaultvalue="0x00",
        accesstype=AccessType.RO,
    )
    eds.ods[0x1001] = od2

    return eds


class TestDocumentationGenMarkup:
    def test_export_produces_file(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "doc.md")
            DocumentationGenMarkup()._gen_md_doc(filepath, eds)
            assert os.path.exists(filepath)

    def test_md_contains_device_info(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "doc.md")
            DocumentationGenMarkup()._gen_md_doc(filepath, eds)
            with open(filepath) as f:
                content = f.read()
            assert "TestProduct" in content
            assert "TestVendor" in content

    def test_md_contains_od_entries(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "doc.md")
            DocumentationGenMarkup()._gen_md_doc(filepath, eds)
            with open(filepath) as f:
                content = f.read()
            assert "0x1000" in content
            assert "Device type" in content

    def test_md_contains_baud_rates(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "doc.md")
            DocumentationGenMarkup()._gen_md_doc(filepath, eds)
            with open(filepath) as f:
                content = f.read()
            assert "1000 kBit/s" in content
            assert "[x]" in content


class TestDocumentationGenHtml:
    def test_export_produces_file(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "doc.html")
            DocumentationGenHtml()._gen_html_doc(filepath, eds)
            assert os.path.exists(filepath)

    def test_html_contains_device_info(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "doc.html")
            DocumentationGenHtml()._gen_html_doc(filepath, eds)
            with open(filepath) as f:
                content = f.read()
            assert "TestProduct" in content
            assert "<table" in content

    def test_html_contains_od_entries(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "doc.html")
            DocumentationGenHtml()._gen_html_doc(filepath, eds)
            with open(filepath) as f:
                content = f.read()
            assert "0x1000" in content
            assert "Device type" in content


class TestExporterRegistrationFull:
    def test_markup_registered(self):
        exporters = Filetypes.find_by_extension(".md")
        descriptions = [e.description for e in exporters]
        assert "Documentation Markup" in descriptions

    def test_html_registered(self):
        exporters = Filetypes.find_by_extension(".html")
        descriptions = [e.description for e in exporters]
        assert "Documentation HTML" in descriptions

    def test_canopen_node_registered(self):
        exporters = Filetypes.find_by_extension(".h")
        descriptions = [e.description for e in exporters]
        assert "CanOpenNode" in descriptions
        assert "CanOpenNodeV4" in descriptions

    def test_eds_registered(self):
        from src.core.models.info_section import Filetype
        exporters = Filetypes.find_by_extension(".eds")
        # EDS/DCF exporters are in EDS.GetExporters(), not in Filetypes registry
        # So we test via EDS directly
        eds = EDS()
        exp_list = eds.GetExporters()
        descriptions = [e.description for e in exp_list]
        assert any("Electronic Data Sheet" in d for d in descriptions)

    def test_dcf_registered(self):
        eds = EDS()
        exp_list = eds.GetExporters()
        descriptions = [e.description for e in exp_list]
        assert any("Device Configuration" in d for d in descriptions)


class TestCLI:
    def test_eds_to_eds_roundtrip(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            infile = os.path.join(tmpdir, "input.eds")
            outfile = os.path.join(tmpdir, "output.eds")

            from src.core.parsers.eds_parser import EDSWriter
            from src.core.models.info_section import Filetype
            EDSWriter(eds).savefile(infile, Filetype.FILE_EDS)

            from src.cli.main import main
            result = main(["--infile", infile, "--outfile", outfile])
            assert result == 0
            assert os.path.exists(outfile)

    def test_eds_to_md_export(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            infile = os.path.join(tmpdir, "input.eds")
            outfile = os.path.join(tmpdir, "doc.md")

            from src.core.parsers.eds_parser import EDSWriter
            from src.core.models.info_section import Filetype
            EDSWriter(eds).savefile(infile, Filetype.FILE_EDS)

            from src.cli.main import main
            result = main(["--infile", infile, "--outfile", outfile])
            assert result == 0
            assert os.path.exists(outfile)
            with open(outfile) as f:
                assert "TestProduct" in f.read()

    def test_list_exporters(self):
        from src.cli.main import main
        result = main(["--list-exporters"])
        assert result == 0

    def test_invalid_exporter_type(self):
        eds = _make_test_eds()
        with tempfile.TemporaryDirectory() as tmpdir:
            infile = os.path.join(tmpdir, "input.eds")

            from src.core.parsers.eds_parser import EDSWriter
            from src.core.models.info_section import Filetype
            EDSWriter(eds).savefile(infile, Filetype.FILE_EDS)

            from src.cli.main import main
            result = main(["--infile", infile, "--outfile", os.path.join(tmpdir, "out.h"),
                           "--type", "NonExistent"])
            assert result == 1
