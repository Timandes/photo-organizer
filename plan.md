# Technical Implementation Plan: Photo Organizer

## Architecture Overview

```
photo-organizer/
├── pyproject.toml          # 项目配置 (uv)
├── src/
│   └── photo_organizer/
│       ├── __init__.py
│       ├── __main__.py     # 入口点
│       ├── cli.py          # 命令行接口
│       ├── organizer.py    # 核心整理逻辑
│       ├── metadata/
│       │   ├── __init__.py
│       │   ├── base.py     # 基类和接口
│       │   ├── exif.py     # JPEG/HEIC EXIF 提取
│       │   ├── quicktime.py # MP4/MOV 元数据提取
│       │   └── fallback.py # 文件系统时间兜底
│       └── utils/
│           ├── __init__.py
│           └── file_ops.py # 文件操作工具
└── constitution.md
├── spec.md
├── plan.md
└── tasks.md
```

## Module Design

### 1. cli.py - 命令行接口

```python
def main() -> None:
    """解析命令行参数并启动整理流程"""

# 参数:
#   --dry-run: bool = False
#   --verbose: bool = False
```

### 2. organizer.py - 核心整理逻辑

```python
class Organizer:
    def __init__(self, dry_run: bool, verbose: bool): ...
    def scan_files(self, directory: Path) -> list[Path]: ...
    def get_date(self, file_path: Path) -> datetime | None: ...
    def organize_file(self, file_path: Path) -> bool: ...
    def run(self) -> None: ...
```

### 3. metadata/base.py - 元数据提取基类

```python
class MetadataExtractor(ABC):
    @abstractmethod
    def can_handle(self, file_path: Path, header: bytes) -> bool: ...
    
    @abstractmethod
    def extract_date(self, file_path: Path) -> datetime | None: ...
```

### 4. metadata/exif.py - EXIF 提取器

**支持的格式**: JPEG, HEIC, TIFF, WebP, RAW formats

**优化策略**:
- JPEG: 读取前 64KB，解析 APP1 段
- HEIC: 解析 ftyp/meta/iloc boxes
- 不依赖外部库，使用纯 Python 解析

**EXIF 日期字段优先级**:
1. `DateTimeOriginal` (0x9003)
2. `CreateDate` / `DateTimeDigitized` (0x9004)
3. `ModifyDate` (0x0132)

### 5. metadata/quicktime.py - QuickTime/MP4 提取器

**支持的格式**: MP4, MOV, 3GP

**优化策略**:
- 解析 moov atom 结构
- 查找 mvhd, tkhd, mdhd 中的创建时间
- 查找 ContentCreateDate/CreationDate metadata

**QuickTime 日期来源优先级**:
1. ContentCreateDate (metadata atom)
2. mvhd creation_time
3. tkhd creation_time

### 6. metadata/fallback.py - 文件系统时间兜底

```python
def get_filesystem_date(file_path: Path) -> datetime | None:
    """获取文件系统创建时间"""
    stat = file_path.stat()
    # 优先使用 st_birthtime (macOS/BSD)
    # 回退到 st_ctime (Linux)
```

## Data Flow

```
┌─────────────────┐
│   CLI Entry     │
│  (cli.py)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Organizer     │
│ (organizer.py)  │
└────────┬────────┘
         │
         ├──── scan_files() ────► 当前目录文件列表
         │
         ├──── for each file ────┐
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────────┐
│ Metadata Router │    │ File Operations  │
│ (metadata/)     │    │ (utils/)         │
└────────┬────────┘    └──────────────────┘
         │
         ├─► EXIF Extractor (if image)
         ├─► QuickTime Extractor (if video)
         └─► Filesystem Fallback
```

## Date Extraction Strategy

### Step 1: 文件类型识别
```python
def identify_file_type(header: bytes) -> str:
    """根据文件头识别类型"""
    # JPEG: FF D8 FF
    # PNG: 89 50 4E 47
    # HEIC: ftyp heic/heix
    # MP4/MOV: ftyp mp41/mp42/isom/qt
```

### Step 2: 按类型提取元数据
- 读取最少必要的字节数
- 使用二进制解析而非正则表达式

### Step 3: 解析日期字符串
```python
def parse_exif_date(date_str: bytes) -> datetime | None:
    """解析 EXIF 日期格式: YYYY:MM:DD HH:MM:SS"""

def parse_quicktime_date(timestamp: int) -> datetime | None:
    """解析 QuickTime 时间戳 (1904 epoch)"""
```

## Implementation Strategy

### Phase A: 项目初始化
1. 创建 pyproject.toml
2. 设置目录结构

### Phase B: 元数据提取
1. 实现 EXIF 解析器（JPEG）
2. 实现 QuickTime 解析器（MP4/MOV）
3. 实现文件系统时间兜底

### Phase C: 核心逻辑
1. 实现文件扫描
2. 实现日期提取路由
3. 实现文件移动逻辑

### Phase D: CLI
1. 实现参数解析
2. 实现 dry-run 模式
3. 实现 verbose 输出

## Dependencies

使用 Python 标准库，不依赖第三方包：
- `pathlib` - 路径操作
- `argparse` - 命令行解析
- `struct` - 二进制解析
- `datetime` - 日期处理
- `logging` - 日志记录
- `shutil` - 文件移动
- `os` - 文件系统操作

**无外部依赖**，保持轻量。
