#!/usr/bin/env python3
"""
Helper functions for patch parsing.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional


def parse_patches(lines: List[str]) -> Tuple[List[Dict], List[str]]:
    """

    Returns:
        Tuple of (patches, credits)
    """
    patches = []
    credits = []
    current_patch = None
    current_action = None
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()


        if not line:
            i += 1
            continue


        if line.startswith('CREDIT:'):
            credit_text = line[7:].strip()
            if credit_text:
                credits.append(credit_text)
            i += 1
            continue


        if line.startswith('FILE:'):

            if current_patch:
                patches.append(current_patch)

            file_path = line[5:].strip()
            current_patch = {
                'type': 'FILE',
                'file_path': file_path,
                'actions': []
            }
            current_action = None
            i += 1
            continue


        if line.startswith('CREATE:'):
            if current_patch:
                patches.append(current_patch)

            file_path = line[7:].strip()
            current_patch = {
                'type': 'CREATE',
                'file_path': file_path,
                'content': []
            }
            current_action = None
            i += 1


            while i < len(lines):
                next_line = lines[i]
                if (next_line.startswith('FILE:') or
                    next_line.startswith('CREATE:') or
                    next_line.startswith('REMOVE:') or
                    next_line.startswith('REMOVE_FILE:') or
                    next_line.startswith('CREDIT:')):
                    break
                current_patch['content'].append(next_line.rstrip())
                i += 1
            continue


        if line.startswith('REMOVE:') or line.startswith('REMOVE_FILE:'):
            if current_patch:
                patches.append(current_patch)

            if line.startswith('REMOVE:'):
                file_path = line[7:].strip()
            else:
                file_path = line[12:].strip()

            current_patch = {
                'type': 'REMOVE_FILE',
                'file_path': file_path
            }
            current_action = None
            patches.append(current_patch)
            current_patch = None
            i += 1
            continue


        if line.startswith('FIND_REPLACE'):
            if not current_patch or current_patch.get('type') != 'FILE':
                i += 1
                continue


            match = re.match(r'FIND_REPLACE\s+"([^"]+)"\s+"([^"]*)"', line)
            if not match:
                i += 1
                continue

            old_value = match.group(1)
            new_value = match.group(2)

            action = {
                'type': 'FIND_REPLACE',
                'old': old_value,
                'new': new_value
            }
            current_patch['actions'].append(action)
            current_action = None
            i += 1
            continue

        # Parse other action types
        if line in ['PATCH:', 'REPLACE:', 'CREATE_METHOD:', 'REMOVE_METHOD:',
                    'ADD_FIELD:', 'REMOVE_FIELD:']:
            if not current_patch or current_patch.get('type') != 'FILE':
                i += 1
                continue

            action_type = line.rstrip(':')
            current_action = {
                'type': action_type,
                'context': [],
                'code': []
            }
            current_patch['actions'].append(current_action)
            i += 1


            in_code = False
            while i < len(lines):
                next_line = lines[i]


                if (next_line.startswith('FILE:') or
                    next_line.startswith('CREATE:') or
                    next_line.startswith('REMOVE:') or
                    next_line.startswith('REMOVE_FILE:') or
                    next_line.startswith('CREDIT:') or
                    next_line in ['PATCH:', 'REPLACE:', 'CREATE_METHOD:',
                                 'REMOVE_METHOD:', 'ADD_FIELD:', 'REMOVE_FIELD:'] or
                    next_line.startswith('FIND_REPLACE')):
                    break


                if next_line.strip() == '---':
                    in_code = True
                    i += 1
                    continue


                if in_code:
                    current_action['code'].append(next_line.rstrip())
                else:
                    current_action['context'].append(next_line.rstrip())

                i += 1

            current_action = None
            continue

        i += 1


    if current_patch:
        patches.append(current_patch)

    return patches, credits


def apply_create_action(work_dir: str, patch: Dict, dry_run: bool) -> Tuple[bool, str]:

    file_path = patch.get('file_path', '')
    content = patch.get('content', [])

    if not file_path:
        return False, "No file path specified"

    full_path = Path(work_dir) / file_path

    if full_path.exists():
        return False, f"File already exists: {file_path}"

    if dry_run:
        print(f"  Would create: {file_path}")
        return True, ""

    try:
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        print(f"  Created: {file_path}")
        return True, ""
    except Exception as e:
        return False, str(e)


def apply_remove_file(work_dir: str, patch: Dict, dry_run: bool) -> Tuple[bool, str]:

    file_path = patch.get('file_path', '')

    if not file_path:
        return False, "No file path specified"

    full_path = Path(work_dir) / file_path

    if not full_path.exists():
        return False, f"File not found: {file_path}"

    if dry_run:
        print(f"  Would remove: {file_path}")
        return True, ""

    try:
        full_path.unlink()
        print(f"  Removed: {file_path}")
        return True, ""
    except Exception as e:
        return False, str(e)


def apply_find_replace(work_dir: str, patch: Dict, dry_run: bool) -> Tuple[bool, str]:

    file_path = patch.get('file_path', '')
    actions = patch.get('actions', [])

    if not file_path:
        return False, "No file path specified"

    full_path = Path(work_dir) / file_path

    if not full_path.exists():
        return False, f"File not found: {file_path}"

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        replacements = 0

        for action in actions:
            if action.get('type') != 'FIND_REPLACE':
                continue

            old_value = action.get('old', '')
            new_value = action.get('new', '')

            if old_value in content:
                count = content.count(old_value)
                content = content.replace(old_value, new_value)
                replacements += count

        if replacements == 0:
            return False, "No matches found"

        if dry_run:
            print(f"  Would replace {replacements} occurrence(s) in {file_path}")
            return True, ""

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  Replaced {replacements} occurrence(s) in {file_path}")
        return True, ""

    except Exception as e:
        return False, str(e)


def apply_file_patch(work_dir: str, patch: Dict, dry_run: bool) -> Tuple[bool, str]:

    file_path = patch.get('file_path', '')
    actions = patch.get('actions', [])

    if not file_path:
        return False, "No file path specified"

    if not actions:
        return False, "No actions specified"

    full_path = Path(work_dir) / file_path

    if not full_path.exists():
        return False, f"File not found: {file_path}"

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = [line.rstrip('\r\n') for line in f.readlines()]

        modified = False

        for action in actions:
            action_type = action.get('type', '')

            if action_type == 'FIND_REPLACE':

                old_value = action.get('old', '')
                new_value = action.get('new', '')

                content = '\n'.join(lines)
                if old_value in content:
                    content = content.replace(old_value, new_value)
                    lines = content.split('\n')
                    modified = True

            elif action_type in ['PATCH', 'REPLACE', 'CREATE_METHOD', 'REMOVE_METHOD',
                                'ADD_FIELD', 'REMOVE_FIELD']:

                context = action.get('context', [])
                code = action.get('code', [])

                if not context:
                    continue


                match_idx = find_context(lines, context)
                if match_idx == -1:
                    continue


                if action_type == 'PATCH':

                    lines = lines[:match_idx + len(context)] + code + lines[match_idx + len(context):]
                    modified = True

                elif action_type == 'REPLACE':

                    lines = lines[:match_idx] + code + lines[match_idx + len(context):]
                    modified = True

                elif action_type == 'REMOVE_METHOD' or action_type == 'REMOVE_FIELD':
                    #
                    lines = lines[:match_idx] + lines[match_idx + len(context):]
                    modified = True

                elif action_type == 'CREATE_METHOD' or action_type == 'ADD_FIELD':

                    lines = lines[:match_idx + len(context)] + code + lines[match_idx + len(context):]
                    modified = True

        if not modified:
            return False, "No changes applied"

        if dry_run:
            print(f"  Would modify: {file_path}")
            return True, ""

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"  Modified: {file_path}")
        return True, ""

    except Exception as e:
        return False, str(e)


def find_context(lines: List[str], context: List[str]) -> int:

    if not context:
        return -1


    context = [c for c in context if c.strip()]
    if not context:
        return -1

    for i in range(len(lines) - len(context) + 1):
        match = True
        for j, ctx_line in enumerate(context):
            if lines[i + j].strip() != ctx_line.strip():
                match = False
                break
        if match:
            return i

    return -1
