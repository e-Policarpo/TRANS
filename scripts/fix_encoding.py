#!/usr/bin/env python3
"""
Quick script to fix UTF-8 encoding issues in Python files.
Run this to fix corrupted special characters.
"""

import os
from pathlib import Path

def fix_encoding(filepath):
    """Fix common encoding issues in a file."""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Fix common corrupted characters
    replacements = {
        'Â²': '²',
        'µ': 'µ',
        'Ç': 'Ç',
        'Ã': 'Ã',
        'ÇÃO': 'ÇÃO',
        'd²I/dV²': 'd²I/dV²',  # Ensure correct
    }
    
    modified = False
    for old, new in replacements.items():
        if old in content:
            content = content.replace(old, new)
            modified = True
            print(f"  Fixed: {old} → {new}")
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Fixed: {filepath}")
        return True
    else:
        print(f"⭕ No changes needed: {filepath}")
        return False

def main():
    """Fix encoding in all Python files."""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / 'src'
    
    files_fixed = 0
    
    for py_file in src_dir.rglob('*.py'):
        print(f"\nChecking: {py_file}")
        if fix_encoding(py_file):
            files_fixed += 1
    
    print(f"\n{'='*60}")
    print(f"Encoding fix complete: {files_fixed} files modified")
    print(f"{'='*60}")

if __name__ == '__main__':
    main()
