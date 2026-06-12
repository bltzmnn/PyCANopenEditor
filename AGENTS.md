# AGENTS.md

## 项目简介

[CANopenEditor](https://github.com/CANopenNode/CANopenEditor)（C# 版）的 Python + PySide6 跨平台重写。编辑 CANopen 对象字典（EDS/XDD 文件），导出为 C 源码、EDS、XDD、HTML、Protobuf 等格式。

**语言约定**：代码注释和 docstring 使用中文，请遵循此规范。

## 常用命令

```bash
# 安装（editable 模式，含开发依赖）
pip install -e ".[dev]"

# 运行全部测试（357 个，自动使用 eds/ 目录作为测试数据）
pytest tests/

# 仅核心库测试
pytest tests/core/

# GUI 测试（本机有 X11 可直接跑，无显示器环境用 xvfb-run）
pytest tests/gui/

# CLI 测试
pytest tests/cli/
```

## 环境变量

- `PYCANOPEN_TEST_EDS_DIR` — 指向真实 `.eds` 文件目录，用于兼容性测试。**未设置时自动使用仓库 `eds/` 目录**（包含 14 个 EDS + 4 个 XDD 样本）。指向其他目录可覆盖。

## 项目结构

```
src/
├── core/                  # 纯库，不依赖 GUI
│   ├── models/            #   数据模型：EDS、ODentry、DeviceInfo、PDOHelper、datatypes
│   ├── parsers/           #   解析器：eds_parser.py（EDS/DCF）、xdd_handler.py（XDD/XDC）
│   ├── exporters/         #   所有导出器 + exporter_factory.py（注册表）
│   └── proto/             #   Protobuf 生成代码
├── gui/                   # PySide6 GUI 层
│   ├── views/             #   视图：MainWindow、ODView、PDOView、ModuleView
│   ├── viewmodels/        #   MVVM ViewModel
│   └── app.py             #   GUI 入口：pycanopen-gui
└── cli/
    └── main.py            #   CLI 入口：pycanopen
```

- **入口点**（`pyproject.toml` 定义）：`pycanopen` → `src.cli.main:main`，`pycanopen-gui` → `src.gui.app:run_gui`
- **导出器**通过 `exporter_factory.py` 的 `Filetypes.register()` 注册。每个导出器实现 `IFileExporter.get_exporters()`，返回 `ExporterDescriptor` 列表。
- **C 源码导出**仅支持 CANopenNode V4 格式（`CanOpenNodeExporterV4`），与 CANopenNode V4 协议栈配合使用。

## 添加新导出器

1. 在 `src/core/exporters/` 下创建新文件
2. 实现 `IFileExporter` 接口和 `get_exporters()` 方法
3. 在 `exporter_factory.py` 中注册

## 测试说明

- `tests/conftest.py` 提供 `test_eds_dir`、`test_eds_files`、`eds_path` fixture
- `eds_path` 自动选取 OD 条目最丰富的 EDS 文件（GUI/集成测试需要较多 PDO 槽位）
- 最小测试数据位于 `tests/core/test_data/minimal.eds`
- XDD 测试样本位于 `eds/minimal_project.xdd`
- C# 参考输出位于 `eds/<设备名>/OD.h`、`eds/<设备名>/OD.c`
- 本仓库未配置 linting、typecheck 或 formatter
- 无 CI 工作流（`.github/workflows/` 为空）

## 注意事项

- `pip install -e .` 会把 `pycanopen-gui` 放到 `~/.local/bin`，可能需要 `export PATH="$HOME/.local/bin:$PATH"`
- Linux GUI 依赖 `libxcb-cursor0`：`sudo apt install libxcb-cursor0`
- 输出扩展名对应多个导出器时（如 `.xdd` → 完整版 vs 精简版），CLI 自动选择默认导出器，也可用 `--type` 指定
