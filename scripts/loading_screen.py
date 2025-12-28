import os
import shutil
import sys
import subprocess
import time
import re
from PIL import Image
import winreg
import vdf
import glob

# The following functions for finding the Steam/CS2 directory were provided by the user.
def get_steam_directory():
    """Get the Steam installation directory from the Windows Registry."""
    try:
        # Open the Steam key in the registry
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            # Get the SteamPath value
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            return steam_path
    except FileNotFoundError:
        print("Steam is not installed or the registry key was not found.")
        return None

def find_cs2_library_path(libraryfolders_path):
    """Parse the libraryfolders.vdf file to get all library paths."""
    try:
        if not os.path.exists(libraryfolders_path):
            print(f"libraryfolders.vdf not found at {libraryfolders_path}")
            return None

        with open(libraryfolders_path, 'r', encoding='utf-8') as file:
            library_data = vdf.load(file)

        if 'libraryfolders' in library_data:
            for _, folder in library_data['libraryfolders'].items():
                if 'apps' in folder and '730' in folder['apps']:
                    return folder['path']
        print("Failed to find CS2 library path.")
    except Exception as e:
        print(f"Error parsing libraryfolders.vdf: {e}")
    return None

def get_cs2_path():
    """Find the CS2 installation directory using the Steam app ID."""
    try:
        steam_path = get_steam_directory()
        if steam_path is None:
            return None
        library_path = find_cs2_library_path(os.path.join(steam_path, "steamapps", "libraryfolders.vdf"))
        if library_path is None:
            return None
        appmanifest_path = os.path.join(library_path, 'steamapps', 'appmanifest_730.acf')
        if not os.path.exists(appmanifest_path):
            print(f"appmanifest_730.acf not found at {appmanifest_path}")
            return None
        with open(appmanifest_path, 'r', encoding='utf-8') as file:
            return os.path.join(library_path, 'steamapps', 'common', vdf.load(file)['AppState']['installdir'])
    except Exception as e:
        print(f"Failed to get CS2 path: {e}")
    return None

def handle_compiled_files(game_root, map_name, addon_name):
    """
    Finds and renames the compiled VMAT, VTEX, and VSVG files, then removes original compiled files.
    """
    print("\nHandling compiled files...")
    print(f"Game root: {game_root}")
    print(f"Map name: {map_name}")
    print(f"Addon name: {addon_name}")
    
    game_addons_dir = os.path.join(game_root, 'game', 'csgo_addons', addon_name)
    content_addons_dir = os.path.join(game_root, 'content', 'csgo_addons', addon_name)
    
    # Define the base directory for compiled materials and textures
    compiled_screenshots_dir = os.path.join(game_addons_dir, 'panorama', 'images', 'map_icons', 'screenshots', '1080p')
    compiled_icons_dir = os.path.join(game_addons_dir, 'panorama', 'images', 'map_icons')
    
    print(f"Compiled screenshots dir: {compiled_screenshots_dir}")
    print(f"Directory exists: {os.path.exists(compiled_screenshots_dir)}")
        # Handle compiled screenshot files (.vmat_c, .vtex_c)
    if os.path.exists(compiled_screenshots_dir):
        print(f"Looking in: {compiled_screenshots_dir}")
        print(f"Map name: {map_name}")
        
        # List all files in the directory for debugging
        all_files = glob.glob(os.path.join(compiled_screenshots_dir, "*.*"))
        print(f"All files in directory: {[os.path.basename(f) for f in all_files]}")
        
        files_to_handle = glob.glob(os.path.join(compiled_screenshots_dir, f"{map_name}_*_png_*.vmat_c")) + \
                          glob.glob(os.path.join(compiled_screenshots_dir, f"{map_name}_*_png_*.vtex_c")) + \
                          glob.glob(os.path.join(compiled_screenshots_dir, f"*_png_*.vmat_c")) + \
                          glob.glob(os.path.join(compiled_screenshots_dir, f"*_png_*.vtex_c"))
        
        # Remove duplicates
        files_to_handle = list(set(files_to_handle))
        
        print(f"Found {len(files_to_handle)} compiled files to rename")
        for file_path in files_to_handle:
            file_name = os.path.basename(file_path)
            print(f"Processing: {file_name}")
            
            # Remove the hash part added by the compiler
            # e.g., kz_ashen_1_png_8363d5cd.vtex_c -> kz_ashen_1_png.vtex_c
            if '_png_' in file_name:
                if file_name.endswith('.vtex_c'):
                    # For vtex files, look for pattern: mapname_X_png_hash.vtex_c -> mapname_X_png.vtex_c
                    match = re.match(r'(.+_\d+_png)_[a-f0-9]+\.vtex_c$', file_name)
                    if match:
                        new_name = match.group(1) + '.vtex_c'
                        print(f"Renaming to: {new_name}")
                        new_file_path = os.path.join(compiled_screenshots_dir, new_name)
                        
                        # Check if the destination file exists and remove it before renaming
                        if os.path.exists(new_file_path):
                            os.remove(new_file_path)
                            print(f"Overwrote existing file: {new_name}")
                        
                        os.rename(file_path, new_file_path)
                        print(f"Successfully renamed {file_name} to {new_name}")
                    else:
                        print(f"Warning: Could not parse vtex filename: {file_name}")
                elif file_name.endswith('.vmat_c'):
                    # For vmat files: mapname_X_png.vmat_c (should already be correct)
                    match = re.match(r'(.+_\d+_png)\.vmat_c$', file_name)
                    if match:
                        new_name = file_name  # Keep as is for .vmat_c files
                        print(f"Keeping vmat_c file as: {new_name}")
                    else:
                        print(f"Warning: Could not parse vmat_c filename: {file_name}")
                else:
                    print(f"Warning: Unknown file extension: {file_name}")
            else:
                print(f"Warning: '_png_' pattern not found in filename: {file_name}")

    # Handle compiled SVG file (.vsvg_c)
    if os.path.exists(compiled_icons_dir):
        files_to_handle = glob.glob(os.path.join(compiled_icons_dir, f"map_icon_{map_name}_svg_*.vsvg_c"))
                          
        for file_path in files_to_handle:
            file_name = os.path.basename(file_path)
            parts = file_name.split('_svg_')
            if len(parts) > 1:
                new_name = parts[0] + "_svg" + file_name[file_name.rfind('.'):]
                new_file_path = os.path.join(compiled_icons_dir, new_name)
                
                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
                    print(f"Overwrote existing file: {new_name}")
                
                os.rename(file_path, new_file_path)
                print(f"Renamed {file_name} to {new_name}")

    # Note: Keeping .vmat and .vmat_c files as they are needed
    print("\nKeeping compiled files (.vmat and .vmat_c) as they are required.")

def compile_vmat_files(game_root, vmat_files, map_name, addon_name=None):
    """
    Compiles a list of .vmat files using resourcecompiler.exe.
    """
    # If addon_name not provided, use map_name for backwards compatibility
    if addon_name is None:
        addon_name = map_name
    
    compiler_path = os.path.join(game_root, 'game', 'bin', 'win64', 'resourcecompiler.exe')
    if not os.path.exists(compiler_path):
        print(f"Error: resourcecompiler.exe not found at {compiler_path}")
        return

    # Set the working directory for the compiler
    compiler_cwd = os.path.join(game_root, 'game')

    for vmat_file in vmat_files:
        print(f"Compiling {os.path.basename(vmat_file)}...")
        try:
            # The input file path needs to be relative to the 'game' directory
            relative_vmat_path = os.path.relpath(vmat_file, start=compiler_cwd).replace("\\", "/")
            
            command = [compiler_path, relative_vmat_path]
            result = subprocess.run(command, cwd=compiler_cwd, check=True, capture_output=True, text=True)
            print(f"Compilation successful for {os.path.basename(vmat_file)}")
            print("--- Compiler Output (stdout) ---")
            print(result.stdout)
            print("--------------------------------")
        except subprocess.CalledProcessError as e:
            print(f"Compilation failed for {os.path.basename(vmat_file)}: {e}")
            print("--- Compiler Output (stdout) ---")
            print(e.stdout)
            print("--- Compiler Error (stderr) ---")
            print(e.stderr)
            print("--------------------------------")
            # If a compilation fails, we can't handle the compiled files for it, so we break
            return
        except FileNotFoundError:
            print(f"Error: resourcecompiler.exe not found. Please check the path: {compiler_path}")
            break
        except Exception as e:
            print(f"An unexpected error occurred during compilation: {e}")
            break

    # After all files are compiled successfully, handle the compiled files
    handle_compiled_files(game_root, map_name, addon_name)

def compile_svg_files(game_root, svg_files, map_name, addon_name=None):
    """
    Compiles a list of .svg files using resourcecompiler.exe.
    """
    # If addon_name not provided, use map_name for backwards compatibility
    if addon_name is None:
        addon_name = map_name
    compiler_path = os.path.join(game_root, 'game', 'bin', 'win64', 'resourcecompiler.exe')
    if not os.path.exists(compiler_path):
        print(f"Error: resourcecompiler.exe not found at {compiler_path}")
        return

    # Set the working directory for the compiler
    compiler_cwd = os.path.join(game_root, 'game')

    for svg_file in svg_files:
        print(f"Compiling {os.path.basename(svg_file)}...")
        try:
            # The input file path needs to be relative to the 'game' directory
            relative_svg_path = os.path.relpath(svg_file, start=compiler_cwd).replace("\\", "/")
            
            command = [compiler_path, relative_svg_path]
            result = subprocess.run(command, cwd=compiler_cwd, check=True, capture_output=True, text=True)
            print(f"Compilation successful for {os.path.basename(svg_file)}")
            print("--- Compiler Output (stdout) ---")
            print(result.stdout)
            print("--------------------------------")
        except subprocess.CalledProcessError as e:
            print(f"Compilation failed for {os.path.basename(svg_file)}: {e}")
            print("--- Compiler Output (stdout) ---")
            print(e.stdout)
            print("--- Compiler Error (stderr) ---")
            print(e.stderr)
            print("--------------------------------")
            # If a compilation fails, we can't handle the compiled files for it, so we break
            return
        except FileNotFoundError:
            print(f"Error: resourcecompiler.exe not found. Please check the path: {compiler_path}")
            break
        except Exception as e:
            print(f"An unexpected error occurred during compilation: {e}")
            break

def create_vmat_content(map_name, index):
    """
    Generates the content for a .vmat file with the new path structure.
    """
    content = f'''// THIS FILE IS AUTO-GENERATED

Layer0
{{
    shader "csgo_composite_generic.vfx"

    g_flAlphaBlend "0.000"

    //---- Options ----
    TextureA "panorama/images/map_icons/screenshots/1080p/{map_name}_{index}.png"
    TextureB ""


    VariableState
    {{
        "Options"
        {{
        }}
    }}
}}
'''
    return content

def create_map_files():
    """
    Automates the process of organizing map-related files for a Source 2 map.
    """
    # Find CS2 directory using the new, robust method
    game_root = get_cs2_path()
    if not game_root:
        game_root = input("Could not find Steam directory. Please enter the path to your csgo folder (e.g., C:\\...\\Counter-Strike Global Offensive\\csgo): ")
        if not os.path.exists(game_root):
            print("The provided path does not exist. Exiting.")
            return

    # Always prompt the user for the map name
    map_name = input("Please enter the map name (e.g., kz_jakke): ")
    if not map_name:
        print("Map name cannot be empty. Exiting.")
        return

    source_dir = os.getcwd()

    # Define the base paths for the new directory structure
    content_addons_dir = os.path.join(game_root, 'content', 'csgo_addons', map_name)
    game_addons_dir = os.path.join(game_root, 'game', 'csgo_addons', map_name)
    
    # Define full destination folder paths based on the new structure
    loading_screen_dir = os.path.join(content_addons_dir, 'panorama', 'images', 'map_icons', 'screenshots', '1080p')
    map_icon_content_dir = os.path.join(content_addons_dir, 'panorama', 'images', 'map_icons')
    maps_dir = os.path.join(game_addons_dir, 'maps')

    # Create destination directories if they don't exist
    for directory in [loading_screen_dir, map_icon_content_dir, maps_dir]:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")
    
    files_to_process = os.listdir(source_dir)
    vmat_files_to_compile = []
    svg_files_to_compile = []
    
    # Process loading screen images
    image_extensions = ('.jpg', '.jpeg', '.png', '.tga', '.bmp')
    image_files = sorted([f for f in files_to_process if f.lower().endswith(image_extensions)])
    
    for i, source_image_name in enumerate(image_files, 1):
        dest_image_name = f"{map_name}_{i}.png"
        dest_image_path = os.path.join(loading_screen_dir, dest_image_name)

        try:
            with Image.open(os.path.join(source_dir, source_image_name)) as img:
                # Get original dimensions
                width, height = img.size
                
                # Calculate new dimensions to crop to a 16:9 aspect ratio
                target_aspect_ratio = 16.0 / 9.0
                original_aspect_ratio = width / height

                if original_aspect_ratio > target_aspect_ratio:
                    # Image is too wide, crop the sides
                    new_width = int(height * target_aspect_ratio)
                    left = (width - new_width) / 2
                    top = 0
                    right = (width + new_width) / 2
                    bottom = height
                else:
                    # Image is too tall, crop the top and bottom
                    new_height = int(width / target_aspect_ratio)
                    left = 0
                    top = (height - new_height) / 2
                    right = width
                    bottom = (height + new_height) / 2

                # Crop the image
                img_cropped = img.crop((left, top, right, bottom))
                
                # Save the final image without resizing
                img_cropped.save(dest_image_path, "PNG")
                
            print(f"Converted and saved {source_image_name} to {dest_image_path} (16:9 aspect ratio)")
        except Exception as e:
            print(f"Error processing {source_image_name}: {e}")

        # Generate the corresponding vmat file
        dest_vmat_name = f"{map_name}_{i}_png.vmat"
        dest_vmat_path = os.path.join(loading_screen_dir, dest_vmat_name)
        vmat_content = create_vmat_content(map_name, i)
        
        with open(dest_vmat_path, 'w') as f:
            f.write(vmat_content)
        print(f"Generated and saved {dest_vmat_name} to {dest_vmat_path}")
        vmat_files_to_compile.append(dest_vmat_path)
            
    # Process map icon file
    found_icon = False
    for f in files_to_process:
        if f.endswith('.svg'):
            icon_source_name = f
            found_icon = True
            break
            
    if found_icon:
        dest_icon_name = f"map_icon_{map_name}.svg"
        dest_icon_path = os.path.join(map_icon_content_dir, dest_icon_name)
        shutil.copy(os.path.join(source_dir, icon_source_name), dest_icon_path)
        print(f"Copied {icon_source_name} to {dest_icon_path} and renamed to {dest_icon_name}")
        svg_files_to_compile.append(dest_icon_path)

    # Process map description file
    description_file_name = f"{map_name}.txt"
    description_file_path = os.path.join(maps_dir, description_file_name)
    
    # Find and move an existing .txt file, or create a new empty one
    txt_files = [f for f in files_to_process if f.lower().endswith('.txt') and f.lower() != 'readme.txt' and f != os.path.basename(sys.argv[0])]
    
    if txt_files:
        source_txt_path = os.path.join(source_dir, txt_files[0])
        # The line below has been changed to copy the file instead of moving it
        shutil.copy(source_txt_path, description_file_path)
        print(f"Copied and renamed {txt_files[0]} to {description_file_path}")

    # Compile all the generated VMAT files
    if vmat_files_to_compile:
        compile_vmat_files(game_root, vmat_files_to_compile, map_name)
    
    # Compile all the SVG files
    if svg_files_to_compile:
        compile_svg_files(game_root, svg_files_to_compile, map_name)

    print("\nProcess completed.") 
    time.sleep(3)

if __name__ == "__main__":

    create_map_files()
