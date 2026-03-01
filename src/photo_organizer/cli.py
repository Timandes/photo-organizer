"""Command-line interface for photo organizer."""

import argparse
import logging
import sys
from pathlib import Path

from photo_organizer import __version__
from photo_organizer.organizer import Organizer


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.WARNING
    format_str = '%(levelname)s: %(message)s' if verbose else '%(message)s'
    logging.basicConfig(level=level, format=format_str)


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog='photo-organizer',
        description='Organize photos and videos by media creation date.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                    Organize files in current directory
  %(prog)s --dry-run          Preview changes without moving files
  %(prog)s --verbose          Show detailed processing information
  %(prog)s --dry-run --verbose Preview with details

Supported formats:
  Images: JPEG, PNG, HEIC/HEIF, TIFF, WebP, RAW (CR2, NEF, ARW, DNG)
  Videos: MP4, MOV, 3GP, 3G2, M4V

Output directory format:
  [年].[月].[日]/[filename]
  Example: 2024.03.15/photo.jpg
'''
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='preview changes without moving files'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='show detailed processing information'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Run organizer
    organizer = Organizer(dry_run=args.dry_run, verbose=args.verbose)
    organizer.run()


if __name__ == '__main__':
    main()
