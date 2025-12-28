"""
CS2 Skybox Converter - PyImGui Interface
Convert cubemap skyboxes to CS2 format with optional addon integration
"""

import imgui
import glfw
from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
import sys
import os
import subprocess
import threading
import tempfile
from tkinter import filedialog
import tkinter as tk
from PIL import Image

# Helper function for PyInstaller resource paths
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Face order for the skybox
TARGET_SLOTS = ['up', 'left', 'front', 'right', 'back', 'down']

# Transformation configuration for standard VTF/PNG files
# Format: 'Target Slot': ('Source Face', Rotation Degrees (CCW), PIL Flip Constant)
DEFAULT_TRANSFORMS = {
    'up':      ('up', 0, None),
    'down':    ('down', 0, None),
    'left':    ('back', 0, None), 
    'front':   ('right', 0, None),
    'right':   ('front', 0, None), 
    'back':    ('left', 0, None),
}

def select_skybox_files():
    """Open dialog to select all 6 skybox face images at once"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "skybox.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    # Show instructions
    messagebox.showinfo(
        "Select Skybox Files",
        "Please select all 6 skybox face images.\n\n"
        "Images must be named with these face identifiers:\n\n"
        "• UP: _up, up_, up.\n"
        "• DOWN: _down, down_, down., _dn, dn_, dn.\n"
        "• LEFT: _left, left_, left., _lf, lf_, lf.\n"
        "• RIGHT: _right, right_, right., _rt, rt_, rt.\n"
        "• FRONT: _front, front_, front., _ft, ft_, ft.\n"
        "• BACK: _back, back_, back., _bk, bk_, bk.\n\n"
        "Supported formats: VTF, PNG, JPG, JPEG, TGA, EXR"
    )
    
    # Ask user to select all 6 files at once
    file_paths = filedialog.askopenfilenames(
        title="Select all 6 skybox face images",
        filetypes=[
            ("Image files", "*.vtf *.png *.jpg *.jpeg *.tga *.exr"),
            ("All files", "*.*")
        ]
    )
    
    if not file_paths:
        # User cancelled, just return None without showing error
        return None
    
    if len(file_paths) != 6:
        messagebox.showerror("Invalid Selection", f"Please select exactly 6 images. You selected {len(file_paths)}.")
        return None
    
    # Try to automatically match files to faces based on filename
    files = {}
    unmatched_files = []
    
    for file_path in file_paths:
        filename = os.path.basename(file_path).lower()
        matched = False
        
        for face in TARGET_SLOTS:
            # Common abbreviations for each face
            face_patterns = {
                'up': ['_up.', 'up.', '_up_', 'up_', '_pz.', 'pz.', '_pz_', 'pz_'],
                'down': ['_down.', 'down.', '_down_', 'down_', '_dn.', 'dn.', '_dn_', 'dn_', '_nz.', 'nz.', '_nz_', 'nz_'],
                'left': ['_left.', 'left.', '_left_', 'left_', '_lf.', 'lf.', '_lf_', 'lf_', '_nx.', 'nx.', '_nx_', 'nx_'],
                'right': ['_right.', 'right.', '_right_', 'right_', '_rt.', 'rt.', '_rt_', 'rt_', '_px.', 'px.', '_px_', 'px_'],
                'front': ['_front.', 'front.', '_front_', 'front_', '_ft.', 'ft.', '_ft_', 'ft_', '_ny.', 'ny.', '_ny_', 'ny_'],
                'back': ['_back.', 'back.', '_back_', 'back_', '_bk.', 'bk.', '_bk_', 'bk_', '_py.', 'py.', '_py_', 'py_']
            }
            
            patterns = face_patterns.get(face, [])
            
            if any(pattern in filename for pattern in patterns):
                if face in files:
                    # Duplicate face found
                    messagebox.showerror(
                        "Duplicate Face",
                        f"Multiple files detected for '{face}' face.\nPlease ensure each face has only one image."
                    )
                    return None
                files[face] = file_path
                matched = True
                break
        
        if not matched:
            unmatched_files.append(os.path.basename(file_path))
    
    # Check if we matched all 6 faces
    if len(files) != 6:
        missing_faces = [face for face in TARGET_SLOTS if face not in files]
        messagebox.showerror(
            "Cannot Auto-Detect Faces",
            f"Could not automatically detect which image corresponds to which skybox face.\n\n"
            f"Matched: {len(files)}/6 faces\n"
            f"Missing: {', '.join(missing_faces)}\n"
            f"Unmatched files: {', '.join(unmatched_files) if unmatched_files else 'None'}\n\n"
            f"Please ensure your files are named with face indicators:\n"
            f"Examples: skybox_up.png, left.tga, mysky_front.jpg, etc."
        )
        return None
    
    return files

def ask_vmat_preferences():
    """Ask user which VMAT files they want to create (before selecting output location)"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "skybox.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    # Ask about Skybox material
    create_skybox = messagebox.askyesno(
        "Skybox Material",
        "Do you want to create a Skybox Material?\n\n(Uses standard sky.vfx shader)",
        parent=root
    )
    
    # Ask about Moondome material
    create_moondome = messagebox.askyesno(
        "Moondome Material",
        "Do you want to create a Moondome Material?\n\n(Uses csgo_moondome.vfx shader)",
        parent=root
    )
    
    root.destroy()
    
    return create_skybox, create_moondome

def select_output_location():
    """Open dialog to select output file location"""
    root = tk.Tk()
    root.withdraw()
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "skybox.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    # Show instructions
    messagebox.showinfo(
        "Choose Output Destination",
        "Where do you want to save the skybox assets?"
    )
    
    file_path = filedialog.asksaveasfilename(
        title="Save Skybox As",
        defaultextension=".png",
        filetypes=[("PNG Image", "*.png")]
    )
    
    if not file_path:
        messagebox.showerror("Cancelled", "No output location selected. Aborting.")
        return None
    
    return file_path

def get_ldr_vmat_content(sky_texture_path):
    """Generates the VMAT content for standard skybox with the correct dynamic texture path."""
    return f"""// THIS FILE IS AUTO-GENERATED (STANDARD SKYBOX)

Layer0
{{
    shader "sky.vfx"

    //---- Format ----
    F_TEXTURE_FORMAT2 1 // Dxt1 (LDR)

    //---- Texture ----
    g_flBrightnessExposureBias "0.000"
    g_flRenderOnlyExposureBias "0.000"
    SkyTexture "{sky_texture_path}"


    VariableState
    {{
        "Texture"
        {{
        }}
    }}
}}"""

def get_moondome_vmat_content(sky_texture_path):
    """Generates the Moondome VMAT content with the correct dynamic texture path."""
    return f"""// THIS FILE IS AUTO-GENERATED (MOONDOME)

Layer0
{{
    shader "csgo_moondome.vfx"

    //---- Color ----
    g_flTexCoordRotation "0.000"
    g_nScaleTexCoordUByModelScaleAxis "0" // None
    g_nScaleTexCoordVByModelScaleAxis "0" // None
    g_vColorTint "[1.000000 1.000000 1.000000 0.000000]"
    g_vTexCoordCenter "[0.500 0.500]"
    g_vTexCoordOffset "[0.000 0.000]"
    g_vTexCoordScale "[1.000 1.000]"
    g_vTexCoordScrollSpeed "[0.000 0.000]"
    TextureColor "[1.000000 1.000000 1.000000 0.000000]"

    //---- CubeParallax ----
    g_flCubeParallax "0.000"

    //---- Fog ----
    g_bFogEnabled "1"

    //---- Texture ----
    TextureCubeMap "{sky_texture_path}"

    //---- Texture Address Mode ----
    g_nTextureAddressModeU "0" // Wrap
    g_nTextureAddressModeV "0" // Wrap


    VariableState
    {{
        "Color"
        {{
        }}
        "CubeParallax"
        {{
        }}
        "Fog"
        {{
        }}
        "Texture"
        {{
        }}
        "Texture Address Mode"
        {{
        }}
    }}
}}"""

def create_vmat_files(output_path, create_skybox, create_moondome):
    """Create VMAT files based on user preferences"""
    if not create_skybox and not create_moondome:
        return []
    
    created_files = []
    output_dir = os.path.dirname(output_path)
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    png_filename = os.path.basename(output_path)
    
    # Engine texture path for VMAT (relative path from content folder)
    # Assuming output is in a skybox folder or similar
    sky_texture_path = f"materials/skybox/{png_filename}"
    
    try:
        if create_skybox:
            skybox_vmat_path = os.path.join(output_dir, f"skybox_{base_name}.vmat")
            with open(skybox_vmat_path, 'w') as f:
                f.write(get_ldr_vmat_content(sky_texture_path))
            created_files.append(skybox_vmat_path)
            print(f"Created Skybox VMAT: {os.path.basename(skybox_vmat_path)}")
        
        if create_moondome:
            moondome_vmat_path = os.path.join(output_dir, f"moondome_{base_name}.vmat")
            with open(moondome_vmat_path, 'w') as f:
                f.write(get_moondome_vmat_content(sky_texture_path))
            created_files.append(moondome_vmat_path)
            print(f"Created Moondome VMAT: {os.path.basename(moondome_vmat_path)}")
            
    except Exception as e:
        print(f"Error creating VMAT files: {e}")
    
    return created_files

def convert_vtf_to_pil_image(vtf_path):
    """
    Converts a VTF file to a PIL Image object.
    Returns the Image or raises an exception.
    """
    if not VTF_SUPPORT:
        raise ImportError("vtf2img library is not installed. Cannot convert VTF files.")
    
    try:
        parser = Parser(vtf_path)
        image = parser.get_image()
        # Ensure image is in RGBA format
        image = image.convert("RGBA")
        return image
    except Exception as e:
        if "Unknown image format 3" in str(e):
            raise Exception(
                f"This VTF uses a rare compression format (Type 3) that is not supported.\n"
                f"Please use VTFEdit to manually export '{os.path.basename(vtf_path)}' to PNG/TGA."
            )
        raise Exception(f"Error converting VTF file '{os.path.basename(vtf_path)}': {e}")

def stitch_skybox(files, output_path):
    """Stitch the 6 faces into a single skybox image with proper transformations"""
    temp_files = []  # Track temporary files for cleanup
    
    try:
        # Load all images (convert VTF if needed)
        images = {}
        base_size = None
        
        for face, path in files.items():
            # Check if it's a VTF file
            if path.lower().endswith('.vtf'):
                if not VTF_SUPPORT:
                    raise ImportError(
                        "VTF files detected but vtf2img library is not installed.\n"
                        "Please install it with: pip install vtf2img"
                    )
                print(f"Converting VTF file: {os.path.basename(path)}")
                img = convert_vtf_to_pil_image(path)
            else:
                img = Image.open(path).convert("RGBA")
            
            images[face] = img
            
            # Use the first image size as base size
            if base_size is None:
                base_size = img.size[0]  # Assuming square images
        
        # Create the final image (4x3 grid)
        final_width = base_size * 4
        final_height = base_size * 3
        final_image = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
        
        # Coordinates for each face in the 4x3 grid
        COORDS = {
            'up':    (base_size * 1, base_size * 0),
            'left':  (base_size * 0, base_size * 1),
            'front': (base_size * 1, base_size * 1),
            'right': (base_size * 2, base_size * 1),
            'back':  (base_size * 3, base_size * 1),
            'down':  (base_size * 1, base_size * 2),
        }
        
        print("\nStitching images with proper transformations...")
        
        # Loop over target slots and apply transformations
        for target_slot in TARGET_SLOTS:
            # Get transformation from DEFAULT_TRANSFORMS
            source_face, rotation_degrees, flip = DEFAULT_TRANSFORMS.get(target_slot, (target_slot, 0, None))
            
            # Get the source image
            image_to_paste = images[source_face]
            
            # Resize to base size if needed
            if image_to_paste.size[0] != base_size:
                image_to_paste = image_to_paste.resize((base_size, base_size), Image.Resampling.LANCZOS)
            
            # Apply rotation if specified
            if rotation_degrees != 0:
                image_to_paste = image_to_paste.rotate(rotation_degrees, expand=False)
            
            # Apply flip/transpose if specified
            if flip is not None:
                image_to_paste = image_to_paste.transpose(flip)
            
            # Paste into final image at correct position
            position = COORDS[target_slot]
            final_image.paste(image_to_paste, position)
            
            print(f"  {target_slot}: source='{source_face}', rotation={rotation_degrees}°")
        
        # Save the final image
        final_image.save(output_path, "PNG")
        
        return True, f"Skybox saved successfully to:\n{output_path}\n\nResolution: {final_width}x{final_height}"
        
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error creating skybox: {str(e)}"

def main():
    """Main function"""
    # Select the 6 skybox faces
    files = select_skybox_files()
    if not files:
        sys.exit(1)
    
    # Ask about VMAT creation BEFORE selecting output location
    create_skybox, create_moondome = ask_vmat_preferences()
    
    # Select output location
    output_path = select_output_location()
    if not output_path:
        # User cancelled, exit gracefully without showing more dialogs
        sys.exit(0)
    
    # Stitch the skybox
    success, message = stitch_skybox(files, output_path)
    
    # Create VMAT files if requested and skybox was created successfully
    vmat_files = []
    if success:
        vmat_files = create_vmat_files(output_path, create_skybox, create_moondome)
    
    # Show result
    root = tk.Tk()
    root.withdraw()
    
    # Set window icon
    try:
        icon_path = resource_path(os.path.join("icons", "skybox.ico"))
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Could not set window icon: {e}")
    
    if success:
        # Add VMAT info to success message
        if vmat_files:
            vmat_names = "\n".join([f"  • {os.path.basename(f)}" for f in vmat_files])
            message += f"\n\nVMAT files created:\n{vmat_names}"
        
        messagebox.showinfo("Success", message)
        # Open the folder containing the output image
        try:
            output_folder = os.path.dirname(output_path)
            if sys.platform == 'win32':
                os.startfile(output_folder)
            elif sys.platform == 'darwin':  # macOS
                os.system(f'open "{output_folder}"')
            else:  # linux
                os.system(f'xdg-open "{output_folder}"')
        except Exception as e:
            print(f"Could not open output folder: {e}")
    else:
        messagebox.showerror("Error", message)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
