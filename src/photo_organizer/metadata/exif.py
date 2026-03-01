"""EXIF metadata extractor for JPEG, HEIC, TIFF and other image formats.

Optimized to read only the necessary bytes from the file header.
"""

import struct
from datetime import datetime
from pathlib import Path
from typing import BinaryIO


# EXIF date tags (TIFF tag IDs)
EXIF_DATE_TAGS = [
    0x9003,  # DateTimeOriginal
    0x9004,  # DateTimeDigitized / CreateDate
    0x0132,  # DateTime / ModifyDate
]

# JPEG markers
JPEG_SOI = b'\xff\xd8'
JPEG_APP1 = b'\xff\xe1'
JPEG_APP2 = b'\xff\xe2'


class ExifExtractor:
    """Extract date from EXIF metadata in image files."""

    # Maximum bytes to read for EXIF data
    MAX_EXIF_SIZE = 65536 * 2  # 128KB should be enough for EXIF

    @classmethod
    def can_handle(cls, file_path: Path) -> bool:
        """Check if this extractor can handle the file type."""
        suffix = file_path.suffix.lower()
        return suffix in {'.jpg', '.jpeg', '.heic', '.heif', '.tiff', '.tif', '.webp', '.cr2', '.nef', '.arw', '.dng', '.raw'}

    @classmethod
    def extract_date(cls, file_path: Path) -> datetime | None:
        """Extract the earliest valid date from EXIF metadata."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
                
                # Check file type by magic bytes
                if header.startswith(b'\xff\xd8\xff'):
                    return cls._extract_from_jpeg(f)
                elif header[4:8] in (b'ftyp',):
                    # HEIC/HEIF - ftyp box at offset 4
                    return cls._extract_from_heic(f)
                elif header.startswith(b'II') or header.startswith(b'MM'):
                    # TIFF (also CR2, NEF, ARW, DNG)
                    return cls._extract_from_tiff(f)
                elif header.startswith(b'RIFF') and header[8:12] == b'WEBP':
                    return cls._extract_from_webp(f)
        except (OSError, struct.error):
            pass
        return None

    @classmethod
    def _extract_from_jpeg(cls, f: BinaryIO) -> datetime | None:
        """Extract EXIF date from JPEG file."""
        # Skip to APP1 marker
        while True:
            marker = f.read(2)
            if len(marker) < 2:
                return None
            
            if marker == JPEG_APP1:
                # APP1 segment length
                length = struct.unpack('>H', f.read(2))[0]
                exif_data = f.read(length - 2)
                
                # Check for EXIF header
                if exif_data.startswith(b'Exif\x00\x00'):
                    tiff_data = exif_data[6:]
                    return cls._parse_tiff_exif(tiff_data)
                
            elif marker[0:1] == b'\xff' and marker[1:2] not in (b'\x00', b'\xff'):
                # Other marker, skip it
                if marker[1:2] >= b'\xd0' and marker[1:2] <= b'\xd9':
                    # RST or SOF markers (no length)
                    continue
                length = struct.unpack('>H', f.read(2))[0]
                f.seek(length - 2, 1)
            else:
                break
        
        return None

    @classmethod
    def _extract_from_heic(cls, f: BinaryIO) -> datetime | None:
        """Extract EXIF date from HEIC/HEIF file."""
        # Parse ISO base media file format boxes
        f.seek(0)
        
        # First pass: find meta box and exif location
        meta_offset = None
        meta_size = None
        exif_location = None
        
        while True:
            box_header = f.read(8)
            if len(box_header) < 8:
                break
            
            size, box_type = struct.unpack('>I4s', box_header)
            
            if size == 0:
                break
            elif size == 1:
                size = struct.unpack('>Q', f.read(8))[0]
            
            if box_type == b'meta':
                meta_offset = f.tell()
                meta_size = size - 8
                # Parse meta box to find exif location
                exif_location = cls._parse_heic_meta_for_exif(f, size - 8)
                if exif_location:
                    # Read exif data from location
                    f.seek(exif_location)
                    exif_data = f.read(cls.MAX_EXIF_SIZE)
                    
                    # HEIC Exif item may have a 4-byte prefix before Exif header
                    # Format: [4 bytes: offset/size] [Exif\x00\x00] [TIFF data]
                    # or: [Exif\x00\x00] [TIFF data]
                    # or: [TIFF data directly]
                    
                    tiff_data = None
                    
                    # Check for 4-byte prefix + Exif header
                    if len(exif_data) > 10 and exif_data[4:10] == b'Exif\x00\x00':
                        tiff_data = exif_data[10:]
                    # Check for direct Exif header
                    elif exif_data[:6] == b'Exif\x00\x00':
                        tiff_data = exif_data[6:]
                    # Check for direct TIFF header (II or MM)
                    elif exif_data[:2] in (b'II', b'MM'):
                        tiff_data = exif_data
                    # Check for prefix + TIFF (without Exif header)
                    elif len(exif_data) > 6 and exif_data[4:6] in (b'II', b'MM'):
                        tiff_data = exif_data[4:]
                    
                    if tiff_data:
                        return cls._parse_tiff_exif(tiff_data)
                break
            else:
                f.seek(size - 8, 1)
        
        return None

    @classmethod
    def _parse_heic_meta_for_exif(cls, f: BinaryIO, remaining: int) -> int | None:
        """Parse HEIC meta box to find EXIF item location.
        
        Returns the file offset where EXIF data starts, or None.
        """
        # meta box: version(1) + flags(3) + boxes...
        version_flags = f.read(4)
        if len(version_flags) < 4:
            return None
        remaining -= 4
        
        exif_item_id = None
        iloc_data = None
        
        # Parse sub-boxes to find iinf (for exif item id) and iloc (for location)
        while remaining > 8:
            box_header = f.read(8)
            if len(box_header) < 8:
                break
            
            size, box_type = struct.unpack('>I4s', box_header)
            if size < 8 or size > remaining:
                break
            
            box_start = f.tell()
            box_content_size = size - 8
            
            if box_type == b'iinf':
                # Item Info box - find Exif item
                exif_item_id = cls._parse_iinf_for_exif(f, box_content_size)
            
            elif box_type == b'iloc':
                # Item Location box - read for later processing
                iloc_data = f.read(box_content_size)
            
            else:
                f.seek(box_content_size, 1)
            
            remaining -= size
        
        # If we found both exif item id and iloc data, find the location
        if exif_item_id is not None and iloc_data:
            return cls._find_exif_location_in_iloc(iloc_data, exif_item_id)
        
        return None

    @classmethod
    def _parse_iinf_for_exif(cls, f: BinaryIO, size: int) -> int | None:
        """Parse iinf box to find Exif item ID."""
        # iinf: version(1) + flags(3) + entry_count(2) + infe boxes...
        version_flags = f.read(4)
        if len(version_flags) < 4:
            return None
        
        entry_count = struct.unpack('>H', f.read(2))[0]
        remaining = size - 6
        
        result = None
        
        for _ in range(entry_count):
            if remaining < 8:
                break
            box_header = f.read(8)
            if len(box_header) < 8:
                break
            
            box_size, box_type = struct.unpack('>I4s', box_header)
            if box_size < 8 or box_size > remaining:
                break
            
            if box_type == b'infe':
                # infe: version(1) + flags(3) + item_id(2) + item_protection_index(2) + item_type(4) + item_name...
                version = f.read(1)
                if version == b'\x02':
                    # Version 2 format
                    f.read(3)  # flags
                    item_id = struct.unpack('>H', f.read(2))[0]
                    f.read(2)  # protection index
                    item_type = f.read(4)
                    if item_type == b'Exif':
                        result = item_id
                        # Don't return immediately - need to skip remaining data first
                    # Skip rest of box
                    f.seek(box_size - 8 - 12, 1)
                else:
                    # Version 0/1 format or unknown, skip
                    f.seek(box_size - 8 - 1, 1)
            else:
                f.seek(box_size - 8, 1)
            
            remaining -= box_size
        
        # Skip any remaining bytes in iinf box
        if remaining > 0:
            f.seek(remaining, 1)
        
        return result

    @classmethod
    def _find_exif_location_in_iloc(cls, iloc_data: bytes, exif_item_id: int) -> int | None:
        """Parse iloc box data to find Exif item location."""
        if len(iloc_data) < 8:
            return None
        
        version = iloc_data[0]
        flags = iloc_data[1:4]
        
        # offset_size(4 bits) + length_size(4 bits) + base_offset_size(4 bits) + index_size(4 bits)
        sizes = iloc_data[4]
        offset_size = (sizes >> 4) & 0x0F
        length_size = sizes & 0x0F
        
        if version == 1 or version == 2:
            sizes2 = iloc_data[5]
            base_offset_size = (sizes2 >> 4) & 0x0F
            index_size = sizes2 & 0x0F
            pos = 6
        else:
            base_offset_size = 0
            index_size = 0
            pos = 5
        
        # item_count
        if pos + 2 > len(iloc_data):
            return None
        item_count = struct.unpack('>H', iloc_data[pos:pos+2])[0]
        pos += 2
        
        for _ in range(item_count):
            if pos + 2 > len(iloc_data):
                break
            
            # item_id
            item_id = struct.unpack('>H', iloc_data[pos:pos+2])[0]
            pos += 2
            
            if version == 1 or version == 2:
                # construction_method (for version 1 or 2)
                if pos + 2 > len(iloc_data):
                    break
                pos += 2
            
            # data_reference_index
            if pos + 2 > len(iloc_data):
                break
            data_ref_index = struct.unpack('>H', iloc_data[pos:pos+2])[0]
            pos += 2
            
            # base_offset
            if base_offset_size == 4:
                if pos + 4 > len(iloc_data):
                    break
                base_offset = struct.unpack('>I', iloc_data[pos:pos+4])[0]
                pos += 4
            elif base_offset_size == 8:
                if pos + 8 > len(iloc_data):
                    break
                base_offset = struct.unpack('>Q', iloc_data[pos:pos+8])[0]
                pos += 8
            else:
                base_offset = 0
            
            # extent_count
            if pos + 2 > len(iloc_data):
                break
            extent_count = struct.unpack('>H', iloc_data[pos:pos+2])[0]
            pos += 2
            
            for _ in range(extent_count):
                # index (only for version 1 or 2 with index_size > 0)
                if index_size > 0:
                    if index_size == 4:
                        pos += 4
                    elif index_size == 8:
                        pos += 8
                
                # extent_offset
                if offset_size == 4:
                    if pos + 4 > len(iloc_data):
                        break
                    extent_offset = struct.unpack('>I', iloc_data[pos:pos+4])[0]
                    pos += 4
                elif offset_size == 8:
                    if pos + 8 > len(iloc_data):
                        break
                    extent_offset = struct.unpack('>Q', iloc_data[pos:pos+8])[0]
                    pos += 8
                else:
                    extent_offset = 0
                
                # extent_length
                if length_size == 4:
                    if pos + 4 > len(iloc_data):
                        break
                    pos += 4
                elif length_size == 8:
                    if pos + 8 > len(iloc_data):
                        break
                    pos += 8
                
                # Check if this is our exif item
                if item_id == exif_item_id:
                    return base_offset + extent_offset
        
        return None

    @classmethod
    def _extract_from_tiff(cls, f: BinaryIO) -> datetime | None:
        """Extract EXIF date from TIFF file (including RAW formats)."""
        f.seek(0)
        tiff_data = f.read(cls.MAX_EXIF_SIZE)
        return cls._parse_tiff_exif(tiff_data)

    @classmethod
    def _extract_from_webp(cls, f: BinaryIO) -> datetime | None:
        """Extract EXIF date from WebP file."""
        f.seek(0)
        
        # Read RIFF header
        riff_header = f.read(12)
        if len(riff_header) < 12:
            return None
        
        file_size = struct.unpack('<I', riff_header[4:8])[0]
        
        # Search for EXIF chunk
        remaining = min(file_size, cls.MAX_EXIF_SIZE)
        while remaining > 8:
            chunk_header = f.read(8)
            if len(chunk_header) < 8:
                break
            
            chunk_size = struct.unpack('<I', chunk_header[4:8])[0]
            chunk_type = chunk_header[0:4]
            
            if chunk_type == b'EXIF':
                exif_data = f.read(min(chunk_size, cls.MAX_EXIF_SIZE))
                if exif_data.startswith(b'Exif\x00\x00'):
                    return cls._parse_tiff_exif(exif_data[6:])
                return cls._parse_tiff_exif(exif_data)
            else:
                # Skip chunk (padded to even size)
                skip = chunk_size + (chunk_size % 2)
                f.seek(skip, 1)
                remaining -= 8 + skip
        
        return None

    @classmethod
    def _parse_tiff_exif(cls, data: bytes) -> datetime | None:
        """Parse TIFF-format EXIF data for date tags."""
        if len(data) < 8:
            return None
        
        # TIFF header
        byte_order = data[0:2]
        if byte_order == b'II':
            endian = '<'  # Little-endian
        elif byte_order == b'MM':
            endian = '>'  # Big-endian
        else:
            return None
        
        # Check TIFF magic number (42)
        magic = struct.unpack(f'{endian}H', data[2:4])[0]
        if magic != 42:
            return None
        
        # First IFD offset
        ifd_offset = struct.unpack(f'{endian}I', data[4:8])[0]
        
        # Parse IFDs
        dates = []
        visited_offsets = set()
        
        while ifd_offset > 0 and ifd_offset < len(data) and ifd_offset not in visited_offsets:
            visited_offsets.add(ifd_offset)
            result = cls._parse_ifd(data, ifd_offset, endian, dates)
            if result is None:
                break
            ifd_offset = result
        
        # Return the earliest valid date (DateTimeOriginal preferred)
        if dates:
            # Sort by tag priority
            for tag in EXIF_DATE_TAGS:
                for dt, t in dates:
                    if t == tag and dt is not None:
                        return dt
            
            # Return first valid date
            for dt, _ in dates:
                if dt is not None:
                    return dt
        
        return None

    @classmethod
    def _parse_ifd(cls, data: bytes, offset: int, endian: str, dates: list) -> int | None:
        """Parse an Image File Directory and collect date values."""
        if offset + 2 > len(data):
            return None
        
        entry_count = struct.unpack(f'{endian}H', data[offset:offset+2])[0]
        offset += 2
        
        for _ in range(entry_count):
            if offset + 12 > len(data):
                return None
            
            tag, field_type, count = struct.unpack(
                f'{endian}HHI', data[offset:offset+8]
            )
            value_offset = data[offset+8:offset+12]
            offset += 12
            
            # Check for date tags
            if tag in EXIF_DATE_TAGS and field_type == 2:  # ASCII string
                date_str = cls._read_value(data, value_offset, count, endian)
                dt = cls._parse_exif_date(date_str)
                if dt:
                    dates.append((dt, tag))
            
            # Check for SubIFD (ExifIFD)
            elif tag == 0x8769:  # ExifIFD
                sub_ifd_offset = struct.unpack(f'{endian}I', value_offset)[0]
                cls._parse_ifd(data, sub_ifd_offset, endian, dates)
            
            # Check for GPS IFD
            elif tag == 0x8825:  # GPSInfo
                pass  # GPS date not used
        
        # Next IFD offset
        if offset + 4 > len(data):
            return None
        return struct.unpack(f'{endian}I', data[offset:offset+4])[0]

    @classmethod
    def _read_value(cls, data: bytes, value_offset: bytes, count: int, endian: str) -> bytes:
        """Read a value from IFD entry."""
        if count <= 4:
            return value_offset[:count]
        else:
            offset = struct.unpack(f'{endian}I', value_offset)[0]
            if offset + count <= len(data):
                return data[offset:offset+count]
            return b''

    @staticmethod
    def _parse_exif_date(date_str: bytes) -> datetime | None:
        """Parse EXIF date format: 'YYYY:MM:DD HH:MM:SS'."""
        try:
            # Handle null-terminated strings
            date_str = date_str.rstrip(b'\x00').strip()
            if len(date_str) < 10:
                return None
            
            # Try standard EXIF format
            if b':' in date_str:
                # Format: YYYY:MM:DD HH:MM:SS
                s = date_str.decode('ascii', errors='ignore')
                # Replace colons in date part
                parts = s.split(' ')
                if len(parts) >= 1:
                    date_part = parts[0].replace(':', '-')
                    time_part = parts[1] if len(parts) > 1 else '00:00:00'
                    s = f'{date_part} {time_part}'
                return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
            
            return None
        except (ValueError, UnicodeDecodeError):
            return None
