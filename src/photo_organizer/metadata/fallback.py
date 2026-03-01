"""Fallback date extraction from file system metadata."""

import os
from datetime import datetime, timezone
from pathlib import Path


def get_filesystem_date(file_path: Path) -> datetime | None:
    """Get file creation/modification time as fallback date.
    
    Tries in order:
    1. st_birthtime (macOS/BSD) - actual creation time
    2. st_ctime (Linux) - metadata change time (closest to creation on Linux)
    3. st_mtime - modification time
    
    Args:
        file_path: Path to the file
        
    Returns:
        datetime object or None if file cannot be accessed
    """
    try:
        stat = file_path.stat()
        
        # Try birthtime first (macOS, BSD, some Windows)
        # Not all platforms have st_birthtime
        birthtime = getattr(stat, 'st_birthtime', None)
        if birthtime is not None and birthtime > 0:
            return datetime.fromtimestamp(birthtime, tz=timezone.utc)
        
        # On Linux, st_ctime is metadata change time
        # It's the closest we have to creation time
        if stat.st_ctime > 0:
            return datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
        
        # Fallback to modification time
        if stat.st_mtime > 0:
            return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        
    except OSError:
        pass
    
    return None
