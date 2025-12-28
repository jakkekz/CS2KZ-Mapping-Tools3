"""
CS2 Sounds Manager - PyImGui Interface
Simplifies adding custom sounds to CS2 maps.
"""

import imgui
import glfw
from imgui.integrations.glfw import GlfwRenderer
import OpenGL.GL as gl
import sys
import subprocess
import os
import re
import shutil
import tempfile
import winreg
import vdf
from tkinter import filedialog
import tkinter as tk
from PIL import Image
import threading
import urllib.request
import zipfile
import io

# Try to import optional modules
try:
    import vpk
except ImportError:
    print("Warning: vpk module not available. Install with: pip install python-vpk")
    vpk = None

try:
    import pygame
except ImportError:
    print("Warning: pygame module not available. Install with: pip install pygame")
    pygame = None

# Try to import VSND decompiler
try:
    from vsnd_decompiler import VSNDDecompiler
    VSND_DECOMPILER = VSNDDecompiler()
except Exception as e:
    print(f"Warning: VSND decompiler not available: {e}")
    VSND_DECOMPILER = None

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


class SoundsManagerApp:
    def __init__(self):
        self.window = None
        self.impl = None
        
        # Theme manager
        self.theme_manager = ThemeManager()
        
        # Application state
        self.cs2_basefolder = None
        self.addon_name = ""
        
        # Sound source toggle
        self.use_internal_sound = False  # False = custom file, True = internal CS2 sound
        
        # Custom sound file
        self.sound_file_path = ""
        self.sound_file_display = "None selected"
        self.sound_name = ""  # Name for the soundevent (without extension)
        self.output_name = ""  # User-editable output name for the sound file
        
        # Internal sound browser
        self.internal_sounds = []  # List of internal sound paths from VPK
        self.internal_sounds_tree = {}  # Hierarchical structure for tree display
        self.internal_sounds_loaded = False
        self.loading_internal_sounds = False
        self.selected_internal_sound = ""
        self.internal_sound_filter = ""
        self.filtered_internal_sounds = []
        self.cached_internal_sound_path = ""  # Path to cached/decompiled internal sound WAV
        
        # Audio preview (pygame mixer)
        self.preview_sound = None
        self.preview_playing = False
        self.preview_volume = 0.5  # Default preview volume at 50%
        if pygame:
            try:
                pygame.mixer.init()
                pygame.mixer.music.set_volume(self.preview_volume)
            except Exception as e:
                print(f"Warning: pygame mixer initialization failed: {e}")
                pygame = None
        
        # VSND decompiler for internal sound preview
        self.vsnd_decompiler = None
        try:
            from vsnd_decompiler import VSNDDecompiler
            self.vsnd_decompiler = VSNDDecompiler()
        except Exception as e:
            print(f"Note: VSND decompiler not available: {e}")
            print("  Internal sound preview requires .NET Desktop Runtime 8.0")
            print("  Download: https://dotnet.microsoft.com/download/dotnet/8.0/runtime")
        
        # Addon autocomplete
        self.available_addons = []
        self.filtered_addons = []
        self.show_addon_dropdown = False
        self.selected_addon_index = -1
        self.addon_just_selected = False  # Flag to force input update
        
        # Sound parameters with default values
        self.sound_type = "csgo_mega"  # Default sound type
        self.volume = 1.0
        self.pitch = 1.0
        self.distance_near = 0.0
        self.distance_near_volume = 1.0
        self.distance_mid = 1000.0
        self.distance_mid_volume = 0.5
        self.distance_far = 3000.0
        self.distance_far_volume = 0.0
        self.occlusion_intensity = 100.0
        
        # Curve points (Bézier control points for smooth interpolation)
        # Near to Mid curve points
        self.curve_near_mid_cp1 = 0.0
        self.curve_near_mid_cp2 = 0.0
        self.curve_near_mid_cp3 = 1.0
        self.curve_near_mid_cp4 = 1.0
        # Mid to Far curve points
        self.curve_mid_far_cp1 = 0.0
        self.curve_mid_far_cp2 = 0.0
        self.curve_mid_far_cp3 = 1.0
        self.curve_mid_far_cp4 = 1.0
        
        # Toggle states for UI controls
        self.show_pitch = False  # Default: hidden
        self.show_occlusion = False  # Default: hidden
        self.show_visualizer = False  # Default: hidden
        self.show_curve_editor = False  # Default: hidden
        self.use_wav_markers = False  # Default: no encoding.txt
        
        # Audio timeline and loop points
        self.audio_duration_ms = 0  # Duration of loaded audio in milliseconds
        self.audio_waveform = []  # Simplified waveform data for visualization
        self.playback_position_ms = 0  # Current playback position
        self.playback_start_time = 0  # Time when playback started
        self.timeline_width = 550  # Width of timeline visualization (wider)
        self.timeline_height = 100  # Height of timeline visualization
        self.temp_loop_file = None  # Path to temporary loop preview file
        
        # encoding.txt configuration options
        self.encoding_format = "mp3"  # Compression format: "PCM", "mp3", "adpcm"
        self.encoding_minbitrate = 128  # MP3 minimum bitrate
        self.encoding_maxbitrate = 320  # MP3 maximum bitrate
        self.encoding_vbr = True  # Variable bitrate for MP3
        self.encoding_sample_rate = 0  # Sample rate (0 = auto)
        
        # Normalization settings
        self.encoding_normalize = False  # Enable normalization
        self.encoding_normalize_level = -3.0  # Target level in dB
        self.encoding_normalize_compression = False  # Enable compression
        self.encoding_normalize_limiter = False  # Enable limiter
        
        # Loop point settings (part of encoding.txt)
        self.encoding_loop_enabled = False  # Whether loop points are active
        self.encoding_loop_start_ms = 0  # Loop start position in milliseconds
        self.encoding_loop_end_ms = 0  # Loop end position in milliseconds
        self.dragging_loop_start = False  # Whether user is dragging loop start marker
        self.dragging_loop_end = False  # Whether user is dragging loop end marker
        self.encoding_crossfade_ms = 1  # Crossfade duration in milliseconds
        
        # ffmpeg download state (needed for MP3 to WAV conversion)
        self.ffmpeg_path = None  # Path to ffmpeg.exe
        self.downloading_ffmpeg = False  # Whether ffmpeg download is in progress
        
        # UI state
        self.sound_status_color = (1.0, 0.0, 0.0, 1.0)    # Red initially
        
        # Custom title bar drag state
        self.dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Console output
        self.console_output = []
        self.last_console_line_count = 0
        
        # Icon textures
        self.title_icon = None
        self.play_icon = None
        self.pause_icon = None
        
        # Cursors (will be created after window initialization)
        self.arrow_cursor = None
        self.hand_cursor = None
        
        # Theme tracking
        self.current_theme_name = self.theme_manager.get_theme_name()
        
        # Detect CS2 path
        self.detect_cs2_path()
        
        # Check if ffmpeg already exists (don't download, just check)
        # MUST have BOTH ffmpeg.exe and ffprobe.exe (pydub needs both)
        ffmpeg_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp', '.CS2KZ-mapping-tools', 'Sounds', 'ffmpeg')
        ffmpeg_path = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
        ffprobe_path = os.path.join(ffmpeg_dir, 'ffprobe.exe')
        if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
            self.ffmpeg_path = ffmpeg_path
            # Configure environment for pydub (add ffmpeg directory to PATH)
            try:
                ffmpeg_dir_path = os.path.dirname(ffmpeg_path)
                # Add ffmpeg directory to PATH so pydub can find it
                if 'PATH' in os.environ:
                    os.environ['PATH'] = ffmpeg_dir_path + os.pathsep + os.environ['PATH']
                else:
                    os.environ['PATH'] = ffmpeg_dir_path
                print(f"✓ Added ffmpeg to PATH: {ffmpeg_dir_path}")
            except Exception as e:
                print(f"⚠ ffmpeg PATH configuration warning: {e}")
        
        # Clean up old preview cache on startup
        cache_dir = os.path.join(tempfile.gettempdir(), '.CS2KZ-mapping-tools', 'Sounds', 'preview')
        if os.path.exists(cache_dir):
            self.cleanup_preview_cache(cache_dir, max_files=5)
        
        # Window dimensions - will be adjusted dynamically based on content
        self.window_width = 900  # Adjusted for narrower left panel
        self.base_window_width = 900  # Base width without visualizer
        self.visualizer_width = 350  # Width of the visualizer panel
        self.left_panel_width = 300  # Narrower since we show only filenames now
        self.right_panel_width = 600  # window_width - left_panel_width
        self.content_height = 0  # Will be calculated during first render
        self.base_window_height = 800  # Initial height, will scale dynamically based on content
    
    def detect_cs2_path(self):
        """Detect CS2 installation path from Steam"""
        try:
            # Read Steam path from registry
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                    steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            except FileNotFoundError:
                self.log("✗ Steam installation not found in registry")
                return False
            
            # Read libraryfolders.vdf to find CS2
            libraryfolders_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
            if not os.path.exists(libraryfolders_path):
                self.log("✗ Steam library folders not found")
                return False
            
            with open(libraryfolders_path, 'r', encoding='utf-8') as file:
                library_data = vdf.load(file)
            
            # Find CS2 (appid 730)
            cs2_library_path = None
            if 'libraryfolders' in library_data:
                for _, folder in library_data['libraryfolders'].items():
                    if 'apps' in folder and '730' in folder['apps']:
                        cs2_library_path = folder['path']
                        break
            
            if not cs2_library_path:
                self.log("✗ CS2 installation not found in Steam libraries")
                return False
            
            self.cs2_basefolder = os.path.join(cs2_library_path, 'steamapps', 'common', 'Counter-Strike Global Offensive')
            
            if os.path.exists(self.cs2_basefolder):
                self.log(f"✓ CS2 detected at: {self.cs2_basefolder}")
                return True
            else:
                self.log(f"✗ CS2 folder not found at {self.cs2_basefolder}")
                return False
                
        except Exception as e:
            self.log(f"✗ Error detecting CS2 path: {e}")
            return False
    
    def scan_available_addons(self):
        """Scan for available addons in csgo_addons folder"""
        if not self.cs2_basefolder:
            return []
        
        addons_path = os.path.join(self.cs2_basefolder, 'content', 'csgo_addons')
        if not os.path.exists(addons_path):
            return []
        
        try:
            # Get all directories in csgo_addons
            addons = [d for d in os.listdir(addons_path) 
                     if os.path.isdir(os.path.join(addons_path, d))]
            return sorted(addons)
        except Exception as e:
            self.log(f"✗ Error scanning addons: {e}")
            return []
    
    def load_internal_sounds(self):
        """Load internal CS2 sounds from VPK in background thread"""
        if not self.cs2_basefolder:
            self.log("✗ CS2 path not detected")
            return
        
        self.loading_internal_sounds = True
        self.log("Loading internal CS2 sounds from VPK...")
        
        def load_thread():
            try:
                pak_path = os.path.join(self.cs2_basefolder, 'game', 'csgo', 'pak01_dir.vpk')
                if not os.path.exists(pak_path):
                    self.log(f"✗ VPK not found at: {pak_path}")
                    self.loading_internal_sounds = False
                    return
                
                # Open VPK
                pak = vpk.open(pak_path)
                
                # Extract all sound paths
                sounds = []
                vsnd_count = 0
                for filepath in pak:
                    # Look for vsnd_c files (compiled sounds)
                    if filepath.endswith('.vsnd_c'):
                        vsnd_count += 1
                        # Check if it's in sounds folder (use backslash for Windows paths)
                        if 'sounds' in filepath.lower():
                            # Remove .vsnd_c extension for display
                            sound_path = filepath.replace('.vsnd_c', '')
                            # Strip "sounds/" prefix to avoid redundant root folder in tree
                            if sound_path.lower().startswith('sounds/'):
                                sound_path = sound_path[7:]  # Remove "sounds/" (7 characters)
                            sounds.append(sound_path)
                
                self.internal_sounds = sorted(sounds)
                self.filtered_internal_sounds = self.internal_sounds
                self.internal_sounds_loaded = True
                self.loading_internal_sounds = False
                self.log(f"✓ Loaded {len(sounds)} internal sounds")
                
            except Exception as e:
                self.log(f"✗ Error loading internal sounds: {e}")
                self.loading_internal_sounds = False
        
        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()
    
    def filter_internal_sounds(self, search_text):
        """Filter internal sounds based on search text"""
        if not search_text:
            self.filtered_internal_sounds = self.internal_sounds
        else:
            search_lower = search_text.lower()
            self.filtered_internal_sounds = [
                sound for sound in self.internal_sounds
                if search_lower in sound.lower()
            ]
    
    def cleanup_preview_cache(self, cache_dir, max_files=5, make_room_for_new=False):
        """Keep only the most recent N preview files in cache"""
        try:
            if not os.path.exists(cache_dir):
                return
                
            # Get all files in cache directory (audio files with or without extensions)
            cache_files = []
            try:
                for f in os.listdir(cache_dir):
                    file_path = os.path.join(cache_dir, f)
                    # Only include files (not directories)
                    if os.path.isfile(file_path):
                        cache_files.append(file_path)
            except Exception as e:
                print(f"Warning: Could not list cache directory: {e}")
                return
            
            # Debug: show what we found
            if cache_files:
                print(f"🔍 Found {len(cache_files)} files in cache")
            
            # Determine how many files to keep
            if make_room_for_new:
                # Keep max_files - 1 to make room for incoming file
                target_count = max_files - 1
            else:
                # Keep exactly max_files
                target_count = max_files
            
            # If we have more than target, delete oldest
            if len(cache_files) > target_count:
                # Sort by modification time (oldest first)
                cache_files.sort(key=lambda f: os.path.getmtime(f))
                
                # Delete oldest files
                files_to_delete = len(cache_files) - target_count
                for file_path in cache_files[:files_to_delete]:
                    try:
                        os.remove(file_path)
                        print(f"🗑 Removed old cache: {os.path.basename(file_path)}")
                    except Exception as e:
                        print(f"Warning: Could not delete cache file {file_path}: {e}")
        except Exception as e:
            print(f"Warning: Cache cleanup failed: {e}")
    
    def preview_internal_sound(self):
        """Extract and play internal CS2 sound using .NET Core decompiler"""
        if not pygame:
            self.log("✗ pygame not available. Install with: pip install pygame")
            return
        
        if not self.selected_internal_sound:
            self.log("✗ No sound selected for preview")
            return
        
        # Try to use vsnd_decompiler with .NET Core
        if self.vsnd_decompiler:
            try:
                # Build paths
                vpk_path = os.path.join(self.cs2_basefolder, 'game', 'csgo', 'pak01_dir.vpk')
                # The selected sound is stored without "sounds/" prefix, add it back for VPK lookup
                internal_path = 'sounds/' + self.selected_internal_sound + '.vsnd_c'
                # Keep forward slashes for VPK (it uses forward slashes internally)
                internal_path = internal_path.replace('\\', '/')
                
                # Create cache directory
                cache_dir = os.path.join(tempfile.gettempdir(), '.CS2KZ-mapping-tools', 'Sounds', 'preview')
                os.makedirs(cache_dir, exist_ok=True)
                
                # Build output path (decompiler outputs files without extensions)
                sound_name = os.path.basename(self.selected_internal_sound)
                output_path = os.path.join(cache_dir, sound_name)
                
                # Clean up any old cache files (from previous runs with incorrect logic)
                # We'll regenerate them with proper MP3→WAV conversion
                for ext in ['.wav', '.mp3', '']:
                    old_file = output_path + ext
                    if os.path.exists(old_file):
                        try:
                            # Try to verify if it's a valid WAV by checking conversion timestamp
                            # For now, just delete and regenerate to ensure consistency
                            os.remove(old_file)
                        except:
                            pass
                
                # Clean up old cache files before adding new one (make room for the new file)
                self.cleanup_preview_cache(cache_dir, max_files=5, make_room_for_new=True)
                
                self.log(f"⏳ Decompiling {self.selected_internal_sound}...")
                
                # Decompile from VPK
                decompiled_path = self.vsnd_decompiler.decompile_vsnd(
                    vpk_path=vpk_path,
                    internal_sound_path=internal_path,
                    output_path=output_path
                )
                
                if decompiled_path and os.path.exists(decompiled_path):
                    # Decompiler outputs MP3 files without extension
                    # Just rename to .mp3 and use as-is (conversion on-demand during loop playback)
                    if not os.path.splitext(decompiled_path)[1]:
                        mp3_path = decompiled_path + '.mp3'
                        os.rename(decompiled_path, mp3_path)
                        decompiled_path = mp3_path
                        self.log(f"    Renamed to .mp3")
                    
                    self.cached_internal_sound_path = decompiled_path
                    self.analyze_audio_file(decompiled_path)  # Analyze for waveform and loop
                    self.play_sound_file(decompiled_path)
                else:
                    self.log("✗ Failed to decompile sound")
                    self.log("ℹ Internal sound preview requires .NET Desktop Runtime 8.0")
                    self.log("  Download: https://dotnet.microsoft.com/download/dotnet/8.0")
                    self.log("  Click 'Download x64' under '.NET Desktop Runtime 8.0'")
                    self.log("  The sound will still work in-game when you click 'Add Sound'")
                    
            except Exception as e:
                error_str = str(e)
                if "MemoryMarshal" in error_str or "TypeLoadException" in error_str:
                    self.log("✗ .NET 8 Desktop Runtime is required for internal sound preview")
                    self.log("  Download: https://dotnet.microsoft.com/download/dotnet/8.0")
                    self.log("  Click 'Download x64' under '.NET Desktop Runtime 8.0'")
                    self.log("  The sound will still work in-game when you click 'Add Sound'")
                else:
                    self.log(f"✗ Error previewing sound: {e}")
                    import traceback
                    traceback.print_exc()
        else:
            # Fallback message if decompiler not available
            self.log("ℹ Internal sound preview requires .NET Desktop Runtime 8.0")
            self.log("  Download: https://dotnet.microsoft.com/download/dotnet/8.0")
            self.log("  The sound will still work in-game when you click 'Add Sound'")
            self.log(f"  Selected: {self.selected_internal_sound}")
    
    
    def play_sound_file(self, file_path):
        """Play audio file using pygame with pitch adjustment and loop points"""
        try:
            # Check if it's a large MP3 file (pygame has issues with large MP3s)
            is_large_mp3 = False
            actual_play_path = file_path
            
            if file_path.lower().endswith('.mp3'):
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                if file_size_mb > 5:  # Over 5MB
                    is_large_mp3 = True
                    self.log(f"  Large MP3 detected ({file_size_mb:.1f}MB), converting to WAV for playback...")
                    
                    # Check if ffmpeg is available
                    if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
                        self.log(f"  ⏳ ffmpeg required for large MP3 conversion, downloading...")
                        self.download_ffmpeg()
                        self.log(f"  ℹ Large MP3 will be converted on next preview after ffmpeg download completes")
                        # For now, skip conversion and let pygame try (will likely fail, but user knows why)
                        is_large_mp3 = False
                    else:
                        try:
                            from pydub import AudioSegment
                            
                            # Explicitly set ffmpeg paths (PATH might not work if pydub was already imported)
                            ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                            ffprobe_path = os.path.join(ffmpeg_dir, 'ffprobe.exe')
                            AudioSegment.converter = self.ffmpeg_path
                            AudioSegment.ffprobe = ffprobe_path
                            
                            self.log(f"  DEBUG: ffmpeg={self.ffmpeg_path}")
                            self.log(f"  DEBUG: ffprobe={ffprobe_path}")
                            self.log(f"  DEBUG: Source MP3={file_path}")
                            self.log(f"  DEBUG: Source size={os.path.getsize(file_path)} bytes")
                            
                            # Stop and unload any current playback to release file locks
                            try:
                                pygame.mixer.music.stop()
                                pygame.mixer.music.unload()
                            except:
                                pass
                            
                            # Create temp WAV for playback
                            temp_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp', '.CS2KZ-mapping-tools', 'Sounds', 'temp')
                            os.makedirs(temp_dir, exist_ok=True)
                            temp_wav_path = os.path.join(temp_dir, "large_mp3_preview.wav")
                            
                            self.log(f"  DEBUG: Converting MP3→WAV with ffmpeg directly...")
                            # Use ffmpeg directly instead of pydub's MP3 decoder (more reliable)
                            import subprocess
                            
                            # Call ffmpeg directly to convert MP3 to WAV
                            # -i input, -y overwrite, -acodec pcm_s16le standard WAV codec
                            ffmpeg_cmd = [
                                self.ffmpeg_path,
                                '-i', file_path,
                                '-acodec', 'pcm_s16le',
                                '-ar', '44100',
                                '-y',  # Overwrite output
                                temp_wav_path
                            ]
                            
                            self.log(f"  DEBUG: Running: {' '.join(ffmpeg_cmd)}")
                            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                            
                            if result.returncode != 0:
                                self.log(f"  DEBUG: ffmpeg stderr: {result.stderr}")
                                raise Exception(f"ffmpeg failed with code {result.returncode}")
                            
                            wav_size = os.path.getsize(temp_wav_path) if os.path.exists(temp_wav_path) else 0
                            self.log(f"  DEBUG: WAV created, size={wav_size} bytes")
                            
                            actual_play_path = temp_wav_path
                            self.log(f"  ✓ Converted to WAV for playback")
                        except Exception as e:
                            self.log(f"  ✗ Conversion failed: {e}")
                            import traceback
                            self.log(f"  Traceback: {traceback.format_exc()}")
                            is_large_mp3 = False
            
            # Reinitialize mixer to ensure clean state
            if not pygame:
                self.log("✗ pygame not available. Install with: pip install pygame")
                return
            
            pygame.mixer.quit()
            
            # If pitch toggle is enabled and pitch != 1.0, adjust frequency
            # Standard frequency is 44100 Hz
            base_frequency = 44100
            
            if self.show_pitch and self.pitch != 1.0:
                # Change playback frequency to simulate pitch
                # Lower frequency = lower pitch, higher frequency = higher pitch
                # We need to load at normal rate but play at adjusted rate
                adjusted_frequency = int(base_frequency / self.pitch)
                # Clamp frequency to reasonable values (8000 Hz to 48000 Hz)
                adjusted_frequency = max(8000, min(48000, adjusted_frequency))
            else:
                adjusted_frequency = base_frequency
            
            pygame.mixer.init(frequency=adjusted_frequency, size=-16, channels=2, buffer=512)
            
            # If loop is enabled and we have loop points, use pygame.mixer.Sound for better control
            if self.encoding_loop_enabled and self.audio_duration_ms > 0 and self.encoding_loop_start_ms > 0:
                # Note: pygame.mixer.Sound doesn't support seeking either, but we can
                # at least set the playback position by using set_volume fade-in effect
                # For now, we'll just play from the beginning and show a message
                pygame.mixer.music.load(actual_play_path)
                pygame.mixer.music.set_volume(self.preview_volume)
                pygame.mixer.music.play(-1, start=self.encoding_loop_start_ms / 1000.0)  # Start position in seconds
                loop_msg = f" (looping from {self.encoding_loop_start_ms/1000:.2f}s to {self.encoding_loop_end_ms/1000:.2f}s)"
            elif self.encoding_loop_enabled and self.audio_duration_ms > 0:
                # Loop from beginning
                pygame.mixer.music.load(actual_play_path)
                pygame.mixer.music.set_volume(self.preview_volume)
                pygame.mixer.music.play(-1)  # -1 means loop indefinitely
                loop_msg = f" (looping: {self.encoding_loop_start_ms/1000:.2f}s - {self.encoding_loop_end_ms/1000:.2f}s)"
            else:
                # Normal playback
                pygame.mixer.music.load(actual_play_path)
                pygame.mixer.music.set_volume(self.preview_volume)
                pygame.mixer.music.play()
                loop_msg = ""
            
            self.preview_playing = True
            self.playback_position_ms = int(self.encoding_loop_start_ms) if self.encoding_loop_enabled else 0
            self.playback_start_time = pygame.time.get_ticks()  # Record start time
            
            if self.show_pitch and self.pitch != 1.0:
                self.log(f"♪ Playing: {os.path.basename(file_path)} (pitch: {self.pitch:.2f}){loop_msg}")
            else:
                self.log(f"♪ Playing: {os.path.basename(file_path)}{loop_msg}")
        except Exception as e:
            self.log(f"✗ Error playing sound: {e}")
            # Try to reinitialize mixer to default if there was an error
            try:
                pygame.mixer.quit()
                pygame.mixer.init()
            except:
                pass
    
    def play_sound(self):
        """Play the currently selected sound (custom or internal)"""
        if self.use_internal_sound:
            self.preview_internal_sound()
        elif self.sound_file_path:
            self.play_sound_file(self.sound_file_path)
        else:
            self.log("✗ No sound selected")
    
    def stop_sound(self):
        """Stop currently playing sound"""
        if not pygame:
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()  # Unload the file to release the lock
            self.preview_playing = False
            
            # Clean up temporary loop preview file if it exists
            if self.temp_loop_file and os.path.exists(self.temp_loop_file):
                try:
                    os.remove(self.temp_loop_file)
                    self.temp_loop_file = None
                except:
                    pass  # File might be in use, will be cleaned up on next run
            
            self.log("⏹ Stopped playback")
        except Exception as e:
            self.log(f"✗ Error stopping sound: {e}")
    
    def play_loop_region(self):
        """Play only the loop region of the audio"""
        # Determine which audio file to use (custom or cached internal sound)
        audio_path = self.sound_file_path if not self.use_internal_sound else self.cached_internal_sound_path
        
        if not audio_path or not self.encoding_loop_enabled:
            return
        
        # Check if it's a WAV file - we can use pydub for WAV without ffmpeg
        is_wav = audio_path.lower().endswith('.wav')
        
        # Try to detect if file without extension is WAV
        if not is_wav and not audio_path.lower().endswith('.mp3'):
            try:
                import wave
                with wave.open(audio_path, 'rb') as test_wav:
                    is_wav = True
            except:
                is_wav = False
        
        # For WAV files, use pydub to extract loop region
        if is_wav:
            try:
                from pydub import AudioSegment
                
                # Stop and unload any current playback to release file locks
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                except:
                    pass
                
                # Load audio with pydub
                audio = AudioSegment.from_wav(audio_path)
                
                # Extract loop region
                loop_segment = audio[self.encoding_loop_start_ms:self.encoding_loop_end_ms]
                
                # Clean up old temp file if it exists (now that file is unlocked)
                if self.temp_loop_file and os.path.exists(self.temp_loop_file):
                    try:
                        os.remove(self.temp_loop_file)
                    except:
                        pass
                
                # Create a temporary file for the loop in our app-specific temp folder
                temp_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp', '.CS2KZ-mapping-tools')
                os.makedirs(temp_dir, exist_ok=True)
                temp_loop_path = os.path.join(temp_dir, "cs2_sound_loop_preview.wav")
                self.temp_loop_file = temp_loop_path
                
                # Export loop segment (repeat it a few times so it actually loops)
                looped_audio = loop_segment * 10  # Repeat 10 times
                looped_audio.export(temp_loop_path, format="wav")
                
                # Reinitialize mixer
                pygame.mixer.quit()
                base_frequency = 44100
                
                if self.show_pitch and self.pitch != 1.0:
                    adjusted_frequency = int(base_frequency / self.pitch)
                    adjusted_frequency = max(8000, min(48000, adjusted_frequency))
                else:
                    adjusted_frequency = base_frequency
                
                pygame.mixer.init(frequency=adjusted_frequency, size=-16, channels=2, buffer=512)
                
                # Load and play the looped segment
                pygame.mixer.music.load(temp_loop_path)
                pygame.mixer.music.set_volume(self.preview_volume)
                pygame.mixer.music.play(-1)  # Loop continuously
                
                self.preview_playing = True
                self.playback_position_ms = int(self.encoding_loop_start_ms)
                self.playback_start_time = pygame.time.get_ticks()
                
                self.log(f"♪ Playing loop: {self.encoding_loop_start_ms/1000:.2f}s - {self.encoding_loop_end_ms/1000:.2f}s")
            except Exception as e:
                self.log(f"✗ Error playing loop region: {e}")
        else:
            # For MP3 files, try to extract loop with ffmpeg if available
            if self.ffmpeg_path and os.path.exists(self.ffmpeg_path):
                try:
                    # Also check ffprobe path (pydub needs both)
                    ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                    ffprobe_path = os.path.join(ffmpeg_dir, 'ffprobe.exe')
                    
                    # Verify both exist before configuring
                    if not os.path.exists(ffprobe_path):
                        self.log(f"✗ ffprobe.exe not found at: {ffprobe_path}")
                        self.log(f"ℹ Please download ffmpeg + ffprobe")
                        return
                    
                    # Configure pydub BEFORE importing AudioSegment
                    # This ensures pydub uses our custom paths
                    from pydub import AudioSegment
                    from pydub.utils import which
                    
                    # Override the paths
                    AudioSegment.converter = self.ffmpeg_path
                    AudioSegment.ffprobe = ffprobe_path
                    
                    # Also set as environment to ensure subprocess can find them
                    import os as os_module
                    ffmpeg_dir_for_path = os.path.dirname(self.ffmpeg_path)
                    if 'PATH' in os_module.environ:
                        os_module.environ['PATH'] = ffmpeg_dir_for_path + os.pathsep + os_module.environ['PATH']
                    else:
                        os_module.environ['PATH'] = ffmpeg_dir_for_path
                    
                    self.log(f"DEBUG: Using ffmpeg: {self.ffmpeg_path}")
                    self.log(f"DEBUG: Using ffprobe: {ffprobe_path}")
                    self.log(f"DEBUG: Added to PATH: {ffmpeg_dir_for_path}")
                    
                    # Stop and unload any current playback
                    try:
                        pygame.mixer.music.stop()
                        pygame.mixer.music.unload()
                    except:
                        pass
                    
                    self.log(f"    Extracting loop segment with ffmpeg...")
                    
                    # Clean up old temp file
                    if self.temp_loop_file and os.path.exists(self.temp_loop_file):
                        try:
                            os.remove(self.temp_loop_file)
                        except:
                            pass
                    
                    # Create temp file for loop
                    temp_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp', '.CS2KZ-mapping-tools', 'Sounds', 'temp')
                    os.makedirs(temp_dir, exist_ok=True)
                    temp_loop_path = os.path.join(temp_dir, "cs2_sound_loop_preview.wav")
                    self.temp_loop_file = temp_loop_path
                    
                    # Use ffmpeg directly to extract and loop the segment
                    # Convert ms to seconds for ffmpeg
                    loop_start_sec = self.encoding_loop_start_ms / 1000.0
                    loop_duration_sec = (self.encoding_loop_end_ms - self.encoding_loop_start_ms) / 1000.0
                    
                    # Extract loop segment and repeat it 10 times using ffmpeg
                    # -stream_loop must come BEFORE -i (input option, not output option)
                    # -ss start time, -t duration
                    import subprocess
                    ffmpeg_cmd = [
                        self.ffmpeg_path,
                        '-ss', str(loop_start_sec),
                        '-t', str(loop_duration_sec),
                        '-stream_loop', '9',  # Loop 9 times = 10 total plays (must be before -i)
                        '-i', audio_path,
                        '-acodec', 'pcm_s16le',
                        '-ar', '44100',
                        '-y',
                        temp_loop_path
                    ]
                    
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                    
                    if result.returncode != 0:
                        self.log(f"  ffmpeg stderr: {result.stderr}")
                        raise Exception(f"ffmpeg loop extraction failed with code {result.returncode}")
                    
                    # Reinitialize mixer and play
                    pygame.mixer.quit()
                    base_frequency = 44100
                    
                    if self.show_pitch and self.pitch != 1.0:
                        adjusted_frequency = int(base_frequency / self.pitch)
                        adjusted_frequency = max(8000, min(48000, adjusted_frequency))
                    else:
                        adjusted_frequency = base_frequency
                    
                    pygame.mixer.init(frequency=adjusted_frequency, size=-16, channels=2, buffer=512)
                    
                    pygame.mixer.music.load(temp_loop_path)
                    pygame.mixer.music.set_volume(self.preview_volume)
                    pygame.mixer.music.play(-1)
                    
                    self.preview_playing = True
                    self.playback_position_ms = int(self.encoding_loop_start_ms)
                    self.playback_start_time = pygame.time.get_ticks()
                    
                    self.log(f"♪ Playing loop: {self.encoding_loop_start_ms/1000:.2f}s - {self.encoding_loop_end_ms/1000:.2f}s")
                except Exception as e:
                    self.log(f"✗ Error extracting MP3 loop: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # Fallback: simple playback from start position
                try:
                    pygame.mixer.quit()
                    base_frequency = 44100
                    
                    if self.show_pitch and self.pitch != 1.0:
                        adjusted_frequency = int(base_frequency / self.pitch)
                        adjusted_frequency = max(8000, min(48000, adjusted_frequency))
                    else:
                        adjusted_frequency = base_frequency
                    
                    pygame.mixer.init(frequency=adjusted_frequency, size=-16, channels=2, buffer=512)
                    
                    # Load and play from loop start position
                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.set_volume(self.preview_volume)
                    loop_start_sec = self.encoding_loop_start_ms / 1000.0
                    pygame.mixer.music.play(-1, start=loop_start_sec)
                    
                    self.preview_playing = True
                    self.playback_position_ms = int(self.encoding_loop_start_ms)
                    self.playback_start_time = pygame.time.get_ticks()
                    
                    self.log(f"♪ Playing loop: {self.encoding_loop_start_ms/1000:.2f}s - {self.encoding_loop_end_ms/1000:.2f}s")
                    self.log(f"ℹ MP3 loops play from start point to end of file (download ffmpeg for exact loops)")
                except Exception as e:
                    self.log(f"✗ Error playing loop region: {e}")
    
    def analyze_audio_file(self, file_path):
        """Analyze audio file to extract duration and generate waveform data"""
        try:
            import wave
            import struct
            
            # Reset timeline data
            self.audio_duration_ms = 0
            self.audio_waveform = []
            self.encoding_loop_start_ms = 0
            self.encoding_loop_end_ms = 0
            self.playback_position_ms = 0
            
            # Try to detect file type (some decompiled files have no extension)
            is_mp3 = file_path.lower().endswith('.mp3')
            is_wav = file_path.lower().endswith('.wav')
            
            # If no extension, try to detect by attempting to open as WAV first
            if not is_mp3 and not is_wav:
                try:
                    with wave.open(file_path, 'rb') as test_wav:
                        is_wav = True
                except:
                    is_mp3 = True  # Assume MP3 if WAV fails
            
            # Check file extension
            if is_mp3:
                # For MP3, just get duration with pygame (no conversion for UI responsiveness)
                try:
                    sound = pygame.mixer.Sound(file_path)
                    duration_seconds = sound.get_length()
                    self.audio_duration_ms = int(duration_seconds * 1000)
                    self.encoding_loop_end_ms = self.audio_duration_ms
                    
                    # Generate simple waveform placeholder for MP3s
                    # Actual waveform would require conversion which blocks UI
                    num_samples = 200
                    # Create a semi-random looking waveform (alternating between 0.2-0.5)
                    import random
                    random.seed(hash(file_path))  # Consistent per file
                    self.audio_waveform = [random.uniform(0.2, 0.5) for _ in range(num_samples)]
                    
                    self.log(f"✓ Analyzed MP3: {duration_seconds:.2f}s (approximate waveform)")
                except Exception as e:
                    self.log(f"✗ Error analyzing MP3: {e}")
                    return False
                    
            elif is_wav:
                # For WAV, use wave module to extract detailed data
                with wave.open(file_path, 'rb') as wav_file:
                    framerate = wav_file.getframerate()
                    n_frames = wav_file.getnframes()
                    n_channels = wav_file.getnchannels()
                    sampwidth = wav_file.getsampwidth()
                    
                    # Calculate duration
                    duration_seconds = n_frames / framerate
                    self.audio_duration_ms = int(duration_seconds * 1000)
                    self.encoding_loop_end_ms = self.audio_duration_ms
                    
                    # Read all frames
                    frames = wav_file.readframes(n_frames)
                    
                    # Convert to samples
                    if sampwidth == 1:
                        fmt = f"{n_frames * n_channels}B"
                        samples = struct.unpack(fmt, frames)
                        samples = [(s - 128) / 128.0 for s in samples]
                    elif sampwidth == 2:
                        fmt = f"{n_frames * n_channels}h"
                        samples = struct.unpack(fmt, frames)
                        samples = [s / 32768.0 for s in samples]
                    else:
                        # Unsupported sample width, use placeholder
                        samples = [0.5] * (n_frames * n_channels)
                    
                    # If stereo, average channels
                    if n_channels == 2:
                        samples = [(samples[i] + samples[i+1]) / 2 for i in range(0, len(samples), 2)]
                    
                    # Downsample for visualization (200 points)
                    num_vis_samples = 200
                    chunk_size = max(1, len(samples) // num_vis_samples)
                    
                    self.audio_waveform = []
                    for i in range(num_vis_samples):
                        start_idx = i * chunk_size
                        end_idx = min(start_idx + chunk_size, len(samples))
                        if start_idx < len(samples):
                            chunk = samples[start_idx:end_idx]
                            # Get peak amplitude in this chunk (max absolute value)
                            peak = max(abs(s) for s in chunk) if chunk else 0.0
                            self.audio_waveform.append(peak)
                        else:
                            self.audio_waveform.append(0.0)
                    
                    self.log(f"✓ Analyzed WAV: {duration_seconds:.2f}s, {framerate}Hz, {n_channels}ch")
            else:
                return False
                
            return True
            
        except Exception as e:
            self.log(f"✗ Error analyzing audio: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_addon_filter(self, search_text):
        """Filter available addons based on search text"""
        if not search_text:
            self.filtered_addons = self.available_addons  # Show all when empty
        else:
            # Case-insensitive filter
            search_lower = search_text.lower()
            self.filtered_addons = [addon for addon in self.available_addons 
                                   if search_lower in addon.lower()]
        
        self.show_addon_dropdown = len(self.filtered_addons) > 0
        self.selected_addon_index = -1
    
    def log(self, message):
        """Add message to console output"""
        self.console_output.append(message)
        print(message)
    
    def browse_sound_file(self):
        """Open file dialog to select sound file"""
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        file_path = filedialog.askopenfilename(
            title="Select Sound File",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav"),
                ("MP3 Files", "*.mp3"),
                ("WAV Files", "*.wav"),
                ("All Files", "*.*")
            ]
        )
        root.destroy()
        
        if file_path:
            self.sound_file_path = file_path.replace("\\", "/")
            filename = os.path.basename(file_path)
            self.sound_file_display = filename
            # Extract sound name without extension
            self.sound_name = os.path.splitext(filename)[0]
            # Set default output name to match the input filename
            self.output_name = self.sound_name
            self.sound_status_color = (0.0, 1.0, 0.0, 1.0)  # Green
            self.log(f"✓ Selected: {self.sound_file_display}")
            self.log(f"  Sound name: {self.sound_name}")
            
            # Analyze audio file for timeline
            self.analyze_audio_file(file_path)
        else:
            self.log("✗ No file selected")
    
    def check_and_download_lame_dll(self):
        """Check if lame_enc.dll exists, download if missing"""
        if not self.cs2_basefolder:
            return False
        
        dll_path = os.path.join(self.cs2_basefolder, 'game', 'bin', 'win64', 'lame_enc.dll')
        
        # Check if DLL already exists
        if os.path.exists(dll_path):
            return True
        
        try:
            self.log("⏳ Downloading lame_enc.dll for MP3 compression...")
            
            # Download the ZIP file
            url = "https://www.rarewares.org/files/mp3/lame3.100.1-x64.zip"
            
            with urllib.request.urlopen(url, timeout=30) as response:
                zip_data = response.read()
            
            # Extract only lame_enc.dll from the ZIP (don't keep anything else)
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                # Find lame_enc.dll in the ZIP
                dll_found = False
                for file_info in zip_file.namelist():
                    if file_info.endswith('lame_enc.dll'):
                        # Extract directly to the target location (memory -> file)
                        # This avoids extracting other files from the archive
                        with zip_file.open(file_info) as source:
                            os.makedirs(os.path.dirname(dll_path), exist_ok=True)
                            with open(dll_path, 'wb') as target:
                                target.write(source.read())
                        dll_found = True
                        self.log(f"✓ Extracted lame_enc.dll (discarded other archive contents)")
                        break
                
                if not dll_found:
                    self.log("✗ Error: lame_enc.dll not found in downloaded archive")
                    return False
            
            self.log(f"✓ Successfully installed lame_enc.dll to: {dll_path}")
            self.log("  MP3 compression is now available")
            return True
            
        except urllib.error.URLError as e:
            self.log(f"✗ Error downloading lame_enc.dll: {e}")
            self.log("  Please download manually from: https://www.rarewares.org/files/mp3/lame3.100.1-x64.zip")
            self.log(f"  Extract lame_enc.dll to: {dll_path}")
            return False
        except Exception as e:
            self.log(f"✗ Error installing lame_enc.dll: {e}")
            import traceback
            traceback.print_exc()
            return False
    

    def create_encoding_txt(self, sounds_folder, sound_filename, use_compression=True):
        """Create encoding.txt file for Source 2 sound compilation with loop points and compression"""
        try:
            encoding_path = os.path.join(sounds_folder, 'encoding.txt')
            
            # Build the encoding.txt content
            header = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->
{
'''
            
            # Global compression settings
            compress_block = ""
            if self.encoding_format != "PCM":
                if self.encoding_format == "mp3":
                    vbr_value = 1 if self.encoding_vbr else 0
                    compress_block = f'''\tcompress =
\t{{
\t\tformat = "mp3"
\t\tminbitrate = {self.encoding_minbitrate}
\t\tmaxbitrate = {self.encoding_maxbitrate}
\t\tvbr = {vbr_value}
\t}}
'''
                elif self.encoding_format == "adpcm":
                    compress_block = '''\tcompress =
\t{
\t\tformat = "adpcm"
\t}
'''
            
            # Sample rate settings
            sample_rate_block = ""
            if self.encoding_sample_rate > 0:
                sample_rate_block = f'''\trate = {self.encoding_sample_rate}
'''
            
            # Normalization settings
            normalize_block = ""
            if self.encoding_normalize:
                normalize_block = f'''\tnormalize =
\t{{
\t\tlevel = {self.encoding_normalize_level}
'''
                if self.encoding_normalize_compression:
                    normalize_block += '''\t\tcompression = true
'''
                if self.encoding_normalize_limiter:
                    normalize_block += '''\t\tlimiter = true
'''
                normalize_block += '''\t}
'''
            
            # File-specific settings (loop points)
            files_block = ""
            if self.encoding_loop_enabled and self.audio_duration_ms > 0:
                # Convert milliseconds to seconds
                loop_start_sec = self.encoding_loop_start_ms / 1000.0
                loop_end_sec = self.encoding_loop_end_ms / 1000.0
                
                files_block = f'''\tfiles =
\t[
\t\t{{
\t\t\tfileName = "{sound_filename}"
\t\t\tloop =
\t\t\t{{
\t\t\t\tloop_start_time = {loop_start_sec}
\t\t\t\tloop_end_time = {loop_end_sec}
\t\t\t\tcrossfade_ms = {self.encoding_crossfade_ms}
\t\t\t}}
\t\t}},
\t]
'''
            
            footer = '}\n'
            
            # Write the file
            with open(encoding_path, 'w', encoding='utf-8') as f:
                f.write(header + compress_block + sample_rate_block + normalize_block + files_block + footer)
            
            self.log(f"✓ Created encoding.txt: {encoding_path}")
            if self.encoding_format != "PCM":
                if self.encoding_format == "mp3":
                    self.log(f"  - MP3 compression: {self.encoding_minbitrate}-{self.encoding_maxbitrate} kbps (VBR: {self.encoding_vbr})")
                else:
                    self.log(f"  - {self.encoding_format.upper()} compression")
            if self.encoding_sample_rate > 0:
                self.log(f"  - Sample rate: {self.encoding_sample_rate} Hz")
            if self.encoding_normalize:
                self.log(f"  - Normalization: {self.encoding_normalize_level} dB")
            if self.encoding_loop_enabled:
                self.log(f"  - Loop points: {loop_start_sec:.2f}s to {loop_end_sec:.2f}s (crossfade: {self.encoding_crossfade_ms}ms)")
            
            return True
            
        except Exception as e:
            self.log(f"✗ Error creating encoding.txt: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def download_ffmpeg(self):
        """Download ffmpeg in background thread (non-blocking)"""
        # Store ffmpeg in the app's temp folder
        ffmpeg_dir = os.path.join(os.getenv('LOCALAPPDATA'), 'Temp', '.CS2KZ-mapping-tools', 'Sounds', 'ffmpeg')
        ffmpeg_path = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
        
        # Check if ffmpeg already exists
        if os.path.exists(ffmpeg_path):
            self.ffmpeg_path = ffmpeg_path
            self.log("✓ ffmpeg already installed")
            return
        
        # Check if already downloading
        if self.downloading_ffmpeg:
            self.log("⏳ ffmpeg download already in progress")
            return
        
        self.downloading_ffmpeg = True
        self.log("⏳ Downloading ffmpeg + ffprobe (~100MB download, ~200MB installed)...")
        
        def download_thread():
            try:
                # Download ffmpeg essentials build (includes both ffmpeg and ffprobe)
                url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
                
                with urllib.request.urlopen(url, timeout=120) as response:
                    zip_data = response.read()
                
                self.log("⏳ Extracting ffmpeg.exe and ffprobe.exe...")
                
                # Extract ffmpeg.exe and ffprobe.exe from the ZIP (pydub needs both)
                os.makedirs(ffmpeg_dir, exist_ok=True)
                
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                    ffmpeg_found = False
                    ffprobe_found = False
                    
                    for file_info in zip_file.namelist():
                        if file_info.endswith('bin/ffmpeg.exe'):
                            # Extract ffmpeg.exe
                            with zip_file.open(file_info) as source:
                                with open(ffmpeg_path, 'wb') as target:
                                    target.write(source.read())
                            ffmpeg_found = True
                            self.log(f"✓ Installed ffmpeg.exe")
                        elif file_info.endswith('bin/ffprobe.exe'):
                            # Extract ffprobe.exe
                            ffprobe_path = os.path.join(ffmpeg_dir, 'ffprobe.exe')
                            with zip_file.open(file_info) as source:
                                with open(ffprobe_path, 'wb') as target:
                                    target.write(source.read())
                            ffprobe_found = True
                            self.log(f"✓ Installed ffprobe.exe")
                        
                        if ffmpeg_found and ffprobe_found:
                            break
                    
                    if not ffmpeg_found or not ffprobe_found:
                        self.log("✗ Error: ffmpeg.exe or ffprobe.exe not found in archive")
                        self.downloading_ffmpeg = False
                        return
                
                # Configure pydub to use our ffmpeg
                from pydub import AudioSegment
                AudioSegment.converter = ffmpeg_path
                self.ffmpeg_path = ffmpeg_path
                
                self.log("✓ ffmpeg + ffprobe installed - MP3 loop extraction now available")
                self.log("  Loop preview will now extract exact segments from MP3 files")
                self.downloading_ffmpeg = False
                
            except Exception as e:
                self.log(f"✗ Error downloading ffmpeg + ffprobe: {e}")
                self.log("  Internal sounds will play as MP3 with limited loop support")
                self.downloading_ffmpeg = False
        
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
    
    def add_sound(self):
        """Add the sound file to the addon folder and update soundevents file"""
        # Validate inputs
        if not self.addon_name.strip():
            self.log("✗ Error: Please enter an addon name")
            return
        
        if not self.cs2_basefolder:
            self.log("✗ Error: CS2 path not detected")
            return
        
        # Validate sound selection based on source
        if self.use_internal_sound:
            if not self.selected_internal_sound:
                self.log("✗ Error: Please select an internal sound")
                return
            if not self.sound_name.strip():
                self.log("✗ Error: Sound name is empty")
                return
        else:
            if not self.sound_file_path:
                self.log("✗ Error: Please select a sound file")
                return
            if not os.path.exists(self.sound_file_path):
                self.log("✗ Error: Selected sound file does not exist")
                return
        
        try:
            addon_name = self.addon_name.strip()
            
            # Handle custom file or internal sound differently
            if not self.use_internal_sound:
                # Custom file workflow (original behavior)
                # Construct the sounds folder path
                sounds_folder = os.path.join(
                    self.cs2_basefolder,
                    'content',
                    'csgo_addons',
                    addon_name,
                    'sounds'
                )
                
                # Create sounds folder if it doesn't exist
                os.makedirs(sounds_folder, exist_ok=True)
                self.log(f"✓ Content sounds folder: {sounds_folder}")
                
                # Use output_name for the destination filename if specified, otherwise use original filename
                output_filename = self.output_name if self.output_name else os.path.splitext(os.path.basename(self.sound_file_path))[0]
                file_extension = os.path.splitext(self.sound_file_path)[1]
                dest_filename = output_filename + file_extension
                dest_path = os.path.join(sounds_folder, dest_filename)
                shutil.copy2(self.sound_file_path, dest_path)
                self.log(f"✓ Content root file (.wav/.mp3): {dest_path}")
                
                # Create encoding.txt for loop points and compression (Source 2 native method)
                if self.use_wav_markers and self.audio_duration_ms > 0:
                    # Check if MP3 compression is enabled and lame_enc.dll is needed
                    if self.encoding_format == "mp3":
                        self.check_and_download_lame_dll()
                    
                    # use_wav_markers now means "use Source 2 encoding.txt for looping/compression"
                    self.create_encoding_txt(sounds_folder, dest_filename, use_compression=True)
                
                # Update sound_name to use the output name for soundevent creation
                sound_name_for_event = output_filename
                
                # Compile the sound file directly (creates .vsnd_c in game root)
                if not self.compile_sound_file(dest_path):
                    self.log("✗ Warning: Sound file compilation failed, but content file was created")
                else:
                    # Calculate game root path where .vsnd_c will be
                    game_sounds_folder = os.path.join(
                        self.cs2_basefolder,
                        'game',
                        'csgo_addons',
                        addon_name,
                        'sounds'
                    )
                    vsnd_c_filename = os.path.splitext(dest_filename)[0] + ".vsnd_c"
                    vsnd_c_path = os.path.join(game_sounds_folder, vsnd_c_filename)
                    self.log(f"✓ Game root file (.vsnd_c): {vsnd_c_path}")
            else:
                # Internal sound workflow - copy the decompiled sound to addon folder
                # so it gets compiled and appears in asset browser like custom sounds
                self.log(f"✓ Using internal CS2 sound: {self.selected_internal_sound}")
                
                # Ensure we have a cached/decompiled version
                if not self.cached_internal_sound_path or not os.path.exists(self.cached_internal_sound_path):
                    self.log("✗ Error: Internal sound not available. Please preview it first.")
                    return
                
                # Construct the sounds folder path in content
                sounds_folder = os.path.join(
                    self.cs2_basefolder,
                    'content',
                    'csgo_addons',
                    addon_name,
                    'sounds'
                )
                
                # Create sounds folder if it doesn't exist
                os.makedirs(sounds_folder, exist_ok=True)
                self.log(f"✓ Content sounds folder: {sounds_folder}")
                
                # Use output_name for the destination filename
                output_filename = self.output_name if self.output_name else os.path.splitext(os.path.basename(self.cached_internal_sound_path))[0]
                
                # Check if source is MP3 and we need WAV for loop points
                file_extension = os.path.splitext(self.cached_internal_sound_path)[1]
                is_mp3 = file_extension.lower() == '.mp3'
                
                # Convert MP3 to WAV if loop points are enabled (CS2 requires WAV for loops)
                if is_mp3 and self.use_wav_markers and self.encoding_loop_enabled:
                    self.log("  Converting MP3 to WAV (required for loop points)...")
                    try:
                        import subprocess
                        
                        dest_filename = output_filename + '.wav'
                        dest_path = os.path.join(sounds_folder, dest_filename)
                        
                        # Use ffmpeg directly for conversion (more reliable than pydub)
                        if self.ffmpeg_path and os.path.exists(self.ffmpeg_path):
                            ffmpeg_cmd = [
                                self.ffmpeg_path,
                                '-i', self.cached_internal_sound_path,
                                '-acodec', 'pcm_s16le',
                                '-ar', '44100',
                                '-y',
                                dest_path
                            ]
                            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, 
                                                  creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                            
                            if result.returncode == 0 and os.path.exists(dest_path):
                                self.log(f"✓ Content root file (.wav): {dest_path}")
                            else:
                                raise Exception(f"ffmpeg conversion failed: {result.stderr}")
                        else:
                            # Fallback to pydub if ffmpeg not available
                            from pydub import AudioSegment
                            audio = AudioSegment.from_mp3(self.cached_internal_sound_path)
                            audio.export(dest_path, format="wav")
                            self.log(f"✓ Content root file (.wav): {dest_path}")
                    except Exception as e:
                        self.log(f"✗ Error converting MP3 to WAV: {e}")
                        self.log("  Falling back to MP3 (loop points may not work)")
                        # Fall back to copying MP3
                        dest_filename = output_filename + file_extension
                        dest_path = os.path.join(sounds_folder, dest_filename)
                        shutil.copy2(self.cached_internal_sound_path, dest_path)
                        self.log(f"✓ Content root file ({file_extension}): {dest_path}")
                else:
                    # Copy the sound file as-is (MP3 or WAV)
                    dest_filename = output_filename + file_extension
                    dest_path = os.path.join(sounds_folder, dest_filename)
                    shutil.copy2(self.cached_internal_sound_path, dest_path)
                    self.log(f"✓ Content root file ({file_extension}): {dest_path}")
                
                # Create encoding.txt for loop points and compression if enabled
                if self.use_wav_markers and self.audio_duration_ms > 0:
                    # Check if MP3 compression is enabled and lame_enc.dll is needed
                    if self.encoding_format == "mp3":
                        self.check_and_download_lame_dll()
                    
                    self.create_encoding_txt(sounds_folder, dest_filename, use_compression=True)
                
                # Update sound_name to use the output name for soundevent creation
                sound_name_for_event = output_filename
                
                # Compile the sound file directly (creates .vsnd_c in game root)
                if not self.compile_sound_file(dest_path):
                    self.log("✗ Warning: Sound file compilation failed, but content file was created")
                else:
                    # Calculate game root path where .vsnd_c will be
                    game_sounds_folder = os.path.join(
                        self.cs2_basefolder,
                        'game',
                        'csgo_addons',
                        addon_name,
                        'sounds'
                    )
                    vsnd_c_filename = os.path.splitext(dest_filename)[0] + ".vsnd_c"
                    vsnd_c_path = os.path.join(game_sounds_folder, vsnd_c_filename)
                    self.log(f"✓ Game root file (.vsnd_c): {vsnd_c_path}")
            
            # Update soundevents_addon.vsndevts file
            soundevents_folder = os.path.join(
                self.cs2_basefolder,
                'content',
                'csgo_addons',
                addon_name,
                'soundevents'
            )
            os.makedirs(soundevents_folder, exist_ok=True)
            
            soundevents_file = os.path.join(soundevents_folder, 'soundevents_addon.vsndevts')
            
            # Both custom files and internal sounds now use local filename
            # (internal sounds are copied to addon folder now)
            self.update_soundevents_file(soundevents_file, dest_filename, None)
            
            # Compile the soundevents file so Hammer can see it
            if not self.compile_sound_file(soundevents_file):
                self.log("✗ Warning: Soundevents file compilation failed")
            else:
                game_soundevents_folder = os.path.join(
                    self.cs2_basefolder,
                    'game',
                    'csgo_addons',
                    addon_name,
                    'soundevents'
                )
                soundevents_c_path = os.path.join(game_soundevents_folder, 'soundevents_addon.vsndevts_c')
                self.log(f"✓ Game soundevents file (.vsndevts_c): {soundevents_c_path}")
            
            event_name = self.output_name if self.output_name else self.sound_name
            self.log(f"✓ Sound added successfully! Event name: {event_name}")
            
        except Exception as e:
            self.log(f"✗ Error adding sound: {e}")
            import traceback
            traceback.print_exc()
    
    def update_soundevents_file(self, soundevents_file, sound_filename=None, internal_sound_path=None):
        """Update or create the soundevents_addon.vsndevts file with new sound entry"""
        # Use output_name for the soundevent name (user-customizable)
        event_name = self.output_name if self.output_name else self.sound_name
        
        # Determine the vsnd reference based on whether it's custom or internal
        if internal_sound_path:
            # Internal sound - use the full path directly (already has .vsnd extension removed)
            vsnd_reference = internal_sound_path
        else:
            # Custom sound - convert filename to .vsnd reference in sounds/ folder
            vsnd_filename = os.path.splitext(sound_filename)[0] + ".vsnd"
            vsnd_reference = f"sounds/{vsnd_filename}"
        
        # Generate the soundevent entry
        # Add wav_markers line if enabled
        wav_markers_line = ""
        if self.use_wav_markers:
            wav_markers_line = '\t\tuse_wav_markers = true\n'
        
        soundevent_entry = f'''\t"{event_name}" =
\t{{
\t\ttype = "{self.sound_type}"
\t\tvsnd_files_track_01 = "{vsnd_reference}"
\t\tvolume = {self.volume:.1f}
\t\tpitch = {self.pitch:.2f}
{wav_markers_line}\t\tuse_distance_volume_mapping_curve = true
\t\tdistance_volume_mapping_curve = 
\t\t[
\t\t\t[{self.distance_near:.1f}, {self.distance_near_volume:.1f}, {self.curve_near_mid_cp1:.3f}, {self.curve_near_mid_cp2:.3f}, {self.curve_near_mid_cp3:.3f}, {self.curve_near_mid_cp4:.3f},],
\t\t\t[{self.distance_mid:.1f}, {self.distance_mid_volume:.1f}, {self.curve_mid_far_cp1:.3f}, {self.curve_mid_far_cp2:.3f}, {self.curve_mid_far_cp3:.3f}, {self.curve_mid_far_cp4:.3f}],
\t\t\t[{self.distance_far:.1f}, {self.distance_far_volume:.1f}, 0.0, 0.0, 1.0, 1.0],
\t\t]
\t\tocclusion = {str(self.show_occlusion).lower()}
\t\tocclusion_intensity = {int(self.occlusion_intensity)}
\t}}
'''
        
        if os.path.exists(soundevents_file):
            # File exists, check if sound name already exists and remove it
            with open(soundevents_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Remove existing entry with the same name if it exists
            # Pattern to match the entire sound entry block
            pattern = rf'\t"{re.escape(event_name)}"\s*=\s*\{{[^}}]*\}}\n?'
            content = re.sub(pattern, '', content, flags=re.DOTALL)
            
            # Find the last closing brace
            last_brace_index = content.rfind('}')
            if last_brace_index != -1:
                # Insert before the last closing brace
                new_content = content[:last_brace_index] + soundevent_entry + content[last_brace_index:]
            else:
                # Shouldn't happen, but append anyway
                new_content = content + soundevent_entry + '\n}'
            
            with open(soundevents_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.log(f"✓ Updated soundevents file (overwritten if existed): {soundevents_file}")
        else:
            # Create new file with header and soundevent
            header = '''<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->
{
'''
            footer = '}\n'
            
            with open(soundevents_file, 'w', encoding='utf-8') as f:
                f.write(header + soundevent_entry + footer)
            
            self.log(f"✓ Created soundevents file: {soundevents_file}")
    
    def compile_sound_file(self, audio_file_path):
        """Compile a .wav/.mp3 file using resourcecompiler.exe to create .vsnd_c"""
        if not self.cs2_basefolder:
            self.log("✗ Error: CS2 path not detected")
            return False
        
        compiler_path = os.path.join(self.cs2_basefolder, 'game', 'bin', 'win64', 'resourcecompiler.exe')
        if not os.path.exists(compiler_path):
            self.log(f"✗ Error: resourcecompiler.exe not found at {compiler_path}")
            return False
        
        # Set the working directory for the compiler (should be the 'game' directory)
        compiler_cwd = os.path.join(self.cs2_basefolder, 'game')
        
        try:
            # The input file path needs to be relative to the 'game' directory
            relative_audio_path = os.path.relpath(audio_file_path, start=compiler_cwd).replace("\\", "/")
            
            self.log(f"Compiling {os.path.basename(audio_file_path)}...")
            
            command = [compiler_path, '-i', relative_audio_path]
            result = subprocess.run(command, cwd=compiler_cwd, check=True, capture_output=True, text=True)
            
            self.log(f"✓ Compilation successful for {os.path.basename(audio_file_path)}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"✗ Compilation failed for {os.path.basename(audio_file_path)}: {e}")
            self.log(f"Compiler stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            self.log(f"✗ Error: resourcecompiler.exe not found at {compiler_path}")
            return False
        except Exception as e:
            self.log(f"✗ Unexpected error during compilation: {e}")
            return False
    
    def open_addon_sounds_folder(self):
        """Open the addon sounds folder in Windows Explorer"""
        try:
            if not self.cs2_basefolder:
                self.log("✗ Error: CS2 path not detected")
                return
            
            if not self.addon_name.strip():
                self.log("✗ Error: Please enter an addon name")
                return
            
            sounds_folder = os.path.join(
                self.cs2_basefolder,
                'content',
                'csgo_addons',
                self.addon_name.strip(),
                'sounds'
            )
            
            if not os.path.exists(sounds_folder):
                os.makedirs(sounds_folder, exist_ok=True)
                self.log(f"✓ Created sounds folder: {sounds_folder}")
            
            os.startfile(sounds_folder)
            self.log(f"✓ Opened sounds folder")
            
        except Exception as e:
            self.log(f"✗ Error opening sounds folder: {e}")
    
    def init_window(self):
        """Initialize GLFW window and ImGui"""
        if not glfw.init():
            print("Could not initialize OpenGL context")
            sys.exit(1)
        
        # Scan for available addons after CS2 path is detected
        self.available_addons = self.scan_available_addons()
        self.update_addon_filter("")  # Initialize filtered list
        
        # Window hints
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, gl.GL_TRUE)
        glfw.window_hint(glfw.DECORATED, glfw.FALSE)
        
        # Create window
        self.window = glfw.create_window(self.window_width, self.base_window_height, "CS2 Sounds Manager", None, None)
        if not self.window:
            glfw.terminate()
            print("Could not initialize Window")
            sys.exit(1)
        
        # Create cursors
        self.arrow_cursor = glfw.create_standard_cursor(glfw.ARROW_CURSOR)
        self.hand_cursor = glfw.create_standard_cursor(glfw.HAND_CURSOR)
        
        # Center window on screen
        monitor = glfw.get_primary_monitor()
        video_mode = glfw.get_video_mode(monitor)
        x_pos = (video_mode.size.width - self.window_width) // 2
        y_pos = (video_mode.size.height - self.base_window_height) // 2
        glfw.set_window_pos(self.window, x_pos, y_pos)
        
        glfw.make_context_current(self.window)
        glfw.swap_interval(1)
        
        # Set window icon
        icon_path = resource_path(os.path.join("icons", "sounds.ico"))
        if os.path.exists(icon_path):
            try:
                icon_img = Image.open(icon_path)
                if icon_img.mode != 'RGBA':
                    icon_img = icon_img.convert('RGBA')
                
                try:
                    from glfw import _GLFWimage
                    img_buffer = icon_img.tobytes()
                    img = _GLFWimage()
                    img.width = icon_img.width
                    img.height = icon_img.height
                    img.pixels = img_buffer
                    glfw.set_window_icon(self.window, 1, img)
                except:
                    icon_data = icon_img.tobytes()
                    glfw.set_window_icon(self.window, 1, [[icon_img.width, icon_img.height, icon_data]])
            except:
                pass
        
        # Setup ImGui
        imgui.create_context()
        
        # Load font BEFORE creating renderer
        io = imgui.get_io()
        theme_name = self.theme_manager.get_theme_name()
        
        # Always use Consolas font (Windows system font)
        consolas_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'consola.ttf')
        if os.path.exists(consolas_path):
            io.fonts.add_font_from_file_ttf(consolas_path, 13.0)
        else:
            # Fallback to Roboto if Consolas not found
            font_path = resource_path(os.path.join("fonts", "Roboto-Regular.ttf"))
            if os.path.exists(font_path):
                io.fonts.add_font_from_file_ttf(font_path, 13.0)
        
        # Create renderer AFTER loading fonts
        self.impl = GlfwRenderer(self.window)
        
        # Apply theme colors to ImGui
        theme = self.theme_manager.get_theme()
        style = imgui.get_style()
        
        # Apply theme colors
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = theme['window_bg']
        style.colors[imgui.COLOR_BUTTON] = theme['button']
        style.colors[imgui.COLOR_BUTTON_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = theme['button_active']
        style.colors[imgui.COLOR_BORDER] = theme['border']
        style.colors[imgui.COLOR_TEXT] = theme['text']
        style.colors[imgui.COLOR_FRAME_BACKGROUND] = theme['button']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = theme['button_active']
        
        # Slider colors (match theme)
        style.colors[imgui.COLOR_SLIDER_GRAB] = theme['button_active']
        style.colors[imgui.COLOR_SLIDER_GRAB_ACTIVE] = theme['button_hover']
        
        # Checkbox colors (match theme)
        style.colors[imgui.COLOR_CHECK_MARK] = theme['button_active']
        
        # Style settings
        style.window_rounding = 0.0
        style.frame_rounding = 7.0
        style.window_padding = (14, 14)
        style.frame_padding = (10, 10)
        style.item_spacing = (7, 7)
        style.window_border_size = 0.0
        style.frame_border_size = 2.0
        style.scrollbar_size = 10.0  # Set to small value for child windows
        
        # Load icons as textures
        self.load_title_icon()
        self.load_control_icons()
    
    def load_title_icon(self):
        """Load title icon as OpenGL texture"""
        icon_path = resource_path(os.path.join("icons", "sounds.ico"))
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
            except Exception as e:
                print(f"Failed to load title icon: {e}")
    
    def load_control_icons(self):
        """Load play and pause icons as OpenGL textures"""
        # Load play icon
        play_icon_path = resource_path(os.path.join("icons", "play.ico"))
        if os.path.exists(play_icon_path):
            try:
                img = Image.open(play_icon_path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                img = img.resize((20, 20), Image.Resampling.LANCZOS)
                width, height = img.size
                img_data = img.tobytes()
                
                texture = gl.glGenTextures(1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height,
                               0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data)
                
                self.play_icon = texture
            except Exception as e:
                print(f"Failed to load play icon: {e}")
        
        # Load pause icon
        pause_icon_path = resource_path(os.path.join("icons", "pause.ico"))
        if os.path.exists(pause_icon_path):
            try:
                img = Image.open(pause_icon_path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                img = img.resize((20, 20), Image.Resampling.LANCZOS)
                width, height = img.size
                img_data = img.tobytes()
                
                texture = gl.glGenTextures(1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
                gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
                gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height,
                               0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, img_data)
                
                self.pause_icon = texture
            except Exception as e:
                print(f"Failed to load pause icon: {e}")
    
    def render_title_bar(self):
        """Render custom title bar"""
        imgui.set_next_window_position(0, 0)
        imgui.set_next_window_size(self.window_width, CUSTOM_TITLE_BAR_HEIGHT)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_ROUNDING, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        
        # Darker title bar
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
        if self.title_icon:
            imgui.image(self.title_icon, 16, 16)
            imgui.same_line(spacing=4)
        
        # Title text with theme color
        theme = self.theme_manager.get_theme()
        text_color = theme['text']
        imgui.push_style_color(imgui.COLOR_TEXT, *text_color)
        imgui.text("CS2 Sounds Manager")
        imgui.pop_style_color(1)
        
        # Get the position for the buttons (right side)
        button_size = 20
        button_spacing = 4
        total_button_width = (button_size * 2) + button_spacing  # Minimize + Close
        
        imgui.same_line(self.window_width - total_button_width - 6)
        
        # VS Code style buttons - flat, no borders when not hovered
        imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 0.0)
        
        # Minimize button (VS Code style)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)  # Transparent
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.2, 0.2, 0.2, 1.0)  # Dark gray
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)  # No border
        
        minimize_clicked = imgui.button("##minimize", width=button_size, height=button_size)
        
        # Draw centered minimize symbol manually
        min_button_min = imgui.get_item_rect_min()
        draw_list = imgui.get_window_draw_list()
        
        # Draw a centered horizontal line for minimize
        line_width = 8
        line_height = 1
        line_x = min_button_min.x + (button_size - line_width) // 2
        line_y = min_button_min.y + (button_size - line_height) // 2
        line_color = imgui.get_color_u32_rgba(0.8, 0.8, 0.8, 1.0)
        draw_list.add_rect_filled(line_x, line_y, line_x + line_width, line_y + line_height + 1, line_color)
        
        imgui.pop_style_color(4)
        
        if minimize_clicked:
            glfw.iconify_window(self.window)
        
        imgui.same_line(spacing=button_spacing)
        
        # Close button (VS Code style - red hover)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.0, 0.0, 0.0)  # Transparent
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.9, 0.2, 0.2, 1.0)  # Red
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.8, 0.15, 0.15, 1.0)
        imgui.push_style_color(imgui.COLOR_BORDER, 0.0, 0.0, 0.0, 0.0)  # No border
        
        close_clicked = imgui.button("##close", width=button_size, height=button_size)
        
        # Draw centered X symbol manually
        close_button_min = imgui.get_item_rect_min()
        
        # Calculate center of button
        center_x = close_button_min.x + button_size // 2
        center_y = close_button_min.y + button_size // 2
        
        # Draw X with two lines
        x_size = 6
        text_color = imgui.get_color_u32_rgba(0.8, 0.8, 0.8, 1.0)
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
        
        # Restore style
        imgui.pop_style_var(1)
        
        # Handle window dragging
        if imgui.is_window_hovered() and imgui.is_mouse_clicked(0):
            self.dragging_window = True
            mouse_x, mouse_y = glfw.get_cursor_pos(self.window)
            win_x, win_y = glfw.get_window_pos(self.window)
            self.drag_offset_x = mouse_x
            self.drag_offset_y = mouse_y
        
        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(3)
    
    def render_main_window(self):
        """Render main application window with two-panel layout"""
        # Left Panel - File Selection (leave room for bottom button bar)
        button_bar_height = 60
        imgui.set_next_window_position(0, CUSTOM_TITLE_BAR_HEIGHT)
        imgui.set_next_window_size(self.left_panel_width, self.base_window_height - CUSTOM_TITLE_BAR_HEIGHT - button_bar_height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (14, 14))
        
        flags = (
            imgui.WINDOW_NO_TITLE_BAR |
            imgui.WINDOW_NO_RESIZE |
            imgui.WINDOW_NO_MOVE |
            imgui.WINDOW_NO_COLLAPSE
        )
        
        imgui.begin("##left_panel", flags=flags)
        
        # === Addon Name Section ===
        imgui.text("Addon Name:")
        imgui.push_item_width(-1)
        
        # If addon was just selected, the value has already been updated in self.addon_name
        # ImGui's input_text will pick up the new value on this frame
        if self.addon_just_selected:
            print(f"DEBUG: Addon just selected, current value: '{self.addon_name}'")
            self.addon_just_selected = False
        
        changed, new_value = imgui.input_text(
            "##addon_name",
            self.addon_name,
            256
        )
        if changed:
            print(f"DEBUG: Input changed from '{self.addon_name}' to '{new_value}'")
            self.addon_name = new_value
            # Update filtered addons when user types
            self.update_addon_filter(new_value)
        
        # Track if input is focused
        is_focused = imgui.is_item_focused()
        
        # Don't immediately hide dropdown when losing focus - give time for button click to register
        # Only show dropdown when input is focused
        # (Dropdown will close itself when a selection is made)
        # Check if input is focused and Enter is pressed
        if is_focused:
            # Handle arrow keys for dropdown navigation
            if self.show_addon_dropdown and len(self.filtered_addons) > 0:
                if imgui.is_key_pressed(imgui.KEY_DOWN_ARROW):
                    self.selected_addon_index = min(self.selected_addon_index + 1, len(self.filtered_addons) - 1)
                elif imgui.is_key_pressed(imgui.KEY_UP_ARROW):
                    self.selected_addon_index = max(self.selected_addon_index - 1, -1)
                elif imgui.is_key_pressed(imgui.KEY_ENTER) and self.selected_addon_index >= 0:
                    # Select the addon
                    self.addon_name = self.filtered_addons[self.selected_addon_index]
                    self.show_addon_dropdown = False
                    self.selected_addon_index = -1
                elif imgui.is_key_pressed(imgui.KEY_ESCAPE):
                    self.show_addon_dropdown = False
                    self.selected_addon_index = -1
        
        imgui.pop_item_width()
        
        # Show dropdown with available addons
        if self.show_addon_dropdown and len(self.filtered_addons) > 0:
            # Get current theme colors
            theme = self.theme_manager.get_theme()
            
            # Use theme colors for dropdown
            imgui.push_style_color(imgui.COLOR_CHILD_BACKGROUND, *theme['window_bg'])
            imgui.push_style_color(imgui.COLOR_BORDER, *theme['border'])
            imgui.push_style_var(imgui.STYLE_CHILD_ROUNDING, 4.0)
            imgui.push_style_var(imgui.STYLE_CHILD_BORDERSIZE, 1.0)
            
            # Calculate dropdown height
            item_height = 30  # Height per item
            num_items = len(self.filtered_addons)
            
            # If 5 or fewer items, show them all without scrollbar
            # Otherwise, show max 8 items with scrollbar
            if num_items <= 5:
                # Show exact height for all items (no scrollbar)
                # Add extra pixels to account for padding/borders/spacing
                dropdown_height = (num_items * item_height) + 45
            else:
                # Show max 8 items with scrollbar
                max_visible_items = 8
                dropdown_height = (max_visible_items * item_height) + 45
            
            dropdown_width = max(self.left_panel_width - 28, 100)  # Ensure minimum width
            
            imgui.begin_child("##addon_dropdown", dropdown_width, dropdown_height, border=True)
            
            for i, addon in enumerate(self.filtered_addons):
                is_selected = (i == self.selected_addon_index)
                
                # Highlight selected item with theme colors
                if is_selected:
                    imgui.push_style_color(imgui.COLOR_BUTTON, *theme['button_active'])
                else:
                    imgui.push_style_color(imgui.COLOR_BUTTON, *theme['button'])
                
                imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *theme['button_hover'])
                imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *theme['button_active'])
                
                if imgui.button(addon, width=-1, height=item_height):
                    print(f"DEBUG: Selected addon: '{addon}'")
                    self.addon_name = addon
                    print(f"DEBUG: self.addon_name set to: '{self.addon_name}'")
                    self.show_addon_dropdown = False
                    self.selected_addon_index = -1
                    # Clear the filter since we selected something
                    self.filtered_addons = []
                    self.addon_just_selected = True  # Flag to force input update next frame
                
                imgui.pop_style_color(3)
            
            imgui.end_child()
            imgui.pop_style_var(2)
            imgui.pop_style_color(2)
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # === Sound Source Selection ===
        imgui.text("Sound Source:")
        imgui.spacing()
        
        # Radio buttons for custom file vs internal sound
        if imgui.radio_button("Custom Sound", not self.use_internal_sound):
            self.use_internal_sound = False
        
        imgui.same_line()
        if imgui.radio_button("CS2 Sounds", self.use_internal_sound):
            self.use_internal_sound = True
            # Load internal sounds on first use
            if not self.internal_sounds_loaded and not self.loading_internal_sounds:
                self.load_internal_sounds()
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Use CS2's built-in sounds from game VPK files")
            imgui.text("Sounds are decompiled, copied to addon/sounds/ folder")
            imgui.text("Compiled to .vsnd_c and visible in Hammer asset browser")
            imgui.text("Behaves identically to custom sounds after import")
            if not self.vsnd_decompiler:
                imgui.spacing()
                imgui.text_colored("Note: Requires .NET 8 Desktop Runtime", 1.0, 0.8, 0.0, 1.0)
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        # Show .NET Runtime warning if vsnd_decompiler is not available
        if self.use_internal_sound and not self.vsnd_decompiler:
            imgui.spacing()
            imgui.push_text_wrap_pos(self.left_panel_width - 14)
            imgui.text_colored("⚠ .NET 8 Runtime Required", 1.0, 0.6, 0.0, 1.0)
            imgui.text_colored("Internal sounds require .NET Desktop Runtime 8.0", 0.9, 0.9, 0.0, 1.0)
            imgui.pop_text_wrap_pos()
            
            if imgui.button("Download .NET 8 Runtime", width=-1, height=25):
                import webbrowser
                webbrowser.open("https://dotnet.microsoft.com/download/dotnet/8.0/runtime")
            if imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.text("Opens Microsoft's official .NET download page")
                imgui.text("Install: .NET Desktop Runtime 8.0 (x64)")
                imgui.text("After installation, restart Sound Manager")
                imgui.end_tooltip()
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # === Sound File/Internal Sound Selection ===
        if not self.use_internal_sound:
            # Custom file browser
            imgui.text("Sound File:")
            
            # File path display with color
            imgui.push_style_color(imgui.COLOR_TEXT, *self.sound_status_color)
            # Wrap text to fit in narrow panel
            imgui.push_text_wrap_pos(self.left_panel_width - 28)
            imgui.text(self.sound_file_display)
            imgui.pop_text_wrap_pos()
            imgui.pop_style_color(1)
            
            imgui.spacing()
            
            # Browse button
            if imgui.button("Browse Sound", width=-1, height=30):
                self.browse_sound_file()
            
            # Output name field (only show when a file is selected)
            if self.sound_file_path:
                imgui.spacing()
                imgui.separator()
                imgui.spacing()
                
                imgui.text("Output Name:")
                imgui.spacing()
                
                # Input field for output name
                changed, new_output_name = imgui.input_text(
                    "##output_name",
                    self.output_name,
                    256
                )
                if changed:
                    self.output_name = new_output_name
                
                imgui.spacing()
            
            # Preview controls for custom sounds
            if self.sound_file_path:
                imgui.spacing()
                imgui.separator()
                imgui.spacing()
                
                # Preview button with icon
                button_width = (self.left_panel_width - 28 - 7) / 2  # Split width for two buttons
                
                if self.play_icon:
                    # Use icon button
                    if imgui.image_button(self.play_icon, 20, 20):
                        self.play_sound_file(self.sound_file_path)
                    if imgui.is_item_hovered():
                        imgui.begin_tooltip()
                        imgui.text("Play Sound")
                        imgui.end_tooltip()
                else:
                    # Fallback to text button
                    if imgui.button("Play", width=button_width, height=25):
                        self.play_sound_file(self.sound_file_path)
                
                imgui.same_line()
                
                # Stop button with icon
                if self.pause_icon:
                    # Use icon button
                    if imgui.image_button(self.pause_icon, 20, 20):
                        self.stop_sound()
                    if imgui.is_item_hovered():
                        imgui.begin_tooltip()
                        imgui.text("Stop Sound")
                        imgui.end_tooltip()
                else:
                    # Fallback to text button
                    if imgui.button("Stop", width=button_width, height=25):
                        self.stop_sound()
                
                imgui.spacing()
                
                imgui.text("Preview Volume:")
                imgui.spacing()
                
                # Volume slider
                changed, self.preview_volume = imgui.slider_float(
                    "##preview_vol", 
                    self.preview_volume, 
                    0.0, 
                    1.0, 
                    "%.2f"
                )
                if changed:
                    pygame.mixer.music.set_volume(self.preview_volume)
                
                imgui.spacing()
        else:
            # Internal sound browser
            imgui.text("Search:")
            
            if self.loading_internal_sounds:
                imgui.text_colored("Loading...", 1.0, 1.0, 0.0)
            elif not self.internal_sounds_loaded:
                imgui.text_colored("Click 'Load Sounds' to browse", 1.0, 0.5, 0.0)
                if imgui.button("Load Sounds", width=-1, height=30):
                    self.load_internal_sounds()
            else:
                # Get current theme colors
                theme = self.theme_manager.get_theme()
                
                # Filter input
                changed, self.internal_sound_filter = imgui.input_text("##internal_filter", self.internal_sound_filter, 256)
                if changed:
                    self.filter_internal_sounds(self.internal_sound_filter)
                
                imgui.spacing()
                
                # Sound list in scrollable child window with tree structure
                imgui.begin_child("##internal_sounds_list", 0, 250, border=True)
                
                # Build tree structure from filtered sounds
                tree = {}
                for sound in self.filtered_internal_sounds:
                    parts = sound.split('/')
                    current = tree
                    for part in parts[:-1]:  # All but the last (filename)
                        if part not in current:
                            current[part] = {}
                        current = current[part]
                    # Add filename
                    if '__files__' not in current:
                        current['__files__'] = []
                    current['__files__'].append(sound)
                
                # Render tree recursively
                def render_tree(node, path=""):
                    # Render folders first
                    for folder_name in sorted([k for k in node.keys() if k != '__files__']):
                        folder_path = f"{path}/{folder_name}" if path else folder_name
                        
                        imgui.push_style_color(imgui.COLOR_HEADER_HOVERED, *theme['button_hover'])
                        imgui.push_style_color(imgui.COLOR_HEADER_ACTIVE, *theme['button_active'])
                        imgui.push_style_color(imgui.COLOR_HEADER, *theme['button'])
                        
                        # Tree node for folder
                        opened = imgui.tree_node(f"{folder_name}###{folder_path}")
                        
                        imgui.pop_style_color(3)
                        
                        if opened:
                            render_tree(node[folder_name], folder_path)
                            imgui.tree_pop()
                    
                    # Render files in this folder
                    if '__files__' in node:
                        for sound in sorted(node['__files__']):
                            is_selected = (sound == self.selected_internal_sound)
                            display_name = os.path.basename(sound)
                            
                            imgui.push_style_color(imgui.COLOR_HEADER_HOVERED, *theme['button_hover'])
                            imgui.push_style_color(imgui.COLOR_HEADER_ACTIVE, *theme['button_active'])
                            
                            if is_selected:
                                imgui.push_style_color(imgui.COLOR_HEADER, *theme['button_active'])
                            else:
                                imgui.push_style_color(imgui.COLOR_HEADER, *theme['button'])
                            
                            clicked, _ = imgui.selectable(f"  {display_name}###{sound}", is_selected)
                            if clicked:
                                self.selected_internal_sound = sound
                                self.sound_name = display_name
                                self.output_name = display_name
                                self.preview_internal_sound()
                            
                            imgui.pop_style_color(3)
                
                render_tree(tree)
                
                imgui.end_child()
                
                # Show selected sound (also just filename)
                if self.selected_internal_sound:
                    imgui.spacing()
                    imgui.text_colored("Selected:", 0.0, 1.0, 0.0)
                    imgui.push_text_wrap_pos(self.left_panel_width - 28)
                    imgui.text(os.path.basename(self.selected_internal_sound))
                    imgui.pop_text_wrap_pos()
                    
                    # Output name field for internal sounds
                    imgui.spacing()
                    imgui.separator()
                    imgui.spacing()
                    
                    imgui.text("Output Name:")
                    imgui.spacing()
                    
                    # Input field for output name
                    changed, new_output_name = imgui.input_text(
                        "##output_name_internal",
                        self.output_name,
                        256
                    )
                    if changed:
                        self.output_name = new_output_name
                
                # === Preview Controls (moved here, right after sound list) ===
                imgui.spacing()
                imgui.separator()
                imgui.spacing()
                
                imgui.text("Preview Volume:")
                imgui.spacing()
                
                # Volume slider
                changed, self.preview_volume = imgui.slider_float(
                    "##preview_vol", 
                    self.preview_volume, 
                    0.0, 
                    1.0, 
                    "%.2f"
                )
                if changed:
                    pygame.mixer.music.set_volume(self.preview_volume)
                
                imgui.spacing()
                
                # Play/Stop buttons with icons
                button_width = (self.left_panel_width - 24 - imgui.get_style().item_spacing.x) / 2
                
                # Play button
                if self.play_icon:
                    if imgui.image_button(self.play_icon, 20, 20):
                        self.play_sound()
                    if imgui.is_item_hovered():
                        imgui.set_tooltip("Play Sound")
                else:
                    if imgui.button("Play", width=button_width, height=25):
                        self.play_sound()
                
                imgui.same_line()
                
                # Stop button
                if self.pause_icon:
                    if imgui.image_button(self.pause_icon, 20, 20):
                        self.stop_sound()
                    if imgui.is_item_hovered():
                        imgui.set_tooltip("Stop Sound")
                else:
                    if imgui.button("Stop", width=button_width, height=25):
                        self.stop_sound()
        
        imgui.end()
        imgui.pop_style_var(2)
        
        # Right Panel - Sound Settings (leave room for bottom button bar)
        button_bar_height = 60
        imgui.set_next_window_position(self.left_panel_width, CUSTOM_TITLE_BAR_HEIGHT)
        imgui.set_next_window_size(self.right_panel_width, self.base_window_height - CUSTOM_TITLE_BAR_HEIGHT - button_bar_height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (0, 0))
        
        imgui.begin("##right_panel", flags=flags)
        
        # Create a scrollable child region for all content
        imgui.begin_child("##right_panel_scroll", 0, 0, border=False, flags=imgui.WINDOW_ALWAYS_VERTICAL_SCROLLBAR)
        
        # Add padding back inside the scrollable region
        imgui.dummy(14, 14)
        imgui.indent(14)
        
        content_start_y = imgui.get_cursor_pos_y()
        
        # === Toggle Buttons (moved to top of right panel) ===
        imgui.text("Show Parameters:")
        imgui.spacing()
        
        changed, self.show_pitch = imgui.checkbox("Pitch", self.show_pitch)
        imgui.same_line()
        changed, self.show_occlusion = imgui.checkbox("Occlusion", self.show_occlusion)
        imgui.same_line()
        changed, self.use_wav_markers = imgui.checkbox("Use encoding.txt", self.use_wav_markers)
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Create encoding.txt for Source 2 audio compilation")
            imgui.text("Audio files must be stored in addon/sounds/ folder")
            imgui.text("Compiled .vsnd files generated in game directory")
            imgui.text("Configure: compression format, sample rate, normalization")
            imgui.text("Supports: MP3 (VBR 128-320 kbps), PCM, ADPCM")
            imgui.text("Loop points: native CS2 seamless looping (WAV/MP3)")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.same_line()
        imgui.text_colored("?", 0.5, 0.5, 1.0, 1.0)
        if imgui.is_item_hovered():
            imgui.set_mouse_cursor(imgui.MOUSE_CURSOR_HAND)
            imgui.begin_tooltip()
            imgui.text("Click for documentation")
            imgui.end_tooltip()
            if imgui.is_mouse_clicked(0):
                import webbrowser
                webbrowser.open("https://www.source2.wiki/CommunityGuides/encodingtxt?game=cs2")
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        imgui.text("Sound Settings")
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # Sound Type selection
        imgui.text("Sound Type:")
        imgui.spacing()
        
        # Enable text wrapping for descriptions
        imgui.push_text_wrap_pos(self.right_panel_width - 20)
        
        if imgui.radio_button("csgo_mega", self.sound_type == "csgo_mega"):
            self.sound_type = "csgo_mega"
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Standard sound type for most audio in CS2")
            imgui.text("Use for general sound events and ambient sounds")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.same_line()
        if imgui.radio_button("csgo_music", self.sound_type == "csgo_music"):
            self.sound_type = "csgo_music"
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Music sound type - volume affected by snd_musicvolume")
            imgui.text("Use for background music and musical elements")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.same_line()
        if imgui.radio_button("csgo_3d", self.sound_type == "csgo_3d"):
            self.sound_type = "csgo_3d"
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("3D positional sound type for ambient noises")
            imgui.text("Use for environmental sounds with spatial positioning")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.pop_text_wrap_pos()
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # Volume slider
        imgui.text("Volume:")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Sound volume multiplier")
            imgui.text("1.0 = full power, 0.0 = silent")
            imgui.text("Can exceed 1.0 for amplification")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        imgui.push_item_width(-1)
        changed, self.volume = imgui.slider_float("##volume", self.volume, 0.0, 50.0, "%.1f")
        imgui.pop_item_width()
        imgui.spacing()
        
        # Pitch slider (conditional)
        if self.show_pitch:
            imgui.text("Pitch:")
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Audio pitch and playback speed multiplier")
                imgui.text("1.0 = original pitch and speed")
                imgui.text("2.0 = one octave higher, twice as fast")
                imgui.text("0.5 = one octave lower, half speed")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            imgui.push_item_width(-1)
            changed, self.pitch = imgui.slider_float("##pitch", self.pitch, 0.1, 3.0, "%.2f")
            imgui.pop_item_width()
            imgui.spacing()
        
        # Occlusion slider (conditional, moved under pitch)
        if self.show_occlusion:
            imgui.text("Occlusion Intensity:")
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("How much sounds are muffled when blocked by geometry")
                imgui.text("Percentage value: 0 = no occlusion, 100 = full muffling")
                imgui.text("Applied when player has no line of sight to sound origin")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            imgui.push_item_width(-1)
            changed, self.occlusion_intensity = imgui.slider_float("##occlusion", self.occlusion_intensity, 0.0, 100.0, "%.0f")
            imgui.pop_item_width()
            imgui.spacing()
        
        imgui.text("Distance Volume Curve")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Position-based volume attenuation mapping")
            imgui.text("Define how volume changes with distance from sound origin")
            imgui.text("Distance in Hammer Units, Volume 0.0 (silent) to 1.0 (full)")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.same_line()
        if imgui.button("Visualize" if not self.show_visualizer else "Hide"):
            self.show_visualizer = not self.show_visualizer
            # Update window width based on visualizer state
            if self.show_visualizer:
                self.window_width = self.base_window_width + self.visualizer_width
            else:
                self.window_width = self.base_window_width
            glfw.set_window_size(self.window, self.window_width, self.base_window_height)
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Show visual representation of distance volume curve")
            imgui.text("Displays how volume falloff works with Bézier interpolation")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.same_line()
        if imgui.button("Edit Curves" if not self.show_curve_editor else "Hide Curves"):
            self.show_curve_editor = not self.show_curve_editor
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Edit Bézier curve control points for custom falloff shapes")
            imgui.text("Control points define interpolation between distance points")
            imgui.text("Create exponential, logarithmic, or custom attenuation curves")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.spacing()
        
        # Column widths
        distance_col_width = 220
        volume_col_width = 220
        
        # Near distance settings (side by side)
        imgui.columns(2, "near_columns", False)
        imgui.set_column_width(0, distance_col_width)
        imgui.set_column_width(1, volume_col_width)
        
        imgui.text("Near Distance (units):")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("First control point - closest distance to sound origin")
            imgui.text("Measured in Hammer Units from entity origin")
            imgui.text("Typically set to 0 or very close to sound source")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        # Calculate width based on text length (min 50px, max 100px)
        text_width = max(50, min(100, len(f"{self.distance_near:.0f}") * 10 + 20))
        imgui.push_item_width(text_width)
        changed, new_value = imgui.input_float("##dist_near_input", self.distance_near, 0.0, 0.0, "%.0f")
        if changed:
            # Near can't exceed Mid or Far, and must be non-negative
            self.distance_near = max(0.0, min(new_value, self.distance_mid))
        imgui.pop_item_width()
        
        imgui.same_line()
        imgui.push_item_width(-1)
        # Near can't exceed Mid
        max_near = min(self.distance_mid, 10000.0)
        changed, self.distance_near = imgui.slider_float("##dist_near", self.distance_near, 0.0, max_near, "")
        imgui.pop_item_width()
        
        imgui.next_column()
        
        imgui.text("Near Volume:")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Volume at near distance point")
            imgui.text("1.0 = full power, 0.0 = silent")
            imgui.text("Usually set to 1.0 for full volume at source")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        # Calculate width for volume input box (min 45px, max 70px)
        vol_text_width = max(45, min(70, len(f"{self.distance_near_volume:.1f}") * 10 + 20))
        imgui.push_item_width(volume_col_width - vol_text_width - 20)
        changed, self.distance_near_volume = imgui.slider_float("##vol_near", self.distance_near_volume, 0.0, 1.0, "")
        imgui.pop_item_width()
        
        imgui.same_line()
        imgui.push_item_width(vol_text_width)
        changed, new_value = imgui.input_float("##vol_near_input", self.distance_near_volume, 0.0, 0.0, "%.1f")
        if changed:
            self.distance_near_volume = max(0.0, min(new_value, 1.0))
        imgui.pop_item_width()
        
        imgui.columns(1)
        imgui.spacing()
        
        # Mid distance settings (side by side)
        imgui.columns(2, "mid_columns", False)
        imgui.set_column_width(0, distance_col_width)
        imgui.set_column_width(1, volume_col_width)
        
        imgui.text("Mid Distance (units):")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Second control point - middle falloff distance")
            imgui.text("Measured in Hammer Units from entity origin")
            imgui.text("Defines transition range for volume attenuation")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        # Calculate width based on text length (min 50px, max 100px)
        text_width = max(50, min(100, len(f"{self.distance_mid:.0f}") * 10 + 20))
        imgui.push_item_width(text_width)
        changed, new_value = imgui.input_float("##dist_mid_input", self.distance_mid, 0.0, 0.0, "%.0f")
        if changed:
            # Mid must be between Near and Far
            self.distance_mid = max(self.distance_near, min(new_value, self.distance_far))
        imgui.pop_item_width()
        
        imgui.same_line()
        imgui.push_item_width(-1)
        # Mid must be between Near and Far
        min_mid = self.distance_near
        max_mid = min(self.distance_far, 10000.0)
        changed, self.distance_mid = imgui.slider_float("##dist_mid", self.distance_mid, min_mid, max_mid, "")
        imgui.pop_item_width()
        
        imgui.next_column()
        
        imgui.text("Mid Volume:")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Volume at mid distance point")
            imgui.text("1.0 = full power, 0.0 = silent")
            imgui.text("Controls falloff curve steepness")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        # Calculate width for volume input box (min 45px, max 70px)
        vol_text_width = max(45, min(70, len(f"{self.distance_mid_volume:.1f}") * 10 + 20))
        imgui.push_item_width(volume_col_width - vol_text_width - 20)
        changed, self.distance_mid_volume = imgui.slider_float("##vol_mid", self.distance_mid_volume, 0.0, 1.0, "")
        imgui.pop_item_width()
        
        imgui.same_line()
        imgui.push_item_width(vol_text_width)
        changed, new_value = imgui.input_float("##vol_mid_input", self.distance_mid_volume, 0.0, 0.0, "%.1f")
        if changed:
            self.distance_mid_volume = max(0.0, min(new_value, 1.0))
        imgui.pop_item_width()
        
        imgui.columns(1)
        imgui.spacing()
        
        # Far distance settings (side by side)
        imgui.columns(2, "far_columns", False)
        imgui.set_column_width(0, distance_col_width)
        imgui.set_column_width(1, volume_col_width)
        
        imgui.text("Far Distance (units):")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Third control point - maximum audible distance")
            imgui.text("Measured in Hammer Units from entity origin")
            imgui.text("Beyond this distance, sound is typically inaudible")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        # Calculate width based on text length (min 50px, max 100px)
        text_width = max(50, min(100, len(f"{self.distance_far:.0f}") * 10 + 20))
        imgui.push_item_width(text_width)
        changed, new_value = imgui.input_float("##dist_far_input", self.distance_far, 0.0, 0.0, "%.0f")
        if changed:
            # Far must be at least Mid
            self.distance_far = max(self.distance_mid, new_value)
        imgui.pop_item_width()
        
        imgui.same_line()
        imgui.push_item_width(-1)
        # Far must be at least Mid
        min_far = self.distance_mid
        changed, self.distance_far = imgui.slider_float("##dist_far", self.distance_far, min_far, 10000.0, "")
        imgui.pop_item_width()
        
        imgui.next_column()
        
        imgui.text("Far Volume:")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Volume at far distance point")
            imgui.text("1.0 = full power, 0.0 = silent")
            imgui.text("Usually set to 0.0 for complete silence at max range")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        # Calculate width for volume input box (min 45px, max 70px)
        vol_text_width = max(45, min(70, len(f"{self.distance_far_volume:.1f}") * 10 + 20))
        imgui.push_item_width(volume_col_width - vol_text_width - 20)
        changed, self.distance_far_volume = imgui.slider_float("##vol_far", self.distance_far_volume, 0.0, 1.0, "")
        imgui.pop_item_width()
        
        imgui.same_line()
        imgui.push_item_width(vol_text_width)
        changed, new_value = imgui.input_float("##vol_far_input", self.distance_far_volume, 0.0, 0.0, "%.1f")
        if changed:
            self.distance_far_volume = max(0.0, min(new_value, 1.0))
        imgui.pop_item_width()
        
        imgui.columns(1)
        imgui.spacing()
        
        # Curve point editors (conditional)
        if self.show_curve_editor:
            imgui.separator()
            imgui.spacing()
            imgui.text("Curve Control Points (Bézier)")
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Bézier curve control points for volume interpolation")
                imgui.text("Each segment uses 4 control points (curve point #1-4)")
                imgui.text("Format: [distance, volume, cp1, cp2, cp3, cp4]")
                imgui.text("Adjust for exponential, logarithmic, or custom curves")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            imgui.spacing()
            
            # Near to Mid curve points
            imgui.text("Near → Mid Curve:")
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Control points for interpolation from Near to Mid distance")
                imgui.text("Defines volume falloff curve shape in close-range zone")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            imgui.spacing()
            
            # Use 2x2 layout for curve points
            imgui.columns(2, "curve_near_mid_columns", False)
            imgui.set_column_width(0, 220)
            imgui.set_column_width(1, 220)
            
            imgui.text("Control Point 1:")
            imgui.push_item_width(-1)
            changed, self.curve_near_mid_cp1 = imgui.slider_float("##curve_near_mid_cp1", self.curve_near_mid_cp1, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.next_column()
            
            imgui.text("Control Point 2:")
            imgui.push_item_width(-1)
            changed, self.curve_near_mid_cp2 = imgui.slider_float("##curve_near_mid_cp2", self.curve_near_mid_cp2, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.next_column()
            
            imgui.text("Control Point 3:")
            imgui.push_item_width(-1)
            changed, self.curve_near_mid_cp3 = imgui.slider_float("##curve_near_mid_cp3", self.curve_near_mid_cp3, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.next_column()
            
            imgui.text("Control Point 4:")
            imgui.push_item_width(-1)
            changed, self.curve_near_mid_cp4 = imgui.slider_float("##curve_near_mid_cp4", self.curve_near_mid_cp4, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.columns(1)
            imgui.spacing()
            
            # Mid to Far curve points
            imgui.text("Mid → Far Curve:")
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Control points for interpolation from Mid to Far distance")
                imgui.text("Defines volume falloff curve shape in long-range zone")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            imgui.spacing()
            
            imgui.columns(2, "curve_mid_far_columns", False)
            imgui.set_column_width(0, 220)
            imgui.set_column_width(1, 220)
            
            imgui.text("Control Point 1:")
            imgui.push_item_width(-1)
            changed, self.curve_mid_far_cp1 = imgui.slider_float("##curve_mid_far_cp1", self.curve_mid_far_cp1, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.next_column()
            
            imgui.text("Control Point 2:")
            imgui.push_item_width(-1)
            changed, self.curve_mid_far_cp2 = imgui.slider_float("##curve_mid_far_cp2", self.curve_mid_far_cp2, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.next_column()
            
            imgui.text("Control Point 3:")
            imgui.push_item_width(-1)
            changed, self.curve_mid_far_cp3 = imgui.slider_float("##curve_mid_far_cp3", self.curve_mid_far_cp3, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.next_column()
            
            imgui.text("Control Point 4:")
            imgui.push_item_width(-1)
            changed, self.curve_mid_far_cp4 = imgui.slider_float("##curve_mid_far_cp4", self.curve_mid_far_cp4, 0.0, 1.0, "%.3f")
            imgui.pop_item_width()
            
            imgui.columns(1)
            imgui.spacing()
        
        # Render encoding.txt configuration options if enabled
        self.render_encoding_options()
        
        # Add bottom padding
        imgui.dummy(14, 14)
        
        # Close the scrollable child region
        imgui.unindent(14)
        imgui.end_child()
        
        imgui.end()
        imgui.pop_style_var(2)
        
        # Visualizer panel (conditional, shown to the right of the main content)
        if self.show_visualizer:
            visualizer_x = self.left_panel_width + self.right_panel_width
            button_bar_height = 60
            imgui.set_next_window_position(visualizer_x, CUSTOM_TITLE_BAR_HEIGHT)
            imgui.set_next_window_size(self.visualizer_width, self.base_window_height - CUSTOM_TITLE_BAR_HEIGHT - button_bar_height)
            
            imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (14, 14))
            
            imgui.begin("##visualizer_panel", flags=flags)
            
            imgui.text("Distance Volume Visualizer")
            imgui.spacing()
            imgui.separator()
            imgui.spacing()
            
            # Render the visualization
            self.render_distance_visualizer()
            
            imgui.end()
            imgui.pop_style_var(2)
        
        # Bottom action buttons bar (spanning full window width)
        button_bar_height = 60
        imgui.set_next_window_position(0, self.base_window_height - button_bar_height)
        imgui.set_next_window_size(self.window_width, button_bar_height)
        
        imgui.push_style_var(imgui.STYLE_WINDOW_BORDERSIZE, 0.0)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (14, 10))
        
        imgui.begin("##bottom_bar", flags=flags)
        
        # Calculate button widths
        button_width = 150
        button_spacing = 10
        total_button_width = (button_width * 2) + button_spacing
        
        # Position buttons on the right side
        imgui.set_cursor_pos_x(self.window_width - total_button_width - 14)
        
        # Open Folder button (Yellow)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.8, 0.7, 0.2, 1.0)  # Yellow
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.9, 0.8, 0.3, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.7, 0.6, 0.15, 1.0)
        
        if imgui.button("Open Folder", width=button_width, height=40):
            self.open_addon_sounds_folder()
        
        imgui.pop_style_color(3)
        
        imgui.same_line(spacing=button_spacing)
        
        # Add Sound button (Green)
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.2, 0.7, 0.3, 1.0)  # Green
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.3, 0.8, 0.4, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.15, 0.6, 0.25, 1.0)
        
        if imgui.button("Add Sound", width=button_width, height=40):
            self.add_sound()
        
        imgui.pop_style_color(3)
        
        imgui.end()
        imgui.pop_style_var(2)
    
    def reapply_theme(self):
        """Reapply theme colors when theme changes"""
        theme = self.theme_manager.get_theme()
        style = imgui.get_style()
        
        # Apply theme colors
        style.colors[imgui.COLOR_WINDOW_BACKGROUND] = theme['window_bg']
        style.colors[imgui.COLOR_BUTTON] = theme['button']
        style.colors[imgui.COLOR_BUTTON_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_BUTTON_ACTIVE] = theme['button_active']
        style.colors[imgui.COLOR_BORDER] = theme['border']
        style.colors[imgui.COLOR_TEXT] = theme['text']
        style.colors[imgui.COLOR_FRAME_BACKGROUND] = theme['button']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_HOVERED] = theme['button_hover']
        style.colors[imgui.COLOR_FRAME_BACKGROUND_ACTIVE] = theme['button_active']
        
        # Slider colors (match theme)
        style.colors[imgui.COLOR_SLIDER_GRAB] = theme['button_active']
        style.colors[imgui.COLOR_SLIDER_GRAB_ACTIVE] = theme['button_hover']
        
        # Checkbox colors (match theme)
        style.colors[imgui.COLOR_CHECK_MARK] = theme['button_active']
        
        # No need to reload font as we always use Consolas now
        new_theme_name = self.theme_manager.get_theme_name()
        self.current_theme_name = new_theme_name
    
    def calculate_visualizer_color(self, distance, volume, max_distance):
        """Calculate color for a distance circle based on distance and volume.
        Color interpolates from green (close/loud) to red (far/quiet)."""
        
        # Normalize distance relative to the actual max distance being visualized
        if max_distance > 0:
            distance_factor = min(distance / max_distance, 1.0)
        else:
            distance_factor = 0.0
        
        # Volume factor (0-1, where 1 is loudest)
        volume_factor = volume
        
        # Combined factor: weighted average of distance and volume
        # Distance has more weight (70%) since it's the primary indicator
        # Volume has less weight (30%) but affects color intensity
        combined_factor = (distance_factor * 0.7) + ((1.0 - volume_factor) * 0.3)
        
        # Interpolate from green (0.0) to red (1.0)
        # Green: (0.0, 1.0, 0.0), Red: (1.0, 0.0, 0.0)
        r = combined_factor
        g = 1.0 - combined_factor
        b = 0.0
        
        return (r, g, b, 1.0)
    
    def render_distance_visualizer(self):
        """Render the distance volume visualizer panel."""
        draw_list = imgui.get_window_draw_list()
        
        # Get panel dimensions and position
        panel_pos = imgui.get_cursor_screen_pos()
        panel_width = self.visualizer_width - 28  # Account for padding
        panel_height = self.base_window_height - CUSTOM_TITLE_BAR_HEIGHT - 60 - 28  # Subtract title bar, button bar, padding
        
        # Center point (red dot)
        center_x = panel_pos[0] + panel_width / 2
        center_y = panel_pos[1] + panel_height / 2
        
        # Calculate max radius based on available space
        max_radius = min(panel_width, panel_height) / 2 - 40  # Leave margin
        
        # Normalize distances to fit in visualization
        max_distance = max(self.distance_near, self.distance_mid, self.distance_far)
        if max_distance == 0:
            max_distance = 1.0  # Avoid division by zero
        
        # Calculate radii for each circle (scaled to fit)
        near_radius = (self.distance_near / max_distance) * max_radius if max_distance > 0 else 5
        mid_radius = (self.distance_mid / max_distance) * max_radius if max_distance > 0 else max_radius * 0.5
        far_radius = (self.distance_far / max_distance) * max_radius if max_distance > 0 else max_radius
        
        # Ensure minimum radius for visibility
        near_radius = max(near_radius, 5)
        mid_radius = max(mid_radius, near_radius + 10)
        far_radius = max(far_radius, mid_radius + 10)
        
        # Calculate colors based on volume only
        # Volume gradient: high volume (loud) = green, low volume (quiet) = red
        def volume_to_color(volume, alpha):
            """Convert volume (0-1) to color gradient from red (quiet) to green (loud)"""
            # Invert so high volume = green, low volume = red
            r = 1.0 - volume
            g = volume
            b = 0.0
            return imgui.get_color_u32_rgba(r, g, b, alpha)
        
        # Draw filled circles (solid colors, no gradient)
        far_color = volume_to_color(self.distance_far_volume, alpha=0.3)
        mid_color = volume_to_color(self.distance_mid_volume, alpha=0.3)
        near_color = volume_to_color(self.distance_near_volume, alpha=0.3)
        
        draw_list.add_circle_filled(center_x, center_y, far_radius, far_color, 64)
        draw_list.add_circle_filled(center_x, center_y, mid_radius, mid_color, 64)
        draw_list.add_circle_filled(center_x, center_y, near_radius, near_color, 64)
        
        # Bézier curve interpolation function
        def cubic_bezier(t, p0, p1, p2, p3):
            """Cubic Bézier curve interpolation"""
            return (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3
        
        # Draw intermediate circles to visualize volume curve
        # These are semi-transparent circles with tooltips showing interpolated values
        intermediate_circles = []
        
        # Between Near and Mid (using Bézier curve with control points)
        if abs(self.distance_mid - self.distance_near) > 100:  # Only if there's significant distance
            steps = 20  # Fixed number of steps for smooth curve
            for i in range(1, steps):
                t = i / steps
                
                # Linear interpolation for distance
                interp_distance = self.distance_near + (self.distance_mid - self.distance_near) * t
                
                # Bézier interpolation for volume using curve control points
                # Map control points (0-1 range) to volume range
                cp1 = self.distance_near_volume + (self.distance_mid_volume - self.distance_near_volume) * self.curve_near_mid_cp1
                cp2 = self.distance_near_volume + (self.distance_mid_volume - self.distance_near_volume) * self.curve_near_mid_cp2
                cp3 = self.distance_near_volume + (self.distance_mid_volume - self.distance_near_volume) * self.curve_near_mid_cp3
                cp4 = self.distance_near_volume + (self.distance_mid_volume - self.distance_near_volume) * self.curve_near_mid_cp4
                
                interp_volume = cubic_bezier(t, self.distance_near_volume, cp1, cp3, self.distance_mid_volume)
                
                interp_radius = (interp_distance / max_distance) * max_radius if max_distance > 0 else 0
                intermediate_circles.append((interp_distance, interp_volume, interp_radius))
        
        # Between Mid and Far (using Bézier curve with control points)
        if abs(self.distance_far - self.distance_mid) > 100:  # Only if there's significant distance
            steps = 20  # Fixed number of steps for smooth curve
            for i in range(1, steps):
                t = i / steps
                
                # Linear interpolation for distance
                interp_distance = self.distance_mid + (self.distance_far - self.distance_mid) * t
                
                # Bézier interpolation for volume using curve control points
                # Map control points (0-1 range) to volume range
                cp1 = self.distance_mid_volume + (self.distance_far_volume - self.distance_mid_volume) * self.curve_mid_far_cp1
                cp2 = self.distance_mid_volume + (self.distance_far_volume - self.distance_mid_volume) * self.curve_mid_far_cp2
                cp3 = self.distance_mid_volume + (self.distance_far_volume - self.distance_mid_volume) * self.curve_mid_far_cp3
                cp4 = self.distance_mid_volume + (self.distance_far_volume - self.distance_mid_volume) * self.curve_mid_far_cp4
                
                interp_volume = cubic_bezier(t, self.distance_mid_volume, cp1, cp3, self.distance_far_volume)
                
                interp_radius = (interp_distance / max_distance) * max_radius if max_distance > 0 else 0
                intermediate_circles.append((interp_distance, interp_volume, interp_radius))
        
        # Draw intermediate circles (smaller, more transparent)
        for dist, vol, radius in intermediate_circles:
            if radius > 0:
                interp_color = volume_to_color(vol, alpha=0.5)
                draw_list.add_circle(center_x, center_y, radius, interp_color, 64, 1.0)
        
        # Draw border circles for each distance (opaque borders)
        near_color_border = volume_to_color(self.distance_near_volume, alpha=1.0)
        mid_color_border = volume_to_color(self.distance_mid_volume, alpha=1.0)
        far_color_border = volume_to_color(self.distance_far_volume, alpha=1.0)
        
        draw_list.add_circle(center_x, center_y, near_radius, near_color_border, 64, 2.0)
        draw_list.add_circle(center_x, center_y, mid_radius, mid_color_border, 64, 2.0)
        draw_list.add_circle(center_x, center_y, far_radius, far_color_border, 64, 2.0)
        
        # Player representation (32 units wide, shaped like player from above)
        # Calculate pixel scale: how many pixels = 1 unit
        if max_distance > 0:
            pixels_per_unit = max_radius / max_distance
        else:
            pixels_per_unit = 1.0
        
        # Player dimensions in pixels (32 units wide, slightly taller)
        player_width = 32 * pixels_per_unit
        player_height = 24 * pixels_per_unit  # Slightly narrower front-to-back
        
        # Draw player as a capsule (rounded rectangle) - red color
        player_color = imgui.get_color_u32_rgba(1.0, 0.0, 0.0, 1.0)  # Red
        
        # Capsule is two circles connected by a rectangle
        # Top and bottom circles (shoulders and feet area)
        half_height = player_height / 2
        radius = player_width / 2
        
        # Top circle (shoulders)
        top_y = center_y - half_height
        draw_list.add_circle_filled(center_x, top_y, radius, player_color, 32)
        
        # Bottom circle (feet)
        bottom_y = center_y + half_height
        draw_list.add_circle_filled(center_x, bottom_y, radius, player_color, 32)
        
        # Rectangle connecting them
        draw_list.add_rect_filled(
            center_x - radius, top_y,
            center_x + radius, bottom_y,
            player_color
        )
        
        # Add labels for each circle (white text for visibility)
        # Far label
        far_label_y = center_y - far_radius - 20
        imgui.set_cursor_screen_pos((center_x - 80, far_label_y))
        imgui.text_colored(f"Far: {self.distance_far:.0f} units", 1.0, 1.0, 1.0, 1.0)
        imgui.same_line()
        imgui.text_colored(f"Vol: {self.distance_far_volume:.1f}", 1.0, 1.0, 1.0, 1.0)
        
        # Mid label
        mid_label_y = center_y - mid_radius - 20
        imgui.set_cursor_screen_pos((center_x - 80, mid_label_y))
        imgui.text_colored(f"Mid: {self.distance_mid:.0f} units", 1.0, 1.0, 1.0, 1.0)
        imgui.same_line()
        imgui.text_colored(f"Vol: {self.distance_mid_volume:.1f}", 1.0, 1.0, 1.0, 1.0)
        
        # Near label
        near_label_y = center_y - near_radius - 20
        imgui.set_cursor_screen_pos((center_x - 80, near_label_y))
        imgui.text_colored(f"Near: {self.distance_near:.0f} units", 1.0, 1.0, 1.0, 1.0)
        imgui.same_line()
        imgui.text_colored(f"Vol: {self.distance_near_volume:.1f}", 1.0, 1.0, 1.0, 1.0)
        
        # Check for mouse hover on intermediate circles and show tooltips
        mouse_pos = imgui.get_mouse_pos()
        mouse_x = mouse_pos[0]
        mouse_y = mouse_pos[1]
        
        # Calculate distance from mouse to center
        dx = mouse_x - center_x
        dy = mouse_y - center_y
        mouse_distance_from_center = (dx * dx + dy * dy) ** 0.5
        
        # Check if mouse is hovering over any intermediate circle (within tolerance)
        tooltip_shown = False
        tolerance = 5.0  # pixels
        for dist, vol, radius in intermediate_circles:
            if radius > 0 and abs(mouse_distance_from_center - radius) < tolerance:
                imgui.begin_tooltip()
                imgui.text(f"Distance: {dist:.0f} units")
                imgui.text(f"Volume: {vol:.2f}")
                imgui.end_tooltip()
                tooltip_shown = True
                break
    
    def render_audio_timeline(self):
        """Render audio timeline with waveform, loop markers, and playback position"""
        if self.audio_duration_ms == 0:
            return  # No audio loaded
        
        draw_list = imgui.get_window_draw_list()
        theme = self.theme_manager.get_theme()
        
        # Get timeline position
        timeline_pos = imgui.get_cursor_screen_pos()
        timeline_x = timeline_pos[0]
        timeline_y = timeline_pos[1]
        
        # Timeline dimensions
        width = self.timeline_width
        height = self.timeline_height
        
        # Background
        bg_color = imgui.get_color_u32_rgba(0.15, 0.15, 0.15, 1.0)
        draw_list.add_rect_filled(timeline_x, timeline_y, timeline_x + width, timeline_y + height, bg_color)
        
        # Border
        border_color = imgui.get_color_u32_rgba(*theme['border'])
        draw_list.add_rect(timeline_x, timeline_y, timeline_x + width, timeline_y + height, border_color, 0.0, 0, 1.0)
        
        # Draw waveform
        if len(self.audio_waveform) > 0:
            waveform_color = imgui.get_color_u32_rgba(0.3, 0.5, 0.7, 0.8)
            center_y = timeline_y + height / 2
            waveform_height = height * 0.85  # Use more of the height
            
            # Find maximum amplitude to normalize the waveform
            max_amplitude = max(self.audio_waveform) if self.audio_waveform else 1.0
            max_amplitude = max(max_amplitude, 0.01)  # Avoid division by zero
            
            for i, amplitude in enumerate(self.audio_waveform):
                x = timeline_x + (i / len(self.audio_waveform)) * width
                # Normalize amplitude so the highest peak fills the available height
                normalized_amplitude = amplitude / max_amplitude
                bar_height = normalized_amplitude * waveform_height / 2
                draw_list.add_line(x, center_y - bar_height, x, center_y + bar_height, waveform_color, 1.5)
        
        # Draw loop region if enabled
        if self.encoding_loop_enabled and self.audio_duration_ms > 0:
            loop_start_x = timeline_x + (self.encoding_loop_start_ms / self.audio_duration_ms) * width
            loop_end_x = timeline_x + (self.encoding_loop_end_ms / self.audio_duration_ms) * width
            
            # Loop region highlight
            loop_color = imgui.get_color_u32_rgba(0.2, 0.8, 0.2, 0.2)
            draw_list.add_rect_filled(loop_start_x, timeline_y, loop_end_x, timeline_y + height, loop_color)
            
            # Loop start marker (green line with handle)
            loop_start_color = imgui.get_color_u32_rgba(0.0, 1.0, 0.0, 1.0)
            draw_list.add_line(loop_start_x, timeline_y, loop_start_x, timeline_y + height, loop_start_color, 2.0)
            draw_list.add_circle_filled(loop_start_x, timeline_y + 10, 5, loop_start_color)
            
            # Loop end marker (red line with handle)
            loop_end_color = imgui.get_color_u32_rgba(1.0, 0.0, 0.0, 1.0)
            draw_list.add_line(loop_end_x, timeline_y, loop_end_x, timeline_y + height, loop_end_color, 2.0)
            draw_list.add_circle_filled(loop_end_x, timeline_y + 10, 5, loop_end_color)
            
            # Handle dragging
            mouse_pos = imgui.get_mouse_pos()
            mouse_x = mouse_pos[0]
            mouse_y = mouse_pos[1]
            
            # Check if mouse is over timeline
            if (timeline_x <= mouse_x <= timeline_x + width and 
                timeline_y <= mouse_y <= timeline_y + height):
                
                # Check for loop start handle click
                if abs(mouse_x - loop_start_x) < 8 and abs(mouse_y - (timeline_y + 10)) < 8:
                    if imgui.is_mouse_clicked(0):
                        self.dragging_loop_start = True
                    if imgui.is_mouse_down(0) and self.dragging_loop_start:
                        # Update loop start position
                        new_pos = ((mouse_x - timeline_x) / width) * self.audio_duration_ms
                        self.encoding_loop_start_ms = max(0, min(new_pos, self.encoding_loop_end_ms - 100))  # Min 100ms loop
                
                # Check for loop end handle click
                elif abs(mouse_x - loop_end_x) < 8 and abs(mouse_y - (timeline_y + 10)) < 8:
                    if imgui.is_mouse_clicked(0):
                        self.dragging_loop_end = True
                    if imgui.is_mouse_down(0) and self.dragging_loop_end:
                        # Update loop end position
                        new_pos = ((mouse_x - timeline_x) / width) * self.audio_duration_ms
                        self.encoding_loop_end_ms = max(self.encoding_loop_start_ms + 100, min(new_pos, self.audio_duration_ms))
            
            # Release dragging when mouse is released
            if not imgui.is_mouse_down(0):
                self.dragging_loop_start = False
                self.dragging_loop_end = False
        
        # Draw playback position if playing
        if self.preview_playing and pygame.mixer.music.get_busy():
            # Calculate elapsed time since playback started
            current_time = pygame.time.get_ticks()
            elapsed_ms = current_time - self.playback_start_time
            
            # Add the initial start position (for looped playback)
            start_offset = self.encoding_loop_start_ms if self.encoding_loop_enabled else 0
            self.playback_position_ms = start_offset + elapsed_ms
            
            # For non-looping playback, cap at duration
            if not self.encoding_loop_enabled:
                self.playback_position_ms = min(self.playback_position_ms, self.audio_duration_ms)
            else:
                # For looping playback, wrap around within the loop region
                loop_duration = self.encoding_loop_end_ms - self.encoding_loop_start_ms
                if loop_duration > 0:
                    position_in_loop = (self.playback_position_ms - self.encoding_loop_start_ms) % loop_duration
                    self.playback_position_ms = self.encoding_loop_start_ms + position_in_loop
            
            if self.audio_duration_ms > 0 and self.playback_position_ms <= self.audio_duration_ms:
                playback_x = timeline_x + (self.playback_position_ms / self.audio_duration_ms) * width
                playback_color = imgui.get_color_u32_rgba(1.0, 1.0, 1.0, 0.8)
                draw_list.add_line(playback_x, timeline_y, playback_x, timeline_y + height, playback_color, 2.0)
        elif self.preview_playing and not pygame.mixer.music.get_busy():
            # Music stopped, reset preview state
            self.preview_playing = False
            self.playback_position_ms = 0
        
        # Time labels
        imgui.set_cursor_screen_pos((timeline_x, timeline_y + height + 4))
        imgui.text_colored(f"0:00", 0.7, 0.7, 0.7, 1.0)
        
        duration_seconds = self.audio_duration_ms / 1000.0
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        imgui.same_line(timeline_x + width - 40)
        imgui.text_colored(f"{minutes}:{seconds:02d}", 0.7, 0.7, 0.7, 1.0)
        
        # Loop time labels if enabled
        if self.encoding_loop_enabled:
            loop_start_sec = self.encoding_loop_start_ms / 1000.0
            loop_end_sec = self.encoding_loop_end_ms / 1000.0
            imgui.set_cursor_screen_pos((timeline_x, timeline_y + height + 20))
            imgui.text_colored(f"Loop: {loop_start_sec:.2f}s - {loop_end_sec:.2f}s", 0.0, 1.0, 0.0, 1.0)
        
        # Reserve space for the timeline
        imgui.dummy(width, height + 35)
    
    def render_encoding_options(self):
        """Render encoding.txt configuration panel with all options"""
        if not self.use_wav_markers:
            return
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        imgui.text("encoding.txt Configuration (defaults)")
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.text("Default values shown in parentheses")
            imgui.text("Configure compression, sample rate, normalization, and loop points")
            imgui.end_tooltip()
        imgui.spacing()
        
        # === Compression Settings ===
        imgui.text("Compression Format:")
        imgui.spacing()
        
        if imgui.radio_button("PCM (Uncompressed)", self.encoding_format == "PCM"):
            self.encoding_format = "PCM"
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("PCM: Uncompressed audio")
            imgui.text("Highest quality, largest file size")
            imgui.text("Use for short, critical sounds requiring perfect fidelity")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.same_line()
        if imgui.radio_button("MP3 (Recommended)", self.encoding_format == "mp3"):
            self.encoding_format = "mp3"
            # Check for lame_enc.dll when MP3 is selected
            if self.cs2_basefolder:
                dll_path = os.path.join(self.cs2_basefolder, 'game', 'bin', 'win64', 'lame_enc.dll')
                if not os.path.exists(dll_path):
                    self.log("ℹ MP3 compression requires lame_enc.dll")
                    self.log("  It will be downloaded automatically when you add a sound")
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("MP3: Variable bitrate compression (VBR 128-320 kbps)")
            imgui.text("Good quality-to-size ratio, smaller files")
            imgui.text("Requires lame_enc.dll in game/bin/win64/")
            imgui.text("Recommended for most sounds and music")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.same_line()
        if imgui.radio_button("ADPCM", self.encoding_format == "adpcm"):
            self.encoding_format = "adpcm"
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("ADPCM: Adaptive compression")
            imgui.text("Lower quality, very small file size")
            imgui.text("Use for background ambience or less critical sounds")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.spacing()
        
        # MP3 Bitrate settings (only show if MP3 is selected)
        if self.encoding_format == "mp3":
            imgui.text("MP3 Bitrate Settings:")
            
            # Show lame_enc.dll status
            if self.cs2_basefolder:
                dll_path = os.path.join(self.cs2_basefolder, 'game', 'bin', 'win64', 'lame_enc.dll')
                if os.path.exists(dll_path):
                    imgui.same_line()
                    imgui.text_colored("(lame_enc.dll: OK)", 0.0, 1.0, 0.0, 1.0)
                else:
                    imgui.same_line()
                    imgui.text_colored("(lame_enc.dll: will download)", 1.0, 0.8, 0.0, 1.0)
            
            imgui.spacing()
            
            changed, self.encoding_minbitrate = imgui.slider_int(
                "Min Bitrate (128)##encoding", 
                self.encoding_minbitrate, 
                64, 
                320, 
                "%d kbps"
            )
            if imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.text("Minimum bitrate for variable bitrate encoding")
                imgui.text("Default: 128 kbps")
                imgui.end_tooltip()
            
            changed, self.encoding_maxbitrate = imgui.slider_int(
                "Max Bitrate (320)##encoding", 
                self.encoding_maxbitrate, 
                64, 
                320, 
                "%d kbps"
            )
            if imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.text("Maximum bitrate for variable bitrate encoding")
                imgui.text("Default: 320 kbps")
                imgui.end_tooltip()
            
            # Ensure min <= max
            if self.encoding_minbitrate > self.encoding_maxbitrate:
                self.encoding_maxbitrate = self.encoding_minbitrate
            
            changed, self.encoding_vbr = imgui.checkbox("Variable Bitrate (VBR) [enabled]##encoding", self.encoding_vbr)
            if imgui.is_item_hovered():
                imgui.begin_tooltip()
                imgui.text("Variable bitrate adjusts quality based on complexity")
                imgui.text("Recommended for best quality-to-size ratio")
                imgui.text("Default: enabled")
                imgui.end_tooltip()
            
            imgui.spacing()
        
        # === Sample Rate ===
        imgui.text("Sample Rate (Auto):")
        imgui.spacing()
        
        sample_rate_options = ["Auto", "22050 Hz", "44100 Hz", "48000 Hz"]
        sample_rate_values = [0, 22050, 44100, 48000]
        
        current_rate_idx = 0
        try:
            current_rate_idx = sample_rate_values.index(self.encoding_sample_rate)
        except ValueError:
            current_rate_idx = 0
        
        changed, new_rate_idx = imgui.combo(
            "##sample_rate",
            current_rate_idx,
            sample_rate_options
        )
        if changed:
            self.encoding_sample_rate = sample_rate_values[new_rate_idx]
        
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Sample rate: Audio samples per second (Hz)")
            imgui.text("Auto: Uses source file's original sample rate")
            imgui.text("22050 Hz: Low quality, smallest files")
            imgui.text("44100 Hz: CD quality, standard for most sounds")
            imgui.text("48000 Hz: High quality, professional audio standard")
            imgui.text("Higher rates = better quality but larger file size")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # === Normalization Settings ===
        imgui.text("Normalization:")
        imgui.spacing()
        
        changed, self.encoding_normalize = imgui.checkbox("Enable Normalization##encoding", self.encoding_normalize)
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Normalize: Adjust audio levels to target loudness")
            imgui.text("Ensures consistent volume across different source files")
            imgui.text("Prevents clipping and optimizes perceived loudness")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        if self.encoding_normalize:
            imgui.spacing()
            imgui.indent(20)
            
            changed, self.encoding_normalize_level = imgui.slider_float(
                "Target Level (-3.0 dB)##encoding",
                self.encoding_normalize_level,
                -24.0,
                0.0,
                "%.1f dB"
            )
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Target loudness level in decibels (dB)")
                imgui.text("-3.0 dB: Recommended for most sounds (default)")
                imgui.text("-6.0 dB: Quieter, more dynamic range")
                imgui.text("0.0 dB: Maximum loudness, risk of clipping")
                imgui.text("Lower values preserve more dynamic range")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            
            changed, self.encoding_normalize_compression = imgui.checkbox("Compression [disabled]##encoding", self.encoding_normalize_compression)
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Dynamic range compression")
                imgui.text("Reduces difference between loud and quiet parts")
                imgui.text("Makes quiet sections more audible")
                imgui.text("Use for dialogue or consistent-volume sounds")
                imgui.text("Default: disabled")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            
            imgui.same_line()
            changed, self.encoding_normalize_limiter = imgui.checkbox("Limiter [disabled]##encoding", self.encoding_normalize_limiter)
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Peak limiter - prevents audio clipping")
                imgui.text("Caps maximum volume to prevent distortion")
                imgui.text("Useful when normalizing to high target levels")
                imgui.text("Default: disabled")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            
            imgui.unindent(20)
        
        imgui.spacing()
        imgui.separator()
        imgui.spacing()
        
        # === Loop Points ===
        imgui.text("Loop Points:")
        imgui.spacing()
        
        changed, self.encoding_loop_enabled = imgui.checkbox("Enable Loop Points##encoding", self.encoding_loop_enabled)
        if imgui.is_item_hovered():
            imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
            imgui.begin_tooltip()
            imgui.text("Loop Points: Define custom start/end for seamless audio loops")
            imgui.text("Creates cue points for Source 2 native looping support")
            imgui.text("Both WAV and MP3 files can be looped in Source 2")
            imgui.text("Use for music, ambient sounds, and repeating effects")
            imgui.end_tooltip()
            imgui.pop_style_var(1)
        
        if self.encoding_loop_enabled and self.audio_duration_ms > 0:
            imgui.spacing()
            
            # Crossfade duration
            changed, self.encoding_crossfade_ms = imgui.slider_int(
                "Crossfade (1 ms)##encoding",
                self.encoding_crossfade_ms,
                0,
                100,
                "%d ms"
            )
            if imgui.is_item_hovered():
                imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 6))
                imgui.begin_tooltip()
                imgui.text("Crossfade duration for smooth loop transitions")
                imgui.text("Blends loop end back to loop start")
                imgui.text("0 ms: Instant loop (may cause clicks)")
                imgui.text("1-10 ms: Short fade (most sounds)")
                imgui.text("10-100 ms: Longer fade (ambient/music)")
                imgui.text("Default: 1 ms")
                imgui.end_tooltip()
                imgui.pop_style_var(1)
            
            imgui.spacing()
            
            # Loop preview controls
            imgui.text("Preview Loop:")
            imgui.same_line()
            
            # Play loop button with icon
            if self.play_icon:
                if imgui.image_button(self.play_icon, 20, 20):
                    self.play_loop_region()
                if imgui.is_item_hovered():
                    imgui.begin_tooltip()
                    imgui.text("Play Loop Region")
                    imgui.end_tooltip()
            else:
                if imgui.button("Play Loop", width=80, height=25):
                    self.play_loop_region()
            
            imgui.same_line()
            
            # Stop button with icon
            if self.pause_icon:
                if imgui.image_button(self.pause_icon, 20, 20):
                    self.stop_sound()
                if imgui.is_item_hovered():
                    imgui.begin_tooltip()
                    imgui.text("Stop Loop")
                    imgui.end_tooltip()
            else:
                if imgui.button("Stop Loop", width=80, height=25):
                    self.stop_sound()
            
            # Show ffmpeg status for internal sounds
            if self.use_internal_sound and self.cached_internal_sound_path:
                # Check if cached sound is MP3
                is_mp3 = self.cached_internal_sound_path.lower().endswith('.mp3')
                
                if is_mp3:
                    imgui.spacing()
                    imgui.text_colored("(i) Internal sounds as MP3 (limited loop support)", 0.8, 0.8, 0.0, 1.0)
                    
                    # Show ffmpeg download button
                    if self.ffmpeg_path and os.path.exists(self.ffmpeg_path):
                        imgui.text_colored("ffmpeg + ffprobe available", 0.0, 1.0, 0.0, 1.0)
                        imgui.same_line()
                        if imgui.button("Open Folder", width=100, height=25):
                            ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
                            os.startfile(ffmpeg_dir)
                        if imgui.is_item_hovered():
                            imgui.begin_tooltip()
                            imgui.text("Open ffmpeg installation folder")
                            imgui.end_tooltip()
                    elif self.downloading_ffmpeg:
                        imgui.text_colored("⏳ Downloading ffmpeg + ffprobe...", 1.0, 1.0, 0.0, 1.0)
                    else:
                        if imgui.button("Download ffmpeg + ffprobe for loop extraction", width=290, height=25):
                            self.download_ffmpeg()
                        if imgui.is_item_hovered():
                            imgui.begin_tooltip()
                            imgui.text("Download ffmpeg + ffprobe (~100MB download, ~200MB installed)")
                            imgui.text("Enables perfect loop segment extraction from internal sounds")
                            imgui.text("Download happens in background, won't freeze UI")
                            imgui.end_tooltip()
            
            imgui.spacing()
            
            # Audio Timeline (reuse existing timeline rendering)
            self.render_audio_timeline()
        
        imgui.spacing()
    
    def run(self):
        """Main application loop"""
        self.init_window()
        
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.impl.process_inputs()
            
            # Check for theme updates
            if self.theme_manager.check_for_updates():
                self.reapply_theme()
            
            # Handle window dragging
            if self.dragging_window:
                if glfw.get_mouse_button(self.window, glfw.MOUSE_BUTTON_LEFT) == glfw.PRESS:
                    mouse_x, mouse_y = glfw.get_cursor_pos(self.window)
                    win_x, win_y = glfw.get_window_pos(self.window)
                    new_x = int(win_x + mouse_x - self.drag_offset_x)
                    new_y = int(win_y + mouse_y - self.drag_offset_y)
                    glfw.set_window_pos(self.window, new_x, new_y)
                else:
                    self.dragging_window = False
            
            imgui.new_frame()
            
            self.render_title_bar()
            self.render_main_window()
            
            # Set cursor to pointer when hovering over clickable items
            if imgui.is_any_item_hovered():
                glfw.set_cursor(self.window, self.hand_cursor)
            else:
                glfw.set_cursor(self.window, self.arrow_cursor)
            
            gl.glClearColor(0.1, 0.1, 0.1, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)
            
            imgui.render()
            self.impl.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)
        
        self.impl.shutdown()
        glfw.terminate()


if __name__ == '__main__':
    app = SoundsManagerApp()
    app.run()
