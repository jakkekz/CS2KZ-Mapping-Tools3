"""
Loading Screen Creator - GUI Version
Creates loading screen images and map icons for CS2 maps
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import subprocess
import ctypes
from pathlib import Path
from PIL import Image, ImageTk

# Add the scripts directory to the path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import the loading screen functions
from loading_screen import (
    get_cs2_path,
    create_vmat_content,
    compile_vmat_files,
    compile_svg_files
)

# Helper function for PyInstaller resource paths
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Import theme manager after resource_path is defined
utils_path = resource_path('utils')
if not os.path.exists(utils_path):
    utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils'))
sys.path.insert(0, utils_path)

try:
    from theme_manager import ThemeManager
except ImportError:
    class ThemeManager:
        def __init__(self):
            pass
        def get_current_theme(self):
            return {'bg': '#1e1e1e', 'fg': '#ffffff', 'button_bg': '#2d2d2d', 'button_hover': '#3d3d3d'}

# CustomTkinter-like dark theme colors (defaults - will be overridden by theme manager)
DARK_BG = "#1a1a1a"  # Window background (0.1, 0.1, 0.1)
DARK_FRAME = "#2b2b2b"  # Frame/Entry background (0.17, 0.17, 0.17)
DARK_BUTTON = "#4a4a4a"  # Button background (0.29, 0.29, 0.29)
DARK_BUTTON_HOVER = "#595959"  # Button hover (0.35, 0.35, 0.35)
DARK_BORDER = "#666666"  # Border color (0.40, 0.40, 0.40)
DARK_TEXT = "#ffffff"  # Text color
DARK_TEXT_SECONDARY = "#b0b0b0"  # Secondary text
ACCENT_ORANGE = "#FF9800"  # Orange accent
ACCENT_GREEN = "#4CAF50"  # Green accent
ACCENT_RED = "#f44336"  # Red accent
ACCENT_BLUE = "#2196F3"  # Blue accent
TITLE_BAR_BG = "#1f1f1f"  # Custom title bar background
TITLE_BAR_HEIGHT = 30


class LoadingScreenCreatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CS2 Loading Screen Creator")
        
        # Initialize theme manager
        self.theme_manager = ThemeManager()
        self.apply_theme()
        
        # Set window icon
        try:
            icon_path = resource_path(os.path.join("icons", "loading.ico"))
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        # Window size and position - set BEFORE overrideredirect
        window_width = 480
        window_height = 775  # Increased to fit all content including Go button
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(False, False)
        
        # Update window to ensure it's created
        self.root.update_idletasks()
        
        # Remove default title bar but keep in taskbar
        self.root.overrideredirect(True)
        
        # Set taskbar button immediately (before window is fully shown)
        self.root.after(10, self._set_taskbar_button)
        
        # Apply dark theme
        self.root.configure(bg=DARK_BG)
        
        # Variables for window dragging
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Variables
        self.addon_name = tk.StringVar()
        self.map_name = tk.StringVar()
        self.image_files = []
        self.svg_file = None
        self.map_description = ""
        self.cs2_path = None
        
        # Try to find CS2 path automatically
        self.cs2_path = get_cs2_path()
        
        self.create_widgets()
        
        # Start theme update checking
        self.check_theme_updates()
    
    def start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_start_x
        y = self.root.winfo_y() + event.y - self._drag_start_y
        self.root.geometry(f"+{x}+{y}")
    
    def _set_taskbar_button(self):
        """Force the window to appear in the Windows taskbar using Win32 API"""
        try:
            # Get window handle
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            
            # Constants for window styles
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            
            # Get current extended window style
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            
            # Remove tool window style and add app window style
            style = style & ~WS_EX_TOOLWINDOW
            style = style | WS_EX_APPWINDOW
            
            # Set the new style
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            
            # Show in taskbar without flashing - use ShowWindow instead
            SW_HIDE = 0
            SW_SHOW = 5
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
            ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
        except Exception as e:
            print(f"Could not set taskbar button: {e}")
    
    def minimize_window(self):
        # Store window position before minimizing
        self.root.update_idletasks()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        
        # Temporarily disable overrideredirect to allow minimize
        self.root.overrideredirect(False)
        self.root.update_idletasks()
        
        # Minimize the window
        self.root.iconify()
        
        # When window is restored, re-enable overrideredirect and restore position
        def restore_overrideredirect():
            if self.root.state() == 'normal':
                self.root.overrideredirect(True)
                self.root.geometry(f"+{x}+{y}")
            else:
                # Check again later
                self.root.after(100, restore_overrideredirect)
        
        # Start checking for restore
        self.root.after(100, restore_overrideredirect)
    
    def close_window(self):
        self.root.destroy()
    
    def apply_theme(self):
        """Apply theme colors from theme manager"""
        global DARK_BG, DARK_FRAME, DARK_BUTTON, DARK_BUTTON_HOVER, DARK_BORDER, DARK_TEXT, DARK_TEXT_SECONDARY, ACCENT_ORANGE, TITLE_BAR_BG
        theme = self.theme_manager.get_theme()
        
        DARK_BG = self.theme_manager.to_hex(theme['window_bg'])
        TITLE_BAR_BG = self.theme_manager.to_hex(theme['title_bar_bg'])
        DARK_FRAME = self.theme_manager.to_hex(theme['title_bar_bg'])
        DARK_BUTTON = self.theme_manager.to_hex(theme['button'])
        DARK_BUTTON_HOVER = self.theme_manager.to_hex(theme['button_hover'])
        DARK_BORDER = self.theme_manager.to_hex(theme['border'])
        DARK_TEXT = self.theme_manager.to_hex(theme['text'])
        ACCENT_ORANGE = self.theme_manager.to_hex(theme['accent'])
        
        # Apply to root window if it exists
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.configure(bg=DARK_BG)
            self._update_widget_colors(self.root)
    
    def _update_widget_colors(self, widget):
        """Recursively update all widget colors"""
        try:
            if isinstance(widget, tk.Frame):
                # Check if it's the title bar (first frame)
                if widget.winfo_height() == TITLE_BAR_HEIGHT or widget == widget.master.winfo_children()[0]:
                    widget.configure(bg=TITLE_BAR_BG)
                else:
                    widget.configure(bg=DARK_BG)
            elif isinstance(widget, tk.Label):
                parent = widget.master
                if isinstance(parent, tk.Frame) and (parent.winfo_height() == TITLE_BAR_HEIGHT or parent == parent.master.winfo_children()[0]):
                    widget.configure(bg=TITLE_BAR_BG, fg=DARK_TEXT)
                else:
                    widget.configure(bg=DARK_BG, fg=DARK_TEXT)
            elif isinstance(widget, tk.Button):
                parent = widget.master
                if isinstance(parent, tk.Frame) and (parent.winfo_height() == TITLE_BAR_HEIGHT or parent == parent.master.winfo_children()[0]):
                    widget.configure(bg=TITLE_BAR_BG, fg=DARK_TEXT, activebackground=DARK_BUTTON_HOVER)
                else:
                    widget.configure(bg=DARK_BUTTON, fg=DARK_TEXT, activebackground=DARK_BUTTON_HOVER)
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=DARK_FRAME, fg=DARK_TEXT, insertbackground=DARK_TEXT, disabledbackground=DARK_FRAME, disabledforeground=DARK_TEXT)
            elif isinstance(widget, tk.Text):
                widget.configure(bg=DARK_FRAME, fg=DARK_TEXT, insertbackground=DARK_TEXT)
            
            # Recursively update children
            for child in widget.winfo_children():
                self._update_widget_colors(child)
        except:
            pass
    
    def check_theme_updates(self):
        """Check for theme updates and reapply if needed"""
        if self.theme_manager.check_for_updates():
            self.apply_theme()
            # Would need to rebuild UI to fully apply - just update what we can
        self.root.after(1000, self.check_theme_updates)
    
    def create_widgets(self):
        # Custom title bar
        title_bar = tk.Frame(self.root, bg=TITLE_BAR_BG, height=TITLE_BAR_HEIGHT)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False)
        
        # Bind drag events to title bar
        title_bar.bind("<Button-1>", self.start_drag)
        title_bar.bind("<B1-Motion>", self.on_drag)
        
        # Try to load and add icon to title bar
        try:
            icon_path = resource_path(os.path.join("icons", "loading.ico"))
            if os.path.exists(icon_path):
                # Load icon image and resize to 16x16
                icon_img = Image.open(icon_path)
                icon_img = icon_img.resize((16, 16), Image.Resampling.LANCZOS)
                self.title_icon = ImageTk.PhotoImage(icon_img)
                
                # Add icon label
                icon_label = tk.Label(title_bar, image=self.title_icon, bg=TITLE_BAR_BG)
                icon_label.pack(side=tk.LEFT, padx=(10, 5))
                icon_label.bind("<Button-1>", self.start_drag)
                icon_label.bind("<B1-Motion>", self.on_drag)
        except Exception as e:
            print(f"Could not load title bar icon: {e}")
        
        # Title text
        title_label = tk.Label(title_bar, text="CS2 Loading Screen Creator", 
                              bg=TITLE_BAR_BG, fg=DARK_TEXT,
                              font=("Segoe UI", 9))
        title_label.pack(side=tk.LEFT, padx=0)
        title_label.bind("<Button-1>", self.start_drag)
        title_label.bind("<B1-Motion>", self.on_drag)
        
        # Close button (rightmost)
        close_btn = tk.Button(title_bar, text="✕", bg=TITLE_BAR_BG, fg=DARK_TEXT,
                             font=("Segoe UI", 9), bd=0, padx=15, pady=0,
                             activebackground="#e81123", activeforeground=DARK_TEXT,
                             cursor="hand2",
                             command=self.close_window)
        close_btn.pack(side=tk.RIGHT)
        close_btn.bind("<Enter>", lambda e: close_btn.config(bg="#e81123"))
        close_btn.bind("<Leave>", lambda e: close_btn.config(bg=TITLE_BAR_BG))
        
        # Minimize button (left of close)
        minimize_btn = tk.Button(title_bar, text="─", bg=TITLE_BAR_BG, fg=DARK_TEXT,
                                font=("Segoe UI", 9), bd=0, padx=15, pady=0,
                                activebackground="#333333", activeforeground=DARK_TEXT,
                                cursor="hand2",
                                command=self.minimize_window)
        minimize_btn.pack(side=tk.RIGHT)
        minimize_btn.bind("<Enter>", lambda e: minimize_btn.config(bg="#333333"))
        minimize_btn.bind("<Leave>", lambda e: minimize_btn.config(bg=TITLE_BAR_BG))
        
        # Content frame
        content_frame = tk.Frame(self.root, bg=DARK_BG)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(content_frame, text="CS2 Loading Screen Creator", 
                        font=("Segoe UI", 16, "bold"),
                        bg=DARK_BG, fg=DARK_TEXT)
        title.pack(pady=10)
        
        # Addon Name
        addon_frame = tk.Frame(content_frame, bg=DARK_BG)
        addon_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(addon_frame, text="Addon Folder Name:", 
                font=("Segoe UI", 10, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(anchor=tk.W)
        
        addon_entry = tk.Entry(addon_frame, textvariable=self.addon_name, 
                        font=("Segoe UI", 10),
                        bg=DARK_FRAME, fg=DARK_TEXT,
                        insertbackground=DARK_TEXT,
                        relief=tk.FLAT,
                        highlightthickness=2,
                        highlightbackground=DARK_BORDER,
                        highlightcolor=ACCENT_ORANGE)
        addon_entry.pack(fill=tk.X, pady=5, ipady=5)
        
        tk.Label(addon_frame, text="Example: kz_jakke → csgo_addons/kz_jakke/", 
                font=("Segoe UI", 8), 
                bg=DARK_BG, fg=DARK_TEXT_SECONDARY).pack(anchor=tk.W)
        
        # Map Name
        map_frame = tk.Frame(content_frame, bg=DARK_BG)
        map_frame.pack(pady=5, padx=20, fill=tk.X)
        
        tk.Label(map_frame, text="Map Name:", 
                font=("Segoe UI", 10, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(anchor=tk.W)
        
        map_entry = tk.Entry(map_frame, textvariable=self.map_name, 
                        font=("Segoe UI", 10),
                        bg=DARK_FRAME, fg=DARK_TEXT,
                        insertbackground=DARK_TEXT,
                        relief=tk.FLAT,
                        highlightthickness=2,
                        highlightbackground=DARK_BORDER,
                        highlightcolor=ACCENT_ORANGE)
        map_entry.pack(fill=tk.X, pady=5, ipady=5)
        
        tk.Label(map_frame, text="Example: kz_jakke_v2 → csgo_addons/kz_jakke/maps/kz_jakke_v2.vmap", 
                font=("Segoe UI", 8), 
                bg=DARK_BG, fg=DARK_TEXT_SECONDARY).pack(anchor=tk.W)
        
        # Images Section
        images_frame = tk.Frame(content_frame, bg=DARK_BG)
        images_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Title with clickable link
        loading_title_frame = tk.Frame(images_frame, bg=DARK_BG)
        loading_title_frame.pack(anchor=tk.W)
        
        loading_screen_link = tk.Label(loading_title_frame, text="Loading Screen Images", 
                font=("Segoe UI", 10, "bold", "underline"),
                bg=DARK_BG, fg=ACCENT_BLUE, cursor="hand2")
        loading_screen_link.pack(side=tk.LEFT)
        loading_screen_link.bind("<Button-1>", lambda e: self.open_loading_screen_example())
        
        tk.Label(loading_title_frame, text=" (1-9, optional):", 
                font=("Segoe UI", 10, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(side=tk.LEFT)
        
        tk.Label(images_frame, text="Images will be cropped to 16:9 aspect ratio and converted to PNG", 
                font=("Segoe UI", 8),
                bg=DARK_BG, fg=DARK_TEXT_SECONDARY).pack(anchor=tk.W, pady=(0, 5))
        
        btn_frame = tk.Frame(images_frame, bg=DARK_BG)
        btn_frame.pack(pady=5, fill=tk.X)
        
        # Styled buttons - matching SVG button colors
        select_btn = tk.Button(btn_frame, text="Select Images", command=self.select_images,
                 bg=ACCENT_BLUE, fg=DARK_TEXT, font=("Segoe UI", 9, "bold"),
                 relief=tk.FLAT, cursor="hand2",
                 activebackground="#0b7dda", activeforeground=DARK_TEXT,
                 padx=15, pady=5)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_btn = tk.Button(btn_frame, text="Clear", command=self.clear_images,
                 bg=DARK_BUTTON, fg=DARK_TEXT, font=("Segoe UI", 9),
                 relief=tk.FLAT, cursor="hand2",
                 activebackground=DARK_BUTTON_HOVER, activeforeground=DARK_TEXT,
                 padx=10, pady=5)
        clear_btn.pack(side=tk.LEFT)
        
        # Images listbox
        listbox_frame = tk.Frame(images_frame, bg=DARK_BG)
        listbox_frame.pack(fill=tk.X, pady=5)
        
        self.images_listbox = tk.Listbox(listbox_frame,
                                         height=4, font=("Segoe UI", 9),
                                         bg=DARK_FRAME, fg=DARK_TEXT,
                                         selectbackground=DARK_BUTTON_HOVER,
                                         selectforeground=DARK_TEXT,
                                         relief=tk.FLAT,
                                         highlightthickness=2,
                                         highlightbackground=DARK_BORDER,
                                         highlightcolor=DARK_BORDER)
        self.images_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Map Icon Section
        svg_frame = tk.Frame(content_frame, bg=DARK_BG)
        svg_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Title with clickable link
        title_frame = tk.Frame(svg_frame, bg=DARK_BG)
        title_frame.pack(anchor=tk.W)
        
        map_icon_link = tk.Label(title_frame, text="Map Icon", 
                font=("Segoe UI", 10, "bold", "underline"),
                bg=DARK_BG, fg=ACCENT_BLUE, cursor="hand2")
        map_icon_link.pack(side=tk.LEFT)
        map_icon_link.bind("<Button-1>", lambda e: self.open_map_icon_example())
        
        tk.Label(title_frame, text=" (optional):", 
                font=("Segoe UI", 10, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(side=tk.LEFT)
        
        desc_frame = tk.Frame(svg_frame, bg=DARK_BG)
        desc_frame.pack(anchor=tk.W, pady=(0, 5))
        
        tk.Label(desc_frame, text="Select an SVG file (square) for the map icon - ", 
                font=("Segoe UI", 8),
                bg=DARK_BG, fg=DARK_TEXT_SECONDARY).pack(side=tk.LEFT)
        
        converter_link = tk.Label(desc_frame, text="PNG to SVG Converter", 
                font=("Segoe UI", 8, "underline"),
                bg=DARK_BG, fg=ACCENT_BLUE, cursor="hand2")
        converter_link.pack(side=tk.LEFT)
        converter_link.bind("<Button-1>", lambda e: self.open_converter())
        
        svg_btn_frame = tk.Frame(svg_frame, bg=DARK_BG)
        svg_btn_frame.pack(pady=5, fill=tk.X)
        
        svg_btn = tk.Button(svg_btn_frame, text="Select SVG", command=self.select_svg,
                 bg=ACCENT_BLUE, fg=DARK_TEXT, font=("Segoe UI", 9, "bold"),
                 relief=tk.FLAT, cursor="hand2",
                 activebackground="#0b7dda", activeforeground=DARK_TEXT,
                 padx=15, pady=5)
        svg_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        clear_svg_btn = tk.Button(svg_btn_frame, text="Clear", command=self.clear_svg,
                 bg=DARK_BUTTON, fg=DARK_TEXT, font=("Segoe UI", 9),
                 relief=tk.FLAT, cursor="hand2",
                 activebackground=DARK_BUTTON_HOVER, activeforeground=DARK_TEXT,
                 padx=10, pady=5)
        clear_svg_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.svg_label = tk.Label(svg_btn_frame, text="No file selected", 
                                  font=("Segoe UI", 9),
                                  bg=DARK_BG, fg=DARK_TEXT_SECONDARY)
        self.svg_label.pack(side=tk.LEFT, padx=5)
        
        # Description Text Section
        txt_frame = tk.Frame(content_frame, bg=DARK_BG)
        txt_frame.pack(pady=5, padx=20, fill=tk.X)
        
        # Title with clickable link
        desc_title_frame = tk.Frame(txt_frame, bg=DARK_BG)
        desc_title_frame.pack(anchor=tk.W)
        
        map_desc_link = tk.Label(desc_title_frame, text="Map Description", 
                font=("Segoe UI", 10, "bold", "underline"),
                bg=DARK_BG, fg=ACCENT_BLUE, cursor="hand2")
        map_desc_link.pack(side=tk.LEFT)
        map_desc_link.bind("<Button-1>", lambda e: self.open_map_description_example())
        
        tk.Label(desc_title_frame, text=" (optional):", 
                font=("Segoe UI", 10, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).pack(side=tk.LEFT)
        
        tk.Label(txt_frame, text="Write the map description text below:", 
                font=("Segoe UI", 8),
                bg=DARK_BG, fg=DARK_TEXT_SECONDARY).pack(anchor=tk.W, pady=(0, 5))
        
        # Text area without scrollbar
        text_frame = tk.Frame(txt_frame, bg=DARK_BG)
        text_frame.pack(fill=tk.X)
        
        self.description_text = tk.Text(text_frame, height=4, font=("Segoe UI", 9),
                                        wrap=tk.WORD,
                                        bg=DARK_FRAME, fg=DARK_TEXT,
                                        insertbackground=DARK_TEXT,
                                        relief=tk.FLAT,
                                        highlightthickness=2,
                                        highlightbackground=DARK_BORDER,
                                        highlightcolor=ACCENT_ORANGE,
                                        padx=5, pady=5)
        self.description_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Create Button
        create_btn = tk.Button(content_frame, text="Go!", 
                              command=self.create_files,
                              bg=ACCENT_GREEN, fg=DARK_TEXT, 
                              font=("Segoe UI", 10, "bold"),
                              relief=tk.FLAT, cursor="hand2",
                              activebackground="#45a049", activeforeground=DARK_TEXT,
                              height=1)
        create_btn.pack(pady=15, padx=20, fill=tk.X)
    
    def select_images(self):
        files = filedialog.askopenfilenames(
            title="Select Loading Screen Images (1-9 images)",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.tga *.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if files:
            # Limit to 9 images
            files = list(files)[:9]
            self.image_files = files
            
            # Update listbox
            self.images_listbox.delete(0, tk.END)
            for i, file in enumerate(files, 1):
                self.images_listbox.insert(tk.END, f"{i}. {os.path.basename(file)}")
    
    def clear_images(self):
        self.image_files = []
        self.images_listbox.delete(0, tk.END)
    
    def select_svg(self):
        file = filedialog.askopenfilename(
            title="Select Map Icon (SVG)",
            filetypes=[
                ("SVG files", "*.svg"),
                ("All files", "*.*")
            ]
        )
        
        if file:
            self.svg_file = file
            self.svg_label.config(text=os.path.basename(file), fg=DARK_TEXT)
    
    def clear_svg(self):
        self.svg_file = None
        self.svg_label.config(text="No file selected", fg=DARK_TEXT_SECONDARY)
    
    def open_converter(self):
        import webbrowser
        webbrowser.open("https://www.pngtosvg.com/")
    
    def open_loading_screen_example(self):
        import webbrowser
        webbrowser.open("https://imgur.com/a/XqXcL6j")
    
    def open_map_icon_example(self):
        import webbrowser
        webbrowser.open("https://imgur.com/a/Z3v8dG4")
    
    def open_map_description_example(self):
        import webbrowser
        webbrowser.open("https://imgur.com/a/XNSxleb")
    
    def create_files(self):
        # Validate addon name and map name
        if not self.addon_name.get().strip():
            messagebox.showerror("Error", "Please enter an addon folder name!")
            return
        
        if not self.map_name.get().strip():
            messagebox.showerror("Error", "Please enter a map name!")
            return
        
        addon_name = self.addon_name.get().strip()
        map_name = self.map_name.get().strip()
        
        # Check if CS2 path is found
        if not self.cs2_path:
            messagebox.showerror(
                "CS2 Not Found",
                "Could not automatically find CS2 installation.\n\n"
                "Please make sure Counter-Strike 2 is installed via Steam."
            )
            return
        
        try:
            # Define the base paths using addon_name for folder, map_name for files
            content_addons_dir = os.path.join(self.cs2_path, 'content', 'csgo_addons', addon_name)
            game_addons_dir = os.path.join(self.cs2_path, 'game', 'csgo_addons', addon_name)
            
            # Define full destination folder paths
            loading_screen_dir = os.path.join(content_addons_dir, 'panorama', 'images', 'map_icons', 'screenshots', '1080p')
            map_icon_content_dir = os.path.join(content_addons_dir, 'panorama', 'images', 'map_icons')
            maps_dir = os.path.join(game_addons_dir, 'maps')
            
            # Create destination directories
            for directory in [loading_screen_dir, map_icon_content_dir, maps_dir]:
                os.makedirs(directory, exist_ok=True)
            
            vmat_files_to_compile = []
            svg_files_to_compile = []
            
            # Process images
            if self.image_files:
                for i, source_image_path in enumerate(self.image_files, 1):
                    dest_image_name = f"{map_name}_{i}.png"
                    dest_image_path = os.path.join(loading_screen_dir, dest_image_name)
                    
                    # Crop to 16:9 and save
                    with Image.open(source_image_path) as img:
                        width, height = img.size
                        
                        # Calculate new dimensions for 16:9 aspect ratio
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
                        
                        # Crop and save
                        img_cropped = img.crop((left, top, right, bottom))
                        img_cropped.save(dest_image_path, "PNG")
                    
                    # Generate corresponding vmat file
                    dest_vmat_name = f"{map_name}_{i}_png.vmat"
                    dest_vmat_path = os.path.join(loading_screen_dir, dest_vmat_name)
                    vmat_content = create_vmat_content(map_name, i)
                    
                    with open(dest_vmat_path, 'w') as f:
                        f.write(vmat_content)
                    
                    vmat_files_to_compile.append(dest_vmat_path)
            
            # Process SVG
            if self.svg_file:
                import shutil
                dest_icon_name = f"map_icon_{map_name}.svg"
                dest_icon_path = os.path.join(map_icon_content_dir, dest_icon_name)
                shutil.copy(self.svg_file, dest_icon_path)
                svg_files_to_compile.append(dest_icon_path)
            
            # Process description text
            description_text = self.description_text.get("1.0", tk.END)
            # Remove only the trailing newline that tkinter adds, but preserve leading/intentional whitespace
            if description_text.endswith('\n'):
                description_text = description_text[:-1]
            if description_text:
                description_file_name = f"{map_name}.txt"
                description_file_path = os.path.join(maps_dir, description_file_name)
                with open(description_file_path, 'w', encoding='utf-8') as f:
                    f.write(description_text)
            
            # Compile VMAT files
            if vmat_files_to_compile:
                compile_vmat_files(self.cs2_path, vmat_files_to_compile, map_name, addon_name)
            
            # Compile SVG files
            if svg_files_to_compile:
                compile_svg_files(self.cs2_path, svg_files_to_compile, map_name, addon_name)
            
            messagebox.showinfo(
                "Success",
                f"Loading screen files created successfully!\n\n"
                f"Map Name: {map_name}\n"
                f"Images: {len(self.image_files)}\n"
                f"SVG Icon: {'Yes' if self.svg_file else 'No'}\n"
                f"Description: {'Yes' if description_text else 'No'}\n\n"
                f"Files have been compiled and placed in:\n"
                f"game/csgo_addons/{addon_name}/"
            )
            
            # Open the output folder
            try:
                os.startfile(game_addons_dir)
            except Exception:
                pass
            
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")


def main():
    root = tk.Tk()
    app = LoadingScreenCreatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
