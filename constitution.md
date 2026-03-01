# Project Constitution: Photo Organizer

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11 |
| Package Manager | uv |
| CLI Framework | argparse (标准库) |
| Metadata Extraction | 自定义实现，优化读取效率 |

## Coding Standards

- **Type Hints**: 所有公开函数必须有类型注解
- **Docstrings**: 公开模块和函数使用简洁的 docstring
- **Error Handling**: 使用自定义异常，提供清晰错误信息
- **Logging**: 使用标准库 logging 模块，支持 --verbose 参数

## Security Rules

- 只读取文件元数据，不修改文件内容
- 文件移动操作使用原子操作（os.rename 或 shutil.move）
- 不执行任意代码或命令注入

## Performance Requirements

- **Partial Read**: 只读取必要的字节数来提取元数据，不读取整个文件
- **Memory Efficient**: 处理大文件时内存占用可控
- **No Unnecessary I/O**: 最小化文件系统操作

## Supported File Types

### Image Formats
- JPEG (EXIF metadata)
- PNG (可能包含 EXIF)
- HEIC (HEIF container, EXIF metadata)
- TIFF (EXIF metadata)
- WebP (可能包含 EXIF)
- RAW formats: CR2, NEF, ARW, DNG

### Video Formats
- MP4 (QuickTime/MP4 metadata atoms)
- MOV (QuickTime metadata atoms)
- AVI (RIFF metadata)
- MKV (EBML metadata)
- 3GP/3G2

## Date Extraction Priority

1. **Media Create Date** (创建媒体日期)
   - EXIF: `DateTimeOriginal`
   - QuickTime: `ContentCreateDate`, `MediaCreateDate`
   -优先级最高

2. **Shot Date** (拍摄日期)
   - EXIF: `CreateDate`, `DateTimeDigitized`
   - QuickTime: `CreationDate`

3. **Fallback**: File system creation time (st_ctime / st_birthtime)

## Output Directory Format

- 格式: `[年].[月].[日]`
- 示例: `2024.03.15/photo.jpg`
- 目录不存在时自动创建
