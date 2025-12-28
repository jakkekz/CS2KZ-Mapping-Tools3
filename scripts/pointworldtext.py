import sys
import os
import subprocess
import tempfile
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont # Ensure all PIL components are imported

# Helper function for PyInstaller resource paths
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Import ThemeManager
utils_path = resource_path('utils')
if not os.path.exists(utils_path):
    utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils'))
sys.path.insert(0, utils_path)

try:
    from theme_manager import ThemeManager
except ImportError:
    # Fallback if theme_manager not available
    ThemeManager = None

# CustomTkinter-like dark theme colors (will be updated by theme manager)
DARK_BG = "#1a1a1a"  # Window background
DARK_FRAME = "#2b2b2b"  # Frame/Entry background
DARK_BUTTON = "#4a4a4a"  # Button background
DARK_BUTTON_HOVER = "#595959"  # Button hover
DARK_BORDER = "#666666"  # Border color
DARK_TEXT = "#ffffff"  # Text color
DARK_TEXT_SECONDARY = "#b0b0b0"  # Secondary text
ACCENT_ORANGE = "#FF9800"  # Orange accent
ACCENT_GREEN = "#4CAF50"  # Green accent
ACCENT_BLUE = "#2196F3"  # Blue accent
TITLE_BAR_BG = "#1f1f1f"  # Custom title bar background
TITLE_BAR_HEIGHT = 30

# --- Core Logic Functions ---

def extract_characters(input_image_path, output_folder="chars"):
    """Extracts individual characters from a character sheet image."""
    img = Image.open(input_image_path).convert('RGBA')
    width, height = img.size
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    pixels = img.load()
    
    # Find rows (vertical segmentation)
    rows = []
    in_row = False
    start_y = 0
    
    for y in range(height):
        row_has_content = False
        for x in range(width):
            r, g, b, a = pixels[x, y]
            # Check for non-white/transparent content
            if r < 250 or g < 250 or b < 250:
                row_has_content = True
                break
        
        if row_has_content and not in_row:
            start_y = y
            in_row = True
        elif not row_has_content and in_row:
            rows.append((start_y, y))
            in_row = False
    
    if in_row:
        rows.append((start_y, height))
    
    # Character mapping structure (must match the rows in the sheet)
    char_rows = [
        ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'], # Digits
        ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z'], # Lowercase
        ['aa', 'bb', 'cc', 'dd', 'ee', 'ff', 'gg', 'hh', 'ii', 'jj', 'kk', 'll', 'mm', 'nn', 'oo', 'pp', 'qq', 'rr', 'ss', 'tt', 'uu', 'vv', 'ww', 'xx', 'yy', 'zz'], # Uppercase mapped (double letters)
        ['!', '"', '#', '$', '%', '&', "'", '(', ')', '*', '+', ',', '-', '.', '/', ':', ';', '<', '=', '>', '?', '@', '[', '\\', ']', '^', '_', '`', '{', '|', '}', '~'] # Symbols
    ]
    
    for row_idx, (y1, y2) in enumerate(rows):
        if row_idx >= len(char_rows):
            break
        
        row_img = img.crop((0, y1, width, y2))
        row_pixels = row_img.load()
        row_width = row_img.width
        
        # Find characters in this row (horizontal segmentation)
        chars = []
        in_char = False
        start_x = 0
        
        for x in range(row_width):
            col_has_content = False
            for y in range(row_img.height):
                r, g, b, a = row_pixels[x, y]
                if r < 250 or g < 250 or b < 250:
                    col_has_content = True
                    break
            
            if col_has_content and not in_char:
                start_x = x
                in_char = True
            elif not col_has_content and in_char:
                chars.append((start_x, x))
                in_char = False
        
        if in_char:
            chars.append((start_x, row_width))
        
        # Save individual character images
        for char_idx, (x1, x2) in enumerate(chars):
            if char_idx >= len(char_rows[row_idx]):
                break
            
            char_img = row_img.crop((x1, 0, x2, row_img.height))
            
            # Make white transparent
            data = char_img.getdata()
            new_data = []
            for item in data:
                if item[0] > 250 and item[1] > 250 and item[2] > 250:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            char_img.putdata(new_data)
            
            char_name = char_rows[row_idx][char_idx]
            safe_name = char_name
            
            # 1. Digits ('0' to '9'): Use underscore prefix (e.g., '0' -> '_0')
            if len(char_name) == 1 and char_name.isdigit():
                safe_name = "_" + char_name
            
            # 2. Symbols: Use ASCII number (e.g., '!' -> '33')
            # Check if it's a single character AND not a letter or digit (i.e., a symbol)
            elif len(char_name) == 1 and not char_name.isalnum():
                safe_name = str(ord(char_name))
            
            # 3. Uppercase mappings (e.g., 'A' -> 'aa', stored as 'aa.png')
            elif len(char_name) == 2 and char_name.islower() and char_name[0] == char_name[1]:
                safe_name = char_name

            filepath = os.path.join(output_folder, f"{safe_name}.png")
            char_img.save(filepath)
    
def stitch_text(text, chars_folder="chars", output_path="stitched_output.png", space_width_ratio=0.5, scale_factor=1.0, canvas_width=512, canvas_height=512):
    """Stitches characters together to form a text image with auto-scaling to fill the canvas. Supports multiple lines."""
    char_images = {}
    
    # Load all extracted character images
    for filename in os.listdir(chars_folder):
        if filename.endswith('.png'):
            char_name = filename[:-4]
            char_key = None
            
            # 1. Check for prefixed digits (e.g., '_1.png' -> key '1')
            if char_name.startswith('_') and char_name[1:].isdigit() and len(char_name) == 2:
                char_key = char_name[1] # The key is the digit itself ('1', '2', etc.)
            
            # 2. Check for symbols (e.g., '33.png' -> key '!')
            elif char_name.isdigit():
                try:
                    # Convert the numerical filename back to the character key (e.g., '33' -> '!')
                    char_key = chr(int(char_name))
                except ValueError:
                    continue # Skip if it's a number that isn't a valid ASCII code

            # 3. Check for lowercase letters (e.g., 'a.png' -> key 'a')
            elif len(char_name) == 1 and char_name.islower():
                char_key = char_name
            
            # 4. Check for uppercase/double letters (e.g., 'aa.png' -> key 'aa' for 'A')
            elif len(char_name) == 2 and char_name.islower() and char_name[0] == char_name[1]:
                char_key = char_name
            
            if char_key:
                try:
                    char_images[char_key] = Image.open(os.path.join(chars_folder, filename))
                except Exception:
                    # Skip corrupted or unreadable files
                    continue
    
    # Split text into lines
    lines = text.split('\n')
    spacing = 5 # Fixed spacing between characters
    line_spacing = 10 # Spacing between lines
    
    # Calculate dimensions for each line
    line_data = []
    max_line_width = 0
    total_height = 0
    
    for line in lines:
        line_width = 0
        line_height = 0
        
        for char in line:
            # Map uppercase letters to their lookup key
            if char.isupper():
                char_lookup_key = char.lower() * 2
            else:
                char_lookup_key = char
            
            if char == ' ':
                # Calculate space width based on average char height (will refine later)
                line_width += 50 # placeholder
            elif char_lookup_key in char_images:
                img = char_images[char_lookup_key]
                line_width += img.width + spacing
                line_height = max(line_height, img.height)
        
        # Calculate effective space width for this line
        effective_space_width = int(line_height * space_width_ratio) if line_height > 0 else 25
        
        # Recalculate line width with proper space width
        final_line_width = 0
        for char in line:
            if char.isupper():
                char_lookup_key = char.lower() * 2
            else:
                char_lookup_key = char
            
            if char == ' ':
                final_line_width += effective_space_width
            elif char_lookup_key in char_images:
                final_line_width += char_images[char_lookup_key].width + spacing
        
        line_data.append({
            'text': line,
            'width': final_line_width,
            'height': line_height,
            'space_width': effective_space_width
        })
        
        max_line_width = max(max_line_width, final_line_width)
        total_height += line_height
    
    # Add spacing between lines
    if len(lines) > 1:
        total_height += line_spacing * (len(lines) - 1)
    
    if max_line_width == 0 or total_height == 0:
        return None
    
    # Create the stitched image at native size
    stitched_img = Image.new('RGBA', (max_line_width, total_height), (0, 0, 0, 0))
    
    # Render each line
    y_offset = 0
    for line_info in line_data:
        line = line_info['text']
        line_height = line_info['height']
        space_width = line_info['space_width']
        
        x_offset = 0
        for char in line:
            if char.isupper():
                char_lookup_key = char.lower() * 2
            else:
                char_lookup_key = char
            
            if char == ' ':
                x_offset += space_width
            elif char_lookup_key in char_images:
                img = char_images[char_lookup_key]
                stitched_img.paste(img, (x_offset, y_offset), img)
                x_offset += img.width + spacing
        
        y_offset += line_height + line_spacing
            
    # 2. Auto-calculate scale factor to fill canvas
    # Calculate scale factors for both width and height
    scale_w = canvas_width / stitched_img.width if stitched_img.width > 0 else 1.0
    scale_h = canvas_height / stitched_img.height if stitched_img.height > 0 else 1.0
    
    # Use the smaller scale factor to ensure the text fits entirely within canvas
    auto_scale = min(scale_w, scale_h)
    
    # Apply both user scale and auto scale
    final_scale = scale_factor * auto_scale
    
    scaled_w = int(stitched_img.width * final_scale)
    scaled_h = int(stitched_img.height * final_scale)
    
    # Use LANCZOS for high-quality resizing
    scaled_img = stitched_img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

    # 3. Create Final Canvas ("Resolution")
    final_canvas = Image.new('RGBA', (canvas_width, canvas_height), (0, 0, 0, 0))
    
    # Calculate position to center the scaled text on the canvas
    paste_x = max(0, (canvas_width - scaled_img.width) // 2)
    paste_y = max(0, (canvas_height - scaled_img.height) // 2)

    # Paste the scaled text onto the center of the fixed-size canvas
    final_canvas.paste(scaled_img, (paste_x, paste_y), scaled_img)
    
    # Save the final canvas
    final_canvas.save(output_path)
    return output_path, final_canvas # Return both path and PIL image object

# --- GUI Application Class ---

class TextStitcherApp:
    def __init__(self, master):
        self.master = master
        master.title("point_worldtext Text Generator")
        
        # Initialize theme manager
        if ThemeManager:
            self.theme_manager = ThemeManager()
            self.apply_theme()
        else:
            self.theme_manager = None
        
        # Set window icon
        try:
            icon_path = resource_path(os.path.join("icons", "text.ico"))
            if os.path.exists(icon_path):
                master.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        # Remove default title bar
        master.overrideredirect(True)
        
        # Window size and position
        window_width = 600
        window_height = 700
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        master.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        master.configure(bg=DARK_BG)
        
        # Variables for window dragging
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Create custom title bar first
        self.create_title_bar()
        
        # Create content frame
        content_frame = tk.Frame(master, bg=DARK_BG)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure the content frame grid
        content_frame.grid_rowconfigure(0, weight=0) # Text Label
        content_frame.grid_rowconfigure(1, weight=1) # Text Input Area
        content_frame.grid_rowconfigure(2, weight=0) # Settings Frame
        content_frame.grid_rowconfigure(3, weight=0) # Make Button
        content_frame.grid_rowconfigure(4, weight=2) # Image Display Frame
        content_frame.grid_rowconfigure(5, weight=0) # Save As Button
        content_frame.grid_rowconfigure(6, weight=0) # Status Label
        content_frame.grid_columnconfigure(0, weight=1)
        
        self.tk_img = None
        self.last_image_path = "stitched_output.png"
        self.last_pil_image = None
        
        # Create temp directory in user's temp folder (works for all users)
        system_temp = tempfile.gettempdir()
        self.temp_dir = os.path.join(system_temp, ".CS2KZ-mapping-tools")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.temp_output_path = os.path.join(self.temp_dir, "stitched_output.png")
        
        row_idx = 0
        
        # Create a list of valid resolutions
        self.valid_resolutions = [8 * (2**n) for n in range(11)]

        # 1. Text Entry Label
        tk.Label(content_frame, text="Enter Text to Stitch (Ctrl+Enter to generate):", 
                font=("Segoe UI", 10, "bold"),
                bg=DARK_BG, fg=DARK_TEXT).grid(row=row_idx, column=0, pady=(10, 0), padx=10, sticky="w")
        row_idx += 1
        
        # 2. Text Area (Chatbox style) - supports multiple lines
        self.text_input = tk.Text(content_frame, height=5, font=('Segoe UI', 12),
                                 bg=DARK_FRAME, fg=DARK_TEXT,
                                 insertbackground=DARK_TEXT,
                                 relief=tk.FLAT,
                                 highlightthickness=2,
                                 highlightbackground=DARK_BORDER,
                                 highlightcolor=ACCENT_ORANGE)
        self.text_input.grid(row=row_idx, column=0, padx=10, pady=5, sticky="nsew")
        row_idx += 1
        
        # Bind Ctrl+Enter to generate image (allow normal Enter for new lines)
        self.text_input.bind("<Control-Return>", self.make_image)
        
        # 3. Settings Frame
        settings_frame = tk.Frame(content_frame, bg=DARK_BG)
        settings_frame.grid(row=row_idx, column=0, pady=10)
        row_idx += 1
        
        # --- Scale Factor (Font Size) Control ---
        tk.Label(settings_frame, text="Font Scale (1.0 = native):", 
                font=("Segoe UI", 9),
                bg=DARK_BG, fg=DARK_TEXT).grid(row=0, column=0, columnspan=2, padx=5, sticky="w")
        self.scale_var = tk.DoubleVar(value=1.0)
        tk.Scale(settings_frame, from_=0.0, to=1.0, resolution=0.01, orient=tk.HORIZONTAL, 
                variable=self.scale_var, width=10, length=200,
                bg=DARK_BG, fg=DARK_TEXT, 
                troughcolor=DARK_FRAME, activebackground=ACCENT_ORANGE,
                highlightthickness=0).grid(row=0, column=2, columnspan=2, padx=5, sticky="ew")

        # --- Canvas Width Control ---
        tk.Label(settings_frame, text="Canvas Width (px, power of two):", 
                font=("Segoe UI", 9),
                bg=DARK_BG, fg=DARK_TEXT).grid(row=1, column=0, padx=5, sticky="w")
        self.width_var = tk.IntVar(value=1024)
        self.width_entry = tk.Spinbox(
            settings_frame, 
            values=self.valid_resolutions, 
            textvariable=self.width_var, 
            width=6,
            wrap=True,
            bg=DARK_FRAME, fg=DARK_TEXT,
            buttonbackground=DARK_BUTTON,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=DARK_BORDER
        )
        self.width_entry.grid(row=1, column=1, padx=5, sticky="w")
        self.width_entry.delete(0, tk.END)
        self.width_entry.insert(0, "1024")
        
        # --- Canvas Height Control ---
        tk.Label(settings_frame, text="Canvas Height (px, power of two):", 
                font=("Segoe UI", 9),
                bg=DARK_BG, fg=DARK_TEXT).grid(row=1, column=2, padx=5, sticky="w")
        self.height_var = tk.IntVar(value=1024)
        self.height_entry = tk.Spinbox(
            settings_frame, 
            values=self.valid_resolutions, 
            textvariable=self.height_var, 
            width=6,
            wrap=True,
            bg=DARK_FRAME, fg=DARK_TEXT,
            buttonbackground=DARK_BUTTON,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=DARK_BORDER
        )
        self.height_entry.grid(row=1, column=3, padx=5, sticky="w")
        self.height_entry.delete(0, tk.END)
        self.height_entry.insert(0, "1024")
        
        # 4. Make Button
        self.make_button = tk.Button(content_frame, text="Generate Image", command=lambda: self.make_image(None),
                                     bg=ACCENT_ORANGE, fg=DARK_TEXT,
                                     font=("Segoe UI", 10, "bold"),
                                     relief=tk.FLAT, cursor="hand2",
                                     activebackground="#e68900", activeforeground=DARK_TEXT,
                                     padx=20, pady=8)
        self.make_button.grid(row=row_idx, column=0, pady=10)
        row_idx += 1
        
        # 5. Image Display Frame
        self.img_frame = tk.Frame(content_frame, borderwidth=2, relief="groove",
                                 bg=DARK_FRAME, highlightbackground=DARK_BORDER,
                                 highlightthickness=2)
        self.img_frame.grid(row=row_idx, column=0, padx=10, pady=10, sticky="nsew")
        self.img_frame.grid_rowconfigure(0, weight=1)
        self.img_frame.grid_columnconfigure(0, weight=1)
        row_idx += 1
        
        # 6. Image Display Label
        self.img_label = tk.Label(self.img_frame, 
                                 text="Generated image will appear here.\nClick to open file.",
                                 bg=DARK_FRAME, fg=DARK_TEXT_SECONDARY,
                                 font=("Segoe UI", 10))
        self.img_label.grid(row=0, column=0, sticky="nsew")
        
        # Bind click and right-click events to the image label
        self.img_label.bind("<Button-1>", self.open_image_file) 
        self.img_label.bind("<Button-3>", self.show_context_menu)
        self.img_label.bind("<Button-2>", self.show_context_menu)
        
        # Bind the frame resize event to update the display image
        self.img_frame.bind('<Configure>', self._on_frame_resize)
        
        # 6b. Save As Button (initially hidden) - placed under the image display
        self.save_button = tk.Button(content_frame, text="Save As...", command=self.save_image_as,
                                     bg=ACCENT_GREEN, fg=DARK_TEXT,
                                     font=("Segoe UI", 10, "bold"),
                                     relief=tk.FLAT, cursor="hand2",
                                     activebackground="#45a049", activeforeground=DARK_TEXT,
                                     padx=20, pady=8)
        # Don't grid it yet - will show after image generation
        self.save_button_row = row_idx
        row_idx += 1
        
        # 7. Status Label
        self.status_label = tk.Label(content_frame, text="", 
                                     bg=DARK_BG, fg=ACCENT_BLUE,
                                     font=("Segoe UI", 9))
        self.status_label.grid(row=row_idx, column=0, pady=(0, 10))
        row_idx += 1

        # 8. Setup Context Menu
        self.context_menu = tk.Menu(self.master, tearoff=0,
                                   bg=DARK_BUTTON, fg=DARK_TEXT,
                                   activebackground=ACCENT_ORANGE, 
                                   activeforeground=DARK_TEXT)
        self.context_menu.add_command(label="Copy Image", command=self.copy_image_to_clipboard)
        
        # Start theme update checking
        if self.theme_manager:
            self.master.after(1000, self.check_theme_updates)
    
    def create_title_bar(self):
        """Create custom title bar"""
        title_bar = tk.Frame(self.master, bg=TITLE_BAR_BG, height=TITLE_BAR_HEIGHT)
        title_bar.pack(fill=tk.X, side=tk.TOP)
        title_bar.pack_propagate(False)
        
        # Bind drag events
        title_bar.bind("<Button-1>", self.start_drag)
        title_bar.bind("<B1-Motion>", self.on_drag)
        
        # Try to load and add icon to title bar
        try:
            icon_path = resource_path(os.path.join("icons", "text.ico"))
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
        title_label = tk.Label(title_bar, text="point_worldtext Text Generator", 
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
    
    def start_drag(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def on_drag(self, event):
        x = self.master.winfo_x() + event.x - self._drag_start_x
        y = self.master.winfo_y() + event.y - self._drag_start_y
        self.master.geometry(f"+{x}+{y}")
    
    def minimize_window(self):
        # Store window position before minimizing
        self.master.update_idletasks()
        x = self.master.winfo_x()
        y = self.master.winfo_y()
        
        # Temporarily disable overrideredirect to allow minimize
        self.master.overrideredirect(False)
        self.master.update_idletasks()
        
        # Minimize the window
        self.master.iconify()
        
        # When window is restored, re-enable overrideredirect and restore position
        def restore_overrideredirect():
            if self.master.state() == 'normal':
                self.master.overrideredirect(True)
                self.master.geometry(f"+{x}+{y}")
            else:
                # Check again later
                self.master.after(100, restore_overrideredirect)
        
        # Start checking for restore
        self.master.after(100, restore_overrideredirect)
    
    def close_window(self):
        self.master.destroy()
    
    def apply_theme(self):
        """Apply theme colors from theme manager"""
        if not self.theme_manager:
            return
        
        global DARK_BG, DARK_FRAME, DARK_BUTTON, DARK_BUTTON_HOVER, DARK_BORDER
        global DARK_TEXT, DARK_TEXT_SECONDARY, ACCENT_ORANGE, ACCENT_GREEN, ACCENT_BLUE, TITLE_BAR_BG
        
        theme = self.theme_manager.get_theme()
        
        # Convert RGB tuples to hex
        DARK_BG = self.theme_manager.to_hex(theme['window_bg'])
        TITLE_BAR_BG = self.theme_manager.to_hex(theme['title_bar_bg'])
        DARK_FRAME = self.theme_manager.to_hex(theme['title_bar_bg'])
        DARK_BUTTON = self.theme_manager.to_hex(theme['button'])
        DARK_BUTTON_HOVER = self.theme_manager.to_hex(theme['button_hover'])
        DARK_BORDER = self.theme_manager.to_hex(theme['border'])
        DARK_TEXT = self.theme_manager.to_hex(theme['text'])
        DARK_TEXT_SECONDARY = self.theme_manager.to_hex(theme['text'])
        ACCENT_ORANGE = self.theme_manager.to_hex(theme['accent'])
        ACCENT_GREEN = self.theme_manager.to_hex(theme['button_active'])
        ACCENT_BLUE = self.theme_manager.to_hex(theme['accent'])
        
        # Update master window background
        if hasattr(self, 'master'):
            self.master.configure(bg=DARK_BG)
            
            # Update title bar widgets if they exist
            for widget in self.master.winfo_children():
                if isinstance(widget, tk.Frame) and widget.winfo_height() == TITLE_BAR_HEIGHT:
                    # Found title bar
                    widget.configure(bg=TITLE_BAR_BG)
                    # Update all child widgets in title bar
                    for child in widget.winfo_children():
                        if isinstance(child, (tk.Label, tk.Button)):
                            try:
                                child.configure(bg=TITLE_BAR_BG, fg=DARK_TEXT)
                            except:
                                pass
    
    def check_theme_updates(self):
        """Check for theme updates and reapply if changed"""
        if self.theme_manager and self.theme_manager.check_for_updates():
            self.apply_theme()
        
        # Schedule next check
        if hasattr(self, 'master'):
            self.master.after(1000, self.check_theme_updates)

    def _update_display_image(self, width, height):
        """Resizes the last generated image to fit the given dimensions for preview."""
        if not self.last_pil_image:
            self.img_label.config(text="Generated image will appear here.\nClick to open file.", 
                                image="",
                                bg=DARK_FRAME, fg=DARK_TEXT_SECONDARY)
            self.tk_img = None
            return

        # The image to display is the LAST GENERATED one (the scaled/canvased output)
        source_img = self.last_pil_image
        w, h = source_img.size
        
        if w > 0 and h > 0 and width > 0 and height > 0:
            # Calculate ratio to fit inside the frame while maintaining aspect ratio
            ratio_w = width / w
            ratio_h = height / h
            ratio = min(ratio_w, ratio_h)
            
            # If the image is smaller than the frame, display it at its native size (ratio capped at 1.0)
            if ratio > 1.0:
                 ratio = 1.0

            new_w = max(1, int(w * ratio))
            new_h = max(1, int(h * ratio))

            if new_w > 0 and new_h > 0:
                # Use ANTIALIAS/LANCZOS for high-quality resizing
                display_img = source_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(display_img)
                self.img_label.config(image=self.tk_img, text="")
            else:
                self.img_label.config(text="Generated image is too large/small to display.", image="")
                self.tk_img = None
        else:
            self.img_label.config(text="Generated image will appear here.\nClick to open file.", image="")
            self.tk_img = None

    def _on_frame_resize(self, event):
        """Called when the image display frame size changes."""
        # Only proceed if the width or height of the event is valid (sometimes configure fires with 1x1)
        if event.width > 1 and event.height > 1:
            self._update_display_image(event.width, event.height)

    def open_image_file(self, event=None):
        """Opens the last generated PNG file in the default system application."""
        if self.last_image_path and os.path.exists(self.last_image_path):
            try:
                # Platform-specific commands to open the file
                if sys.platform == "win32":
                    os.startfile(self.last_image_path)
                elif sys.platform == "darwin": # macOS
                    subprocess.call(("open", self.last_image_path))
                else: # Linux
                    subprocess.call(("xdg-open", self.last_image_path))
                
                self.status_label.config(text=f"Opened: {self.last_image_path}", fg="blue")
            except Exception as e:
                self.status_label.config(text=f"Error opening file: {e}", fg="red")
        else:
            self.status_label.config(text="No image generated yet.", fg="red")

    def copy_image_to_clipboard(self):
        """Copies the generated PIL image object to the system clipboard."""
        if self.last_pil_image:
            try:
                self.last_pil_image.copy()
                self.status_label.config(text="Image copied to clipboard!", fg="green")
            except Exception as e:
                messagebox.showerror("Copy Error", "Failed to copy image to clipboard. Ensure you have the necessary system components installed (e.g., xclip on Linux).")
                self.status_label.config(text="Failed to copy image.", fg="red")
        else:
            self.status_label.config(text="No image to copy.", fg="red")
    
    def save_image_as(self):
        """Opens a file dialog to save the generated image to a chosen location."""
        if not self.last_pil_image:
            self.status_label.config(text="No image to save. Generate an image first.", fg="red")
            return
        
        # Open save dialog
        file_path = filedialog.asksaveasfilename(
            title="Save Image As",
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                self.last_pil_image.save(file_path)
                
                # Create alpha mask: Convert alpha channel to grayscale
                # Extract the alpha channel from the saved image
                alpha_channel = self.last_pil_image.split()[3]  # RGBA - index 3 is alpha
                
                # Create RGB image from the alpha channel (grayscale representation)
                alpha_mask = Image.new('RGB', self.last_pil_image.size, (0, 0, 0))
                alpha_mask.paste(alpha_channel, mask=None)
                
                # Save alpha mask with _alpha suffix
                base_path, ext = os.path.splitext(file_path)
                alpha_mask_path = f"{base_path}_alpha{ext}"
                alpha_mask.save(alpha_mask_path)
                
                self.status_label.config(text=f"Image and alpha mask saved to {os.path.dirname(file_path)}", fg="green")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save image: {e}")
                self.status_label.config(text="Failed to save image.", fg="red")
            
    def show_context_menu(self, event):
        """Displays the right-click context menu."""
        if self.last_pil_image:
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

    def make_image(self, event):
        """Generates the image from the input text."""
        # Get text, keeping newlines for multiple rows
        text_to_stitch = self.text_input.get("1.0", tk.END).rstrip('\n')  # Keep internal newlines, remove trailing
            
        if not text_to_stitch:
            self.status_label.config(text="Please enter some text.", fg="red")
            return "break" if event else None

        scale_factor = self.scale_var.get()
        
        try:
            canvas_width = self.width_var.get()
            canvas_height = self.height_var.get()
        except tk.TclError:
            # This handles cases where the user might manually type a non-integer or invalid value
            messagebox.showerror("Resolution Error", "Canvas dimensions must be valid integers from the list of options.")
            return "break" if event else None

        # Input validation: Check if the entered value is in the predetermined list.
        # This is a stronger check than just checking for multiples of 8.
        if canvas_width not in self.valid_resolutions or canvas_height not in self.valid_resolutions:
            messagebox.showerror("Resolution Error", "Canvas Width and Height must be selected from the predefined list (8, 16, 32, 64, etc.).")
            # Attempt to reset to a valid value if possible
            if canvas_width not in self.valid_resolutions:
                 self.width_var.set(1024)
            if canvas_height not in self.valid_resolutions:
                 self.height_var.set(1024)
            return "break" if event else None

        # Use temp directory for temporary output
        self.last_image_path = self.temp_output_path
        
        try:
            self.status_label.config(text="Stitching text...")
            self.master.update()

            # Get chars folder path using resource_path for PyInstaller compatibility
            chars_path = resource_path("chars")
            
            result = stitch_text(
                text_to_stitch,
                chars_folder=chars_path,
                output_path=self.last_image_path,
                scale_factor=scale_factor,
                canvas_width=canvas_width,
                canvas_height=canvas_height
            )
            
            if result:
                result_path, self.last_pil_image = result

                # Get current frame size and update the display image
                frame_w = self.img_frame.winfo_width()
                frame_h = self.img_frame.winfo_height()
                
                # Force update if the frame size is available
                if frame_w > 1 and frame_h > 1:
                    self._update_display_image(frame_w, frame_h)
                
                # Show the Save As button after successful generation
                self.save_button.grid(row=self.save_button_row, column=0, pady=5)
                
                self.status_label.config(text=f"Image generated at {canvas_width}x{canvas_height}. Click 'Save As' to save.", fg="green")
            else:
                self.status_label.config(text="Could not stitch text (no characters found).", fg="red")

        except FileNotFoundError:
            messagebox.showerror("Error", "The 'chars' folder or character files were not found. Ensure you have run character extraction previously.")
            self.status_label.config(text="Error: Characters folder missing.", fg="red")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during stitching: {e}")
            self.status_label.config(text="Stitching Failed.", fg="red")

        return "break" if event else None # Prevents Tkinter's default Enter action

# --- Main Execution Block ---

if __name__ == "__main__":
    # If run from command line with 'extract' argument, run the extraction logic
    if len(sys.argv) > 1 and sys.argv[1] == "extract":
        if len(sys.argv) < 3:
            print("Usage: python s.py extract <image_path>")
            sys.exit(1)
        
        try:
            print(f"Starting extraction for: {sys.argv[2]}")
            extract_characters(sys.argv[2])
            print("Extraction complete. Character files saved in the 'chars' folder.")
            sys.exit(0)
        except FileNotFoundError:
            print(f"Error: Input file not found at {sys.argv[2]}")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred during extraction: {e}")
            sys.exit(1)
            
    # Default: Start the GUI application
    try:
        from PIL import ImageTk
    except ImportError:
        print("Error: Pillow is not installed or incorrectly configured. Please run: pip install Pillow")
        sys.exit(1)

    root = tk.Tk()
    app = TextStitcherApp(root)
    root.mainloop()
