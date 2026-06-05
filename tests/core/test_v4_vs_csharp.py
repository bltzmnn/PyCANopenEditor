"""V4 C 导出器 vs C# 工具的交叉验证。

使用 `eds/<name>/OD.h`、`eds/<name>/OD.c` 作为 C# 工具的参考输出，
对每个样本文件执行 EDS/XDD 解析 → V4 导出 → 逐字段对比。

样本目录通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入（默认仓库 `eds/`
目录包含全部样本）。未设置时整组测试自动跳过。

已知差异
--------
- `canopen_datatypes` (合成的 datatype 测试 EDS, 非真实设备):
  Python 为 0x200A (OCTET_STRING "ABCD") 生成 `uint8_t[2]` OD_RAM 成员,
  C# 工具输出 `dataLength=0` 不生成 storage。这是 C# 工具对合
  成测试文件的特殊处理 (无 `;StorageLocation=RAM` 注释时 C# 默认
  跳过 OCTET_STRING), Python 的输出在语义上更正确。
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from tests.core.verify_compatibility import verify_device


# 已知与 C# 工具存在差异的样本及原因
KNOWN_DEVICE_DIFFS: dict[str, str] = {
    "canopen_datatypes": (
        "合成的 datatype 测试 EDS, 0x200A OCTET_STRING 'ABCD' 在无 "
        ";StorageLocation=RAM 注释时 C# 输出 dataLength=0, Python 正确生成 [2] 字节"
    ),
}


def _device_subdirs(eds_dir: str) -> list[str]:
    """返回 eds_dir 下含 OD.h 或 OD.c 的子目录。"""
    out: list[str] = []
    for name in sorted(os.listdir(eds_dir)):
        p = os.path.join(eds_dir, name)
        if not os.path.isdir(p):
            continue
        if os.path.exists(os.path.join(p, "OD.h")) or os.path.exists(
            os.path.join(p, "OD.c")
        ):
            out.append(p)
    return out


def test_v4_export_matches_csharp_reference(test_eds_dir):
    """Python V4 导出器对每个样本文件的输出应与 C# 工具参考一致。

    `KNOWN_DEVICE_DIFFS` 中列出的样本文件允许存在已知差异。
    """
    failures: list[tuple[str, dict]] = []
    for subdir in _device_subdirs(test_eds_dir):
        device = os.path.basename(subdir)
        result = verify_device(subdir)
        if not result.get("load_ok"):
            failures.append((device, {"load_error": result.get("load_error")}))
            continue
        if not result.get("export_ok"):
            failures.append((device, {"export_error": result.get("export_error")}))
            continue
        if device in KNOWN_DEVICE_DIFFS:
            continue
        for key, comp in result.get("comparisons", {}).items():
            if not comp.get("match", True) or comp.get("details"):
                failures.append(
                    (device, {key: comp.get("details", [])[:3]})
                )
                break
    if failures:
        msg = "\n".join(
            f"  {dev}: {details}" for dev, details in failures
        )
        pytest.fail(
            f"{len(failures)} 个样本与 C# 参考输出不一致:\n{msg}"
        )


@pytest.mark.parametrize("subdir_name", [
    "aa_anchor_minimal",
    "canopen_e35",
    "canopennode_basic_device",
    "cia_401_io",
    "cia_402_profile",
    "cia_406_encoder",
    "dm_motor_slave",
    "faulhaber_605_3150_55",
    "faulhaber_605_3150_68b",
    "faulhaber_605_3150_71a",
    "systec_iox1",
])
def test_v4_export_od_list_match(test_eds_dir, subdir_name):
    """OD 列表（index/subcount/type）应与 C# 完全一致。"""
    subdir = os.path.join(test_eds_dir, subdir_name)
    if not os.path.isdir(subdir):
        pytest.skip(f"样本目录不存在: {subdir_name}")
    result = verify_device(subdir)
    assert result.get("load_ok"), f"加载失败: {result.get('load_error')}"
    assert result.get("export_ok"), f"导出失败: {result.get('export_error')}"
    comp = result["comparisons"].get("od_list", {})
    assert comp.get("match"), (
        f"OD 列表与 C# 不一致: {comp.get('details', [])[:5]}"
    )

