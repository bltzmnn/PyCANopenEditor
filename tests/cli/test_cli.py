"""CLI 集成测试。

外部 EDS 样本通过 `PYCANOPEN_TEST_EDS_DIR` 环境变量注入；未设置时
相关 CLI 批量测试会通过 `pytest.skip` 自动跳过。

`eds/minimal_project.xdd` 为可选上游测试样本，未提供时仅 XDD 类
测试跳过，其它 CLI 测试仍可执行。
"""
import os
import pytest

from src.cli.main import main


REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
MINIMAL_XDD = os.path.join(REPO_ROOT, "eds", "minimal_project.xdd")


@pytest.mark.skipif(not os.path.exists(MINIMAL_XDD), reason="minimal_project.xdd not found")
class TestCLI:
    def test_xdd_to_canopen_node_v4(self, tmp_path):
        """对应 C# XddToCanOpenNodeV4"""
        out_base = str(tmp_path / "V4")
        ret = main(["--type", "CanOpenNodeV4", "--infile", MINIMAL_XDD, "--outfile", out_base])
        assert ret == 0
        assert os.path.exists(out_base + ".h")
        assert os.path.exists(out_base + ".c")

    def test_only_single_exporter_by_extension(self, tmp_path):
        """对应 C# OnlySingleExporterByExtensionPossible — .eds 只有一个导出器"""
        out_file = str(tmp_path / "file.eds")
        ret = main(["--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)

    def test_multiple_exporter_by_extension_defaults_without_type(self, tmp_path):
        """对应 C# MultipleExporterByExtensionPossibleWithoutType — .html 对应多个导出器，不指定 --type 时自动选择"""
        out_file = str(tmp_path / "file.html")
        ret = main(["--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)

    def test_multiple_exporter_by_extension_with_type(self, tmp_path):
        """对应 C# MultipleExporterByExtensionPossibleWithType — 指定 --type 后成功"""
        out_file = str(tmp_path / "file.nxdd")
        ret = main(["--type", "CanOpen Network XDD v1.1", "--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)

    def test_list_exporters(self, capsys):
        """--list-exporters 正常输出"""
        ret = main(["--list-exporters"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "可用导出器" in captured.out

    def test_xdd_to_eds(self, tmp_path):
        """XDD → EDS 转换"""
        out_file = str(tmp_path / "output.eds")
        ret = main(["--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)

    def test_xdd_to_html(self, tmp_path):
        """XDD → HTML 文档导出（.html 有多个导出器，需指定 --type）"""
        out_file = str(tmp_path / "output.html")
        ret = main(["--type", "Documentation HTML", "--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)

    def test_xdd_to_markdown(self, tmp_path):
        """XDD → Markdown 文档导出"""
        out_file = str(tmp_path / "output.md")
        ret = main(["--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)

    def test_xdd_to_network_xdd(self, tmp_path):
        """XDD → Network XDD 导出"""
        out_file = str(tmp_path / "output.nxdd")
        ret = main(["--type", "CanOpen Network XDD v1.1", "--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 0
        assert os.path.exists(out_file)

    def test_invalid_infile(self, tmp_path):
        """无效输入文件返回错误"""
        out_file = str(tmp_path / "output.eds")
        ret = main(["--infile", "/nonexistent/file.xdd", "--outfile", out_file])
        assert ret == 1

    def test_unknown_exporter_type(self, tmp_path):
        """无效导出器类型返回错误"""
        out_file = str(tmp_path / "output.xdd")
        ret = main(["--type", "NonexistentExporter", "--infile", MINIMAL_XDD, "--outfile", out_file])
        assert ret == 1


EDS_DIR = os.environ.get("PYCANOPEN_TEST_EDS_DIR", "").strip()
EDS_DIR = os.path.abspath(EDS_DIR) if EDS_DIR else ""


def _collect_eds_files(root: str) -> list[str]:
    result: list[str] = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".eds"):
                result.append(os.path.join(dirpath, name))
    return sorted(result)


def _all_real_eds() -> list[str]:
    if not EDS_DIR or not os.path.isdir(EDS_DIR):
        return []
    return _collect_eds_files(EDS_DIR)


@pytest.fixture(scope="module")
def external_eds_files() -> list[str]:
    files = _all_real_eds()
    if not files:
        pytest.skip(f"环境变量 PYCANOPEN_TEST_EDS_DIR 未设置或目录无 EDS 文件: {EDS_DIR!r}")
    return files


def test_cli_eds_to_eds_round_trip_all_files(external_eds_files, tmp_path):
    """外部 EDS 样本走 CLI EDS→EDS 往返，输出文件应非空"""
    for eds_path in external_eds_files:
        out_file = str(tmp_path / "rt.eds")
        ret = main(["--infile", eds_path, "--outfile", out_file])
        assert ret == 0, f"CLI 返回非零: {eds_path}"
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 500, f"导出文件太小: {out_file}"


def test_cli_eds_to_c_v4_all_files(external_eds_files, tmp_path):
    """外部 EDS 样本走 CLI 导出 CANopenNode V4 C 源码"""
    for eds_path in external_eds_files:
        out_base = str(tmp_path / "OD")
        ret = main(["--type", "CanOpenNodeV4", "--infile", eds_path, "--outfile", out_base])
        assert ret == 0, f"CLI 返回非零: {eds_path}"
        assert os.path.exists(out_base + ".h")
        assert os.path.exists(out_base + ".c")
        assert os.path.getsize(out_base + ".h") > 500


def test_cli_eds_to_xdd_all_files(external_eds_files, tmp_path):
    """外部 EDS 样本走 CLI EDS→XDD（指定 --type 避免多 exporter 歧义）"""
    for eds_path in external_eds_files:
        out_file = str(tmp_path / "rt.xdd")
        ret = main(["--type", "CanOpenXDDv1.1", "--infile", eds_path, "--outfile", out_file])
        assert ret == 0, f"CLI 返回非零: {eds_path}"
        assert os.path.exists(out_file)
        assert os.path.getsize(out_file) > 1000
