"""
VTF to PNG Converter - GUI Version
Allows user to select multiple VTF files and converts them to PNG using VTFCmd.exe
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import subprocess
import tempfile
import urllib.request
import zipfile
import io

# Import VTF conversion from vtf2png.py
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    from vtf2png import find_vtfcmd, VTFCMD_PATH
    VTF_SUPPORT = VTFCMD_PATH is not None
except Exception as e:
    VTF_SUPPORT = False
    VTFCMD_PATH = None
    print(f"Warning: VTF tools not found: {e}")

# Helper function for PyInstaller resource paths
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def convert_vtf_to_png(vtf_path, output_path=None):
    """
    Convert a single VTF file to PNG using VTFCmd.exe.
    
    Args:
        vtf_path: Path to the VTF file
        output_path: Optional output path. If None, uses same directory with .png extension
    
    Returns:
        tuple: (success: bool, message: str)
    """
    if not VTF_SUPPORT or not VTFCMD_PATH:
        return False, "VTFCmd.exe is not available"
    
    try:
        base_name = os.path.basename(vtf_path)
        
        # Determine output directory
        if output_path is None:
            output_dir = os.path.dirname(vtf_path) or '.'
            output_path = os.path.splitext(vtf_path)[0] + '.png'
        else:
            output_dir = os.path.dirname(output_path) or '.'
        
        # Use absolute paths
        abs_vtf_path = os.path.abspath(vtf_path)
        abs_output_dir = os.path.abspath(output_dir)
        
        # Get VTFCmd.exe directory to ensure VTFLib.dll is accessible
        vtfcmd_dir = os.path.dirname(VTFCMD_PATH)
        vtflib_path = os.path.join(vtfcmd_dir, 'VTFLib.dll')
        
        if not os.path.exists(vtflib_path):
            return False, f"VTFLib.dll not found at: {vtflib_path}"
        
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
            error_msg = result.stderr if result.stderr else f"VTFCmd.exe failed with return code {result.returncode}"
            return False, f"Conversion error: {error_msg}"
        
        # Check if output file was created
        expected_png = os.path.join(abs_output_dir, os.path.splitext(base_name)[0] + '.png')
        if os.path.exists(expected_png):
            return True, expected_png
        else:
            return False, "Output file was not created"
        
    except Exception as e:
        return False, f"Conversion error: {str(e)}"


def select_vtf_files():
    """Open dialog to select VTF files"""
    root = tk.Tk()
    root.withdraw()
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "vtf2png.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    file_paths = filedialog.askopenfilenames(
        title="Select VTF files to convert",
        filetypes=[
            ("VTF files", "*.vtf"),
            ("All files", "*.*")
        ]
    )
    
    if not file_paths:
        return None
    
    return list(file_paths)


def select_output_directory():
    """Open dialog to select output directory"""
    root = tk.Tk()
    root.withdraw()
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "vtf2png.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    dir_path = filedialog.askdirectory(
        title="Select output directory (or Cancel to use same directory as VTF files)"
    )
    
    return dir_path if dir_path else None


def convert_files(vtf_files, output_dir=None):
    """
    Convert multiple VTF files to PNG.
    
    Args:
        vtf_files: List of VTF file paths
        output_dir: Optional output directory. If None, saves next to original files
    
    Returns:
        tuple: (converted_count, failed_count, results_list, actual_output_dir)
    """
    converted = 0
    failed = 0
    results = []
    actual_output_dir = output_dir
    
    for vtf_file in vtf_files:
        filename = os.path.basename(vtf_file)
        
        # Determine output path
        if output_dir:
            output_filename = os.path.splitext(filename)[0] + '.png'
            output_path = os.path.join(output_dir, output_filename)
        else:
            output_path = None  # Will use same directory as VTF
            # Track the actual output directory from first file
            if actual_output_dir is None:
                actual_output_dir = os.path.dirname(vtf_file)
        
        # Convert
        success, message = convert_vtf_to_png(vtf_file, output_path)
        
        if success:
            converted += 1
            results.append(f"[OK] {filename} -> {os.path.basename(message)}")
        else:
            failed += 1
            results.append(f"[FAIL] {filename}: {message}")
    
    return converted, failed, results, actual_output_dir


def main():
    """Main function"""
    # Check if VTF support is available
    if not VTF_SUPPORT:
        root = tk.Tk()
        root.withdraw()
        
        # Set window icon
        try:
            icon_path = resource_path(os.path.join("icons", "vtf2png.ico"))
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        messagebox.showerror(
            "VTF Tools Not Found",
            "VTFCmd.exe could not be found or downloaded.\n\n"
            "VTF conversion tools are required for this program to work.\n"
            "Please check your internet connection and try again."
        )
        sys.exit(1)
    
    # Select VTF files
    vtf_files = select_vtf_files()
    if not vtf_files:
        sys.exit(0)
    
    # Ask about output directory
    root = tk.Tk()
    root.withdraw()
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "vtf2png.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    use_custom_dir = messagebox.askyesno(
        "Output Location",
        f"Selected {len(vtf_files)} VTF file(s).\n\n"
        "Save PNG files to a different directory?\n\n"
        "Yes = Choose output directory\n"
        "No = Save next to VTF files"
    )
    
    output_dir = None
    if use_custom_dir:
        output_dir = select_output_directory()
        if not output_dir:
            # User cancelled directory selection
            messagebox.showinfo("Cancelled", "Output directory selection cancelled.\nUsing same directory as VTF files.")
    
    # Convert files
    converted, failed, results, actual_output_dir = convert_files(vtf_files, output_dir)
    
    # Show results
    root = tk.Tk()
    root.withdraw()
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "vtf2png.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    result_text = "\n".join(results)
    summary = f"Conversion Complete!\n\nConverted: {converted}\nFailed: {failed}\n\n{result_text}"
    
    if failed > 0:
        messagebox.showwarning("Conversion Complete (with errors)", summary)
    else:
        messagebox.showinfo("Success", summary)
    
    # Open output directory if any files were converted
    if converted > 0 and actual_output_dir:
        try:
            if sys.platform == 'win32':
                os.startfile(actual_output_dir)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{actual_output_dir}"')
            else:  # linux
                os.system(f'xdg-open "{actual_output_dir}"')
        except Exception:
            pass


if __name__ == "__main__":
    main()
