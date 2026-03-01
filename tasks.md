# Task Breakdown: Photo Organizer

## Task List

| ID | Task | Dependencies | Estimated Effort |
|----|------|--------------|------------------|
| T1 | 创建项目结构 (pyproject.toml + 目录) | - | 10 min |
| T2 | 实现 EXIF 日期提取器 | T1 | 1-2 hours |
| T3 | 实现 QuickTime 日期提取器 | T1 | 1-2 hours |
| T4 | 实现文件系统时间兜底 | T1 | 15 min |
| T5 | 实现核心 Organizer 类 | T2, T3, T4 | 1 hour |
| T6 | 实现 CLI 接口 | T5 | 30 min |
| T7 | 测试与验证 | T6 | 30 min |

---

## T1: 创建项目结构

**目标**: 初始化项目配置和目录结构

**步骤**:
1. 创建 `pyproject.toml` (uv 格式)
2. 创建目录结构: `src/photo_organizer/`
3. 创建 `__init__.py` 和 `__main__.py`

**验收标准**:
- [ ] `uv run python -m photo_organizer --help` 正常工作

---

## T2: 实现 EXIF 日期提取器

**目标**: 从 JPEG/HEIC/TIFF 文件中提取 EXIF 日期

**步骤**:
1. 实现 JPEG 文件头识别
2. 解析 APP1 段定位 EXIF 数据
3. 解析 TIFF IFD 结构
4. 提取 DateTimeOriginal / CreateDate 字段
5. 解析日期字符串为 datetime 对象

**关键文件**: `src/photo_organizer/metadata/exif.py`

**验收标准**:
- [ ] 正确提取 JPEG EXIF 日期
- [ ] 只读取文件头部，不加载整个文件
- [ ] 无效日期返回 None

---

## T3: 实现 QuickTime 日期提取器

**目标**: 从 MP4/MOV 文件中提取创建日期

**步骤**:
1. 解析 ftyp atom 识别文件类型
2. 定位 moov atom
3. 解析 mvhd 获取创建时间
4. 解析 metadata atom 获取 ContentCreateDate
5. 转换 QuickTime 时间戳 (1904 epoch)

**关键文件**: `src/photo_organizer/metadata/quicktime.py`

**验收标准**:
- [ ] 正确提取 MP4/MOV 创建日期
- [ ] 只读取必要的 atom，不加载整个文件

---

## T4: 实现文件系统时间兜底

**目标**: 当无法提取元数据时，使用文件系统时间

**步骤**:
1. 获取文件 stat 信息
2. 尝试 st_birthtime (macOS/BSD)
3. 回退到 st_ctime (Linux)

**关键文件**: `src/photo_organizer/metadata/fallback.py`

**验收标准**:
- [ ] 正确返回文件系统创建时间

---

## T5: 实现核心 Organizer 类

**目标**: 整合元数据提取和文件移动逻辑

**步骤**:
1. 实现 `scan_files()` - 扫描当前目录文件
2. 实现 `get_date()` - 路由到正确的提取器
3. 实现 `organize_file()` - 创建目录并移动文件
4. 实现冲突处理（同名文件加后缀）

**关键文件**: `src/photo_organizer/organizer.py`

**验收标准**:
- [ ] 正确扫描当前目录文件
- [ ] 按优先级提取日期
- [ ] 文件移动到正确目录
- [ ] 同名冲突正确处理

---

## T6: 实现 CLI 接口

**目标**: 提供命令行入口

**步骤**:
1. 使用 argparse 解析参数
2. 实现 --dry-run 模式
3. 实现 --verbose 模式
4. 实现 --help 信息

**关键文件**: `src/photo_organizer/cli.py`, `src/photo_organizer/__main__.py`

**验收标准**:
- [ ] `photo-organizer --help` 显示帮助
- [ ] `photo-organizer --dry-run` 不移动文件
- [ ] `photo-organizer --verbose` 显示详情

---

## T7: 测试与验证

**目标**: 验证程序正确性

**步骤**:
1. 准备测试文件（JPEG + MP4）
2. 运行 dry-run 验证输出
3. 运行实际移动验证结果
4. 验证边界情况

**验收标准**:
- [ ] JPEG 文件正确移动
- [ ] MP4 文件正确移动
- [ ] 无元数据文件正确兜底
