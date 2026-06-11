"""Network PDO 报告导出器，对应 C# NetworkPDOreport"""
from __future__ import annotations

from ..models.datatypes import DataType, ObjectType
from ..models.eds import EDS
from ..models.od_entry import ODentry, _convert_to_byte, _convert_to_uint16, _convert_to_uint32
from .exporter_factory import ExporterDescriptor, ExporterFlags, IFileExporter


class NetworkPDOreport(IFileExporter):
    """Network PDO 报告导出器"""

    def get_exporters(self) -> list[ExporterDescriptor]:
        return [
            ExporterDescriptor(
                "Network PDO Report",
                [".html"],
                ExporterFlags.Documentation | ExporterFlags.MultipleNodeSupport,
                lambda filepath, eds_list: NetworkPDOreport()._gen_net_pdo_doc(filepath, eds_list),
            )
        ]

    def _gen_net_pdo_doc(self, filepath: str, network: list[EDS]) -> None:
        with open(filepath, "w", newline="\n") as f:
            f.write("<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                    "<link rel=\"stylesheet\" type=\"text/css\" href=\"style.css\" /> "
                    "<title>Network PDO report</title></head><body>")

            f.write("<h1>PDO Network Documentation </h1>")

            f.write("<table id=\"nodelist\">")
            f.write("<tr><th>Node ID</th><th>Name</th></tr>")
            for eds in network:
                f.write(f"<tr><td>{eds.dc.NodeID}</td><td>{eds.di.ProductName}</td></tr>")
            f.write("</table>")

            f.write("<h1>PDO Map</h1>")

            for eds in network:
                for idx, od in eds.ods.items():
                    if not (0x1800 <= idx < 0x1A00):
                        continue

                    map_idx = idx + 0x200
                    if map_idx not in eds.ods:
                        continue

                    map_od = eds.ods[map_idx]
                    com_od = eds.ods[idx]

                    tx_cob = 0
                    sync_start = 0
                    timer = 0
                    inhibit = 0
                    tx_type = 0

                    if com_od.Containssubindex(1):
                        tx_cob, _ = eds.GetNodeID(com_od.Getsubobject(1).defaultvalue)
                    if com_od.Containssubindex(2):
                        tx_type = _convert_to_byte(com_od.Getsubobject(2).defaultvalue)
                    if com_od.Containssubindex(3):
                        inhibit = _convert_to_uint16(com_od.Getsubobject(3).defaultvalue)
                    if com_od.Containssubindex(5):
                        timer = _convert_to_uint16(com_od.Getsubobject(5).defaultvalue)
                    if com_od.Containssubindex(6):
                        sync_start = _convert_to_byte(com_od.Getsubobject(6).defaultvalue)

                    total_size = 0
                    max_sub = map_od.Getmaxsubindex()
                    for sub in range(1, max_sub + 1):
                        if not map_od.Containssubindex(sub):
                            continue
                        try:
                            mapping = _convert_to_uint32(map_od.Getsubobject(sub).defaultvalue)
                            if mapping == 0:
                                continue
                            size = mapping & 0xFF
                            total_size += size
                        except (ValueError, TypeError):
                            continue

                    if total_size == 0:
                        continue

                    f.write(f"<h2> PDO 0x{tx_cob:03x} </h2>")
                    f.write("<table><tr> <th>Parameter</th> <th>value</th> </tr>")
                    f.write(f"<tr><td>COB</td><td>0x{tx_cob:03x}</td></tr>")
                    f.write(f"<tr><td>Type</td><td>0x{tx_type:x}</td></tr>")
                    f.write(f"<tr><td>Inhibit</td><td>0x{inhibit:x} ({inhibit})</td></tr>")
                    f.write(f"<tr><td>Event timer</td><td>0x{timer:x} ({timer})</td></tr>")
                    f.write(f"<tr><td>Sync start</td><td>0x{sync_start:x} ({sync_start})</td></tr>")
                    f.write(f"<tr><td>PDO Size (Bytes)</td><td>0x{total_size // 8:x}</td></tr>")

                    f.write("<table class=\"pdomap\">")
                    f.write("<tr><th>Node</th><th>Dev name</th><th>OD Index</th>"
                            "<th>Name</th><th>Size</th><th>Receivers</th></tr>")

                    offset_end = 0
                    offset_start = 0

                    for sub in range(1, max_sub + 1):
                        if not map_od.Containssubindex(sub):
                            continue
                        dv = map_od.Getsubobject(sub).defaultvalue
                        if not dv:
                            continue
                        try:
                            mapping = _convert_to_uint32(dv)
                        except (ValueError, TypeError):
                            continue
                        if mapping == 0:
                            continue

                        index_val = (mapping >> 16) & 0xFFFF
                        subindex = (mapping >> 8) & 0xFF
                        size = mapping & 0xFF

                        if index_val not in eds.ods:
                            break

                        if subindex == 0:
                            name = eds.ods[index_val].parameter_name
                        elif subindex in eds.ods[index_val].subobjects:
                            name = eds.ods[index_val].subobjects[subindex].parameter_name
                        else:
                            name = eds.ods[index_val].parameter_name

                        f.write(f"<tr> <td>0x{eds.dc.NodeID:02x}</td> "
                                f"<td>{eds.di.ProductName}</td> "
                                f"<td>0x{index_val:04x}/0x{subindex:02x}</td>"
                                f"<td>{name}</td> <td>{size}</td><td>")

                        f.write("<table class=\"receivers\">")
                        f.write("<tr> <th>Node</th> <th>Dev Name</th> <th>OD Index</th> "
                                "<th>Name</th> <th>Size</th></tr>")

                        offset_end += size // 8

                        for eds2 in network:
                            if eds is eds2:
                                continue

                            for idx2, od2 in eds2.ods.items():
                                if not (0x1400 <= idx2 < 0x1600):
                                    continue
                                map_idx2 = idx2 + 0x200
                                if map_idx2 not in eds2.ods:
                                    continue

                                try:
                                    rx_cob, _ = eds2.GetNodeID(od2.Getsubobject(1).defaultvalue)
                                except (ValueError, KeyError):
                                    continue

                                if rx_cob != tx_cob:
                                    continue

                                map2 = eds2.ods[map_idx2]
                                offset_start2 = 0
                                offset_end2 = 0

                                total_size2 = 0
                                for sub2 in range(1, map2.Getmaxsubindex() + 1):
                                    try:
                                        mapping2 = _convert_to_uint32(map2.Getsubobject(sub2).defaultvalue)
                                        total_size2 += mapping2 & 0xFF
                                    except (ValueError, TypeError):
                                        continue

                                if total_size2 != total_size:
                                    f.write("<B> Critical error with network RX PDO size != TX PDO SIZE</B>")

                                for sub2 in range(1, map2.Getmaxsubindex() + 1):
                                    try:
                                        mapping2 = _convert_to_uint32(map2.Getsubobject(sub2).defaultvalue)
                                    except (ValueError, TypeError):
                                        continue
                                    if mapping2 == 0:
                                        continue

                                    index2 = (mapping2 >> 16) & 0xFFFF
                                    subindex2 = (mapping2 >> 8) & 0xFF
                                    size2 = mapping2 & 0xFF

                                    offset_end2 += size2 // 8

                                    if offset_start2 < offset_start:
                                        offset_start2 += size2 // 8
                                        continue

                                    if offset_end2 > offset_end and offset_start2 > offset_start:
                                        break

                                    offset_start2 += size2 // 8

                                    od_entry2 = eds2.Getobject(index2)
                                    if od_entry2 is None:
                                        continue
                                    if subindex2 == 0:
                                        name2 = od_entry2.parameter_name
                                    else:
                                        sub_od2 = od_entry2.Getsubobject(subindex2)
                                        name2 = sub_od2.parameter_name if sub_od2 else ""

                                    size_msg = " <b>WARNING</b>" if size != size2 else ""

                                    f.write(f"<tr> <td>0x{eds2.dc.NodeID:02x}</td> "
                                            f"<td>{eds2.di.ProductName}</td> "
                                            f"<td>0x{index2:04x}/0x{subindex2:02x}</td> "
                                            f"<td>{name2}</td><td>{size2}{size_msg}</td></tr>")

                        offset_start += size // 8
                        f.write("</table>")
                        f.write("</td>")
                        f.write("</tr>")

                    f.write("</table>")

            f.write("</body></html>")
