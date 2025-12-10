"""
Helper/Plugin for Smalipatcher 
Smalipatcher :  utility for applying patches to .smali files.

You can put your comments/info with # and // 
"""

import os
import re
import logging
import difflib
from typing import List, Dict, Tuple, Optional, Literal
from pathlib import Path

PatchOperation = Tuple[Literal['+', '-', ' '], str]
PatchAction = Dict[str, any]
Patch = Dict[str, any]
ApplyResult = Literal["applied", "created", "skipped", "failed", "hunk_failed"]


KEYWORDS = [
    'FILE', 'CREATE', 'REMOVE', 'REPLACE', 'PATCH', 
    'CREATE_METHOD', 'REMOVE_METHOD', 'ADD_FIELD', 'REMOVE_FIELD',
    'CREDIT', 'FIND_REPLACE', 'END'
]



def normalize(line: str) -> Optional[str]:
    """
    Normalizes a smali line for robust comparison.
    Returns None if the line is skippable (comments, directives, empty).
    """
    line = line.strip()
    
    # Ignore comments and empty lines
    if not line or line.startswith(('#', '//')):
        return None
    
    # Collapse internal whitespace
    line = re.sub(r'\s+', ' ', line)
    
    return line


def is_structure_comment(line: str) -> bool:
    """Checks if a line is a patch-file comment (// or #)."""
    stripped = line.strip()
    return stripped.startswith('//') or stripped.startswith('#')




def parse_patches(lines: List[str]) -> Tuple[List[Patch], List[str]]:
    """
    Parses text lines into a structured list of patches.
    Returns (patches, credits).
    """
    patches = []
    credits = []
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if not line or is_structure_comment(line):
            i += 1
            continue

        if line.startswith('CREDIT '):
            credits.append(line[7:].strip())
            i += 1
        elif line.startswith('FILE '):
            patch, i = parse_file_block(lines, i)
            if patch:
                patches.append(patch)
        elif line.startswith('CREATE '):
            patch, i = parse_create_block(lines, i)
            if patch:
                patches.append(patch)
        elif line.startswith('REMOVE '):
            file_path = line[7:].strip()
            patches.append({'type': 'REMOVE', 'file_path': file_path})
            i += 1

        elif line.startswith('FIND_REPLACE '):
            match = fr_pattern.match(line)
            if match:
                patches.append({
                    'type': 'FIND_REPLACE',
                    'find': match.group(1),
                    'replace': match.group(2)
                })
            else:
                logging.warning(f"Invalid FIND_REPLACE syntax at line {i+1}: {line}")
            i += 1

        else:
            i += 1
            
    return patches, credits


def parse_file_block(lines: List[str], start_index: int) -> Tuple[Optional[Patch], int]:
    """Parses a 'FILE ...' block."""
    file_path = lines[start_index].strip()[5:].strip()
    patch = {'type': 'FILE', 'file_path': file_path, 'actions': []}
    
    i = start_index + 1
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Check for new top-level block
        if line.startswith(('FILE ', 'CREATE ', 'REMOVE ')):
            logging.debug(f"Implicit END for FILE {file_path}")
            return patch, i

        if not line or is_structure_comment(line):
            i += 1
            continue

        if line == 'END':
            return patch, i + 1
        
        elif line.startswith('REPLACE '):
            action, i = parse_action_block(lines, i, 'REPLACE')
            patch['actions'].append(action)
        elif line.startswith('PATCH'):
            action, i = parse_action_block(lines, i, 'PATCH')
            patch['actions'].append(action)
        elif line == 'CREATE_METHOD':
            action, i = parse_action_block(lines, i, 'CREATE_METHOD')
            patch['actions'].append(action)
        elif line.startswith('REMOVE_METHOD '):
            action, i = parse_action_block(lines, i, 'REMOVE_METHOD')
            patch['actions'].append(action)
        elif line.startswith('ADD_FIELD'):
            action, i = parse_action_block(lines, i, 'ADD_FIELD')
            patch['actions'].append(action)
        elif line.startswith('REMOVE_FIELD '):
            action, i = parse_action_block(lines, i, 'REMOVE_FIELD')
            patch['actions'].append(action)
        else:
            i += 1
            
    return patch, i


def parse_create_block(lines: List[str], start_index: int) -> Tuple[Optional[Patch], int]:
    """Parses a 'CREATE ...' block."""
    file_path = lines[start_index].strip()[7:].strip()
    content, i = read_content_block(lines, start_index + 1)
    patch = {'type': 'CREATE', 'file_path': file_path, 'content': content}
    return patch, i


def parse_action_block(lines: List[str], start_index: int, action_type: str) -> Tuple[PatchAction, int]:
    """Parses action blocks with optional arguments."""
    line = lines[start_index].strip()
    
    header = ""
    if action_type == 'PATCH' and len(line) > 5:
        header = line[5:].strip()
    elif action_type == 'REPLACE':
        header = line[8:].strip()
    elif action_type == 'REMOVE_METHOD':
        header = line[14:].strip()
    elif action_type == 'REMOVE_FIELD':
        header = line[13:].strip()
    elif action_type == 'ADD_FIELD':
        header = line[9:].strip()

    action = {'type': action_type}
    if header:
        action['signature'] = header
    
    content_lines, i = read_content_block(lines, start_index + 1)
    
    if action_type == 'PATCH':
        action['operations'] = parse_patch_operations(content_lines)
    else:
        action['content'] = content_lines
        
    return action, i


def read_content_block(lines: List[str], start_index: int) -> Tuple[List[str], int]:
    """Reads lines until a reserved KEYWORD is found."""
    content = []
    i = start_index
    
    while i < len(lines):
        line = lines[i]
        line_strip = line.strip()
        
        first_word = line_strip.split(' ')[0] if line_strip else ""
        
        if first_word in KEYWORDS:
            if first_word == 'END':
                return content, i + 1
            else:
                return content, i
        
        content.append(line)
        i += 1
    
    return content, i


def parse_patch_operations(lines: List[str]) -> List[PatchOperation]:
    """Converts content lines into +/-/ operations."""
    ops = []
    for line in lines:
        if line.startswith('+ '):
            ops.append(('+', line[2:]))
        elif line.startswith('- '):
            ops.append(('-', line[2:]))
        else:
            ops.append((' ', line))
    return ops



def apply_remove_file(work_dir: str, patch: Patch, dry_run: bool = False) -> ApplyResult:
    """Remove a file."""
    full_path = Path(work_dir) / patch['file_path']
    
    if not full_path.exists():
        logging.warning(f"  ~ Skipped: File not found")
        return "skipped"
    
    if dry_run:
        logging.info(f"  [DRY RUN] Would remove: {patch['file_path']}")
        return "applied"
    
    try:
        full_path.unlink()
        logging.info(f"   Removed file")
        return "applied"
    except OSError as e:
        logging.error(f"   Failed to remove file: {e}")
        return "failed"


def apply_create_action(work_dir: str, patch: Patch, dry_run: bool = False) -> ApplyResult:
    """Create a new file."""
    file_path = patch['file_path']
    full_path = Path(work_dir) / file_path

    if full_path.exists():
        logging.warning(f"  ~ Skipped: File already exists")
        return "skipped"

    if dry_run:
        logging.info(f"  [DRY RUN] Would create: {file_path}")
        logging.info(f"              with {len(patch['content'])} lines")
        return "created"

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(patch['content']) + '\n')
        logging.info(f"   Created file ({len(patch['content'])} lines)")
        return "created"
    except IOError as e:
        logging.error(f"   Failed to create file: {e}")
        return "failed"


def apply_file_patch(work_dir: str, patch: Patch, dry_run: bool = False) -> ApplyResult:
    """Apply multiple actions to a file."""
    full_path = Path(work_dir) / patch['file_path']

    if not full_path.exists():
        logging.error(f"   Target file not found")
        return "failed"

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            original_lines = [line.rstrip('\r\n') for line in f.readlines()]
    except IOError as e:
        logging.error(f"   Failed to read file: {e}")
        return "failed"

    modified_lines = original_lines[:]
    
    for j, action in enumerate(patch['actions'], 1):
        action_type = action.get('type', 'Unknown')
        logging.debug(f"    Action {j}/{len(patch['actions'])}: {action_type}")
        
        result = None
        
        if action['type'] == 'REPLACE':
            result = _apply_replace(modified_lines, action)
        elif action['type'] == 'PATCH':
            result = _apply_patch(modified_lines, action)
        elif action['type'] == 'CREATE_METHOD':
            result = _apply_create_method(modified_lines, action)
        elif action['type'] == 'REMOVE_METHOD':
            result = _apply_remove_method(modified_lines, action)
        elif action['type'] == 'ADD_FIELD':
            result = _apply_add_field(modified_lines, action)
        elif action['type'] == 'REMOVE_FIELD':
            result = _apply_remove_field(modified_lines, action)
        
        if result is None:
            logging.error(f"   Action {j} ({action_type}) failed")
            return "hunk_failed"
        
        modified_lines = result

    if original_lines == modified_lines:
        logging.info(f"  ~ No changes needed (already applied)")
        return "skipped"

    if dry_run:
        show_diff(original_lines, modified_lines, patch['file_path'], preview=True)
        return "applied"

    show_diff(original_lines, modified_lines, patch['file_path'])
    
    try:
        with open(full_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(modified_lines) + '\n')
        logging.info(f"   Successfully patched")
    except IOError as e:
        logging.error(f"   Failed to write file: {e}")
        return "failed"
        
    return "applied"



def _apply_add_field(lines: List[str], action: PatchAction) -> Optional[List[str]]:
    """Add a field to the class."""
    content = action['content']
    
    if not content:
        logging.error("     ADD_FIELD: No field definition provided")
        return None
    

    insert_pos = -1
    
    # Try to find last .field declaration
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith('.field '):
            insert_pos = i + 1
            break
    
    # If no fields found, insert before first .method or after .super
    if insert_pos == -1:
        for i, line in enumerate(lines):
            if line.strip().startswith('.method '):
                insert_pos = i
                break
            elif line.strip().startswith('.super '):
                insert_pos = i + 1
    
    if insert_pos == -1:
        logging.error("     ADD_FIELD: Could not find insertion point")
        return None
    
    # Ensure blank line before if needed
    new_content = content[:]
    if insert_pos > 0 and lines[insert_pos - 1].strip() != '':
        new_content = [''] + new_content
    
    logging.info(f"     Added field at line {insert_pos + 1}")
    return lines[:insert_pos] + new_content + lines[insert_pos:]


def _apply_remove_field(lines: List[str], action: PatchAction) -> Optional[List[str]]:
    """Remove a field from the class."""
    field_sig = action.get('signature', '')
    
    if not field_sig:
        logging.error("     REMOVE_FIELD: No field signature provided")
        return None
    
    # Create regex pattern for field
    pattern = re.compile(r'^\.field\s+.*' + re.escape(field_sig))
    
    # Find and remove field
    for i, line in enumerate(lines):
        if pattern.search(line.strip()):
            logging.info(f"     Removed field at line {i + 1}")
            return lines[:i] + lines[i+1:]
    
    logging.error(f"     REMOVE_FIELD: Field not found: {field_sig}")
    return None


def _apply_remove_method(lines: List[str], action: PatchAction) -> Optional[List[str]]:
    """Removes a method from the class."""
    pattern = method_sig_to_regex(action['signature'])
    start_idx, end_idx = find_method_range(lines, pattern)

    if start_idx == -1:
        logging.error(f"     REMOVE_METHOD: Method not found")
        return None
    
    logging.info(f"     Removed method at line {start_idx + 1}")
    return lines[:start_idx] + lines[end_idx + 1:]


def _apply_replace(lines: List[str], action: PatchAction) -> Optional[List[str]]:
    """Replaces an entire method."""
    pattern = method_sig_to_regex(action['signature'])
    start_idx, end_idx = find_method_range(lines, pattern)

    if start_idx == -1:
        logging.error(f"     REPLACE: Method not found")
        return None
    
    logging.info(f"     Replaced method at line {start_idx + 1}")
    return lines[:start_idx + 1] + action['content'] + lines[end_idx:]


def _apply_create_method(lines: List[str], action: PatchAction) -> Optional[List[str]]:
    """Creates a new method."""
    # Insert before the last .end class or method
    insert_pos = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith('.end class'):
            insert_pos = i
            break
    
    if insert_pos == -1:
        logging.error("     CREATE_METHOD: '.end class' not found")
        return None
    
    new_content = action['content']
    if insert_pos > 0 and lines[insert_pos - 1].strip() != '':
        new_content = [''] + new_content

    logging.info(f"     Added method at line {insert_pos + 1}")
    return lines[:insert_pos] + new_content + lines[insert_pos:]


def _apply_patch(lines: List[str], action: PatchAction) -> Optional[List[str]]:
    """Apply a context-based patch."""
    operations = action['operations']
    

    fingerprint = []
    for op, line in operations:
        if op in (' ', '-'):
            norm = normalize(line)
            if norm:
                fingerprint.append(norm)

    if not fingerprint:
        logging.error("     PATCH: No context lines provided")
        return None

    # Find fingerprint in file
    match_start_idx = find_fingerprint(lines, fingerprint)

    if match_start_idx == -1:
        logging.error(f"     PATCH: Context not found")
        logging.debug(f"     Looking for: {fingerprint[0][:50]}...")
        return None

    # Apply patch operations
    modified_lines = lines[:match_start_idx]
    op_idx = 0
    target_idx = match_start_idx
    changes_count = 0

    while op_idx < len(operations):
        op, patch_line = operations[op_idx]
        
        if op == '+':
            modified_lines.append(patch_line)
            changes_count += 1
            op_idx += 1
        elif op in (' ', '-'):

            while target_idx < len(lines) and not normalize(lines[target_idx]):
                if op == ' ':
                    modified_lines.append(lines[target_idx])
                target_idx += 1
            
            if target_idx >= len(lines):
                logging.error("   PATCH: Unexpected end of file")
                return None
            
            if op == ' ':
                modified_lines.append(lines[target_idx])
            else:
                changes_count += 1
                
            target_idx += 1
            op_idx += 1

    modified_lines.extend(lines[target_idx:])
    logging.info(f"     Applied patch at line {match_start_idx + 1} (~{changes_count} changes)")
    return modified_lines


def find_fingerprint(lines: List[str], fingerprint: List[str]) -> int:

    for i in range(len(lines)):
        f_idx = 0
        t_idx = i
        
        while f_idx < len(fingerprint) and t_idx < len(lines):
            norm_target = normalize(lines[t_idx])
            
            if not norm_target:
                t_idx += 1
                continue
                
            if norm_target == fingerprint[f_idx]:
                f_idx += 1
                t_idx += 1
            else:
                break
        
        if f_idx == len(fingerprint):
            return i
    
    return -1


def method_sig_to_regex(method_sig: str) -> re.Pattern:
    """Convert method signature to regex pattern."""
    escaped = re.escape(method_sig).replace(r'\ ', r'\s+')
    return re.compile(f'^{escaped}')


def find_method_range(lines: List[str], pattern: re.Pattern) -> Tuple[int, int]:

    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == '.end method':
                    return i, j
            return i, -1
    return -1, -1


def show_diff(original: List[str], modified: List[str], filename: str, preview: bool = False):

    diff = list(difflib.unified_diff(
        original, modified,
        fromfile=f'a/{filename}',
        tofile=f'b/{filename}',
        lineterm=''
    ))
    
    if not diff:
        return

    # For large diffs, show summary
    if len(diff) > 20:
        added = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
        removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
        prefix = "[PREVIEW] " if preview else ""
        logging.info(f"  {prefix}Changes: +{added} lines, -{removed} lines")
        return


    prefix = "[PREVIEW] " if preview else ""
    logging.info(f"  {prefix}Diff:")
    for line in diff[:50]:
        if line.startswith('+') and not line.startswith('+++'):
            print(f"    \033[92m{line}\033[0m")
        elif line.startswith('-') and not line.startswith('---'):
            print(f"    \033[91m{line}\033[0m")
        elif line.startswith('@@'):
            print(f"    \033[96m{line}\033[0m")


def apply_global_find_replace(work_dir: str, patch: Patch, dry_run: bool = False) -> ApplyResult:
    """
Will find result in full apk/jar path
    """
    find_str = patch['find']
    replace_str = patch['replace']
    work_path = Path(work_dir)

    files_changed = 0
    total_occurrences = 0

    logging.info(f"   Scanning for '{find_str}' -> '{replace_str}'...")


    smali_files = list(work_path.rglob('*.smali'))

    if not smali_files:
        logging.warning("   ~ No .smali files found in directory.")
        return "skipped"

    for file_path in smali_files:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()


            if find_str not in content:
                continue

            count = content.count(find_str)
            if count > 0:
                new_content = content.replace(find_str, replace_str)
                files_changed += 1
                total_occurrences += count

                rel_path = file_path.relative_to(work_path)

                if dry_run:
                    logging.info(f"   [DRY RUN] Would modify: {rel_path} ({count} matches)")
                else:
                    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                        f.write(new_content)
                    logging.debug(f"   Modified: {rel_path} ({count} matches)")

        except Exception as e:
            logging.error(f"   Error processing {file_path}: {e}")

    if files_changed == 0:
        logging.info("   ~ No matches found.")
        return "skipped"

    logging.info(f"   Updated {files_changed} files ({total_occurrences} occurrences)")
    return "applied"
