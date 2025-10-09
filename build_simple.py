#!/usr/bin/env python3
"""
Simple build script for Bullseye Injector executable
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    print("Building Bullseye Injector...")
    
    # Check if required files exist
    if not Path("sprite_converter_gui.py").exists():
        print("Error: sprite_converter_gui.py not found!")
        return False
    
    if not Path("sprite_processor.py").exists():
        print("Error: sprite_processor.py not found!")
        return False
    
    if not Path("modpackages").exists():
        print("Error: modpackages directory not found!")
        return False
    
    # Build command using python -m PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name=BullseyeInjector",
        "--add-data=sprite_processor.py;.",
        "--add-data=Template.zip;.",
        "--add-data=modpackages;modpackages",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageSequence",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.filedialog",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=tkinter.scrolledtext",
        "--hidden-import=mod_packager",
        "sprite_converter_gui.py"
    ]
    
    # Add icon if it exists
    icon_path = Path("icon.ico")
    if icon_path.exists():
        cmd.append(f"--icon=icon.ico")
        print(f"SUCCESS: Found icon.ico - will be included in executable")
        print(f"Icon path: {icon_path}")
    else:
        print("WARNING: No icon.ico found - executable will use default icon")
    
    try:
        print("Running PyInstaller...")
        result = subprocess.run(cmd, check=True)
        
        exe_path = Path("dist/BullseyeInjector.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"SUCCESS: Build successful!")
            print(f"Executable: {exe_path.absolute()}")
            print(f"Size: {size_mb:.1f} MB")
            return True
        else:
            print("ERROR: Build failed - executable not found")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Build failed with error code: {e.returncode}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        print("\nTroubleshooting:")
        print("1. Make sure PyInstaller is installed: pip install pyinstaller")
        print("2. Check that all required files are in the current directory")
        print("3. Try running: python -m pip install --upgrade pyinstaller")
    
    input("\nPress Enter to continue...")
    sys.exit(0 if success else 1)

