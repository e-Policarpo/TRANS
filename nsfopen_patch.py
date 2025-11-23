"""
Patch for NSFopen library to handle STM data without cantilever metadata
"""
import os
import site
import re

def patch_nsfopen():
    """Apply patches to NSFopen read.py file"""
    
    # Find NSFopen installation
    for site_dir in site.getsitepackages():
        nsfopen_path = os.path.join(site_dir, 'NSFopen', 'read.py')
        if os.path.exists(nsfopen_path):
            print(f"Found NSFopen at: {nsfopen_path}")
            
            # Read the file
            with open(nsfopen_path, 'r') as f:
                lines = f.readlines()
            
            modified = False
            
            # Comment out lines 212-228 (cantilever section)
            for i in range(211, min(228, len(lines))):
                if i < len(lines) and not lines[i].strip().startswith('#'):
                    lines[i] = '# ' + lines[i]
                    modified = True
            
            # Remove 'cantilever' references around line 489
            for i in range(485, min(495, len(lines))):
                if i < len(lines) and 'cantilever' in lines[i].lower():
                    lines[i] = lines[i].replace('cantilever', '').replace('Cantilever', '')
                    modified = True
            
            if modified:
                # Backup original file
                backup_path = nsfopen_path + '.bak'
                if not os.path.exists(backup_path):
                    with open(backup_path, 'w') as f:
                        with open(nsfopen_path, 'r') as orig:
                            f.write(orig.read())
                    print(f"Backup created at: {backup_path}")
                
                # Write patched file
                with open(nsfopen_path, 'w') as f:
                    f.writelines(lines)
                print("NSFopen patched successfully!")
                return True
            else:
                print("NSFopen appears to be already patched or doesn't need patching.")
                return True
    
    print("Warning: NSFopen not found in site-packages. You may need to patch it manually.")
    return False

if __name__ == "__main__":
    patch_nsfopen()
