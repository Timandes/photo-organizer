# Feature Specification: Photo Organizer

## User Story

**作为** 照片/视频管理者
**我希望** 能够按照媒体日期自动整理文件到对应目录
**以便于** 快速找到特定日期拍摄的照片和视频

## Functional Requirements

### FR-001: 文件扫描
WHEN 用户运行程序时
THEN THE SYSTEM SHALL 扫描当前工作目录下的所有文件（不遍历子目录）

### FR-002: 元数据提取 - 创建媒体日期
WHEN 文件是支持的媒体格式时
THEN THE SYSTEM SHALL 尝试提取"创建媒体日期"元数据
  - 图片: EXIF `DateTimeOriginal`
  - 视频: QuickTime `ContentCreateDate` 或 `MediaCreateDate`

### FR-003: 元数据提取 - 拍摄日期
WHEN "创建媒体日期"不可用时
THEN THE SYSTEM SHALL 尝试提取"拍摄日期"元数据
  - 图片: EXIF `CreateDate` 或 `DateTimeDigitized`
  - 视频: QuickTime `CreationDate`

### FR-004: 兜底日期
WHEN 无法从元数据提取日期时
THEN THE SYSTEM SHALL 使用文件系统的创建时间作为日期
  - Linux: `st_ctime` (实际是元数据修改时间，但作为兜底)
  - macOS/BSD: `st_birthtime`

### FR-005: 目录创建与文件移动
WHEN 成功获取日期时
THEN THE SYSTEM SHALL 创建格式为 `[年].[月].[日]` 的目录
AND 将文件移动到该目录中

### FR-006: 文件名冲突处理
WHEN 目标目录已存在同名文件时
THEN THE SYSTEM SHALL 为新文件添加数字后缀
  - 格式: `filename_001.ext`, `filename_002.ext`, ...

### FR-007: Dry-Run 模式
WHEN 用户指定 `--dry-run` 参数时
THEN THE SYSTEM SHALL 只显示将要执行的操作，不实际移动文件

### FR-008: 详细输出模式
WHEN 用户指定 `--verbose` 参数时
THEN THE SYSTEM SHALL 显示每个文件的处理详情

## Non-Functional Requirements

### NFR-001: 性能 - 部分文件读取
WHEN 提取 JPEG EXIF 元数据时
THEN THE SYSTEM SHALL 只读取文件头部（前 64KB 或 APP1 段）

### NFR-002: 性能 - 视频元数据
WHEN 提取视频元数据时
THEN THE SYSTEM SHALL 使用 atom/box 解析，只读取必要的文件块

### NFR-003: 健壮性
WHEN 遇到无法处理的文件格式或损坏文件时
THEN THE SYSTEM SHALL 跳过该文件并记录警告，继续处理其他文件

## Edge Cases

| 场景 | 处理方式 |
|------|----------|
| 文件没有元数据 | 使用文件系统创建时间 |
| 元数据日期无效（如 0000:00:00） | 使用文件系统创建时间 |
| 目标目录已存在 | 直接移动文件到该目录 |
| 目标文件已存在 | 添加数字后缀 |
| 文件正在被其他进程使用 | 跳过并警告 |
| 符号链接 | 跳过符号链接 |
| 隐藏文件（以.开头） | 跳过隐藏文件 |

## Command Line Interface

```
photo-organizer [OPTIONS]

Options:
  --dry-run    预览模式，只显示将要执行的操作
  --verbose    显示详细处理信息
  --help       显示帮助信息
```

## Acceptance Criteria

1. 运行 `photo-organizer --dry-run` 显示所有文件的计划移动操作，但不实际移动
2. 运行 `photo-organizer` 后，所有支持的媒体文件被移动到对应的日期目录
3. 不支持的文件格式保持原位置不变
4. 元数据读取不加载整个文件到内存
