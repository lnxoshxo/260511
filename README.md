# Zipora

Zipora 是一个基于 Python 3.10+ 和 PyQt6 的跨平台桌面压缩解压缩软件。项目采用核心业务与 GUI 分离的结构，支持后台任务、格式扩展、命令行调用和 PyInstaller 打包。

## 功能

- 创建压缩包：ZIP、7Z、TAR、TAR.GZ、TAR.BZ2、TAR.XZ、LZ4、ZSTD。
- 解压压缩包：ZIP、7Z、TAR、TAR.GZ、TAR.BZ2、TAR.XZ、LZ4、ZSTD、RAR。
- 浏览压缩包内容，查看条目大小、压缩后大小和类型。
- 双击预览 ZIP 内文本文件。
- ZIP 压缩包管理：添加文件、删除条目、重命名条目。
- 完整性校验：ZIP 使用 CRC 校验，TAR 系列读取所有成员验证可读性。
- 批量压缩与批量解压命令行入口。
- 收藏夹：保存常用压缩包和目录。
- 后台压缩与解压，进度实时显示，UI 保持响应。
- 支持拖拽文件到主窗口。
- 支持浅色与深色主题切换。
- 支持命令行创建、解压、列出、查看信息和格式转换。
- 支持从公开或已授权 JSON 数据源采集热点归因数据，提供去重存储和 CSV 导出。
- 提供热点归因静态前端页面，可在浏览器中预览采集看板效果。
- 解压时阻止路径遍历攻击，降低恶意压缩包风险。
- 提供设置存储、历史记录、密码强度检测和强密码生成器。

## 支持格式

| 格式 | 创建 | 解压 | 说明 |
| --- | --- | --- | --- |
| ZIP | 支持 | 支持 | 使用标准库 `zipfile` |
| TAR | 支持 | 支持 | 使用标准库 `tarfile` |
| TAR.GZ | 支持 | 支持 | 使用标准库 `tarfile` |
| TAR.BZ2 | 支持 | 支持 | 使用标准库 `tarfile` |
| TAR.XZ | 支持 | 支持 | 使用标准库 `tarfile` |
| 7Z | 支持 | 支持 | 需要 `py7zr` |
| RAR | 读取限制 | 支持 | 需要 `rarfile` 和系统解码工具 |
| LZ4 | 支持 | 支持 | 单文件压缩，需 `lz4` |
| ZSTD | 支持 | 支持 | 单文件压缩，需 `zstandard` |

## 安装

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment on Linux or macOS
source .venv/bin/activate

# Install runtime dependencies
python -m pip install --break-system-packages -r requirements.txt
```

## 运行 GUI

```bash
python -m zipora
```

开发环境运行时建议设置 `PYTHONPATH`：

```bash
PYTHONPATH=src python -m zipora
```

## 预览热点归因前端

```bash
# Start a local static preview server
python3 -m http.server 8000
```

启动后访问 `http://localhost:8000/` 查看热点归因采集控制台。

## 命令行用法

```bash
# Create a ZIP archive
PYTHONPATH=src python -m zipora.cli create archive.zip ./some-file.txt

# Extract an archive
PYTHONPATH=src python -m zipora.cli extract archive.zip ./output

# List archive entries
PYTHONPATH=src python -m zipora.cli list archive.zip

# Show archive information with SHA-256
PYTHONPATH=src python -m zipora.cli info archive.zip --hash

# Test archive integrity
PYTHONPATH=src python -m zipora.cli test archive.zip

# Add files to an existing ZIP archive
PYTHONPATH=src python -m zipora.cli zip-add archive.zip ./new-file.txt

# Remove entries from a ZIP archive
PYTHONPATH=src python -m zipora.cli zip-remove archive.zip old-file.txt

# Rename a ZIP entry
PYTHONPATH=src python -m zipora.cli zip-rename archive.zip old.txt new.txt

# Create one archive per input path
PYTHONPATH=src python -m zipora.cli batch-create ./archives ./file-a.txt ./file-b.txt

# Extract multiple archives into separate folders
PYTHONPATH=src python -m zipora.cli batch-extract ./output ./a.zip ./b.zip

# Manage favorites
PYTHONPATH=src python -m zipora.cli favorites add WorkArchive ./archive.zip

# List favorites
PYTHONPATH=src python -m zipora.cli favorites list

# Convert an archive to TAR.GZ
PYTHONPATH=src python -m zipora.cli convert archive.zip archive.tar.gz --format tar.gz

# Collect authorized hotspot attribution sources
PYTHONPATH=src python -m zipora.cli hotspots collect sources.json --db hotspots.sqlite3

# List collected hotspot attribution records
PYTHONPATH=src python -m zipora.cli hotspots list --db hotspots.sqlite3 --limit 20

# Export collected records to CSV
PYTHONPATH=src python -m zipora.cli hotspots export hotspots.csv --db hotspots.sqlite3
```

热点归因采集配置使用 JSON 数组，数据源必须是公开或已获得授权的 JSON 接口：

```json
[
  {
    "name": "authorized-sample",
    "url": "https://example.com/hotspots.json"
  }
]
```

采集器会对常见字段名进行归一化，例如 `topic`、`plateName`、`reason`、`description`、`stockCode`、`stockName`、`score`。系统内置请求超时、请求间隔、SQLite 去重存储和 CSV 导出能力。

## 项目结构

```text
src/zipora/
  app.py                 GUI 启动入口
  cli.py                 命令行入口
  core/
    archive_service.py   压缩格式后端和统一服务
    models.py            核心数据模型
    utils.py             路径、格式识别和安全工具
    settings.py          设置持久化
    history.py           历史记录
    hotspots.py          热点归因采集、解析、存储和导出
    security.py          密码工具
    system.py            系统资源和回收站集成
  gui/
    main_window.py       主窗口
    workers.py           后台任务线程
    styles.py            浅色和深色主题
tests/                   单元测试
scripts/                 平台打包脚本
```

## 测试

```bash
# Install development dependencies
python -m pip install --break-system-packages -r requirements-dev.txt

# Run tests
PYTHONPATH=src pytest
```

## 打包

Linux：

```bash
bash scripts/build_linux.sh
```

macOS：

```bash
bash scripts/build_macos.sh
```

Windows PowerShell：

```powershell
scripts\build_windows.ps1
```

生成结果位于 `dist/` 目录。Windows 安装包可接入 Inno Setup，macOS 安装镜像可基于 `dist/Zipora` 制作 DMG。

## 架构说明

项目采用 MVC 思路组织：

- Model：`core/models.py` 定义压缩选项、解压选项、条目和进度事件。
- View：`gui/main_window.py` 和 `gui/styles.py` 负责界面布局和主题。
- Controller/Service：`core/archive_service.py` 负责压缩、解压、浏览、校验和格式转换。

GUI 中的压缩和解压任务通过 `QRunnable` 与 `QThreadPool` 在后台执行，并使用 Qt 信号更新进度和状态。

## 安全策略

- 解压前对每个成员路径执行根目录约束，阻止 `../` 路径逃逸。
- TAR 解压跳过符号链接和硬链接，减少链接型攻击面。
- 密码仅在任务参数中传递，当前版本没有持久化明文密码。
- 临时目录用于格式转换，任务结束后自动清理。

## 开发路线

- 添加任务暂停、继续和取消。
- 添加完整右键菜单集成和默认应用关联。
- 添加分卷压缩、分卷合并和损坏修复。
- 添加 PDF、图片等更多预览器。
- 添加 Inno Setup 和 DMG 的安装器模板。
- 添加多语言资源文件和翻译切换。
