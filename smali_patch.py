#!/usr/bin/env python3
import os
import sys
import re
import logging

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        format='%(message)s',
        level=logging.INFO
    )

def apply_smalipatch(work_dir, patch_file):
    """Apply .smalipatch files to smali files"""
    
    with open(patch_file, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\r\n') for line in f.readlines()]
    
    if not lines:
        logging.error(f"ERROR: Empty patch file {patch_file}")
        return False
    
    patches = parse_patches(lines)
    if not patches:
        logging.error(f"ERROR: No valid patches found in {patch_file}")
        return False
    
    success_count = 0
    total_patches = len(patches)
    
    for i, patch in enumerate(patches):
        logging.info(f"Applying patch {i+1}/{total_patches}...")
        result = apply_single_patch(work_dir, patch)
        if result == "applied":
            success_count += 1
            logging.info("✓ Patch applied successfully")
        elif result == "skipped":
            logging.info("✓ Patch already applied, skipping")
            success_count += 1
        elif result == "failed":
            logging.error("✗ Patch failed to apply")
        elif result == "hunk_failed":
            logging.error("✗ Hunk doesn't match, skipping patch")
    
    logging.info(f"Final result: {success_count}/{total_patches} patches applied successfully")
    return success_count == total_patches

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
                patch_header = line[6:].strip()
                method_sig = None
                if patch_header and not patch_header.startswith(('+', '-')):
                    method_sig = patch_header
                    i += 1
                else:
                    i += 1
                
                patch_operations = []
                
                while i < len(lines) and not lines[i].strip() in ['END', 'FILE ']:
                    patch_line = lines[i]
                    if patch_line.startswith('+ '):
                        patch_operations.append(('+', patch_line[2:]))
                    elif patch_line.startswith('- '):
                        patch_operations.append(('-', patch_line[2:]))
                    else:
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
    
    if current_patch:
        patches.append(current_patch)
    
    return patches

def apply_single_patch(work_dir, patch):
    """Apply a single patch to a file - always dry run first"""
    file_path = patch['file_path']
    full_path = os.path.join(work_dir, file_path)
    
    if not os.path.exists(full_path):
        logging.error(f"ERROR: Target file not found: {full_path}")
        return "failed"
    
    with open(full_path, 'r', encoding='utf-8') as f:
        original_lines = [line.rstrip('\r\n') for line in f.readlines()]
    
    current_lines = original_lines.copy()
    patch_applied = False
    any_hunk_failed = False
    
    for action in patch['actions']:
        if action['type'] == 'REPLACE':
            result = apply_replace_action(current_lines, action, dry_run=True)
            if result and result != current_lines:
                current_lines = result
                patch_applied = True
            elif not result:
                any_hunk_failed = True
                
        elif action['type'] == 'PATCH':
            result = apply_patch_action(current_lines, action, dry_run=True)
            if result and result != current_lines:
                current_lines = result
                patch_applied = True
            elif result == current_lines:
                # Patch would make no changes (already applied)
                pass
            else:
                any_hunk_failed = True
    
    if any_hunk_failed:
        return "hunk_failed"
    
    if not patch_applied:
        return "skipped"
    
    # Show what would be changed
    show_diff(original_lines, current_lines)
    
    # Actually apply the patch
    final_lines = original_lines.copy()
    for action in patch['actions']:
        if action['type'] == 'REPLACE':
            result = apply_replace_action(final_lines, action, dry_run=False)
            if result:
                final_lines = result
        elif action['type'] == 'PATCH':
            result = apply_patch_action(final_lines, action, dry_run=False)
            if result:
                final_lines = result
    
    with open(full_path, 'w', encoding='utf-8', newline='\n') as f:
        for line in final_lines:
            f.write(line + '\n')
    
    return "applied"

def apply_replace_action(smali_lines, action, dry_run=True):
    """Apply REPLACE action - replace entire method using regex matching"""
    method_sig = action['method_sig']
    patch_content = action['content']
    
    pattern = method_sig_to_regex(method_sig)
    
    new_lines = []
    i = 0
    replaced = False
    
    while i < len(smali_lines):
        line = smali_lines[i]
        
        if not replaced and re.match(pattern, line):
            new_lines.append(line)
            i += 1
            replaced = True
            
            while i < len(smali_lines) and not smali_lines[i].startswith('.end method'):
                i += 1
            
            for patch_line in patch_content:
                new_lines.append(patch_line)
            
            if i < len(smali_lines):
                new_lines.append(smali_lines[i])
                i += 1
        else:
            new_lines.append(line)
            i += 1
    
    if not replaced:
        logging.error(f"ERROR: Method not found: {method_sig}")
        return None
        
    return new_lines

def apply_patch_action(smali_lines, action, dry_run=True):
    """Apply PATCH action with simple +/- logic"""
    operations = action['operations']
    method_sig = action['method_sig']
    
    if not operations:
        logging.error("ERROR: PATCH action requires operations")
        return None
    
    # Filter out .line directives for context matching
    def filter_line_directives(lines):
        return [line for line in lines if not line.strip().startswith('.line ')]
    
    # Get context lines (regular lines without +/-)
    context_lines = [line for op, line in operations if op == ' ']
    context_lines_clean = filter_line_directives(context_lines)
    
    if not context_lines_clean:
        logging.error("ERROR: PATCH action requires context lines")
        return None
    
    # If method signature provided, search within that method
    search_range = None
    if method_sig:
        pattern = method_sig_to_regex(method_sig)
        method_start, method_end = find_method_range(smali_lines, pattern)
        if method_start == -1:
            logging.error(f"ERROR: Method not found: {method_sig}")
            return None
        search_range = (method_start, method_end)
    
    # Create clean version of smali lines for context matching
    smali_clean = filter_line_directives(smali_lines)
    clean_to_original = [i for i, line in enumerate(smali_lines) if not line.strip().startswith('.line ')]
    
    # Find context in clean lines
    context_index_clean = find_context(smali_clean, context_lines_clean)
    if context_index_clean == -1:
        logging.error("ERROR: Context not found in target file")
        return None
    
    # Map back to original line numbers
    context_index = clean_to_original[context_index_clean]
    
    # Find the exact position considering .line directives
    exact_position = find_exact_position(smali_lines, context_index, context_lines)
    if exact_position == -1:
        logging.error("ERROR: Cannot find exact position for patch")
        return None
    
    if dry_run:
        # For dry run, just return modified lines to check if changes would be made
        test_lines = smali_lines.copy()
        result = apply_modifications(test_lines, exact_position, operations)
        return result
    
    # Apply modifications for real
    return apply_modifications(smali_lines, exact_position, operations)

def apply_modifications(smali_lines, context_index, operations):
    """Apply the actual modifications to the smali lines"""
    new_lines = smali_lines.copy()
    offset = 0
    
    # Group operations by type and position
    removes = []
    adds = []
    
    current_pos = 0
    for op_type, content in operations:
        if op_type == ' ':
            current_pos += 1
        elif op_type == '-':
            removes.append((current_pos, content))
        elif op_type == '+':
            adds.append((current_pos, content))
    
    # Apply removals first (from bottom to top)
    for pos, content in reversed(removes):
        target_index = context_index + pos + offset
        found = False
        # Search around the expected position
        for i in range(max(0, target_index-2), min(len(new_lines), target_index+3)):
            if i < len(new_lines) and content in new_lines[i]:
                del new_lines[i]
                offset -= 1
                found = True
                break
        if not found:
            logging.warning(f"WARNING: Line to remove not found: {content}")
    
    # Apply additions
    for pos, content in adds:
        target_index = context_index + pos + offset
        new_lines.insert(target_index, content)
        offset += 1
    
    return new_lines

def find_exact_position(smali_lines, context_index, context_lines):
    """Find the exact position considering all context lines including .line"""
    for i in range(max(0, context_index-5), min(len(smali_lines), context_index+10)):
        match = True
        for j, context_line in enumerate(context_lines):
            check_idx = i + j
            if check_idx >= len(smali_lines) or context_line not in smali_lines[check_idx]:
                match = False
                break
        if match:
            return i
    return -1

def method_sig_to_regex(method_sig):
    """Convert method signature to regex pattern"""
    escaped = re.escape(method_sig)
    escaped = escaped.replace(r'\ ', r'\s+')
    if not escaped.startswith('^'):
        escaped = '^\\s*' + escaped
    return escaped

def find_method_range(smali_lines, method_pattern):
    """Find the start and end line numbers of a method"""
    for i, line in enumerate(smali_lines):
        if re.match(method_pattern, line):
            for j in range(i, len(smali_lines)):
                if smali_lines[j].startswith('.end method'):
                    return i, j
            break
    return -1, -1

def find_context(smali_lines, context_lines, search_range=None):
    """Find the starting index of context lines in smali code"""
    if not context_lines:
        return -1
    
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
    logging.info("Changes to be applied:")
    for i in range(max(len(original), len(modified))):
        if i < len(original) and i < len(modified):
            if original[i] != modified[i]:
                logging.info(f"@@ Line {i+1} @@")
                logging.info(f"- {original[i]}")
                logging.info(f"+ {modified[i]}")
        elif i < len(original):
            logging.info(f"@@ Line {i+1} @@")
            logging.info(f"- {original[i]}")
        elif i < len(modified):
            logging.info(f"@@ Line {i+1} @@")
            logging.info(f"+ {modified[i]}")

def main():
    if len(sys.argv) != 3:
        print("Usage: smalipatch.py <work_dir> <patch_file>")
        sys.exit(1)
    
    work_dir = sys.argv[1]
    patch_file = sys.argv[2]
    
    setup_logging()
    
    if not os.path.exists(work_dir):
        logging.error(f"ERROR: Work directory does not exist: {work_dir}")
        sys.exit(1)
    
    if not os.path.exists(patch_file):
        logging.error(f"ERROR: Patch file does not exist: {patch_file}")
        sys.exit(1)
    
    success = apply_smalipatch(work_dir, patch_file)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
