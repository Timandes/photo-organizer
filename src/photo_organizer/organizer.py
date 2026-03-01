"""Core organizer logic for photo/video file organization."""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterator

from photo_organizer.metadata.exif import ExifExtractor
from photo_organizer.metadata.quicktime import QuickTimeExtractor
from photo_organizer.metadata.fallback import get_filesystem_date


logger = logging.getLogger(__name__)


class Organizer:
    """Organize media files by creation date into date-based directories."""

    def __init__(self, dry_run: bool = False, verbose: bool = False):
        """Initialize the organizer.
        
        Args:
            dry_run: If True, only show what would be done without moving files
            verbose: If True, show detailed information
        """
        self.dry_run = dry_run
        self.verbose = verbose
        
        # Statistics
        self.processed = 0
        self.moved = 0
        self.skipped = 0
        self.errors = 0

    def scan_files(self, directory: Path) -> list[Path]:
        """Scan directory for files (non-recursive).
        
        Args:
            directory: Directory to scan
            
        Returns:
            List of file paths (excludes directories and hidden files)
        """
        files = []
        for item in directory.iterdir():
            # Skip directories
            if item.is_dir():
                continue
            # Skip hidden files
            if item.name.startswith('.'):
                continue
            # Skip symbolic links
            if item.is_symlink():
                continue
            files.append(item)
        return sorted(files)

    def get_date(self, file_path: Path) -> datetime | None:
        """Extract date from file metadata.
        
        Priority:
        1. EXIF metadata (images)
        2. QuickTime metadata (videos)
        3. File system time (fallback)
        
        Args:
            file_path: Path to the file
            
        Returns:
            datetime object or None if date cannot be determined
        """
        # Try EXIF extractor for images
        if ExifExtractor.can_handle(file_path):
            dt = ExifExtractor.extract_date(file_path)
            if dt:
                if self.verbose:
                    logger.info(f"  EXIF date: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                return dt

        # Try QuickTime extractor for videos
        if QuickTimeExtractor.can_handle(file_path):
            dt = QuickTimeExtractor.extract_date(file_path)
            if dt:
                if self.verbose:
                    logger.info(f"  QuickTime date: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                return dt

        # Fallback to file system time
        dt = get_filesystem_date(file_path)
        if dt:
            if self.verbose:
                logger.info(f"  Filesystem date: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            return dt

        return None

    def get_target_path(self, file_path: Path, date: datetime) -> Path:
        """Get target path for a file based on its date.
        
        Args:
            file_path: Original file path
            date: File date
            
        Returns:
            Target path in format: [年].[月].[日]/[filename]
        """
        # Format directory name
        dir_name = f"{date.year}.{date.month:02d}.{date.day:02d}"
        target_dir = file_path.parent / dir_name
        
        return target_dir / file_path.name

    def get_unique_path(self, target_path: Path) -> Path:
        """Get unique target path by adding numeric suffix if needed.
        
        Args:
            target_path: Desired target path
            
        Returns:
            Unique path that doesn't conflict with existing files
        """
        if not target_path.exists():
            return target_path

        # Add numeric suffix
        stem = target_path.stem
        suffix = target_path.suffix
        parent = target_path.parent
        
        counter = 1
        while True:
            new_name = f"{stem}_{counter:03d}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
            if counter > 9999:
                raise ValueError(f"Too many file conflicts for {target_path}")

    def organize_file(self, file_path: Path) -> bool:
        """Organize a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file was organized successfully, False otherwise
        """
        self.processed += 1
        
        # Get date
        dt = self.get_date(file_path)
        if not dt:
            logger.warning(f"Cannot determine date for: {file_path.name}")
            self.skipped += 1
            return False

        # Get target path
        target_path = self.get_target_path(file_path, dt)
        
        # Check if already in correct location
        if target_path == file_path:
            if self.verbose:
                logger.info(f"  Already in correct location: {file_path.name}")
            self.skipped += 1
            return True

        # Handle conflicts
        if target_path.exists():
            target_path = self.get_unique_path(target_path)

        # Log action
        relative_target = target_path.relative_to(file_path.parent)
        if self.dry_run:
            print(f"[DRY-RUN] {file_path.name} -> {relative_target}")
        else:
            print(f"{file_path.name} -> {relative_target}")
            # Create target directory
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # Move file
            try:
                shutil.move(str(file_path), str(target_path))
                self.moved += 1
            except OSError as e:
                logger.error(f"Failed to move {file_path.name}: {e}")
                self.errors += 1
                return False

        return True

    def run(self, directory: Path | None = None) -> None:
        """Run the organizer on the specified directory.
        
        Args:
            directory: Directory to organize (defaults to current directory)
        """
        if directory is None:
            directory = Path.cwd()
        
        print(f"Scanning directory: {directory}")
        files = self.scan_files(directory)
        
        if not files:
            print("No files found.")
            return

        print(f"Found {len(files)} file(s).\n")
        
        if self.dry_run:
            print("=== DRY RUN MODE (no files will be moved) ===\n")

        # Process each file
        for file_path in files:
            if self.verbose:
                print(f"\nProcessing: {file_path.name}")
            self.organize_file(file_path)

        # Print summary
        print(f"\n=== Summary ===")
        print(f"Processed: {self.processed}")
        if not self.dry_run:
            print(f"Moved: {self.moved}")
        print(f"Skipped: {self.skipped}")
        if self.errors:
            print(f"Errors: {self.errors}")
