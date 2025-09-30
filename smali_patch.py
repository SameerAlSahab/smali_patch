#!/usr/bin/env python3
import os
import sys
import re
import logging
import argparse

def setup_logging(verbose=False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format='%(levelname)s: %(message)s',
        level=level
    )

def apply_smalipatch(work_dir, patch_file, dry_run=False):
    """Apply .smalipatch files to smali files"""
    
    with open(patch_file, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\r\n') for line in f.readlines()]
    
    if not lines:
        logging.error(f"Empty patch file {patch_file}")
        return False
    
    patches = parse_patches(lines)
    if not patches:
        logging.error(f"No valid patches found in {patch_file}")
        return False
    
    success_count = 0
    for i, patch in enumerate(patches):
        logging.info(f"Applying patch {i+1}/{len(patches)}...")
        if apply_single_patch(work_dir, patch, dry_run):
            success_count += 1
    
    logging.info(f"Applied {success_count}/{len(patches)} patches successfully")
    return success_count > 0

def parse_patches(lines):
    """Parse multiple patches from a single file"""
    patches = []
    current_patch = None
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('FILE '):
            if current_patch:
                patches.append(current_patch)
            current_patch = {
                'file_path': line[5:].strip(),
                'actions': []
            }
            i += 1
            
        elif line == 'END' and current_patch:
            patches.append(current_patch)
            current_patch = None
            i += 1
            
        elif current_patch is not None:
            if line.startswith('REPLACE '):
                method_sig = line[8:].strip()
                patch_content = []
                i += 1
                while i < len(lines) and not lines[i].strip() in ['END', 'FILE ']:
                    patch_content.append(lines[i])
                    i += 1
                current_patch['actions'].append({
                    'type': 'REPLACE',
                    'method_sig': method_sig,
                    'content': patch_content
                })
                
            elif line.startswith('PATCH '):
                # Check if method signature is provided
                patch_header = line[6:].strip()
                method_sig = None
                if patch_header and not patch_header.startswith(('+', '-')):
                    # Method signature provided, extract it
                    method_sig = patch_header
                    i += 1
                else:
                    # No method signature, use context-based search
                    i += 1
                
                # Parse patch content with simple +/- logic
                patch_operations = []
                
                # Read patch content until END or next FILE
                while i < len(lines) and not lines[i].strip() in ['END', 'FILE ']:
                    patch_line = lines[i]
                    if patch_line.startswith('+ '):
                        patch_operations.append(('+', patch_line[2:]))
                    elif patch_line.startswith('- '):
                        patch_operations.append(('-', patch_line[2:]))
                    else:
                        # Regular line (context)
                        patch_operations.append((' ', patch_line))
                    i += 1
                
                current_patch['actions'].append({
                    'type': 'PATCH',
                    'method_sig': method_sig,
                    'operations': patch_operations
                })
            else:
                i += 1
        else:
            i += 1
    
    # Add the last patch if exists
    if current_patch:
        patches.append(current_patch)
    
    return patches

def apply_single_patch(work_dir, patch, dry_run=False):
    """Apply a single patch to a file"""
    file_path = patch['file_path']
    full_path = os.path.join(work_dir, file_path)
    
    if not os.path.exists(full_path):
        logging.error(f"Target file not found: {full_path}")
        return False
    
    # Read the target smali file
    with open(full_path, 'r', encoding='utf-8') as f:
        smali_lines = [line.rstrip('\r\n') for line in f.readlines()]
    
    original_lines = smali_lines.copy()
    new_lines = smali_lines.copy()
    modified = False
    
    for action in patch['actions']:
        if action['type'] == 'REPLACE':
            result = apply_replace_action(new_lines, action, dry_run)
            if result:
                new_lines = result
                modified = True
            else:
                return False
                
        elif action['type'] == 'PATCH':
            result = apply_patch_action(new_lines, action, dry_run)
            if result:
                new_lines = result
                modified = True
            else:
                return False
    
    if modified and not dry_run:
        # Write the modified content back
        with open(full_path, 'w', encoding='utf-8', newline='\n') as f:
            for line in new_lines:
                f.write(line + '\n')
        logging.info(f"SUCCESS: Applied patch to {file_path}")
        return True
    elif dry_run and modified:
        logging.info(f"DRY-RUN: Would apply patch to {file_path}")
        show_diff(original_lines, new_lines)
        return True
    
    return False

def apply_replace_action(smali_lines, action, dry_run=False):
    """Apply REPLACE action - replace entire method using regex matching"""
    method_sig = action['method_sig']
    patch_content = action['content']
    
    # Convert simple method signature to regex pattern
    pattern = method_sig_to_regex(method_sig)
    
    new_lines = []
    i = 0
    replaced = False
    
    while i < len(smali_lines):
        line = smali_lines[i]
        
        if not replaced and re.match(pattern, line):
            # Found the method signature using regex
            logging.debug(f"Found method with regex: {pattern}")
            new_lines.append(line)
            i += 1
            replaced = True
            
            # Skip all lines until .end method
            while i < len(smali_lines) and not smali_lines[i].startswith('.end method'):
                i += 1
            
            # Add the patch content
            for patch_line in patch_content:
                new_lines.append(patch_line)
            
            # Add the .end method
            if i < len(smali_lines):
                new_lines.append(smali_lines[i])
                i += 1
        else:
            new_lines.append(line)
            i += 1
    
    if not replaced:
        logging.error(f"Method not found with pattern: {pattern}")
        return None
        
    return new_lines

def apply_patch_action(smali_lines, action, dry_run=False):
    """Apply PATCH action with simple +/- logic"""
    operations = action['operations']
    method_sig = action['method_sig']
    
    if not operations:
        logging.error("PATCH action requires operations")
        return None
    
    # Extract context lines (regular lines without +/-)
    context_lines = [line for op, line in operations if op == ' ']
    
    if not context_lines:
        logging.error("PATCH action requires context lines (lines without +/-)")
        return None
    
    # If method signature is provided, search within that method
    search_range = None
    if method_sig:
        pattern = method_sig_to_regex(method_sig)
        method_start, method_end = find_method_range(smali_lines, pattern)
        if method_start == -1:
            logging.error(f"Method not found with pattern: {pattern}")
            return None
        search_range = (method_start, method_end)
        logging.debug(f"Searching within method: {method_sig} (lines {method_start}-{method_end})")
    
    # Find the context in the smali code
    context_index = find_context(smali_lines, context_lines, search_range)
    if context_index == -1:
        logging.error("Context not found in target file")
        logging.error("Context looked for:")
        for ctx in context_lines:
            logging.error(f"  {ctx}")
        return None
    
    logging.debug(f"Found context at line {context_index}")
    
    if dry_run:
        logging.info(f"DRY-RUN: Would apply patch at line {context_index}")
        return smali_lines
    
    new_lines = smali_lines.copy()
    
    # Find where the modifications should happen relative to context
    context_end = context_index + len(context_lines)
    
    # Group operations by their position relative to context
    modifications_before = []
    modifications_after = []
    
    current_pos = 0
    for op_type, content in operations:
        if op_type == ' ':
            # Context line - move position forward
            current_pos += 1
        elif op_type == '-':
            # Remove line - should match current position
            modifications_after.append(('-', content, current_pos))
        elif op_type == '+':
            # Add line - can be at current position
            modifications_after.append(('+', content, current_pos))
    
    # Apply modifications (removals first, then additions)
    offset = 0
    
    # First, handle removals
    for op_type, content, pos in modifications_after:
        if op_type == '-':
            target_index = context_index + pos + offset
            if target_index < len(new_lines) and content in new_lines[target_index]:
                del new_lines[target_index]
                offset -= 1
                logging.debug(f"Removed: {content}")
            else:
                logging.warning(f"Line to remove not found at position: {content}")
    
    # Then, handle additions
    for op_type, content, pos in modifications_after:
        if op_type == '+':
            target_index = context_index + pos + offset
            new_lines.insert(target_index, content)
            offset += 1
            logging.debug(f"Added: {content}")
    
    return new_lines

def method_sig_to_regex(method_sig):
    """Convert method signature to regex pattern for better matching"""
    # Escape special regex characters but preserve wildcards if needed
    escaped = re.escape(method_sig)
    
    # Allow flexible matching for common variations
    # Convert escaped spaces to allow any whitespace
    escaped = escaped.replace(r'\ ', r'\s+')
    
    # Allow any number of parameters (.*) but be careful with regex
    if r'\.\.\.' in escaped:
        escaped = escaped.replace(r'\.\.\.', r'\.\.\.')
    
    # Make sure we match the whole line (or at least start with the pattern)
    if not escaped.startswith('^'):
        escaped = '^\\s*' + escaped
    
    return escaped

def find_method_range(smali_lines, method_pattern):
    """Find the start and end line numbers of a method"""
    start_line = -1
    end_line = -1
    
    for i, line in enumerate(smali_lines):
        if start_line == -1 and re.match(method_pattern, line):
            start_line = i
            # Now find the corresponding .end method
            for j in range(i, len(smali_lines)):
                if smali_lines[j].startswith('.end method'):
                    end_line = j
                    return start_line, end_line
            break
    
    return -1, -1

def find_context(smali_lines, context_lines, search_range=None):
    """Find the starting index of context lines in smali code"""
    if not context_lines:
        return 0 if search_range else -1
    
    start_idx = search_range[0] if search_range else 0
    end_idx = search_range[1] if search_range else len(smali_lines) - len(context_lines) + 1
    
    for i in range(start_idx, end_idx):
        match = True
        for j, context_line in enumerate(context_lines):
            check_idx = i + j
            if check_idx >= len(smali_lines) or context_line not in smali_lines[check_idx]:
                match = False
                break
        if match:
            return i
    
    return -1

def show_diff(original, modified):
    """Show diff between original and modified content"""
    logging.info("Changes that would be applied:")
    for i, (orig, mod) in enumerate(zip(original, modified)):
        if orig != mod:
            logging.info(f"Line {i+1}:")
            if i < len(original) and i < len(modified):
                if orig != modified[i]:
                    logging.info(f"  - {orig}")
                    logging.info(f"  + {modified[i]}")
            elif i >= len(original):
                logging.info(f"  + {modified[i]}")
            elif i >= len(modified):
                logging.info(f"  - {orig}")

def main():
    parser = argparse.ArgumentParser(description='Apply smali patches')
    parser.add_argument('work_dir', help='Working directory containing smali files')
    parser.add_argument('patch_file', help='Patch file to apply')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be patched without applying')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if not os.path.exists(args.work_dir):
        logging.error(f"Work directory does not exist: {args.work_dir}")
        sys.exit(1)
    
    if not os.path.exists(args.patch_file):
        logging.error(f"Patch file does not exist: {args.patch_file}")
        sys.exit(1)
    
    success = apply_smalipatch(args.work_dir, args.patch_file, args.dry_run)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
