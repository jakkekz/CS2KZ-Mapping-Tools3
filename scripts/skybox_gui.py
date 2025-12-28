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

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Import theme manager
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils')))
try:
    from theme_manager import ThemeManager
except ImportError:
    class ThemeManager:
        def __init__(self):
            pass
        def get_current_theme(self):
            return {'bg': '#1e1e1e', 'fg': '#ffffff', 'button_bg': '#2d2d2d', 'button_hover': '#3d3d3d'}
from scripts.common import get_cs2_path
from scripts.SkyboxConverter import find_vtfcmd

# Constants
CUSTOM_TITLE_BAR_HEIGHT = 30

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SkyboxConverterApp:
    def __init__(self):
        self.window = None
        self.impl = None
        
        # Theme manager
        self.theme_manager = ThemeManager()
        
    # Application state
        self.skybox_files = []  # List of 6 selected files
        self.skybox_files_status = "Not selected"
        self.output_mode = "custom"  # "custom" or "addon"
        self.output_dir = None
        self.skybox_prefix = "skybox_custom"
        self.addon_name = ""
        self.cs2_path = None
        
        # Conversion options (toggleable buttons)
        self.create_skybox_vmat = False
        self.create_moondome_vmat = False
        self.cleanup_source_files = False
        
        # Get addon list
        self.addon_list = []
        self.selected_addon_index = 0
        
        # UI state
        self.status_message = ""
        self.status_color = (1.0, 1.0, 1.0, 1.0)  # White
        
        # Custom title bar drag state
        self.dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Conversion state
        self.conversion_in_progress = False
        self.conversion_completed = False
        self.progress_spinner = 0.0
        self.show_done_popup = False
        
        # Window dimensions
        self.base_window_height = 570
          # Optimized for compact checkbox layout
        self.window_padding = 20
        
        # Cursor state
        self.text_input_hovered = False
        
        # Font reload tracking
        self._last_theme_for_font = None
        self._needs_font_reload = False
        
        # Title icon
        self.title_icon = None
        
        # Cursors (will be created after window initialization)
        self.arrow_cursor = None
        self.hand_cursor = None
        
        # Button icons
        self.button_icons = {}
        
        # Auto-detect CS2 path
        self.auto_detect_cs2()
        
        # Check for VTF tools
        self.check_vtf_tools()
    
    def log(self, message):
        """Log message to console with proper encoding handling"""
        try:
            print(message)
        except UnicodeEncodeError:
            # Fallback to ASCII if console doesn't support Unicode
            print(message.encode('ascii', errors='replace').decode('ascii'))
    
    def auto_detect_cs2(self):
        """Auto-detect CS2 installation path using common.py and get addon list"""
        try:
            self.cs2_path = get_cs2_path()
            
            if self.cs2_path and os.path.exists(self.cs2_path):
                self.log(f"Auto-detected CS2: {self.cs2_path}")
                
                # CS2 addons are in "Counter-Strike Global Offensive\content\csgo_addons"
                # Navigate up to find the "Counter-Strike Global Offensive" root
                cs2_root = self.cs2_path
                while cs2_root and not cs2_root.endswith("Counter-Strike Global Offensive"):
                    parent = os.path.dirname(cs2_root)
                    if parent == cs2_root:  # Reached filesystem root
                        break
                    cs2_root = parent
                
                if cs2_root.endswith("Counter-Strike Global Offensive"):
                    addons_path = os.path.join(cs2_root, "content", "csgo_addons")
                    self.log(f"Checking for addons at: {addons_path}")
                    
                    if os.path.exists(addons_path):
                        self.addon_list = [d for d in os.listdir(addons_path) 
                                         if os.path.isdir(os.path.join(addons_path, d)) and not d.startswith('.')]
                        if self.addon_list:
                            self.log(f"Found {len(self.addon_list)} addons: {', '.join(self.addon_list)}")
                        else:
                            self.log("Addons directory exists but no addons found")
                    else:
                        self.log(f"Addons directory not found at: {addons_path}")
                else:
                    self.log(f"Could not find Counter-Strike Global Offensive root from: {self.cs2_path}")
                return
                
        except Exception as e:
            self.log(f"Error detecting CS2 path: {e}")
        
        self.log("CS2 path not auto-detected. You can still convert to custom directory.")
    
    def check_vtf_tools(self):
        """Check for VTF tools and download if missing"""
        try:
            vtf_path = find_vtfcmd()
            if vtf_path:
                self.log(f"VTF tools ready: {os.path.basename(vtf_path)}")
            else:
                self.log("Warning: VTF tools not available - conversion will fail")
        except Exception as e:
            self.log(f"Error checking VTF tools: {e}")
    
    def select_all_skybox_files(self):
        """Open file dialog to select all 6 skybox face images at once"""
        root = tk.Tk()
        root.withdraw()
        
        file_paths = filedialog.askopenfilenames(
            title="Select all 6 skybox face images (up, down, left, right, front, back)",
            filetypes=[
                ("Image files", "*.vtf *.png *.jpg *.jpeg *.tga *.exr"),
                ("All files", "*.*")
            ]
        )
        
        if file_paths:
            if len(file_paths) != 6:
                self.status_message = f"Error: Please select exactly 6 files. You selected {len(file_paths)}"
                self.status_color = (1.0, 0.0, 0.0, 1.0)
                return
            
            self.skybox_files = list(file_paths)
            self.skybox_files_status = f"Selected {len(file_paths)} files"
            
            # Auto-generate skybox prefix from first file
            first_file = os.path.splitext(os.path.basename(file_paths[0]))[0]
            # Remove common face suffixes
            face_suffixes = ['up', 'dn', 'lf', 'rt', 'ft', 'bk', 'top', 'down', 'left', 'right', 'front', 'back']
            skybox_prefix = first_file
            for suffix in face_suffixes:
                if skybox_prefix.endswith(suffix):
                    skybox_prefix = skybox_prefix[:-len(suffix)]
                    break
            self.skybox_prefix = skybox_prefix
            
            self.log(f"Selected {len(file_paths)} skybox files")
            self.log(f"Auto-generated skybox prefix: {skybox_prefix}")
            for file_path in file_paths:
                self.log(f"  - {os.path.basename(file_path)}")
    
    def select_output_directory(self):
        """Open dialog to select output directory"""
        root = tk.Tk()
        root.withdraw()
        
        dir_path = filedialog.askdirectory(title="Select Output Directory")
        
        if dir_path:
            self.output_dir = dir_path
            self.log(f"Output directory: {dir_path}")
    
    def start_conversion(self):
        """Start skybox conversion in background thread"""
        # Validate inputs
        if len(self.skybox_files) != 6:
            self.status_message = "Error: Please select all 6 skybox faces"
            self.status_color = (1.0, 0.0, 0.0, 1.0)
            return
        
        # Check output mode
        if self.output_mode == "custom":
            if not self.output_dir:
                self.status_message = "Error: Please select output directory"
                self.status_color = (1.0, 0.0, 0.0, 1.0)
                return
        else:  # addon mode
            if not self.addon_list or self.selected_addon_index >= len(self.addon_list):
                self.status_message = "Error: No addon selected"
                self.status_color = (1.0, 0.0, 0.0, 1.0)
                return
        
        if not self.skybox_prefix.strip():
            # Generate prefix from first file if empty
            if self.skybox_files:
                first_file = os.path.splitext(os.path.basename(self.skybox_files[0]))[0]
                face_suffixes = ['up', 'dn', 'lf', 'rt', 'ft', 'bk', 'top', 'down', 'left', 'right', 'front', 'back']
                skybox_prefix = first_file
                for suffix in face_suffixes:
                    if skybox_prefix.endswith(suffix):
                        skybox_prefix = skybox_prefix[:-len(suffix)]
                        break
                self.skybox_prefix = skybox_prefix
            
            if not self.skybox_prefix.strip():
                self.status_message = "Error: Could not determine skybox prefix from files"
                self.status_color = (1.0, 0.0, 0.0, 1.0)
                return
        
        self.conversion_in_progress = True
        self.conversion_completed = False
        self.console_output = []
        self.status_message = "Converting..."
        self.status_color = (1.0, 1.0, 0.0, 1.0)
        
        thread = threading.Thread(target=self.run_conversion_thread, daemon=True)
        thread.start()
    
    def run_conversion_thread(self):
        """Run skybox conversion in background thread"""
        try:
            # This will call SkyboxConverter.py as a subprocess since it's a complete script
            self.log("Starting skybox conversion...")
            
            # Determine output directory
            if self.output_mode == "addon":
                selected_addon = self.addon_list[self.selected_addon_index]
                # Get the CS2 root directory (Counter-Strike Global Offensive)
                cs2_root = self.cs2_path
                while cs2_root and not cs2_root.endswith("Counter-Strike Global Offensive"):
                    parent = os.path.dirname(cs2_root)
                    if parent == cs2_root:
                        break
                    cs2_root = parent
                
                # Build correct addon path: CS2_ROOT/content/csgo_addons/ADDON_NAME/materials/skybox
                addon_path = os.path.join(cs2_root, "content", "csgo_addons", selected_addon, "materials", "skybox")
                output_dir = addon_path
                os.makedirs(output_dir, exist_ok=True)
                self.log(f"Output to addon: {selected_addon}")
                self.log(f"Output path: {output_dir}")
            else:
                output_dir = self.output_dir
                self.log(f"Output to directory: {output_dir}")
            
            # Copy selected files to output directory temporarily
            import shutil
            temp_dir = tempfile.mkdtemp(prefix="skybox_files_")
            
            for i, file_path in enumerate(self.skybox_files):
                dest_file = os.path.join(temp_dir, os.path.basename(file_path))
                shutil.copy(file_path, dest_file)
                self.log(f"Copied: {os.path.basename(file_path)}")
            
            # Run SkyboxConverter.py
            skybox_script = resource_path(os.path.join("scripts", "SkyboxConverter.py"))
            
            # Set environment variables to pass parameters
            env = os.environ.copy()
            env['SKYBOX_INPUT_DIR'] = temp_dir
            env['SKYBOX_OUTPUT_DIR'] = output_dir
            env['SKYBOX_PREFIX'] = self.skybox_prefix
            env['CREATE_SKYBOX_VMAT'] = '1' if self.create_skybox_vmat else '0'
            env['CREATE_MOONDOME_VMAT'] = '1' if self.create_moondome_vmat else '0'
            env['CLEANUP_SOURCE_FILES'] = '1' if self.cleanup_source_files else '0'
            
            # Pass original file paths for cleanup (separated by |)
            env['ORIGINAL_FILE_PATHS'] = '|'.join(self.skybox_files)
            
            # Run as subprocess
            result = subprocess.run(
                [sys.executable, skybox_script],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                env=env
            )
            
            # Log output
            for line in result.stdout.splitlines():
                self.log(line)
            
            if result.stderr:
                for line in result.stderr.splitlines():
                    self.log(f"Error: {line}")
            
            if result.returncode == 0:
                self.log("[OK] Skybox conversion completed successfully!")
                
                # Copy generated files from temp directory to final output location
                skybox_temp_dir = os.path.join(temp_dir, "skybox")
                if os.path.exists(skybox_temp_dir):
                    # Copy skybox PNG
                    skybox_png = f"{self.skybox_prefix}.png"
                    temp_skybox_path = os.path.join(skybox_temp_dir, skybox_png)
                    final_skybox_path = os.path.join(output_dir, skybox_png)
                    
                    if os.path.exists(temp_skybox_path):
                        os.makedirs(output_dir, exist_ok=True)
                        shutil.copy(temp_skybox_path, final_skybox_path)
                        self.log(f"[OK] Copied skybox to: {final_skybox_path}")
                    
                    # Copy VMAT files if created
                    for vmat_file in os.listdir(skybox_temp_dir):
                        if vmat_file.endswith('.vmat'):
                            temp_vmat_path = os.path.join(skybox_temp_dir, vmat_file)
                            final_vmat_path = os.path.join(output_dir, vmat_file)
                            shutil.copy(temp_vmat_path, final_vmat_path)
                            self.log(f"[OK] Copied VMAT to: {final_vmat_path}")
                
                self.status_message = "Conversion completed successfully!"
                self.status_color = (0.0, 1.0, 0.0, 1.0)
                self.conversion_completed = True
            else:
                raise Exception("Skybox conversion failed")
            
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Clean up temp directory
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            self.status_message = "Conversion completed successfully!"
            self.status_color = (0.0, 1.0, 0.0, 1.0)
            self.conversion_completed = True
            self.show_done_popup = True
            
        except Exception as e:
            self.log(f"Error during conversion: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.status_message = f"Error: {str(e)}"
            self.status_color = (1.0, 0.0, 0.0, 1.0)
        finally:
            self.conversion_in_progress = False
    
    def load_texture(self, image_path):
        """Load image texture for ImGui"""
        try:
            image = Image.open(image_path)
            image = image.convert("RGBA")
            width, height = image.size
            image_data = image.tobytes()
            
            texture_id = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, image_data)
            
            return texture_id, width, height
        except Exception as e:
            print(f"Failed to load texture {image_path}: {e}")
            return None, 0, 0
    
    def init_imgui(self):
        """Initialize ImGui and GLFW"""
        if not glfw.init():
            sys.exit(1)
        
        # Create window
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)
        glfw.window_hint(glfw.DECORATED, glfw.FALSE)  # No default title bar
        
        self.window = glfw.create_window(480, self.base_window_height, "CS2 Skybox Converter", None, None)
        if not self.window:
            glfw.terminate()
            sys.exit(1)
        
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)  # Enable vsync
        
        # Create cursors
        self.arrow_cursor = glfw.create_standard_cursor(glfw.ARROW_CURSOR)
        self.hand_cursor = glfw.create_standard_cursor(glfw.HAND_CURSOR)
        
        # Initialize ImGui
        imgui.create_context()
        
        # Disable imgui.ini file creation
        io = imgui.get_io()
        io.ini_file_name = None  # Disable saving imgui.ini
        
        # Load fonts BEFORE creating the renderer
        self._load_fonts()
        
        # Load title icon
        self.load_title_icon()
        
        self.impl = GlfwRenderer(self.window)
        
        # Set window icon - skip for now as it causes issues
        # Window icon can be set via the .exe properties instead
        
        # Apply theme
        self._apply_theme()
    
    def _apply_theme(self):
        """Apply theme colors to ImGui"""
        theme = self.theme_manager.get_theme()
        style = imgui.get_style()
        io = imgui.get_io()
        
        # Set font scale - important for proper font rendering
        io.font_global_scale = 1.0
        
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
        style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = theme['title_bar_bg']
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
    
    def _load_fonts(self):
        """Load custom fonts"""
        io = imgui.get_io()
        
        try:
            # Clear default fonts first to ensure our font is used
            io.fonts.clear()
            
            # Always use Consolas font (Windows system font) - matches CS2 importer
            consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
            if os.path.exists(consolas_path):
                io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
                print(f"Loaded Consolas font from: {consolas_path}")
            else:
                # Fallback to Roboto-Regular if Consolas not available
                font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
                if os.path.exists(font_path):
                    io.fonts.add_font_from_file_ttf(font_path, 13.0)
                    print(f"Loaded Roboto font from: {font_path}")
                else:
                    print("No custom fonts available, using default")
                    # Re-add default font if no custom fonts work
                    io.fonts.add_font_default()
            
            # Note: Font texture refresh will happen automatically when renderer is created
        except Exception as e:
            print(f"Failed to load font: {e}")
    
    def load_title_icon(self):
        """Load title icon as OpenGL texture"""
        icon_path = resource_path(os.path.join("icons", "skybox.ico"))
        if os.path.exists(icon_path):
            try:
                img = Image.open(icon_path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
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
                
                self.title_icon = texture
                print(f"Loaded title icon: {icon_path}")
            except Exception as e:
                print(f"Failed to load title icon: {e}")
    
    def render_ui(self):
        """Render main UI with custom title bar"""
        window_width, window_height = glfw.get_window_size(self.window)
        
        # Single window that fills the entire GLFW window
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(window_width, window_height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (0, 0))
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        
        flags = (
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_COLLAPSE |
            imgui.WINDOW_NO_SCROLLBAR |
            imgui.WINDOW_NO_SCROLL_WITH_MOUSE
        )
        
        imgui.begin("MainWindow", flags=flags)
        
        # Render custom title bar at top (no padding here)
        self.render_custom_title_bar_content()
        
        # Content area with manual padding
        imgui.dummy(0, 10)  # Spacing after title bar
        imgui.indent(self.window_padding)  # Left padding
        
        # Set content width to account for right padding
        content_width = window_width - (self.window_padding * 2)
        imgui.push_item_width(content_width)
        
        self.render_main_content()
        
        imgui.pop_item_width()
        imgui.unindent(self.window_padding)  # Remove left padding
        imgui.dummy(0, self.window_padding)  # Bottom padding
        
        imgui.end()
        imgui.pop_style_var(3)  # Window rounding, padding, border
    
    def render_custom_title_bar_content(self):
        """Render title bar content with window dragging"""
        window_width, _ = glfw.get_window_size(self.window)
        
        # Create an invisible button for the entire title bar area for dragging
        # Leave space for the close button
        drag_area_width = window_width - 60
        
        if imgui.invisible_button("title_bar_drag", drag_area_width, CUSTOM_TITLE_BAR_HEIGHT - 5):
            pass
        
        # Handle window dragging
        if imgui.is_item_active() and imgui.is_mouse_dragging(0, 0.0):
            if not self.dragging_window:
                # Start dragging - store initial offset
                mouse_pos = imgui.get_mouse_pos()
                cursor_pos = glfw.get_cursor_pos(self.window)
                self.drag_offset_x = cursor_pos[0]
                self.drag_offset_y = cursor_pos[1]
                self.dragging_window = True
        
        # Reset cursor to draw over the invisible button
        imgui.set_cursor_pos((10, 5))
        
        # Draw icon if available
        if self.title_icon:
            imgui.image(self.title_icon, 16, 16)
            imgui.same_line(spacing=4)
        
        # Title text
        theme = self.theme_manager.get_theme()
        imgui.push_style_color(imgui.COLOR_TEXT, *theme["text"])
        imgui.text("Skybox Converter")
        imgui.pop_style_color()
        
        # Position close button on the right
        imgui.same_line(window_width - 35)
        imgui.set_cursor_pos_y(5)
        
        # Close button
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.8, 0.2, 0.2, 0.8)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.9, 0.3, 0.3, 0.9)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.7, 0.1, 0.1, 0.9)
        
        if imgui.button("×", width=25, height=20):
            glfw.set_window_should_close(self.window, True)
        
        imgui.pop_style_color(3)
        
        # Add separator line
        imgui.separator()
    
    def render_main_content(self):
        """Render the main application content"""
        
        # Skybox face selection
        imgui.text("1. Select Skybox Files:")
        imgui.separator()
        
        # Display selection status
        status_color = (0.0, 1.0, 0.0, 1.0) if len(self.skybox_files) == 6 else (1.0, 0.0, 0.0, 1.0)
        imgui.text_colored(self.skybox_files_status, *status_color)
        
        if imgui.button("Select All 6 Skybox Files", width=0, height=30):
            self.select_all_skybox_files()
        
        imgui.text_colored("(Select up, down, left, right, front, back - in any order)", 0.7, 0.7, 0.7, 1.0)
        
        imgui.separator()
        imgui.spacing()
        
        # Output mode selection
        imgui.text("2. Output Destination:")
        imgui.separator()
        
        # Radio buttons for output mode
        if imgui.radio_button("Custom Directory", self.output_mode == "custom"):
            self.output_mode = "custom"
        
        imgui.same_line(spacing=20)
        
        if imgui.radio_button("Addon", self.output_mode == "addon"):
            self.output_mode = "addon"
        
        imgui.spacing()
        
        # Show appropriate controls based on output mode
        if self.output_mode == "custom":
            # Output directory selection
            output_display = self.output_dir if self.output_dir else "Not selected"
            imgui.text(output_display)
            
            if imgui.button("Browse Directory", width=0):
                self.select_output_directory()
        
        else:  # addon mode
            # Addon selection dropdown
            if self.addon_list:
                imgui.text("Select Addon:")
                imgui.push_item_width(0)
                clicked, self.selected_addon_index = imgui.combo(
                    "##addon_select",
                    self.selected_addon_index,
                    self.addon_list
                )
                imgui.pop_item_width()
                
                if self.selected_addon_index < len(self.addon_list):
                    selected_addon = self.addon_list[self.selected_addon_index]
                    imgui.text_colored(f"Will save to: csgo_addons/{selected_addon}/materials/skybox/", 0.5, 0.5, 1.0, 1.0)
            else:
                imgui.text_colored(f"No addons found. CS2 detected: {bool(self.cs2_path)}", 1.0, 0.0, 0.0, 1.0)
                if self.cs2_path:
                    # Show where we're looking for addons
                    cs2_root = self.cs2_path
                    while cs2_root and not cs2_root.endswith("Counter-Strike Global Offensive"):
                        parent = os.path.dirname(cs2_root)
                        if parent == cs2_root:
                            break
                        cs2_root = parent
                    
                    if cs2_root.endswith("Counter-Strike Global Offensive"):
                        addons_path = os.path.join(cs2_root, "content", "csgo_addons")
                        imgui.text_colored(f"Checked: {addons_path}", 0.7, 0.7, 0.7, 1.0)
        
        imgui.separator()
        imgui.spacing()
        
        # Conversion Options
        imgui.text("3. Conversion Options:")
        imgui.separator()
        
        # Set checkbox colors to match theme accent
        theme = self.theme_manager.get_theme()
        imgui.push_style_color(imgui.COLOR_CHECK_MARK, *theme['accent'])
        imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND_HOVERED, *theme['title_bar_bg'])
        
        # Skybox VMAT options
        clicked, self.create_skybox_vmat = imgui.checkbox("Create Skybox VMAT", self.create_skybox_vmat)
        
        # Moondome VMAT options
        clicked, self.create_moondome_vmat = imgui.checkbox("Create Moondome VMAT", self.create_moondome_vmat)
        
        # Cleanup options
        clicked, self.cleanup_source_files = imgui.checkbox("Cleanup Source Files", self.cleanup_source_files)
        
        imgui.pop_style_color(2)  # Pop checkbox colors
        
        imgui.separator()
        imgui.spacing()
        
        # Convert button
        if not self.conversion_in_progress:
            if imgui.button("CONVERT SKYBOX", width=0, height=40):
                self.start_conversion()
        else:
            # Show a disabled button during conversion instead of text
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.3, 0.3, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.3, 0.3, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.3, 0.3, 0.3, 1.0)
            imgui.button("CONVERT SKYBOX", width=0, height=40)
            imgui.pop_style_color(3)
            self.progress_spinner += 0.1
        
        # Status message
        if self.status_message:
            imgui.spacing()
            imgui.text_colored(self.status_message, *self.status_color)
        
        imgui.spacing()
    
    def run(self):
        """Main application loop"""
        self.init_imgui()
        
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.impl.process_inputs()
            
            # Check for theme updates from main app
            if self.theme_manager.check_for_updates():
                self._apply_theme()
            
            # Handle window dragging (BEFORE rendering starts)
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
            
            imgui.new_frame()
            
            # Render single UI window
            self.render_ui()
            
            # Set cursor to pointer when hovering over clickable items (but not title bar)
            if imgui.is_any_item_hovered():
                # Check if we're not hovering over the title bar area
                mouse_pos = imgui.get_mouse_pos()
                if mouse_pos[1] > 35:  # Below title bar area
                    glfw.set_cursor(self.window, self.hand_cursor)
                else:
                    glfw.set_cursor(self.window, self.arrow_cursor)
            else:
                glfw.set_cursor(self.window, self.arrow_cursor)
            
            # Rendering
            gl.glClearColor(0.1, 0.1, 0.1, 1)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            
            imgui.render()
            self.impl.render(imgui.get_draw_data())
            
            glfw.swap_buffers(self.window)
        
        self.impl.shutdown()
        glfw.terminate()


if __name__ == "__main__":
    app = SkyboxConverterApp()
    app.run()
