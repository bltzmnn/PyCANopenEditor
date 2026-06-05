# PyCANopenEditor

CANopen 对象字典编辑器 —— [CANopenEditor](https://github.com/CANopenNode/CANopenEditor) 的 Python + PySide6 跨平台重写，功能与 C# 原版保持一致。

> **一句话介绍**：打开你的 EDS/XDD 文件，编辑对象字典和 PDO 映射，导出为 C 源码、EDS、XDD 等格式。

---

## 快速开始

### 1. 安装

```bash
# 安装依赖（需要 Python 3.10+）
pip install -e .
```

> **Linux 用户**：GUI 依赖 `libxcb-cursor0`，启动报错时先安装：
> ```bash
> sudo apt install libxcb-cursor0   # Debian/Ubuntu
> ```

### 2. 启动 GUI

```bash
pycanopen-gui
```

或直接运行模块：

```bash
python -m src.gui.app
```

> **Linux 用户**：`pip install -e .` 会把 `pycanopen-gui` 放到 `~/.local/bin`。如果提示 `未找到命令`，先执行 `export PATH="$HOME/.local/bin:$PATH"`，或将该行加入 `~/.bashrc`。如不想改 `PATH`，使用 `python -m src.gui.app` 同样可以启动。

### 3. 命令行转换（不需要 GUI）

```bash
# EDS 转 XDD
pycanopen --infile device.eds --outfile device.xdd

# EDS 转 CANopenNode V4 C 源码
pycanopen --type CanOpenNodeV4 --infile device.eds --outfile OD.h

# 查看所有可用导出器
pycanopen --list-exporters
```

---

## 支持的文件格式

### 导入（打开）

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| Electronic Data Sheet | `.eds` | CiA 306-1 标准格式 |
| Device Configuration File | `.dcf` | 含 actual value 的 EDS 扩展 |
| XML Device Description v1.1 | `.xdd` | CiA 311 标准格式 |
| XML Device Configuration v1.1 | `.xdc` | 含 actual value 和 commissioning 的 XDD 扩展 |
| XML Device Description v1.0 | `.xdd` | 旧版格式（best-effort 兼容） |
| Network XDD/XDC | `.nxdd` / `.nxdc` | 多设备网络文件 |
| Protobuf Binary | `.binpb` | CANopenNode 项目文件 |
| Protobuf JSON | `.json` | CANopenNode 项目文件（JSON） |
| XML Profile Description | `.xpd` | 配置文件描述（与 XDD 格式相同） |

### 导出（保存/导出）

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| Electronic Data Sheet | `.eds` | CiA 306-1 |
| Device Configuration File | `.dcf` | CiA 306-1（含 actual value） |
| CanOpenXDDv1.1 | `.xdd` | CiA 311 完整版 |
| CanOpenXDDv1.1stripped | `.xdd` | 去除 disabled 对象和自定义属性 |
| CanOpenXDCv1.1 | `.xdc` | 含 actual value 和 commissioning |
| CanOpen Network XDD v1.1 | `.nxdd` | 多设备网络描述 |
| CanOpen Network XDC v1.1 | `.nxdc` | 多设备网络配置 |
| CanOpenNode (Legacy V1-3) | `.h` / `.c` | CANopenNode C 源码（旧版） |
| CanOpenNodeV4 | `.h` / `.c` | CANopenNode V4 C 源码（推荐） |
| Documentation HTML | `.html` | HTML 文档 |
| Documentation Markup | `.md` | Markdown 文档 |
| Network PDO Report | `.html` | 网络 PDO 映射报告 |
| Protobuf Binary | `.binpb` | CANopenNode 项目文件 |
| Protobuf JSON | `.json` | CANopenNode 项目文件（JSON） |

---

## GUI 使用指南

### 打开文件

1. 菜单 → **文件 → 打开**（或 `Ctrl+O`）
2. 选择 `.eds` / `.dcf` / `.xdd` / `.xdc` 文件
3. 左侧设备列表出现设备名，右侧显示 4 个标签页

### 四个标签页

| 标签页 | 功能 |
|--------|------|
| **设备信息** | 编辑供应商、产品名、版本号、Commissioning 参数 |
| **对象字典** | 浏览/添加/删除/编辑 OD 条目和子对象 |
| **PDO 映射** | 查看 TX/RX PDO 通信参数和映射关系，添加/删除 PDO |
| **Modules** | 查看设备模块信息 |

### 对象字典编辑

- **左侧**：按范围分组显示（通信对象 0x1000-0x1FFF、制造商对象 0x2000-0x5FFF、设备对象 0x6000+）
- **右键** → 添加/删除 OD 条目
- **右侧上方**：子对象表格
- **右侧下方**：属性编辑面板（名称、数据类型、访问类型、PDO 映射、默认值、禁用标记）
- 禁用的条目以灰色 + `[disabled]` 标记显示

### PDO 映射编辑

- **左侧**：TX PDO（0x1800-0x19FF）和 RX PDO（0x1400-0x15FF）列表
- **`+ TX PDO` / `+ RX PDO`**：添加新 PDO
- **`- TX PDO` / `- RX PDO`**：删除选中 PDO
- **右侧上方**：通信参数（COB-ID、传输类型、Inhibit、Event Timer 等）
- **右侧下方**：映射表格 + 位数可视化（超过 64 位会警告）
- 支持 32 个 PDO 槽位（TX 和 RX 各最多 512 个通信参数）

### 导入 Profile

1. 菜单 → **文件 → 导入 Profile...**
2. 从 `profiles/` 目录选择标准 CANopen Profile（如 DS301、DS401）
3. 预览合并结果，设置 index 偏移，解决冲突
4. 点击 **导入**

### 导出文件

1. 菜单 → **文件 → 导出...**
2. 选择导出格式
3. 选择输出路径

---

## CLI 使用指南

### 基本格式

```bash
pycanopen --infile <输入文件> --outfile <输出文件>
pycanopen --infile <输入文件> --outfile <输出文件> --type <导出器名称>
```

### 常用示例

```bash
# EDS → XDD
pycanopen --infile device.eds --outfile device.xdd

# EDS → DCF（含 actual value）
pycanopen --infile device.eds --outfile device.dcf

# XDD → EDS
pycanopen --infile device.xdd --outfile output.eds

# EDS → CANopenNode V4 C 源码（生成 OD.h 和 OD.c）
pycanopen --type CanOpenNodeV4 --infile device.eds --outfile OD.h

# EDS → CANopenNode V1 C 源码（旧版格式）
pycanopen --type CanOpenNode --infile device.eds --outfile OD.h

# XDD → XDC（含 actual value）
pycanopen --type CanOpenXDCv1.1 --infile device.xdd --outfile output.xdc

# EDS → HTML 文档
pycanopen --type "Documentation HTML" --infile device.eds --outfile doc.html

# EDS → Markdown 文档
pycanopen --infile device.eds --outfile doc.md

# XDD → Network XDD（多设备）
pycanopen --type "CanOpen Network XDD v1.1" --infile device.xdd --outfile network.nxdd

# XDD → Protobuf JSON
pycanopen --infile device.xdd --outfile device.json

# 多个导出器对应同一扩展名时，必须指定 --type
pycanopen --type CanOpenXDDv1.1 --infile device.xdd --outfile output.xdd
```

> **提示**：当输出扩展名对应多个导出器时（如 `.xdd` 同时对应完整版和精简版），必须用 `--type` 指定。错误提示会列出可选项。

---

## 项目结构

```
PyCANopenEditor/
├── src/
│   ├── core/                  # 核心库（不依赖 GUI）
│   │   ├── models/            #   数据模型（EDS, ODentry, DeviceInfo, PDOHelper）
│   │   ├── parsers/           #   解析器（EDS/DCF 读写、XDD/XDC 读写）
│   │   ├── exporters/         #   导出器（CanOpenNode C, 文档, Protobuf, XDD）
│   │   └── proto/             #   Protobuf 生成代码（CanOpen.proto → CanOpen_pb2.py）
│   ├── gui/                   # GUI 层（PySide6）
│   │   ├── views/             #   视图（MainWindow, ODView, PDOView, ModuleView）
│   │   ├── viewmodels/        #   ViewModel（MVVM 模式）
│   │   └── app.py             #   GUI 入口
│   └── cli/
│       └── main.py            #   CLI 入口
├── tests/
│   ├── core/                  #   核心库单元测试
│   ├── gui/                   #   GUI 集成测试（需 xvfb-run）
│   └── cli/                   #   CLI 测试
├── profiles/                  # 标准 CANopen Profile 文件
│   ├── DS301_profile.xpd
│   ├── DS401_profile.xpd
│   └── DSP302-NMTMaster.xpd
├── eds/                       # 真实 EDS/XDD 样本（13 EDS + 3 XDD）
│   ├── SOURCES.md             #   文件来源与覆盖矩阵
│   ├── canopennode_basic_device.eds
│   ├── dm_motor_slave.eds
│   └── ...                    #   含 CiA 401/402/406、Systec、Faulhaber 等
└── pyproject.toml             # 项目配置
```

---

## 与 C# 版本的对应关系

PyCANopenEditor 是 [CANopenEditor](https://github.com/CANopenNode/CANopenEditor)（C# 版）的 Python + PySide6 重写：

- **功能对等**：C# 版有的功能全部实现
- **文件兼容**：生成的 EDS/DCF/XDD/XDC/C 文件与 C# 版本格式一致，可互换使用
- **跨平台**：Python + Qt 天然支持 Windows / Linux / macOS

### C# → Python 类对应表

| C# 类 | Python 模块 |
|--------|-------------|
| `eds.cs` / `EDS` | `core/models/eds.py` |
| `CanOpenEDS.cs` | `core/parsers/eds_parser.py` |
| `CanOpenXDD_1_1.cs` | `core/parsers/xdd_handler.py` |
| `CanOpenNodeExporter.cs` | `core/exporters/canopen_node_exporter.py` |
| `CanOpenNodeExporter_V4.cs` | `core/exporters/canopen_node_exporter_v4.py` |
| `DocumentationGenHtml.cs` | `core/exporters/documentation_gen_html.py` |
| `DocumentationGenMarkup.cs` | `core/exporters/documentation_gen_markup.py` |
| `NetworkPDOreport.cs` | `core/exporters/network_pdo_report.py` |
| `ExporterFactory.cs` / `Filetypes.cs` | `core/exporters/exporter_factory.py` |
| `PDOHelper.cs` | `core/models/pdo_helper.py` |
| `Warnings.cs` | `core/models/warnings.py` |

### 已知差异

| 项目 | 说明 |
|------|------|
| XSD 验证 | C# 版也未实现，by design 跳过 |
| GUI 框架 | C# 用 Avalonia/WPF，Python 用 PySide6 |
| Module C 导出 | C# 版也不在 C 源码中导出 module 信息 |

---

## 兼容性验证

- EDS round-trip 保留 OD 条目、parameter_name、datatype
- XDD/XDC round-trip 保留 OD 条目、属性、访问类型
- XDD → EDS → XDD 跨格式 round-trip
- CANopenNode V4 C 源码输出与 C# 版本逐字段比对通过
- Network XDD/XDC round-trip 保留 NodeID/NodeName/Baudrate
- Protobuf 二进制/JSON round-trip 通过

`eds/` 目录下附带 **13 个真实 EDS + 3 个 XDD** 样本文件，覆盖
CiA 401/402/406 标准 profile、Systec 工业 I/O、Faulhaber 伺服电机、
CANopenNode 参考设备、达妙电机驱动等不同厂商/行业，用于兼容性
测试。完整文件清单与来源见 `eds/SOURCES.md`。

---

## 开发

### 运行测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行全部测试
pytest tests/

# 仅运行核心库测试（不需要显示服务器）
pytest tests/core/

# 运行 GUI 测试（需要 xvfb-run 或显示服务器）
xvfb-run -a pytest tests/gui/

# 运行 CLI 测试
pytest tests/cli/
```

涉及外部 EDS 样本的测试（`test_external_eds_files_roundtrip`、
`test_cli_eds_to_*_all_files` 等）通过环境变量 `PYCANOPEN_TEST_EDS_DIR`
读取样本目录。推荐使用仓库自带的 `eds/` 目录：

```bash
# 使用仓库附带的 13 EDS + 3 XDD 样本
export PYCANOPEN_TEST_EDS_DIR=eds
pytest tests/

# 也可指向你自己的样本目录
export PYCANOPEN_TEST_EDS_DIR=/path/to/your/eds-samples
pytest tests/
```

未设置时上述测试会自动 `skip`，不影响 CI 跑通。仓库自带的最小
样本 `tests/core/test_data/minimal.eds` 不需要该环境变量。

### 添加新导出器

1. 在 `src/core/exporters/` 下创建新文件
2. 实现 `IFileExporter` 接口和 `get_exporters()` 方法
3. 在 `exporter_factory.py` 中注册

---

## 许可证

GPL（与上游 CANopenEditor 一致）