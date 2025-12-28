"""
VTF to PNG Converter
Converts all VTF files in the current directory to PNG format using VTFCmd.exe
"""

import os
import sys
import subprocess
import tempfile
import shutil
import urllib.request
import zipfile
import io
from pathlib import Path

# --- VTF Tools Path Detection ---
def find_vtfcmd():
    """Find VTFCmd.exe in various locations, download if not found"""
    
    # Check 1: .CS2KZ-mapping-tools/vtf folder in Temp (preferred - shared location)
    temp_dir = os.environ.get('TEMP', os.environ.get('TMP', tempfile.gettempdir()))
    if temp_dir:
        tools_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools', 'vtf')
        vtfcmd_path = os.path.join(tools_dir, 'VTFCmd.exe')
        vtflib_path = os.path.join(tools_dir, 'VTFLib.dll')
        
        if os.path.exists(vtfcmd_path) and os.path.exists(vtflib_path):
            print(f"[OK] Using VTF tools from: {vtfcmd_path}")
            return vtfcmd_path
    
    # Check 2: Bundled VTF tools (fallback)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    bundled_vtfcmd = os.path.join(project_root, 'vtf', 'VTFCmd.exe')
    
    if os.path.exists(bundled_vtfcmd):
        bundled_vtflib = os.path.join(project_root, 'vtf', 'VTFLib.dll')
        if os.path.exists(bundled_vtflib):
            print(f"[OK] Using bundled VTF tools from: {bundled_vtfcmd}")
            return bundled_vtfcmd
    
    # Download VTF tools if not found anywhere
    if not temp_dir:
        print("[ERROR] Cannot determine temp directory for VTF tools download")
        return None
    
    tools_dir = os.path.join(temp_dir, '.CS2KZ-mapping-tools', 'vtf')
    os.makedirs(tools_dir, exist_ok=True)
    
    vtfcmd_path = os.path.join(tools_dir, 'VTFCmd.exe')
    vtflib_path = os.path.join(tools_dir, 'VTFLib.dll')
    
    print("VTF tools not found. Downloading from GitHub...")
    print("This is a one-time download (~2 MB)...")
    
    try:
        download_url = "https://nemstools.github.io/files/vtflib132-bin.zip"
        print(f"Downloading VTFLib binaries from {download_url}...")
        
        with urllib.request.urlopen(download_url, timeout=30) as response:
            download_data = response.read()
        
        # Extract all required VTF tools and dependencies from the zip
        with zipfile.ZipFile(io.BytesIO(download_data)) as zf:
            # Required files to extract (all x64 versions)
            required_files = {
                'VTFCmd.exe': vtfcmd_path,
                'VTFLib.dll': vtflib_path,
                'DevIL.dll': os.path.join(tools_dir, 'DevIL.dll'),
                'ILU.dll': os.path.join(tools_dir, 'ILU.dll'),
                'ILUT.dll': os.path.join(tools_dir, 'ILUT.dll')
            }
            found_files = set()
            
            for file_info in zf.namelist():
                # Extract each required file (prefer x64 version)
                for filename, output_path in required_files.items():
                    if filename in file_info and filename not in found_files:
                        if 'x64' in file_info:  # Prefer x64 version
                            with open(output_path, 'wb') as f:
                                f.write(zf.read(file_info))
                            found_files.add(filename)
                            print(f"[OK] Extracted {filename}")
                            break
                
                # Stop if all required files are found
                if len(found_files) >= len(required_files):
                    break
            
            # Report missing files
            missing = set(required_files.keys()) - found_files
            if missing:
                print(f"[WARNING] Missing files: {', '.join(missing)}")
        
        if 'VTFCmd.exe' in found_files and 'VTFLib.dll' in found_files:
            print(f"[OK] VTF tools installed to: {tools_dir}")
            return vtfcmd_path
        else:
            print("[ERROR] Failed to extract required VTF tools from archive")
            return None
            
    except Exception as e:
        print(f"[ERROR] Failed to download VTF tools: {e}")
        return None

# Initialize VTFCmd path
VTFCMD_PATH = find_vtfcmd()
if not VTFCMD_PATH:
    print("Error: VTFCmd.exe not found and could not be downloaded.")
    print("Cannot proceed without VTF conversion tools.")
    sys.exit(1)


def convert_vtf_to_png(vtf_path, output_dir=None):
    """
    Convert a single VTF file to PNG using VTFCmd.exe.
    
    Args:
        vtf_path: Path to the VTF file
        output_dir: Output directory. If None, uses same directory as vtf_path
    
    Returns:
        True if successful, False otherwise
    """
    try:
        base_name = os.path.basename(vtf_path)
        
        # Determine output directory
        if output_dir is None:
            output_dir = os.path.dirname(vtf_path) or '.'
        
        # Use absolute paths
        abs_vtf_path = os.path.abspath(vtf_path)
        abs_output_dir = os.path.abspath(output_dir)
        
        # Get VTFCmd.exe directory to ensure VTFLib.dll is accessible
        vtfcmd_dir = os.path.dirname(VTFCMD_PATH)
        vtflib_path = os.path.join(vtfcmd_dir, 'VTFLib.dll')
        
        if not os.path.exists(vtflib_path):
            raise Exception(f"VTFLib.dll not found at: {vtflib_path}")
        
        # VTFCmd.exe command for VTF to PNG conversion
        cmd = [
            VTFCMD_PATH,
            '-file', abs_vtf_path,
            '-output', abs_output_dir,
            '-exportformat', 'png'
        ]
        
        # Run VTFCmd.exe from its own directory to ensure DLL loading works
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=vtfcmd_dir,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        if result.returncode != 0:
            print(f"  Error: VTFCmd.exe failed with return code {result.returncode}")
            if result.stderr:
                print(f"  {result.stderr}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  Error: {e}")
        return False


def main():
    """Main function - convert all VTF files in current directory"""
    # Get current directory
    current_dir = Path.cwd()
    
    # Find all VTF files
    vtf_files = list(current_dir.glob("*.vtf"))
    
    if not vtf_files:
        print("No VTF files found in the current directory.")
        return
    
    print(f"Found {len(vtf_files)} VTF file(s)")
    print("-" * 50)
    
    converted = 0
    failed = 0
    
    for vtf_file in vtf_files:
        print(f"Converting: {vtf_file.name}")
        
        if convert_vtf_to_png(vtf_file):
            output_name = vtf_file.with_suffix('.png').name
            print(f"  -> Saved: {output_name}")
            converted += 1
        else:
            failed += 1
    
    print("-" * 50)
    print(f"Conversion complete!")
    print(f"  Converted: {converted}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    print("VTF to PNG Converter")
    print("=" * 50)
    main()
