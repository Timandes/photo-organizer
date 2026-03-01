"""QuickTime/MP4 metadata extractor for video files.

Optimized to read only necessary atoms from the file.
"""

import struct
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import BinaryIO


# QuickTime epoch: January 1, 1904
QUICKTIME_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)

# Maximum bytes to scan for metadata
MAX_SCAN_SIZE = 1024 * 1024  # 1MB should contain moov atom


class QuickTimeExtractor:
    """Extract creation date from QuickTime/MP4 video files."""

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {'.mp4', '.mov', '.3gp', '.3g2', '.m4v', '.m4a'}

    # QuickTime/MP4 file types
    QT_BRANDS = {
        b'qt  ',  # QuickTime
        b'mp41', b'mp42',  # MP4 v1/v2
        b'isom', b'iso2', b'iso3', b'iso4', b'iso5', b'iso6',  # ISO Base Media
        b'avc1', b'msdh',  # AVC
        b'M4V ', b'M4A ', b'M4P ',  # iTunes
        b'3gp4', b'3gp5', b'3gp6', b'3g2a',  # 3GPP
        b'heic', b'heix', b'mif1',  # HEIF (may contain video)
    }

    @classmethod
    def can_handle(cls, file_path: Path) -> bool:
        """Check if this extractor can handle the file type."""
        suffix = file_path.suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def extract_date(cls, file_path: Path) -> datetime | None:
        """Extract creation date from QuickTime/MP4 metadata."""
        try:
            with open(file_path, 'rb') as f:
                return cls._extract_from_file(f)
        except (OSError, struct.error):
            return None

    @classmethod
    def _extract_from_file(cls, f: BinaryIO) -> datetime | None:
        """Parse QuickTime/MP4 file for creation date."""
        # Read ftyp atom to verify file type
        ftyp_data = f.read(20)
        if len(ftyp_data) < 12:
            return None

        # Verify it's a QuickTime/MP4 file
        if not cls._verify_ftyp(ftyp_data):
            return None

        # Parse atoms looking for moov
        dates: list[tuple[datetime, int]] = []  # (date, priority)
        
        f.seek(0)
        end_scan = MAX_SCAN_SIZE
        
        while f.tell() < end_scan:
            atom = cls._read_atom_header(f)
            if atom is None:
                break
            
            atom_type, atom_size, atom_data = atom
            
            if atom_type == b'moov':
                # Parse moov atom for metadata
                cls._parse_moov(atom_data, f, dates, atom_size)
                break  # moov contains all we need
            elif atom_type == b'mdat':
                # Media data - skip and continue
                if atom_size > 0:
                    remaining = atom_size - 8
                    f.seek(remaining, 1)
            else:
                # Skip unknown atoms
                if atom_size > 8:
                    remaining = atom_size - 8
                    f.seek(remaining, 1)

        # Return date by priority
        if dates:
            dates.sort(key=lambda x: x[1])  # Sort by priority (lower is better)
            return dates[0][0]

        return None

    @classmethod
    def _verify_ftyp(cls, data: bytes) -> bool:
        """Verify file type from ftyp atom."""
        if len(data) < 12:
            return False
        
        size, atom_type = struct.unpack('>I4s', data[0:8])
        
        if atom_type != b'ftyp':
            return False
        
        brand = data[8:12]
        return brand in cls.QT_BRANDS

    @classmethod
    def _read_atom_header(cls, f: BinaryIO) -> tuple[bytes, int, bytes] | None:
        """Read QuickTime atom header."""
        header = f.read(8)
        if len(header) < 8:
            return None

        size, atom_type = struct.unpack('>I4s', header)

        if size == 1:
            # Extended size (64-bit)
            ext_size = f.read(8)
            if len(ext_size) < 8:
                return None
            size = struct.unpack('>Q', ext_size)[0]
        elif size == 0:
            # Atom extends to end of file
            current = f.tell()
            f.seek(0, 2)  # Seek to end
            end = f.tell()
            f.seek(current)
            size = end - current + 8

        return atom_type, size, header

    @classmethod
    def _parse_moov(cls, atom_data: bytes, f: BinaryIO, dates: list, total_size: int):
        """Parse moov atom for creation date metadata."""
        # Read moov atom content
        content_size = total_size - 8
        content_size = min(content_size, MAX_SCAN_SIZE)
        
        moov_data = f.read(content_size)
        pos = 0

        while pos < len(moov_data) - 8:
            try:
                size, atom_type = struct.unpack('>I4s', moov_data[pos:pos+8])
                if size < 8:
                    break

                atom_content = moov_data[pos+8:pos+size]

                if atom_type == b'mvhd':
                    # Movie header contains creation time
                    dt = cls._parse_mvhd(atom_content)
                    if dt:
                        dates.append((dt, 1))

                elif atom_type == b'meta':
                    # Metadata may contain ContentCreateDate
                    cls._parse_meta(atom_content, dates)

                elif atom_type == b'udta':
                    # User data may contain metadata
                    cls._parse_udta(atom_content, dates)

                elif atom_type == b'trak':
                    # Track may have tkhd with creation time
                    cls._parse_trak(atom_content, dates)

                pos += size
            except struct.error:
                break

    @classmethod
    def _parse_mvhd(cls, data: bytes) -> datetime | None:
        """Parse movie header atom for creation time."""
        if len(data) < 20:
            return None

        version = data[0]

        if version == 0:
            # 32-bit format
            if len(data) < 20:
                return None
            creation_time = struct.unpack('>I', data[4:8])[0]
            mod_time = struct.unpack('>I', data[8:12])[0]
        else:
            # 64-bit format
            if len(data) < 36:
                return None
            creation_time = struct.unpack('>Q', data[8:16])[0]
            mod_time = struct.unpack('>Q', data[16:24])[0]

        # Convert QuickTime timestamp
        if creation_time > 0:
            return cls._quicktime_to_datetime(creation_time)
        
        return None

    @classmethod
    def _parse_meta(cls, data: bytes, dates: list):
        """Parse metadata atom for ContentCreateDate."""
        # Meta atom has version/flags before hdlr/ilst
        pos = 0
        if len(data) < 12:
            return

        # Skip version/flags if present (4 bytes)
        # Look for ilst (item list)
        while pos < len(data) - 8:
            try:
                size, atom_type = struct.unpack('>I4s', data[pos:pos+8])
                if size < 8:
                    break

                if atom_type == b'ilst':
                    cls._parse_ilst(data[pos+8:pos+size], dates)
                    break

                pos += size
            except struct.error:
                break

    @classmethod
    def _parse_ilst(cls, data: bytes, dates: list):
        """Parse item list atom for creation date."""
        # Common metadata item types for creation date:
        # - com.apple.quicktime.creationdate (in ---- atom)
        # - ©day (day atom, 0xa9day)
        
        pos = 0
        while pos < len(data) - 8:
            try:
                size, atom_type = struct.unpack('>I4s', data[pos:pos+8])
                if size < 8:
                    break

                item_data = data[pos+8:pos+size]

                # Check for creation date related atoms
                if atom_type == b'\xa9day':
                    # ©day - content creation date as string
                    dt = cls._parse_metadata_string(item_data)
                    if dt:
                        dates.append((dt, 0))  # Highest priority

                elif atom_type == b'----':
                    # Free form metadata - check for creationdate
                    dt = cls._parse_freeform_metadata(item_data)
                    if dt:
                        dates.append((dt, 0))  # Highest priority

                pos += size
            except struct.error:
                break

    @classmethod
    def _parse_udta(cls, data: bytes, dates: list):
        """Parse user data atom for metadata."""
        pos = 0
        while pos < len(data) - 8:
            try:
                size, atom_type = struct.unpack('>I4s', data[pos:pos+8])
                if size < 8:
                    break

                if atom_type == b'meta':
                    cls._parse_meta(data[pos+8:pos+size], dates)

                pos += size
            except struct.error:
                break

    @classmethod
    def _parse_trak(cls, data: bytes, dates: list):
        """Parse track atom for track header creation time."""
        pos = 0
        while pos < len(data) - 8:
            try:
                size, atom_type = struct.unpack('>I4s', data[pos:pos+8])
                if size < 8:
                    break

                if atom_type == b'tkhd':
                    dt = cls._parse_tkhd(data[pos+8:pos+size])
                    if dt:
                        dates.append((dt, 2))  # Lower priority than mvhd

                pos += size
            except struct.error:
                break

    @classmethod
    def _parse_tkhd(cls, data: bytes) -> datetime | None:
        """Parse track header atom for creation time."""
        if len(data) < 20:
            return None

        version = data[0]

        if version == 0:
            creation_time = struct.unpack('>I', data[4:8])[0]
        else:
            if len(data) < 28:
                return None
            creation_time = struct.unpack('>Q', data[8:16])[0]

        if creation_time > 0:
            return cls._quicktime_to_datetime(creation_time)
        
        return None

    @classmethod
    def _parse_metadata_string(cls, data: bytes) -> datetime | None:
        """Parse metadata string value for date."""
        # Data atom structure: [size][type='data'][...]
        if len(data) < 16:
            return None

        # Find 'data' atom
        pos = 0
        while pos < len(data) - 8:
            size, atom_type = struct.unpack('>I4s', data[pos:pos+8])
            if atom_type == b'data' and size >= 16:
                # Data type (4 bytes) + locale (4 bytes) + value
                value = data[pos+16:pos+size]
                try:
                    value_str = value.decode('utf-8', errors='ignore').strip('\x00')
                    # Parse ISO date format
                    if 'T' in value_str:
                        return datetime.fromisoformat(value_str.replace('Z', '+00:00'))
                    elif len(value_str) >= 10:
                        return datetime.strptime(value_str[:10], '%Y-%m-%d')
                except (ValueError, UnicodeDecodeError):
                    pass
                break
            pos += size if size > 0 else 8

        return None

    @classmethod
    def _parse_freeform_metadata(cls, data: bytes) -> datetime | None:
        """Parse freeform metadata (----) for creationdate."""
        # Format: [size][----][mean][name][data]
        pos = 0
        mean = None
        name = None

        while pos < len(data) - 8:
            try:
                size, atom_type = struct.unpack('>I4s', data[pos:pos+8])
                if size < 8:
                    break

                item_data = data[pos+8:pos+size]

                if atom_type == b'mean':
                    # Skip version/flags (4 bytes)
                    mean = item_data[4:].decode('utf-8', errors='ignore').strip('\x00')
                elif atom_type == b'name':
                    name = item_data[4:].decode('utf-8', errors='ignore').strip('\x00')
                elif atom_type == b'data':
                    if name and 'creationdate' in name.lower():
                        # Found creation date
                        if len(item_data) >= 12:
                            value = item_data[8:]  # Skip type and locale
                            try:
                                value_str = value.decode('utf-8', errors='ignore').strip('\x00')
                                if 'T' in value_str:
                                    return datetime.fromisoformat(value_str.replace('Z', '+00:00'))
                                elif len(value_str) >= 10:
                                    return datetime.strptime(value_str[:10], '%Y-%m-%d')
                            except (ValueError, UnicodeDecodeError):
                                pass

                pos += size
            except (struct.error, UnicodeDecodeError):
                break

        return None

    @classmethod
    def _quicktime_to_datetime(cls, timestamp: int) -> datetime | None:
        """Convert QuickTime timestamp to datetime."""
        # QuickTime epoch is 1904-01-01
        # Valid range: reasonable dates between 1970 and 2100
        if timestamp < 2082844800:  # Before 1970-01-01 in QT time
            return None
        if timestamp > 6190915200:  # After 2100-01-01 in QT time
            # Might be Unix timestamp instead
            try:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                return None

        try:
            delta = timedelta(seconds=timestamp)
            dt = QUICKTIME_EPOCH + delta
            return dt
        except OverflowError:
            return None
