"""pytest 全局配置与共享 fixture。

外部测试数据约定：
    需要真实 EDS 文件做兼容性测试时，将目录路径写入环境变量
    `PYCANOPEN_TEST_EDS_DIR`，fixture 会自动扫描该目录下所有
    `.eds` 文件。未设置环境变量时，默认使用仓库根目录下的 `eds/`
    文件夹（包含 13 个 EDS + 4 个 XDD 样本）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

EDS_DIR_ENV = "PYCANOPEN_TEST_EDS_DIR"

_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
_DEFAULT_EDS_DIR = os.path.join(_REPO_ROOT, "eds")

if not os.environ.get(EDS_DIR_ENV, "").strip():
    os.environ[EDS_DIR_ENV] = _DEFAULT_EDS_DIR


def _resolve_eds_dir() -> str | None:
    """解析环境变量指向的 EDS 目录。"""
    p = os.environ.get(EDS_DIR_ENV, "").strip()
    if p and os.path.isdir(p):
        return os.path.abspath(p)
    return None


def _collect_eds_files(root: str) -> list[str]:
    """递归收集目录下所有 .eds 文件。"""
    result: list[str] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".eds"):
                result.append(os.path.join(dirpath, name))
    return sorted(result)


def _pick_richest_eds(files: list[str]) -> str | None:
    """从 EDS 文件列表中选出 OD 条目最多的一个（PDO 测试需要）。"""
    if not files:
        return None
    best = files[0]
    best_count = 0
    for path in files:
        try:
            from src.core.models.eds import EDS
            from src.core.parsers.eds_parser import EDSParser
            eds = EDS()
            EDSParser(eds).loadfile(path)
            count = len(eds.ods)
            if count > best_count:
                best_count = count
                best = path
        except Exception:
            continue
    return best


@pytest.fixture(scope="session")
def test_eds_dir() -> str:
    """返回 `PYCANOPEN_TEST_EDS_DIR` 指向的目录；未设置时跳过。"""
    p = _resolve_eds_dir()
    if not p:
        pytest.skip(f"环境变量 {EDS_DIR_ENV} 未设置或路径无效")
    return p


@pytest.fixture(scope="session")
def test_eds_files() -> list[str]:
    """返回测试 EDS 目录下所有 `.eds` 文件路径列表。"""
    p = _resolve_eds_dir()
    if not p:
        pytest.skip(f"环境变量 {EDS_DIR_ENV} 未设置或路径无效")
    files = _collect_eds_files(p)
    if not files:
        pytest.skip(f"{EDS_DIR_ENV}={p} 下未找到 .eds 文件")
    return files


@pytest.fixture
def eds_path() -> str:
    """返回 OD 条目最丰富的 EDS 文件路径，用于 GUI/集成测试。"""
    p = _resolve_eds_dir()
    if not p:
        pytest.skip(f"环境变量 {EDS_DIR_ENV} 未设置或路径无效")
    files = _collect_eds_files(p)
    if not files:
        pytest.skip(f"{EDS_DIR_ENV}={p} 下未找到 .eds 文件")
    richest = _pick_richest_eds(files)
    if not richest:
        pytest.skip("无法解析任何 EDS 文件")
    return richest
