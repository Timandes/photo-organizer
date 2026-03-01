# Photo Organizer

按媒体创建日期整理照片和视频文件。

## 功能特性

- 按媒体元数据中的创建日期整理文件到 `[年].[月].[日]` 目录
- 支持多种图片格式：JPEG、PNG、HEIC/HEIF、TIFF、WebP、RAW (CR2, NEF, ARW, DNG)
- 支持多种视频格式：MP4、MOV、3GP、3G2、M4V
- 优化的元数据读取：只读取必要的文件字节，不加载整个文件
- 无外部依赖：纯 Python 标准库实现

## 日期提取优先级

1. **创建媒体日期** (最高优先级)
   - 图片：EXIF `DateTimeOriginal`
   - 视频：QuickTime `ContentCreateDate`

2. **拍摄日期**
   - 图片：EXIF `CreateDate`
   - 视频：QuickTime `CreationDate`

3. **文件系统时间** (兜底)
   - 创建时间或修改时间

## 安装

```bash
# 从本地安装
uv tool install .

# 或从 Git 仓库安装
uv tool install git+https://github.com/your-repo/photo-organizer.git
```

## 更新

```bash
# 从本地更新（重新安装）
uv tool install . --reinstall --force

# 从 Git 仓库更新到最新版本
uv tool install git+https://github.com/your-repo/photo-organizer.git --reinstall --force
```

## 卸载

```bash
uv tool uninstall photo-organizer
```

## 使用方法

```bash
# 预览模式（不移动文件）
photo-organizer --dry-run

# 实际执行整理
photo-organizer

# 显示详细信息
photo-organizer --verbose

# 组合使用
photo-organizer --dry-run --verbose
```

## 命令行选项

| 选项 | 说明 |
|------|------|
| `--dry-run` | 预览模式，只显示将要执行的操作，不移动文件 |
| `--verbose, -v` | 显示详细处理信息 |
| `--version` | 显示版本号 |
| `--help` | 显示帮助信息 |

## 输出示例

```
$ photo-organizer --dry-run
Scanning directory: /home/user/photos
Found 3 file(s).

=== DRY RUN MODE (no files will be moved) ===

[DRY-RUN] IMG_001.jpg -> 2024.03.15/IMG_001.jpg
[DRY-RUN] VID_001.mp4 -> 2024.03.15/VID_001.mp4
[DRY-RUN] document.pdf -> 2026.03.01/document.pdf

=== Summary ===
Processed: 3
Skipped: 0
```

## 目录结构

整理后的目录结构：

```
photos/
├── 2024.03.15/
│   ├── IMG_001.jpg
│   └── VID_001.mp4
├── 2024.03.20/
│   └── IMG_002.jpg
└── 2026.03.01/
    └── document.pdf
```

## 技术细节

- **JPEG EXIF 解析**：读取文件头部 APP1 段，最大 128KB
- **QuickTime/MP4 解析**：解析 moov atom，最大扫描 1MB
- **无第三方依赖**：使用 Python 标准库 (`struct`, `pathlib`, `datetime` 等)

## 许可证

Apache License 2.0
