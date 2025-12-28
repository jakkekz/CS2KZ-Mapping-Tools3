"""
CS2 Map Importer - PyImGui Interface
Automatically detects CS2 path, modifies required files, and restores them after porting
"""

import imgui
import glfw
from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
import re
import traceback
import sys
import subprocess
import os
import shutil
import tempfile
import winreg
import vdf
from tkinter import filedialog
import tkinter as tk
import webbrowser
import urllib.request
import zipfile
import io
from PIL import Image

# Constants
CUSTOM_TITLE_BAR_HEIGHT = 30


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Import theme manager after resource_path is defined
utils_path = resource_path('utils')
if not os.path.exists(utils_path):
    # If running from scripts/porting, go up two levels to find utils
    utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
sys.path.insert(0, utils_path)

try:
    from theme_manager import ThemeManager
except ImportError:
    # Fallback: create a dummy ThemeManager if not found
    class ThemeManager:
        def __init__(self):
            pass
        def get_current_theme(self):
            return {
                'bg': '#1e1e1e',
                'fg': '#ffffff',
                'button_bg': '#2d2d2d',
                'button_hover': '#3d3d3d'
            }

class CS2ImporterApp:
    def __init__(self):
        self.window = None
        self.impl = None
        
        # Theme manager
        self.theme_manager = ThemeManager()
        
        # Application state
        self.vmf_default_path = "C:\\"
        self.csgo_basefolder = None
        self.vmf_folder = None
        self.vmf_folder_to_save = None
        self.addon = ""
        self.map_name = None
        self.previous_map_name = None  # Track previous map to detect changes
        self.launch_options = "-usebsp"
        
        # UI state
        self.vmf_path_display = "None selected"
        self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)    # Red
        
        # Custom title bar drag state
        self.dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Import completion popup
        self.show_done_popup = False
        
        # Import state tracking
        self.import_in_progress = False
        self.import_completed = False
        self.progress_spinner = 0.0  # For animated progress indicator
        
        # Progress tracking
        self.total_materials = 0
        self.imported_materials = 0
        self.total_models = 0
        self.imported_models = 0
        self.total_vmaps = 0
        self.imported_vmaps = 0
        self.vmap_done = False
        self.current_stage = ""  # Current import stage description
        self.total_compiled_assets = 0
        self.compiled_assets = 0
        self.current_compiling_asset = ""
        
        # Failed asset tracking
        self.failed_materials = []
        self.failed_models = []
        self.failed_count = 0
        
        # Console output
        self.console_output = []
        self.bspsrc_output = []  # Separate storage for BSPSrc extraction output
        self.in_bspsrc_extraction = False  # Flag to track if we're doing BSPSrc extraction
        self.last_console_line_count = 0  # Track for auto-scroll
        
        # Prerequisites visibility (closed by default)
        self.show_guide = False
        self.prerequisites_height = 0  # Track prerequisites section height
        
        # Window dimensions
        self.base_window_height = 280  # Base height for main UI (increased to add space under GO button)
        self.helper_text_height = 50  # Height added when BSP is selected (for helper text)
        self.progress_tracking_height = 110  # Height added when showing progress tracking
        self.completed_height = 80  # Height added when import completes (for failed assets section if needed)
        self.prerequisites_expanded_height = 270  # Height for prerequisites section (increased to prevent GO button cutoff)
        
        # Cursor state
        self.text_input_hovered = False
        self.link_hovered = False  # Track when hovering over clickable links
        
        # Font reload tracking
        self._last_theme_for_font = None
        self._needs_font_reload = False
        
        # Button icons (texture IDs will be loaded here)
        self.button_icons = {}
        
        # Override print for this instance
        self._original_print = print
        
        # Load saved config
        self.load_from_cfg()
        
        # Auto-detect CS2 path
        self.auto_detect_cs2()
    
    def log(self, message):
        """Add message to console output and parse for progress tracking"""
        msg = str(message)
        self.console_output.append(msg)
        
        # Also store BSPSrc extraction output separately
        if self.in_bspsrc_extraction:
            self.bspsrc_output.append(msg)
        
        print(message)  # Also print to actual console
        
        # Parse message for progress tracking
        msg = str(message)
        import re  # Import re at the top for all pattern matching
        
        # Track total materials found
        if "unique material references in VMF" in msg:
            match = re.search(r'Found (\d+) unique material references', msg)
            if match:
                self.total_materials = int(match.group(1))
                self.current_stage = "Importing materials..."
        
        # Track material imports (including failed count)
        elif "Imported" in msg and "materials" in msg:
            match = re.search(r'Imported (\d+) materials', msg)
            if match:
                self.imported_materials = int(match.group(1))
            # Parse failed count from final summary
            if "failed" in msg:
                failed_match = re.search(r'(\d+) failed', msg)
                if failed_match:
                    self.failed_count += int(failed_match.group(1))
        
        # Track failed material imports
        elif "Failed to import material" in msg or "Warning: Material import command failed" in msg:
            # Try to extract material name from the message
            material_match = re.search(r'material ([^\s:]+)', msg)
            if material_match:
                material_name = material_match.group(1)
                if material_name not in self.failed_materials:
                    self.failed_materials.append(material_name)
        
        # Track total models found
        elif "unique model references in VMF" in msg:
            match = re.search(r'Found (\d+) unique model references', msg)
            if match:
                self.total_models = int(match.group(1))
                self.current_stage = "Importing models..."
        
        # Track model imports (including failed count)
        elif "Imported" in msg and "models" in msg:
            match = re.search(r'Imported (\d+) models', msg)
            if match:
                self.imported_models = int(match.group(1))
            # Parse skipped/failed count from summary
            if "skipped/failed" in msg:
                failed_match = re.search(r'(\d+) skipped/failed', msg)
                if failed_match:
                    self.failed_count += int(failed_match.group(1))
        
        # Track VMF import stages
        elif "Starting VMF import" in msg:
            self.current_stage = "Converting VMF to VMAP..."
        # Skip compilation tracking - we're no longer compiling assets
        # elif "Running Command: resourcecompiler" in msg:
        #     self.current_stage = "Compiling assets..."
        #     self.current_compiling_asset = ""
        # elif re.match(r"\s*\+- .*(\.vmat|\.vtex|\.vmdl)", msg):
        #     self.compiled_assets += 1
        #     asset_match = re.search(r"\+- (.*)", msg)
        #     if asset_match:
        #         self.current_compiling_asset = asset_match.group(1)
        # elif re.match(r"\s*OK: ", msg):
        #     self.current_compiling_asset = ""
        # elif "Successfully compiled" in msg and "imported materials" in msg:
        #     self.current_stage = "Compiling materials..."
        # elif "Compiled" in msg and "model materials" in msg:
        #     self.current_stage = "Compiling model materials..."
        # elif "Compiling" in msg and "imported models" in msg:
        #     self.current_stage = "Compiling models..."
        # elif "Finished compiling models from pak01" in msg:
        #     self.current_stage = "Finalizing models..."
        elif "Skipping" in msg and "compilation" in msg:
            self.current_stage = "Finishing up..."
        elif "Found" in msg and "VMAP files to move" in msg:
            import re
            match = re.search(r'Found (\d+) VMAP files', msg)
            if match:
                self.total_vmaps = int(match.group(1))
                self.imported_vmaps = 0  # Reset counter
                self.current_stage = "Moving VMAP files..."
        elif "Found" in msg and "prefab VMAP file" in msg:
            # Track prefab VMAP files separately and add to total
            import re
            match = re.search(r'Found (\d+) prefab VMAP', msg)
            if match:
                prefab_count = int(match.group(1))
                self.total_vmaps += prefab_count
                self.current_stage = "Processing VMAP files..."
        elif "-> Moved" in msg and ".vmap" in msg:
            # Count main VMAP files being moved
            self.imported_vmaps += 1
        elif "-> Found" in msg and ".vmap" in msg and "already in maps folder" in msg:
            # Count main VMAP that was already in maps folder
            self.imported_vmaps += 1
        elif msg.strip().startswith("-> ") and ".vmap" in msg and "Moved" not in msg and "Found" not in msg:
            # Count prefab VMAP listings (they use "  -> filename.vmap" format without "Moved" or "Found")
            self.imported_vmaps += 1
        elif "Successfully imported VMF to VMAP" in msg:
            self.vmap_done = True
            # Don't change stage here, let the VMAP counting messages handle it
        elif "VMF import process completed" in msg:
            self.current_stage = "Finalizing import..."
        elif "Import complete!" in msg:
            self.current_stage = "Complete!"
    
    def copy_to_clipboard(self, text):
        """Copy text to clipboard using tkinter"""
        try:
            root = tk.Tk()
            root.withdraw()  # Hide the window
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()  # Required to make clipboard persist
            root.destroy()
            self.log("✓ Console output copied to clipboard")
        except Exception as e:
            self.log(f"Error copying to clipboard: {e}")
    
    def open_log_file(self):
        """Save console output to log file and open it"""
        try:
            # Get logs folder path
            temp_folder = os.path.join(tempfile.gettempdir(), ".CS2KZ-mapping-tools")
            logs_folder = os.path.join(temp_folder, "logs")
            os.makedirs(logs_folder, exist_ok=True)
            
            # Create log filename with timestamp
            import datetime
            import glob
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"cs2_import_log_{timestamp}.txt"
            log_path = os.path.join(logs_folder, log_filename)
            
            # Clean up old logs - keep only 5 most recent
            existing_logs = sorted(glob.glob(os.path.join(logs_folder, "cs2_import_log_*.txt")))
            if len(existing_logs) >= 5:
                # Remove oldest logs to keep only 4 (so with the new one we'll have 5)
                for old_log in existing_logs[:-4]:
                    try:
                        os.remove(old_log)
                    except Exception:
                        pass  # Ignore errors removing old logs
            
            # Write console output to file
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("CS2 Map Import Log\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                
                # Write BSPSrc extraction section (if any)
                if self.bspsrc_output:
                    f.write("BSP EXTRACTION\n")
                    f.write("-" * 80 + "\n")
                    for line in self.bspsrc_output:
                        f.write(line + "\n")
                    f.write("\n")
                
                # Write import summary
                f.write("IMPORT SUMMARY\n")
                f.write("-" * 80 + "\n")
                f.write(f"Materials: {self.imported_materials}/{self.total_materials}\n")
                f.write(f"Models: {self.imported_models}/{self.total_models}\n")
                f.write(f"VMAP: {'Complete' if self.vmap_done else 'Incomplete'}\n")
                f.write(f"Failed Assets: {self.failed_count}\n")
                f.write("\n")
                
                # Write failed assets if any
                if self.failed_materials or self.failed_models:
                    f.write("FAILED ASSETS\n")
                    f.write("-" * 80 + "\n")
                    if self.failed_materials:
                        f.write(f"Failed Materials ({len(self.failed_materials)}):\n")
                        for material in self.failed_materials:
                            f.write(f"  - {material}\n")
                        f.write("\n")
                    if self.failed_models:
                        f.write(f"Failed Models ({len(self.failed_models)}):\n")
                        for model in self.failed_models:
                            f.write(f"  - {model}\n")
                        f.write("\n")
                
                # Write CS2 import output (all console output except BSPSrc)
                f.write("CS2 IMPORT OUTPUT\n")
                f.write("-" * 80 + "\n")
                for line in self.console_output:
                    # Skip BSPSrc lines (they're already written above)
                    if line not in self.bspsrc_output:
                        f.write(line + "\n")
            
            # Open the file with default text editor
            os.startfile(log_path)
            self.log(f"✓ Log saved to {log_path}")
            
        except Exception as e:
            self.log(f"Error opening log file: {e}")
    
    def open_addon_folder(self):
        """Open the addon folder in Windows Explorer"""
        try:
            if not self.csgo_basefolder:
                self.log("Error: CS2 path not detected")
                return
            
            if not self.addon:
                self.log("Error: Addon name not specified")
                return
            
            # Construct the content addon path
            # csgo_basefolder is like "C:/Program Files/Steam/steamapps/common/Counter-Strike Global Offensive"
            addon_path = os.path.join(self.csgo_basefolder, 'content', 'csgo_addons', self.addon)
            addon_path = addon_path.replace("/", "\\")
            
            if os.path.exists(addon_path):
                os.startfile(addon_path)
                self.log(f"✓ Opened addon folder: {addon_path}")
            else:
                self.log(f"Error: Addon folder not found at {addon_path}")
                
        except Exception as e:
            self.log(f"Error opening addon folder: {e}")
    
    def init_window(self):
        """Initialize GLFW window and ImGui"""
        if not glfw.init():
            print("Could not initialize OpenGL context")
            sys.exit(1)
        
        # Window hints
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)
        glfw.window_hint(glfw.DECORATED, glfw.FALSE)  # Remove window decorations for custom title bar
        
        # Create window with base height
        self.window = glfw.create_window(345, self.base_window_height, "CS2 Map Importer", None, None)
        if not self.window:
            glfw.terminate()
            print("Could not initialize Window")
            sys.exit(1)
        
        # Center window on screen
        monitor = glfw.get_primary_monitor()
        video_mode = glfw.get_video_mode(monitor)
        window_width = 360
        x_pos = (video_mode.size.width - window_width) // 2
        y_pos = (video_mode.size.height - self.base_window_height) // 2
        glfw.set_window_pos(self.window, x_pos, y_pos)
        
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)  # Enable vsync
        
        # Set window icon
        icon_path = resource_path(os.path.join("icons", "porting.ico"))
        if os.path.exists(icon_path):
            try:
                icon_img = Image.open(icon_path)
                if icon_img.mode != 'RGBA':
                    icon_img = icon_img.convert('RGBA')
                
                # Try to set window icon - GLFW format varies by version
                try:
                    # Try newer format with GLFWimage
                    from glfw import _GLFWimage
                    img_buffer = icon_img.tobytes()
                    img = _GLFWimage()
                    img.width = icon_img.width
                    img.height = icon_img.height
                    img.pixels = img_buffer
                    glfw.set_window_icon(self.window, 1, img)
                except:
                    # Try older list format
                    icon_data = icon_img.tobytes()
                    glfw.set_window_icon(self.window, 1, [[icon_img.width, icon_img.height, icon_data]])
            except Exception as e:
                # Silently fail - icon is nice to have but not critical
                pass
        
        # Create cursors for different UI elements
        self.hand_cursor = glfw.create_standard_cursor(glfw.HAND_CURSOR)
        self.arrow_cursor = glfw.create_standard_cursor(glfw.ARROW_CURSOR)
        self.ibeam_cursor = glfw.create_standard_cursor(glfw.IBEAM_CURSOR)
        
        # Setup ImGui
        imgui.create_context()
        
        # Disable imgui.ini file creation (we don't need to save window positions)
        io = imgui.get_io()
        io.ini_file_name = None  # Disable saving imgui.ini
        
        # Load font based on current theme
        current_theme = self.theme_manager.get_theme_name()
        self._last_theme_for_font = current_theme  # Initialize tracking
        
        # Always use Consolas font (Windows system font)
        consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
        if os.path.exists(consolas_path):
            io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
        else:
            # Fallback to Roboto if Consolas not found
            font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
            if os.path.exists(font_path):
                io.fonts.add_font_from_file_ttf(font_path, 13.0)
        
        self.impl = GlfwRenderer(self.window)
        
        # Setup style
        self.setup_style()
        
        # Load icons
        self.load_icons()
    
    def load_icons(self):
        """Load icons as OpenGL textures"""
        icons = {
            "title_icon": "porting.ico"
        }
        
        for name, filename in icons.items():
            path = resource_path(os.path.join("icons", filename))
            if os.path.exists(path):
                try:
                    img = Image.open(path)
                    # Ensure RGBA mode
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    # Use smaller size for title icon
                    img = img.resize((16, 16), Image.Resampling.LANCZOS)
                    width, height = img.size
                    img_data = img.tobytes()
                    
                    # Create OpenGL texture
                    texture = gl.glGenTextures(1)
                    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
                    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height,
                                   0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data)
                    
                    self.button_icons[name] = texture
                except Exception as e:
                    pass  # Silently fail
    
    def setup_style(self):
        """Configure ImGui visual style using theme manager"""
        style = imgui.get_style()
        io = imgui.get_io()
        
        # Check if theme changed and requires different font
        # Flag for reload but don't do it during frame rendering
        if hasattr(self, '_last_theme_for_font'):
            current_theme = self.theme_manager.get_theme_name()
            old_was_dracula = self._last_theme_for_font == 'dracula'
            new_is_dracula = current_theme == 'dracula'
            if old_was_dracula != new_is_dracula:
                self._needs_font_reload = True
        
        io.font_global_scale = 1.0
        
        # Get theme from theme manager
        theme = self.theme_manager.get_theme()
        
        imgui.style_colors_dark()
        # Apply theme colors
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = theme['window_bg']
        style.colors[imgui.COLOR_MENUBAR_BACKGROUND] = theme['title_bar_bg']
        style.colors[imgui.COLOR_BUTTON] = theme['button']
        style.colors[imgui.COLOR_BUTTON_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = theme['button_active']
        style.colors[imgui.COLOR_BORDER] = theme['border']
        style.colors[imgui.COLOR_TEXT] = theme['text']
        style.colors[imgui.COLOR_FRAME_BACKGROUND] = theme['title_bar_bg']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = theme['button_active']
        style.colors[imgui.COLOR_CHECK_MARK] = theme['accent']
        
        # Window rounding
        style.window_rounding = 0.0
        style.frame_rounding = 3.0
        style.grab_rounding = 3.0
        style.window_border_size = 1.0
        style.frame_border_size = 0.0
        style.window_padding = (10, 10)
        style.frame_padding = (8, 4)
        style.item_spacing = (8, 8)
    
    def get_steam_directory(self):
        """Get Steam installation directory from registry"""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
                return steam_path
        except FileNotFoundError:
            return None

    def find_cs2_library_path(self, libraryfolders_path):
        """Find CS2 library path from Steam library folders"""
        if not os.path.exists(libraryfolders_path):
            return None

        with open(libraryfolders_path, 'r', encoding='utf-8') as file:
            library_data = vdf.load(file)

        if 'libraryfolders' in library_data:
            for _, folder in library_data['libraryfolders'].items():
                if 'apps' in folder and '730' in folder['apps']:
                    return folder['path']
        return None

    def get_cs2_path(self):
        """Get CS2 installation path"""
        steam_path = self.get_steam_directory()
        if steam_path is None:
            return None
        library_path = self.find_cs2_library_path(os.path.join(steam_path, "steamapps", "libraryfolders.vdf"))
        if library_path is None:
            return None
        with open(os.path.join(library_path, 'steamapps', 'appmanifest_730.acf'), 'r', encoding='utf-8') as file:
            installdir = vdf.load(file)['AppState']['installdir']
            return os.path.join(library_path, 'steamapps', 'common', installdir)

    def auto_detect_cs2(self):
        """Automatically detect and set CS2 path"""
        try:
            cs2_path = self.get_cs2_path()
            if cs2_path:
                self.csgo_basefolder = cs2_path
                print(f"CS2 detected at: {cs2_path}")
        except Exception as e:
            print(f"Could not auto-detect CS2: {e}")

    def select_vmf(self):
        """Open file dialog to select BSP file and auto-extract"""
        # Make sure the main window doesn't block
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)  # Keep dialog on top
        root.update()  # Process events
        
        path = filedialog.askopenfilename(
            title="Select a BSP file to import",
            initialdir=self.vmf_default_path,
            filetypes=[("BSP files", "*.bsp"), ("All files", "*.*")],
            parent=root
        )
        root.destroy()
        
        if not path:
            return
        
        path = path.replace("\\", "/")
        bsp_filename = os.path.basename(path)
        new_map_name = os.path.splitext(bsp_filename)[0]
        
        # Update addon name if it's empty or matches the previous default
        if not self.addon or self.addon.strip() == "" or self.addon == self.previous_map_name:
            self.addon = new_map_name
        
        # Update tracking
        self.previous_map_name = new_map_name
        self.map_name = new_map_name
        
        # Auto-extract BSP using BSPSource
        if not self.extract_bsp(path):
            self.log("Failed to extract BSP file")
            self.vmf_path_display = "Extraction failed"
            self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)
            return
        
        # Set VMF path to the extracted location in sdk_content/maps folder
        # BSPSource creates VMF with same name as BSP (no suffix)
        if self.csgo_basefolder:
            sdk_content_folder = os.path.join(self.csgo_basefolder.replace("/", "\\"), "sdk_content")
            sdk_content_maps_folder = os.path.join(sdk_content_folder, "maps")
            vmf_path = os.path.join(sdk_content_maps_folder, f"{self.map_name}.vmf")
            
            if os.path.exists(vmf_path):
                # Store sdk_content path (import script will add \maps itself)
                self.vmf_folder = sdk_content_folder.replace("\\", "/")
                self.vmf_path_display = f"{self.map_name}.vmf (decompiled)"
                self.vmf_status_color = (0.0, 1.0, 0.0, 1.0)
                self.vmf_default_path = os.path.dirname(path)
            else:
                self.log(f"VMF not found at: {vmf_path}")
                self.vmf_path_display = "VMF not found after extraction"
                self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)
        else:
            self.log("CS:GO folder not detected")
            self.vmf_path_display = "CS:GO folder not found"
            self.vmf_status_color = (1.0, 0.0, 0.0, 1.0)
    
    def fix_vmf_structure(self, vmf_path):
        """Add proper VMF header structure for CS2 importer compatibility and fix tool textures"""
        try:
            # Read the VMF file
            with open(vmf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Fix tool textures that BSPSource incorrectly converts
            # BSPSource often converts nodraw faces to playerclip/skip/hint/etc based on brush properties
            # But for CS2 import, we want to preserve nodraw on void-facing faces
            # Note: The actual void face culling happens in VBSP with -usebsp flag
            import re
            
            # Count replacements for logging
            replacements = {
                'TOOLS/TOOLSPLAYERCLIP': 0,
                'TOOLS/TOOLSSKIP': 0,
                'TOOLS/TOOLSHINT': 0,
                'TOOLS/TOOLSTRIGGER': 0,
                'TOOLS/TOOLSBLOCKLIGHT': 0,
                'TOOLS/TOOLSBLOCKBULLETS': 0,
                'TOOLS/TOOLSINVISIBLE': 0,
                'TOOLS/TOOLSCLIP': 0
            }
            
            # Replace tool textures that should be nodraw for proper void culling
            # Keep these as-is - VBSP will handle optimization with -usebsp flag
            # Actually, don't replace them - let VBSP handle it with the original BSP
            # The issue is BSPSource guessing wrong, but VBSP with -usebsp uses original BSP geo
            
            # Check if it already has versioninfo (Hammer-formatted VMF)
            if 'versioninfo' in content.lower():
                self.log("VMF already has proper structure")
                return
            
            # Add proper VMF header
            vmf_header = '''versioninfo
{
\t"editorversion" "400"
\t"editorbuild" "8997"
\t"mapversion" "1"
\t"formatversion" "100"
\t"prefab" "0"
}
visgroups
{
}
viewsettings
{
\t"bSnapToGrid" "1"
\t"bShowGrid" "1"
\t"bShowLogicalGrid" "0"
\t"nGridSpacing" "64"
}
'''
            # Prepend header to existing content
            new_content = vmf_header + content
            
            # Write back
            with open(vmf_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.log("✓ Fixed VMF structure for CS2 compatibility")
            
        except Exception as e:
            self.log(f"Warning: Could not fix VMF structure: {e}")
    
    def extract_bsp(self, bsp_path):
        """Extract BSP file using BSPSource"""
        try:
            # Mark that we're starting BSPSrc extraction
            self.in_bspsrc_extraction = True
            
            if not self.csgo_basefolder:
                self.log("CS:GO folder not set")
                return False
            
            # Check/download BSPSource to temp folder in .cs2kz-mapping-tools
            cs2kz_temp = os.path.join(tempfile.gettempdir(), ".cs2kz-mapping-tools")
            os.makedirs(cs2kz_temp, exist_ok=True)
            bspsrc_dir = os.path.join(cs2kz_temp, "bspsrc")
            bspsrc_bat = os.path.join(bspsrc_dir, "bspsrc.bat")
            
            if not os.path.exists(bspsrc_bat):
                self.log("Downloading BSPSource...")
                try:
                    # Download latest BSPSource Windows release
                    bspsrc_url = "https://github.com/ata4/bspsrc/releases/download/v1.4.7/bspsrc-windows.zip"
                    
                    # Download zip to memory
                    response = urllib.request.urlopen(bspsrc_url)
                    zip_data = io.BytesIO(response.read())
                    
                    # Extract zip to temp folder
                    os.makedirs(bspsrc_dir, exist_ok=True)
                    with zipfile.ZipFile(zip_data) as zip_ref:
                        zip_ref.extractall(bspsrc_dir)
                    
                    self.log("BSPSource downloaded and extracted successfully")
                except Exception as e:
                    self.log(f"Failed to download BSPSource: {e}")
                    return False
            

            # Create a unique temporary directory for BSPSource output
            # Using mkdtemp ensures a unique, safe directory that doesn't conflict
            # Place it in .cs2kz-mapping-tools subfolder for organization
            cs2kz_temp = os.path.join(tempfile.gettempdir(), ".cs2kz-mapping-tools")
            os.makedirs(cs2kz_temp, exist_ok=True)
            temp_output_dir = tempfile.mkdtemp(prefix="bspsrc_output_", dir=cs2kz_temp)
            
            # BSPSource needs the FULL VMF OUTPUT PATH, not just directory
            map_base_name = os.path.splitext(os.path.basename(bsp_path))[0]
            temp_vmf = os.path.join(temp_output_dir, f"{map_base_name}.vmf")
            
            self.log(f"Using temp directory: {temp_output_dir}")
            self.log(f"Target VMF: {temp_vmf}")

            # Ensure csgo directory exists
            base_dir = self.csgo_basefolder.replace("/", "\\")
            csgo_dir = os.path.join(base_dir, "csgo")
            os.makedirs(csgo_dir, exist_ok=True)


            self.log(f"Extracting {os.path.basename(bsp_path)}...")
            
            # Call Java directly instead of batch file for better control
            java_exe = os.path.join(bspsrc_dir, "bin", "java.exe")
            
            # Normalize paths for Windows - ensure backslashes
            temp_vmf_normalized = temp_vmf.replace("/", "\\")
            bsp_path_normalized = bsp_path.replace("/", "\\")
            
            command = [
                java_exe,
                "-m", "info.ata4.bspsrc.app/info.ata4.bspsrc.app.src.cli.BspSourceCli",
                "--unpack_embedded",  # Extract embedded files (materials, models, sounds, etc.)
                "--no_ttfix",  # Don't "fix" tool textures - preserve original toolsnodraw etc.
                "-o", temp_vmf_normalized,
                bsp_path_normalized
            ]
            self.log(f"Running command: {' '.join(command)}")
            self.log(f"Working directory: {bspsrc_dir}")
            # Use Popen to capture output
            process = subprocess.Popen(
                command,
                cwd=bspsrc_dir,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Read output line by line
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log(line)
            
            process.wait(timeout=120)
            
            self.log(f"Process finished with return code: {process.returncode}")

            # Check what BSPSource actually extracted
            self.log(f"Checking temp directory contents: {temp_output_dir}")
            if os.path.exists(temp_output_dir):
                for item in os.listdir(temp_output_dir):
                    item_path = os.path.join(temp_output_dir, item)
                    if os.path.isdir(item_path):
                        self.log(f"  Found folder: {item}/")
                        # Show contents of folders
                        for subitem in os.listdir(item_path):
                            self.log(f"    - {subitem}")
                    else:
                        self.log(f"  Found file: {item}")

            # Check for output files regardless of return code (BSPSource may return non-zero but still extract)
            if True:  # Always check for extracted files
                # BSPSource extracts files to temp_output_dir/mapname/ folder
                map_base_name = os.path.splitext(os.path.basename(bsp_path))[0]
                extracted_folder = os.path.join(temp_output_dir, map_base_name)
                
                # Check if files were extracted to mapname subfolder (BSPSource behavior)
                if os.path.exists(extracted_folder):
                    temp_maps = os.path.join(extracted_folder, "maps")
                    temp_materials = os.path.join(extracted_folder, "materials")
                else:
                    # Fallback to root temp directory
                    temp_maps = os.path.join(temp_output_dir, "maps")
                    temp_materials = os.path.join(temp_output_dir, "materials")
                
                csgo_maps = os.path.join(csgo_dir, "maps")
                csgo_materials = os.path.join(csgo_dir, "materials")
                
                # Use sdk_content/maps for VMF (where CS:GO Hammer expects it and where importer will look)
                sdk_content_maps = os.path.join(base_dir, "sdk_content", "maps")
                
                # VMF file goes to sdk_content/maps only
                sdk_vmf = os.path.join(sdk_content_maps, os.path.basename(temp_vmf))
                
                # Move VMF file to sdk_content/maps
                if os.path.exists(temp_vmf):
                    # Create directory
                    os.makedirs(sdk_content_maps, exist_ok=True)
                    
                    # Copy to sdk_content/maps
                    shutil.copy2(temp_vmf, sdk_vmf)
                    self.log(f"Copied {os.path.basename(temp_vmf)} to sdk_content/maps/")
                    
                    # Fix VMF structure for CS2 importer compatibility
                    self.fix_vmf_structure(sdk_vmf)
                
                # Move maps folder contents (nav files, bsp files, but NOT vmf)
                if os.path.exists(temp_maps):
                    os.makedirs(csgo_maps, exist_ok=True)
                    os.makedirs(sdk_content_maps, exist_ok=True)
                    for item in os.listdir(temp_maps):
                        src = os.path.join(temp_maps, item)
                        dst_csgo = os.path.join(csgo_maps, item)
                        dst_sdk = os.path.join(sdk_content_maps, item)
                        if os.path.isfile(src):
                            # Skip VMF files - they should only be in sdk_content/maps
                            if item.endswith('.vmf'):
                                continue
                            # Copy NAV files to csgo/maps
                            shutil.copy2(src, dst_csgo)
                            # Also copy BSP and NAV files to sdk_content/maps
                            if item.endswith(('.bsp', '.nav')):
                                shutil.copy2(src, dst_sdk)
                            self.log(f"Copied {item} to csgo/maps/")
                
                # Move models folder contents (embedded custom models)
                temp_models = os.path.join(extracted_folder, "models") if os.path.exists(extracted_folder) else os.path.join(temp_output_dir, "models")
                if os.path.exists(temp_models):
                    self.log("Extracting embedded models...")
                    csgo_models = os.path.join(csgo_dir, "models")
                    os.makedirs(csgo_models, exist_ok=True)
                    
                    # Also create models folder in content directory (maps/)
                    csgo_maps_models = os.path.join(csgo_maps, "models")
                    os.makedirs(csgo_maps_models, exist_ok=True)
                    
                    model_count = 0
                    for root, dirs, files in os.walk(temp_models):
                        rel_path = os.path.relpath(root, temp_models)
                        dst_dir_game = os.path.join(csgo_models, rel_path) if rel_path != "." else csgo_models
                        dst_dir_content = os.path.join(csgo_maps_models, rel_path) if rel_path != "." else csgo_maps_models
                        os.makedirs(dst_dir_game, exist_ok=True)
                        os.makedirs(dst_dir_content, exist_ok=True)
                        for file in files:
                            src = os.path.join(root, file)
                            # Copy to both game and content directories
                            dst_game = os.path.join(dst_dir_game, file)
                            dst_content = os.path.join(dst_dir_content, file)
                            shutil.copy2(src, dst_game)
                            shutil.copy2(src, dst_content)
                            model_count += 1
                            # Log relative path to show model structure
                            rel_file = os.path.join(rel_path, file) if rel_path != "." else file
                            self.log(f"  Copied model: {rel_file}")
                    
                    self.log(f"✓ Extracted {model_count} model files")
                else:
                    self.log("⚠ No embedded models found in BSP")
                
                # Move materials folder contents  
                # Copy to BOTH game dir (csgo/materials/) AND content dir (csgo/maps/materials/)
                # for source1import to find them
                if os.path.exists(temp_materials):
                    self.log("Extracting embedded materials...")
                    os.makedirs(csgo_materials, exist_ok=True)
                    
                    # Also create materials folder in content directory (maps/)
                    csgo_maps_materials = os.path.join(csgo_maps, "materials")
                    os.makedirs(csgo_maps_materials, exist_ok=True)
                    
                    material_count = 0
                    extracted_vmts = []  # Track VMT files for refs list
                    for root, dirs, files in os.walk(temp_materials):
                        rel_path = os.path.relpath(root, temp_materials)
                        dst_dir_game = os.path.join(csgo_materials, rel_path) if rel_path != "." else csgo_materials
                        dst_dir_content = os.path.join(csgo_maps_materials, rel_path) if rel_path != "." else csgo_maps_materials
                        os.makedirs(dst_dir_game, exist_ok=True)
                        os.makedirs(dst_dir_content, exist_ok=True)
                        for file in files:
                            src = os.path.join(root, file)
                            # Copy to both game and content directories
                            dst_game = os.path.join(dst_dir_game, file)
                            dst_content = os.path.join(dst_dir_content, file)
                            shutil.copy2(src, dst_game)
                            shutil.copy2(src, dst_content)
                            material_count += 1
                            # Log relative path to show material structure
                            rel_file = os.path.join(rel_path, file) if rel_path != "." else file
                            self.log(f"  Copied material: {rel_file}")
                            
                            # Track VMT files for creating refs list
                            if file.lower().endswith('.vmt'):
                                # Convert to material path (remove .vmt and use forward slashes)
                                mat_path = rel_file.replace('\\', '/').rsplit('.', 1)[0]
                                extracted_vmts.append(mat_path)
                    
                    self.log(f"✓ Extracted {material_count} material files")
                    
                    # Create _refs.txt file for the importer to process embedded materials
                    # Format must match source1import's expected KeyValues format
                    if extracted_vmts:
                        refs_file = os.path.join(csgo_maps, f"{map_base_name}_embedded_refs.txt")
                        with open(refs_file, 'w') as f:
                            f.write('importfilelist\n{\n')
                            for vmt in extracted_vmts:
                                # Use forward slashes and proper quoting like the example files
                                mat_path = vmt.replace('\\', '/')
                                f.write(f'\t"file" "materials/{mat_path}.vmt"\n')
                            f.write('}\n')
                        self.log(f"✓ Created refs file with {len(extracted_vmts)} embedded materials")
                else:
                    self.log("⚠ No embedded materials found in BSP")
                
                # Clean up temp folder
                try:
                    if os.path.exists(temp_output_dir):
                        shutil.rmtree(temp_output_dir)
                except Exception as e:
                    self.log(f"Warning: Could not clean up temp directory: {e}")
                
                # Copy the original BSP file to sdk_content/maps (where VMF is located)
                # This allows source1import to use it with -usebsp flag for optimized face culling
                # and keeps BSP alongside VMF for CS:GO Hammer convenience
                self.log(f"Copying original BSP file for optimized import...")
                try:
                    bsp_dest_sdk = os.path.join(sdk_content_maps, map_base_name + ".bsp")
                    if os.path.exists(bsp_dest_sdk):
                        os.remove(bsp_dest_sdk)
                    shutil.copy2(bsp_path, bsp_dest_sdk)
                    self.log(f"✓ Copied BSP file to: {bsp_dest_sdk}")
                except Exception as e:
                    self.log(f"⚠ Could not copy BSP file: {e}")
                    self.log("  Will compile VMF to BSP during import (may take longer)")
                
                # Check if VMF was successfully moved
                if os.path.exists(sdk_vmf):
                    self.log(f"✓ VMF found at: {sdk_vmf}")
                    self.log("✓ Extraction completed successfully")
                    self.in_bspsrc_extraction = False  # End BSPSrc extraction tracking
                    return True
                else:
                    # Check if embedded files were at least extracted
                    if os.path.exists(csgo_materials) and os.listdir(csgo_materials):
                        self.log("⚠ Embedded files extracted, but VMF decompilation failed")
                        self.log("⚠ This BSP may be protected or corrupted")
                        self.log("⚠ Try downloading a different version of this map from:")
                        self.log("   https://files.femboy.kz/fastdl/csgo/maps/")
                    else:
                        self.log("✗ VMF not found. BSP may be corrupt or CS2 format.")
                        self.log("✗ Note: This tool only works with CS:GO/Source 1 BSP files.")
                    self.in_bspsrc_extraction = False  # End BSPSrc extraction tracking
                    return False
                
        except subprocess.TimeoutExpired:
            self.log("Extraction timed out (took more than 2 minutes)")
            self.in_bspsrc_extraction = False  # End BSPSrc extraction tracking
            return False
        except Exception as e:
            self.log(f"Error during extraction: {e}")
            self.in_bspsrc_extraction = False  # End BSPSrc extraction tracking
            return False
        
        # Save the folder path for next time
        self.vmf_default_path = self.vmf_folder

        # if path doesn't end with /maps
        if not self.vmf_folder.endswith("/maps"):
            temp_dir = tempfile.gettempdir()

            # check if /maps is in temp already, otherwise create it
            if not os.path.exists(temp_dir + "/maps"):
                os.mkdir(temp_dir + "/maps")
            
            # delete vmf in /maps if exists, as maybe it isn't the newest ver. 
            else:
                if os.path.isfile(temp_dir + "/maps/" + self.map_name + ".vmf"):
                    os.remove(temp_dir + "/maps/" + self.map_name + ".vmf")

            # copy *.vmf to temp/maps/*.vmf
            shutil.copy(self.vmf_folder + "/" + self.map_name + ".vmf", temp_dir + "/maps")
            
            self.vmf_folder_to_save = self.vmf_folder
            self.vmf_folder = temp_dir

        else:
            self.vmf_folder = "/".join(self.vmf_folder.split("/")[:-1])
            self.vmf_folder_to_save = self.vmf_folder

        # update UI
        self.vmf_path_display = path
        self.vmf_status_color = (0.0, 1.0, 0.0, 1.0)  # Green

    def save_to_cfg(self):
        """Save configuration to file"""
        config_path = os.path.join(os.path.dirname(__file__), "cs2importer.cfg")
        default_path = self.vmf_default_path if self.vmf_default_path else 'C:\\'
        temp = f"""{self.launch_options}
{self.csgo_basefolder if self.csgo_basefolder else ''}
{default_path}"""
        
        with open(config_path, "w") as f:
            f.write(temp)

    def load_from_cfg(self):
        """Load configuration from file"""
        config_path = os.path.join(os.path.dirname(__file__), "cs2importer.cfg")
        
        if not os.path.isfile(config_path):
            return

        try:
            with open(config_path, "r") as f:
                temp = f.readlines()
                if not temp:
                    return

            if len(temp) > 0:
                self.launch_options = temp[0].strip()
            if len(temp) > 1 and temp[1].strip():
                self.set_csgo_folder(temp[1].strip())
            if len(temp) > 2 and temp[2].strip():
                self.vmf_default_path = temp[2].strip()
        except:
            pass

    def go(self):
        """Execute the import process"""
        try:
            if not self.csgo_basefolder:
                self.log("Error: CS:GO folder not detected")
                return
            
            if not self.vmf_folder or not self.map_name:
                self.log("Error: VMF file not selected")
                return
            
            if not self.addon:
                self.log("Error: Addon name not specified")
                return
            
            # Set import state
            self.import_in_progress = True
            self.import_completed = False
            self.console_output = []  # Clear previous output
            
            # Reset progress tracking
            self.total_materials = 0
            self.imported_materials = 0
            self.total_models = 0
            self.imported_models = 0
            self.total_vmaps = 0
            self.imported_vmaps = 0
            self.vmap_done = False
            self.current_stage = "Starting import..."
            self.failed_materials = []
            self.failed_models = []
            self.failed_count = 0
            self.total_compiled_assets = 0
            self.compiled_assets = 0
            self.current_compiling_asset = ""
            
            self.save_to_cfg()

            # Clean up any VMF files from csgo/maps to avoid conflicts
            # VMF files should only exist in sdk_content/maps
            csgo_maps_dir = os.path.join(self.csgo_basefolder, 'csgo', 'maps')
            if os.path.exists(csgo_maps_dir):
                vmf_in_csgo = os.path.join(csgo_maps_dir, self.map_name + '.vmf')
                if os.path.exists(vmf_in_csgo):
                    try:
                        os.remove(vmf_in_csgo)
                        self.log(f"Removed conflicting VMF from csgo/maps/")
                    except Exception as e:
                        self.log(f"Warning: Could not remove VMF from csgo/maps: {e}")

            cd = os.path.join(self.csgo_basefolder, 'game', 'csgo', 'import_scripts').replace("/", "\\")
            
            # Get the path to our custom import script using resource_path for PyInstaller compatibility
            jakke_script = resource_path(os.path.join('scripts', 'porting', 'import_map_community_jakke.py')).replace("/", "\\")
            
            # Build command using our custom script with unbuffered output
            # Pass sdk_content as the content directory (where VMF and BSP are located)
            sdk_content_dir = os.path.join(self.csgo_basefolder, 'sdk_content').replace("/", "\\")
            
            # Try to find bundled Python first (has required packages), fall back to system Python
            bundled_python = resource_path(os.path.join('python-embed', 'python.exe'))
            if os.path.exists(bundled_python):
                python_exe = bundled_python
                self.log(f"Using bundled Python: {python_exe}")
            else:
                # Fall back to system Python
                python_exe = shutil.which('python') or shutil.which('python3')
                if python_exe and os.path.exists(python_exe):
                    self.log(f"Using system Python: {python_exe}")
                else:
                    self.log("ERROR: Python not found!")
                    self.log("Please install Python 3.11+ from python.org")
                    self.log("Download: https://www.python.org/downloads/")
                    self.import_in_progress = False
                    return
            
            command = f'"{python_exe}" -u "{jakke_script}" '
            command += '"' + os.path.join(self.csgo_basefolder, 'csgo').replace("/", "\\") + '" '
            command += '"' + sdk_content_dir + '" '
            command += '"' + os.path.join(self.csgo_basefolder, 'game', 'csgo').replace("/", "\\") + '" '
            command += self.addon + ' '
            command += self.map_name + ' '
            command += self.launch_options
            
            self.log("Starting import process...")
            
            # Run the process without stdin/stdout pipes - let it run directly
            # Use unbuffered Python output
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            
            process = subprocess.Popen(
                command, 
                cwd=cd, 
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=0,  # Unbuffered
                env=env
            )
            
            # Read output and wait for process in a background thread
            import threading
            def run_process():
                try:
                    while True:
                        line = process.stdout.readline()
                        if not line:
                            break
                        line = line.rstrip()
                        if line:
                            self.log(line)
                    
                    # Wait for process to complete
                    process.wait()
                    self.log("Import process completed.")
                    
                    # Update import state
                    self.import_in_progress = False
                    self.import_completed = True
                    
                    # Show done popup
                    self.show_done_popup = True
                    
                except Exception as e:
                    self.log(f"Process error: {e}")
                    self.import_in_progress = False
            
            process_thread = threading.Thread(target=run_process, daemon=True)
            process_thread.start()
            
            # Don't wait here - let the GUI remain responsive

        except Exception as e:
            self.log(f"Error: {e}")
            # Update import state on error
            self.import_in_progress = False
            self.import_completed = True
            # Restore files even if there's an error
            try:
                self.restore_files()
            except:
                pass

    def render_custom_title_bar(self):
        """Render custom title bar with minimize and close buttons"""
        window_width, _ = glfw.get_window_size(self.window)
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(window_width, CUSTOM_TITLE_BAR_HEIGHT)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        
        # Title bar background color from theme (slightly darker than window background)
        theme = self.theme_manager.get_theme()
        r, g, b, a = theme['window_bg']
        title_bg = (r * 0.8, g * 0.8, b * 0.8, a)
        imgui.push_style_color(imgui.COLOR_WINDOW_BACKGROUND, *title_bg)
        
        flags = (
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_SCROLLBAR
        )
        
        imgui.begin("##titlebar", flags=flags)
        
        # Draw icon if available
        if "title_icon" in self.button_icons:
            imgui.image(self.button_icons["title_icon"], 16, 16)
            imgui.same_line(spacing=4)
        
        # Title text
        imgui.text("CS2 Map Importer")
        
        # Get the position for the buttons (right side)
        button_size = 20
        button_spacing = 4
        total_button_width = (button_size * 2) + button_spacing
        
        imgui.same_line(window_width - total_button_width - 6)
        
        # VS Code style buttons
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 0.0)
        
        # Minimize button
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.2, 0.2, 0.2, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)
        
        minimize_clicked = imgui.button("##minimize", width=button_size, height=button_size)
        
        # Draw minimize symbol
        min_button_min = imgui.get_item_rect_min()
        draw_list = imgui.get_window_draw_list()
        line_width = 8
        line_height = 1
        line_x = min_button_min.x + (button_size - line_width) // 2
        line_y = min_button_min.y + (button_size - line_height) // 2
        text_color = imgui.get_color_u32_rgba(0.8, 0.8, 0.8, 1.0)
        draw_list.add_rect_filled(line_x, line_y, line_x + line_width, line_y + line_height + 1, text_color)
        
        imgui.pop_style_color(4)
        
        if minimize_clicked:
            glfw.iconify_window(self.window)
        
        imgui.same_line(spacing=button_spacing)
        
        # Close button (red hover)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.9, 0.2, 0.2, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.8, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)
        
        close_clicked = imgui.button("##close", width=button_size, height=button_size)
        
        # Draw X symbol
        close_button_min = imgui.get_item_rect_min()
        center_x = close_button_min.x + button_size // 2
        center_y = close_button_min.y + button_size // 2
        x_size = 6
        draw_list.add_line(
            center_x - x_size // 2, center_y - x_size // 2,
            center_x + x_size // 2, center_y + x_size // 2,
            text_color, 1.5
        )
        draw_list.add_line(
            center_x + x_size // 2, center_y - x_size // 2,
            center_x - x_size // 2, center_y + x_size // 2,
            text_color, 1.5
        )
        
        imgui.pop_style_color(4)
        
        if close_clicked:
            glfw.set_window_should_close(self.window, True)
        
        imgui.pop_style_var(1)
        
        # Handle window dragging from title bar
        if imgui.is_window_hovered() and imgui.is_mouse_clicked(0):
            mouse_pos = imgui.get_mouse_pos()
            if mouse_pos.x < window_width - total_button_width - 15:
                window_pos = glfw.get_window_pos(self.window)
                self.dragging_window = True
                # Store the offset from window position to cursor
                cursor_pos = glfw.get_cursor_pos(self.window)
                self.drag_offset_x = cursor_pos[0]
                self.drag_offset_y = cursor_pos[1]
        
        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(3)

    def render(self):
        """Render the ImGui interface"""
        # Check for theme updates
        if self.theme_manager.check_for_updates():
            self.setup_style()
        
        # Render custom title bar first
        self.render_custom_title_bar()
        
        window_width, window_height = glfw.get_window_size(self.window)
        imgui.set_next_window_position(0, CUSTOM_TITLE_BAR_HEIGHT)
        imgui.set_next_window_size(window_width, window_height - CUSTOM_TITLE_BAR_HEIGHT)
        
        imgui.begin(
            "CS2 Map Importer",
            flags=imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE | imgui.WINDOW_NO_MOVE | imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )
        
        # Content (remove duplicate title since it's in title bar now)
        imgui.spacing()
        
        # Read Before Import Section
        prerequisites_opened = imgui.collapsing_header("Read Before Import")[0]
        
        # Dynamically resize window based on prerequisites, progress tracking, and completed state
        current_height = self.base_window_height
        current_width = 240
        
        # Add height for helper text if BSP is selected
        if self.vmf_status_color == (0.0, 1.0, 0.0, 1.0):  # Green = success
            current_height += self.helper_text_height
        
        if prerequisites_opened:
            current_height += self.prerequisites_expanded_height
            current_width = 330  # Slightly wider for prerequisites text
        if self.import_in_progress:
            current_height += self.progress_tracking_height
            # Keep the same width as current state (prereqs open or closed)
            if not prerequisites_opened:
                current_width = 240  # Match normal width
            # else: keep 340 from prerequisites
        if self.import_completed:
            current_height += self.completed_height
            current_width = max(current_width, 275)  # Back to normal width when complete
        
        current_window_size = glfw.get_window_size(self.window)
        
        if current_window_size[0] != current_width or current_window_size[1] != current_height:
            glfw.set_window_size(self.window, current_width, current_height)
        
        if prerequisites_opened:
            imgui.push_text_wrap_pos(imgui.get_content_region_available_width())
            
            # Step 1
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 1.0, 1.0)  # White
            imgui.text_wrapped("1. Download the .bsp")
            imgui.pop_style_color()
            imgui.push_style_color(imgui.COLOR_TEXT, 0.8, 0.8, 0.8, 1.0)
            imgui.text_wrapped("Example from FKZ database:")
            imgui.pop_style_color()
            
            # FKZ link - clickable
            fkz_url = "https://files.femboy.kz/fastdl/csgo/maps/"
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.8, 1.0, 1.0)
            if imgui.selectable(fkz_url, False)[0]:
                webbrowser.open(fkz_url)
            imgui.pop_style_color()
            
            imgui.spacing()
            
            # Step 2
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 1.0, 1.0)  # White
            imgui.text_wrapped("2. Select the .bsp (stuff will decompile)")
            imgui.pop_style_color()
            imgui.push_style_color(imgui.COLOR_TEXT, 0.8, 0.8, 0.8, 1.0)
            imgui.text_wrapped("- IF your map has displacements go ahead and open the .vmf in CSGO hammer and save it")
            imgui.text_wrapped("- The .vmf is decompiled to \"sdk_content/maps\"")
            imgui.pop_style_color()
            
            imgui.spacing()
            
            # Step 3
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 1.0, 1.0)  # White
            imgui.text_wrapped("3. Choose a new Addon Name")
            imgui.pop_style_color()
            
            imgui.spacing()
            
            # Step 4
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 1.0, 1.0, 1.0)  # White
            imgui.text_wrapped("4. GO!")
            imgui.pop_style_color()
            
            imgui.pop_text_wrap_pos()
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
        
        # BSP File Selection
        imgui.text("BSP File:")
        if imgui.button("Select BSP File", width=200):
            self.select_vmf()
        
        # Display VMF path below button with smaller text
        imgui.push_style_color(imgui.COLOR_TEXT, *self.vmf_status_color)
        imgui.set_window_font_scale(1)  # Make text smaller
        imgui.text_wrapped(self.vmf_path_display)
        imgui.set_window_font_scale(1.0)  # Reset font scale
        imgui.pop_style_color()
        
        # Show helper text if VMF was successfully extracted
        if self.vmf_status_color == (0.0, 1.0, 0.0, 1.0):  # Green = success
            imgui.set_window_font_scale(0.9)
            
            # First line - gray, non-clickable text
            imgui.push_style_color(imgui.COLOR_TEXT, 0.7, 0.7, 0.7, 1.0)  # Gray
            imgui.text("If map has displacements, open it")
            imgui.pop_style_color()
            
            # Second line - blue clickable text
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.8, 1.0, 1.0)  # Blue
            imgui.push_style_color(imgui.COLOR_HEADER, 0.0, 0.0, 0.0, 0.0)  # Transparent background
            imgui.push_style_color(imgui.COLOR_HEADER_HOVERED, 0.2, 0.4, 0.6, 0.3)  # Slight highlight on hover
            
            clicked = imgui.selectable("in CS:GO Hammer and save it", False)[0]
            hovered = imgui.is_item_hovered()
            
            if clicked:
                # Open SDK Launcher
                if self.csgo_basefolder:
                    sdk_launcher = os.path.join(self.csgo_basefolder, "bin", "sdklauncher.exe")
                    if os.path.exists(sdk_launcher):
                        try:
                            os.startfile(sdk_launcher)
                            self.log("✓ Opened CS:GO SDK Launcher")
                        except Exception as e:
                            self.log(f"Error opening SDK Launcher: {e}")
                    else:
                        self.log(f"SDK Launcher not found at: {sdk_launcher}")
            
            self.link_hovered = hovered  # Track hover state for cursor
            imgui.pop_style_color(3)
            
            imgui.set_window_font_scale(1.0)
        
        imgui.spacing()
        imgui.spacing()
        
        # Addon Name Input
        imgui.text("Addon Name:")
        imgui.set_next_item_width(200)
        _, self.addon = imgui.input_text("##addon", self.addon, 256)
        self.text_input_hovered = imgui.is_item_hovered()
        
        imgui.spacing()
        imgui.separator()
        
        # Add extra padding before GO button if prerequisites are open
        if prerequisites_opened:
            imgui.spacing()
            imgui.spacing()
        
        # GO Button
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.7, 0.2, 1.0)  # Green
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.8, 0.3, 1.0)  # Lighter green
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.6, 0.15, 1.0)  # Darker green
        
        # Disable button while import is in progress
        if self.import_in_progress:
            imgui.push_style_var(imgui.STYLE_ALPHA, 0.5)
        
        button_clicked = imgui.button("GO!", width=50, height=30)
        
        if self.import_in_progress:
            imgui.pop_style_var(1)
        
        if button_clicked and not self.import_in_progress:
            self.go()
        
        imgui.pop_style_color(3)
        
        # Show progress bar while import is in progress
        if self.import_in_progress:
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
            
            # Calculate overall progress
            # Don't count VMAPs in total until we know how many there are
            total_items = self.total_materials + self.total_models
            completed_items = self.imported_materials + self.imported_models
            
            # Add VMAPs to calculation if we know the count
            if self.total_vmaps > 0:
                total_items += self.total_vmaps
                completed_items += self.imported_vmaps
            
            progress = 0.0
            if total_items > 0:
                progress = completed_items / total_items
            
            # Display current stage
            imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.8, 0.0, 1.0)  # Yellow
            imgui.text(self.current_stage)
            imgui.pop_style_color()
            
            # Progress bar with text shadow
            imgui.push_style_color(imgui.COLOR_PLOT_HISTOGRAM, 0.2, 0.8, 0.2, 1.0)  # Green
            
            # Get progress bar position before drawing it
            cursor_pos = imgui.get_cursor_screen_pos()
            progress_width = 200  # Match "Select BSP File" button width
            progress_height = imgui.get_frame_height()
            
            # Draw the progress bar (without overlay text)
            imgui.progress_bar(progress, (progress_width, 0), "")
            
            # Draw text with shadow on top of progress bar
            draw_list = imgui.get_window_draw_list()
            percentage_text = f"{int(progress * 100)}%"
            
            # Calculate text size and center position
            text_size = imgui.calc_text_size(percentage_text)
            text_x = cursor_pos.x + (progress_width - text_size.x) / 2
            text_y = cursor_pos.y + (progress_height - text_size.y) / 2
            
            # Draw shadow (slightly offset)
            shadow_color = imgui.get_color_u32_rgba(0.0, 0.0, 0.0, 0.5)
            draw_list.add_text(text_x + 1, text_y + 1, shadow_color, percentage_text)
            
            # Draw white text on top
            text_color = imgui.get_color_u32_rgba(1.0, 1.0, 1.0, 1.0)
            draw_list.add_text(text_x, text_y, text_color, percentage_text)
            
            imgui.pop_style_color()
            
            # Details
            imgui.set_window_font_scale(0.85)
            if self.total_materials > 0:
                imgui.text(f"Materials: {self.imported_materials}/{self.total_materials}")
            if self.total_models > 0:
                imgui.text(f"Models: {self.imported_models}/{self.total_models}")
            # Always show VMAP count if we have one, even after completion
            if self.total_vmaps > 0:
                imgui.text(f"VMAPs: {self.imported_vmaps}/{self.total_vmaps}")
            elif self.vmap_done:
                # Only show "Complete" if we never got a count
                imgui.text("VMAP: Complete")
            imgui.set_window_font_scale(1.0)
        
        # Open Log button (only show after import is completed)
        if self.import_completed:
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
            
            # Open Log button
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.5, 0.8, 1.0)  # Blue
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.6, 0.9, 1.0)  # Lighter blue
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.4, 0.7, 1.0)  # Darker blue
            
            # Store cursor position after Open Log button for stats alignment
            cursor_y_start = imgui.get_cursor_pos_y()
            
            if imgui.button("Open Log", width=85, height=30):
                self.open_log_file()
            
            imgui.pop_style_color(3)
            
            # Open Folder button (below Open Log)
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.8, 0.7, 0.2, 1.0)  # Yellow
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.8, 0.6, 1.0)  # Lighter teal
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.6, 0.4, 1.0)  # Darker teal
            
            if imgui.button("Open Folder", width=95, height=30):
                if self.addon and self.csgo_basefolder:
                    # Addon folder is at {csgo_basefolder}/content/csgo_addons/{addon}
                    addon_path = os.path.join(self.csgo_basefolder, 'content', 'csgo_addons', self.addon).replace("/", "\\")
                    if os.path.exists(addon_path):
                        os.startfile(addon_path)
                        self.log(f"✓ Opened folder: {addon_path}")
                    else:
                        self.log(f"Error: Addon folder not found: {addon_path}")
                else:
                    self.log("Error: No addon name or CS:GO folder specified")
            
            imgui.pop_style_color(3)
            
            # Display import stats to the right of buttons, aligned with Open Log
            imgui.set_cursor_pos((115, cursor_y_start))
            imgui.begin_group()
            imgui.set_window_font_scale(0.85)
            imgui.push_style_color(imgui.COLOR_TEXT, 0.7, 0.7, 0.7, 1.0)  # Grey text
            imgui.text(f"Materials: {self.imported_materials}/{self.total_materials}")
            imgui.text(f"Models: {self.imported_models}/{self.total_models}")
            if self.total_vmaps > 0:
                imgui.text(f"VMAPs: {self.imported_vmaps}/{self.total_vmaps}")
            elif self.vmap_done:
                imgui.text("VMAP: ✓")
            imgui.pop_style_color()
            imgui.set_window_font_scale(1.0)
            imgui.end_group()
            
            # Add spacing after the buttons/stats section
            imgui.spacing()
            imgui.spacing()
        
        # Only show console output section after import is completed
        if self.import_completed:
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
            
            # Failed Assets section (if any failures)
            if self.failed_count > 0 or self.failed_materials or self.failed_models:
                failed_opened = imgui.collapsing_header(f"Failed Assets ({self.failed_count} total)")[0]
                if failed_opened:
                    imgui.push_style_color(imgui.COLOR_CHILD_BACKGROUND, 0.15, 0.1, 0.1, 1.0)  # Dark red background
                    imgui.begin_child("failed_assets_region", 0, 100, True)
                    
                    if self.failed_materials:
                        imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.6, 0.6, 1.0)  # Light red
                        imgui.text(f"Failed Materials ({len(self.failed_materials)}):")
                        imgui.pop_style_color()
                        imgui.set_window_font_scale(0.85)
                        for material in self.failed_materials:
                            imgui.bullet_text(material)
                        imgui.set_window_font_scale(1.0)
                        imgui.spacing()
                    
                    if self.failed_models:
                        imgui.push_style_color(imgui.COLOR_TEXT, 1.0, 0.6, 0.6, 1.0)  # Light red
                        imgui.text(f"Failed Models ({len(self.failed_models)}):")
                        imgui.pop_style_color()
                        imgui.set_window_font_scale(0.85)
                        for model in self.failed_models:
                            imgui.bullet_text(model)
                        imgui.set_window_font_scale(1.0)
                    
                    imgui.end_child()
                    imgui.pop_style_color()
                    imgui.spacing()
                    imgui.separator()
                    imgui.spacing()
        
        imgui.end()
        
        # Done popup
        if self.show_done_popup:
            imgui.open_popup("Import Complete")
        
        if imgui.begin_popup_modal("Import Complete", flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
            imgui.text("Map import completed successfully!")
            imgui.spacing()
            imgui.spacing()
            
            if imgui.button("OK", width=120):
                self.show_done_popup = False
                imgui.close_current_popup()
            
            imgui.end_popup()

    def run(self):
        """Main application loop"""
        self.init_window()
        
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.impl.process_inputs()
            
            # Handle window dragging
            if self.dragging_window:
                if imgui.is_mouse_down(0):
                    # Get cursor position in screen coordinates
                    cursor_pos = glfw.get_cursor_pos(self.window)
                    window_pos = glfw.get_window_pos(self.window)
                    
                    # Calculate new window position
                    new_x = int(window_pos[0] + cursor_pos[0] - self.drag_offset_x)
                    new_y = int(window_pos[1] + cursor_pos[1] - self.drag_offset_y)
                    glfw.set_window_pos(self.window, new_x, new_y)
                else:
                    self.dragging_window = False
            
            # Handle font reload if needed (must be done BEFORE new_frame)
            if hasattr(self, '_needs_font_reload') and self._needs_font_reload:
                io = imgui.get_io()
                io.fonts.clear()
                
                current_theme = self.theme_manager.get_theme_name()
                
                # Always use Consolas font
                consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
                if os.path.exists(consolas_path):
                    io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
                else:
                    # Fallback to Roboto
                    font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
                    if os.path.exists(font_path):
                        io.fonts.add_font_from_file_ttf(font_path, 13.0)
                
                # Rebuild font atlas
                self.impl.refresh_font_texture()
                
                self._last_theme_for_font = current_theme
                self._needs_font_reload = False
            
            imgui.new_frame()
            
            self.render()
            
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            
            imgui.render()
            
            # Set cursor based on what's being hovered
            # Must be called after imgui.render() to get accurate hover state
            io = imgui.get_io()
            if self.text_input_hovered or io.want_text_input:
                # Text input field is active or hovered
                glfw.set_cursor(self.window, self.ibeam_cursor)
            elif self.link_hovered or imgui.is_any_item_hovered():
                # Clickable item is hovered
                glfw.set_cursor(self.window, self.hand_cursor)
            else:
                # Default cursor
                glfw.set_cursor(self.window, self.arrow_cursor)
            
            self.impl.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)
        
        self.impl.shutdown()
        glfw.terminate()


if __name__ == "__main__":
    app = CS2ImporterApp()
    app.run()
