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
        
        while True:
            box_header = f.read(8)
            if len(box_header) < 8:
                break
            
            size, box_type = struct.unpack('>I4s', box_header)
            
            if size == 0:
                # Box extends to end of file
                break
            elif size == 1:
                # Extended size
                size = struct.unpack('>Q', f.read(8))[0]
            
            if box_type == b'meta':
                # Meta box contains EXIF
                return cls._parse_heic_meta(f, size - 8)
            else:
                # Skip to next box
                f.seek(size - 8, 1)
        
        return None

    @classmethod
    def _parse_heic_meta(cls, f: BinaryIO, remaining: int) -> datetime | None:
        """Parse HEIC meta box for EXIF data."""
        # Read meta box content (limited)
        meta_data = f.read(min(remaining, cls.MAX_EXIF_SIZE))
        
        # Look for Exif item in iloc/infe boxes
        # This is a simplified parser - look for Exif payload
        pos = 0
        while pos < len(meta_data) - 8:
            try:
                size, box_type = struct.unpack('>I4s', meta_data[pos:pos+8])
                if size < 8:
                    break
                
                if box_type == b'iloc':
                    # Item location box - find Exif item
                    pass
                elif box_type == b'iinf':
                    # Item info box
                    pass
                elif box_type == b'iprp':
                    # Item properties - may contain Exif data
                    # Search for Exif TIFF header in remaining data
                    exif_pos = meta_data.find(b'Exif\x00\x00', pos)
                    if exif_pos >= 0:
                        tiff_data = meta_data[exif_pos + 6:]
                        if len(tiff_data) > 8:
                            return cls._parse_tiff_exif(tiff_data)
                
                pos += size
            except struct.error:
                break
        
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
