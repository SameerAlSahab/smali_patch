#!/usr/bin/env python3
import os
import sys
import re

def apply_smalipatch(work_dir, patch_file):
    """Apply .smalipatch files to smali files"""
    
    with open(patch_file, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\r\n') for line in f.readlines()]
    
    if not lines or not lines[0].startswith('FILE '):
        print(f"ERROR: Invalid patch file {patch_file}")
        return False
    
    # Get target file path
    target_path = lines[0][5:].strip()  # Remove 'FILE '
    full_target_path = os.path.join(work_dir, target_path)
    
    if not os.path.exists(full_target_path):
        print(f"ERROR: Target file not found: {full_target_path}")
        return False
    
    if len(lines) < 3 or not (lines[1].startswith('REPLACE ') or lines[1].startswith('MODIFY ')):
        print(f"ERROR: Invalid patch format in {patch_file}")
        return False
    
    action = lines[1].split()[0]
    method_sig = lines[1][len(action)+1:].strip()
    
    # Read the target smali file
    with open(full_target_path, 'r', encoding='utf-8') as f:
        smali_lines = [line.rstrip('\r\n') for line in f.readlines()]
    
    if action == 'REPLACE':
        # Find the method and replace its body
        new_lines = []
        i = 0
        replaced = False
        
        while i < len(smali_lines):
            line = smali_lines[i]
            
            if not replaced and method_sig in line:
                # Found the method signature
                new_lines.append(line)
                i += 1
                replaced = True
                
                # Skip all lines until .end method
                while i < len(smali_lines) and not smali_lines[i].startswith('.end method'):
                    i += 1
                
                # Add the patch content (lines 2 to end of patch file)
                for patch_line in lines[2:]:
                    new_lines.append(patch_line)
                
                # Add the .end method
                if i < len(smali_lines):
                    new_lines.append(smali_lines[i])
                    i += 1
            else:
                new_lines.append(line)
                i += 1
        
        if not replaced:
            print(f"ERROR: Method not found: {method_sig}")
            return False
            
        # Write the modified content back
        with open(full_target_path, 'w', encoding='utf-8', newline='\n') as f:
            for line in new_lines:
                f.write(line + '\n')
        
        print(f"SUCCESS: Replaced method in {target_path}")
        return True
    
    elif action == 'MODIFY':
        # MODIFY logic would go here
        print("MODIFY action not implemented yet")
        return False
    
    return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: smalipatch.py <work_dir> <patch_file>")
        sys.exit(1)
    
    work_dir = sys.argv[1]
    patch_file = sys.argv[2]
    
    success = apply_smalipatch(work_dir, patch_file)
    sys.exit(0 if success else 1)
