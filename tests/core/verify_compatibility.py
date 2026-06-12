"""兼容性验证：加载 EDS → V4 导出 → 与 C# 参考输出对比。

通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量指定包含参考输出 (OD.h / OD.c)
的设备目录树。脚本会逐个遍历子目录：
  - 解析子目录里的 `.eds` 或 `.xdd`
  - 加载 `OD.h` / `OD.c` 作为 C# 参考输出
  - 解析 V4 导出结果，与参考输出逐字段对比

未设置环境变量时脚本直接打印提示并退出。
"""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.models.eds import EDS
from src.core.parsers.eds_parser import EDSParser
from src.core.parsers.xdd_handler import XDDHandler
from src.core.exporters.canopen_node_exporter_v4 import CanOpenNodeExporterV4

BASE = os.environ.get("PYCANOPEN_TEST_EDS_DIR", "").strip()
BASE = os.path.abspath(BASE) if BASE else ""


def load_eds(filepath: str) -> EDS:
    eds = EDS()
    parser = EDSParser(eds)
    parser.loadfile(filepath)
    return eds


def load_xdd(filepath: str) -> EDS:
    handler = XDDHandler()
    eds = handler.read_xml(filepath)
    if eds is None:
        raise ValueError(f"无法加载 XDD: {filepath}")
    return eds


def export_v4(eds: EDS, tmpdir: str) -> tuple[str, str]:
    exporter = CanOpenNodeExporterV4()
    exporter._export(os.path.join(tmpdir, "OD"), eds)
    with open(os.path.join(tmpdir, "OD.h")) as f:
        h = f.read()
    with open(os.path.join(tmpdir, "OD.c")) as f:
        c = f.read()
    return h, c


def extract_od_list(content: str) -> list[tuple[str, str, str]]:
    """从 V4 的 .c 文件提取 ODList 条目 (index, count, type)"""
    pattern = r'\{0x([0-9A-Fa-f]+),\s*0x([0-9A-Fa-f]+),\s*(ODT_\w+),'
    return re.findall(pattern, content)


def extract_cnt_arr(content: str) -> dict[str, str]:
    """提取 OD_CNT_ARR_* 定义（跳过 #ifndef 保护的 fallback 定义）"""
    result = {}
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#ifndef") and "CNT_ARR_" in line:
            i += 3
            continue
        m = re.match(r'#define\s+(OD_CNT_ARR_\w+)\s+(\d+)', line)
        if m:
            result[m.group(1)] = m.group(2)
        i += 1
    return result


def extract_storage_structs(content: str) -> dict[str, list[str]]:
    """提取 .h 文件中 typedef struct 的成员列表

    用花括号配对的方式定位 typedef struct { ... } NAME_t; 边界，
    以正确处理嵌套的 RECORD struct（如 x1018_identity）。
    """
    result = {}
    for m in re.finditer(r'\} (\w+)_t;', content):
        name = m.group(1)
        end = m.start()
        depth = 1
        i = end - 1
        while i >= 0 and depth > 0:
            ch = content[i]
            if ch == '}':
                depth += 1
            elif ch == '{':
                depth -= 1
            i -= 1
        if depth != 0:
            continue
        start = i + 2
        body = content[start:end]
        members = [
            line.strip().rstrip(";").strip()
            for line in body.split("\n")
            if line.strip() and not line.strip().startswith("//")
        ]
        result[name] = members
    return result


def extract_entry_shortcuts(content: str) -> dict[str, str]:
    """提取 OD_ENTRY_H* 定义（跳过 #ifndef 保护的 fallback 定义）"""
    result = {}
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#ifndef") and "ENTRY_H" in line:
            i += 3
            continue
        m = re.match(r'#define\s+(OD_ENTRY_\w+)\s+([^\\\n]+)', line)
        if m:
            result[m.group(1)] = m.group(2).strip()
        i += 1
    return result


def compare_od_list(py_entries: list, cs_entries: list) -> dict:
    """对比 OD 列表"""
    py_map = {e[0].upper(): e for e in py_entries}
    cs_map = {e[0].upper(): e for e in cs_entries}

    result = {"match": True, "details": []}
    py_indices = set(py_map.keys())
    cs_indices = set(cs_map.keys())

    missing = cs_indices - py_indices
    extra = py_indices - cs_indices
    if missing:
        result["match"] = False
        result["details"].append(f"Python 缺少索引: {sorted(missing)}")
    if extra:
        result["match"] = False
        result["details"].append(f"Python 多出索引: {sorted(extra)}")

    for idx in sorted(cs_indices & py_indices):
        py_e = py_map[idx]
        cs_e = cs_map[idx]
        if py_e[1] != cs_e[1]:
            result["details"].append(f"0x{idx}: subEntries 不同 py=0x{py_e[1]} cs=0x{cs_e[1]}")
        if py_e[2] != cs_e[2]:
            result["details"].append(f"0x{idx}: type 不同 py={py_e[2]} cs={cs_e[2]}")

    result["py_count"] = len(py_entries)
    result["cs_count"] = len(cs_entries)
    return result


def compare_cnt_arr(py_map: dict, cs_map: dict) -> dict:
    """对比 OD_CNT_ARR_ 定义"""
    result = {"match": True, "details": []}
    missing = set(cs_map.keys()) - set(py_map.keys())
    extra = set(py_map.keys()) - set(cs_map.keys())
    if missing:
        result["match"] = False
        result["details"].append(f"Python 缺少: {sorted(missing)}")
    if extra:
        result["match"] = False
        result["details"].append(f"Python 多出: {sorted(extra)}")
    for k in sorted(set(py_map.keys()) & set(cs_map.keys())):
        if py_map[k] != cs_map[k]:
            result["details"].append(f"{k}: py={py_map[k]} cs={cs_map[k]}")
    result["py_count"] = len(py_map)
    result["cs_count"] = len(cs_map)
    return result


def compare_storage_structs(py_structs: dict, cs_structs: dict) -> dict:
    """对比 storage struct 定义（按成员名匹配，忽略顺序和格式差异）"""
    result = {"match": True, "details": []}
    missing = set(cs_structs.keys()) - set(py_structs.keys())
    extra = set(py_structs.keys()) - set(cs_structs.keys())
    if missing:
        result["match"] = False
        result["details"].append(f"Python 缺少 struct: {sorted(missing)}")
    if extra:
        result["match"] = False
        result["details"].append(f"Python 多出 struct: {sorted(extra)}")
    for name in sorted(set(py_structs.keys()) & set(cs_structs.keys())):
        # 按成员名对比（忽略格式细节如缩进和struct内嵌方式）
        def extract_member_names(members):
            names = set()
            for m in members:
                m = m.strip()
                if not m or m.startswith("//"):
                    continue
                # 提取变量名（如 "uint32_t x1000_deviceType" -> "x1000_deviceType"）
                # 或 "struct { ... } x1018_identity;" -> "x1018_identity"
                parts = m.split()
                if parts:
                    last = parts[-1].rstrip(";")
                    # 去掉数组部分如 [OD_CNT_ARR_1003]
                    last = re.sub(r'\[.*?\]', '', last)
                    names.add(last)
            return names
        
        py_names = extract_member_names(py_structs[name])
        cs_names = extract_member_names(cs_structs[name])
        
        if py_names != cs_names:
            result["match"] = False
            only_py = sorted(py_names - cs_names)
            only_cs = sorted(cs_names - py_names)
            if only_py:
                result["details"].append(f"struct {name}: Python 多出成员 {only_py[:10]}")
            if only_cs:
                result["details"].append(f"struct {name}: Python 缺少成员 {only_cs[:10]}")
    result["py_count"] = len(py_structs)
    result["cs_count"] = len(cs_structs)
    return result


def verify_device(dirpath: str) -> dict:
    """验证一个设备目录。

    支持两种布局：
      1) `<dirpath>/foo.eds` + `<dirpath>/OD.h` + `<dirpath>/OD.c`
      2) `<parent>/foo.eds` + `<dirpath>/OD.h` + `<dirpath>/OD.c`
         （即 EDS/XDD 放在子目录同名的父级兄弟位置）
    """
    name = os.path.basename(dirpath.rstrip("/"))
    parent = os.path.dirname(dirpath.rstrip("/"))
    files = os.listdir(dirpath)
    cs_h = os.path.join(dirpath, "OD.h") if "OD.h" in files else None
    cs_c = os.path.join(dirpath, "OD.c") if "OD.c" in files else None

    eds_candidates: list[str] = []
    for fname in os.listdir(parent) if os.path.isdir(parent) else []:
        stem, ext = os.path.splitext(fname)
        if stem == name and ext.lower() in (".eds", ".xdd"):
            eds_candidates.append(os.path.join(parent, fname))
    for fname in files:
        if fname.endswith(".eds") or fname.endswith(".xdd"):
            eds_candidates.append(os.path.join(dirpath, fname))

    eds_path = next(
        (p for p in eds_candidates if p.endswith(".eds")), None
    )
    xdd_path = next(
        (p for p in eds_candidates if p.endswith(".xdd")), None
    )

    result = {"device": name, "load_ok": False, "export_ok": False, "comparisons": {}}

    eds = None
    if eds_path:
        try:
            eds = load_eds(eds_path)
            result["load_ok"] = True
            result["od_count"] = len(eds.ods)
        except Exception as e:
            result["load_error"] = str(e)
            return result
    elif xdd_path:
        try:
            eds = load_xdd(xdd_path)
            result["load_ok"] = True
            result["od_count"] = len(eds.ods)
        except Exception as e:
            result["load_error"] = str(e)
            return result

    if eds is None:
        result["load_error"] = "没有 EDS 或 XDD 文件"
        return result

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            py_h, py_c = export_v4(eds, tmpdir)
        result["export_ok"] = True
    except Exception as e:
        result["export_error"] = str(e)
        return result

    if cs_h and cs_c:
        with open(cs_h) as f:
            cs_h_content = f.read()
        with open(cs_c) as f:
            cs_c_content = f.read()

        result["comparisons"]["od_list"] = compare_od_list(
            extract_od_list(py_c), extract_od_list(cs_c_content)
        )
        result["comparisons"]["cnt_arr"] = compare_cnt_arr(
            extract_cnt_arr(py_h), extract_cnt_arr(cs_h_content)
        )
        result["comparisons"]["storage_structs"] = compare_storage_structs(
            extract_storage_structs(py_h), extract_storage_structs(cs_h_content)
        )

    return result


def main():
    if not BASE or not os.path.isdir(BASE):
        print(f"环境变量 PYCANOPEN_TEST_EDS_DIR 未设置或路径无效: {BASE!r}")
        print("请将包含设备子目录（含 .eds / OD.h / OD.c）的根目录赋值给该变量。")
        return 1

    devices = sorted([d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE, d))])

    total_pass = 0
    total_fail = 0

    for device in devices:
        dirpath = os.path.join(BASE, device)
        result = verify_device(dirpath)
        print(f"\n{'='*60}")
        print(f"设备: {result['device']}")
        print(f"  加载: {'OK' if result['load_ok'] else 'FAIL ' + result.get('load_error', '')}")
        if result.get("od_count"):
            print(f"  OD 条目: {result['od_count']}")
        print(f"  导出: {'OK' if result['export_ok'] else 'FAIL ' + result.get('export_error', '')}")

        comparisons = result.get("comparisons", {})
        all_match = True
        for key, comp in comparisons.items():
            py_c = comp.get("py_count", "?")
            cs_c = comp.get("cs_count", "?")
            is_match = comp.get("match", True)
            details = comp.get("details", [])

            status = "MATCH" if is_match and not details else "DIFF"
            print(f"  {key}: {status} (py={py_c}, cs={cs_c})")
            if details:
                all_match = False
                for d in details[:5]:
                    print(f"    - {d}")
                if len(details) > 5:
                    print(f"    ... 共 {len(details)} 个差异")

        if result['load_ok'] and result['export_ok'] and all_match:
            total_pass += 1
            print(f"  >>> 完全匹配!")
        else:
            total_fail += 1

    print(f"\n{'='*60}")
    print(f"总计: {total_pass} 完全匹配, {total_fail} 有差异 (共 {total_pass + total_fail} 个设备)")


if __name__ == "__main__":
    main()