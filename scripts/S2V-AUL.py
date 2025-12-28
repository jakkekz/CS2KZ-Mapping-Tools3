import requests
import zipfile
import io
import os
import shutil
import subprocess
import time
import re
import platform
import ctypes
import sys
import tempfile

# Note: The win32api/win32con check is kept for local version checking.
# If these imports cause issues with your specific build, you can safely
# remove the try/except block below and the get_local_version function,
# which will force an update every time.
try:
    if platform.system() == 'Windows':
        import win32api
        import win32con
except ImportError:
    print("WARNING: 'pywin32' library not found. Local version checking will fail.")


def get_base_path():
    """
    Returns the persistent directory in the temp folder where Source2Viewer will be installed.
    Uses the same location as the settings file for consistency.
    """
    temp_dir = tempfile.gettempdir()
    base_path = os.path.join(temp_dir, '.CS2KZ-mapping-tools')
    
    # Create directory if it doesn't exist
    os.makedirs(base_path, exist_ok=True)
    
    return base_path


# --- Core Path Definitions ---
BASE_PATH = get_base_path()
# INSTALL_DIR is the permanent directory in temp folder
INSTALL_DIR = BASE_PATH
# APP_EXECUTABLE is the path to the NEW executable in the temp folder.
APP_EXECUTABLE = os.path.join(INSTALL_DIR, "Source2Viewer.exe")
XML_FILE_TO_DELETE = os.path.join(INSTALL_DIR, "ValveResourceFormat.xml")
# -----------------------------

VERSION_CHECK_URL = "https://api.github.com/repos/ValveResourceFormat/ValveResourceFormat/commits/master"
DOWNLOAD_URL = "https://nightly.link/ValveResourceFormat/ValveResourceFormat/workflows/build/master/Source2Viewer.zip"

COMMON_LOCALE_PATHS = [
    '\\StringFileInfo\\040904B0\\ProductVersion',
    '\\StringFileInfo\\000004B0\\ProductVersion',
    '\\StringFileInfo\\040004B0\\ProductVersion'
]

def set_hidden_attribute(filepath):
    # (Function implementation is omitted for brevity but should be included)
    if platform.system() == 'Windows':
        try:
            if 'win32con' in sys.modules:
                FILE_ATTRIBUTE_HIDDEN = win32con.FILE_ATTRIBUTE_HIDDEN
            else:
                FILE_ATTRIBUTE_HIDDEN = 0x02

            ctypes.windll.kernel32.SetFileAttributesW(filepath, FILE_ATTRIBUTE_HIDDEN)
        except Exception as e:
            print(f"WARNING: Could not set hidden attribute on {filepath}: {e}")

def get_remote_version():
    # (Function implementation is omitted for brevity but should be included)
    print(f"Checking remote version using GitHub API: {VERSION_CHECK_URL}")
    try:
        response = requests.get(VERSION_CHECK_URL, timeout=10)
        response.raise_for_status()

        commit_data = response.json()
        full_sha = commit_data.get('sha')

        if full_sha:
            version_string = full_sha[:8].upper()
            print(f"Found remote version (Commit SHA): {version_string}")
            return version_string
        else:
            print("ERROR: Could not find the commit SHA in the GitHub API response.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Could not connect to GitHub API: {e}")
        return None
    except Exception as e:
        print(f"ERROR processing GitHub API response: {e}")
        return None

def get_local_version():
    # (Function implementation is omitted for brevity but should be included)
    if not os.path.exists(APP_EXECUTABLE):
        print("Application executable not found. Assuming '0' (oldest).")
        return '0'

    if platform.system() != 'Windows' or 'win32api' not in sys.modules:
        print("Local version checking is disabled or failed (Not Windows/pywin32 missing). Assuming '0'.")
        return '0'

    try:
        for path in COMMON_LOCALE_PATHS:
            try:
                full_version_string = win32api.GetFileVersionInfo(APP_EXECUTABLE, path)

                match = re.search(r'\+([a-fA-F0-9]{6,8})', full_version_string)

                if match:
                    sha_version = match.group(1).upper()

                    locale_id = path.split('\\')[2]
                    print(f"Found local version (Embedded SHA via {locale_id}): {sha_version}")

                    return sha_version

            except Exception:
                continue

        print("WARNING: Could not find the SHA in the 'ProductVersion' using common locale paths.")

        info = win32api.GetFileVersionInfo(APP_EXECUTABLE, '\\')
        ms_file_version = info['FileVersionMS']
        ls_file_version = info['FileVersionLS']
        major = win32api.HIWORD(ms_file_version)
        minor = win32api.LOWORD(ms_file_version)
        build = win32api.HIWORD(ls_file_version)
        revision = win32api.LOWORD(ls_file_version)
        numerical_version = f"{major}.{minor}.{build}.{revision}"
        print(f"Numerical version found: {numerical_version}. Forcing update.")

        return '0'

    except Exception as e:
        print(f"ERROR reading EXE metadata: {e}. Assuming '0'.")
        return '0'

def download_and_install(new_version):
    print(f"\n--- Starting Update to Version {new_version} ---")
    
    # Create download flag file
    download_flag = os.path.join(BASE_PATH, '.s2v_downloading')
    try:
        with open(download_flag, 'w') as f:
            f.write('1')
    except:
        pass

    try:
        print(f"Downloading build from {DOWNLOAD_URL}...")
        download_response = requests.get(DOWNLOAD_URL, stream=True, timeout=300)
        download_response.raise_for_status()

        zip_data = io.BytesIO(download_response.content)

        # Cleanup: Remove old Source2Viewer.exe before extraction
        if os.path.exists(APP_EXECUTABLE):
            print("Removing old Source2Viewer executable...")
            try:
                # This should only fail if Source2Viewer is running from a *previous* launch
                # AND Source2Viewer was NOT launched via this wrapper script.
                os.remove(APP_EXECUTABLE)
            except Exception as e:
                print(f"CRITICAL WARNING: Could not remove old Source2Viewer.exe. Please ensure it is fully closed. Error: {e}")
                # You may choose to exit here if the error is fatal for the update

        os.makedirs(INSTALL_DIR, exist_ok=True)

        print("Extracting new files...")
        with zipfile.ZipFile(zip_data, 'r') as zip_ref:
            # Extract everything directly into the persistent directory (INSTALL_DIR)
            zip_ref.extractall(INSTALL_DIR)

        if os.path.exists(XML_FILE_TO_DELETE):
            print(f"Removing unwanted XML file: {os.path.basename(XML_FILE_TO_DELETE)}")
            try:
                os.remove(XML_FILE_TO_DELETE)
            except Exception as e:
                print(f"Warning: Could not remove XML file {XML_FILE_TO_DELETE}. {e}")

        # Save version info to file for display in GUI
        version_file = os.path.join(INSTALL_DIR, 'cs2kz_versions.txt')
        try:
            # Read existing versions
            versions = {}
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.strip().split('=', 1)
                            versions[key] = value
            
            # Update Source2Viewer version (this is now the latest)
            versions['source2viewer'] = new_version
            versions['source2viewer_latest'] = new_version  # Store latest known version
            
            # Write back all versions
            with open(version_file, 'w') as f:
                for key, value in versions.items():
                    f.write(f"{key}={value}\n")
            
            print(f"Saved Source2Viewer version: {new_version}")
        except Exception as e:
            print(f"Warning: Could not save version info: {e}")

        print("Update complete!")
        
        # Remove download flag on success
        download_flag = os.path.join(BASE_PATH, '.s2v_downloading')
        try:
            if os.path.exists(download_flag):
                os.remove(download_flag)
        except:
            pass
        
        return True

    except requests.exceptions.RequestException as e:
        print(f"ERROR during download: {e}")
        # Remove download flag on error
        download_flag = os.path.join(BASE_PATH, '.s2v_downloading')
        try:
            if os.path.exists(download_flag):
                os.remove(download_flag)
        except:
            pass
        return False
    except zipfile.BadZipFile:
        print("ERROR: Downloaded file is not a valid ZIP archive.")
        # Remove download flag on error
        download_flag = os.path.join(BASE_PATH, '.s2v_downloading')
        try:
            if os.path.exists(download_flag):
                os.remove(download_flag)
        except:
            pass
        return False
    except Exception as e:
        print(f"An unexpected error occurred during installation: {e}")
        # Remove download flag on error
        download_flag = os.path.join(BASE_PATH, '.s2v_downloading')
        try:
            if os.path.exists(download_flag):
                os.remove(download_flag)
        except:
            pass
        return False

def launch_app():
    if not os.path.exists(APP_EXECUTABLE):
        print(f"ERROR: Executable not found at {APP_EXECUTABLE}. Cannot launch.")
        return False

    print(f"\nLaunching Source2Viewer: {APP_EXECUTABLE}")
    try:
        # CRITICAL CHANGE: Use Popen for non-blocking launch.
        # This launches Source2Viewer and immediately returns control to the wrapper script.
        subprocess.Popen([APP_EXECUTABLE])

        print("Source2Viewer launched successfully. Exiting wrapper script immediately.")
        return True

    except Exception as e:
        print(f"ERROR launching application: {e}")
        return False

def main():
    remote_version = get_remote_version()

    if remote_version is None:
        sys.exit(1)

    local_version = get_local_version()

    if remote_version != local_version:
        print(f"\nUpdate needed! Local: {local_version}, Remote: {remote_version}")

        success = download_and_install(remote_version)
        if not success:
            sys.exit(1)
    else:
        print("\nLocal version is up-to-date. No update necessary.")
        
        # Update the cache file with current version info
        version_file = os.path.join(BASE_PATH, 'cs2kz_versions.txt')
        versions = {}
        
        # Read existing versions
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line:
                            key, value = line.split('=', 1)
                            versions[key.strip()] = value.strip()
            except Exception as e:
                print(f"Warning: Could not read version file: {e}")
        
        # Update Source2Viewer version info
        versions['source2viewer'] = local_version
        versions['source2viewer_latest'] = remote_version
        
        # Write back to file
        try:
            with open(version_file, 'w') as f:
                for key, value in versions.items():
                    f.write(f"{key}={value}\n")
            print(f"Updated version cache: source2viewer={local_version}, source2viewer_latest={remote_version}")
        except Exception as e:
            print(f"Warning: Could not update version file: {e}")


    # This call will launch Source2Viewer non-blockingly and return immediately.
    app_launched_and_closed = launch_app()

    # If the launch was successful, the wrapper script exits immediately,
    # closing the console window and allowing PyInstaller's bootloader to clean up its temp files.
    if app_launched_and_closed:
        print("Exiting wrapper script immediately to initiate PyInstaller cleanup.")
        sys.exit(0)
    else:
        print("Application launch failed. Closing wrapper.")
        sys.exit(1)

if __name__ == "__main__":
    main()
