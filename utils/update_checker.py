"""
Update checker for CS2KZ-Mapping-Tools
Checks GitHub Releases for new versions and manages update process!!
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
import tempfile
import shutil
import subprocess
from datetime import datetime, timedelta

class UpdateChecker:
    def __init__(self):
        """Initialize the update checker"""
        self.github_repo = "jakkekz/CS2KZ-Mapping-Tools"
        self.github_releases_api = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
        self.last_check_time = None
        self.update_available = False
        self.latest_download_url = None
        self.latest_version = None
        self.latest_version_tag = None
        self.latest_version_date = None
        self.current_version_date = None
        self.current_version = self._get_current_version()
        
    def _get_current_version(self):
        """Get the current version from the executable or a version file"""
        try:
            # Try to read from version file
            if hasattr(sys, '_MEIPASS'):
                # Running as PyInstaller executable
                exe_path = sys.executable
                timestamp = os.path.getmtime(exe_path)
                # Store as UTC datetime for consistency with GitHub API
                self.current_version_date = datetime.fromtimestamp(timestamp)
                
                # Detect if running console version
                exe_name = os.path.basename(exe_path).lower()
                self.is_console_version = 'console' in exe_name
                
                print(f"[Update] Running as executable: {exe_path}")
                print(f"[Update] Console version detected: {self.is_console_version}")
                print(f"[Update] Executable timestamp (UTC): {timestamp}")
                print(f"[Update] Executable date (local): {self.current_version_date}")
                return timestamp
            else:
                # Running as script - use main.py timestamp
                main_py = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
                timestamp = os.path.getmtime(main_py)
                # Store as UTC datetime for consistency with GitHub API
                self.current_version_date = datetime.fromtimestamp(timestamp)
                self.is_console_version = False  # Default for script
                print(f"[Update] Running as script: {main_py}")
                print(f"[Update] Script timestamp (UTC): {timestamp}")
                print(f"[Update] Script date (local): {self.current_version_date}")
                return timestamp
        except Exception as e:
            print(f"[Update] Error getting current version: {e}")
            self.is_console_version = False
            return 0
    
    def should_check_for_updates(self):
        """Check if enough time has passed since last check (X minutes)"""
        if self.last_check_time is None:
            return True
        
        time_since_check = time.time() - self.last_check_time
        return time_since_check >= 150  # 2.5 minutes in seconds
    
    def check_for_updates(self):
        """Check GitHub Releases for new versions"""
        if not self.should_check_for_updates():
            print(f"[Update] Skipping check - last checked {time.time() - self.last_check_time:.0f}s ago")
            return self.update_available
        
        self.last_check_time = time.time()
        print(f"[Update] Checking for updates from GitHub Releases...")
        print(f"[Update] Current version timestamp: {self.current_version}")
        
        try:
            # Get the latest release from GitHub
            req = urllib.request.Request(
                self.github_releases_api,
                headers={'Accept': 'application/vnd.github.v3+json'}
            )
            
            print(f"[Update] Fetching: {self.github_releases_api}")
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                # Get release information
                published_at = data.get('published_at', '')
                release_tag = data.get('tag_name', 'unknown')
                print(f"[Update] Latest release: {release_tag} published at {published_at}")
                
                if not published_at:
                    print("[Update] No published_at field in release")
                    return False
                
                # Parse release timestamp
                release_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                release_timestamp = release_time.timestamp()
                print(f"[Update] Release timestamp: {release_timestamp}")
                
                # Compare with current version
                if release_timestamp > self.current_version:
                    print(f"[Update] Release is newer! ({release_timestamp} > {self.current_version})")
                    # Find the correct .exe asset based on current version type
                    assets = data.get('assets', [])
                    print(f"[Update] Found {len(assets)} assets")
                    
                    target_asset_name = None
                    for asset in assets:
                        name = asset.get('name', '')
                        print(f"[Update] Asset: {name}")
                        if name.endswith('.exe') and 'CS2KZ' in name and 'MappingTools' in name:
                            # Check if this matches the current version type
                            is_console_asset = 'console' in name.lower()
                            
                            if self.is_console_version == is_console_asset:
                                target_asset_name = name
                                self.update_available = True
                                self.latest_download_url = asset.get('browser_download_url')
                                self.latest_version = release_timestamp
                                self.latest_version_tag = release_tag
                                self.latest_version_date = release_time
                                print(f"[Update] ✓ Found matching version: {name} (console: {is_console_asset})")
                                print(f"[Update] Download URL: {self.latest_download_url}")
                                return True
                    
                    if not target_asset_name:
                        version_type = "console" if self.is_console_version else "windowed"
                        print(f"[Update] No matching {version_type} version found in assets")
                else:
                    print(f"[Update] Release is not newer ({release_timestamp} <= {self.current_version})")
                
        except urllib.error.URLError as e:
            print(f"[Update] Network error: {e}")
        except Exception as e:
            print(f"[Update] Error: {e}")
        
        self.update_available = False
        print("[Update] No update available")
        return False
    
    def download_and_install_update(self):
        """Download the latest version and replace the current executable"""
        if not self.update_available or not self.latest_download_url:
            print("[Update] No update available or no download URL")
            return False
        
        try:
            print(f"[Update] Starting update process...")
            # Get temp directory
            temp_dir = os.path.join(tempfile.gettempdir(), ".cs2kz-mapping-tools")
            update_dir = os.path.join(temp_dir, "update")
            
            # Create update directory
            os.makedirs(update_dir, exist_ok=True)
            print(f"[Update] Update directory: {update_dir}")
            
            # Download the new executable
            new_exe_path = os.path.join(update_dir, "CS2KZ-Mapping-Tools-new.exe")
            
            print(f"[Update] Downloading from {self.latest_download_url}...")
            urllib.request.urlretrieve(self.latest_download_url, new_exe_path)
            print(f"[Update] Downloaded to {new_exe_path}")
            
            if not os.path.exists(new_exe_path):
                print("[Update] Failed to download update - file doesn't exist")
                return False
            
            file_size = os.path.getsize(new_exe_path)
            print(f"[Update] Downloaded file size: {file_size} bytes")
            
            # Clear temp folder (except settings and Source2Viewer)
            print("[Update] Clearing temp folder...")
            self._clear_temp_folder(temp_dir)
            
            # Get current executable path
            if hasattr(sys, '_MEIPASS'):
                current_exe = sys.executable
                print(f"[Update] Current executable: {current_exe}")
            else:
                # Running as script - can't update
                print("[Update] Running as script - update only works for compiled executable")
                return False
            
            # Create a batch script to replace the executable
            batch_script = os.path.join(update_dir, "update.bat")
            print(f"[Update] Creating batch script: {batch_script}")
            with open(batch_script, 'w') as f:
                f.write('@echo off\n')
                f.write('echo Waiting for application to close...\n')
                f.write('timeout /t 5 /nobreak > nul\n')  # Wait longer for main app to close
                f.write(f'echo Replacing executable...\n')
                # Try to delete the old exe first (in case move fails)
                f.write(f'del /f /q "{current_exe}" 2>nul\n')
                f.write(f'move /y "{new_exe_path}" "{current_exe}"\n')
                f.write(f'if errorlevel 1 (\n')
                f.write(f'    echo Failed to replace executable\n')
                f.write(f'    echo Error: %%errorlevel%%\n')
                f.write(f'    pause\n')
                f.write(f'    exit /b 1\n')
                f.write(f')\n')
                f.write(f'echo Update successful!\n')
                f.write(f'echo Starting updated application: {current_exe}\n')
                f.write(f'echo.\n')
                # Use full path and proper quoting for start command
                f.write(f'cd /d "{os.path.dirname(current_exe)}"\n')
                f.write(f'start "" "{os.path.basename(current_exe)}"\n')
                f.write(f'if errorlevel 1 (\n')
                f.write(f'    echo Failed to start application\n')
                f.write(f'    echo Trying alternate method...\n')
                f.write(f'    "{current_exe}"\n')
                f.write(f')\n')
                f.write(f'timeout /t 2 /nobreak > nul\n')  # Brief delay before cleanup
                f.write(f'del "%~f0"\n')  # Delete the batch script itself
            
            print("[Update] Launching update script and exiting...")
            print(f"[Update] Batch script will replace: {current_exe}")
            print(f"[Update] With new file: {new_exe_path}")
            # Run the batch script with visible window for debugging
            subprocess.Popen(['cmd', '/c', batch_script])
            
            # Force immediate exit
            print("[Update] Exiting application for update...")
            import os as _os
            _os._exit(0)  # Immediate exit without cleanup
            
        except Exception as e:
            print(f"[Update] Error during update: {e}")
            return False
    
    def _clear_temp_folder(self, temp_dir):
        """Clear the temp folder but preserve settings and Source2Viewer"""
        try:
            if not os.path.exists(temp_dir):
                return
            
            # Files/folders to preserve (include both possible S2V names)
            preserve = ['settings.json', 'Source2Viewer-win.exe', 'Source2Viewer.exe', 'update']
            
            print(f"[Update] Clearing temp folder (preserving: {', '.join(preserve)})")
            
            for item in os.listdir(temp_dir):
                if item in preserve:
                    print(f"[Update] Preserving: {item}")
                    continue
                
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                        print(f"[Update] Removed file: {item}")
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                        print(f"[Update] Removed directory: {item}")
                except Exception as e:
                    print(f"[Update] Warning: Could not remove {item}: {e}")
                    
        except Exception as e:
            print(f"[Update] Error clearing temp folder: {e}")
    
    def restart_application(self):
        """Restart the application after update"""
        try:
            if hasattr(sys, '_MEIPASS'):
                # Running as executable - exit and let batch script restart
                sys.exit(0)
            else:
                # Running as script
                python = sys.executable
                subprocess.Popen([python] + sys.argv)
                sys.exit(0)
            
        except Exception as e:
            print(f"Error restarting application: {e}")
            return False
