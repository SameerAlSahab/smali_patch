#!/usr/bin/env python3
"""
Smalipatcher: Utility for applying patches to .smali files.

Tags:
- CREDIT: Attribution support
- FILE: Patch existing files with multiple actions

Actions:
- CREATE: Create new files
- REMOVE: Delete files
- REMOVE_FILE: Delete specific file
- PATCH: Context-based code patching
- REPLACE: Replace entire methods
- CREATE_METHOD: Add new methods
- REMOVE_METHOD: Delete methods
- ADD_FIELD: Add static/instance fields
- REMOVE_FIELD: Remove fields
- FIND_REPLACE: Replace all matching patterns (requires FILE tag)

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
    smalipatcher.py ./decompiled_app patches/fix.smalipatch
    smalipatcher.py ./app patches/fix.smalipatch --skip-failed
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
from pathlib import Path

import patch_helper

__version__ = "1.3.0"


def setup_logging(verbose: bool = False, quiet: bool = False):

    level = logging.WARNING if quiet else (logging.DEBUG if verbose else logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)


def validate_inputs(work_dir: str, patch_file: str) -> bool:

    work_path = Path(work_dir)
    patch_path = Path(patch_file)

    if not work_path.exists():
        print(f"Error: Work directory does not exist: {work_dir}")
        return False

    if not work_path.is_dir():
        print(f"Error: Work directory path is not a directory: {work_dir}")
        return False

    if not patch_path.exists():
        print(f"Error: Patch file does not exist: {patch_file}")
        return False

    if not patch_path.is_file():
        print(f"Error: Patch file path is not a file: {patch_file}")
        return False

    if not patch_file.endswith('.smalipatch'):
        print(f"Warning: Patch file should have .smalipatch extension")

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
        print(f"Error: Could not read patch file {patch_file}: {e}")
        return False

    if not lines:
        print(f"Error: Empty patch file {patch_file}")
        return False

    try:
        patches, credits = patch_helper.parse_patches(lines)
    except Exception as e:
        print(f"Error: Failed to parse patch file")
        print(f"  Reason: {e}")
        return False

    if not patches and not credits:
        print(f"Error: No valid patch definitions found in {patch_file}")
        return False

    # Show credits if available
    if credits:
        for credit in credits:
            print(f"Credit: {credit}")

    if len(patches) == 0:
        print("Info: Patch file contained credits but no actual patches")
        return True

    # Apply patches
    all_success = True

    for i, patch in enumerate(patches, 1):
        patch_type = patch.get('type', 'FILE')
        file_path = patch.get('file_path', 'unknown')
        patch_name = Path(patch_file).stem

        print(f"Applying {patch_name}")

        try:
            if patch_type == 'CREATE':
                result, error_msg = patch_helper.apply_create_action(work_dir, patch, dry_run)
            elif patch_type == 'REMOVE' or patch_type == 'REMOVE_FILE':
                result, error_msg = patch_helper.apply_remove_file(work_dir, patch, dry_run)
            elif patch_type == 'FIND_REPLACE':
                result, error_msg = patch_helper.apply_find_replace(work_dir, patch, dry_run)
            else:
                result, error_msg = patch_helper.apply_file_patch(work_dir, patch, dry_run)

            if not result:
                all_success = False
                print(f"  Failed: {error_msg}")
                if stop_on_fail:
                    break

        except Exception as e:
            all_success = False
            print(f"  Failed: {str(e)}")
            if stop_on_fail:
                break

    return all_success


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

    parser.add_argument('work_dir', help='Root directory containing smali files')
    parser.add_argument('patch_file', help='Path to .smalipatch file')
    parser.add_argument('--skip-failed', action='store_true',
                       help='Continue execution even if a patch fails')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without modifying files')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output for debugging')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Minimize output (only show errors)')
    parser.add_argument('--version', action='version',
                       version=f'%(prog)s {__version__}')

    args = parser.parse_args()

    setup_logging(verbose=args.verbose, quiet=args.quiet)

    if not validate_inputs(args.work_dir, args.patch_file):
        sys.exit(2)

    success = apply_smalipatch(
        args.work_dir,
        args.patch_file,
        stop_on_fail=not args.skip_failed,
        dry_run=args.dry_run
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
