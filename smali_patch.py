#!/usr/bin/env python3
"""
Smalipatcher :  utility for applying patches to .smali files.

Tags:
- CREDIT: Attribution support
- FILE: Patch existing files with multiple actions
Actions:
- CREATE: Create new files
- REMOVE: Delete files
- PATCH: Context-based code patching
- REPLACE: Replace entire methods
- CREATE_METHOD: Add new methods
- REMOVE_METHOD: Delete methods
- ADD_FIELD: Add static/instance fields
- REMOVE_FIELD: Remove fields
- FIND_REPLACE: Replaces all matching titles


Usage:
    smalipatcher.py <work_dir> <patch_file> [options]

Arguments:
    work_dir     Root directory containing smali files
    patch_file   Path to .smalipatch file

Options:
    --skip-failed    Continue execution even if a patch fails
    --dry-run       Preview changes without applying them
    --verbose       Show detailed operation information
    --quiet         Minimize output (only show errors)

Examples:
    # Apply patches, stop on first failure
    smalipatcher.py ./decompiled_app patches/x1q_hfr_mode.smalipatch

    # Apply patches, continue on failures
    smalipatcher.py ./app patches/fix.smalipatch --skip-failed

    # Preview changes without applying
    smalipatcher.py ./app patches/test.smalipatch --dry-run

Exit Codes:
    0: All patches applied successfully
    1: One or more patches failed
    2: Invalid arguments or file not found
"""

import os
import sys
import logging
import argparse
from typing import List, Optional
from pathlib import Path


import patch_helper

__version__ = "1.2.5"

class ColoredFormatter(logging.Formatter):
    """Custom formatter with color support."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[37m',     # White
        'WARNING': '\033[93m',  # Yellow
        'ERROR': '\033[91m',    # Red
        'CRITICAL': '\033[95m', # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        if hasattr(record, 'no_color') or os.getenv('NO_COLOR'):
            return super().format(record)
        
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging(verbose: bool = False, quiet: bool = False):
    """Configure logging with optional color support."""
    if os.name == 'nt':
        try:
            import colorama
            colorama.init()
        except ImportError:
            pass
    
    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)
    
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter('%(message)s'))
    
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)


def validate_inputs(work_dir: str, patch_file: str) -> bool:
    """Validate input arguments."""
    work_path = Path(work_dir)
    patch_path = Path(patch_file)
    
    if not work_path.exists():
        logging.error(f"ERROR: Work directory does not exist: {work_dir}")
        return False
    
    if not work_path.is_dir():
        logging.error(f"ERROR: Work directory path is not a directory: {work_dir}")
        return False
    
    if not patch_path.exists():
        logging.error(f"ERROR: Patch file does not exist: {patch_file}")
        return False
    
    if not patch_path.is_file():
        logging.error(f"ERROR: Patch file path is not a file: {patch_file}")
        return False
    
    if not patch_file.endswith('.smalipatch'):
        logging.warning(f"WARNING: Patch file should have .smalipatch extension")
    
    return True


def apply_smalipatch(
    work_dir: str, 
    patch_file: str, 
    stop_on_fail: bool, 
    dry_run: bool = False
) -> bool:
    """
    Apply patches from a .smalipatch file.
    
    Args:
        work_dir: Root directory containing smali files
        patch_file: Path to patch file
        stop_on_fail: Whether to stop on first failure
        dry_run: If True, preview changes without applying
    
    Returns:
        True if all patches succeeded, False otherwise
    """
    
    try:
        with open(patch_file, 'r', encoding='utf-8') as f:
            lines = [line.rstrip('\r\n') for line in f.readlines()]
    except IOError as e:
        logging.error(f"ERROR: Could not read patch file {patch_file}: {e}")
        return False

    if not lines:
        logging.error(f"ERROR: Empty patch file {patch_file}")
        return False

  
    patches, credits = patch_helper.parse_patches(lines)
    
    if not patches and not credits:
        logging.error(f"ERROR: No valid patch definitions found in {patch_file}")
        return False

    
    logging.info("\n" + "="*60)
    logging.info(f" SMALIPATCHER v{__version__}")
    logging.info(f" Patch Set: {Path(patch_file).name}")
    logging.info(f" Mode: {'DRY RUN (Preview Only)' if dry_run else 'APPLY'}")
    
    if credits:
        logging.info(" Credits:")
        for credit in credits:
            logging.info(f"  • {credit}")
    
    logging.info("="*60 + "\n")

    # Apply patches
    success_count = 0
    failed_count = 0
    skipped_count = 0
    total_patches = len(patches)
    
    if total_patches == 0:
        logging.info("Info: Patch file contained credits but no actual patches.")
        return True

    for i, patch in enumerate(patches, 1):
        patch_type = patch.get('type', 'FILE')
        file_path = patch.get('file_path', 'unknown')
        
        
        prefix = f"[{i}/{total_patches}]"

            if patch_type == 'CREATE':
            logging.info(f"{prefix} CREATE: {file_path}")
        elif patch_type == 'REMOVE':
            logging.info(f"{prefix} REMOVE: {file_path}")
        elif patch_type == 'FIND_REPLACE':
            logging.info(f"{prefix} GLOBAL REPLACE")
        else:
            action_count = len(patch.get('actions', []))
            logging.info(f"{prefix} PATCH:  {file_path} ({action_count} action{'s' if action_count != 1 else ''})")


        try:
            if patch_type == 'CREATE':
                result = patch_helper.apply_create_action(work_dir, patch, dry_run)
            elif patch_type == 'REMOVE':
                result = patch_helper.apply_remove_file(work_dir, patch, dry_run)
            elif patch_type == 'FIND_REPLACE':

                result = patch_helper.apply_global_find_replace(work_dir, patch, dry_run)
            else:
                result = patch_helper.apply_file_patch(work_dir, patch, dry_run)

            if result in ("applied", "created"):
                success_count += 1
            elif result == "skipped":
                skipped_count += 1
            else:
                failed_count += 1
                if stop_on_fail:
                    logging.error("\n✗ Stopping execution due to failure.")
                    break
        
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            failed_count += 1
            if stop_on_fail:
                logging.error("\n✗ Stopping execution due to error.")
                break

    
    logging.info("\n" + "="*60)
    logging.info(" SUMMARY")
    logging.info(f" Total Patches: {total_patches}")
    logging.info(f" ✓ Successful:  {success_count}")
    
    if skipped_count > 0:
        logging.info(f" ~ Skipped:     {skipped_count}")
    
    if failed_count > 0:
        logging.error(f" Failed:      {failed_count}")
    
    if dry_run:
        logging.info("\n DRY RUN: No changes were written to disk.")
    
    logging.info("="*60 + "\n")

    return failed_count == 0


def main():
    parser = argparse.ArgumentParser(
        description="Smalipatcher - Professional smali patching utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./app patches/fix.smalipatch
  %(prog)s ./app patches/bundle.smalipatch --skip-failed
  %(prog)s ./app patches/test.smalipatch --dry-run --verbose

For more information, visit: https://github.com/SameerAlSahab/smalipatcher
        """
    )
    
    parser.add_argument(
        'work_dir',
        help='Root directory containing smali files'
    )
    
    parser.add_argument(
        'patch_file',
        help='Path to .smalipatch file'
    )
    
    parser.add_argument(
        '--skip-failed',
        action='store_true',
        help='Continue execution even if a patch fails (default: stop on failure)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output for debugging'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimize output (only show errors)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    args = parser.parse_args()

    
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    
    if not validate_inputs(args.work_dir, args.patch_file):
        sys.exit(2)

    # Apply patches
    success = apply_smalipatch(
        args.work_dir,
        args.patch_file,
        stop_on_fail=not args.skip_failed,
        dry_run=args.dry_run
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
