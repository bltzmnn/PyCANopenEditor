"""CANopenEditor CLI 工具，对应 C# EDS CLI"""
from __future__ import annotations

import argparse
import os
import sys

from ..core.models.eds import EDS
from ..core.parsers.eds_parser import EDSParser
from ..core.parsers.xdd_handler import XDDHandler
from ..core.exporters.exporter_factory import Filetypes, ExporterFlags


def _detect_loader(filepath: str) -> tuple[str, str]:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".eds", ".dcf"):
        return "eds", ext
    elif ext in (".xdd", ".xdc", ".xml"):
        return "xdd", ext
    else:
        return "unknown", ext


def _load_file(filepath: str) -> EDS:
    loader_type, ext = _detect_loader(filepath)
    if loader_type == "eds":
        eds = EDS()
        EDSParser(eds).loadfile(filepath)
        eds.edsfilename = filepath
        return eds
    elif loader_type == "xdd":
        handler = XDDHandler()
        eds = handler.read_xml(filepath)
        if eds is None:
            raise ValueError(f"无法加载 XDD/XDC 文件: {filepath}")
        eds.xddfilename_1_1 = filepath
        return eds
    else:
        raise ValueError(f"不支持的输入文件格式: {ext}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="canopeneditor",
        description="CANopenEditor - CANopen EDS/XDD 文件转换和导出工具",
    )
    parser.add_argument("--infile", default=None, help="输入文件路径 (EDS, DCF, XDD, XDC)")
    parser.add_argument("--outfile", default=None, help="输出文件路径")
    parser.add_argument("--type", default=None, dest="export_type",
                        help="导出器类型名称（当扩展名对应多个导出器时必须指定）")
    parser.add_argument("--list-exporters", action="store_true",
 help="列出所有可用导出器")

    args = parser.parse_args(argv)

    if args.list_exporters:
        print("可用导出器:")
        exporters = Filetypes.get_exporters()
        for exp in exporters:
            print(f"  {exp.description}: {', '.join(exp.filetypes)}")
        return 0

    if not args.infile or not args.outfile:
        parser.error("--infile 和 --outfile 是必需的（除非使用 --list-exporters）")

    try:
        eds = _load_file(args.infile)
    except Exception as e:
        print(f"错误: 无法加载输入文件: {e}", file=sys.stderr)
        return 1

    out_ext = os.path.splitext(args.outfile)[1].lower()
    out_dir = os.path.dirname(args.outfile) or "."

    # EDS/DCF 直接通过 EDS.Savefile 处理（仅在未指定 --type 时）
    if out_ext in (".eds", ".dcf") and not args.export_type:
        from ..core.models.info_section import Filetype
        ft = Filetype.FILE_EDS if out_ext == ".eds" else Filetype.FILE_DCF
        try:
            os.makedirs(out_dir, exist_ok=True)
            eds.Savefile(args.outfile, ft)
        except Exception as e:
            print(f"错误: 导出失败: {e}", file=sys.stderr)
            return 1
        print(f"成功导出: {args.outfile}")
        return 0

    if args.export_type:
        exporter = Filetypes.find_by_description(args.export_type)
        if exporter is None:
            print(f"错误: 找不到导出器 '{args.export_type}'", file=sys.stderr)
            print("可用导出器:")
            for exp in Filetypes.get_exporters():
                print(f"  {exp.description}: {', '.join(exp.filetypes)}")
            return 1
    else:
        matching = Filetypes.find_by_extension(out_ext)
        if not matching:
            print(f"错误: 没有支持扩展名 '{out_ext}' 的导出器", file=sys.stderr)
            return 1
        if len(matching) > 1:
            print(f"错误: 扩展名 '{out_ext}' 对应多个导出器，请使用 --type 指定:", file=sys.stderr)
            for exp in matching:
                print(f"  {exp.description}")
            return 1
        exporter = matching[0]

    try:
        os.makedirs(out_dir, exist_ok=True)
        exporter.func(args.outfile, [eds])
    except Exception as e:
        print(f"错误: 导出失败: {e}", file=sys.stderr)
        return 1

    print(f"成功导出: {args.outfile} ({exporter.description})")
    return 0


if __name__ == "__main__":
    sys.exit(main())