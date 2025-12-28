"""
Shared theme manager for all GUI tools
Reads theme from main app's settings and provides theme colors
"""
import json
import os
import tempfile
import time

class ThemeManager:
    """Manager to read and monitor theme from main app settings"""
    
    # Font configuration for each theme
    FONTS = {
        'dracula': 'Roboto-Regular.ttf',  # Dracula uses Roboto
        'default': 'Roboto-Regular.ttf'    # All other themes use Roboto
    }
    
    # Dracula theme colors (ImGui format: R, G, B, A as 0.0-1.0)
    THEMES = {
        'grey': {
            'window_bg': (0.1, 0.1, 0.1, 1.0),
            'title_bar_bg': (0.12, 0.12, 0.12, 1.0),
            'button': (0.29, 0.29, 0.29, 1.0),
            'button_hover': (0.35, 0.35, 0.35, 1.0),
            'button_active': (0.40, 0.40, 0.40, 1.0),
            'border': (0.40, 0.40, 0.40, 1.0),
            'text': (1.0, 1.0, 1.0, 1.0),
            'accent': (1.0, 0.6, 0.0, 1.0)
        },
        'black': {
            'window_bg': (0.0, 0.0, 0.0, 1.0),
            'title_bar_bg': (0.02, 0.02, 0.02, 1.0),
            'button': (0.15, 0.15, 0.15, 1.0),
            'button_hover': (0.20, 0.20, 0.20, 1.0),
            'button_active': (0.25, 0.25, 0.25, 1.0),
            'border': (0.30, 0.30, 0.30, 1.0),
            'text': (1.0, 1.0, 1.0, 1.0),
            'accent': (1.0, 0.6, 0.0, 1.0)
        },
        'white': {
            'window_bg': (0.94, 0.94, 0.94, 1.0),
            'title_bar_bg': (0.90, 0.90, 0.90, 1.0),
            'button': (0.75, 0.75, 0.75, 1.0),
            'button_hover': (0.70, 0.70, 0.70, 1.0),
            'button_active': (0.65, 0.65, 0.65, 1.0),
            'border': (0.60, 0.60, 0.60, 1.0),
            'text': (0.1, 0.1, 0.1, 1.0),
            'accent': (1.0, 0.6, 0.0, 1.0)
        },
        'dracula': {
            'window_bg': (0.157, 0.165, 0.212, 1.0),
            'title_bar_bg': (0.121, 0.129, 0.173, 1.0),
            'button': (0.271, 0.282, 0.353, 1.0),
            'button_hover': (0.506, 0.475, 0.702, 1.0),
            'button_active': (0.380, 0.345, 0.580, 1.0),
            'border': (0.380, 0.396, 0.486, 1.0),
            'text': (0.973, 0.973, 0.949, 1.0),
            'accent': (0.506, 0.475, 0.702, 1.0)
        },
        'pink': {
            'window_bg': (0.25, 0.12, 0.18, 1.0),
            'title_bar_bg': (0.20, 0.10, 0.15, 1.0),
            'button': (0.55, 0.25, 0.40, 1.0),
            'button_hover': (0.65, 0.30, 0.48, 1.0),
            'button_active': (0.75, 0.35, 0.55, 1.0),
            'border': (0.80, 0.40, 0.60, 1.0),
            'text': (1.0, 0.95, 0.98, 1.0),
            'accent': (1.0, 0.4, 0.7, 1.0)
        },
        'orange': {
            'window_bg': (0.25, 0.15, 0.08, 1.0),
            'title_bar_bg': (0.20, 0.12, 0.06, 1.0),
            'button': (0.60, 0.35, 0.15, 1.0),
            'button_hover': (0.70, 0.40, 0.18, 1.0),
            'button_active': (0.80, 0.45, 0.20, 1.0),
            'border': (0.85, 0.50, 0.25, 1.0),
            'text': (1.0, 0.98, 0.95, 1.0),
            'accent': (1.0, 0.6, 0.0, 1.0)
        },
        'blue': {
            'window_bg': (0.08, 0.12, 0.25, 1.0),
            'title_bar_bg': (0.06, 0.10, 0.20, 1.0),
            'button': (0.20, 0.30, 0.60, 1.0),
            'button_hover': (0.25, 0.35, 0.70, 1.0),
            'button_active': (0.30, 0.40, 0.80, 1.0),
            'border': (0.35, 0.45, 0.85, 1.0),
            'text': (0.95, 0.98, 1.0, 1.0),
            'accent': (0.3, 0.5, 1.0, 1.0)
        },
        'red': {
            'window_bg': (0.25, 0.08, 0.08, 1.0),
            'title_bar_bg': (0.20, 0.06, 0.06, 1.0),
            'button': (0.60, 0.20, 0.20, 1.0),
            'button_hover': (0.70, 0.25, 0.25, 1.0),
            'button_active': (0.80, 0.30, 0.30, 1.0),
            'border': (0.85, 0.35, 0.35, 1.0),
            'text': (1.0, 0.95, 0.95, 1.0),
            'accent': (1.0, 0.3, 0.3, 1.0)
        },
        'green': {
            'window_bg': (0.08, 0.18, 0.08, 1.0),
            'title_bar_bg': (0.06, 0.15, 0.06, 1.0),
            'button': (0.20, 0.50, 0.20, 1.0),
            'button_hover': (0.25, 0.60, 0.25, 1.0),
            'button_active': (0.30, 0.70, 0.30, 1.0),
            'border': (0.35, 0.75, 0.35, 1.0),
            'text': (0.95, 1.0, 0.95, 1.0),
            'accent': (0.3, 1.0, 0.3, 1.0)
        },
        'yellow': {
            'window_bg': (0.5, 0.5, 0.00, 1.0),
            'title_bar_bg': (0.4, 0.4, 0.00, 1.0),
            'button': (0.60, 0.55, 0.15, 1.0),
            'button_hover': (0.70, 0.65, 0.20, 1.0),
            'button_active': (0.80, 0.75, 0.25, 1.0),
            'border': (0.85, 0.80, 0.30, 1.0),
            'text': (1.0, 1.0, 0.90, 1.0),
            'accent': (1.0, 1.0, 0.0, 1.0)
        }
    }
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
        self.app_dir = os.path.join(self.temp_dir, '.CS2KZ-mapping-tools')
        self.settings_file = os.path.join(self.app_dir, 'settings.json')
        self.last_mtime = 0
        self.current_theme = 'grey'
        self._load_theme()
    
    def _load_theme(self):
        """Load theme from settings file"""
        try:
            if os.path.exists(self.settings_file):
                # Check if file has content
                if os.path.getsize(self.settings_file) == 0:
                    # Empty file, use default theme
                    self.current_theme = 'grey'
                    return
                
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    theme = settings.get('appearance_mode', 'grey')
                    if theme in self.THEMES:
                        self.current_theme = theme
                    self.last_mtime = os.path.getmtime(self.settings_file)
        except json.JSONDecodeError:
            # Invalid JSON, use default theme silently
            self.current_theme = 'grey'
        except Exception as e:
            # Other errors, print but use default
            print(f"Error loading theme: {e}")
            self.current_theme = 'grey'
    
    def check_for_updates(self):
        """Check if theme has been updated"""
        try:
            if os.path.exists(self.settings_file):
                mtime = os.path.getmtime(self.settings_file)
                if mtime > self.last_mtime:
                    self._load_theme()
                    return True
        except Exception:
            pass
        return False
    
    def get_theme(self):
        """Get current theme colors"""
        return self.THEMES.get(self.current_theme, self.THEMES['grey'])
    
    def get_theme_name(self):
        """Get current theme name"""
        return self.current_theme
    
    def get_font(self):
        """Get font filename for current theme"""
        return self.FONTS.get(self.current_theme, self.FONTS['default'])
    
    def to_hex(self, rgb_tuple):
        """Convert RGB tuple (0-1) to hex color"""
        r = int(rgb_tuple[0] * 255)
        g = int(rgb_tuple[1] * 255)
        b = int(rgb_tuple[2] * 255)
        return f'#{r:02x}{g:02x}{b:02x}'
